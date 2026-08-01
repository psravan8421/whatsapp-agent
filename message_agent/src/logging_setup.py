"""Central logging configuration: console handler plus a file handler."""

import logging
import os
from typing import Optional

_LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
_ROOT_NAME = "agent"
_file_handler: Optional[logging.FileHandler] = None


def get_logger(name: str = _ROOT_NAME) -> logging.Logger:
    """Return a logger writing to the console (and the log file once configured)."""
    root = logging.getLogger(_ROOT_NAME)
    if not root.handlers:
        console = logging.StreamHandler()
        console.setFormatter(logging.Formatter(_LOG_FORMAT))
        root.addHandler(console)
        root.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())
        root.propagate = False
    return logging.getLogger(name)


def configure_file_logging(log_path: str) -> str:
    """Attach a file handler at `log_path`, creating parent directories as needed."""
    global _file_handler

    root = get_logger()
    os.makedirs(os.path.dirname(os.path.abspath(log_path)), exist_ok=True)

    if _file_handler is not None:
        root.removeHandler(_file_handler)
        _file_handler.close()

    _file_handler = logging.FileHandler(log_path, encoding="utf-8")
    _file_handler.setFormatter(logging.Formatter(_LOG_FORMAT))
    root.addHandler(_file_handler)
    return log_path
