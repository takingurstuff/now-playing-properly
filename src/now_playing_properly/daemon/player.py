import time
import random
import asyncio
from .log_manager import setup_logging
from typing import Any, Dict, List, Literal, Optional, Union
from ..common.metadata_spec import AudioMetadata, PlayerProperties
from ..common.communication_models import (
    Actions,
    SeekEvent,
    UpdateEvent,
    SeekRequest,
    ActionRequest,
)
from ..common.interfaces import (
    MediaPlayer2Interface,
    MediaPlayer2PlayerInterface,
)
from sdbus import SdBus
from .helpers import teto
from .config import Config
from sdbus_async.dbus_daemon import FreedesktopDbus

logger = setup_logging()


class Player:
    def __init__(
        self,
        player_name: str,
        mpris_player_interface: MediaPlayer2PlayerInterface,
        mpris_root_interface: MediaPlayer2Interface,
        event_queue: asyncio.Queue[Union[UpdateEvent, SeekEvent]],
        request_queue: asyncio.Queue[Union[ActionRequest, SeekRequest]],
    ) -> None:
        self.interface = mpris_player_interface
        self.root_interface = mpris_root_interface
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
        self.request_queue = request_queue
        self.listen_task: Optional[asyncio.Task] = None
        self.request_task: Optional[asyncio.Task] = None
        self.props: Optional[PlayerProperties] = None

    def start(self):
        self.listen_task = asyncio.create_task(self.update_handler())
        self.request_task = asyncio.create_task(self.requests_handler())

    async def stop(
        self,
    ):
        """
        look i know naming is idiotic. \n
        stop is a public method, it kills the event listener and makes the object safe for disposal \n
        _stop is a private state tracking method, it sets the player state to stopped
        """
        self.listen_task.cancel()
        self.request_task.cancel()
        await asyncio.gather(self.listen_task, self.request_task)

    def _pause(self) -> None:
        if self.status == "Paused":
            return
        cur = time.time() * 1_000_000
        self.active = False
        self.status = "Paused"
        self.elapsed_time += cur - self.start_time
        self.start_time = cur
        self.last_active = cur

    def _play(self) -> None:
        if self.status == "Playing":
            return
        self.status = "Playing"
        cur = time.time() * 1_000_000
        self.start_time = cur
        self.active = True

    def _stop(self) -> None:
        cur = time.time() * 1_000_000
        self.status = "Stopped"
        self.active = False
        self.last_active = cur
        self.elapsed_time = 0
        self.metadata = None
        self.last_parsed_metadata = None

    async def on_seek(self) -> None:
        """Handler for the Seeked signal, the Seeked signal is not part of PropertiesChanged"""
        self.elapsed_time = await self.interface.position
        self.start_time = time.time() * 1_000_000

    async def seek_listener(self):
        async for seeked_ms in self.interface.seeked:
            await self.on_seek()

    def _miku(self, value: Any) -> Any:
        """ooeeoo"""
        if isinstance(value, tuple) and len(value) == 2 and isinstance(value[0], str):
            return value[1]
        return value

    async def set_metadata(self, raw_metadata: Dict[str, Any]) -> AudioMetadata:
        async with self.metadata_lock:
            # 1. Unpack sdbus variants
            cleaned_metadata = {k: self._miku(v) for k, v in raw_metadata.items()}

            # 2. Parse and validate through Pydantic
            try:
                parsed_model = AudioMetadata.from_dbus(cleaned_metadata)
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
                        await self.on_seek()
                    return

            self.metadata = parsed_model
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
            ) in self.interface.properties_changed:
                """Listener for the PropertiesChanged signal"""
                changed_properties = {
                    k: self._miku(v) for k, v in changed_properties.items()
                }

                uevent = UpdateEvent(self.name, id=random.randbytes(4))
                if "PlaybackStatus" in changed_properties:
                    status: Literal["Playing", "Paused", "Stopped"] = (
                        changed_properties["PlaybackStatus"]
                    )
                    await self.update_status(status)
                    uevent.status = self.status
                    uevent.start_time = self.start_time
                    uevent.elapsed_time = self.elapsed_time

                if "Metadata" in changed_properties:
                    logger.debug(f"[{self.name}] Metadata updated.")
                    await self.set_metadata(changed_properties["Metadata"])
                    uevent.metadata = self.metadata
                    await self.on_seek()
                    uevent.start_time = self.start_time
                    uevent.elapsed_time = self.elapsed_time

                if props := teto(changed_properties):
                    logger.debug(f"[{self.name}] Player Properties Changed.")
                    self.props = props
                    uevent.props = props

                await self.event_queue.put(uevent)

        except asyncio.CancelledError:
            return

    async def requests_handler(self) -> None:
        try:
            while True:
                request = await self.request_queue.get()
                logger.debug(f"[{self.name}] Received new request")
                if isinstance(request, SeekRequest):
                    logger.debug(f"[{self.name}] Seek Event received")
                    if request.offset:
                        logger.debug(
                            f"[{self.name}] Seek to {request.offset} (relative)"
                        )
                        await self.interface.seek(request.offset)
                    elif request.absolute:
                        logger.debug(
                            f"[{self.name}] Seek to {request.absolute} (absolute)"
                        )
                        await self.interface.set_position(
                            self.metadata.track_id, request.absolute
                        )
                elif isinstance(request, ActionRequest):
                    logger.debug(f"[{self.name}] Action request received")
                    match request.action:
                        case Actions.NEXT:
                            logger.debug(f"[{self.name}] Next track")
                            await self.interface.next()
                        case Actions.PREVIOUS:
                            logger.debug(f"[{self.name}] Previous track")
                            await self.interface.previous()
                        case Actions.PLAY:
                            logger.debug(f"[{self.name}] Play")
                            await self.interface.play()
                        case Actions.PAUSE:
                            logger.debug(f"[{self.name}] Pause")
                            self.interface.pause()
                        case Actions.STOP:
                            logger.debug(f"[{self.name}] Stop")
                            self.interface.stop()
                        case Actions.PLAYPAUSE:
                            logger.debug(f"[{self.name}] PlayPause toggle")
                            self.interface.play_pause()
                        case Actions.STARTSHUFFLE:
                            logger.debug(f"[{self.name}] Shuffling")
                            self.interface.shuffle = True
                        case Actions.STOPSHUFFLE:
                            logger.debug(f"[{self.name}] Not Shuffling")
                            self.interface.shuffle = False
        except asyncio.CancelledError:
            return

    async def state_sync(self) -> None:
        """CALL ON FIRST CONNECT ONLY
        Synchronizes the state with the actual player
        """
        metadata = await self.interface.metadata
        status = await self.interface.playback_status
        volume = await self.interface.volume
        shuffle = await self.interface.shuffle
        loop_status = await self.interface.loop_status
        minrate = await self.interface.minimum_rate
        maxrate = await self.interface.maximum_rate
        rate = await self.interface.rate
        self.props = PlayerProperties(
            volume, shuffle, loop_status, minrate, maxrate, rate
        )

        match status:
            case "Playing":
                self._play()
            case "Paused":
                self._pause()
            case "Stopped":
                self._stop()
            case _:
                raise ValueError(f"Unexpected Status: {status}")

        metadata = await self.set_metadata(metadata)
        await self.on_seek()

        await self.event_queue.put(
            UpdateEvent(
                player=self.name,
                status=status,
                metadata=metadata,
                start_time=self.start_time,
                elapsed_time=self.elapsed_time,
                props=self.props,
                id=random.randbytes(4),
            )
        )

    def __ge__(self, other):
        if isinstance(other, Player):
            return (
                self.active and not other.active
                if self.active != other.active
                else self.last_active > other.last_active and not self.active
            )
        return False

    def __eq__(self, other):
        if isinstance(other, Player):
            return self.active == other.active and self.active
        return False


async def discover_initial(
    config: Config, conn: SdBus, dbus_daemon: FreedesktopDbus
) -> tuple[
    asyncio.Queue[Union[UpdateEvent, SeekRequest]],
    list[tuple[Player, asyncio.Queue[Union[ActionRequest, SeekRequest]]]],
]:
    equeue = asyncio.Queue()
    players = []
    for name in filter(
        lambda x: x.startswith("org.mpris.MediaPlayer2.")
        and x.split(".")[3].lower() not in config.general.player_name_blacklist,
        await dbus_daemon.list_names(),
    ):
        mpris_player_interface = MediaPlayer2PlayerInterface.new_proxy(
            name, "/org/mpris/MediaPlayer2", conn
        )
        mpris_root_interface = MediaPlayer2Interface.new_proxy(
            name, "/org/mpris/MediaPlayer2", conn
        )
        pname = name.split(".")[3].lower()
        req_queue = asyncio.Queue()
        pset = (
            Player(
                pname, mpris_player_interface, mpris_root_interface, equeue, req_queue
            ),
            req_queue,
        )
        players.append(pset)
    return equeue, players
