"""Per-chat session pointer for gateway platforms.

One JSON file per profile at ``~/.alpi/<profile>/gateway/sessions/_map.json``
keyed by ``chat_id`` → ``session_id``. ``chat_id`` is whatever the
platform puts in ``IncomingMessage.external_chat_id``: a Telegram
chat id, a sender email for IMAP/Gmail, or whatever the webhook
caller sent. Same mechanism, natural per-platform semantics:
Telegram gets per-chat threading, IMAP/Gmail get per-sender
threading. ``/new`` removes the pointer but never touches the
session file — history stays.

Concurrency: gateway runs in one process, but the CLI subprocess
it spawns reads + writes this file too. ``fcntl`` locking keeps
the two from racing.
"""

from __future__ import annotations

import contextlib
import fcntl
import json
from pathlib import Path


_FILENAME = "_map.json"


def _path(home: Path) -> Path:
    return home / "gateway" / "sessions" / _FILENAME


def _lock_path(home: Path) -> Path:
    return home / "gateway" / "sessions" / "_map.lock"


@contextlib.contextmanager
def _locked(home: Path):
    lp = _lock_path(home)
    lp.parent.mkdir(parents=True, exist_ok=True)
    with lp.open("a") as fh:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


def _load(home: Path) -> dict[str, str]:
    p = _path(home)
    if not p.exists():
        return {}
    try:
        with p.open("r") as fh:
            fcntl.flock(fh.fileno(), fcntl.LOCK_SH)
            try:
                data = json.load(fh)
            finally:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
    except (OSError, json.JSONDecodeError):
        return {}
    return {str(k): str(v) for k, v in data.items()} if isinstance(data, dict) else {}


def _save(home: Path, data: dict[str, str]) -> None:
    p = _path(home)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    with tmp.open("w") as fh:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        try:
            json.dump(data, fh, indent=2, sort_keys=True)
            fh.flush()
        finally:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
    tmp.replace(p)


def get(home: Path, chat_id: str) -> str | None:
    """Return the session id currently bound to ``chat_id``, or None."""
    if not chat_id:
        return None
    return _load(home).get(chat_id) or None


def set(home: Path, chat_id: str, session_id: str) -> None:  # noqa: A001
    """Bind ``chat_id`` to ``session_id``. Overwrites any prior pointer."""
    if not chat_id or not session_id:
        return
    with _locked(home):
        data = _load(home)
        data[chat_id] = session_id
        _save(home, data)


def forget(home: Path, chat_id: str) -> bool:
    """Remove the pointer for ``chat_id``. Returns True if something was dropped.

    The underlying session file is NOT deleted — only the "which session is
    active for this chat" mapping. Historical sessions stay on disk under
    ``gateway/sessions/*.json``.
    """
    if not chat_id:
        return False
    with _locked(home):
        data = _load(home)
        if chat_id not in data:
            return False
        del data[chat_id]
        _save(home, data)
        return True


def all_pointers(home: Path) -> dict[str, str]:
    """Snapshot of the full map — useful for debugging."""
    return dict(_load(home))
