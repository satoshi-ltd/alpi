"""Reclaimable-storage categories shared by `alpi setup → Cleanup` and host.cleanup.*."""

from __future__ import annotations

import re
import shutil
import time
from pathlib import Path
from typing import Any

# "old transcripts" contract: the sessions category only ever touches sessions past this age.
SESSIONS_KEEP_DAYS = 30

# chat-delivered artifacts in out/ stay downloadable this long before cleanup offers them.
GENERATED_KEEP_DAYS = 30


_CLEANUP_CLAIM = object()


def _busy_session_ids(h: Path) -> set[str] | None:
    """Snapshot under _active_lock. None = state unknown — destructive callers must fail closed."""
    try:
        from alpi.home import profile_name
        from alpi.host import chat as host_chat
        prof = profile_name(h)
        with host_chat._active_lock:
            return {sid for (p, sid) in host_chat._session_active if p == prof}
    except Exception:  # noqa: BLE001
        return None


def _old_sessions(h: Path) -> tuple[list[str] | None, int]:
    """``(None, 0)`` propagates unknown busy state so ``apply`` can refuse instead of no-op succeeding."""
    from alpi.host import sessions as host_sessions

    cutoff = time.time() - SESSIONS_KEEP_DAYS * 86_400
    busy = _busy_session_ids(h)
    if busy is None:
        return None, 0
    ids: list[str] = []
    total = 0
    for row in host_sessions.list_sessions(h, limit=None):
        if float(row.get("updated_at") or 0.0) >= cutoff:
            continue
        sid = str(row.get("id"))
        if not sid or sid in busy:
            continue
        for p in host_sessions.session_paths(h, sid):
            try:
                total += p.stat().st_size
            except OSError:
                pass
        ids.append(sid)
    return ids, total


def categories(h: Path) -> list[dict[str, Any]]:
    def _dir(name: str) -> Path:
        return h / name

    def _sum(files: list[Path]) -> int:
        total = 0
        for p in files:
            try:
                total += p.stat().st_size
            except OSError:
                pass
        return total

    def _all(d: Path) -> list[Path]:
        if not d.exists():
            return []
        return [p for p in d.iterdir() if p.is_file()]

    from alpi.core import store as store_mod

    def _dir_size(d: Path) -> int:
        total = 0
        if d.exists():
            for p in d.rglob("*"):
                if p.is_file():
                    try:
                        total += p.stat().st_size
                    except OSError:
                        pass
        return total

    tts_files = _all(_dir("cache/tts"))
    inbound_files = _all(_dir("cache/inbound"))
    old_session_ids, old_sessions_size = _old_sessions(h)
    mention_files = _all(_dir("mentions"))
    logs_root = _dir("logs")
    log_files: list[Path] = (
        [
            p for p in logs_root.iterdir()
            if p.is_file() and re.fullmatch(r".+\.log(?:\.\d+)?", p.name)
        ]
        if logs_root.exists() else []
    )
    sched_files = _all(_dir("schedule/output"))
    wg_root = _dir("alp/workgroups")
    wg_files: list[Path] = (
        [p for p in wg_root.rglob("*") if p.is_file()] if wg_root.exists() else []
    )
    turns_path = _dir("alp/turns.jsonl")
    if turns_path.is_file():
        wg_files.append(turns_path)
    curator_root = _dir("logs/curator")
    curator_dirs: list[Path] = (
        [p for p in curator_root.iterdir() if p.is_dir()]
        if curator_root.exists() else []
    )
    curator_size = sum(_dir_size(d) for d in curator_dirs)
    knowledge_reclaimable = store_mod.reclaimable_bytes(h)
    knowledge_files: list[Path] = (
        [store_mod.store_path(h)] if knowledge_reclaimable > 0 else []
    )
    from alpi.home import out_root as _safe_out_root
    gen_root = _safe_out_root(h)
    gen_cutoff = time.time() - GENERATED_KEEP_DAYS * 86_400
    gen_files: list[Path] = []
    if gen_root is not None:
        import os as _os
        for parent, _dirs, files in _os.walk(gen_root, followlinks=False):
            for fn in files:
                p = Path(parent) / fn
                try:
                    if not p.is_symlink() and p.stat().st_mtime < gen_cutoff:
                        gen_files.append(p)
                except OSError:
                    pass
    att_root = _dir("host/attachments/tmp")
    att_dirs: list[Path] = (
        [p for p in att_root.iterdir() if p.is_dir()] if att_root.exists() else []
    )
    att_size = sum(_dir_size(d) for d in att_dirs)

    return [
        {
            "key": "tts",
            "label": "TTS cache",
            "desc": "synthesized speech MP3s in `cache/tts/`",
            "files": tts_files,
            "size": _sum(tts_files),
        },
        {
            "key": "inbound_media",
            "label": "Inbound media cache",
            "desc": "downloaded voice notes / attachments in `cache/inbound/`",
            "files": inbound_files,
            "size": _sum(inbound_files),
        },
        {
            "key": "sessions",
            "label": "Old sessions",
            "desc": f"chat transcripts older than {SESSIONS_KEEP_DAYS} days in `sessions/`",
            "files": [],
            "session_ids": old_session_ids,
            "size": old_sessions_size,
            "destructive": True,
        },
        {
            "key": "mentions",
            "label": "Mentions",
            "desc": "per-sender @-mention threads in `mentions/`",
            "files": mention_files,
            "size": _sum(mention_files),
            "destructive": True,
        },
        {
            "key": "logs",
            "label": "Subsystem logs",
            "desc": "`logs/*.log` — per-profile agent.log + approval.log (daemon-wide service.log lives at the alpi root)",
            "files": log_files,
            "size": _sum(log_files),
        },
        {
            "key": "schedule",
            "label": "Schedule output",
            "desc": "stdout/stderr of past scheduled jobs",
            "files": sched_files,
            "size": _sum(sched_files),
        },
        {
            "key": "workgroups",
            "label": "Workgroups",
            "desc": "ALL workgroup transcripts + turn telemetry under `alp/`",
            "files": wg_files,
            "size": _sum(wg_files),
            "destructive": True,
        },
        {
            "key": "curator",
            "label": "Curator reports",
            "desc": "past skill curator reviews under `logs/curator/<timestamp>/`",
            "files": curator_dirs,
            "size": curator_size,
            "action": "rmtree",
        },
        {
            "key": "generated",
            "label": "Generated files",
            "desc": f"chat-delivered images/documents older than {GENERATED_KEEP_DAYS} days in `out/`",
            "files": gen_files,
            "size": _sum(gen_files),
            "destructive": True,
        },
        {
            "key": "attachments",
            "label": "Attachment staging",
            "desc": "uploaded chat attachments staged in `host/attachments/tmp/`",
            "files": att_dirs,
            "size": att_size,
            "action": "rmtree",
        },
        {
            "key": "knowledge",
            "label": "Knowledge index bloat",
            "desc": "SQLite freelist pages in `knowledge.sqlite` from past force-reindexes",
            "files": knowledge_files,
            "size": knowledge_reclaimable,
            "action": "vacuum",
        },
    ]


def item_count(cat: dict[str, Any]) -> int:
    """Count for either category shape: id-based (sessions) or file-based."""
    if "session_ids" in cat:
        return len(cat["session_ids"] or [])
    return len(cat["files"])


def plan(h: Path) -> list[dict[str, Any]]:
    """Wire-safe view of ``categories`` (no Path objects)."""
    return [
        {
            "key": c["key"],
            "label": c["label"],
            "desc": c["desc"],
            "size": int(c["size"]),
            "count": item_count(c),
            "action": c.get("action", "unlink"),
            "destructive": bool(c.get("destructive", False)),
        }
        for c in categories(h)
    ]


def apply(h: Path, key: str) -> dict[str, Any]:
    """Reclaim one category. Returns ``{key, ok, removed, freed_bytes, errors}``."""
    target = next((c for c in categories(h) if c["key"] == key), None)
    if target is None:
        return {"key": key, "ok": False, "removed": 0, "freed_bytes": 0,
                "errors": [f"unknown category: {key}"]}
    if "session_ids" in target:
        return _apply_sessions(h, target)
    if not target["files"]:
        return {"key": key, "ok": True, "removed": 0, "freed_bytes": 0, "errors": []}

    errors: list[str] = []
    if target.get("action") == "vacuum":
        from alpi.core import store as store_mod
        before, after = store_mod.compact(h)
        return {
            "key": key, "ok": True, "removed": 1,
            "freed_bytes": max(0, before - after), "errors": [],
            "before": before, "after": after,
        }

    def _item_size(p: Path) -> int:
        try:
            if p.is_dir():
                return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
            return p.stat().st_size
        except OSError:
            return 0

    removed = 0
    freed = 0
    for p in target["files"]:
        size = _item_size(p)
        try:
            if target.get("action") == "rmtree":
                shutil.rmtree(p)
            else:
                p.unlink()
            removed += 1
            freed += size
        except OSError as e:
            errors.append(f"{p.name}: {e}")
    return {
        "key": key, "ok": not errors, "removed": removed,
        "freed_bytes": freed, "errors": errors,
    }


def _apply_sessions(h: Path, target: dict[str, Any]) -> dict[str, Any]:
    from alpi.host import sessions as host_sessions

    ids = target["session_ids"]
    if ids is None:
        return {"key": target["key"], "ok": False, "removed": 0, "freed_bytes": 0,
                "errors": ["cannot verify busy sessions; aborting"]}
    if not ids:
        return {"key": target["key"], "ok": True, "removed": 0,
                "freed_bytes": 0, "errors": []}
    try:
        from alpi.home import profile_name
        from alpi.host import chat as host_chat
        prof = profile_name(h)
    except Exception as e:  # noqa: BLE001
        return {"key": target["key"], "ok": False, "removed": 0, "freed_bytes": 0,
                "errors": [f"cannot verify busy sessions ({e}); aborting"]}

    removed = 0
    freed = 0
    errors: list[str] = []
    for sid in ids:
        key = host_chat.session_key(prof, sid)
        # Claim the slot so a turn starting mid-delete gets the same "busy" answer host.chat gives.
        with host_chat._active_lock:
            if key in host_chat._session_active:
                errors.append(f"{sid}: session-busy")
                continue
            host_chat._session_active[key] = _CLEANUP_CLAIM
        try:
            size = 0
            for p in host_sessions.session_paths(h, sid):
                try:
                    size += p.stat().st_size
                except OSError:
                    pass
            if host_sessions.delete_session(h, sid):
                removed += 1
                freed += size
            else:
                errors.append(f"{sid}: delete failed")
        finally:
            with host_chat._active_lock:
                if host_chat._session_active.get(key) is _CLEANUP_CLAIM:
                    del host_chat._session_active[key]
    return {
        "key": target["key"], "ok": not errors, "removed": removed,
        "freed_bytes": freed, "errors": errors,
    }
