from __future__ import annotations

import time
import asyncio
from .config import Config
from .helpers import prep_metadata, wrap
from ..common.interfaces import MediaPlayer2PlayerInterface, MediaPlayer2Interface
from ..common.metadata_spec import (
    AudioMetadata,
    PlaybackStatus,
    PlayerProperties,
    PlayerProperties,
    PlaybackStatusMetadata,
)
from ..common.communication_models import (
    Actions,
    SeekEvent,
    SeekRequest,
    UpdateEvent,
    ServerInType,
    ServerOutType,
    ActionRequest,
    OpenURIRequest,
    SetRateRequest,
    SetVolumeRequest,
    PluginResponseEvent,
)

from typing import Any

from sdbus import (
    dbus_method_async,
    dbus_signal_async,
    dbus_property_async,
    DbusUnprivilegedFlag,
    DbusPropertyEmitsChangeFlag,
)


class MediaPlayer2PlayerServerInterface(MediaPlayer2PlayerInterface):
    def __init__(
        self,
        update_queue: asyncio.Queue[ServerOutType],
        request_queue: asyncio.Queue[ServerInType],
        config: Config,
    ):
        super().__init__()
        self.request_queue = request_queue
        self.update_queue = update_queue
        self.config = config
        self._playback_status: PlaybackStatus = PlaybackStatus.STOPPED
        self._metadata: AudioMetadata | None = None
        self._last_metadata_id = None
        self._plugin_extras: dict[str, dict[str, Any]] | None = None
        self._full_metadata: dict[str, tuple[str, Any]] | None = None
        self._position = 0
        self._stime = 0
        self._etime = 0
        self._props: PlayerProperties = PlayerProperties()

    async def start_serve(self):
        while True:
            to_update = {}
            should_emit_seek = False
            update = await self.update_queue.get()
            if isinstance(update, SeekEvent):
                self._stime = update.start_time
                self._etime = update.elapsed_time
            elif isinstance(update, UpdateEvent):
                if update.start_time and update.elapsed_time:
                    should_emit_seek = True
                    self._stime = update.start_time
                    self._etime = update.elapsed_time
                if update.metadata:
                    self._metadata = update.metadata
                    self._full_metadata = prep_metadata(self._metadata.to_dbus())
                    self._last_metadata_id = update.id
                    to_update["Metadata"] = (r"a{sv}", self._full_metadata)
                if update.props:
                    self._props = update.props
                    to_update.update(prep_metadata(update.props.to_dbus()))

            elif isinstance(update, PluginResponseEvent):
                if update.id == self._last_metadata_id:
                    self._plugin_extras = update.plugin_data
                    self._full_metadata = prep_metadata(
                        self._metadata.to_dbus(), self._plugin_extras
                    )
                    to_update["Metadata"] = (r"a{sv}", self._full_metadata)
            if should_emit_seek:
                self.seeked.emit(time.time() * 1_000_000 - self._stime + self._etime)
            if to_update:
                self.properties_changed.emit(
                    ("org.mpris.MediaPlayer2.Player", to_update, [])
                )

    @dbus_method_async(
        flags=DbusUnprivilegedFlag,
        result_args_names=(),
    )
    async def next(
        self,
    ) -> None:
        await self.request_queue.put(ActionRequest(Actions.NEXT))

    @dbus_method_async(
        flags=DbusUnprivilegedFlag,
        result_args_names=(),
    )
    async def previous(
        self,
    ) -> None:
        await self.request_queue.put(ActionRequest(Actions.PREVIOUS))

    @dbus_method_async(
        flags=DbusUnprivilegedFlag,
        result_args_names=(),
    )
    async def pause(
        self,
    ) -> None:
        await self.request_queue.put(ActionRequest(Actions.PAUSE))

    @dbus_method_async(
        flags=DbusUnprivilegedFlag,
        result_args_names=(),
    )
    async def play_pause(
        self,
    ) -> None:
        await self.request_queue.put(ActionRequest(Actions.PLAYPAUSE))

    @dbus_method_async(
        flags=DbusUnprivilegedFlag,
        result_args_names=(),
    )
    async def stop(
        self,
    ) -> None:
        await self.request_queue.put(ActionRequest(Actions.STOP))

    @dbus_method_async(
        flags=DbusUnprivilegedFlag,
        result_args_names=(),
    )
    async def play(
        self,
    ) -> None:
        await self.request_queue.put(ActionRequest(Actions.PLAY))

    @dbus_method_async(
        input_signature="x",
        flags=DbusUnprivilegedFlag,
        result_args_names=(),
    )
    async def seek(
        self,
        offset: int,
    ) -> None:
        await self.request_queue.put(SeekRequest(offset=offset))

    @dbus_method_async(
        input_signature="ox",
        flags=DbusUnprivilegedFlag,
        result_args_names=(),
    )
    async def set_position(
        self,
        track_id: str,
        position: int,
    ) -> None:
        await self.request_queue.put(SeekRequest(absolute=position))

    @dbus_method_async(
        input_signature="s",
        flags=DbusUnprivilegedFlag,
        result_args_names=(),
    )
    async def open_uri(
        self,
        uri: str,
    ) -> None:
        await self.request_queue.put(OpenURIRequest(uri))

    @dbus_method_async(
        result_signature="sh",
        flags=DbusUnprivilegedFlag,
        result_args_names=("MimeType", "Image"),
    )
    async def get_artwork_fd(
        self,
    ) -> tuple[str, int]:
        """Dummy Function, this method will not be implemented as it is more often than not unused and imlementing it could mean technical debt"""
        raise NotImplementedError

    @dbus_property_async(
        property_signature="s",
        flags=DbusPropertyEmitsChangeFlag,
    )
    def playback_status(self) -> str:
        match self.playback_status:
            case PlaybackStatus.PLAYING:
                return "Playing"
            case PlaybackStatus.PAUSED:
                return "Paused"
            case PlaybackStatus.STOPPED:
                return "Stopped"

    @dbus_property_async(
        property_signature="s",
        flags=DbusPropertyEmitsChangeFlag,
    )
    def loop_status(self) -> str:
        return (
            self._props.loop_status if self._props.loop_status is not None else "None"
        )

    @loop_status.setter
    async def setloopstatus(self, loop_status: str):
        if loop_status == self._props.loop_status:
            return
        await self.request_queue.put(
            ActionRequest(
                Actions.LOOPLIST
                if loop_status == "Playlist"
                else Actions.LOOPTRACK if loop_status == "Track" else Actions.NOLOOP
            )
        )

    @dbus_property_async(
        property_signature="d",
        flags=DbusPropertyEmitsChangeFlag,
    )
    def rate(self) -> float:
        return self._props.rate if self._props.rate is not None else 1.0

    @rate.setter
    async def setrate(self, rate: float):
        await self.request_queue.put(SetRateRequest(rate))

    @dbus_property_async(
        property_signature="b",
        flags=DbusPropertyEmitsChangeFlag,
    )
    def shuffle(self) -> bool:
        return self._props.shuffle if self._props.shuffle is not None else False

    @shuffle.setter
    async def setshuffle(self, shuffle: bool):
        if shuffle == self._props.shuffle:
            return
        await self.request_queue.put(
            ActionRequest(Actions.STARTSHUFFLE if shuffle else Actions.STOPSHUFFLE)
        )

    @dbus_property_async(
        property_signature="a{sv}",
        flags=DbusPropertyEmitsChangeFlag,
    )
    def metadata(self) -> dict[str, tuple[str, Any]]:
        return self._full_metadata

    @dbus_property_async(
        property_signature="d",
        flags=DbusPropertyEmitsChangeFlag,
    )
    def volume(self) -> float:
        return self._props.volume if self._props.volume is not None else 1.0

    @volume.setter
    async def setvolume(self, volume: float):
        self.request_queue.put_nowait(SetVolumeRequest(volume))

    @dbus_property_async(
        property_signature="x",
    )
    def position(self) -> int:
        cur = time.time() * 1_000_000
        pos = cur - self._stime + self._etime
        return int(pos)

    @dbus_property_async(
        property_signature="d",
        flags=DbusPropertyEmitsChangeFlag,
    )
    def minimum_rate(self) -> float:
        return self._props.minrate if self._props.minrate is not None else 0.0

    @dbus_property_async(
        property_signature="d",
        flags=DbusPropertyEmitsChangeFlag,
    )
    def maximum_rate(self) -> float:
        return self._props.maxrate if self._props.maxrate is not None else 5.0

    @dbus_property_async(
        property_signature="b",
        flags=DbusPropertyEmitsChangeFlag,
    )
    def can_go_next(self) -> bool:
        return True

    @dbus_property_async(
        property_signature="b",
        flags=DbusPropertyEmitsChangeFlag,
    )
    def can_go_previous(self) -> bool:
        return True

    @dbus_property_async(
        property_signature="b",
        flags=DbusPropertyEmitsChangeFlag,
    )
    def can_play(self) -> bool:
        return True

    @dbus_property_async(
        property_signature="b",
        flags=DbusPropertyEmitsChangeFlag,
    )
    def can_pause(self) -> bool:
        return True

    @dbus_property_async(
        property_signature="b",
        flags=DbusPropertyEmitsChangeFlag,
    )
    def can_seek(self) -> bool:
        return True

    @dbus_property_async(
        property_signature="b",
    )
    def can_control(self) -> bool:
        return True

    @dbus_signal_async(
        signal_signature="x",
        signal_args_names=("Position",),
    )
    def seeked(self) -> int:
        raise NotImplementedError


class MediaPlayer2ServerInterface(MediaPlayer2Interface):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @dbus_method_async(
        flags=DbusUnprivilegedFlag,
        result_args_names=(),
    )
    async def Raise(
        self,
    ) -> None:
        pass

    @dbus_method_async(
        flags=DbusUnprivilegedFlag,
        result_args_names=(),
    )
    async def quit(
        self,
    ) -> None:
        pass

    @dbus_property_async(
        property_signature="b",
        flags=DbusPropertyEmitsChangeFlag,
    )
    def can_quit(self) -> bool:
        return False

    @dbus_property_async(
        property_signature="b",
        flags=DbusPropertyEmitsChangeFlag,
    )
    def fullscreen(self) -> bool:
        return False

    @dbus_property_async(
        property_signature="b",
        flags=DbusPropertyEmitsChangeFlag,
    )
    def can_set_fullscreen(self) -> bool:
        return False

    @dbus_property_async(
        property_signature="b",
        flags=DbusPropertyEmitsChangeFlag,
    )
    def can_raise(self) -> bool:
        return False

    @dbus_property_async(
        property_signature="b",
        flags=DbusPropertyEmitsChangeFlag,
    )
    def has_track_list(self) -> bool:
        return False

    @dbus_property_async(
        property_signature="s",
        flags=DbusPropertyEmitsChangeFlag,
    )
    def identity(self) -> str:
        return "now-playing-properly"

    @dbus_property_async(
        property_signature="s",
        flags=DbusPropertyEmitsChangeFlag,
    )
    def desktop_entry(self) -> str:
        return "unavalaible"

    @dbus_property_async(
        property_signature="as",
        flags=DbusPropertyEmitsChangeFlag,
    )
    def supported_uri_schemes(self) -> list[str]:
        return []

    @dbus_property_async(
        property_signature="as",
        flags=DbusPropertyEmitsChangeFlag,
    )
    def supported_mime_types(self) -> list[str]:
        return []


class CombinedObject(MediaPlayer2ServerInterface, MediaPlayer2PlayerServerInterface):
    def __init__(
        self,
        update_queue: asyncio.Queue[ServerOutType],
        request_queue: asyncio.Queue[ServerInType],
        config: Config,
    ):
        super().__init__(update_queue, request_queue, config)
