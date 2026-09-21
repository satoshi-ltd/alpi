"""MCPClient — stdio JSON-RPC client for MCP servers."""

from __future__ import annotations

import collections
import json
import logging
import os
import queue
import signal
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("alpi.mcp")

# Handshake uses the November 2024 MCP spec.
_PROTOCOL_VERSION = "2024-11-05"
_CLIENT_INFO = {"name": "alpi", "version": "0.2"}


# Deep enough for any burst a real call answers through, shallow enough to bound the daemon.
_STDOUT_BUFFER_LINES = 1024
# One reply per in-flight request; the rest is a server repeating an id it already answered.
_REPLY_BUFFER_LINES = 16


class _LineBuffer:
    # A ring, not a queue: notifications at rest must not grow memory, and put() must not block.

    def __init__(self, maxlen: int = _STDOUT_BUFFER_LINES) -> None:
        self._lines: collections.deque[str] = collections.deque(maxlen=maxlen)
        self._replies: collections.deque[str] = collections.deque()
        self._expected: set[int] = set()
        self._cv = threading.Condition()
        self._eof = False
        self.dropped = 0

    def expect(self, rid: int) -> None:
        with self._cv:
            self._expected.add(rid)

    def stop_expecting(self, rid: int) -> None:
        with self._cv:
            self._expected.discard(rid)

    def _is_expected_reply(self, line: str) -> bool:
        # Total by construction: this runs on the reader thread, where a raise loses the pipe.
        if not self._expected or '"id"' not in line:
            return False
        try:
            msg = json.loads(line)
        except (ValueError, RecursionError):
            return False
        if not isinstance(msg, dict):
            return False
        rid = msg.get("id")
        # Request ids are the ints this client issues; a list or dict id is not even hashable.
        return isinstance(rid, int) and rid in self._expected

    def put(self, line: str) -> None:
        with self._cv:
            if self._is_expected_reply(line):
                # Never evicted, and newest first if it must be: losing an awaited reply
                # reports a tool that ran as failed and invites the caller to run it again.
                if len(self._replies) < _REPLY_BUFFER_LINES:
                    self._replies.append(line)
                else:
                    self.dropped += 1
            else:
                if len(self._lines) == self._lines.maxlen:
                    self.dropped += 1
                self._lines.append(line)
            self._cv.notify()

    def close(self) -> None:
        with self._cv:
            self._eof = True
            self._cv.notify_all()

    def pending(self) -> int:
        with self._cv:
            return len(self._lines) + len(self._replies)

    def get(self, timeout: float) -> str | None:
        """Next line, or None once the pipe is closed for good; raises queue.Empty on timeout."""
        deadline = time.monotonic() + timeout
        with self._cv:
            while not self._replies and not self._lines:
                if self._eof:
                    return None
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise queue.Empty
                self._cv.wait(remaining)
            return self._replies.popleft() if self._replies else self._lines.popleft()


class MCPError(Exception):
    """Any failure the caller should surface — spawn, handshake, RPC."""


@dataclass
class ToolSpec:
    """MCP tool metadata as returned by ``tools/list``."""
    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)


class MCPClient:
    """Sync client for one MCP server over stdio."""

    def __init__(
        self, name: str, command: str, args: list[str] | None = None,
        env: dict[str, str] | None = None,
        env_base: dict[str, str] | None = None,
    ) -> None:
        self.name = name
        self.command = command
        self.args = list(args or [])
        self._env_spec = dict(env or {})
        self._env_base = env_base
        self._proc: subprocess.Popen | None = None
        self._req_id = 0
        self._lock = threading.Lock()
        self._tools: list[ToolSpec] = []
        # Buffer stderr so handshake failures can surface the real error.
        self._stderr_buf: list[str] = []
        self._stderr_lock = threading.Lock()
        # A reader thread owns the blocking readline so _wait_for can hold a real deadline.
        self._lines = _LineBuffer()

    def start(self, timeout: float = 45.0) -> None:
        """Spawn the subprocess, handshake, cache the tool list."""
        if self._proc is not None:
            return
        env = _build_env(self._env_spec, self._env_base)
        # A fresh buffer per spawn: a restart must not inherit the previous pipe's EOF.
        self._lines = _LineBuffer()
        try:
            self._proc = subprocess.Popen(
                [self.command, *self.args],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                text=True,
                bufsize=1,
                # Own process group: an `npx` server is a wrapper chain, and stop() must reach the real server, not just the wrapper.
                start_new_session=True,
            )
        except FileNotFoundError as e:
            raise MCPError(
                f"{self.name}: command not found ({self.command}). "
                f"Install the server first (e.g. `npm i -g @some/pkg`) "
                f"or check the path."
            ) from e
        except OSError as e:
            raise MCPError(f"{self.name}: spawn failed: {e}") from e

        # Drain both pipes in the background so chatty servers don't block.
        threading.Thread(
            target=self._drain_stderr, daemon=True,
        ).start()
        threading.Thread(
            target=self._drain_stdout, args=(self._proc, self._lines), daemon=True,
        ).start()

        try:
            self._handshake(timeout=timeout)
            self._tools = self._fetch_tools(timeout=timeout)
        except MCPError:
            self.stop()
            raise

    def stop(self) -> None:
        proc = self._proc
        if proc is None:
            return
        try:
            _stop_process_group(proc)
        except Exception:  # noqa: BLE001
            pass
        self._proc = None

    def is_running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def list_tools(self) -> list[ToolSpec]:
        return list(self._tools)

    def call_tool(self, tool_name: str, arguments: dict,
                  timeout: float = 60.0) -> dict[str, Any]:
        """Invoke ``tool_name`` with ``arguments``. Returns the MCP result"""
        if not self.is_running():
            raise MCPError(f"{self.name}: server is not running")
        resp = self._request(
            "tools/call",
            {"name": tool_name, "arguments": arguments or {}},
            timeout=timeout,
        )
        return resp  # tools/call result is the MCP CallToolResult directly

    def _handshake(self, timeout: float) -> None:
        self._request(
            "initialize",
            {
                "protocolVersion": _PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "clientInfo": _CLIENT_INFO,
            },
            timeout=timeout,
        )
        # MCP expects notifications/initialized right after initialize.
        self._notify("notifications/initialized", {})

    def _fetch_tools(self, timeout: float) -> list[ToolSpec]:
        from alpi.tools._guards import scan_injection
        resp = self._request("tools/list", {}, timeout=timeout)
        tools = []
        for t in resp.get("tools", []):
            description = t.get("description", "") or ""
            warning = scan_injection(description)
            if warning:
                description = f"[external MCP description; {warning}]\n\n{description}"
            tools.append(ToolSpec(
                name=t.get("name", ""),
                description=description,
                input_schema=t.get("inputSchema", {}) or {},
            ))
        return tools

    def _request(self, method: str, params: dict, timeout: float) -> dict:
        with self._lock:
            self._req_id += 1
            rid = self._req_id
            buf = self._lines
            # Registered before the send: a reply can land before _wait_for is even reached.
            buf.expect(rid)
            try:
                self._send({
                    "jsonrpc": "2.0", "id": rid,
                    "method": method, "params": params,
                })
                return self._wait_for(rid, timeout=timeout)
            finally:
                buf.stop_expecting(rid)

    def _notify(self, method: str, params: dict) -> None:
        self._send({
            "jsonrpc": "2.0", "method": method, "params": params,
        })

    def _send(self, obj: dict) -> None:
        # Under the caller's lock: another turn's timeout can stop a client after is_running().
        proc = self._proc
        if proc is None or proc.stdin is None:
            raise MCPError(f"{self.name}: server is not running")
        try:
            proc.stdin.write(json.dumps(obj) + "\n")
            proc.stdin.flush()
        except (BrokenPipeError, OSError) as e:
            raise MCPError(f"{self.name}: stdin write failed: {e}") from e

    def _wait_for(self, rid: int, timeout: float) -> dict:
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                # A server silent past its deadline will not come back: never leave it wedged.
                self.stop()
                raise MCPError(self._wrap_failure(
                    f"timeout waiting for response to id {rid} "
                    f"(waited {timeout:.0f}s)"
                ))
            try:
                line = self._lines.get(timeout=remaining)
            except queue.Empty:
                continue
            if line is None:
                # Let the stderr drainer flush the last error lines.
                time.sleep(0.2)
                raise MCPError(self._wrap_failure("server closed stdout"))
            try:
                msg = json.loads(line.strip())
            except json.JSONDecodeError:
                log.debug("%s: dropping non-json line: %r", self.name, line)
                continue
            if msg.get("id") != rid:
                continue
            if "error" in msg:
                err = msg["error"]
                raise MCPError(
                    f"{self.name}: {method_from_error(err)}: "
                    f"{err.get('message', 'unknown error')}"
                )
            return msg.get("result", {})

    def _wrap_failure(self, reason: str) -> str:
        base = f"{self.name}: {reason}"
        if self._lines.dropped:
            base += f" ({self._lines.dropped} unread lines dropped from the read buffer)"
        tail = self._stderr_tail()
        if tail:
            return f"{base}\nServer stderr:\n{tail}"
        return base + " (server wrote nothing to stderr)"

    def _drain_stdout(self, proc: subprocess.Popen, buf: _LineBuffer) -> None:
        # proc and buf are passed in: stop() nulls self._proc and a restart swaps the buffer.
        if proc.stdout is None:
            buf.close()
            return
        stdout = proc.stdout
        while True:
            try:
                line = stdout.readline()
            except (ValueError, OSError):
                line = ""
            if not line:
                buf.close()
                return
            buf.put(line)

    def _drain_stderr(self) -> None:
        # Capture once: stop() may null self._proc while this loop is running.
        proc = self._proc
        if proc is None or proc.stderr is None:
            return
        stderr = proc.stderr
        while True:
            try:
                line = stderr.readline()
            except (ValueError, OSError):
                return
            if not line:
                return
            log.debug("%s (stderr): %s", self.name, line.rstrip())
            with self._stderr_lock:
                self._stderr_buf.append(line.rstrip())
                if len(self._stderr_buf) > 40:
                    self._stderr_buf = self._stderr_buf[-40:]

    def _stderr_tail(self) -> str:
        with self._stderr_lock:
            # Trim empties and keep the last few lines.
            lines = [ln for ln in self._stderr_buf[-10:] if ln.strip()]
            return "\n".join(lines)



_STOP_GRACE_SECONDS = 3.0
_STOP_TERM_GRACE_SECONDS = 1.0


def _stop_process_group(proc: subprocess.Popen) -> None:
    # A reaped pid may already belong to another group (bpo-38630): never signal it.
    if proc.poll() is not None:
        return
    if proc.stdin is not None:
        try:
            proc.stdin.close()
        except (OSError, ValueError):
            pass
    try:
        proc.wait(timeout=_STOP_GRACE_SECONDS)
        return
    except subprocess.TimeoutExpired:
        pass
    pgid = proc.pid
    try:
        os.killpg(pgid, signal.SIGTERM)
    except OSError:
        pass
    # Never wait on group existence: unreaped zombies keep the group alive, so the SIGTERM grace is a fixed bounded sleep.
    deadline = time.monotonic() + _STOP_TERM_GRACE_SECONDS
    try:
        proc.wait(timeout=_STOP_TERM_GRACE_SECONDS)
    except subprocess.TimeoutExpired:
        pass
    remaining = deadline - time.monotonic()
    if remaining > 0:
        time.sleep(remaining)
    try:
        os.killpg(pgid, signal.SIGKILL)
    except OSError:
        pass
    try:
        proc.wait(timeout=1.0)
    except subprocess.TimeoutExpired:
        pass


_SAFE_ENV_KEYS = (
    "PATH", "HOME", "USER", "LOGNAME", "SHELL",
    "LANG", "LC_ALL", "LC_CTYPE", "TERM", "TZ",
    "PWD", "TMPDIR",
)


def _augmented_path() -> str:
    """PATH the daemon should pass to MCP subprocesses.

    launchd / systemd give the daemon a minimal PATH (``/usr/bin:/bin:…``)
    that misses where users install Node / Python / Rust toolchains. MCP
    servers are typically spawned via ``npx``, ``uvx``, ``python`` —
    so without this augmentation, ``mcp: <name> failed to start: command
    not found`` is the common failure when alpi runs as a launchd-started
    daemon (desktop client path) but works fine when alpi runs from the
    user's shell (TUI path).

    Prepends user-tool locations that actually exist on disk; preserves
    the inherited PATH after them so existing entries still win on
    duplicate names.
    """
    import glob
    extras: list[str] = []

    # Node version managers — nvm publishes per-version bins; volta a single one.
    for nvm_bin in sorted(
        glob.glob(os.path.expanduser("~/.nvm/versions/node/*/bin")),
        reverse=True,
    ):
        if os.path.isdir(nvm_bin):
            extras.append(nvm_bin)
    volta = os.path.expanduser("~/.volta/bin")
    if os.path.isdir(volta):
        extras.append(volta)

    # System package managers.
    for path in (
        "/opt/homebrew/bin",   # mac arm
        "/opt/homebrew/sbin",
        "/usr/local/bin",      # mac intel + generic
        "/usr/local/sbin",
        "/snap/bin",           # linux snap
    ):
        if os.path.isdir(path):
            extras.append(path)

    # User-local tool stores (uv, pipx, cargo, bun, deno).
    for path in ("~/.local/bin", "~/.cargo/bin", "~/.bun/bin", "~/.deno/bin"):
        expanded = os.path.expanduser(path)
        if os.path.isdir(expanded):
            extras.append(expanded)

    inherited = os.environ.get("PATH", "")
    if not extras:
        return inherited
    return ":".join([*extras, inherited]) if inherited else ":".join(extras)


def _build_env(
    spec: dict[str, str], base: dict[str, str] | None = None,
) -> dict[str, str]:
    parent = os.environ
    lookup = base if base is not None else parent
    out: dict[str, str] = {}
    for key in _SAFE_ENV_KEYS:
        if key in parent:
            out[key] = parent[key]
    # PATH gets augmented separately so launchd-started daemons can find
    # `npx` / `uvx` / etc that MCP servers need to spawn.
    out["PATH"] = _augmented_path()
    for key in parent:
        if key.startswith("LC_") and key not in out:
            out[key] = parent[key]
    for key, value in spec.items():
        if isinstance(value, str) and value.startswith("env:"):
            ref = value[len("env:"):]
            resolved = lookup.get(ref, "")
            if not resolved:
                log.warning(
                    "mcp: %s references env:%s but it's empty/unset",
                    key, ref,
                )
            out[key] = resolved
        else:
            out[key] = str(value)
    return out


def method_from_error(err: dict) -> str:
    code = err.get("code", "")
    return f"rpc error {code}" if code else "rpc error"
