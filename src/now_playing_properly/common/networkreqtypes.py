from typing import Any
from enum import Enum, auto
from dataclasses import dataclass


class ReqType(Enum):
    GET = auto()
    POST = auto()
    UPDATE = auto()
    DELETE = auto()


@dataclass
class NetworkReq:
    req: ReqType
    url: str
    params: dict[str, Any]
    headers: dict[str, Any]
    id: bytes


@dataclass
class NetworkResp:
    resp: dict[str, Any] | list[Any] | None = None
    id: bytes
    httpcode: int
    exc: BaseException | None
