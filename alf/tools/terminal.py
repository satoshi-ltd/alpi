"""Terminal tool — run shell commands. Replaces the old `bash` tool.

Supports two modes:

- **foreground** (default): blocks up to ``timeout`` seconds, returns stdout/
  stderr/exit code.
- **background**: spawns the command detached, registers the PID, and returns
  a handle. Later calls can use ``action="status"`` / ``"output"`` /
  ``"kill"`` with the PID.
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
import time
from pathlib import Path

# Matches CSI / OSC / ESC sequences commonly emitted by colorized CLIs.
# Stripped before the output reaches the LLM so styling doesn't pollute
# reasoning. Files still land on disk with whatever bytes the command
# wrote (we only sanitize the in-memory payload we hand back).
_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]|\x1b\][^\x07]*\x07|\x1b[@-_]")


def _strip_ansi(s: str) -> str:
    return _ANSI_RE.sub("", s)

from alf.home import get_home
from alf.tools.base import Tool, ToolResult


def _bg_dir() -> Path:
    root = get_home() / "run" / "bg"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _default_cwd() -> str:
    """Where terminal commands start if the caller doesn't specify cwd.

    The profile's workspace if configured, else the current cwd. This
    doesn't sandbox the shell — absolute paths and ``~`` still work —
    but relative paths and tools like ``ls`` without args stay inside
    the intended area.
    """
    try:
        from alf import config as cfg_mod
        cfg = cfg_mod.load(get_home())
        wp = cfg.workspace_path
        if wp is not None:
            return str(wp)
    except Exception:
        pass
    return os.getcwd()


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


class Terminal(Tool):
    name = "terminal"
    description = (
        "Run shell commands. cwd defaults to your workspace.\n"
        "\n"
        "  action=run        (default) blocks up to `timeout` seconds\n"
        "  action=background spawns detached and returns a pid\n"
        "  action=status|output|kill  query or stop a background pid\n"
        "\n"
        "DO NOT use terminal for:\n"
        "  • reading files        → use read_file\n"
        "  • writing files        → use write_file\n"
        "  • editing files        → use edit_file\n"
        "  • searching contents   → use grep\n"
        "  • listing/globbing     → use glob\n"
        "  • HTTP(S)              → use web_fetch / web_search / web_extract\n"
        "  • memory files         → use memory\n"
        "  • skill files          → use create_skill / edit_skill / delete_skill\n"
        "\n"
        "DO NOT use to escape the workspace sandbox (~/Documents, /etc/*, "
        "parent dirs, $HOME tricks, etc.) unless the user explicitly "
        "confirms. If they ask you to touch something outside, suggest "
        "`/workspace <path>` to widen the scope instead.\n"
        "\n"
        "Good uses: git, npm install, make, pytest, docker, systemctl, any "
        "build or process-management command. Output has ANSI codes stripped."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["run", "background", "status", "output", "kill"],
                "default": "run",
            },
            "command": {"type": "string", "description": "Shell command (run/background)."},
            "timeout": {"type": "integer", "description": "Seconds (run only).", "default": 120},
            "cwd": {"type": "string", "description": "Working directory (absolute)."},
            "pid": {"type": "integer", "description": "PID for status/output/kill."},
        },
    }

    def run(
        self,
        action: str = "run",
        command: str | None = None,
        timeout: int = 120,
        cwd: str | None = None,
        pid: int | None = None,
    ) -> ToolResult:
        if action == "run":
            return self._run_fg(command or "", timeout, cwd)
        if action == "background":
            return self._run_bg(command or "", cwd)
        if action in ("status", "output", "kill"):
            if pid is None:
                return ToolResult(ok=False, output="", error=f"{action}: pid is required")
            return getattr(self, f"_{action}")(pid)
        return ToolResult(ok=False, output="", error=f"unknown action: {action}")

    # ------------------------------------------------------------------
    # Foreground
    # ------------------------------------------------------------------

    def _run_fg(self, command: str, timeout: int, cwd: str | None) -> ToolResult:
        if not command:
            return ToolResult(ok=False, output="", error="command is required")
        try:
            proc = subprocess.run(
                command, shell=True, capture_output=True, text=True,
                timeout=timeout, cwd=cwd or _default_cwd(),
            )
        except subprocess.TimeoutExpired:
            return ToolResult(ok=False, output="", error=f"Timed out after {timeout}s")
        output = _strip_ansi(proc.stdout)
        if proc.stderr:
            output += "\n[stderr]\n" + _strip_ansi(proc.stderr)
        output += f"\n[exit {proc.returncode}]"
        if proc.returncode == 0:
            return ToolResult(ok=True, output=output)
        # Build a short, human-readable error for the UI.
        stderr_first = (_strip_ansi(proc.stderr).strip().splitlines() or [""])[0]
        short_err = stderr_first or f"command failed (exit {proc.returncode})"
        return ToolResult(ok=False, output=output, error=short_err)

    # ------------------------------------------------------------------
    # Background
    # ------------------------------------------------------------------

    def _run_bg(self, command: str, cwd: str | None) -> ToolResult:
        if not command:
            return ToolResult(ok=False, output="", error="command is required")
        log = tempfile.NamedTemporaryFile(
            prefix="alf-bg-", suffix=".log", dir=_bg_dir(), delete=False,
        )
        log.close()
        proc = subprocess.Popen(
            command, shell=True, cwd=cwd or _default_cwd(),
            stdout=open(log.name, "ab"), stderr=subprocess.STDOUT,
            start_new_session=True,  # detach from our session
        )
        registry = _bg_dir() / f"{proc.pid}.meta"
        registry.write_text(
            f"command={command}\nlog={log.name}\nstarted={int(time.time())}\n"
        )
        return ToolResult(ok=True, output=(
            f"started pid={proc.pid}\nlog={log.name}\n"
            f"Use terminal(action='status'/'output'/'kill', pid={proc.pid}) to manage."
        ))

    def _meta(self, pid: int) -> dict[str, str]:
        path = _bg_dir() / f"{pid}.meta"
        if not path.exists():
            return {}
        out: dict[str, str] = {}
        for line in path.read_text().splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                out[k] = v
        return out

    def _status(self, pid: int) -> ToolResult:
        meta = self._meta(pid)
        if not meta:
            return ToolResult(ok=False, output="", error=f"no background job with pid {pid}")
        alive = _pid_alive(pid)
        started = int(meta.get("started", "0"))
        elapsed = int(time.time()) - started if started else 0
        return ToolResult(ok=True, output=(
            f"pid={pid} running={alive} elapsed={elapsed}s\n"
            f"command={meta.get('command', '')}\nlog={meta.get('log', '')}"
        ))

    def _output(self, pid: int) -> ToolResult:
        meta = self._meta(pid)
        log = meta.get("log", "")
        if not log or not Path(log).exists():
            return ToolResult(ok=False, output="", error=f"no log for pid {pid}")
        data = _strip_ansi(Path(log).read_text())
        # Cap to last 8000 chars to avoid huge dumps.
        if len(data) > 8000:
            data = "…\n" + data[-8000:]
        return ToolResult(ok=True, output=data or "(no output yet)")

    def _kill(self, pid: int) -> ToolResult:
        if not _pid_alive(pid):
            return ToolResult(ok=True, output=f"pid {pid} not running")
        try:
            os.kill(pid, 15)  # SIGTERM
        except OSError as e:
            return ToolResult(ok=False, output="", error=f"kill failed: {e}")
        return ToolResult(ok=True, output=f"sent SIGTERM to pid {pid}")


TOOL = Terminal
