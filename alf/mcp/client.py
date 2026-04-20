"""MCPClient — stdio JSON-RPC client for MCP servers.

One client per configured server. Lifecycle:

    c = MCPClient(name="github", command="npx", args=["-y", "..."])
    c.start()               # spawn subprocess, handshake, list tools
    c.list_tools()          # -> list of tool schemas
    c.call_tool(name, args) # -> {"content": [...], "isError": bool}
    c.stop()                # SIGTERM the subprocess

Only stdio transport in v0 — covers the bulk of the MCP ecosystem.
SSE/HTTP can land later if we meet a server that needs it.

Protocol: JSON-RPC 2.0 over line-delimited stdin/stdout. Every
request gets an id, every response matches by id. Notifications
(no id) are ignored for our purposes — we don't surface server-
emitted events (progress updates, log lines) since the agent
loop is synchronous and one-shot per tool call.

Env-var references in the config (``env:GITHUB_TOKEN``) are
expanded at ``start()`` against the current process env. Missing
values are logged but not fatal — the MCP server itself will
complain with an actionable error if it really needs the key.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("alf.mcp")

# Handshake. We speak the November 2024 spec; most servers still
# accept older/newer versions and negotiate.
_PROTOCOL_VERSION = "2024-11-05"
_CLIENT_INFO = {"name": "alf", "version": "0.2"}


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
    ) -> None:
        self.name = name
        self.command = command
        self.args = list(args or [])
        # Preserve the env spec verbatim — expansion happens at start()
        # so re-starts pick up ``.env`` changes without needing to
        # reconstruct the client.
        self._env_spec = dict(env or {})
        self._proc: subprocess.Popen | None = None
        self._req_id = 0
        self._lock = threading.Lock()
        self._tools: list[ToolSpec] = []
        # stderr of the subprocess is captured here so handshake failures
        # ("server closed stdout") can surface what the server actually
        # said before dying. Keeps the background drainer light.
        self._stderr_buf: list[str] = []
        self._stderr_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self, timeout: float = 45.0) -> None:
        """Spawn the subprocess, handshake, cache the tool list."""
        if self._proc is not None:
            return
        env = _build_env(self._env_spec)
        try:
            self._proc = subprocess.Popen(
                [self.command, *self.args],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                text=True,
                bufsize=1,
            )
        except FileNotFoundError as e:
            raise MCPError(
                f"{self.name}: command not found ({self.command}). "
                f"Install the server first (e.g. `npm i -g @some/pkg`) "
                f"or check the path."
            ) from e
        except OSError as e:
            raise MCPError(f"{self.name}: spawn failed: {e}") from e

        # Drain stderr in the background so a chatty server can't fill
        # the pipe and block the subprocess on a write. stderr lines go
        # to our own log at debug level — useful when a handshake fails.
        threading.Thread(
            target=self._drain_stderr, daemon=True,
        ).start()

        try:
            self._handshake(timeout=timeout)
            self._tools = self._fetch_tools(timeout=timeout)
        except MCPError:
            self.stop()
            raise

    def stop(self) -> None:
        if self._proc is None:
            return
        try:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=3.0)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        except Exception:  # noqa: BLE001
            pass
        self._proc = None

    def is_running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def list_tools(self) -> list[ToolSpec]:
        return list(self._tools)

    def call_tool(self, tool_name: str, arguments: dict,
                  timeout: float = 60.0) -> dict[str, Any]:
        """Invoke ``tool_name`` with ``arguments``. Returns the MCP result
        object verbatim: ``{"content": [...], "isError": bool?}``.
        """
        if not self.is_running():
            raise MCPError(f"{self.name}: server is not running")
        resp = self._request(
            "tools/call",
            {"name": tool_name, "arguments": arguments or {}},
            timeout=timeout,
        )
        return resp  # tools/call result is the MCP CallToolResult directly

    # ------------------------------------------------------------------
    # Handshake
    # ------------------------------------------------------------------

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
        # Per spec, the client sends a notifications/initialized right
        # after initialize returns.
        self._notify("notifications/initialized", {})

    def _fetch_tools(self, timeout: float) -> list[ToolSpec]:
        resp = self._request("tools/list", {}, timeout=timeout)
        tools = []
        for t in resp.get("tools", []):
            tools.append(ToolSpec(
                name=t.get("name", ""),
                description=t.get("description", ""),
                input_schema=t.get("inputSchema", {}) or {},
            ))
        return tools

    # ------------------------------------------------------------------
    # JSON-RPC
    # ------------------------------------------------------------------

    def _request(self, method: str, params: dict, timeout: float) -> dict:
        with self._lock:
            self._req_id += 1
            rid = self._req_id
            self._send({
                "jsonrpc": "2.0", "id": rid,
                "method": method, "params": params,
            })
            return self._wait_for(rid, timeout=timeout)

    def _notify(self, method: str, params: dict) -> None:
        self._send({
            "jsonrpc": "2.0", "method": method, "params": params,
        })

    def _send(self, obj: dict) -> None:
        assert self._proc is not None and self._proc.stdin is not None
        try:
            self._proc.stdin.write(json.dumps(obj) + "\n")
            self._proc.stdin.flush()
        except (BrokenPipeError, OSError) as e:
            raise MCPError(f"{self.name}: stdin write failed: {e}") from e

    def _wait_for(self, rid: int, timeout: float) -> dict:
        """Read lines from stdout until we see a response matching rid.

        We swallow notifications (no ``id``) and mismatched responses;
        MCP servers can interleave telemetry we don't care about.
        """
        assert self._proc is not None and self._proc.stdout is not None
        deadline = time.monotonic() + timeout
        while True:
            if time.monotonic() > deadline:
                raise MCPError(self._wrap_failure(
                    f"timeout waiting for response to id {rid} "
                    f"(waited {timeout:.0f}s)"
                ))
            line = self._proc.stdout.readline()
            if not line:
                # Give the stderr drainer a moment to flush any last
                # lines the server wrote before exiting — that's often
                # the actual error message (missing dep, bad args, etc.).
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
        """Build an actionable error message, appending stderr context
        when we have any. Without this the user just saw 'server closed
        stdout' and had no clue what actually went wrong."""
        base = f"{self.name}: {reason}"
        tail = self._stderr_tail()
        if tail:
            return f"{base}\nServer stderr:\n{tail}"
        return base + " (server wrote nothing to stderr)"

    def _drain_stderr(self) -> None:
        if self._proc is None or self._proc.stderr is None:
            return
        while True:
            try:
                line = self._proc.stderr.readline()
            except ValueError:
                return
            if not line:
                return
            log.debug("%s (stderr): %s", self.name, line.rstrip())
            # Keep the last N lines so error messages can show context
            # when the handshake fails. Capped to avoid unbounded growth
            # for chatty servers that spam stderr for telemetry.
            with self._stderr_lock:
                self._stderr_buf.append(line.rstrip())
                if len(self._stderr_buf) > 40:
                    self._stderr_buf = self._stderr_buf[-40:]

    def _stderr_tail(self) -> str:
        with self._stderr_lock:
            # Last ~10 lines, trimmed of empties, joined one per line.
            lines = [ln for ln in self._stderr_buf[-10:] if ln.strip()]
            return "\n".join(lines)


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def _build_env(spec: dict[str, str]) -> dict[str, str]:
    """Expand ``env:VAR_NAME`` placeholders against the current process
    env. Unknown ``env:`` refs resolve to empty strings and log a
    warning; literal values pass through untouched.
    """
    base = dict(os.environ)
    for key, value in spec.items():
        if isinstance(value, str) and value.startswith("env:"):
            ref = value[len("env:"):]
            resolved = os.environ.get(ref, "")
            if not resolved:
                log.warning(
                    "mcp: %s references env:%s but it's empty/unset",
                    key, ref,
                )
            base[key] = resolved
        else:
            base[key] = str(value)
    return base


def method_from_error(err: dict) -> str:
    code = err.get("code", "")
    return f"rpc error {code}" if code else "rpc error"
