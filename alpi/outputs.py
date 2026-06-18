"""JSONL store at ``<home>/outputs/outputs.jsonl``, capped at MAX_OUTPUTS.

Row schema (one JSON object per line):
    id           12 hex chars
    profile      ``default`` or ``<name>``
    created_at   epoch seconds (float)
    title        optional short headline (omitted when not set)
    body         message body
    type         ``info`` | ``warning`` | ``error``
    status       ``unread`` | ``read``
    session_id   originating chat session, or ``""``
    delivered_to channels the matching notification went out on
"""

from __future__ import annotations

import json
import os
import secrets
import threading
import time
from pathlib import Path
from typing import Any, Iterable

MAX_OUTPUTS = 500

VALID_TYPE = frozenset({"info", "warning", "error"})
VALID_STATUS = frozenset({"unread", "read"})

_lock = threading.Lock()


def _store_path(home: Path) -> Path:
    return home / "outputs" / "outputs.jsonl"


def _new_id() -> str:
    return secrets.token_hex(6)


def _read_all(home: Path) -> list[dict[str, Any]]:
    path = _store_path(home)
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and isinstance(obj.get("id"), str) and obj["id"]:
            out.append(obj)
    return out


def _atomic_rewrite(path: Path, items: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            for it in items:
                f.write(json.dumps(it, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())
    except Exception:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise
    os.replace(str(tmp), str(path))


def append(
    home: Path,
    *,
    profile: str,
    body: str,
    type: str = "info",
    session_id: str = "",
    delivered_to: list[str] | None = None,
    title: str = "",
) -> dict[str, Any]:
    if type not in VALID_TYPE:
        type = "info"

    output = {
        "id": _new_id(),
        "profile": profile or "default",
        "created_at": time.time(),
        "body": body or "",
        "type": type,
        "status": "unread",
        "session_id": session_id or "",
        "delivered_to": list(delivered_to or []),
    }
    if title:
        output["title"] = title

    path = _store_path(home)
    with _lock:
        existing = _read_all(home)
        existing.append(output)
        if len(existing) > MAX_OUTPUTS:
            existing = existing[-MAX_OUTPUTS:]
            _atomic_rewrite(path, existing)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(output, ensure_ascii=False) + "\n")
    return output


def list_outputs(
    home: Path,
    *,
    status: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    items = _read_all(home)
    if status is not None:
        if status not in VALID_STATUS:
            return []
        items = [it for it in items if it.get("status") == status]
    items.sort(key=lambda it: float(it.get("created_at") or 0.0), reverse=True)
    if limit > 0:
        items = items[:limit]
    return items


def read(home: Path, output_id: str) -> dict[str, Any] | None:
    for it in _read_all(home):
        if it.get("id") == output_id:
            return it
    return None


def _mutate(home: Path, output_id: str, mutate) -> dict[str, Any] | None:
    with _lock:
        items = _read_all(home)
        target: dict[str, Any] | None = None
        for it in items:
            if it.get("id") == output_id:
                target = it
                break
        if target is None:
            return None
        mutate(target)
        _atomic_rewrite(_store_path(home), items)
        return target


def mark_read(home: Path, output_id: str) -> dict[str, Any] | None:
    def _apply(it: dict[str, Any]) -> None:
        if it.get("status") == "unread":
            it["status"] = "read"
    return _mutate(home, output_id, _apply)


def delete(home: Path, output_id: str) -> bool:
    """Remove one output by id. Returns True iff a row was actually dropped."""
    with _lock:
        items = _read_all(home)
        kept = [it for it in items if it.get("id") != output_id]
        if len(kept) == len(items):
            return False
        _atomic_rewrite(_store_path(home), kept)
        return True


def mark_all_read(home: Path) -> int:
    with _lock:
        items = _read_all(home)
        touched = 0
        for it in items:
            if it.get("status") == "unread":
                it["status"] = "read"
                touched += 1
        if touched:
            _atomic_rewrite(_store_path(home), items)
        return touched


_CHILD_VALID_CHANNELS = frozenset({
    "alpi", "both", "telegram", "imap", "gmail", "matrix", "webhook",
})
_CHILD_GATEWAYS = frozenset({"telegram", "imap", "gmail", "matrix", "webhook"})


def normalize_send_message_args(args: dict) -> dict | None:
    """Returns None when the call wasn't user-facing (empty text or malformed channel) so callers skip it."""
    text = str(args.get("text") or "").strip()
    if not text:
        return None
    channel = str(args.get("channel") or "alpi").strip().lower()
    if channel not in _CHILD_VALID_CHANNELS:
        return None
    type = str(args.get("type") or "info").strip().lower()
    if type not in VALID_TYPE:
        type = "info"
    notification_title = str(args.get("title") or "").strip()
    gateway = ""
    if channel == "both":
        gateway = str(args.get("platform") or "telegram").strip().lower()
    elif channel != "alpi":
        gateway = channel
    if gateway and gateway not in _CHILD_GATEWAYS:
        gateway = ""
    delivered_to: list[str] = []
    if channel in {"alpi", "both"}:
        delivered_to.append("alpi")
    if gateway:
        delivered_to.append(gateway)
    return {
        "notification_title": notification_title,
        "body": text,
        "type": type,
        "channel": channel,
        "delivered_to": delivered_to,
    }


def record_child_send_message(home: Path, args: dict) -> str:
    """Files the output and emits output.created. Emits agent.message (with output_id + deep_link) only for alpi/both — gateway-only channels already dispatched downstream, no need to wake the native client."""
    record = normalize_send_message_args(args)
    if record is None:
        return ""

    try:
        from alpi.home import profile_name
        from alpi.host import events as host_events
    except Exception:  # noqa: BLE001
        return ""

    profile = profile_name(home)
    body = record["body"]
    notification_title = record["notification_title"] or profile or "alpi"
    type = record["type"]
    channel = record["channel"]
    delivered_to = list(record["delivered_to"])

    try:
        output = append(
            home,
            profile=profile,
            body=body,
            type=type,
            delivered_to=delivered_to,
            title=record["notification_title"],
        )
    except Exception:  # noqa: BLE001
        return ""

    output_id = output["id"]
    try:
        host_events.emit("output.created", {
            "profile": profile,
            "id": output_id,
            "type": type,
        })
    except Exception:  # noqa: BLE001
        pass

    if channel in {"alpi", "both"}:
        payload = {
            "profile": profile,
            "title": notification_title,
            "body": body,
            "type": type,
            "output_id": output_id,
            "deep_link": f"/outputs/{profile}/{output_id}",
        }
        try:
            host_events.emit("agent.message", payload)
        except Exception:  # noqa: BLE001
            pass

    return output_id


def _suppress_native_emit() -> bool:
    return (
        os.environ.get("ALPI_SCHEDULE_CHILD") == "1"
        or os.environ.get("ALPI_PARENT_EMITS_AGENT_MESSAGE") == "1"
    )


def create_output(
    *, text: str, type: str,
    delivered_to: list[str],
    title: str = "",
) -> dict | None:
    # Persistence is opportunistic — failures never block delivery.
    try:
        from alpi.home import get_active_session, get_home, profile_name
    except Exception:  # noqa: BLE001
        return None
    try:
        home = get_home()
        prof = profile_name(home)
    except Exception:  # noqa: BLE001
        return None
    try:
        session_id = get_active_session() or ""
    except Exception:  # noqa: BLE001
        session_id = ""
    try:
        return append(
            home, profile=prof,
            body=text, type=type, session_id=session_id,
            delivered_to=delivered_to, title=title,
        )
    except Exception:  # noqa: BLE001
        return None


def create_output_and_emit_message(
    *, text: str, title: str, type: str,
    delivered_to: list[str],
) -> str:
    """Callers must guard with _suppress_native_emit() — schedule/gateway children defer to the parent."""
    output = create_output(
        text=text, type=type,
        delivered_to=delivered_to, title=title,
    )
    if output is None:
        return ""
    payload: dict = {
        "profile": output["profile"],
        "title": title or output["profile"] or "alpi",
        "body": output["body"],
        "type": output["type"],
        "output_id": output["id"],
        "deep_link": f"/outputs/{output['profile']}/{output['id']}",
    }
    if output.get("session_id"):
        payload["session_id"] = output["session_id"]
    try:
        from alpi.host import events as host_events
        host_events.emit("agent.message", payload)
        host_events.emit("output.created", {
            "profile": output["profile"],
            "id": output["id"],
            "type": output["type"],
        })
    except Exception:  # noqa: BLE001
        pass
    return output["id"]


__all__ = [
    "MAX_OUTPUTS",
    "VALID_TYPE",
    "VALID_STATUS",
    "append",
    "list_outputs",
    "read",
    "mark_read",
    "mark_all_read",
    "delete",
    "normalize_send_message_args",
    "record_child_send_message",
    "create_output",
    "create_output_and_emit_message",
]
