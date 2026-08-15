from __future__ import annotations

from typing import Any

from sdbus import (
    DbusNoReplyFlag,
    dbus_method_async,
    dbus_signal_async,
    DbusDeprecatedFlag,
    dbus_property_async,
    DbusUnprivilegedFlag,
    DbusPropertyConstFlag,
    DbusInterfaceCommonAsync,
    DbusPropertyExplicitFlag,
    DbusPropertyEmitsChangeFlag,
    DbusPropertyEmitsInvalidationFlag,
)


class MediaPlayer2PlayerInterface(
    DbusInterfaceCommonAsync,
    interface_name="org.mpris.MediaPlayer2.Player",
):
    @dbus_method_async(
        flags=DbusUnprivilegedFlag,
        result_args_names=(),
    )
    async def next(
        self,
    ) -> None:
        raise NotImplementedError

    @dbus_method_async(
        flags=DbusUnprivilegedFlag,
        result_args_names=(),
    )
    async def previous(
        self,
    ) -> None:
        raise NotImplementedError

    @dbus_method_async(
        flags=DbusUnprivilegedFlag,
        result_args_names=(),
    )
    async def pause(
        self,
    ) -> None:
        raise NotImplementedError

    @dbus_method_async(
        flags=DbusUnprivilegedFlag,
        result_args_names=(),
    )
    async def play_pause(
        self,
    ) -> None:
        raise NotImplementedError

    @dbus_method_async(
        flags=DbusUnprivilegedFlag,
        result_args_names=(),
    )
    async def stop(
        self,
    ) -> None:
        raise NotImplementedError

    @dbus_method_async(
        flags=DbusUnprivilegedFlag,
        result_args_names=(),
    )
    async def play(
        self,
    ) -> None:
        raise NotImplementedError

    @dbus_method_async(
        input_signature="x",
        flags=DbusUnprivilegedFlag,
        result_args_names=(),
    )
    async def seek(
        self,
        offset: int,
    ) -> None:
        raise NotImplementedError

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
        raise NotImplementedError

    @dbus_method_async(
        input_signature="s",
        flags=DbusUnprivilegedFlag,
        result_args_names=(),
    )
    async def open_uri(
        self,
        uri: str,
    ) -> None:
        raise NotImplementedError

    @dbus_method_async(
        result_signature="sh",
        flags=DbusUnprivilegedFlag,
        result_args_names=("MimeType", "Image"),
    )
    async def get_artwork_fd(
        self,
    ) -> tuple[str, int]:
        raise NotImplementedError

    @dbus_property_async(
        property_signature="s",
        flags=DbusPropertyEmitsChangeFlag,
    )
    def playback_status(self) -> str:
        raise NotImplementedError

    @dbus_property_async(
        property_signature="s",
        flags=DbusPropertyEmitsChangeFlag,
    )
    def loop_status(self) -> str:
        raise NotImplementedError

    @dbus_property_async(
        property_signature="d",
        flags=DbusPropertyEmitsChangeFlag,
    )
    def rate(self) -> float:
        raise NotImplementedError

    @dbus_property_async(
        property_signature="b",
        flags=DbusPropertyEmitsChangeFlag,
    )
    def shuffle(self) -> bool:
        raise NotImplementedError

    @dbus_property_async(
        property_signature="a{sv}",
        flags=DbusPropertyEmitsChangeFlag,
    )
    def metadata(self) -> dict[str, tuple[str, Any]]:
        raise NotImplementedError

    @dbus_property_async(
        property_signature="d",
        flags=DbusPropertyEmitsChangeFlag,
    )
    def volume(self) -> float:
        raise NotImplementedError

    @dbus_property_async(
        property_signature="x",
    )
    def position(self) -> int:
        raise NotImplementedError

    @dbus_property_async(
        property_signature="d",
        flags=DbusPropertyEmitsChangeFlag,
    )
    def minimum_rate(self) -> float:
        raise NotImplementedError

    @dbus_property_async(
        property_signature="d",
        flags=DbusPropertyEmitsChangeFlag,
    )
    def maximum_rate(self) -> float:
        raise NotImplementedError

    @dbus_property_async(
        property_signature="b",
        flags=DbusPropertyEmitsChangeFlag,
    )
    def can_go_next(self) -> bool:
        raise NotImplementedError

    @dbus_property_async(
        property_signature="b",
        flags=DbusPropertyEmitsChangeFlag,
    )
    def can_go_previous(self) -> bool:
        raise NotImplementedError

    @dbus_property_async(
        property_signature="b",
        flags=DbusPropertyEmitsChangeFlag,
    )
    def can_play(self) -> bool:
        raise NotImplementedError

    @dbus_property_async(
        property_signature="b",
        flags=DbusPropertyEmitsChangeFlag,
    )
    def can_pause(self) -> bool:
        raise NotImplementedError

    @dbus_property_async(
        property_signature="b",
        flags=DbusPropertyEmitsChangeFlag,
    )
    def can_seek(self) -> bool:
        raise NotImplementedError

    @dbus_property_async(
        property_signature="b",
    )
    def can_control(self) -> bool:
        raise NotImplementedError

    @dbus_signal_async(
        signal_signature="x",
        signal_args_names=("Position",),
    )
    def seeked(self) -> int:
        raise NotImplementedError


class MediaPlayer2PlaylistsInterface(
    DbusInterfaceCommonAsync,
    interface_name="org.mpris.MediaPlayer2.Playlists",
):
    @dbus_method_async(
        input_signature="o",
        flags=DbusUnprivilegedFlag,
        result_args_names=(),
    )
    async def activate_playlist(
        self,
        playlist_id: str,
    ) -> None:
        raise NotImplementedError

    @dbus_method_async(
        input_signature="uusb",
        result_signature="a(oss)",
        flags=DbusUnprivilegedFlag,
        result_args_names=("Playlists",),
    )
    async def get_playlists(
        self,
        index: int,
        max_count: int,
        order: str,
        reverse_order: bool,
    ) -> list[tuple[str, str, str]]:
        raise NotImplementedError

    @dbus_method_async(
        input_signature="o",
        result_signature="sh",
        flags=DbusUnprivilegedFlag,
        result_args_names=("MimeType", "Icon"),
    )
    async def get_playlist_icon_fd(
        self,
        playlist_id: str,
    ) -> tuple[str, int]:
        raise NotImplementedError

    @dbus_property_async(
        property_signature="u",
        flags=DbusPropertyEmitsChangeFlag,
    )
    def playlist_count(self) -> int:
        raise NotImplementedError

    @dbus_property_async(
        property_signature="as",
        flags=DbusPropertyEmitsChangeFlag,
    )
    def orderings(self) -> list[str]:
        raise NotImplementedError

    @dbus_property_async(
        property_signature="(b(oss))",
        flags=DbusPropertyEmitsChangeFlag,
    )
    def active_playlist(self) -> tuple[bool, tuple[str, str, str]]:
        raise NotImplementedError

    @dbus_signal_async(
        signal_signature="(oss)",
        signal_args_names=("Playlist",),
    )
    def playlist_changed(self) -> tuple[str, str, str]:
        raise NotImplementedError


class MediaPlayer2BaseInterface(
    DbusInterfaceCommonAsync,
    interface_name="org.mpris.MediaPlayer2",
):
    @dbus_method_async(
        flags=DbusUnprivilegedFlag,
        result_args_names=(),
    )
    async def Raise(
        self,
    ) -> None:
        raise NotImplementedError

    @dbus_method_async(
        flags=DbusUnprivilegedFlag,
        result_args_names=(),
    )
    async def quit(
        self,
    ) -> None:
        raise NotImplementedError

    @dbus_property_async(
        property_signature="b",
        flags=DbusPropertyEmitsChangeFlag,
    )
    def can_quit(self) -> bool:
        raise NotImplementedError

    @dbus_property_async(
        property_signature="b",
        flags=DbusPropertyEmitsChangeFlag,
    )
    def fullscreen(self) -> bool:
        raise NotImplementedError

    @dbus_property_async(
        property_signature="b",
        flags=DbusPropertyEmitsChangeFlag,
    )
    def can_set_fullscreen(self) -> bool:
        raise NotImplementedError

    @dbus_property_async(
        property_signature="b",
        flags=DbusPropertyEmitsChangeFlag,
    )
    def can_raise(self) -> bool:
        raise NotImplementedError

    @dbus_property_async(
        property_signature="b",
        flags=DbusPropertyEmitsChangeFlag,
    )
    def has_track_list(self) -> bool:
        raise NotImplementedError

    @dbus_property_async(
        property_signature="s",
        flags=DbusPropertyEmitsChangeFlag,
    )
    def identity(self) -> str:
        raise NotImplementedError

    @dbus_property_async(
        property_signature="s",
        flags=DbusPropertyEmitsChangeFlag,
    )
    def desktop_entry(self) -> str:
        raise NotImplementedError

    @dbus_property_async(
        property_signature="as",
        flags=DbusPropertyEmitsChangeFlag,
    )
    def supported_uri_schemes(self) -> list[str]:
        raise NotImplementedError

    @dbus_property_async(
        property_signature="as",
        flags=DbusPropertyEmitsChangeFlag,
    )
    def supported_mime_types(self) -> list[str]:
        raise NotImplementedError


class MediaPlayer2TracklistsInterface(
    DbusInterfaceCommonAsync,
    interface_name="org.mpris.MediaPlayer2.TrackList",
):
    @dbus_method_async(
        input_signature="ao",
        result_signature="aa{sv}",
        flags=DbusUnprivilegedFlag,
        result_args_names=("Metadata",),
    )
    async def get_tracks_metadata(
        self,
        track_ids: list[str],
    ) -> list[dict[str, tuple[str, Any]]]:
        raise NotImplementedError

    @dbus_method_async(
        input_signature="sob",
        flags=DbusUnprivilegedFlag,
        result_args_names=(),
    )
    async def add_track(
        self,
        uri: str,
        after_track: str,
        set_as_current: bool,
    ) -> None:
        raise NotImplementedError

    @dbus_method_async(
        input_signature="o",
        flags=DbusUnprivilegedFlag,
        result_args_names=(),
    )
    async def remove_track(
        self,
        track_id: str,
    ) -> None:
        raise NotImplementedError

    @dbus_method_async(
        input_signature="o",
        flags=DbusUnprivilegedFlag,
        result_args_names=(),
    )
    async def go_to(
        self,
        track_id: str,
    ) -> None:
        raise NotImplementedError

    @dbus_property_async(
        property_signature="ao",
        flags=DbusPropertyEmitsInvalidationFlag,
    )
    def tracks(self) -> list[str]:
        raise NotImplementedError

    @dbus_property_async(
        property_signature="b",
        flags=DbusPropertyEmitsChangeFlag,
    )
    def can_edit_tracks(self) -> bool:
        raise NotImplementedError

    @dbus_signal_async(
        signal_signature="aoo",
        signal_args_names=("Tracks", "CurrentTrack"),
    )
    def track_list_replaced(self) -> tuple[list[str], str]:
        raise NotImplementedError

    @dbus_signal_async(
        signal_signature="a{sv}o",
        signal_args_names=("Metadata", "AfterTrack"),
    )
    def track_added(self) -> tuple[dict[str, tuple[str, Any]], str]:
        raise NotImplementedError

    @dbus_signal_async(
        signal_signature="o",
        signal_args_names=("TrackId",),
    )
    def track_removed(self) -> str:
        raise NotImplementedError

    @dbus_signal_async(
        signal_signature="oa{sv}",
        signal_args_names=("TrackId", "Metadata"),
    )
    def track_metadata_changed(self) -> tuple[str, dict[str, tuple[str, Any]]]:
        raise NotImplementedError
