"""EVENT DATACLASSES To BE USED INTERNALLY"""

from dataclasses import dataclass
from typing import Literal, Union, Optional, List, Any, Dict
from ..common.metadata_spec import AudioMetadata
from enum import Enum


@dataclass
class UpdateEvent:
    player: str
    status: Optional[Literal["Playing", "Paused", "Stopped"]]
    metadata: Optional[AudioMetadata]
    start_time: Optional[int]
    elapsed_time: Optional[int]
    volume: Optional[float]
    shuffle: Optional[str]
    minrate: Optional[float]
    maxrate: Optional[float]
    rate: Optional[float]
    id: bytes


@dataclass
class PluginResponseEvent:
    player: str
    metadata: AudioMetadata
    plugin_data: Dict[str, Dict[str, Any]]
    id: bytes


@dataclass
class SeekEvent:
    player: str
    start_time: int
    elapsed_time: int


@dataclass
class SeekRequest:
    offset: Optional[int]
    absolute: Optional[int]


class Actions(Enum):
    NEXT = 0
    PREVIOUS = 1
    PLAY = 2
    PAUSE = 3
    STOP = 4
    PLAYPAUSE = 5


@dataclass
class ActionRequest:
    action: Actions


@dataclass
class SetVolumeRequest:
    volume: float


@dataclass
class OpenURIRequest:
    uri: str


ServerOutType = UpdateEvent | PluginResponseEvent | SeekEvent
ServerInType = SetVolumeRequest | ActionRequest | OpenURIRequest
