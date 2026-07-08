import time
import random
import asyncio
from .log_manager import setup_logging
from .queue_types import UpdateEvent, SeekEvent
from ..common.metadata_spec import AudioMetadata
from typing import Any, Dict, List, Literal, Optional, Union
from .interface import MprisPlayerInterface, MprisRootInterface, DbusPropertiesInterface

logger = setup_logging()


class Player:
    def __init__(
        self,
        player_name: str,
        mpris_player_interface: MprisPlayerInterface,
        mpris_root_interface: MprisRootInterface,
        dbus_properties_interface: DbusPropertiesInterface,
        event_queue: asyncio.Queue[Union[UpdateEvent, SeekEvent]],
    ) -> None:
        self.interface: MprisPlayerInterface = mpris_player_interface
        self.root_interface = mpris_root_interface
        self.dbus_properties_interface = dbus_properties_interface
        self.name: str = player_name
        self.active: bool = True
        self.last_active: int = 0
        self.start_time: int = 0
        self.elapsed_time: int = 0

        self.metadata: Optional[AudioMetadata] = None
        self.status: Literal["Playing", "Paused", "Stopped"] = "Stopped"

        self.metadata_lock: asyncio.Lock = asyncio.Lock()

        self.last_parsed_metadata: Optional[AudioMetadata] = None
        self.event_queue = event_queue
        self.listen_task: Optional[asyncio.Task] = None

    def start(self):
        self.listen_task = asyncio.create_task(self.update_handler())

    async def stop(
        self,
    ):
        """
        look i know naming is idiotic. \n
        stop is a public method, it kills the event listener and makes the object safe for disposal \n
        _stop is a private state tracking method, it sets the player state to stopped
        """
        self.listen_task.cancel()
        await self.listen_task

    def _pause(self, send_event=True) -> None:
        if self.status == "Paused":
            return
        cur = time.time() * 1_000_000
        self.active = False
        self.status = "Paused"
        self.elapsed_time += cur - self.start_time
        self.start_time = cur
        self.last_active = cur
        if send_event:
            self.event_queue.put_nowait(
                UpdateEvent(
                    self.name,
                    "Paused",
                    None,
                    self.start_time,
                    self.elapsed_time,
                    random.randbytes(4),
                )
            )

    def _play(self, send_event=True) -> None:
        if self.status == "Playing":
            return
        self.status = "Playing"
        cur = time.time() * 1_000_000
        self.start_time = cur
        self.active = True
        if send_event:
            self.event_queue.put_nowait(
                UpdateEvent(
                    self.name,
                    "Playing",
                    None,
                    self.start_time,
                    self.elapsed_time,
                    random.randbytes(4),
                )
            )

    def _stop(self, send_event=True) -> None:
        cur = time.time() * 1_000_000
        self.status = "Stopped"
        self.active = False
        self.last_active = cur
        self.elapsed_time = 0
        self.metadata = None
        self.last_parsed_metadata = None
        if send_event:
            self.event_queue.put_nowait(
                UpdateEvent(
                    self.name,
                    "Stopped",
                    None,
                    self.start_time,
                    self.elapsed_time,
                    random.randbytes(4),
                )
            )

    async def on_seek(self, send_event=True) -> None:
        """Handler for the Seeked signal, the Seeked signal is not part of PropertiesChanged"""
        self.elapsed_time = await self.interface.Position
        self.start_time = time.time() * 1_000_000

        if send_event:
            await self.event_queue.put(
                SeekEvent(self.name, self.start_time, self.elapsed_time)
            )

    async def seek_listener(self):
        async for _ in self.interface.Seeked:
            await self.on_seek()

    def _unpack_sdbus_variant(self, value: Any) -> Any:
        """Helper to unpack sdbus (signature, value) tuples."""
        if isinstance(value, tuple) and len(value) == 2 and isinstance(value[0], str):
            return value[1]
        return value

    async def set_metadata(
        self, raw_metadata: Dict[str, Any], send_event=True
    ) -> AudioMetadata | None:
        async with self.metadata_lock:
            # 1. Unpack sdbus variants
            cleaned_metadata = {
                k: self._unpack_sdbus_variant(v) for k, v in raw_metadata.items()
            }

            # 2. Parse and validate through Pydantic
            try:
                parsed_model = AudioMetadata(**cleaned_metadata)
            except Exception as e:
                logger.error(f"[{self.name}] Failed to parse metadata: {e}")
                return

            # 3. Check for redundant metadata signals
            if self.last_parsed_metadata:
                is_redundant = (
                    parsed_model.title == self.last_parsed_metadata.title
                    and parsed_model.url == self.last_parsed_metadata.url
                    and parsed_model.art_url == self.last_parsed_metadata.art_url
                    and parsed_model.artist == self.last_parsed_metadata.artist
                )

                if is_redundant:
                    logger.debug(
                        f"[{self.name}] Redundant metadata update received. Skipping processing."
                    )

                    # Handle edge case where only the length changed on a redundant broadcast
                    if parsed_model.duration != self.last_parsed_metadata.duration:
                        self.last_parsed_metadata.duration = parsed_model.duration
                        self.metadata.duration = parsed_model.duration
                        await self.on_seek(send_event)
                    return

            self.metadata = parsed_model
            if send_event:
                await self.event_queue.put(
                    UpdateEvent(
                        self.name, None, parsed_model, None, None, random.randbytes(4)
                    )
                )
            else:
                return parsed_model

    async def update_status(
        self, status: Literal["Playing", "Paused", "Stopped"]
    ) -> None:
        match status:
            case "Playing":
                self._play()
            case "Paused":
                self._pause()
            case "Stopped":
                self._stop()
            case _:
                raise ValueError(f"Unexpected Status: {status}")

    async def update_handler(
        self,
    ) -> None:
        try:
            async for (
                interface_name,
                changed_properties,
                invalidated_properties,
            ) in self.dbus_properties_interface.PropertiesChanged:
                """Listener for the PropertiesChanged signal"""
                changed_properties = {
                    k: self._unpack_sdbus_variant(v)
                    for k, v in changed_properties.items()
                }

                if "PlaybackStatus" in changed_properties:
                    status: Literal["Playing", "Paused", "Stopped"] = (
                        changed_properties["PlaybackStatus"]
                    )
                    await self.update_status(status)

                if "Metadata" in changed_properties:
                    logger.debug(f"[{self.name}] Metadata updated.")
                    await self.set_metadata(changed_properties["Metadata"])
                    await self.on_seek()
        except asyncio.CancelledError:
            return

    async def state_sync(self) -> None:
        """CALL ON FIRST CONNECT ONLY
        Synchronizes the state with the actual player
        """
        metadata = await self.interface.Metadata
        status = await self.interface.PlaybackStatus

        match status:
            case "Playing":
                self._play(send_event=False)
            case "Paused":
                self._pause(send_event=False)
            case "Stopped":
                self._stop(send_event=False)
            case _:
                raise ValueError(f"Unexpected Status: {status}")

        metadata = await self.set_metadata(metadata, send_event=False)
        await self.on_seek(send_event=False)

        await self.event_queue.put(
            UpdateEvent(
                self.name,
                status,
                metadata,
                self.start_time,
                self.elapsed_time,
                random.randbytes(4),
            )
        )
