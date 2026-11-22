import asyncio
from typing import Union
from .config import Config
from .plugins import PluginExecutor
from .plugin_loader import load_all_plugins
from .player import Player, discover_initial
from .server_interfaces import CombinedObject
from ..common.communication_models import (
    SeekEvent,
    UpdateEvent,
    SeekRequest,
    ActionRequest,
)


class App:
    def __init__(self, config: Config):
        self.players: list[
            tuple[Player, asyncio.Queue[Union[ActionRequest, SeekRequest]]]
        ] = []
        self.metadata_event_queue: asyncio.Queue[UpdateEvent | SeekEvent] = (
            asyncio.Queue()
        )
        self.config = config

        self.all_plugins = load_all_plugins(config)

    async def __aenter__(self):
        self.metadata_event_queue, self.players = await discover_initial(self.config)
