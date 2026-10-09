"""Terminal tool — run shell commands in foreground or background."""

from __future__ import annotations

import os
import re
import signal
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path

from alpi.home import alpi_root, get_home
from alpi.tools import _state as tool_state_mod
from alpi.tools._approval import check as approval_check
from alpi.tools._sandbox import (
    SandboxUnavailable, member_root_paths, phase_write_rules, scoped_temp_dir, wrap_command,
)
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
    for key in () if _is_member() else _state.get_active_skills_env():
        if key in parent and key not in out:
            out[key] = parent[key]
    out["ALPI_HOME"] = str(get_home())
    from alpi import authority
    out.update(authority.environ())
    from alpi.home import workspace_env
    ws = workspace_env(get_home())
    out.update(ws)
    if "ALPI_WORKSPACE" in ws:
        out["WORKSPACE"] = ws["ALPI_WORKSPACE"]
    from alpi.core.execution_world import current
    world = current()
    if (
        os.environ.get("ALPI_WORKGROUP_WRITE_SCOPE") is not None
        and sys.platform == "darwin"
        and (world is None or world.backend == "local")
    ):
        out["TMPDIR"] = str(scoped_temp_dir())
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


_MEMBER_NO_SANDBOX = (
    "terminal is unavailable here to member devices and to peers without a tool policy: their "
    "commands run only inside an OS "
    "sandbox that hides the whole alpi home and every other process, which only Linux bubblewrap "
    "provides outside Docker (the macOS sandbox cannot hide other processes' arguments and "
    "environment). An admin device can run it."
)
_MEMBER_INSIDE_HOME = (
    "terminal is unavailable to member devices and peers without a tool policy for {what} {path}: "
    "it is inside the alpi home or a credentials folder, or contains one, which their commands never "
    "see. Set the profile's workspace outside them, or run it from an admin device."
)


def _overlaps(path: Path, root: Path) -> bool:
    return path == root or root in path.parents or path in root.parents


def _is_member() -> bool:
    from alpi.tools._paths import private_areas_fenced
    return private_areas_fenced()


def _owner() -> str:
    from alpi.host.connection_context import current
    ctx = current()
    return f"{ctx.connection_id}:{ctx.device_id or ''}"


def _proc_start(stat: str) -> str | None:
    fields = stat.rpartition(")")[2].split()
    return f"proc:{fields[19]}" if len(fields) > 19 else None


def _process_identity(pid: int) -> str | None:
    try:
        return _proc_start(Path(f"/proc/{pid}/stat").read_text(encoding="utf-8"))
    except OSError:
        pass
    try:
        out = subprocess.run(
            ["ps", "-o", "lstart=", "-p", str(pid)], capture_output=True, text=True, timeout=5,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    return out or None


def _sandbox_config() -> tuple[bool, bool]:
    try:
        from alpi import config as cfg_mod
        cfg = cfg_mod.load(get_home())
        return cfg.tools.terminal.sandbox, cfg.tools.terminal.allow_network
    except Exception:
        # Fail closed: unreadable config → sandbox required (wrap_command then raises, caller refuses).
        return True, False


def _resolve_popen_args(
    command: str,
    cwd: str | None = None,
    *,
    docker_container_name: str | None = None,
) -> list[str] | str:
    from alpi import authority
    from alpi.core.execution_world import current as current_world

    world = current_world()
    try:
        from alpi import config as cfg_mod
        cfg = cfg_mod.load(get_home())
        wp = cfg.workspace_path
    except Exception:
        wp = None
    if wp is None:
        wp = Path(_default_cwd())
    from alpi.runtime import is_docker
    if os.environ.get("ALPI_WORKGROUP_WRITE_SCOPE") is not None and is_docker():
        raise SandboxUnavailable(
            "terminal is unavailable during scoped workgroup phases in Docker; "
            "use native file and search tools. Daemon gates still run"
        )
    write_rules = phase_write_rules(wp)
    member_root = alpi_root().resolve() if _is_member() else None
    if member_root is not None:
        home_dir = Path(os.path.expanduser("~"))
        hidden = (*member_root_paths(alpi_root()), *(home_dir / d for d in (".ssh", ".aws", ".gnupg")))
        for what, path in (("workspace", wp), ("cwd", Path(cwd or _default_cwd()))):
            for form in (path.absolute(), path.resolve()):
                if any(_overlaps(form, root) for root in hidden):
                    raise SandboxUnavailable(_MEMBER_INSIDE_HOME.format(what=what, path=path))
    if world is not None and world.backend != "local":
        return world.command(
            command, Path(cwd or _default_cwd()).resolve(),
            _SAFE_ENV_KEYS + ("ALPI_HOME", "ALPI_WORKSPACE", "WORKSPACE", authority.ENV),
            container_name=docker_container_name, write_rules=write_rules,
            member=member_root is not None,
        )
    sandbox_enabled, allow_network = _sandbox_config()
    if member_root is not None:
        try:
            return wrap_command(
                command,
                workspace=wp,
                alpi_home=get_home(),
                allow_network=allow_network if sandbox_enabled else True,
                write_rules=write_rules,
                member_root=member_root,
            )
        except SandboxUnavailable as exc:
            raise SandboxUnavailable(_MEMBER_NO_SANDBOX) from exc
    if not sandbox_enabled and write_rules is None:
        return command
    if not sandbox_enabled:
        allow_network = True
    return wrap_command(
        command,
        workspace=wp,
        alpi_home=get_home(),
        allow_network=allow_network,
        write_rules=write_rules,
    )


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _docker_container_name() -> str | None:
    from alpi.core.execution_world import current as current_world

    world = current_world()
    if world is None or world.backend != "docker":
        return None
    return f"alpi-{uuid.uuid4().hex}"


def _remove_docker_container(container_name: str | None, env: dict[str, str]) -> None:
    if container_name is None or not re.fullmatch(r"alpi-[a-f0-9]{32}", container_name):
        return
    try:
        subprocess.run(
            ["docker", "rm", "-f", container_name],
            capture_output=True, timeout=10, env=env,
        )
    except (OSError, subprocess.SubprocessError):
        pass


def _record_detached_child(pid: int) -> None:
    from alpi.runs import record_current_child

    record_current_child(pid)


def _stamped(env: dict[str, str]) -> dict[str, str]:
    from alpi.runs import stamp_env

    return stamp_env(env)


def _kill_process_group(proc: subprocess.Popen | None) -> None:
    if proc is None:
        return
    try:
        group = os.getpgid(proc.pid)
        # Only when the child leads its own group: otherwise this is OUR group and the
        # signal would take the daemon down with it.
        os.killpg(group, signal.SIGKILL) if group == proc.pid else proc.kill()
    except (ProcessLookupError, PermissionError, OSError, AttributeError):
        proc.kill()
    try:
        proc.wait(timeout=5)
    except Exception:  # noqa: BLE001
        pass


def _record_terminal_run(
    *, outcome: str, at: float, elapsed: float,
    exit_code: int | None = None, timeout_reason: str | None = None,
    pid: int | None = None, output_tail: str | None = None,
) -> None:
    # Never persist the command (secrets in args); output_tail is the redacted output.
    try:
        from alpi import run_ledger
        from alpi.core.execution_world import current as current_world
        from alpi.home import get_home, profile_name
        sandbox_enabled, _ = _sandbox_config()
        home = get_home()
        run_ledger.record(
            home, kind="terminal", outcome=outcome, elapsed_s=elapsed, at=at,
            profile=profile_name(home),
            workgroup_id=os.environ.get("ALPI_WORKGROUP_DISPATCH") or None,
            backend=(
                current_world().backend if current_world() is not None
                else "sandbox" if sandbox_enabled else "local"
            ),
            exit_code=exit_code, timeout_reason=timeout_reason, pid=pid,
            output_tail=output_tail,
        )
    except Exception:  # noqa: BLE001
        pass


PIPELINE_RUN_TIMEOUT_SECONDS = 900
DEFAULT_RUN_TIMEOUT_SECONDS = 120


def default_run_timeout() -> int:
    # A bootstrap's cold `npm ci` under a full fleet outlives 120 s; the soft turn budget still bounds the turn.
    return PIPELINE_RUN_TIMEOUT_SECONDS if os.environ.get("ALPI_WORKGROUP_PIPELINE") == "1" else DEFAULT_RUN_TIMEOUT_SECONDS


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
            "timeout": {"type": "integer", "description": "Seconds (run only). Defaults to 120, or 900 inside a pipeline turn where a cold `npm ci` must finish.", "default": 120},
            "cwd": {"type": "string", "description": "Working directory (absolute)."},
            "pid": {"type": "integer", "description": "PID for status/output/kill."},
        },
    }

    def run(
        self,
        action: str = "run",
        command: str | None = None,
        timeout: int | None = None,
        cwd: str | None = None,
        pid: int | None = None,
    ) -> ToolResult:
        if action == "run":
            return self._run_fg(command or "", timeout or default_run_timeout(), cwd)
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
        if timeout < 1:
            return ToolResult(ok=False, output="", error="timeout must be at least 1 second")
        effective_cwd = cwd or _default_cwd()
        docker_container_name = _docker_container_name()
        fenced_args = None
        if _is_member():
            try:
                fenced_args = _resolve_popen_args(
                    command, effective_cwd, docker_container_name=docker_container_name,
                )
            except (SandboxUnavailable, RuntimeError) as e:
                return ToolResult(ok=False, output="", error=str(e))
        decision = approval_check(command, cwd=effective_cwd)
        if not decision.allowed:
            return ToolResult(
                ok=False, output="",
                error=f"refused ({decision.severity.value}): {decision.reason}",
            )
        try:
            popen_args = fenced_args if fenced_args is not None else _resolve_popen_args(
                command, effective_cwd, docker_container_name=docker_container_name,
            )
        except (SandboxUnavailable, RuntimeError) as e:
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
        subprocess_env = _build_subprocess_env()
        process_completed = False
        child: subprocess.Popen | None = None
        try:
            # Its own process group, so the timeout can reach what the shell spawned;
            # that same session takes it out of the terminal's Ctrl+C, which is why every
            # exceptional exit below has to do the killing itself.
            child = subprocess.Popen(
                popen_args, shell=use_shell,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                cwd=effective_cwd, env=_stamped(subprocess_env), start_new_session=True,
            )
            _record_detached_child(child.pid)
            stdout, stderr = child.communicate(timeout=timeout)
            proc = subprocess.CompletedProcess(
                popen_args, child.returncode, stdout=stdout, stderr=stderr,
            )
            process_completed = True
        except subprocess.TimeoutExpired:
            _kill_process_group(child)
            _record_terminal_run(
                outcome="timeout", at=_started,
                elapsed=time.time() - _started, timeout_reason=f"timeout_{timeout}s",
            )
            return ToolResult(ok=False, output="", error=f"Timed out after {timeout}s")
        except BaseException:
            _kill_process_group(child)
            raise
        finally:
            if docker_container_name is not None:
                if not process_completed:
                    _remove_docker_container(docker_container_name, subprocess_env)
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
        from alpi.core.execution_world import current as current_world

        world = current_world()
        if world is not None and world.backend == "docker":
            return ToolResult(
                ok=False, output="",
                error="background commands are unavailable in the ephemeral Docker execution world",
            )
        effective_cwd = cwd or _default_cwd()
        fenced_args = None
        if _is_member():
            try:
                fenced_args = _resolve_popen_args(command, effective_cwd)
            except SandboxUnavailable as e:
                return ToolResult(ok=False, output="", error=str(e))
        decision = approval_check(command, cwd=effective_cwd)
        if not decision.allowed:
            return ToolResult(
                ok=False, output="",
                error=f"refused ({decision.severity.value}): {decision.reason}",
            )
        try:
            popen_args = fenced_args if fenced_args is not None else _resolve_popen_args(command, effective_cwd)
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
                start_new_session=True, env=_stamped(_build_subprocess_env()),
            )
        _record_detached_child(proc.pid)
        registry = _bg_dir() / f"{proc.pid}.meta"
        registry.write_text(
            f"log={log.name}\nstarted={int(time.time())}\nowner={_owner()}\n"
            f"ident={_process_identity(proc.pid) or ''}\n"
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
        if _is_member() and out.get("owner") != _owner():
            return {}
        return out

    def _same_process(self, pid: int, meta: dict[str, str]) -> bool:
        ident = meta.get("ident")
        if not ident:
            return not _is_member()
        return _process_identity(pid) == ident

    def _status(self, pid: int) -> ToolResult:
        meta = self._meta(pid)
        if not meta:
            return ToolResult(ok=False, output="", error=f"no background job with pid {pid}")
        alive = _pid_alive(pid) and self._same_process(pid, meta)
        started = int(meta.get("started", "0"))
        elapsed = int(time.time()) - started if started else 0
        return ToolResult(ok=True, output=(
            f"pid={pid} running={alive} elapsed={elapsed}s\n"
            f"log={meta.get('log', '')}"
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
        meta = self._meta(pid)
        if _is_member() and not meta:
            return ToolResult(ok=False, output="", error=f"no background job with pid {pid}")
        if not _pid_alive(pid) or (meta and not self._same_process(pid, meta)):
            return ToolResult(ok=True, output=f"pid {pid} not running")
        try:
            os.kill(pid, 15)
        except OSError as e:
            return ToolResult(ok=False, output="", error=f"kill failed: {e}")
        return ToolResult(ok=True, output=f"sent SIGTERM to pid {pid}")


TOOL = Terminal
