from __future__ import annotations

import json
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
    # mtime is unreliable post-checkout/rsync; derive updated_at from content (max turn.at vs started_at).
    rows = [_session_row(p) for p in _session_files(d)]
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
    best: dict[str, Any] | None = None
    for p in _session_files(d):
        row = _session_row(p, large_default_kind="chat")
        if row.get("kind") != "chat":
            continue
        if best is None or float(row.get("updated_at") or 0) > float(best.get("updated_at") or 0):
            best = row
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


def _clear_row_cache() -> None:
    with _row_cache_lock:
        _row_cache.clear()


def _session_row(p: Path, *, large_default_kind: str | None = None) -> dict[str, Any]:
    stats = _session_stats(p)
    row = _cached_row(p, stats)
    if large_default_kind and stats.main_size > _LARGE_SESSION_BYTES and row.get("kind") == "empty":
        row["kind"] = large_default_kind
    return row


def _cached_row(p: Path, stats: _Stats) -> dict[str, Any]:
    key = str(p)
    if stats.sig is not None:
        with _row_cache_lock:
            hit = _row_cache.get(key)
            if hit is not None and hit[0] == stats.sig:
                _row_cache.move_to_end(key)
                return dict(hit[1])
    row = _compute_row(p, stats)
    if stats.sig is not None:
        with _row_cache_lock:
            _row_cache[key] = (stats.sig, dict(row))
            _row_cache.move_to_end(key)
            while len(_row_cache) > _ROW_CACHE_MAX:
                _row_cache.popitem(last=False)
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
        "kind": _classify(first_user),
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
    kind = _classify(first_user)
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


def read_session(home: Path, session_id: str) -> dict[str, Any]:
    p = home / "sessions" / f"{session_id}.json"
    if not p.exists():
        raise FileNotFoundError(f"no session {session_id!r}")
    from alpi.session import normalize_payload
    return normalize_payload(json.loads(p.read_text(encoding="utf-8")))


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


def _classify(first_user: str) -> str:
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
