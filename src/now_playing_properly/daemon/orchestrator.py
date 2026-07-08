import asyncio
from .config import FDS
from .config import Config
from .socket_server import Server
from .plugins import PluginExecutor
from .plugin_helpers import load_all_plugins
from .queue_types import MessageEvent, SeekEvent, UpdateEvent, PluginResponseEvent
from ..common.protocol import (
    Message,
    DataPayload,
    PayloadType,
    StatusPayload,
    CommandPayload,
    ResponsePayload,
)
from .player import Player
from sdbus import sd_bus_open_user
from ..common.command import Commands
from .log_manager import setup_logging
from ..common.metadata_spec import AudioMetadata
from sdbus_async.dbus_daemon import FreedesktopDbus
from .interface import MprisPlayerInterface, MprisRootInterface, DbusPropertiesInterface

logger = setup_logging()


class App:
    def __init__(self, config: Config, fds: FDS):
        self.config = config
        self.fds = fds
        self.outbound: asyncio.Queue[MessageEvent] = asyncio.Queue()
        self.inbound: asyncio.Queue[MessageEvent] = asyncio.Queue()
        self.metadata_event: asyncio.Queue[UpdateEvent] = asyncio.Queue()
        self.plugin_submit: asyncio.Queue[AudioMetadata] = asyncio.Queue()
        self.plugin_complete: asyncio.Queue[PluginResponseEvent] = asyncio.Queue()
        self.server = Server(fds.main_sock_fd, self.inbound, self.outbound)
        self.plugin_executor = PluginExecutor(
            load_all_plugins(config), config, self.plugin_submit, self.plugin_complete
        )
        self.players: dict[str, Player] = {}
        self.player_last_event: dict[str, UpdateEvent] = {}
        self.sbus = sd_bus_open_user()
        self.tasks = []

    async def __aenter__(self):
        await self.server.start()
        await self.plugin_executor.start()
        self.tasks = [
            asyncio.create_task(self._player_listener()),
            asyncio.create_task(self._plugin_route()),
            asyncio.create_task(self._plugin_out_route()),
        ]
        return self

    async def __aexit__(self):
        await self.server.stop()
        await self.plugin_executor.stop()
        futures = [
            self.outbound.join(),
            self.inbound.join(),
            self.metadata_event.join(),
            self.plugin_submit.join(),
            self.plugin_complete.join(),
        ]
        map(asyncio.Task.cancel, self.tasks)
        await asyncio.wait(futures + self.tasks)

    async def _player_listener(self):
        proxy = FreedesktopDbus(self.sbus)
        try:
            async for name, new_owner, old_owner in proxy.name_owner_changed:
                if (
                    name
                    and new_owner
                    and not old_owner
                    and name.startswith("org.mpris.MediaPlayer2")
                ):
                    logger.info(
                        f"Player {name.split(".")[-1]} just connectedk, registering"
                    )
                    player = Player(
                        name.split(".")[-1],
                        MprisPlayerInterface(self.sbus),
                        MprisRootInterface(self.sbus),
                        DbusPropertiesInterface(self.sbus),
                        self.metadata_event,
                    )
                    self.players[player.name] = player
                    player.start()
                    logger.info(f"Player {player.name} registered")
                elif (
                    name
                    and not new_owner
                    and old_owner
                    and name.startswith("org.mpris.MediaPlayer2")
                    and name.split(".")[-1] in self.players
                ):
                    logger.info(
                        f"Player {name.split(".")[-1]} disconnected, unregistering"
                    )
                    player = self.players[name.split(".")[-1]]
                    await player.stop()
                    logger.info(f"Player {player.name} unregistered")
                    del self.players[name.split(".")[-1]]
        except asyncio.CancelledError:
            for n in self.players:
                await self.players[n].stop()
                del self.players[n]
            return

    async def _plugin_route(self):
        try:
            while True:
                event = await self.metadata_event.get()
                if event.metadata is not None:
                    self.player_last_event[event.player] = event
                    await self.plugin_submit.put(event)
                else:
                    message = MessageEvent(
                        broadcast=True,
                        message=Message(
                            PayloadType.STATUS,
                            StatusPayload(
                                event.player,
                                event.status,
                                event.start_time + event.elapsed_time,
                                event.status in {"Paused", "Stopped"},
                            ),
                        ),
                    )
                    await self.outbound.put(message)
                self.metadata_event.task_done()

        except asyncio.CancelledError:
            self.player_last_event = {}
            return

    async def _plugin_out_route(self):
        try:
            while True:
                event = await self.plugin_complete.get()

                message = MessageEvent(
                    broadcast=True,
                    message=Message(
                        PayloadType.DATA, DataPayload(event.metadata, event.plugin_data)
                    ),
                )
                self.plugin_complete.task_done()
                await self.outbound.put(message)
        except asyncio.CancelledError:
            return

    async def _resolve_commands(self):
        """SCOPE CREEP, NO COMMANDS BAKA, even though i could bwaa"""
        try:
            while True:
                event = await self.inbound.get()
                self.inbound.task_done()

        except asyncio.CancelledError:
            return
