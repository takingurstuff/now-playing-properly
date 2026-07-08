import sys
import inspect
import traceback
import importlib.util
from pathlib import Path
from .config import Config
from typing import Any, Optional
from .log_manager import setup_logging
from importlib.metadata import entry_points
from ..common.plugin_types import Plugin, REQUIRED, STATE, NAME

logger = setup_logging()


def preprocess_plugin(module: Any) -> list[Plugin]:
    # PEP517 entry points
    if isinstance(module, Plugin):
        try:
            module()
            return module
        except TypeError as e:
            logger.exception("Entry Point pointed to malformed class")

    # 0. helpers
    def get_local_attrs(module):
        local_attrs = []
        for name in dir(module):
            if name.startswith("__"):
                continue
            attr = getattr(module, name)
            if (
                not attr
                or inspect.ismodule(attr)
                or (
                    hasattr(attr, "__module__")
                    and (attr.__module__ != module.__name__ and attr.__module__ != NAME)
                )
            ):
                continue
            local_attrs.append(attr)
        return local_attrs

    module_attrs = get_local_attrs(module)
    # 1. Verify that single file or non PEP517 modules has a Plugin class defined
    plugin_objects = [a for a in module_attrs if isinstance(a, Plugin)]

    def check_plugin_validity(p: type[Plugin]) -> Plugin | None:
        try:
            p()
            return p
        except TypeError as e:
            logger.exception("Malformed Plugin Class")

    plugin_objects = [p for p in module_attrs if check_plugin_validity(p)]
    # 2. Collect Local names into a plugin if possible and append it to plugin list for this module
    if all(attr in module_attrs for attr in REQUIRED):
        try:
            if all(attr in module_attrs for attr in STATE):
                plugin_objects.append(
                    Plugin(
                        name=module.name if module.name else module.__name__,
                        State=module.State,
                        create_state=module.create_state,
                        Config=module.Config,
                        activation=module.activation,
                        plugin_function=module.plugin_function,
                    )
                )
            else:
                plugin_objects.append(
                    Plugin(
                        name=module.name if module.name else module.__name__,
                        Config=module.Config,
                        activation=module.activation,
                        plugin_function=module.plugin_function,
                    )
                )
        except TypeError as e:
            logger.exception("One or multiple names in module is malformed")
    return plugin_objects


def load_single_plugin_file(plugin_path: Path) -> Any:
    if not plugin_path.is_file():
        logger.error(f"Plugin {plugin_path} is not a single file")
    spec = importlib.util.spec_from_file_location(plugin_path.stem, plugin_path)
    if spec is None or spec.loader is None:
        logger.error(
            f"Could not load plugin {plugin_path}, did it get moved or deleted?"
        )

    module = importlib.util.module_from_spec(spec)
    sys.modules[plugin_path.stem] = module
    spec.loader.exec_module(module)

    return module


def load_single_plugin_module(plugin_path: Path) -> Any:
    if not plugin_path.is_dir():
        logger.error(f"Plugin {plugin_path} is not a multi file python module")
    init_path = plugin_path / "__init__.py"
    if not init_path.exists():
        logger.error(f"Plugin {plugin_path} missing __init__.py")
    spec = importlib.util.spec_from_file_location(plugin_path.stem, init_path)
    if spec is None or spec.loader is None:
        logger.error(f"Plugin {plugin_path} is malformed, did it get moved or deleted")
    module = importlib.util.module_from_spec(spec)
    module.__path__ = [str(plugin_path)]
    sys.modules[plugin_path.stem] = module
    try:
        spec.loader.exec_module(module)
    except Exception as e:
        del sys.modules[plugin_path.stem]
        logger.exception("module initialization failed:")

    return module


def load_site_packages_plugins(project_name: str, component_name: str) -> list[Any]:
    plugins = {}
    discovered = entry_points(group=f"{project_name}.{component_name}")
    if not discovered:
        return "No site-packages plugins found"
    for plugin in discovered:
        try:
            plugin_module = plugin.load()
            plugins[plugin.name] = plugin_module
        except Exception as e:
            plugins[plugin.name] = f"""Plugin Module {plugin.name} failed to load:
Reason: {e}
Traceback: {traceback.format_exc()}"""
    return list(plugins.values())


def load_all_plugins(config: Config):
    package_name = __package__.split(".")[0] if __package__ else __name__
    plugins = load_site_packages_plugins(package_name, "plugins")

    def traverse(path: Path, plugins: list[Any]):
        for node in path.iterdir():
            if node.is_file() and node.name.endswith(".py"):
                if p := load_single_plugin_file(path / node):
                    plugins.append(p)
            elif node.is_dir() and (path / node / "__init__,py").exists():
                if p := load_single_plugin_module(path / node):
                    plugins.append(p)
            elif node.is_dir():
                traverse(path, plugins)
            else:
                logger.warning(f"{path / node} is not a python file nor a module")

    traverse(config.general.plugins_dir, plugins)

    final_plugins = [plugin_obj for i in plugins for plugin_obj in preprocess_plugin(i)]
    return final_plugins
