import struct
from io import BytesIO
from enum import IntEnum
from typing import Protocol, runtime_checkable, Optional, Type

from .metadata_spec import PlayerStatus
from .command_params import _pack_string_list, _unpack_string_list


# --- Global Configuration / Setup ---
class ResponseCode(IntEnum):
    SUCCESS = 0
    NOT_FOUND = 404
    SERVER_ERROR = 500


# --- Structural Payload Interface ---
@runtime_checkable
class ResponsePayloadProtocol(Protocol):
    def serialize(self) -> bytes:
        """Serialize the payload into a bytes object."""
        ...

    @classmethod
    def deserialize(cls, data: bytes) -> "ResponsePayloadProtocol":
        """Deserialize a bytes object back into an instance of the payload."""
        ...


# --- Unified Response Frame ---
class BaseResponse:
    def __init__(
        self,
        eno: IntEnum,
        reason: str = "",
        actual_response: Optional[ResponsePayloadProtocol] = None,
    ):
        self.eno = eno
        self.reason = reason
        self.actual_response = actual_response

    def serialize(self) -> bytes:
        reason_bytes = self.reason.encode("utf-8")
        header = struct.pack("=II", self.eno.value, len(reason_bytes)) + reason_bytes

        if self.actual_response is not None:
            return header + self.actual_response.serialize()
        return header

    @classmethod
    def deserialize(
        cls, data: bytes, payload_cls: Optional[Type[ResponsePayloadProtocol]] = None
    ) -> "BaseResponse":
        if len(data) < 8:
            raise ValueError("BaseResponse buffer truncated.")

        eno_val, reason_len = struct.unpack_from("=II", data, 0)
        header_end = 8 + reason_len

        if len(data) < header_end:
            raise ValueError("BaseResponse reason string segment overflow.")

        reason = data[8:header_end].decode("utf-8")
        payload_bytes = data[header_end:]

        actual_response = None
        # Only attempt to deserialize the payload if bytes remain AND a target class is provided
        if payload_bytes and payload_cls:
            actual_response = payload_cls.deserialize(payload_bytes)

        return cls(
            eno=ResponseCode(eno_val),
            reason=reason,
            actual_response=actual_response,
        )


# --- Concrete Payload Implementations ---


class GetAliasPayload:
    def __init__(self, alias: str = ""):
        self.alias = alias

    def serialize(self) -> bytes:
        alias_bytes = self.alias.encode("utf-8")
        return struct.pack("=I", len(alias_bytes)) + alias_bytes

    @classmethod
    def deserialize(cls, data: bytes) -> "GetAliasPayload":
        if not data:
            return cls("")
        alias_len = struct.unpack_from("=I", data, 0)[0]
        alias = data[4 : 4 + alias_len].decode("utf-8")
        return cls(alias)


class GetStatusPayload:
    def __init__(self, players: list[str] = None, statuses: list[PlayerStatus] = None):
        self.players = players if players is not None else []
        self.statuses = statuses if statuses is not None else []

    def serialize(self) -> bytes:
        players_bytes = _pack_string_list(self.players)
        serialized_statuses = [x.serialize() for x in self.statuses]

        buffer = bytearray()
        buffer.extend(struct.pack("<I", len(players_bytes)))
        buffer.extend(players_bytes)

        for status_bytes in serialized_statuses:
            buffer.extend(struct.pack("<I", len(status_bytes)))
            buffer.extend(status_bytes)

        return bytes(buffer)

    @classmethod
    def deserialize(cls, data: bytes) -> "GetStatusPayload":
        ptr = BytesIO(data)

        # Read players size
        players_size_bytes = ptr.read(4)
        if not players_size_bytes:
            return cls([], [])

        players_size = struct.unpack("<I", players_size_bytes)[0]

        # Read and unpack players
        players_data = ptr.read(players_size)
        players, _ = _unpack_string_list(players_data, 0)

        # Read statuses
        statuses = []
        while True:
            size_bytes = ptr.read(4)
            if not size_bytes or len(size_bytes) < 4:
                break

            size = struct.unpack("<I", size_bytes)[0]
            status_data = ptr.read(size)
            statuses.append(PlayerStatus.deserialize(status_data))

        return cls(players=players, statuses=statuses)
