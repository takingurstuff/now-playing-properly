import os
import asyncio
from enum import Enum, auto
from typing import Any, Literal
from ..common.resolv_strat import PluginConflictResolvStrat
from pydantic import BaseModel, DirectoryPath, FilePath, Field
from systemd.daemon import listen_fds, listen_fds_with_names, notify


class GeneralSettings(BaseModel):
    debug_mode: bool
    socket_path: DirectoryPath
    runtime_file_dir: DirectoryPath
    cache_file_dir: DirectoryPath
    plugins_dir: DirectoryPath
    plugin_conflict_resolv_strat: PluginConflictResolvStrat


class ResourceSettings(BaseModel):
    max_connections: int = Field(ge=1, le=200)
    max_keepalive_connections: int = Field(ge=1, le=100)
    connection_keepalive: float = Field(ge=3, le=60)
    domain_blacklists: frozenset[str]
    max_worker_threads: int = Field(ge=1, le=os.cpu_count() * 2)


class DiscordSettings(BaseModel):
    enabled: bool = False
    hide_paused: bool = True


class Config(BaseModel):
    general: GeneralSettings
    resource: ResourceSettings
    discord: DiscordSettings
    plugins: dict[str, dict[str, Any]]


class FDS:
    main_sock_fd: int

    def __init__(self):
        named_fds = {n: f for f, n in listen_fds_with_names().items()}
        unamed_fds = listen_fds()
        self.main_sock_fd = named_fds.get("app_listen_fd", unamed_fds[0])
        self.named_fds = named_fds
        self.unamed_fds = unamed_fds

    def store(self):
        names, fds = self.named_fds.keys(), self.named_fds.values()
        for i, n in enumerate(names):
            if n == "app_listen_fd":
                continue
            notify(f"FDSTORE=1\nFDNAME={n}", fds=[fds[i]])
        if self.unamed_fds:
            notify(f"FDSTORE=1", fds=[self.unamed_fds])


class Watchdog:
    def __init__(self):
        self.secs = os.environ.get("WATCHDOG_USEC") / 1000
        self.active = os.environ.get("WATCHDOG_PID", 78941237890234590) == os.getpid()

    async def wd(self):
        try:
            while True:
                await asyncio.sleep(self.secs / 2)
                if self.active:
                    notify("WATCHDOG=1")
        except asyncio.CancelledError:
            return
