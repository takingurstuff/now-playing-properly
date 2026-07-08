import os
import socket
import asyncio
import tomllib
from pathlib import Path
from .orchestrator import App
from .log_manager import setup_logging
from .config import Config, FDS, Watchdog

logger = setup_logging(os.environ.get("VERBOSE", False))

CONFIG_LOCATION = os.environ.get(
    "CONFIG_DIR", Path("~") / ".config" / "now_playing_properly"
)


async def startup():
    conf_file = CONFIG_LOCATION / "config.toml"
    with open(conf_file, "rb") as f:
        conf = tomllib.load(f)
    config = Config.model_validate(conf)
    fds = None
    if config.general.debug_mode:

        class FixFD:
            def __init__(self, fd: int):
                self.main_sock_fd = fd

        # 1. Clean up old socket files
        if os.path.exists(config.general.socket_path):
            os.remove(config.general.socket_path)

        # 2. Create and bind the socket
        mock_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        mock_socket.bind(config.general.socket_path)
        mock_socket.listen(5)  # Put it in listening state, just like systemd would
        fds = FixFD(mock_socket.fileno())
        watchdog = Watchdog()
        wd_task = asyncio.create_task(watchdog.wd())
        with App(config, fds) as app:
            while True:
                await asyncio.sleep(120)
    else:
        fds = FDS()
        watchdog = Watchdog()
        wd_task = asyncio.create_task(watchdog.wd())
        try:
            with App(Config, FDS) as app:
                while True:
                    await asyncio.sleep(120)
        except Exception as e:
            logger.exception("Critical, Shutting down")
            wd_task.cancel()
            await wd_task


def main():
    asyncio.run(startup())
