import re
import zlib
import types
import struct
from enum import Enum
from base64 import b64decode
from .bulk_data import BulkData
from typing import Optional, List, Union
from dataclasses import dataclass, fields


class PlaybackStatus(Enum):
    PLAYING = 1
    PAUSED = 2
    STOPPED = 3


@dataclass
class AudioMetadata:
    # MPRIS-specific fields
    track_id: Optional[str] = None
    duration: Optional[int] = None  # Microseconds
    art_url: List[str] = None  # Allows for multiple URIs

    # Common Xesam properties (Strings)
    album: List[str] = None  # Multi Album is indeed a thing
    title: Optional[str] = None
    lyrics: Optional[str] = None
    url: Optional[str] = None

    # Common Xesam properties (Lists of Strings)
    album_artist: List[str] = None
    artist: List[str] = None
    genre: List[str] = None
    composer: List[str] = None
    lyricist: List[str] = None
    comment: List[str] = None

    # Numeric & Rating fields
    track_number: Optional[int] = None
    disc_number: Optional[int] = None
    bpm: Optional[int] = None
    rating_auto: Optional[float] = None
    rating_user: Optional[float] = None
    play_count: Optional[int] = None

    # Date/Time fields (ISO 8601 strings)
    content_created: Optional[str] = None
    first_use: Optional[str] = None
    last_use: Optional[str] = None

    def _handle_potential_base64_url(
        self, url_str: str, field_name: str, fds_list: list[int]
    ) -> str:
        """Detects if a string is a Base64 Data URI, extracts the image subtype extension,

        moves payload to shared memory, and returns a structural placeholder URL.
        """
        # Capture group 1: image extension (e.g. png, jpeg), group 2: base64 payload
        match = re.match(
            r"^data:image/([^;]+);base64,(.*)$", url_str.strip(), re.DOTALL
        )
        if match:
            try:
                img_ext = match.group(1)
                b64_data = match.group(2)

                # Padding correction
                b64_data += "=" * ((4 - len(b64_data) % 4) % 4)
                raw_bytes = b64decode(b64_data)

                # Move payload to Shared Memory Segment
                bulk = BulkData(raw_bytes, name=f"shm_{field_name}")
                size, fd = bulk.ready_shrmem()

                fd_index = len(fds_list)
                fds_list.append(fd)

                # Write information to placeholder URL: shm://<fd_index>:<size>.<ext>
                return f"shm://{fd_index}:{size}.{img_ext}"
            except Exception:
                return url_str
        return url_str

    def serialize(self, fds_list: list[int]) -> bytes:
        """Serializes the dataclass into a custom binary layout using native byte-order."""
        MAGIC_NUMBER = b"AMET"

        dfs = fields(self)
        header_table = bytearray()
        data_section = bytearray()

        base_offset = 20 + (len(dfs) * 9)
        current_global_offset = base_offset

        for field_id, f in enumerate(dfs):
            val = getattr(self, f.name)

            # --- Pre-processing for Base64 mitigation ---
            if f.name == "url" and isinstance(val, str):
                val = self._handle_potential_base64_url(val, f.name, fds_list)
            elif f.name == "art_url" and isinstance(val, list):
                val = [
                    (
                        self._handle_potential_base64_url(item, f.name, fds_list)
                        if isinstance(item, str)
                        else item
                    )
                    for item in val
                ]

            # Handle Nulls and Empty Lists
            if val is None or (isinstance(val, list) and len(val) == 0):
                header_table.extend(struct.pack("=BII", field_id, 0, 0))
                continue

            if isinstance(val, list):
                list_hdr_size = 4 + (len(val) * 8)
                list_item_offset = current_global_offset + list_hdr_size

                list_hdr_bytes = bytearray()
                list_data_bytes = bytearray()

                for item in val:
                    item_bytes = str(item).encode("utf-8")
                    item_len = len(item_bytes)
                    list_hdr_bytes.extend(
                        struct.pack("=II", list_item_offset, item_len)
                    )
                    list_data_bytes.extend(item_bytes)
                    list_item_offset += item_len

                list_payload = (
                    struct.pack("=I", list_hdr_size) + list_hdr_bytes + list_data_bytes
                )
                length = len(list_payload)

                header_table.extend(
                    struct.pack("=BII", field_id, current_global_offset, length)
                )
                data_section.extend(list_payload)
                current_global_offset += length

            elif isinstance(val, int):
                val_bytes = struct.pack("=q", val)
                length = 8
                header_table.extend(
                    struct.pack("=BII", field_id, current_global_offset, length)
                )
                data_section.extend(val_bytes)
                current_global_offset += length

            elif isinstance(val, float):
                val_bytes = struct.pack("=d", val)
                length = 8
                header_table.extend(
                    struct.pack("=BII", field_id, current_global_offset, length)
                )
                data_section.extend(val_bytes)
                current_global_offset += length

            elif isinstance(val, str):
                val_bytes = val.encode("utf-8")
                length = len(val_bytes)
                header_table.extend(
                    struct.pack("=BII", field_id, current_global_offset, length)
                )
                data_section.extend(val_bytes)
                current_global_offset += length

        # --- Generate Sizes & Checksums ---
        hdr_csum = zlib.crc32(header_table) & 0xFFFFFFFF
        hdr_size = 4 + len(header_table)

        data_csum = zlib.crc32(data_section) & 0xFFFFFFFF
        data_size = 4 + len(data_section)

        # --- Final Packet Assembly ---
        packet = bytearray()
        packet.extend(MAGIC_NUMBER)
        packet.extend(struct.pack("=I", hdr_size))
        packet.extend(struct.pack("=I", hdr_csum))
        packet.extend(header_table)
        packet.extend(struct.pack("=I", data_size))
        packet.extend(struct.pack("=I", data_csum))
        packet.extend(data_section)

        return bytes(packet)

    @classmethod
    def deserialize(cls, data: bytes) -> "AudioMetadata":
        """Deserializes a custom binary layout payload back into an AudioMetadata instance."""
        MAGIC_NUMBER = b"AMET"

        if len(data) < 20:
            raise ValueError("Data packet is too short to be valid.")

        # 1. Parse and verify Magic Number
        if data[0:4] != MAGIC_NUMBER:
            raise ValueError("Invalid magic number. Not an AMET packet.")

        # 2. Parse Header Size and Checksum
        hdr_size, hdr_csum = struct.unpack_from("=II", data, 4)
        header_table_start = 12
        header_table_end = header_table_start + (hdr_size - 4)
        header_table = data[header_table_start:header_table_end]

        if zlib.crc32(header_table) & 0xFFFFFFFF != hdr_csum:
            raise ValueError("Header checksum mismatch. Data corruption detected.")

        # 3. Parse Data Section Size and Checksum
        data_size, data_csum = struct.unpack_from("=II", data, header_table_end)
        data_section_start = header_table_end + 8
        data_section_end = data_section_start + (data_size - 4)
        data_section = data[data_section_start:data_section_end]

        if zlib.crc32(data_section) & 0xFFFFFFFF != data_csum:
            raise ValueError(
                "Data section checksum mismatch. Data corruption detected."
            )

        # 4. Reconstruct fields
        dfs = fields(cls)
        kwargs = {}

        # Each entry in the header table is 9 bytes (=BII)
        for i in range(0, len(header_table), 9):
            field_id, offset, length = struct.unpack_from("=BII", header_table, i)

            if field_id >= len(dfs):
                continue  # Safeguard against unexpected field IDs

            field = dfs[field_id]

            # Handle null values or empty lists
            if offset == 0 and length == 0:
                # Revert to default factory/value if available, else None/empty list
                if (
                    isinstance(field.default_factory, type)
                    and field.default_factory is list
                ):
                    kwargs[field.name] = []
                else:
                    kwargs[field.name] = None
                continue

            # Calculate relative offset inside the data_section slice
            # (offset is absolute within the global data packet)
            rel_offset = offset - data_section_start
            field_bytes = data_section[rel_offset : rel_offset + length]

            # Determine field type origin (to account for typing.List, typing.Optional, etc.)
            field_type = field.type
            type_origin = getattr(field_type, "__origin__", field_type)

            # If it's a Union (like Optional[str]), extract the non-None type
            if (
                type_origin is Union or type_origin is types.UnionType
            ):  # supports Python 3.10+ union types
                args = field_type.__args__
                non_none_types = [t for t in args if t is not type(None)]
                if non_none_types:
                    field_type = non_none_types[0]
                    type_origin = getattr(field_type, "__origin__", field_type)

            # 5. Parse types based on schema definition
            if type_origin is list:
                # Lists contain a 4-byte list_hdr_size prefix
                list_hdr_size = struct.unpack_from("=I", field_bytes, 0)[0]
                num_items = (list_hdr_size - 4) // 8

                parsed_list = []
                # Parse item offsets and lengths from the list header
                for item_idx in range(num_items):
                    item_offset, item_len = struct.unpack_from(
                        "=II", field_bytes, 4 + (item_idx * 8)
                    )
                    # item_offset is global, map it to relative position inside packet
                    item_bytes = data[item_offset : item_offset + item_len]
                    parsed_list.append(item_bytes.decode("utf-8"))
                kwargs[field.name] = parsed_list

            elif field_type is int:
                kwargs[field.name] = struct.unpack("=q", field_bytes)[0]

            elif field_type is float:
                kwargs[field.name] = struct.unpack("=d", field_bytes)[0]

            elif field_type is str:
                kwargs[field.name] = field_bytes.decode("utf-8")

        return cls(**kwargs)


@dataclass
class PlayerStatus:
    name: str
    status: PlaybackStatus = PlaybackStatus.STOPPED
    position: int = 0
    active: bool = False

    def serialize(self) -> bytes:
        # 1. Encode the string to bytes
        name_bytes = self.name.encode("utf-8")
        name_len = len(name_bytes)

        # 2. Define the format string (Little Endian '<')
        # I: 4-byte unsigned int (string length)
        # i: 4-byte signed int (enum value)
        # q: 8-byte signed int (position)
        # ?: 1-byte boolean (active)
        # {name_len}s: variable length bytes for the name
        fmt = f"<Iiq?{name_len}s"

        return struct.pack(
            fmt, name_len, self.status.value, self.position, self.active, name_bytes
        )

    @classmethod
    def deserialize(cls, data: bytes) -> "PlayerStatus":
        # 1. Unpack the header first to know the length of the string
        # '<I' reads the first 4 bytes as an unsigned integer
        name_len = struct.unpack("<I", data[:4])[0]

        # 2. Reconstruct the full format string now that we have the length
        fmt = f"<Iiq?{name_len}s"

        # 3. Unpack the full byte array
        _, status_val, position, active, name_bytes = struct.unpack(fmt, data)

        # 4. Reconstruct the dataclass fields
        name = name_bytes.decode("utf-8")
        status = PlaybackStatus(status_val)

        return cls(name=name, status=status, position=position, active=active)
