"""
Unfinished, we will get em next time
"""

import time
import asyncio
from .config import Config
from pypresence.exceptions import PyPresenceException
from .queue_types import UpdateEvent, SeekEvent, PluginResponseEvent
from pypresence.presence import ActivityType, AioPresence, StatusDisplayType

CLIENT_ID = "1524275168631849043"
UPDATE_DEBOUNCE_SECS = 15


class DiscordHandler:
    def __init__(
        self,
        equeue: asyncio.Queue[UpdateEvent, SeekEvent, PluginResponseEvent],
        loop: asyncio.BaseEventLoop,
        config: Config,
    ):
        self.equeue = equeue
        self.presence = AioPresence(client_id=CLIENT_ID, loop=loop)
        self.last_update_ts = time.time()
        self.config = config

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.stop()

    async def start(self):
        if not self.config.discord.enabled:
            return
        await self.presence.connect()
        await self.presence.clear()

    async def stop(self):
        if not self.config.discord.enabled:
            return
        await self.presence.clear()
        await self.presence.close()

    async def update_loop(self):
        try:
            while True:

                event = await self.equeue.get()
                if not self.config.discord.enabled:
                    continue
                if rem := (time.time() - self.last_update_ts) <= UPDATE_DEBOUNCE_SECS:
                    await asyncio.sleep(rem)
                self.last_update_ts = time.time()
                if isinstance(event, UpdateEvent):
                    udict = {
                        "activity_type": ActivityType.WATCHING,
                        "status_display_type": StatusDisplayType.DETAILS,
                    }
                    if event.metadata and event.start_time:
                        udict.update(
                            {
                                "details": event.metadata.title,
                                "state": ", ".join(event.metadata.artist),
                                "start": event.start_time,
                                "end": event.start_time + event.metadata.duration,
                            }
                        )
                self.equeue.task_done()
        except asyncio.CancelledError:
            return
