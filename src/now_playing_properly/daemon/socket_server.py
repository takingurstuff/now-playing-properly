import array
import struct
import socket
import asyncio
from ..common.protocol import Message
from .queue_types import MessageEvent
from .log_manager import setup_logging
from typing import Dict, Set, List, Union, Optional

logger = setup_logging()


class Server:
    def __init__(
        self,
        sock_fd: int,
        inbound_queue: asyncio.Queue[MessageEvent],
        outbound_queue: asyncio.Queue[MessageEvent],
    ):
        self.sock_fd = sock_fd
        self._server: asyncio.Server | None = None
        self._queue_in = inbound_queue
        self._queue_out = outbound_queue

        self._active_tasks: Set[asyncio.Task] = set()
        self._clients: Dict[int, tuple[asyncio.StreamWriter, socket.socket]] = {}

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()

        if (
            exc_type is None
            and hasattr(self, "_crashed_exception")
            and self._crashed_exception
        ):
            raise self._crashed_exception

        return False

    async def start(self):
        """Starts the UNIX Domain Socket server and background queue listeners."""
        sock = socket.fromfd(self.sock_fd, socket.AF_UNIX, socket.SOCK_STREAM)
        self.loop = asyncio.get_running_loop()
        self._server = await asyncio.start_unix_server(self._accept_client, sock=sock)

        server_task = asyncio.create_task(self._server.serve_forever())
        self._outbound_task = asyncio.create_task(self._process_outbound())
        self._critical_tasks = [server_task, self._outbound_task]
        self._active_tasks.update(self._critical_tasks)
        self._supervisor_task = asyncio.create_task(self._supervise_tasks())

        logger.info("Server listening on UNIX Domain Socket...")

    async def _supervise_tasks(self):
        """Monitors background loops. If one crashes, triggers server shutdown."""
        try:
            done, pending = await asyncio.wait(
                self._critical_tasks, return_when=asyncio.FIRST_COMPLETED
            )
            for task in done:
                exc = task.exception()
                if exc:
                    logger.exception(
                        f"Critical server task failed: {task.get_coro()} | Error: {exc}"
                    )
                    self._crashed_exception = exc
        except asyncio.CancelledError:
            pass

    async def _process_outbound(self):
        """Listens for Outbound Message instances on the queue and sends them."""
        try:
            while True:
                msg_packet = await self._queue_out.get()

                # msg_packet is expected to contain a .message (Message class instance)
                if getattr(msg_packet, "broadcast", False):
                    await self.broadcast(msg_packet.message)
                elif isinstance(msg_packet.client_id, list):
                    for cid in msg_packet.client_id:
                        await self.send_to(cid, msg_packet.message)
                elif isinstance(msg_packet.client_id, int):
                    await self.send_to(msg_packet.client_id, msg_packet.message)

                self._queue_out.task_done()
        except asyncio.CancelledError:
            logger.info("Outbound queue processor stopped.")

    def _accept_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ):
        """Callback triggered for every new connection."""
        task = asyncio.create_task(self._handle_client(reader, writer))
        self._active_tasks.add(task)
        task.add_done_callback(self._active_tasks.discard)

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ):
        """Manages the lifecycle of a single client connection using Protocol-level parsing."""
        client_id = id(writer)
        self._clients[client_id] = writer
        logger.info(
            f"Client {client_id} connected. Active connections: {len(self._clients)}"
        )

        try:
            while True:
                # 1. Read the constant framing minimum header width first (9 bytes: 4B Magic + 1B Type + 4B Size)
                try:
                    header_bytes = await reader.readexactly(9)
                except asyncio.IncompleteReadError:
                    logger.info(f"Client {client_id} disconnected gracefully.")
                    break

                # Extract the size parameter from the standard protocol position to know what remains
                _, payload_length = struct.unpack_from("=BI", header_bytes, 4)

                # 2. Read the remaining payload + 4-byte suffix magic footprint altogether
                remaining_bytes = await reader.readexactly(payload_length + 4)
                full_frame = header_bytes + remaining_bytes

                # 3. Delegate absolute structural validation and instantiation to the Message layer
                # Companion shared memory descriptors are resolved using collected references
                message = Message.deserialize(full_frame)

                # 4. Push message object down the internal stream line
                # Expecting down-stream consumers to handle wrapping context mapping structures if necessary
                await self._queue_in.put(
                    MessageEvent(client_id=client_id, message=message)
                )

        except (ValueError, TypeError) as e:
            logger.warning(
                f"Protocol Violation (Client {client_id}): {e}. Disconnecting."
            )
        except asyncio.CancelledError:
            logger.info(f"Task for client {client_id} was cancelled.")
        except Exception as e:
            logger.error(f"Unexpected error with client {client_id}: {e}")
        finally:
            self._clients.pop(client_id, None)
            writer.close()
            await writer.wait_closed()
            logger.info(f"Client {client_id} connection closed.")

    async def send_to(self, client_id: int, message: Message):
        """Sends a serialized protocol message to a specific client by ID."""
        writer, sock = self._clients.get(client_id)
        if not writer:
            logger.warning(
                f"Cannot send: Client {client_id} not found or already disconnected."
            )
            return

        try:
            data, fds = message.serialize()
            writer.write(data)
            if fds:
                fds_data = array.array("i", fds)
                ancdata = [(socket.SOL_SOCKET, socket.SCM_RIGHTS, fds_data.tobytes())]
            if fds:
                await self.loop.run_in_executor(None, sock.sendmsg, [data], ancdata)
            else:
                await writer.drain()
            logger.debug(f"Protocol Message sent to {client_id}.")
        except Exception as e:
            logger.error(f"Failed to send message to client {client_id}: {e}")

    async def broadcast(self, message: Message):
        """Sends a serialized protocol message to all currently connected clients concurrently."""
        if not self._clients:
            return

        frame, fds = message.serialize()
        fds_data = array.array("i", fds)
        ancdata = [(socket.SOL_SOCKET, socket.SCM_RIGHTS, fds_data.tobytes())]
        drain_tasks = []

        for client_id, ws in self._clients.items():
            writer, sock = ws
            try:
                if not fds:
                    writer.write(frame)
                    drain_tasks.append(writer.drain())
                else:
                    drain_tasks.append(
                        self.loop.run_in_executor(None, sock.sendmsg, [frame], ancdata)
                    )
            except Exception as e:
                logger.error(
                    f"Failed to write to client {client_id} during broadcast: {e}"
                )

        if drain_tasks:
            results = await asyncio.gather(*drain_tasks, return_exceptions=True)
            for e in results:
                if isinstance(e, Exception):
                    logger.warning(
                        f"Broadcast encountered an error while draining: {e}"
                    )

    async def stop(self):
        """Gracefully shuts down the server and disconnects all clients."""
        logger.info("Stopping server...")
        if self._server:
            self._server.close()
            await self._server.wait_closed()

        if self._supervisor_task:
            self._supervisor_task.cancel()

        for task in self._active_tasks:
            task.cancel()

        if self._active_tasks:
            await asyncio.gather(*self._active_tasks, return_exceptions=True)

        logger.info("Server stopped.")
