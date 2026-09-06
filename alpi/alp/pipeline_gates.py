from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import signal
import stat
import subprocess
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path

GATE_TIMEOUT_SECONDS = 180
GATE_OUTPUT_CAP = 6_000
GATE_LOG_CAP = 64_000
# Agent context sizes its directed-post budget off this constant; a repair must carry every retained actionable line.
GATE_FINDINGS_POST_CHARS = GATE_OUTPUT_CAP
# Minimal env on purpose: gate commands never see the profile's secrets (.env keys stay out).
_GATE_ENV_KEYS = ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR")


def findings_excerpt(output: str, limit: int = GATE_FINDINGS_POST_CHARS) -> str:
    if limit <= 0:
        return ""
    lines = []
    seen = set()
    for raw in output.splitlines():
        line = raw.rstrip()
        if line.lstrip().startswith(("PASS  ", "INFO  ", "Checking artifact:")):
            continue
        if line in seen:
            continue
        seen.add(line)
        lines.append(line)
    text = "\n".join(lines).strip() or output.strip()
    if len(text) <= limit:
        return text
    kept: list[str] = []
    used = 0
    for line in reversed(text.splitlines()):
        size = len(line) + (1 if kept else 0)
        if used + size > limit:
            if not kept:
                return "…" if limit == 1 else f"…{line[-(limit - 1):]}"
            break
        kept.append(line)
        used += size
    if kept:
        return "\n".join(reversed(kept))
    return ""


@dataclass(frozen=True)
class GateStep:
    phase: str
    owner: str
    next_phase: str
    next_owner: str
    next_task: str
    argv: tuple[str, ...]
    cwd: str
    paths: tuple[str, ...] = ()
    repair: str = "owner"


@dataclass(frozen=True)
class PrepareStep:
    pipeline: str
    phase: str
    argv: tuple[str, ...]
    cwd: str


def prepare_for(meta, pipeline: str) -> PrepareStep | None:
    chain = (getattr(meta, "pipelines", None) or {}).get(pipeline)
    if not chain:
        return None
    phase = chain[0]
    raw = (getattr(meta, "pipeline_steps", None) or {}).get(phase)
    prepare = raw.get("prepare") if isinstance(raw, dict) else None
    if not isinstance(prepare, dict):
        return None
    argv = prepare.get("argv")
    cwd = prepare.get("cwd") or ""
    if (
        not isinstance(argv, list) or not argv or not argv[0]
        or not all(isinstance(a, str) for a in argv)
        or not isinstance(cwd, str)
    ):
        return None
    return PrepareStep(
        pipeline=pipeline, phase=phase, argv=tuple(argv), cwd=cwd,
    )


def chain_for(meta, phase: str) -> tuple[str, ...] | None:
    """``()`` = no chain declared (unconstrained); ``None`` = chains exist and phase is in none."""
    from alpi.alp import workgroup as wg_mod

    owner = wg_mod.pipeline_for_phase(meta, phase)
    if owner is not None:
        return owner[1]
    return None if wg_mod.is_pipeline_workgroup(meta) else ()


def step_for(meta, phase: str) -> GateStep | None:
    """Resolve the gate step for ``phase`` from hub-local meta; None = LLM-owned transition."""
    from alpi.alp import workgroup as wg_mod

    steps = getattr(meta, "pipeline_steps", None) or {}
    raw = steps.get(phase)
    if not isinstance(raw, dict):
        return None
    gate = raw.get("gate")
    owner = str(raw.get("owner") or "")
    if not isinstance(gate, dict) or not owner:
        return None
    argv = gate.get("argv")
    cwd = gate.get("cwd") or ""
    if (
        not isinstance(argv, list) or not argv or not argv[0]
        or not all(isinstance(a, str) for a in argv)
        or not isinstance(cwd, str)
    ):
        return None
    if chain_for(meta, phase) is None:
        return None
    next_phase = wg_mod.pipeline_successor(meta, phase)
    nxt = steps.get(next_phase) if next_phase else None
    if next_phase and (
        not isinstance(nxt, dict)
        or not str(nxt.get("owner") or "")
    ):
        return None
    next_owner = str(nxt.get("owner") or "") if isinstance(nxt, dict) else ""
    next_task = str(nxt.get("task") or "") if isinstance(nxt, dict) else ""
    paths = raw.get("paths")
    repair = str(gate.get("repair") or "owner")
    return GateStep(
        phase=phase, owner=owner,
        next_phase=next_phase, next_owner=next_owner, next_task=next_task,
        argv=tuple(argv), cwd=cwd,
        paths=tuple(str(g) for g in paths) if isinstance(paths, list) else (),
        repair=repair,
    )


# Derived/heavy trees are outside every authoring boundary; pruning them keeps the walk cheap.
_SCAN_EXCLUDE = {".git", "node_modules", "dist", ".astro", "public", "__pycache__", ".venv", ".cache"}
# A gate's own `npm install` rewrites these, so they are nobody's deliverable.
_SCAN_EXCLUDE_FILES = {
    "package-lock.json", "npm-shrinkwrap.json", "yarn.lock", "pnpm-lock.yaml",
    "bun.lockb", ".DS_Store",
}


# Keyed by phase, never opener seq — a per-seq key lets a re-task whitewash earlier out-of-paths edits.
def _baseline_path(wg_dir: Path, phase: str) -> Path:
    return wg_dir / "phase_baselines" / f"{phase}.json"


def _runtime_dir(wg_dir: Path, name: str) -> Path:
    from alpi.alp import subscription as sub_mod

    try:
        home = wg_dir.parents[2]
    except IndexError:
        home = None
    if home is not None and wg_dir.name in sub_mod.tombstones(home):
        raise FileNotFoundError(f"workgroup {wg_dir.name!r} was removed")
    path = wg_dir / name
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    return path


def _file_stamp(fp: Path) -> str | None:
    """Content digest, never mtime: restoring a file must clear its violation, and a rewrite always moves mtime."""
    h = hashlib.blake2b(digest_size=16)
    try:
        with fp.open("rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
    except OSError:
        return None
    return h.hexdigest()


def _state_roots(wg_dir: Path) -> frozenset[Path]:
    # Daemon state under the workspace (Docker: /data/.alpi) is never a deliverable: the hub home, the profiles root and the member homes holding scope baselines all fall outside every phase scope.
    from alpi import home as home_mod

    roots = {home_mod._ROOT}
    home = wg_dir.parents[2] if len(wg_dir.parents) > 2 else None
    if home is not None:
        roots.add(home)
        if home.parent.name == "profiles":
            roots.add(home.parent.parent)
    return frozenset(r.resolve() for r in roots)


def _scan_project(root: Path, exclude: frozenset[Path] = frozenset()) -> dict[str, str]:
    out: dict[str, str] = {}
    if not root.is_dir():
        return out
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            d for d in dirnames
            if d not in _SCAN_EXCLUDE and (Path(dirpath) / d).resolve() not in exclude
        ]
        for fn in filenames:
            if fn in _SCAN_EXCLUDE_FILES:
                continue
            stamp = _file_stamp(Path(dirpath) / fn)
            if stamp is not None:
                out[(Path(dirpath) / fn).relative_to(root).as_posix()] = stamp
    return out


# Same jail as run_gate: an escaping cwd never gets scanned, and run_gate reds it anyway.
def _project_root(step: GateStep, workspace: Path) -> Path | None:
    root = (workspace / step.cwd).resolve() if step.cwd else workspace.resolve()
    try:
        root.relative_to(workspace.resolve())
    except ValueError:
        return None
    return root


def snapshot_baseline(wg_dir: Path, step: GateStep, workspace: Path) -> bool:
    """Record the project's file state when the phase opens; True only when THIS call wrote it."""
    if not step.paths:
        return False
    root = _project_root(step, workspace)
    if root is None:
        return False
    bp = _baseline_path(wg_dir, step.phase)
    if bp.exists():
        return False
    _runtime_dir(wg_dir, "phase_baselines")
    snapshot = _scan_project(root, _state_roots(wg_dir))
    tmp = bp.with_suffix(".tmp")
    tmp.write_text(json.dumps(snapshot, separators=(",", ":")))
    os.replace(tmp, bp)
    return True


def refresh_baseline(wg_dir: Path, step: GateStep, workspace: Path) -> bool:
    """Accept the trusted gate command's own filesystem effects after a clean boundary check."""
    if not step.paths:
        return False
    root = _project_root(step, workspace)
    if root is None:
        return False
    bp = _baseline_path(wg_dir, step.phase)
    _runtime_dir(wg_dir, "phase_baselines")
    snapshot = _scan_project(root, _state_roots(wg_dir))
    tmp = bp.with_suffix(".tmp")
    tmp.write_text(json.dumps(snapshot, separators=(",", ":")))
    os.replace(tmp, bp)
    return True


def owned_paths_changed(
    wg_dir: Path, step: GateStep, workspace: Path,
) -> bool | None:
    """Whether this phase changed an owned path since its opener baseline."""
    if not step.paths:
        return None
    root = _project_root(step, workspace)
    if root is None:
        return None
    try:
        baseline = json.loads(_baseline_path(wg_dir, step.phase).read_text())
    except (OSError, ValueError):
        return None
    if not isinstance(baseline, dict):
        return None
    current = _scan_project(root, _state_roots(wg_dir))
    owned = tuple(step.paths)
    relevant = {
        rel for rel in set(baseline) | set(current)
        if any(fnmatch.fnmatchcase(rel, pattern) for pattern in owned)
    }
    return any(baseline.get(rel) != current.get(rel) for rel in relevant)


# NOT _SCAN_EXCLUDE: a build gate observes dist/ and public/.
_SIGNATURE_EXCLUDE = {".git", "node_modules", ".venv", ".cache", "__pycache__"}


def _signature_entry(fp: Path) -> str | None:
    try:
        st = fp.lstat()
    except OSError:
        return None
    mode = f"{stat.S_IMODE(st.st_mode):04o}"
    if stat.S_ISLNK(st.st_mode):
        try:
            return f"l:{mode}:{os.readlink(fp)}"
        except OSError:
            return None
    stamp = _file_stamp(fp)
    return None if stamp is None else f"f:{mode}:{stamp}"


def workspace_signature(step: GateStep, workspace: Path) -> str:
    root = _project_root(step, workspace)
    if root is None:
        return ""
    h = hashlib.blake2b(digest_size=16)
    entries: list[tuple[str, str]] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SIGNATURE_EXCLUDE]
        here = Path(dirpath)
        for dn in dirnames:
            entries.append(((here / dn).relative_to(root).as_posix(), "d:"))
        for fn in filenames:
            fp = here / fn
            entry = _signature_entry(fp)
            if entry is not None:
                entries.append((fp.relative_to(root).as_posix(), entry))
    for rel, entry in sorted(entries):
        h.update(rel.encode("utf-8", "replace"))
        h.update(b"\0")
        h.update(entry.encode("utf-8", "replace"))
        h.update(b"\0")
    return h.hexdigest()


def clear_baseline(wg_dir: Path, phase: str) -> None:
    _baseline_path(wg_dir, phase).unlink(missing_ok=True)


def paths_violations(wg_dir: Path, step: GateStep, workspace: Path) -> str:
    """Return out-of-path changes; a missing baseline is a hard failure."""
    if not step.paths:
        return ""
    root = _project_root(step, workspace)
    if root is None:
        return ""
    bp = _baseline_path(wg_dir, step.phase)
    try:
        baseline = json.loads(bp.read_text())
    except (OSError, ValueError):
        return (
            f"BOUNDARY {step.phase}: phase baseline is missing or unreadable; "
            "refusing to verify this phase"
        )
    current = _scan_project(root, _state_roots(wg_dir))
    allowed = tuple(step.paths)

    def _within(rel: str) -> bool:
        return any(fnmatch.fnmatchcase(rel, g) for g in allowed)

    offenders: list[str] = []
    for rel, stamp in current.items():
        if baseline.get(rel) == stamp or _within(rel):
            continue
        offenders.append(f"  {rel} — {'changed' if rel in baseline else 'created'}, "
                         f"outside: {', '.join(allowed)}")
    for rel in baseline:
        if rel not in current and not _within(rel):
            offenders.append(f"  {rel} — deleted, outside: {', '.join(allowed)}")
    if not offenders:
        return ""
    return (
        f"BOUNDARY {step.phase}: files outside @{step.owner}'s declared paths "
        "changed during this phase. Name each file below in your handoff so the "
        "hub routes it to the phase that owns it — posting is always available "
        "to you. Undo it yourself ONLY if your own tools can restore the exact "
        "state you found:\n" + "\n".join(sorted(offenders))
    )


def _stop_process_group(proc: subprocess.Popen) -> None:
    try:
        os.killpg(proc.pid, signal.SIGTERM)
        proc.wait(timeout=1)
    except (OSError, subprocess.TimeoutExpired):
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except OSError:
            proc.kill()
        proc.wait()


def _run_command(
    argv: tuple[str, ...], cwd_value: str, workspace: Path, kind: str,
) -> tuple[bool, str]:
    cwd = (workspace / cwd_value).resolve() if cwd_value else workspace.resolve()
    try:
        cwd.relative_to(workspace.resolve())
    except ValueError:
        return False, f"{kind} cwd escapes the workspace: {cwd}"
    if not cwd.is_dir():
        return False, f"{kind} cwd missing: {cwd}"
    env = {k: v for k, v in os.environ.items() if k in _GATE_ENV_KEYS}
    tail = bytearray()
    try:
        proc = subprocess.Popen(
            list(argv), cwd=str(cwd), env=env, shell=False,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    except OSError as e:
        return False, f"{kind} failed to start: {e}"

    def _drain() -> None:
        assert proc.stdout is not None
        while True:
            chunk = proc.stdout.read(8192)
            if not chunk:
                return
            tail.extend(chunk)
            if len(tail) > GATE_OUTPUT_CAP:
                del tail[:-GATE_OUTPUT_CAP]

    reader = threading.Thread(target=_drain, name="alpi-gate-output", daemon=True)
    reader.start()
    timed_out = False
    try:
        returncode = proc.wait(timeout=GATE_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        timed_out = True
        _stop_process_group(proc)
        returncode = proc.returncode
    reader.join(timeout=1)
    if reader.is_alive():
        _stop_process_group(proc)
        reader.join(timeout=1)
    out = bytes(tail).decode("utf-8", errors="replace").strip()
    if timed_out:
        return False, f"{kind} timed out after {GATE_TIMEOUT_SECONDS}s"
    return returncode == 0, out


def run_gate(step: GateStep, workspace: Path) -> tuple[bool, str]:
    return _run_command(step.argv, step.cwd, workspace, "gate")


def run_prepare(step: PrepareStep, workspace: Path) -> tuple[bool, str]:
    return _run_command(step.argv, step.cwd, workspace, "prepare")


def write_prepare_log(
    wg_dir: Path, step: PrepareStep, passed: bool, output: str,
) -> None:
    log_dir = _runtime_dir(wg_dir, "prepares")
    record = json.dumps({
        "pipeline": step.pipeline, "phase": step.phase,
        "argv": list(step.argv), "cwd": step.cwd,
        "passed": passed, "output": output[-GATE_LOG_CAP:],
    }, ensure_ascii=False, indent=2)
    fd, tmp = tempfile.mkstemp(dir=log_dir, prefix=".prepare-")
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write(record + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, log_dir / f"{step.pipeline}.log")
    except OSError:
        Path(tmp).unlink(missing_ok=True)
        raise


def gate_log_record(wg_dir: Path, phase: str, seq: int) -> dict | None:
    """Fail CLOSED on any unexpected shape: a truthy non-bool `passed` would read a red gate as green."""
    try:
        record = json.loads(
            (wg_dir / "gates" / f"{phase}-{seq}.log").read_text(encoding="utf-8"),
        )
    except (OSError, ValueError):
        return None
    if not isinstance(record, dict):
        return None
    if record.get("phase") != phase:
        return None
    logged = record.get("task_seq")
    if type(logged) is not int or logged != seq:
        return None
    if not isinstance(record.get("passed"), bool):
        return None
    return record


def gate_log_verdict(wg_dir: Path, phase: str, seq: int) -> bool | None:
    """``None`` = the gate never ran on the post at ``seq``, or its record is unreadable."""
    record = gate_log_record(wg_dir, phase, seq)
    return None if record is None else bool(record.get("passed"))


def owner_post_under_gate(
    posts: list[dict], owner_pubkeys: set[str], hub_pubkey: str, opened_seq: int,
    *, include_skip: bool = False,
) -> int | None:
    # The daemon gates an owner's bare `#skip` too: after a rewind a phase whose artifacts already stand can only close through its gate, since `#done skipped` is refused once the run holds an earlier delivery.
    from alpi.alp import tasks as tasks_mod

    seqs = [
        int(p.get("seq", 0)) for p in posts
        if int(p.get("seq", 0)) > opened_seq
        and (str(p.get("from") or "") in owner_pubkeys if owner_pubkeys
             else str(p.get("from") or "") != hub_pubkey)
        and not tasks_mod.is_working_only(str(p.get("text") or ""))
        and (include_skip or not tasks_mod.is_skip_only(str(p.get("text") or "")))
    ]
    return max(seqs) if seqs else None


def owner_delivery(
    posts: list[dict], owner_pubkeys: set[str], opened_seq: int,
) -> tuple[int, str] | None:
    """Return the owner's latest non-heartbeat post for the active phase."""
    from alpi.alp import tasks as tasks_mod

    deliveries = [
        (int(p.get("seq", 0)), str(p.get("text") or ""))
        for p in posts
        if int(p.get("seq", 0)) > opened_seq
        and str(p.get("from") or "") in owner_pubkeys
        and not tasks_mod.is_working_only(str(p.get("text") or ""))
    ]
    return max(deliveries, default=None, key=lambda item: item[0])


def write_gate_log(wg_dir: Path, step: GateStep, seq: int, passed: bool, output: str) -> None:
    log_dir = _runtime_dir(wg_dir, "gates")
    record = json.dumps({
        "phase": step.phase, "task_seq": seq, "argv": list(step.argv),
        "cwd": step.cwd, "passed": passed, "output": output[-GATE_LOG_CAP:],
    }, ensure_ascii=False, indent=2)
    fd, tmp = tempfile.mkstemp(dir=log_dir, prefix=".gate-")
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write(record + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, log_dir / f"{step.phase}-{seq}.log")
    except OSError:
        Path(tmp).unlink(missing_ok=True)
        raise


def done_text(step: GateStep, output: str) -> str:
    tail = output.splitlines()[-1][:160] if output else "no output"
    return f"#done {step.phase} verified · gate:{Path(step.argv[0]).name} · {tail}"


def next_task_text(step: GateStep) -> str | None:
    if not (step.next_phase and step.next_owner):
        return None
    body = step.next_task or f"run the {step.next_phase} phase"
    return f"@{step.next_owner} #task #{step.next_phase} · {body}"
