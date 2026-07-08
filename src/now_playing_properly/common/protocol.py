import zlib
import random
import struct
import msgpack
from enum import Enum
from typing import Protocol, runtime_checkable, Union, Any, Optional, Type, Dict

from .bulk_data import BulkData
from .command_params import BaseParams
from .command_responses import BaseResponse
from .metadata_spec import AudioMetadata, PlaybackStatus
from .command import Commands, param_classes, response_classes

# --- Configuration & Protocol Constants ---
PREFIX_MAGIC = b"\x70\x69\x73\x73"  # PISS
SUFFIX_MAGIC = b"\x73\x68\x69\x74"  # SHIT

accep_dtypes = int | float | bytes | bytearray | BulkData
accept_collections = list[accep_dtypes] | dict[str, accep_dtypes]
autoshm_thresh = 10 * 1024  # 10kib


class PayloadType(Enum):
    COMMAND = 0
    RESPONSE = 1
    STATUS = 2
    DATA = 3


# --- Structural Payload Interface ---
@runtime_checkable
class PayloadProtocol(Protocol):
    def serialize(self) -> Union[bytes, tuple[bytes, Optional[list[int]]]]:
        """Serializes the payload instance into raw bytes or bytes + fds tuple."""
        ...

    @classmethod
    def deserialize(cls, data: bytes, **kwargs) -> "PayloadProtocol":
        """Deserializes raw bytes back into an instance of the payload."""
        ...


# Global Registry to map Type Markers to payload implementations without tight coupling
PAYLOAD_REGISTRY: Dict[PayloadType, Type[PayloadProtocol]] = {}


def register_payload(payload_type: PayloadType):
    def decorator(cls: Type[PayloadProtocol]):
        PAYLOAD_REGISTRY[payload_type] = cls
        return cls

    return decorator


# --- Concrete Payload Modules ---


@register_payload(PayloadType.COMMAND)
class CommandPayload:
    def __init__(self, command: Commands, params: Optional[BaseParams]):
        self.command = command
        self.params = params

    def serialize(self) -> bytes:
        cmd_bytes = struct.pack("=B", self.command.value)
        if self.params:
            return cmd_bytes + self.params.serialize()
        return cmd_bytes

    @classmethod
    def deserialize(cls, data: bytes, **kwargs) -> "CommandPayload":
        if len(data) < 1:
            raise ValueError("CommandPayload buffer truncated.")
        cmd_val = struct.unpack_from("=B", data, 0)[0]
        command = Commands(cmd_val)

        target_cls = param_classes.get(command)
        params = None
        if target_cls and len(data) > 1:
            params = target_cls.deserialize(data[1:])
        return cls(command=command, params=params)


@register_payload(PayloadType.STATUS)
class StatusPayload:
    def __init__(
        self, player: str, status: PlaybackStatus, position: int, active: bool
    ):
        self.player = player
        self.status = status
        self.position = position
        self.active = active

    def serialize(self) -> bytes:
        player_bytes = self.player.encode("utf-8")
        header = struct.pack(
            "=IBQ?", len(player_bytes), self.status.value, self.position, self.active
        )
        return header + player_bytes

    @classmethod
    def deserialize(cls, data: bytes, **kwargs) -> "StatusPayload":
        if len(data) < 14:
            raise ValueError("StatusPayload buffer truncated.")
        player_len, status_val, position, active = struct.unpack_from("=IBQ?", data, 0)

        header_len = 14
        if len(data) < header_len + player_len:
            raise ValueError("StatusPayload string data segment overflow.")

        player = data[header_len : header_len + player_len].decode("utf-8")
        return cls(
            player=player,
            status=PlaybackStatus(status_val),
            position=position,
            active=active,
        )


@register_payload(PayloadType.RESPONSE)
class ResponsePayload:
    def __init__(
        self, player: str, res_id: str, response: BaseResponse, called_command: Commands
    ):
        self.player = player
        self.res_id = res_id
        self.called_command = called_command
        self.response = response

    def serialize(self) -> bytes:
        player_bytes = self.player.encode("utf-8")
        res_id_bytes = self.res_id.encode("utf-8")
        resp_bytes = self.response.serialize()

        header = struct.pack(
            "=III", self.called_command.value, len(player_bytes), len(res_id_bytes)
        )
        return header + player_bytes + res_id_bytes + resp_bytes

    @classmethod
    def deserialize(cls, data: bytes, **kwargs) -> "ResponsePayload":
        if len(data) < 8:
            raise ValueError("ResponsePayload buffer truncated.")
        cmd, player_len, res_id_len = struct.unpack_from("=III", data, 0)
        type_hint_cls = response_classes.get(cmd)

        idx = 8
        player = data[idx : idx + player_len].decode("utf-8")
        idx += player_len
        res_id = data[idx : idx + res_id_len].decode("utf-8")
        idx += res_id_len

        if not type_hint_cls:
            raise ValueError(
                "Deserialization of RESPONSE requires valid structural type context handlers passed via 'type_hint_cls'."
            )

        response = type_hint_cls.deserialize(data[idx:])
        return cls(player=player, res_id=res_id, response=response)


@register_payload(PayloadType.DATA)
class DataPayload:
    def __init__(self, standard: AudioMetadata, extra: dict[str, Any]):
        self.standard = standard
        self.extra = extra
        self.fds = []
        self._preprocess_plugin_data()

    def _preprocess_plugin_data(self):
        def traverse(values: Union[dict, list], fds: list[int]):
            if isinstance(values, dict):
                for k, v in list(values.items()):
                    if isinstance(v, (dict, list)):
                        traverse(v, fds)
                    elif isinstance(v, BulkData):
                        size, fd = v.ready_shrmem()
                        fds.append(fd)
                        values[k] = {"size": size, "fd_index": len(fds) - 1}
                    elif isinstance(v, (bytes, bytearray)) and len(v) > autoshm_thresh:
                        shgen = BulkData(v, f"autogen_{random.randint(100000, 999999)}")
                        size, fd = shgen.ready_shrmem()
                        fds.append(fd)
                        values[k] = {"size": size, "fd_index": len(fds) - 1}
            elif isinstance(values, list):
                for i, v in enumerate(values):
                    if isinstance(v, (dict, list)):
                        traverse(v, fds)
                    elif isinstance(v, BulkData):
                        size, fd = v.ready_shrmem()
                        fds.append(fd)
                        values[i] = {"size": size, "fd_index": len(fds) - 1}
                    elif isinstance(v, (bytes, bytearray)) and len(v) > autoshm_thresh:
                        shgen = BulkData(v, f"autogen_{random.randint(100000, 999999)}")
                        size, fd = shgen.ready_shrmem()
                        fds.append(fd)
                        values[i] = {"size": size, "fd_index": len(fds) - 1}

        traverse(self.extra, self.fds)

    def serialize(self) -> tuple[bytes, Optional[list[int]]]:
        main = self.standard.serialize(self.fds)
        extra = msgpack.packb(self.extra)

        # Internal offset calculation is now relative to this payload's internal buffer segment (fully encapsulated)
        header_len = 18  # struct.calcsize("=BIIBII")
        offset0 = header_len
        offset1 = header_len + len(main)

        header = struct.pack("=BII", 0, offset0, len(main)) + struct.pack(
            "=BII", 1, offset1, len(extra)
        )
        buf = header + main + extra
        buf_csum = zlib.crc32(buf) & 0xFFFFFFFF
        return struct.pack("=I", buf_csum) + buf, self.fds

    @classmethod
    def deserialize(
        cls, data: bytes, fds: Optional[list[int]] = None, **kwargs
    ) -> "DataPayload":
        if fds is None:
            fds = kwargs.get("fds")

        if fds is None:
            raise ValueError(
                "Shared file descriptors reference collection mappings missing ('fds')."
            )

        if len(data) < 22:
            raise ValueError("DataPayload buffer header section underflow.")

        sent_csum = struct.unpack_from("=I", data, 0)[0]
        data_buf = data[4:]
        if (zlib.crc32(data_buf) & 0xFFFFFFFF) != sent_csum:
            raise ValueError(
                "DataPayload buffer structural validation checksum corruption."
            )

        type0, offset0, len0, type1, offset1, len1 = struct.unpack_from(
            "=BIIBII", data_buf, 0
        )

        standard = AudioMetadata.deserialize(data_buf[offset0 : offset0 + len0])
        extra = msgpack.unpackb(data_buf[offset1 : offset1 + len1])

        def resolve_traverse(values: Union[dict, list]):
            if isinstance(values, dict):
                for k, v in list(values.items()):
                    if isinstance(v, dict) and "fd_index" in v and "size" in v:
                        values[k] = BulkData.from_shmem(fds[v["fd_index"]], v["size"])
                    elif isinstance(v, (dict, list)):
                        resolve_traverse(v)
            elif isinstance(values, list):
                for i, v in enumerate(values):
                    if isinstance(v, dict) and "fd_index" in v and "size" in v:
                        values[i] = BulkData.from_shmem(fds[v["fd_index"]], v["size"])
                    elif isinstance(v, (dict, list)):
                        resolve_traverse(v)

        resolve_traverse(extra)

        payload = cls.__new__(cls)
        payload.standard = standard
        payload.extra = extra
        payload.fds = fds
        return payload


# --- Unified Framing Messenger ---


class Message:
    def __init__(self, payload_type: PayloadType, payload: PayloadProtocol):
        self.type = payload_type
        self.payload = payload

    def serialize(self) -> tuple[bytes, Optional[list[int]]]:
        serialized_res = self.payload.serialize()
        fds = None
        if isinstance(serialized_res, tuple):
            payload_bytes, fds = serialized_res
        else:
            payload_bytes = serialized_res

        msg_header = PREFIX_MAGIC + struct.pack(
            "=BI", self.type.value, len(payload_bytes)
        )
        return msg_header + payload_bytes + SUFFIX_MAGIC, fds

    @property
    def size(self) -> int:
        return len(self.serialize()[0])

    @classmethod
    def deserialize(cls, data: bytes, **kwargs) -> "Message":
        if len(data) < 13:
            raise ValueError(
                "Buffer frame structure parsing overflow; insufficient segment width."
            )

        if data[:4] != PREFIX_MAGIC:
            raise ValueError(
                "Invalid wire protocol preamble signature sequence identification data."
            )

        type_val, payload_len = struct.unpack_from("=BI", data, 4)
        payload_type = PayloadType(type_val)

        header_offset = 9
        payload_end = header_offset + payload_len

        if data[payload_end : payload_end + 4] != SUFFIX_MAGIC:
            raise ValueError(
                "Malformed protocol packet trailer bounding segment sequence confirmation failure."
            )

        payload_bytes = data[header_offset:payload_end]

        payload_cls = PAYLOAD_REGISTRY.get(payload_type)
        if not payload_cls:
            raise TypeError(
                "Unsupported framing payload type structure specification identifier encountered."
            )

        # Explicitly forward fds if targeting the DataPayload type
        if payload_type == PayloadType.DATA:
            payload = payload_cls.deserialize(
                payload_bytes, fds=kwargs.get("fds"), **kwargs
            )
        else:
            payload = payload_cls.deserialize(payload_bytes, **kwargs)

        return cls(payload_type=payload_type, payload=payload)
