"""CL.2/CL.3 — OpenRouter cache affinity + request-shape diagnostics; hashes only, no prompt text or secrets ever persist."""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

try:
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None

_SHAPES_FILE = "prefix_shapes.json"
_MAX_AFFINITIES = 20
# Rolling hash window: bounds shape size AND per-call hashing cost on long transcripts.
_MSG_WINDOW = 64
REASON_NONE = "none"
REASON_FIRST = "first_contact"


def affinity_id(
    profile: str,
    *,
    workgroup_id: str | None = None,
    peer_id: str | None = None,
    schedule_id: str | None = None,
    session_id: str = "",
    purpose: str = "",
) -> str:
    """Hashed so no profile/peer/workgroup identifier reaches a third party; OpenRouter caps session_id at 256 chars."""
    if workgroup_id:
        scope = f"wg:{workgroup_id}"
    elif peer_id:
        scope = f"peer:{peer_id}"
    elif schedule_id:
        scope = f"sched:{schedule_id}"
    else:
        scope = f"session:{session_id}"
    raw = f"{profile}\x00{scope}\x00{purpose}"
    return "alpi-" + hashlib.sha256(raw.encode("utf-8", "replace")).hexdigest()[:32]


def _h(obj) -> str:
    try:
        payload = json.dumps(obj, separators=(",", ":"), default=str)
    except (TypeError, ValueError):
        payload = repr(obj)
    return hashlib.sha256(payload.encode("utf-8", "replace")).hexdigest()[:16]


@dataclass
class RequestShape:
    model: str = ""
    params_hash: str = ""
    tools_hash: str = ""
    system_hash: str = ""
    # Hashes of the LAST _MSG_WINDOW messages after the system slot (covered by system_hash); msg_count is the full post-system length.
    msg_count: int = 0
    msg_hashes: list[str] = field(default_factory=list)


_PARAM_SKIP = frozenset({"api_key", "messages", "tools"})


def capture(call_kwargs: dict, tools: list, messages: list) -> RequestShape:
    params = {
        k: v for k, v in sorted(call_kwargs.items()) if k not in _PARAM_SKIP
    }
    body = messages[1:] if messages else []
    return RequestShape(
        model=str(call_kwargs.get("model", "")),
        params_hash=_h(params),
        tools_hash=_h(tools),
        system_hash=_h(messages[0]) if messages else "",
        msg_count=len(body),
        msg_hashes=[_h(m) for m in body[-_MSG_WINDOW:]],
    )


def _window_start(shape: RequestShape) -> int:
    return shape.msg_count - len(shape.msg_hashes)


def compare(prev: RequestShape | None, cur: RequestShape) -> list[str]:
    """Append-only growth is NOT a rewrite: only a changed slice of the previous message list counts as ``history_rewrite``."""
    if prev is None:
        return [REASON_FIRST]
    reasons: list[str] = []
    if cur.model != prev.model:
        reasons.append("model")
    if cur.params_hash != prev.params_hash:
        reasons.append("params")
    if cur.tools_hash != prev.tools_hash:
        reasons.append("tools")
    if cur.system_hash != prev.system_hash:
        reasons.append("system")
    if cur.msg_count < prev.msg_count:
        reasons.append("history_rewrite")
    else:
        start = max(_window_start(prev), _window_start(cur))
        prev_slice = prev.msg_hashes[start - _window_start(prev):]
        cur_off = start - _window_start(cur)
        cur_slice = cur.msg_hashes[cur_off:cur_off + len(prev_slice)]
        # A jump beyond both windows leaves nothing comparable — best-effort, not a rewrite claim.
        if prev_slice and cur_slice != prev_slice:
            reasons.append("history_rewrite")
    return reasons or [REASON_NONE]


def first_divergence(prev: RequestShape, cur: RequestShape) -> int | None:
    """Absolute message index (system slot = 0) of the first divergent hash inside the comparable window."""
    start = max(_window_start(prev), _window_start(cur))
    prev_slice = prev.msg_hashes[start - _window_start(prev):]
    cur_off = start - _window_start(cur)
    cur_slice = cur.msg_hashes[cur_off:cur_off + len(prev_slice)]
    for i, (a, b) in enumerate(zip(prev_slice, cur_slice)):
        if a != b:
            return start + i + 1
    return None


def _store_path(home: Path) -> Path:
    return home / "logs" / _SHAPES_FILE


def load_shape(home: Path, key: str) -> RequestShape | None:
    try:
        data = json.loads(_store_path(home).read_text(encoding="utf-8"))
        raw = data.get(key)
        if not isinstance(raw, dict):
            return None
        return RequestShape(
            model=str(raw.get("model", "")),
            params_hash=str(raw.get("params_hash", "")),
            tools_hash=str(raw.get("tools_hash", "")),
            system_hash=str(raw.get("system_hash", "")),
            msg_count=int(raw.get("msg_count", 0) or 0),
            msg_hashes=[str(h) for h in (raw.get("msg_hashes") or [])],
        )
    except Exception:  # noqa: BLE001
        return None


@contextlib.contextmanager
def _store_lock(path: Path):
    # Serializes the read-modify-replace across the daemon's concurrent sessions of one profile; flock on separate fds also covers threads.
    if fcntl is None:
        yield
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    f = open(path.parent / (path.name + ".lock"), "w")
    try:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        try:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        finally:
            f.close()


def save_shape(home: Path, key: str, shape: RequestShape) -> None:
    """Best-effort, diagnostics only — a lost write costs one comparison, never a turn."""
    try:
        path = _store_path(home)
        path.parent.mkdir(parents=True, exist_ok=True)
        with _store_lock(path):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    data = {}
            except Exception:  # noqa: BLE001
                data = {}
            # Re-insert so eviction is LRU-by-write, not FIFO-by-first-insertion.
            data.pop(key, None)
            data[key] = asdict(shape)
            while len(data) > _MAX_AFFINITIES:
                data.pop(next(iter(data)))
            fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".shapes.", suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(json.dumps(data, separators=(",", ":")))
                os.replace(tmp_name, path)
            except Exception:
                with contextlib.suppress(OSError):
                    os.unlink(tmp_name)
                raise
    except Exception:  # noqa: BLE001
        pass
