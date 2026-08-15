import time
import asyncio
from .config import Config
from __future__ import annotations
from .helpers import prep_metadata
from ..common.metadata_spec import AudioMetadata
from ..common.interfaces import MediaPlayer2PlayerInterface
from .queue_types import (
    Actions,
    SeekRequest,
    ServerInType,
    ServerOutType,
    ActionRequest,
    OpenURIRequest,
    SetVolumeRequest,
)

from typing import Any

from sdbus import (
    dbus_method_async,
    dbus_signal_async,
    dbus_property_async,
    DbusUnprivilegedFlag,
    DbusPropertyEmitsChangeFlag,
)


class MediaPlayer2ServerInterface(MediaPlayer2PlayerInterface):
    def __init__(
        self,
        update_queue: asyncio.Queue[ServerOutType],
        request_queue: asyncio.Queue[ServerInType],
        config: Config,
    ):
        super.__init__()
        self.request_queue = request_queue
        self.update_queue = update_queue
        self.config = config
        self._playback_status = "Stopped"
        self._loop_status = "None"
        self._metadata: AudioMetadata | None = None
        self._plugin_extras: dict[str, dict[str, Any]] | None = None
        self._full_metadata: dict[str, tuple[str, Any]] | None = None
        self._position = 0
        self._minrate = 0.00
        self._maxrate = 3.00
        self._stime = 0
        self._etime = 0
        self._volume = 1.0
        self._rate = 1.0
        self._shuffle = False

    async def _update_loop(self):
        async for event in self.update_queue

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
        return self._playback_status

    @dbus_property_async(
        property_signature="s",
        flags=DbusPropertyEmitsChangeFlag,
    )
    def loop_status(self) -> str:
        return self._loop_status

    @dbus_property_async(
        property_signature="d",
        flags=DbusPropertyEmitsChangeFlag,
    )
    def rate(self) -> float:
        raise self._rate

    @dbus_property_async(
        property_signature="b",
        flags=DbusPropertyEmitsChangeFlag,
    )
    def shuffle(self) -> bool:
        return self._rate

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
        return self._volume

    @volume.setter
    async def setvolume(self, volume: float):
        self.request_queue.put_nowait(SetVolumeRequest(volume))

    @dbus_property_async(
        property_signature="x",
    )
    def position(self) -> int:
        cur = time.time() * 1_000_000
        pos = (cur - self._stime + self._etime) * 1_000_000
        return pos

    @dbus_property_async(
        property_signature="d",
        flags=DbusPropertyEmitsChangeFlag,
    )
    def minimum_rate(self) -> float:
        return self._minrate

    @minimum_rate.setter_private
    def setminrate(self, rate: float):
        self._minrate = rate

    @dbus_property_async(
        property_signature="d",
        flags=DbusPropertyEmitsChangeFlag,
    )
    def maximum_rate(self) -> float:
        return self._maxrate

    @maximum_rate.setter_private
    def setmaxrate(self, rate: float):
        self._maxrate = rate

    @dbus_property_async(
        property_signature="b",
        flags=DbusPropertyEmitsChangeFlag,
    )
    def can_go_next(self) -> bool:
        return False

    @dbus_property_async(
        property_signature="b",
        flags=DbusPropertyEmitsChangeFlag,
    )
    def can_go_previous(self) -> bool:
        return False

    @dbus_property_async(
        property_signature="b",
        flags=DbusPropertyEmitsChangeFlag,
    )
    def can_play(self) -> bool:
        return False

    @dbus_property_async(
        property_signature="b",
        flags=DbusPropertyEmitsChangeFlag,
    )
    def can_pause(self) -> bool:
        return False

    @dbus_property_async(
        property_signature="b",
        flags=DbusPropertyEmitsChangeFlag,
    )
    def can_seek(self) -> bool:
        return False

    @dbus_property_async(
        property_signature="b",
    )
    def can_control(self) -> bool:
        return False

    @dbus_signal_async(
        signal_signature="x",
        signal_args_names=("Position",),
    )
    def seeked(self) -> int:
        raise NotImplementedError
