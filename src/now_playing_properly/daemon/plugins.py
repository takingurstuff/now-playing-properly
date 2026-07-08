import asyncio
import inspect
from .config import Config
from types import TracebackType
from typing import Optional, Type, Any
from .log_manager import setup_logging
from concurrent.futures import ThreadPoolExecutor
from httpx import Client, AsyncClient, Request, Limits
from .queue_types import UpdateEvent, PluginResponseEvent
from ..common.resolv_strat import PluginConflictResolvStrat
from ..common.plugin_types import (
    Plugin,
    Resources,
    PluginState,
    BadDomainError,
    PluginResponse,
    BasePluginConfig,
)
from ..common.metadata_spec import AudioMetadata

logger = setup_logging()


class PluginExecutor:
    def __init__(
        self,
        plugins: list[Plugin],
        config: Config,
        task_queue: asyncio.Queue[UpdateEvent],
        response_queue: asyncio.Queue[PluginResponseEvent],
    ):
        self.plugins = plugins
        self.config = config
        self.task_queue = task_queue
        self.response_queuer = response_queue
        self.config_store: dict[str, Optional[BasePluginConfig]]
        self.state_store: dict[str, Optional[PluginState]]
        self.loop = asyncio.get_running_loop()

    def _fill_plugin_stores(self):
        for plugin in self.plugins:
            name = plugin.name
            config_model = plugin.Config
            state_creator = plugin.create_state
            if name not in self.config.plugins:
                logger.warning(
                    f"Plugin {name} not configured in config file, skipping loading, this plugin will be ignored this session, please there is a section named [plugins.{name}] in your config file"
                )
            try:
                config = config_model.model_validate(self.config.plugins[name])
                self.config_store[name] = config
            except Exception as e:
                logger.exception(f"Configuration parsing failed for plugin {name}")
                self.config_store[name] = None

            try:
                state = state_creator()
                self.state_store[name] = state
            except Exception as e:
                logger.exception(f"State Initialization for plugin {name} failed")
                self.state_store[name] = None

    async def __aenter__(self):
        await self.start()
        return self

    async def start(self):
        def _ebl(request: Request, _bl=self.config.resource.domain_blacklists):
            if request.url.host in _bl:
                raise BadDomainError(f"Domain {request.url.host} is blacklisted")

        self.thread_pool = ThreadPoolExecutor(
            max_workers=self.config.resource.max_worker_threads
        )
        limits = Limits(
            max_connections=self.config.resource.max_connections,
            max_keepalive_connections=self.config.resource.max_keepalive_connections,
            keepalive_expiry=self.config.resource.connection_keepalive,
        )
        async_conn_pool = await AsyncClient(
            limits=limits, event_hooks={"request": [_ebl]}
        )
        sync_conn_pool = Client(limits=limits, event_hooks={"request": [_ebl]})
        self.resources = Resources(async_conn_pool, sync_conn_pool)
        self._ltask = asyncio.create_task(self._listen_task())

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ):
        self.stop()

    async def stop(self):
        await self.task_queue.put(None)
        await self.task_queue.join()
        await self._ltask
        await self.resources.network_async.aclose()
        self.resources.network_sync.close()
        self.thread_pool.shutdown()

    async def _exec_one_plugin(
        self, plugin: Plugin, am: AudioMetadata
    ) -> PluginResponse | None:
        state = self.config_store.get(plugin.name)
        config = self.config_store.get(plugin.name)
        if not state or not config or not config.enabled:
            return
        if plugin.activation(state, config, am):
            try:
                if inspect.iscoroutinefunction(plugin.plugin_function):
                    response, state = await plugin.plugin_function(
                        state, config, self.resources, am
                    )
                else:
                    response, state = await self.loop.run_in_executor(
                        self.thread_pool,
                        plugin.plugin_function,
                        *(state, config, self.resources, am),
                    )
                self.state_store[plugin.name] = state
                return response
            except:
                logger.exception(f"Plugin {plugin.name} encountered an error")

    def _merge_all(
        self, responses: dict[str, PluginResponse], am: AudioMetadata
    ) -> tuple[AudioMetadata, dict[str, dict[str, Any]]]:
        # Simple merging of extra data
        all_extra_data = {n: r.added_keys for n, r in responses.items()}
        # How to intepert the priority
        policy = self.config.general.plugin_conflict_resolv_strat

        def _get_prio(x: str, s=self):
            return s.config_store[x].priority

        # In what order to overwrite plugin data in
        order = sorted(
            responses.keys(),
            _get_prio,
            reverse=policy == PluginConflictResolvStrat.HIGH_FIRST,
        )

        # Initialize Copy
        final_am = AudioMetadata(
            am.track_id,
            am.duration,
            am.art_url,
            am.album.copy(),
            am.title,
            am.lyrics,
            am.url,
            am.album_artist.copy(),
            am.artist.copy(),
            am.genre.copy(),
            am.composer.copy(),
            am.lyricist.copy(),
            am.comment.copy(),
            am.track_number,
            am.disc_number,
            am.bpm,
            am.rating_auto,
            am.rating_user,
            am.play_count,
            am.content_created,
            am.first_use,
            am.last_use,
        )

        for name in order:
            plugin_am = responses[name].modified_keys

            final_am.track_id = (
                plugin_am.track_id if plugin_am.track_id else final_am.track_id
            )
            final_am.duration = (
                plugin_am.duration if plugin_am.duration else final_am.duration
            )
            final_am.art_url = (
                plugin_am.art_url if plugin_am.art_url else final_am.art_url
            )
            final_am.album.extend(plugin_am.album if plugin_am.album else [])
            final_am.title = plugin_am.title if plugin_am.title else final_am.title
            final_am.lyrics = plugin_am.lyrics if plugin_am.lyrics else final_am.lyrics
            final_am.url = plugin_am.url if plugin_am.url else final_am.url
            final_am.album_artist.extend(
                plugin_am.album_artist if plugin_am.album_artist else []
            )
            final_am.artist.extend(plugin_am.artist if plugin_am.artist else [])
            final_am.genre.extend(plugin_am.genre if plugin_am.genre else [])
            final_am.composer.extend(plugin_am.composer if plugin_am.composer else [])
            final_am.lyricist.extend(plugin_am.lyricist if plugin_am.lyricist else [])
            final_am.comment.extend(plugin_am.comment if plugin_am.comment else [])
            final_am.track_number = (
                plugin_am.track_number
                if plugin_am.track_number
                else final_am.track_number
            )
            final_am.disc_number = (
                plugin_am.disc_number if plugin_am.disc_number else final_am.disc_number
            )
            final_am.bpm = plugin_am.bpm if plugin_am.bpm else final_am.bpm
            final_am.rating_auto = (
                plugin_am.rating_auto if plugin_am.rating_auto else final_am.rating_auto
            )
            final_am.rating_user = (
                plugin_am.rating_user if plugin_am.rating_user else final_am.rating_user
            )
            final_am.play_count = (
                plugin_am.play_count if plugin_am.play_count else final_am.play_count
            )
            final_am.content_created = (
                plugin_am.content_created
                if plugin_am.content_created
                else final_am.content_created
            )
            final_am.first_use = (
                plugin_am.first_use if plugin_am.first_use else final_am.first_use
            )
            final_am.last_use = (
                plugin_am.last_use if plugin_am.last_use else final_am.last_use
            )
        return final_am, all_extra_data

    async def _exec_all_plugins(self, am: AudioMetadata):
        all_plugin_futures = [self._exec_one_plugin(f, am) for f in self.plugins]
        all_plugin_responses = {
            n.name: r
            for r in await asyncio.gather(*all_plugin_futures)
            for n in self.plugins
        }

        processed_am, extra_data = self._merge_all(all_plugin_responses, am)
        return processed_am, extra_data

    async def _listen_task(self):
        while True:
            event = await self.task_queue.get()
            if event is None:
                break
            rid = event.id
            final_am, extra_data = await self._exec_all_plugins(event.metadata)
            resp = PluginResponseEvent(event.player, final_am, extra_data, rid)
            await self, self.response_queuer.put(resp)
            await self.task_queue.task_done()
