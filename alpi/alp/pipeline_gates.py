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
GATE_OUTPUT_CAP = 8_000
GATE_LOG_CAP = 64_000
# agent_context sizes its directed-post budget off this constant.
GATE_FINDINGS_POST_CHARS = 900
# Minimal env on purpose: gate commands never see the profile's secrets (.env keys stay out).
_GATE_ENV_KEYS = ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR")


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
    return GateStep(
        phase=phase, owner=owner,
        next_phase=next_phase, next_owner=next_owner, next_task=next_task,
        argv=tuple(argv), cwd=cwd,
        paths=tuple(str(g) for g in paths) if isinstance(paths, list) else (),
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


def _scan_project(root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not root.is_dir():
        return out
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SCAN_EXCLUDE]
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
    bp.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    snapshot = _scan_project(root)
    tmp = bp.with_suffix(".tmp")
    tmp.write_text(json.dumps(snapshot, separators=(",", ":")))
    os.replace(tmp, bp)
    return True


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
    """Out-of-paths changes as a re-taskable red; "" = clean, and a missing baseline fails open."""
    if not step.paths:
        return ""
    root = _project_root(step, workspace)
    if root is None:
        return ""
    bp = _baseline_path(wg_dir, step.phase)
    try:
        baseline = json.loads(bp.read_text())
    except (OSError, ValueError):
        return ""
    current = _scan_project(root)
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


def run_gate(step: GateStep, workspace: Path) -> tuple[bool, str]:
    cwd = (workspace / step.cwd).resolve() if step.cwd else workspace.resolve()
    try:
        cwd.relative_to(workspace.resolve())
    except ValueError:
        return False, f"gate cwd escapes the workspace: {cwd}"
    if not cwd.is_dir():
        return False, f"gate cwd missing: {cwd}"
    env = {k: v for k, v in os.environ.items() if k in _GATE_ENV_KEYS}
    tail = bytearray()
    try:
        proc = subprocess.Popen(
            list(step.argv), cwd=str(cwd), env=env, shell=False,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    except OSError as e:
        return False, f"gate failed to start: {e}"

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
        return False, f"gate timed out after {GATE_TIMEOUT_SECONDS}s"
    return returncode == 0, out


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
) -> int | None:
    from alpi.alp import tasks as tasks_mod

    seqs = [
        int(p.get("seq", 0)) for p in posts
        if int(p.get("seq", 0)) > opened_seq
        and (str(p.get("from") or "") in owner_pubkeys if owner_pubkeys
             else str(p.get("from") or "") != hub_pubkey)
        and not tasks_mod.is_working(str(p.get("text") or ""))
        and not tasks_mod.is_skip(str(p.get("text") or ""))
    ]
    return max(seqs) if seqs else None


def write_gate_log(wg_dir: Path, step: GateStep, seq: int, passed: bool, output: str) -> None:
    log_dir = wg_dir / "gates"
    log_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
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
