"""Terminal tool — run shell commands in foreground or background."""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
import threading
import time
from pathlib import Path

from alpi.home import get_home
from alpi.tools import _state as tool_state_mod
from alpi.tools._approval import check as approval_check
from alpi.tools._sandbox import SandboxUnavailable, wrap_command
from alpi.tools.base import Tool, ToolResult

_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]|\x1b\][^\x07]*\x07|\x1b[@-_]")
# Heartbeat for a blocking fg command (npm build): posts tool_state so the daemon idle-timeout sees a live producer.
_FG_HEARTBEAT_SECONDS = 15


def _strip_ansi(s: str) -> str:
    return _ANSI_RE.sub("", s)

_SAFE_ENV_KEYS = (
    "PATH", "HOME", "USER", "LOGNAME", "SHELL",
    "LANG", "LC_ALL", "LC_CTYPE", "TERM", "TZ",
    "PWD", "TMPDIR",
)


def _build_subprocess_env() -> dict[str, str]:
    from alpi.home import effective_profile_env
    from alpi.tools import _state
    parent = effective_profile_env(get_home())
    out: dict[str, str] = {}
    for key in _SAFE_ENV_KEYS:
        if key in parent:
            out[key] = parent[key]
    for key in parent:
        if key.startswith("LC_") and key not in out:
            out[key] = parent[key]
    # Intentional: an active skill's *declared* env reaches ad-hoc terminal so prose-mode skills (no scripts/run.py) can run their CLI steps; scoped to declared keys, not all secrets.
    for key in _state.get_active_skills_env():
        if key in parent and key not in out:
            out[key] = parent[key]
    out["ALPI_HOME"] = str(get_home())
    try:
        from alpi import config as cfg_mod
        wp = cfg_mod.load(get_home()).workspace_path
    except Exception:
        wp = None
    if wp is not None:
        out["WORKSPACE"] = str(wp)
    return out


def _bg_dir() -> Path:
    root = get_home() / "run" / "bg"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _default_cwd() -> str:
    try:
        from alpi import config as cfg_mod
        cfg = cfg_mod.load(get_home())
        wp = cfg.workspace_path
        if wp is not None:
            return str(wp)
    except Exception:
        pass
    return os.getcwd()


def _sandbox_config() -> tuple[bool, bool]:
    try:
        from alpi import config as cfg_mod
        cfg = cfg_mod.load(get_home())
        return cfg.tools.terminal.sandbox, cfg.tools.terminal.allow_network
    except Exception:
        # Fail closed: unreadable config → sandbox required (wrap_command then raises, caller refuses).
        return True, False


def _resolve_popen_args(command: str) -> list[str] | str:
    sandbox_enabled, allow_network = _sandbox_config()
    if not sandbox_enabled:
        return command
    try:
        from alpi import config as cfg_mod
        cfg = cfg_mod.load(get_home())
        wp = cfg.workspace_path
    except Exception:
        wp = None
    if wp is None:
        wp = Path(_default_cwd())
    return wrap_command(
        command,
        workspace=wp,
        alpi_home=get_home(),
        allow_network=allow_network,
    )


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _record_terminal_run(
    *, outcome: str, at: float, elapsed: float,
    exit_code: int | None = None, timeout_reason: str | None = None,
    pid: int | None = None, output_tail: str | None = None,
) -> None:
    # Never persist the command (secrets in args); output_tail is the redacted output.
    try:
        from alpi import run_ledger
        from alpi.home import get_home, profile_name
        sandbox_enabled, _ = _sandbox_config()
        home = get_home()
        run_ledger.record(
            home, kind="terminal", outcome=outcome, elapsed_s=elapsed, at=at,
            profile=profile_name(home),
            backend=("sandbox" if sandbox_enabled else "local"),
            exit_code=exit_code, timeout_reason=timeout_reason, pid=pid,
            output_tail=output_tail,
        )
    except Exception:  # noqa: BLE001
        pass


class Terminal(Tool):
    name = "terminal"
    description = (
        "Run shell commands. cwd defaults to your workspace.\n"
        "\n"
        "  action=run         blocks up to `timeout` seconds (default)\n"
        "  action=background  spawns detached, returns a pid\n"
        "  action=status|output|kill  manage a background pid\n"
        "\n"
        "Do NOT use `cat/head/tail/less` to read files — use `read_file`.\n"
        "Do NOT use `echo >` or `tee` to write files — use `write_file`.\n"
        "Do NOT use `sed/awk` to edit files — use `edit_file`.\n"
        "Do NOT use `grep/rg` to search file contents — use `search` "
        "(target='content').\n"
        "Do NOT use `find/fd` to locate files — use `search` "
        "(target='files').\n"
        "Do NOT use `ls` to list directories — use `search` "
        "(target='files') with pattern='*'.\n"
        "Do NOT use `curl/wget` for HTTP — use `web_fetch`/`web_search`/"
        "`web_extract`.\n"
        "Do NOT touch memory files (USER.md/MEMORY.md/AGENT.md) — "
        "use `memory`.\n"
        "\n"
        "Stay inside the workspace for exploratory shell work. If the user "
        "explicitly gives you a shell command with an absolute path or `~`, "
        "run that literal command instead of refusing in prose; the approval "
        "gate and OS sandbox decide whether it may execute."
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

    def _run_fg(self, command: str, timeout: int, cwd: str | None) -> ToolResult:
        if not command:
            return ToolResult(ok=False, output="", error="command is required")
        effective_cwd = cwd or _default_cwd()
        decision = approval_check(command, cwd=effective_cwd)
        if not decision.allowed:
            return ToolResult(
                ok=False, output="",
                error=f"refused ({decision.severity.value}): {decision.reason}",
            )
        try:
            popen_args = _resolve_popen_args(command)
        except SandboxUnavailable as e:
            return ToolResult(ok=False, output="", error=str(e))
        use_shell = isinstance(popen_args, str)
        # Capture here: _state's ContextVar doesn't propagate to the heartbeat thread, so it calls emit_cb directly.
        emit_cb = tool_state_mod.get_emit()
        stop_beat = threading.Event()
        beat_thread: threading.Thread | None = None
        if emit_cb is not None:
            def _heartbeat() -> None:
                elapsed = 0
                while not stop_beat.wait(_FG_HEARTBEAT_SECONDS):
                    elapsed += _FG_HEARTBEAT_SECONDS
                    try:
                        emit_cb(f"running… {elapsed}s", False)
                    except Exception:  # noqa: BLE001
                        return
            beat_thread = threading.Thread(target=_heartbeat, daemon=True)
            beat_thread.start()
        _started = time.time()
        try:
            proc = subprocess.run(
                popen_args, shell=use_shell, capture_output=True, text=True,
                timeout=timeout, cwd=effective_cwd,
                env=_build_subprocess_env(),
            )
        except subprocess.TimeoutExpired:
            _record_terminal_run(
                outcome="timeout", at=_started,
                elapsed=time.time() - _started, timeout_reason=f"timeout_{timeout}s",
            )
            return ToolResult(ok=False, output="", error=f"Timed out after {timeout}s")
        finally:
            stop_beat.set()
            if beat_thread is not None:
                beat_thread.join(timeout=1)
        output = _strip_ansi(proc.stdout)
        if proc.stderr:
            output += "\n[stderr]\n" + _strip_ansi(proc.stderr)
        output += f"\n[exit {proc.returncode}]"
        _elapsed = time.time() - _started
        if proc.returncode == 0:
            _record_terminal_run(
                outcome="ok", at=_started,
                elapsed=_elapsed, exit_code=0, output_tail=output,
            )
            return ToolResult(ok=True, output=output)
        stderr_first = (_strip_ansi(proc.stderr).strip().splitlines() or [""])[0]
        short_err = stderr_first or f"command failed (exit {proc.returncode})"
        _record_terminal_run(
            outcome="error", at=_started,
            elapsed=_elapsed, exit_code=proc.returncode, output_tail=output,
        )
        return ToolResult(ok=False, output=output, error=short_err)

    def _run_bg(self, command: str, cwd: str | None) -> ToolResult:
        if not command:
            return ToolResult(ok=False, output="", error="command is required")
        effective_cwd = cwd or _default_cwd()
        decision = approval_check(command, cwd=effective_cwd)
        if not decision.allowed:
            return ToolResult(
                ok=False, output="",
                error=f"refused ({decision.severity.value}): {decision.reason}",
            )
        try:
            popen_args = _resolve_popen_args(command)
        except SandboxUnavailable as e:
            return ToolResult(ok=False, output="", error=str(e))
        use_shell = isinstance(popen_args, str)
        log = tempfile.NamedTemporaryFile(
            prefix="alpi-bg-", suffix=".log", dir=_bg_dir(), delete=False,
        )
        log.close()
        # Popen dups the fd at spawn — closing our handle after is safe.
        with open(log.name, "ab") as out_fh:
            proc = subprocess.Popen(
                popen_args, shell=use_shell, cwd=effective_cwd,
                stdout=out_fh, stderr=subprocess.STDOUT,
                start_new_session=True, env=_build_subprocess_env(),
            )
        registry = _bg_dir() / f"{proc.pid}.meta"
        registry.write_text(
            f"command={command}\nlog={log.name}\nstarted={int(time.time())}\n"
        )
        _record_terminal_run(
            outcome="ok", at=time.time(), elapsed=0.0, pid=proc.pid,
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
        if len(data) > 8000:
            data = "…\n" + data[-8000:]
        return ToolResult(ok=True, output=data or "(no output yet)")

    def _kill(self, pid: int) -> ToolResult:
        if not _pid_alive(pid):
            return ToolResult(ok=True, output=f"pid {pid} not running")
        try:
            os.kill(pid, 15)
        except OSError as e:
            return ToolResult(ok=False, output="", error=f"kill failed: {e}")
        return ToolResult(ok=True, output=f"sent SIGTERM to pid {pid}")


TOOL = Terminal
