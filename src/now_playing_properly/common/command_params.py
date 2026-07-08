import struct
from enum import Enum, IntFlag
from typing import Protocol, runtime_checkable


class ResolvStrat(Enum):
    LOW_FIRST = 0
    HIGH_FIRST = 1


# 1. Change Enum to IntFlag and assign bit shifts
class EventTypes(IntFlag):
    NONE = 0
    METADATA_UPDATE = 1 << 0  # 0001 (1)
    PLAY_PAUSE = 1 << 1  # 0010 (2)
    SEEK = 1 << 2  # 0100 (4)
    ALL = METADATA_UPDATE | PLAY_PAUSE | SEEK  # 0111 (7)


# --- Helper Methods for Lists of Strings (Offset Table Method) ---


def _pack_string_list(strings: list[str]) -> bytes:
    payload = struct.pack("=I", len(strings))
    for s in strings:
        encoded = s.encode("utf-8")
        payload += struct.pack(f"=I{len(encoded)}s", len(encoded), encoded)
    return payload


def _unpack_string_list(data: bytes, offset: int) -> tuple[list[str], int]:
    count = struct.unpack_from("=I", data, offset)[0]
    current_offset = offset + 4
    strings = []

    for _ in range(count):
        length = struct.unpack_from("=I", data, current_offset)[0]
        current_offset += 4
        s = struct.unpack_from(f"={length}s", data, current_offset)[0].decode("utf-8")
        current_offset += length
        strings.append(s)

    return strings, current_offset


# --- Structural Payload Interface ---


@runtime_checkable
class ParamsProtocol(Protocol):
    def serialize(self) -> bytes:
        """Serialize the parameters into a bytes object."""
        ...

    @classmethod
    def deserialize(cls, data: bytes) -> "ParamsProtocol":
        """Deserialize a bytes object back into an instance of this parameter class."""
        ...


# --- Concrete Parameter Classes (Implicitly implementing ParamsProtocol) ---


class SetAliasParams:
    def __init__(self, alias: str = ""):
        self.alias = alias

    def serialize(self) -> bytes:
        encoded = self.alias.encode("utf-8")
        return struct.pack(f"=I{len(encoded)}s", len(encoded), encoded)

    @classmethod
    def deserialize(cls, data: bytes) -> "SetAliasParams":
        length = struct.unpack_from("=I", data, 0)[0]
        alias = struct.unpack_from(f"={length}s", data, 4)[0].decode("utf-8")
        return cls(alias)


class PlayerControlParams:
    def __init__(self, players: list[str] = None):
        self.players = players if players is not None else []

    def serialize(self) -> bytes:
        return _pack_string_list(self.players)

    @classmethod
    def deserialize(cls, data: bytes) -> "PlayerControlParams":
        players, _ = _unpack_string_list(data, 0)
        return cls(players)


class SeekParams:
    def __init__(self, player: str = "", position: str = ""):
        self.player = player
        self.position = position

    def serialize(self) -> bytes:
        p_enc = self.player.encode("utf-8")
        pos_enc = self.position.encode("utf-8")
        return struct.pack(
            f"=I{len(p_enc)}sI{len(pos_enc)}s", len(p_enc), p_enc, len(pos_enc), pos_enc
        )

    @classmethod
    def deserialize(cls, data: bytes) -> "SeekParams":
        p_len = struct.unpack_from("=I", data, 0)[0]
        offset = 4
        player = struct.unpack_from(f"={p_len}s", data, offset)[0].decode("utf-8")
        offset += p_len

        pos_len = struct.unpack_from("=I", data, offset)[0]
        offset += 4
        position = struct.unpack_from(f"={pos_len}s", data, offset)[0].decode("utf-8")

        return cls(player, position)


class OpenURIParams:
    def __init__(self, players: list[str] = None, URI: str = ""):
        self.players = players if players is not None else []
        self.URI = URI

    def serialize(self) -> bytes:
        players_bytes = _pack_string_list(self.players)
        uri_enc = self.URI.encode("utf-8")
        uri_bytes = struct.pack(f"=I{len(uri_enc)}s", len(uri_enc), uri_enc)
        return players_bytes + uri_bytes

    @classmethod
    def deserialize(cls, data: bytes) -> "OpenURIParams":
        players, next_offset = _unpack_string_list(data, 0)
        uri_len = struct.unpack_from("=I", data, next_offset)[0]
        URI = struct.unpack_from(f"={uri_len}s", data, next_offset + 4)[0].decode(
            "utf-8"
        )
        return cls(players, URI)


class GetStatusParams:
    def __init__(self, players: list[str] = None, include_plugin_data: bool = False):
        self.players = players if players is not None else []

    def serialize(self) -> bytes:
        players_bytes = _pack_string_list(self.players)
        return players_bytes

    @classmethod
    def deserialize(cls, data: bytes) -> "GetStatusParams":
        players, next_offset = _unpack_string_list(data, 0)
        return cls(players)
