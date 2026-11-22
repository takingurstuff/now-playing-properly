import sys
import inspect
import traceback
import importlib.util
from pathlib import Path
from .config import Config
from typing import Any, Optional
from .log_manager import setup_logging
from importlib.metadata import entry_points
from ..common.plugin_types import BasePlugin

PLUGIN_ENTRY_NAME = "now-playing-properly.plugins"


logger = setup_logging()


def _check_pkg_for_plugins(config: Config):
    plugins = entry_points(group=PLUGIN_ENTRY_NAME)
    loaded_plugins = [p.load() for p in plugins if isinstance(p.load(), BasePlugin)]
    return loaded_plugins


# Only searches 1 layer deep, for multi file non bundled plugins please create __init__.py with all the plugin defs imported, the app will not search the entire subdirectory, if __init__.py is not defined the plugin will be deemed malformed, tho i highly recommend for multi file plugins to be packaged since its cleaner for both the app and dev
def _check_plugin_dir_for_plugins(config: Config):
    plugins = []
    for d in config.general.plugins_dir.iterdir():
        pbundlename = d.stem
        if d.is_file() and d.name.endswith(".py"):
            spec = importlib.util.spec_from_file_location(pbundlename, d)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            plugins.extend(
                plugin
                for _, plugin in module.__dict__.items()
                if isinstance(plugin, BasePlugin)
            )

        elif d.is_dir():
            if "__init__.py" in d:
                pass
