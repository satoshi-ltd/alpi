from __future__ import annotations

import os
import re
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Any

from alpi.host import sessions as host_sessions

_PATH = re.compile(r"/[^\s\"'<>()\[\]{}`|,;*?\\]+")
_MAX_ENTRIES = 4096

_cache: OrderedDict[str, tuple[tuple, frozenset[str]]] = OrderedDict()
_lock = threading.Lock()


def _clear() -> None:
    with _lock:
        _cache.clear()


def _tokens(text: Any) -> set[str]:
    if not isinstance(text, str):
        return set()
    return {os.path.normpath(match.rstrip(".:!?")) for match in _PATH.findall(text)}


def _strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


def collect(payload: dict[str, Any]) -> frozenset[str]:
    structured: set[str] = set()
    mentioned: set[str] = set()
    typed: set[str] = set()
    for turn in payload.get("turns") or []:
        if not isinstance(turn, dict):
            continue
        for key in ("attachments", "output_attachments"):
            for item in turn.get(key) or []:
                if isinstance(item, dict) and isinstance(item.get("path"), str) and item["path"]:
                    structured.add(os.path.normpath(item["path"]))
        typed |= _tokens(turn.get("user"))
        mentioned |= _tokens(turn.get("assistant"))
        for tool in turn.get("tools") or []:
            if isinstance(tool, dict):
                mentioned |= _tokens(tool.get("result"))
                for text in _strings(tool.get("args")):
                    mentioned |= _tokens(text)
    return frozenset(structured | (mentioned - typed))


def for_session(home: Path, row: dict[str, Any]) -> frozenset[str]:
    key = f"{home}|{row.get('id')}"
    stamp = (row.get("mtime"), row.get("size_bytes"))
    with _lock:
        hit = _cache.get(key)
        if hit is not None and hit[0] == stamp and None not in stamp:
            _cache.move_to_end(key)
            return hit[1]
    try:
        offered = collect(host_sessions.read_session(home, str(row.get("id"))))
    except Exception:  # noqa: BLE001
        return frozenset()
    with _lock:
        _cache[key] = (stamp, offered)
        while len(_cache) > _MAX_ENTRIES:
            _cache.popitem(last=False)
    return offered
