from __future__ import annotations
from typing import Any, Dict, List, Tuple, Optional

from sdbus import (
    SdBus,
    dbus_method_async,
    dbus_signal_async,
    dbus_property_async,
    DbusInterfaceCommonAsync,
)


class MprisRootInterface(
    DbusInterfaceCommonAsync, interface_name="org.mpris.MediaPlayer2"
):

    def __init__(self, bus: Optional[SdBus] = None):
        """
        Root MPRIS Interface: org.mpris.MediaPlayer2
        Handles identity, basic windowing actions, and capabilities.

        :param SdBus bus:
            Optional D-Bus connection.
            If not passed the default D-Bus will be used.
        """
        super().__init__()
        self._proxify(
            "org.mpris.MediaPlayer2",
            "/org/mpris/MediaPlayer2/",
            bus,
        )

    # --- Methods ---

    @dbus_method_async()
    async def Raise(self) -> None:
        """Brings the media player's user interface to the front."""
        pass

    @dbus_method_async()
    async def Quit(self) -> None:
        """Causes the media player to stop running."""
        pass

    # --- Properties ---

    @dbus_property_async(property_signature="b")
    def CanQuit(self) -> bool:
        return True

    @dbus_property_async(property_signature="b")
    def Fullscreen(self) -> bool:
        return False

    @Fullscreen.setter
    def Fullscreen(self, value: bool) -> None:
        """Example of a writable property setter in sdbus."""
        pass

    @dbus_property_async(property_signature="b")
    def CanSetFullscreen(self) -> bool:
        return False

    @dbus_property_async(property_signature="b")
    def CanRaise(self) -> bool:
        return False

    @dbus_property_async(property_signature="b")
    def HasTrackList(self) -> bool:
        return False

    @dbus_property_async(property_signature="s")
    def Identity(self) -> str:
        return "Python SDBus Media Player"

    @dbus_property_async(property_signature="s")
    def DesktopEntry(self) -> str:
        return "my-media-player"

    @dbus_property_async(property_signature="as")
    def SupportedUriSchemes(self) -> List[str]:
        return ["file", "http", "https"]

    @dbus_property_async(property_signature="as")
    def SupportedMimeTypes(self) -> List[str]:
        return ["audio/mpeg", "audio/flac", "audio/ogg"]


class MprisPlayerInterface(
    DbusInterfaceCommonAsync, interface_name="org.mpris.MediaPlayer2.Player"
):

    def __init__(self, bus: Optional[SdBus] = None):
        """
        Player MPRIS Interface: org.mpris.MediaPlayer2.Player
        Handles transport controls, volume, metadata, and playback status.

            :param SdBus bus:
                Optional D-Bus connection.
                If not passed the default D-Bus will be used.
        """

        super().__init__()
        self._proxify(
            "org.mpris.MediaPlayer2.Player",
            "/org/mpris/MediaPlayer2",
            bus,
        )

    # --- Methods ---

    @dbus_method_async()
    async def Next(self) -> None:
        pass

    @dbus_method_async()
    async def Previous(self) -> None:
        pass

    @dbus_method_async()
    async def Pause(self) -> None:
        pass

    @dbus_method_async()
    async def PlayPause(self) -> None:
        pass

    @dbus_method_async()
    async def Stop(self) -> None:
        pass

    @dbus_method_async()
    async def Play(self) -> None:
        pass

    @dbus_method_async(input_signature="x")
    async def Seek(self, offset: int) -> None:
        """offset is in microseconds (int64)"""
        pass

    @dbus_method_async(input_signature="ox")
    async def SetPosition(self, track_id: str, position: int) -> None:
        """track_id is an Object Path (o), position is in microseconds (int64)"""
        pass

    @dbus_method_async(input_signature="s")
    async def OpenUri(self, uri: str) -> None:
        pass

    # --- Properties ---

    @dbus_property_async(property_signature="s")
    def PlaybackStatus(self) -> str:
        # Valid values: "Playing", "Paused", "Stopped"
        return "Stopped"

    @dbus_property_async(property_signature="s")
    def LoopStatus(self) -> str:
        # Valid values: "None", "Track", "Playlist"
        return "None"

    @LoopStatus.setter
    def LoopStatus(self, value: str) -> None:
        pass

    @dbus_property_async(property_signature="d")
    def Rate(self) -> float:
        return 1.0

    @Rate.setter
    def Rate(self, value: float) -> None:
        pass

    @dbus_property_async(property_signature="b")
    def Shuffle(self) -> bool:
        return False

    @Shuffle.setter
    def Shuffle(self, value: bool) -> None:
        pass

    @dbus_property_async(property_signature="a{sv}")
    def Metadata(self) -> Dict[str, Any]:
        """
        Returns metadata for the current track.
        In sdbus, variants ('v') are often represented as a tuple of (signature, value).
        Example: {"mpris:length": ("x", 120000000), "xesam:title": ("s", "My Song")}
        """
        return {}

    @dbus_property_async(property_signature="d")
    def Volume(self) -> float:
        return 1.0

    @Volume.setter
    def Volume(self, value: float) -> None:
        pass

    @dbus_property_async(property_signature="x")
    def Position(self) -> int:
        """Playback position in microseconds."""
        return 0

    @dbus_property_async(property_signature="d")
    def MinimumRate(self) -> float:
        return 1.0

    @dbus_property_async(property_signature="d")
    def MaximumRate(self) -> float:
        return 1.0

    @dbus_property_async(property_signature="b")
    def CanGoNext(self) -> bool:
        return True

    @dbus_property_async(property_signature="b")
    def CanGoPrevious(self) -> bool:
        return True

    @dbus_property_async(property_signature="b")
    def CanPlay(self) -> bool:
        return True

    @dbus_property_async(property_signature="b")
    def CanPause(self) -> bool:
        return True

    @dbus_property_async(property_signature="b")
    def CanSeek(self) -> bool:
        return True

    @dbus_property_async(property_signature="b")
    def CanControl(self) -> bool:
        return True

    # --- Signals ---

    @dbus_signal_async(signal_signature="x")
    def Seeked(self) -> int:
        """
        Emitted when a seek occurs.
        Clients call this method on the python object to broadcast the signal.
        """
        raise NotImplementedError


class DbusPropertiesInterface(
    DbusInterfaceCommonAsync, interface_name="org.freedesktop.DBus.Properties"
):

    def __init__(self, bus: Optional[SdBus] = None):
        """
        Standard D-Bus Properties Interface: org.freedesktop.DBus.Properties
        Allows getting, setting, and listening to property changes across any interface.

            :param SdBus bus:
                Optional D-Bus connection.
                If not passed the default D-Bus will be used.
        """

        super().__init__()
        self._proxify(
            "org.freedesktop.DBus.Properties",
            "/org/mpris/MediaPlayer2",
            bus,
        )

    # --- Methods ---

    @dbus_method_async(input_signature="ss", result_signature="v")
    async def Get(self, interface_name: str, property_name: str) -> Tuple[str, Any]:
        """
        Gets a single property.
        Returns a D-Bus variant 'v', represented in sdbus as a tuple: (signature, value).
        """
        ...

    @dbus_method_async(input_signature="ssv")
    async def Set(
        self, interface_name: str, property_name: str, value: Tuple[str, Any]
    ) -> None:
        """
        Sets a single property.
        'value' must be a D-Bus variant tuple, e.g., ("b", True) or ("d", 0.5).
        """
        ...

    @dbus_method_async(input_signature="s", result_signature="a{sv}")
    async def GetAll(self, interface_name: str) -> Dict[str, Tuple[str, Any]]:
        """
        Gets all properties and their values for a specific interface.
        Returns a dictionary mapping property names to variant tuples.
        """
        ...

    # --- Signals ---

    @dbus_signal_async(signal_signature="sa{sv}as")
    def PropertiesChanged(self) -> Tuple[str, Dict[str, Tuple[str, Any]], List[str]]:
        """
        Emitted when one or more properties change.

        Returns a tuple containing:
        1. (str) The name of the interface where properties changed.
        2. (dict) A dictionary of the changed properties and their new values.
        3. (list) A list of property names that were invalidated (changed, but no value provided).
        """
        raise NotImplementedError
