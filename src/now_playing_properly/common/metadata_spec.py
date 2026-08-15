import re
import zlib
import types
import struct
from enum import Enum
from base64 import b64decode
from functools import cached_property
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
    art_url: Optional[List[str]] = None  # Allows for multiple URIs

    # Common Xesam properties (Strings)
    album: Optional[List[str]] = None
    title: Optional[str] = None
    lyrics: Optional[str] = None
    url: Optional[str] = None

    # Common Xesam properties (Lists of Strings)
    album_artist: Optional[List[str]] = (
        None  # Not exactly multi album, but a track can be part of multiple collections, in the present theres not yet specs for something like compilations, workaround until then
    )
    artist: Optional[List[str]] = None
    genre: Optional[List[str]] = None
    composer: Optional[List[str]] = None
    lyricist: Optional[List[str]] = None
    comment: Optional[List[str]] = None

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

    def to_mpris(
        self, delimiter: str = " "
    ) -> (
        dict
    ):  # That is a non breaking space, specifically chosen for its ability to look like a space (so things dont look rediculous) without being a space (you can split safely by nbsp and assume no sane human uses it in an album name)
        """Serializes directly to an MPRIS dictionary, skipping None values."""
        raw_map = {
            "mpris:trackid": self.track_id,
            "mpris:length": self.duration,
            "mpris:artUrl": delimiter.join(self.art_url) if self.art_url else None,
            "xesam:album": delimiter.join(self.album) if self.album else None,
            "xesam:title": self.title,
            "xesam:asText": self.lyrics,
            "xesam:url": self.url,
            "xesam:albumArtist": self.album_artist,
            "xesam:artist": self.artist,
            "xesam:genre": self.genre,
            "xesam:composer": self.composer,
            "xesam:lyricist": self.lyricist,
            "xesam:comment": self.comment,
            "xesam:trackNumber": self.track_number,
            "xesam:discNumber": self.disc_number,
            "xesam:audioBpm": self.bpm,
            "xesam:autoRating": self.rating_auto,
            "xesam:userRating": self.rating_user,
            "xesam:useCount": self.play_count,
            "xesam:contentCreated": self.content_created,
            "xesam:firstUsed": self.first_use,
            "xesam:lastUsed": self.last_use,
        }
        return {k: v for k, v in raw_map.items() if v is not None}

    @classmethod
    def from_mpris(cls, data: dict) -> "AudioMetadata":
        """Deserializes directly from an MPRIS dictionary."""
        album_val = data.get("xesam:album")
        art_val = data.get("mpris:artUrl")

        return cls(
            track_id=data.get("mpris:trackid"),
            duration=data.get("mpris:length"),
            art_url=[art_val] if art_val else None,
            album=[album_val] if album_val else None,
            title=data.get("xesam:title"),
            lyrics=data.get("xesam:asText"),
            url=data.get("xesam:url"),
            album_artist=data.get("xesam:albumArtist"),
            artist=data.get("xesam:artist"),
            genre=data.get("xesam:genre"),
            composer=data.get("xesam:composer"),
            lyricist=data.get("xesam:lyricist"),
            comment=data.get("xesam:comment"),
            track_number=data.get("xesam:trackNumber"),
            disc_number=data.get("xesam:discNumber"),
            bpm=data.get("xesam:audioBpm"),
            rating_auto=data.get("xesam:autoRating"),
            rating_user=data.get("xesam:userRating"),
            play_count=data.get("xesam:useCount"),
            content_created=data.get("xesam:contentCreated"),
            first_use=data.get("xesam:firstUsed"),
            last_use=data.get("xesam:lastUsed"),
        )
