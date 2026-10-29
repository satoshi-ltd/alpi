"""Shared subsystem logging — one rotating file per subsystem in ``~/.alpi/logs/``.

Every subsystem writes to ``{home}/logs/{subsystem}.log`` with the same
format so ``alpi logs`` can merge them cleanly. The logger is namespaced
(``alpi.<subsystem>``) and does NOT propagate to the root — it's
self-contained, so importing this from inside the TUI doesn't leak lines
into stdout.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"
MAX_BYTES = 1_000_000
# RotatingFileHandler with backupCount=0 silently no-ops rollover (stdlib quirk).
BACKUP_COUNT = 3


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


def get_subsystem_logger(home: Path, subsystem: str) -> logging.Logger:
    """Return the dedicated logger for ``subsystem``, configured lazily."""
    name = f"alpi.{subsystem}"
    logger = logging.getLogger(name)
    if getattr(logger, "_alpi_configured", False):
        return logger

    try:
        d = log_dir(home)
        d.mkdir(parents=True, exist_ok=True)
        handler = PrivateRotatingFileHandler(
            d / f"{subsystem}.log", maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT,
        )
        handler.setFormatter(RedactingFormatter(FORMAT))
        logger.addHandler(handler)
    except OSError:
        pass  # no-op logger — better than crashing if the dir can't be made

    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger._alpi_configured = True  # type: ignore[attr-defined]
    return logger
