from __future__ import annotations

import json
from pathlib import Path
from typing import Any


_FIRST_USER_MAX = 140


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
    rows: list[dict[str, Any]] = []
    for p in d.iterdir():
        if not p.is_file() or p.suffix != ".json":
            continue
        if p.stem.startswith("_"):
            continue
        try:
            st = p.stat()
            mtime = int(st.st_mtime)
            size_bytes = int(st.st_size)
        except OSError:
            mtime = 0
            size_bytes = 0
        # The per-turn replay sidecar is freed alongside the session on delete, so its bytes count toward the row's reported size.
        sidecar = d / f"_events_{p.stem}.jsonl"
        try:
            size_bytes += int(sidecar.stat().st_size)
        except OSError:
            pass
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            data = {}
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
        rows.append({
            "id": p.stem,
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
        })
    rows.sort(key=lambda r: r["updated_at"], reverse=True)
    if limit is not None and limit > 0:
        rows = rows[:limit]
    return rows


def read_session(home: Path, session_id: str) -> dict[str, Any]:
    p = home / "sessions" / f"{session_id}.json"
    if not p.exists():
        raise FileNotFoundError(f"no session {session_id!r}")
    return json.loads(p.read_text(encoding="utf-8"))


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
    if s.startswith("[INBOUND TELEGRAM"):
        return "telegram"
    if s.startswith("[INBOUND IMAP") or s.startswith("[INBOUND GMAIL"):
        return "email"
    if s.startswith("[INBOUND "):
        return "gateway"
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
