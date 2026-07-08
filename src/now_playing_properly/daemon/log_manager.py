import sys
import logging
import inspect
from systemd import journal


def setup_logging(verbose: bool = False, logfile: str | None = None):
    """
    Call this anywhere. It configures the root logger once, then
    returns a logger named after the calling module (dot-notation).
    """
    # 1. Identify the calling module's name
    caller_frame = inspect.stack()[1]
    caller_module = inspect.getmodule(caller_frame[0])
    logger_name = caller_module.__name__ if caller_module else "__main__"

    root_logger = logging.getLogger()

    # 2. Singleton Guard: Only configure if the root logger has no handlers
    if not root_logger.handlers:
        level = logging.DEBUG if verbose else logging.INFO
        handlers = []

        # Determine formatting based on TTY vs Daemon/Background execution
        if sys.stderr.isatty():
            # Cyan time, Green module name for local dev
            fmt = "\033[36m%(asctime)s\033[0m [%(levelname)s] \033[32m%(name)s\033[0m: %(message)s"
            h = logging.StreamHandler(sys.stderr)
            h.setFormatter(logging.Formatter(fmt, datefmt="%H:%M:%S"))
            handlers.append(h)
        else:
            # Native systemd journal handling
            handlers.append(journal.JournalHandler())

        if logfile:
            fh = logging.FileHandler(logfile)
            fh.setFormatter(
                logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
            )
            handlers.append(fh)

        logging.basicConfig(level=level, handlers=handlers)

    # 3. Return the logger specific to the file that called this function
    return logging.getLogger(logger_name)
