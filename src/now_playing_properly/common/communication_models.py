import random
from enum import Enum
from .networkreqtypes import *
from dataclasses import dataclass
from typing import Optional, Callable, Any, Literal
from .metadata_spec import AudioMetadata, PlayerProperties


@dataclass
class SeekRequest:
    offset: Optional[int]
    absolute: Optional[int]
    player: Optional[str]


class Actions(Enum):
    NEXT = 0
    PREVIOUS = 1
    PLAY = 2
    PAUSE = 3
    STOP = 4
    PLAYPAUSE = 5
    STARTSHUFFLE = 6
    STOPSHUFFLE = 7
    NOLOOP = 8
    LOOPTRACK = 9
    LOOPLIST = 10


@dataclass
class ActionRequest:
    action: Actions
    player: Optional[str]


@dataclass
class SetVolumeRequest:
    volume: float
    player: Optional[str]


@dataclass
class OpenURIRequest:
    uri: str
    player: Optional[str]


@dataclass
class SetRateRequest:
    rate: float
    player: Optional[str]


@dataclass
class SubprocessReq:
    cmd: tuple[str]
    id: bytes


@dataclass
class SubprocessResp:
    stdout: Optional[str]
    stderr: Optional[str]
    exc: Optional[BaseException]
    id: bytes


@dataclass
class ConcExecReq:
    thread: bool
    func: Callable[[Any], Any | tuple[Any]]
    args: tuple[Any]
    kwargs: dict[str, Any]
    id: bytes


@dataclass
class ConcExecResp:
    res: Optional[Any | tuple[Any]]
    exc: Optional[BaseException]
    id: bytes


@dataclass
class SeekEvent:
    player: str
    start_time: int
    elapsed_time: int


@dataclass
class UpdateEvent:
    player: str
    status: Optional[Literal["Playing", "Paused", "Stopped"]]
    metadata: Optional[AudioMetadata]
    start_time: Optional[int]
    elapsed_time: Optional[int]
    props: Optional[PlayerProperties]
    id: bytes


@dataclass
class PluginResponseEvent:
    player: str
    metadata: AudioMetadata
    plugin_data: dict[str, dict[str, Any]]
    id: bytes


PluginRespTypes = SubprocessResp | ConcExecResp
PluginEventTypes = (
    SeekRequest
    | ActionRequest
    | UpdateEvent
    | SeekEvent
    | SetVolumeRequest
    | OpenURIRequest
    | SetRateRequest
)
PluginReqTypes = (
    SeekRequest
    | ActionRequest
    | UpdateEvent
    | SeekEvent
    | SetVolumeRequest
    | OpenURIRequest
    | SetRateRequest
    | SubprocessReq
    | ConcExecReq
)
ServerOutType = UpdateEvent | PluginResponseEvent | SeekEvent
ServerInType = (
    SetVolumeRequest | ActionRequest | OpenURIRequest | SetRateRequest | SeekRequest
)
