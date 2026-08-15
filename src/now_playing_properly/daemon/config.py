import os
import asyncio
from enum import Enum, auto
from typing import Any, Literal
from ..common.resolv_strat import PluginConflictResolvStrat
from pydantic import BaseModel, DirectoryPath, FilePath, Field
from systemd.daemon import listen_fds, listen_fds_with_names, notify


class GeneralSettings(BaseModel):
    debug_mode: bool
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
