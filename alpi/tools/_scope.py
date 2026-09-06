from __future__ import annotations

import fnmatch
import json
import os
from pathlib import Path


class ScopeUnverifiable(RuntimeError):
    """A bounded scope is declared but cannot be measured; the handoff guard must fail closed."""


def _scope() -> tuple[Path, tuple[str, ...]] | None:
    from alpi.tools import _paths

    raw = os.environ.get("ALPI_WORKGROUP_WRITE_SCOPE")
    if raw is None:
        return None
    try:
        scope = json.loads(raw) or {}
        patterns = tuple(str(item) for item in scope.get("paths") or ())
    except (AttributeError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ScopeUnverifiable(f"invalid write scope: {exc}") from exc
    if not patterns:
        return None
    try:
        if _paths._configured_workspace() is None:
            raise ScopeUnverifiable("no workspace is configured for this profile")
        workspace = _paths._workspace_root().resolve()
        root = (workspace / str(scope.get("root") or "")).resolve()
        root.relative_to(workspace)
    except ScopeUnverifiable:
        raise
    except (TypeError, ValueError) as exc:
        raise ScopeUnverifiable(f"write scope root is not inside the workspace: {exc}") from exc
    return root, patterns


def _baseline_dir() -> Path | None:
    home = os.environ.get("ALPI_HOME")
    if not home:
        from alpi.home import get_home

        home = str(get_home())
    return Path(home) / "alp" / "scope_baselines"


def _baseline_path() -> Path | None:
    # Only a member turn owns artifacts; hub-owned phases and plain chats keep no baseline.
    wg_id = os.environ.get("ALPI_WORKGROUP_DISPATCH", "").strip()
    if not wg_id or os.environ.get("ALPI_WORKGROUP_MEMBER_TURN") != "1":
        return None
    round_seq = os.environ.get("ALPI_WORKGROUP_ROUND_HUB_SEQ", "").strip() or "0"
    return _baseline_dir() / f"{wg_id}-{round_seq}.json"


def _identity(root: Path, patterns: tuple[str, ...]) -> dict:
    return {"root": str(root), "patterns": list(patterns)}


def _prune_baselines(path: Path) -> None:
    # One live round per workgroup: earlier rounds of the same workgroup and anything older than a week are stale state.
    import time

    wg_id = path.name.rsplit("-", 1)[0]
    cutoff = time.time() - 7 * 24 * 3600
    for other in path.parent.glob("*.json"):
        if other == path:
            continue
        try:
            if other.name.startswith(f"{wg_id}-") or other.stat().st_mtime < cutoff:
                other.unlink()
        except OSError:
            continue


def _write_atomic(path: Path, payload: dict) -> None:
    import tempfile

    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".baseline-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, sort_keys=True)
        os.replace(tmp, path)
    except OSError:
        Path(tmp).unlink(missing_ok=True)
        raise


def load_or_create_baseline() -> dict[str, str] | None:
    # The baseline lives for the whole round: a turn resumed after `#working (continuation)` compares against the artifacts as they were when the round opened, not against its own finished work. It is bound to the resolved root and patterns, so a scope that moved is measured afresh.
    resolved = _scope()
    if resolved is None:
        return None
    root, patterns = resolved
    path = _baseline_path()
    if path is not None and path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = None
        if (
            isinstance(data, dict) and isinstance(data.get("files"), dict)
            and data.get("scope") == _identity(root, patterns)
        ):
            return {str(k): str(v) for k, v in data["files"].items()}
    current = snapshot()
    if current is not None and path is not None:
        try:
            _write_atomic(path, {"scope": _identity(root, patterns), "files": current})
            _prune_baselines(path)
        except OSError as exc:
            raise ScopeUnverifiable(f"cannot persist the scope baseline: {exc}") from exc
    return current


def clear_baseline() -> None:
    path = _baseline_path()
    if path is not None:
        path.unlink(missing_ok=True)


def _excluded_roots() -> list[Path]:
    # The guard's own state and the profile home are never deliverables, even when the scope is `**` and the home lives under the workspace.
    out: list[Path] = []
    base = _baseline_dir()
    if base is not None:
        out.append(base.resolve())
    home = os.environ.get("ALPI_HOME")
    if home:
        out.append(Path(home).resolve())
    return out


_WALK_EXCLUDE = {".git", "node_modules", "__pycache__", ".venv", ".cache"}


def _walk_roots(root: Path, patterns: tuple[str, ...]) -> list[Path]:
    # Build phases own generated trees such as dist/** and public/img/**, so only vendor and VCS directories are skipped and each `dir/**` walks its own subtree.
    roots: list[Path] = []
    for pattern in patterns:
        if pattern == "**":
            return [root]
        if pattern.endswith("/**") and not any(c in pattern[:-3] for c in "*?["):
            roots.append(root / pattern[:-3])
        else:
            roots.append(root)
    return roots


def snapshot() -> dict[str, str] | None:
    # Content digests of every file the active phase may write; None when the turn has no bounded scope.
    from alpi.alp.pipeline_gates import _file_stamp, _SCAN_EXCLUDE_FILES

    resolved = _scope()
    if resolved is None:
        return None
    root, patterns = resolved
    out: dict[str, str] = {}
    seen: set[Path] = set()
    for walk_root in _walk_roots(root, patterns):
        if walk_root in seen or not walk_root.is_dir():
            continue
        seen.add(walk_root)
        excluded = _excluded_roots()
        for dirpath, dirnames, filenames in os.walk(walk_root):
            here = Path(dirpath).resolve()
            if any(here == ex or ex in here.parents for ex in excluded):
                dirnames[:] = []
                continue
            dirnames[:] = [d for d in dirnames if d not in _WALK_EXCLUDE]
            for fn in filenames:
                if fn in _SCAN_EXCLUDE_FILES:
                    continue
                fp = Path(dirpath) / fn
                rel = fp.relative_to(root).as_posix()
                if not any(fnmatch.fnmatchcase(rel, pattern) for pattern in patterns):
                    continue
                stamp = _file_stamp(fp)
                if stamp is not None:
                    out[rel] = stamp
    return out
