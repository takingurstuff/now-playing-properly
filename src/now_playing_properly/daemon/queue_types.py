"""EVENT DATACLASSES To BE USED INTERNALLY"""

from dataclasses import dataclass
from typing import Literal, Union, Optional, List, Any, Dict
from ..common.metadata_spec import AudioMetadata
from ..common.protocol import Message


@dataclass
class UpdateEvent:
    player: str
    status: Optional[Literal["Playing", "Paused", "Stopped"]]
    metadata: Optional[AudioMetadata]
    start_time: Optional[int]
    elapsed_time: Optional[int]
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
class MessageEvent:
    client_id: Optional[int | list[int]]
    broadcast: Optional[bool]
    message: Message
