from __future__ import annotations

import json
import os
import re
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Any, NamedTuple


_FIRST_USER_MAX = 140
_LARGE_SESSION_BYTES = 2 * 1024 * 1024
_HEAD_READ_BYTES = 512 * 1024
_STRING_FIELD_RE = re.compile(r'"(?P<key>model|user)"\s*:\s*(?P<value>"(?:\\.|[^"\\])*")')
_NUMBER_FIELD_RE = re.compile(
    r'"(?P<key>started_at|input_tokens|output_tokens|cost_usd|last_ctx_tokens)"\s*:\s*(?P<value>-?\d+(?:\.\d+)?)',
)


def _as_ts(v: Any) -> float:
    """Coerce a session timestamp to float, tolerating garbage.

    Old/corrupt session JSONs occasionally land on disk with non-numeric
    ``started_at`` (a stray string, ``None``, the literal "bad"). One bad
    file would otherwise nuke the whole ``host.sessions.list`` response —
    so we treat anything non-coercible as 0.0 and fall back to file mtime.
    """
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(v) if v else 0.0
    except (TypeError, ValueError):
        return 0.0


def list_sessions(home: Path, limit: int | None = None) -> list[dict[str, Any]]:
    d = home / "sessions"
    if not d.exists():
        return []
    files = _session_files(d)
    disk = _DiskIndex(d)
    # mtime is unreliable post-checkout/rsync; derive updated_at from content (max turn.at vs started_at).
    rows = [_session_row(p, disk=disk) for p in files]
    disk.flush({p.name for p in files})
    rows.sort(key=lambda r: r["updated_at"], reverse=True)
    if limit is not None and limit > 0:
        rows = rows[:limit]
    return rows


def count_sessions(home: Path) -> int:
    d = home / "sessions"
    if not d.exists():
        return 0
    return sum(1 for _ in _session_files(d))


def latest_chat_summary(home: Path) -> dict[str, Any] | None:
    d = home / "sessions"
    if not d.exists():
        return None
    files = _session_files(d)
    disk = _DiskIndex(d)
    best: dict[str, Any] | None = None
    for p in files:
        row = _session_row(p, large_default_kind="chat", disk=disk)
        if row.get("kind") != "chat":
            continue
        if best is None or float(row.get("updated_at") or 0) > float(best.get("updated_at") or 0):
            best = row
    disk.flush({p.name for p in files})
    return best


def _session_files(d: Path) -> list[Path]:
    out = []
    for p in d.iterdir():
        if not p.is_file() or p.suffix != ".json":
            continue
        if p.name.startswith(".") or p.stem.startswith("_"):
            continue
        out.append(p)
    return out


class _Stats(NamedTuple):
    mtime: int
    sidecar_mtime: int
    size_bytes: int
    main_size: int
    sig: tuple[int, int, int, int] | None


_ROW_CACHE_MAX = 8192
_row_cache: OrderedDict[str, tuple[tuple[int, int, int, int], dict[str, Any]]] = OrderedDict()
_row_cache_lock = threading.Lock()

_INDEX_VERSION = 1


def _clear_row_cache() -> None:
    with _row_cache_lock:
        _row_cache.clear()


class _DiskIndex:
    def __init__(self, d: Path):
        self._path = d / "_index.json"
        self._rows: dict[str, list[Any]] | None = None
        self._dirty = False

    def _load(self) -> dict[str, list[Any]]:
        if self._rows is None:
            try:
                raw = json.loads(self._path.read_text(encoding="utf-8"))
                rows = raw.get("rows") if raw.get("v") == _INDEX_VERSION else None
                self._rows = dict(rows) if isinstance(rows, dict) else {}
            except Exception:  # noqa: BLE001
                self._rows = {}
        return self._rows

    def lookup(self, name: str, sig: tuple[int, int, int, int]) -> dict[str, Any] | None:
        hit = self._load().get(name)
        if (
            isinstance(hit, list)
            and len(hit) == 2
            and isinstance(hit[0], list)
            and tuple(hit[0]) == sig
            and isinstance(hit[1], dict)
        ):
            return dict(hit[1])
        return None

    def store(self, name: str, sig: tuple[int, int, int, int], row: dict[str, Any]) -> None:
        self._load()[name] = [list(sig), dict(row)]
        self._dirty = True

    def flush(self, names: set[str]) -> None:
        if self._rows is None:
            return
        stale = set(self._rows) - names
        for n in stale:
            self._rows.pop(n, None)
        if stale:
            self._dirty = True
        if not self._dirty:
            return
        tmp = self._path.with_name(f".index-{os.getpid()}-{threading.get_ident()}.tmp")
        try:
            tmp.write_text(
                json.dumps({"v": _INDEX_VERSION, "rows": self._rows}),
                encoding="utf-8",
            )
            tmp.replace(self._path)
        except OSError:
            try:
                tmp.unlink()
            except OSError:
                pass
        self._dirty = False


def _session_row(
    p: Path,
    *,
    large_default_kind: str | None = None,
    disk: "_DiskIndex | None" = None,
) -> dict[str, Any]:
    stats = _session_stats(p)
    row = _cached_row(p, stats, disk=disk)
    if large_default_kind and stats.main_size > _LARGE_SESSION_BYTES and row.get("kind") == "empty":
        row["kind"] = large_default_kind
    return row


def _cached_row(p: Path, stats: _Stats, disk: "_DiskIndex | None" = None) -> dict[str, Any]:
    key = str(p)
    if stats.sig is not None:
        with _row_cache_lock:
            hit = _row_cache.get(key)
            if hit is not None and hit[0] == stats.sig:
                _row_cache.move_to_end(key)
                return dict(hit[1])
        if disk is not None:
            row = disk.lookup(p.name, stats.sig)
            if row is not None:
                with _row_cache_lock:
                    _row_cache[key] = (stats.sig, dict(row))
                    _row_cache.move_to_end(key)
                    while len(_row_cache) > _ROW_CACHE_MAX:
                        _row_cache.popitem(last=False)
                return row
    row = _compute_row(p, stats)
    if stats.sig is not None:
        with _row_cache_lock:
            _row_cache[key] = (stats.sig, dict(row))
            _row_cache.move_to_end(key)
            while len(_row_cache) > _ROW_CACHE_MAX:
                _row_cache.popitem(last=False)
        if disk is not None:
            disk.store(p.name, stats.sig, row)
    return row


def _compute_row(p: Path, stats: _Stats) -> dict[str, Any]:
    if stats.main_size > _LARGE_SESSION_BYTES:
        return _large_session_row(
            p,
            mtime=stats.mtime,
            sidecar_mtime=stats.sidecar_mtime,
            size_bytes=stats.size_bytes,
        )
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        data = {}
    return _row_from_data(p.stem, data, mtime=stats.mtime, size_bytes=stats.size_bytes)


def _session_stats(p: Path) -> _Stats:
    try:
        st = p.stat()
        mtime = int(st.st_mtime)
        main_size = int(st.st_size)
        main_ns = int(st.st_mtime_ns)
        statable = True
    except OSError:
        mtime = 0
        main_size = 0
        main_ns = 0
        statable = False
    sidecar_mtime = 0
    sidecar_ns = 0
    sidecar_size = 0
    sidecar = p.parent / f"_events_{p.stem}.jsonl"
    try:
        st = sidecar.stat()
        sidecar_mtime = int(st.st_mtime)
        sidecar_ns = int(st.st_mtime_ns)
        sidecar_size = int(st.st_size)
    except OSError:
        pass
    sig = (main_ns, main_size, sidecar_ns, sidecar_size) if statable else None
    return _Stats(mtime, sidecar_mtime, main_size + sidecar_size, main_size, sig)


def _row_from_data(sid: str, data: dict[str, Any], *, mtime: int, size_bytes: int) -> dict[str, Any]:
    turns = data.get("turns") or []
    first_user = ""
    if turns:
        first_user = _truncate(str(turns[0].get("user") or ""), _FIRST_USER_MAX)
    last_user = ""
    last_assistant = ""
    if turns:
        tail = turns[-1] if isinstance(turns[-1], dict) else {}
        last_user = _truncate(str(tail.get("user") or ""), _FIRST_USER_MAX)
        last_assistant = _truncate(str(tail.get("assistant") or ""), _FIRST_USER_MAX)
    started_at = data.get("started_at")
    last_turn_at = 0.0
    if turns:
        for t in reversed(turns):
            v = t.get("at") if isinstance(t, dict) else None
            if isinstance(v, (int, float)) and v > last_turn_at:
                last_turn_at = float(v)
                break
    updated_at = max(_as_ts(last_turn_at), _as_ts(started_at))
    if updated_at <= 0.0:
        updated_at = float(mtime)
    return {
        "id": sid,
        "mtime": mtime,
        "started_at": started_at,
        "updated_at": updated_at,
        "size_bytes": size_bytes,
        "first_user": first_user,
        "last_user": last_user,
        "last_assistant": last_assistant,
        "model": data.get("model"),
        "turn_count": len(turns),
        "kind": classify_first_user(first_user),
        "input_tokens": int(data.get("input_tokens") or 0),
        "output_tokens": int(data.get("output_tokens") or 0),
        "cost_usd": float(data.get("cost_usd") or 0.0),
        "last_ctx_tokens": int(data.get("last_ctx_tokens") or 0),
    }


def _large_session_row(
    p: Path,
    *,
    mtime: int,
    sidecar_mtime: int,
    size_bytes: int,
) -> dict[str, Any]:
    fields = _large_session_head_fields(p)
    first_user = _truncate(str(fields.get("user") or ""), _FIRST_USER_MAX)
    started_at = fields.get("started_at")
    updated_at = max(_as_ts(started_at), float(mtime), float(sidecar_mtime))
    kind = classify_first_user(first_user)
    return {
        "id": p.stem,
        "mtime": mtime,
        "started_at": started_at,
        "updated_at": updated_at,
        "size_bytes": size_bytes,
        "first_user": first_user,
        "last_user": "",
        "last_assistant": "",
        "model": fields.get("model"),
        "turn_count": 0,
        "kind": kind,
        "input_tokens": int(fields.get("input_tokens") or 0),
        "output_tokens": int(fields.get("output_tokens") or 0),
        "cost_usd": float(fields.get("cost_usd") or 0.0),
        "last_ctx_tokens": int(fields.get("last_ctx_tokens") or 0),
    }


def _large_session_head_fields(p: Path) -> dict[str, Any]:
    try:
        with p.open("rb") as fh:
            text = fh.read(_HEAD_READ_BYTES).decode("utf-8", errors="replace")
    except OSError:
        return {}
    out: dict[str, Any] = {}
    for m in _STRING_FIELD_RE.finditer(text):
        key = m.group("key")
        if key in out:
            continue
        try:
            out[key] = json.loads(m.group("value"))
        except json.JSONDecodeError:
            pass
    for m in _NUMBER_FIELD_RE.finditer(text):
        key = m.group("key")
        if key in out:
            continue
        raw = m.group("value")
        out[key] = float(raw) if "." in raw else int(raw)
    return out


_PAYLOAD_CACHE_MAX = 8
_payload_cache: OrderedDict[str, tuple[tuple[int, int], dict[str, Any]]] = OrderedDict()
_payload_cache_lock = threading.Lock()


def _clear_payload_cache() -> None:
    with _payload_cache_lock:
        _payload_cache.clear()


def _payload_sig(p: Path) -> tuple[int, int] | None:
    try:
        st = p.stat()
        return (int(st.st_mtime_ns), int(st.st_size))
    except OSError:
        return None


def _copy_jsonish(v: Any) -> Any:
    if isinstance(v, dict):
        return {k: _copy_jsonish(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_copy_jsonish(x) for x in v]
    return v


def _cached_payload(home: Path, session_id: str) -> dict[str, Any]:
    # returns the SHARED cached object — callers must deep-copy anything they hand out or mutate
    p = home / "sessions" / f"{session_id}.json"
    if not p.exists():
        raise FileNotFoundError(f"no session {session_id!r}")
    key = str(p)
    sig = _payload_sig(p)
    if sig is not None:
        with _payload_cache_lock:
            hit = _payload_cache.get(key)
            if hit is not None and hit[0] == sig:
                _payload_cache.move_to_end(key)
                return hit[1]
    from alpi.session import normalize_payload
    data = normalize_payload(json.loads(p.read_text(encoding="utf-8")))
    # cache only when the file did not change under the read
    if sig is not None and _payload_sig(p) == sig:
        with _payload_cache_lock:
            _payload_cache[key] = (sig, data)
            _payload_cache.move_to_end(key)
            while len(_payload_cache) > _PAYLOAD_CACHE_MAX:
                _payload_cache.popitem(last=False)
    return data


def read_session(home: Path, session_id: str) -> dict[str, Any]:
    return _copy_jsonish(_cached_payload(home, session_id))


def read_session_slice(
    home: Path,
    session_id: str,
    *,
    after_turn: int | None = None,
    tail_turns: int | None = None,
    before_turn: int | None = None,
    max_turns: int | None = None,
) -> tuple[dict[str, Any], int, int, str]:
    data = _cached_payload(home, session_id)
    turns = data.get("turns") or []
    total = len(turns)
    offset = 0
    end = total
    if after_turn is not None:
        offset = min(after_turn, total)
    elif tail_turns is not None and tail_turns > 0:
        offset = max(0, total - tail_turns)
    elif before_turn is not None:
        end = min(before_turn, total)
        if max_turns is not None and max_turns > 0:
            offset = max(0, end - max_turns)
    first_user = str(turns[0].get("user") or "") if turns and isinstance(turns[0], dict) else ""
    out = {k: _copy_jsonish(v) for k, v in data.items() if k != "turns"}
    out["turns"] = [_copy_jsonish(t) for t in turns[offset:end]]
    return out, total, offset, first_user


def session_paths(home: Path, session_id: str) -> tuple[Path, Path]:
    d = home / "sessions"
    return d / f"{session_id}.json", d / f"_events_{session_id}.jsonl"


def delete_session(home: Path, session_id: str) -> bool:
    """Remove ``<id>.json`` + ``_events_<id>.jsonl``. Returns True iff the session file existed."""
    main, sidecar = session_paths(home, session_id)
    existed = main.exists()
    try:
        main.unlink()
    except FileNotFoundError:
        pass
    except OSError:
        return False
    try:
        sidecar.unlink()
    except FileNotFoundError:
        pass
    except OSError:
        pass
    try:
        from alpi.tools.recall import forget_session
        forget_session(home, session_id)
    except Exception:  # noqa: BLE001
        pass
    return existed


def classify_first_user(first_user: str) -> str:
    s = first_user.lstrip()
    if s.startswith("[workgroup-poller]") or s.startswith("[workgroup "):
        return "workgroup"
    if s.startswith("[SCHEDULED:") or s.startswith("[CRON"):
        return "scheduled"
    if s.startswith("[INBOUND IMAP") or s.startswith("[INBOUND GMAIL"):
        return "email"
    if s.startswith("["):
        return "system"
    if not s:
        return "empty"
    return "chat"


def _truncate(s: str, max_chars: int) -> str:
    out: list[str] = []
    for i, ch in enumerate(s):
        if i >= max_chars:
            out.append("…")
            break
        out.append(" " if ch in ("\n", "\r") else ch)
    return "".join(out).strip()
