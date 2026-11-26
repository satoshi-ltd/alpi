"""Shared subsystem logging — one rotating file per subsystem in ``~/.alpi/logs/``.

Every subsystem writes to ``{home}/logs/{subsystem}.log`` with the same
format so ``alpi logs`` can merge them cleanly. The logger is namespaced
(``alpi.<subsystem>``) and does NOT propagate to the root — it's
self-contained, so importing this from inside the TUI doesn't leak lines
into stdout.
"""

from __future__ import annotations

import logging
import os
import threading
from collections import OrderedDict
from logging.handlers import RotatingFileHandler
from pathlib import Path

FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"
MAX_BYTES = 1_000_000
# RotatingFileHandler with backupCount=0 silently no-ops rollover (stdlib quirk).
BACKUP_COUNT = 3

# Each entry holds an open file; the cap keeps a process that sees many homes inside its descriptor limit.
MAX_OPEN = 32
_loggers: OrderedDict[str, logging.Logger] = OrderedDict()
_guard = threading.Lock()


class RedactingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        from alpi._redact import redact
        copy = logging.makeLogRecord(record.__dict__)
        copy.msg, copy.args = redact(record.getMessage()), None
        if copy.exc_info:
            copy.exc_text = redact(copy.exc_text or self.formatException(copy.exc_info))
            copy.exc_info = None
        if copy.stack_info:
            copy.stack_info = redact(copy.stack_info)
        return redact(super().format(copy))


class PrivateRotatingFileHandler(RotatingFileHandler):
    def _open(self):
        from alpi.secrets_io import open_private
        return open_private(self.baseFilename)


def log_dir(home: Path) -> Path:
    """The canonical logs directory for a profile."""
    return home / "logs"


def log_path(home: Path, subsystem: str) -> Path:
    return log_dir(home) / f"{subsystem}.log"


def _moved(handler: RotatingFileHandler) -> bool:
    try:
        on_disk = os.stat(handler.baseFilename)
        held = os.fstat(handler.stream.fileno())
    except (OSError, AttributeError, ValueError):
        return True
    return (on_disk.st_dev, on_disk.st_ino) != (held.st_dev, held.st_ino)


def _handler(path: Path) -> logging.Handler:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        handler: logging.Handler = PrivateRotatingFileHandler(path, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT)
    except OSError:
        return logging.NullHandler()
    handler.setFormatter(RedactingFormatter(FORMAT))
    return handler


def _replace(logger: logging.Logger, handler: logging.Handler) -> None:
    current = logger.handlers[0]
    logger.addHandler(handler)
    logger.removeHandler(current)
    current.close()


def get_subsystem_logger(home: Path, subsystem: str) -> logging.Logger:
    path = log_path(home, subsystem)
    key = os.path.abspath(path)
    with _guard:
        logger = _loggers.get(key)
        if logger is None:
            # Not logging.getLogger: that is one logger per name for the whole process, so every home would share one file.
            logger = _loggers[key] = logging.Logger(f"alpi.{subsystem}", logging.INFO)
            logger.propagate = False
            logger.addHandler(_handler(path))
            while len(_loggers) > MAX_OPEN:
                _, idle = _loggers.popitem(last=False)
                _replace(idle, logging.NullHandler())
            return logger
        _loggers.move_to_end(key)
        current = logger.handlers[0]
        if not isinstance(current, RotatingFileHandler) or _moved(current):
            _replace(logger, _handler(path))
        return logger


def _reset_after_fork() -> None:
    global _guard
    _guard = threading.Lock()


if hasattr(os, "register_at_fork"):
    os.register_at_fork(after_in_child=_reset_after_fork)
