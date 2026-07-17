from __future__ import annotations

import json
import os
import signal
import subprocess
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

GATE_TIMEOUT_SECONDS = 180
GATE_OUTPUT_CAP = 8_000
GATE_LOG_CAP = 64_000
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


def step_for(meta, phase: str) -> GateStep | None:
    """Resolve the gate step for ``phase`` from hub-local meta; None = LLM-owned transition."""
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
    pipeline = tuple(getattr(meta, "pipeline", ()) or ())
    if pipeline and phase not in pipeline:
        return None
    next_phase = str(raw.get("next") or "")
    nxt = steps.get(next_phase) if next_phase else None
    if next_phase and (
        not isinstance(nxt, dict)
        or not str(nxt.get("owner") or "")
        or (pipeline and next_phase not in pipeline)
    ):
        return None
    next_owner = str(nxt.get("owner") or "") if isinstance(nxt, dict) else ""
    next_task = str(nxt.get("task") or "") if isinstance(nxt, dict) else ""
    return GateStep(
        phase=phase, owner=owner,
        next_phase=next_phase, next_owner=next_owner, next_task=next_task,
        argv=tuple(argv), cwd=cwd,
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
