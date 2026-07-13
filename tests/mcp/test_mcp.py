"""Tests for the MCP subsystem — client, registry, tool wrapping.

We don't spawn real MCP servers. Instead, ``MCPClient`` is exercised
against a fake subprocess that speaks JSON-RPC via a pair of
``io.StringIO``-backed streams. That covers:

- Handshake (initialize → initialized → tools/list)
- tools/call with results + errors
- JSON-RPC error propagation
- Env-var ``env:VAR_NAME`` expansion
- Registry: config → spawned clients → wrapped Tool subclasses
  appearing in the shared registry with ``<server>:<tool>`` names
"""

from __future__ import annotations

import io
import json
import os
import threading
from pathlib import Path
from typing import Any

import pytest

from alpi.mcp import client as mcp_client
from alpi.mcp import registry as mcp_registry
from alpi.tools import _TOOLS


# --------------------------------------------------------------------
# Fake subprocess — just enough to pretend we're a well-behaved MCP
# --------------------------------------------------------------------


class _FakeServer:
    """Scripted MCP server. Responds to each request by looking up the
    method in ``self.handlers`` and returning its output as JSON on
    stdout."""

    def __init__(self) -> None:
        self.handlers: dict[str, Any] = {}
        # Pipes: we write responses to _stdout_buf, client reads them.
        # Client writes requests to _stdin_buf, our "server loop" reads.
        self._requests: list[dict] = []
        self._stdout_lines: list[str] = []
        self._lock = threading.Lock()

    def handle(self, method: str, result: Any) -> None:
        self.handlers[method] = result

    def on_request(self, req: dict) -> dict | None:
        self._requests.append(req)
        method = req.get("method", "")
        if "id" not in req:
            # Notification — no response.
            return None
        handler = self.handlers.get(method)
        if handler is None:
            return {
                "jsonrpc": "2.0", "id": req["id"],
                "error": {"code": -32601, "message": f"method {method!r} not found"},
            }
        if callable(handler):
            result = handler(req.get("params") or {})
        else:
            result = handler
        if isinstance(result, dict) and result.get("__error__"):
            return {
                "jsonrpc": "2.0", "id": req["id"],
                "error": {"code": -1, "message": result.get("message", "boom")},
            }
        return {
            "jsonrpc": "2.0", "id": req["id"], "result": result,
        }


class _FakePopen:
    """Stand-in for subprocess.Popen: stdin/stdout are in-memory
    line-oriented streams; each write from the client gets picked up
    by the fake server, which writes the response to the stdout
    buffer synchronously."""

    def __init__(self, server: _FakeServer) -> None:
        self._server = server
        self._stdin = _BufferedStdin(server, self._on_request)
        self._stdout = _BufferedStdout()
        self._stderr = io.StringIO()
        self.returncode: int | None = None

    @property
    def stdin(self):
        return self._stdin

    @property
    def stdout(self):
        return self._stdout

    @property
    def stderr(self):
        return self._stderr

    def _on_request(self, req: dict) -> None:
        resp = self._server.on_request(req)
        if resp is not None:
            self._stdout.push(json.dumps(resp) + "\n")

    def poll(self):
        return self.returncode

    def terminate(self):
        self.returncode = 0

    def kill(self):
        self.returncode = -9

    def wait(self, timeout=None):
        return self.returncode or 0


class _BufferedStdin:
    def __init__(self, server: _FakeServer, on_request) -> None:
        self._server = server
        self._on_request = on_request
        self._buf = ""

    def write(self, data: str) -> int:
        self._buf += data
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            if line.strip():
                try:
                    req = json.loads(line)
                except json.JSONDecodeError:
                    continue
                self._on_request(req)
        return len(data)

    def flush(self):
        pass


class _BufferedStdout:
    def __init__(self) -> None:
        self._queue: list[str] = []
        self._lock = threading.Lock()

    def push(self, s: str) -> None:
        with self._lock:
            self._queue.append(s)

    def readline(self) -> str:
        # Blocks until data is available — in our synchronous tests,
        # the server writes before the client reads, so this always
        # returns immediately.
        with self._lock:
            if self._queue:
                return self._queue.pop(0)
        return ""


@pytest.fixture
def server_and_patch(monkeypatch):
    server = _FakeServer()
    server.handle("initialize", {"protocolVersion": "2024-11-05"})

    def factory(args, stdin=None, stdout=None, stderr=None, env=None, text=None, bufsize=None):
        return _FakePopen(server)

    monkeypatch.setattr(mcp_client.subprocess, "Popen", factory)
    return server


# --------------------------------------------------------------------
# Client: handshake + tools/list + tools/call
# --------------------------------------------------------------------


def test_start_performs_handshake_and_lists_tools(server_and_patch) -> None:
    server = server_and_patch
    server.handle("tools/list", {
        "tools": [
            {"name": "create_issue", "description": "Create a GitHub issue",
             "inputSchema": {"type": "object", "properties": {"title": {"type": "string"}}}},
            {"name": "list_prs", "description": "List open PRs"},
        ],
    })
    c = mcp_client.MCPClient("github", "echo")
    c.start()
    try:
        assert c.is_running()
        tools = c.list_tools()
        assert [t.name for t in tools] == ["create_issue", "list_prs"]
        assert tools[0].description == "Create a GitHub issue"
        assert tools[0].input_schema["properties"]["title"]["type"] == "string"
    finally:
        c.stop()


def test_call_tool_returns_content(server_and_patch) -> None:
    server = server_and_patch
    server.handle("tools/list", {"tools": [{"name": "ping", "description": ""}]})
    server.handle("tools/call", {
        "content": [{"type": "text", "text": "pong"}],
        "isError": False,
    })
    c = mcp_client.MCPClient("x", "echo")
    c.start()
    try:
        result = c.call_tool("ping", {})
        assert result["content"][0]["text"] == "pong"
        assert result.get("isError") is False
    finally:
        c.stop()


def test_rpc_error_raises_mcp_error(server_and_patch) -> None:
    server = server_and_patch
    server.handle("tools/list", {"tools": []})
    server.handle("tools/call", {"__error__": True, "message": "bad args"})
    c = mcp_client.MCPClient("x", "echo")
    c.start()
    try:
        with pytest.raises(mcp_client.MCPError, match="bad args"):
            c.call_tool("ping", {})
    finally:
        c.stop()


def test_missing_command_raises_clean_error(monkeypatch) -> None:
    def failing(*a, **kw):
        raise FileNotFoundError(2, "no such file")

    monkeypatch.setattr(mcp_client.subprocess, "Popen", failing)
    c = mcp_client.MCPClient("nope", "doesntexist")
    with pytest.raises(mcp_client.MCPError, match="command not found"):
        c.start()


# --------------------------------------------------------------------
# Env expansion
# --------------------------------------------------------------------


def test_env_ref_resolves_from_os_environ(monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_xxx")
    env = mcp_client._build_env({"GITHUB_TOKEN": "env:GITHUB_TOKEN"})
    assert env["GITHUB_TOKEN"] == "ghp_xxx"


def test_env_ref_unresolved_falls_back_to_empty(monkeypatch) -> None:
    monkeypatch.delenv("GHOST", raising=False)
    env = mcp_client._build_env({"GHOST": "env:GHOST"})
    assert env["GHOST"] == ""


def test_env_ref_resolves_from_profile_base_not_os_environ(monkeypatch) -> None:
    monkeypatch.delenv("BITBUCKET_URL", raising=False)
    env = mcp_client._build_env(
        {"BITBUCKET_URL": "env:BITBUCKET_URL"},
        base={"BITBUCKET_URL": "https://api.bitbucket.org/2.0"},
    )
    assert env["BITBUCKET_URL"] == "https://api.bitbucket.org/2.0"


def test_env_ref_base_takes_precedence_over_os_environ(monkeypatch) -> None:
    monkeypatch.setenv("TOKEN", "from-process")
    env = mcp_client._build_env(
        {"TOKEN": "env:TOKEN"}, base={"TOKEN": "from-profile"},
    )
    assert env["TOKEN"] == "from-profile"


def test_client_passes_env_base_to_resolution(monkeypatch) -> None:
    monkeypatch.delenv("BITBUCKET_PASSWORD", raising=False)
    client = mcp_client.MCPClient(
        name="bb", command="true",
        env={"BITBUCKET_PASSWORD": "env:BITBUCKET_PASSWORD"},
        env_base={"BITBUCKET_PASSWORD": "app-pw"},
    )
    resolved = mcp_client._build_env(client._env_spec, client._env_base)
    assert resolved["BITBUCKET_PASSWORD"] == "app-pw"


def test_literal_env_value_passes_through() -> None:
    env = mcp_client._build_env({"FOO": "literal"})
    assert env["FOO"] == "literal"


def test_undeclared_secrets_do_not_leak(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-secret")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "1234:abc")
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    env = mcp_client._build_env({"FOO": "literal"})
    assert "OPENAI_API_KEY" not in env
    assert "TELEGRAM_BOT_TOKEN" not in env
    # PATH is augmented (see _augmented_path); inherited PATH must still be
    # present somewhere in the result so original entries keep resolving.
    assert "/usr/bin:/bin" in env.get("PATH", "")


def test_safelist_keys_pass_through(monkeypatch) -> None:
    monkeypatch.setenv("HOME", "/tmp/h")
    monkeypatch.setenv("LANG", "en_US.UTF-8")
    env = mcp_client._build_env({})
    assert env.get("HOME") == "/tmp/h"
    assert env.get("LANG") == "en_US.UTF-8"


# --------------------------------------------------------------------
# PATH augmentation — daemons spawned by launchd / systemd inherit a
# minimal PATH that misses where users install Node / Python / Rust
# tools. _augmented_path() prepends user-tool locations that exist on
# disk so MCP servers (npx / uvx / …) can spawn from the daemon path.
# --------------------------------------------------------------------


def test_augmented_path_preserves_inherited(monkeypatch) -> None:
    """The daemon's PATH still appears in the augmented result."""
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    out = mcp_client._augmented_path()
    assert "/usr/bin:/bin" in out


def test_augmented_path_handles_empty_inherited(monkeypatch) -> None:
    """No inherited PATH still yields a non-empty augmented value if any
    user-tool dir exists on the host (otherwise empty string is fine)."""
    monkeypatch.delenv("PATH", raising=False)
    out = mcp_client._augmented_path()
    assert isinstance(out, str)


def test_augmented_path_only_includes_existing_dirs(monkeypatch, tmp_path) -> None:
    """Non-existent dirs are skipped; existing user-tool dirs land first."""
    fake_home = tmp_path
    real_local = fake_home / ".local" / "bin"; real_local.mkdir(parents=True)
    real_cargo = fake_home / ".cargo" / "bin"; real_cargo.mkdir(parents=True)

    real_expanduser = os.path.expanduser

    def fake_expanduser(p):
        if p.startswith("~/"):
            return str(fake_home / p[2:])
        return real_expanduser(p)

    monkeypatch.setattr(os.path, "expanduser", fake_expanduser)
    monkeypatch.setenv("PATH", "/usr/bin")

    out = mcp_client._augmented_path()
    parts = out.split(":")

    # Existing user dirs are present.
    assert str(real_local) in parts
    assert str(real_cargo) in parts
    # Non-existent paths are NOT.
    assert str(fake_home / ".bun" / "bin") not in parts
    assert str(fake_home / ".deno" / "bin") not in parts
    # User dirs precede inherited PATH so they win on duplicate names.
    assert parts.index(str(real_local)) < parts.index("/usr/bin")


def test_build_env_uses_augmented_path(monkeypatch) -> None:
    """_build_env replaces inherited PATH with the augmented one so MCP
    subprocesses spawned by a launchd-started daemon can find user tools."""
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    env = mcp_client._build_env({})
    # _augmented_path always returns at least the inherited PATH.
    assert env["PATH"] != ""
    assert "/usr/bin:/bin" in env["PATH"]


# --------------------------------------------------------------------
# Registry: config → tools registered with <server>:<tool> names
# --------------------------------------------------------------------


class _FakeConfig:
    def __init__(self, raw: dict, home: Path | None = None) -> None:
        self.raw = raw
        self.home = home or Path("/nonexistent-profile")


def test_registry_registers_prefixed_tools(server_and_patch) -> None:
    server = server_and_patch
    server.handle("tools/list", {
        "tools": [
            {"name": "create_issue", "description": "Create an issue",
             "inputSchema": {"type": "object", "properties": {}}},
        ],
    })
    cfg = _FakeConfig({
        "mcp": {"servers": {
            "github": {"command": "echo", "args": [], "env": {}},
        }},
    })
    clients = mcp_registry.load_and_register(cfg)
    try:
        assert "github__create_issue" in _TOOLS
        cls = _TOOLS["github__create_issue"]
        assert cls.description.startswith("Create an issue")
        # Description picks up the untrusted-content caveat.
        assert "CRITICAL" in cls.description
    finally:
        for c in clients:
            c.stop()
        mcp_registry._stop_existing()


def test_wrapped_tool_calls_delegates_to_client(server_and_patch) -> None:
    server = server_and_patch
    server.handle("tools/list", {"tools": [{"name": "ping", "description": ""}]})
    server.handle("tools/call", {
        "content": [{"type": "text", "text": "pong"}],
    })
    cfg = _FakeConfig({
        "mcp": {"servers": {"x": {"command": "echo"}}},
    })
    clients = mcp_registry.load_and_register(cfg)
    try:
        tool_cls = _TOOLS["x__ping"]
        result = tool_cls().run(arg1="foo")
        assert result.ok is True
        assert result.output == "pong"
    finally:
        for c in clients:
            c.stop()
        mcp_registry._stop_existing()


def test_wrapped_tool_falls_back_to_structured_content(server_and_patch) -> None:
    server = server_and_patch
    server.handle("tools/list", {"tools": [{"name": "lookup", "description": ""}]})
    server.handle("tools/call", {
        "content": [],
        "structuredContent": {"city": "Lisbon", "temp_c": 21},
        "isError": False,
    })
    cfg = _FakeConfig({"mcp": {"servers": {"x": {"command": "echo"}}}})
    clients = mcp_registry.load_and_register(cfg)
    try:
        result = _TOOLS["x__lookup"]().run()
        assert result.ok is True
        assert json.loads(result.output) == {"city": "Lisbon", "temp_c": 21}
    finally:
        for c in clients:
            c.stop()
        mcp_registry._stop_existing()


def test_structured_content_survives_non_text_blocks(server_and_patch) -> None:
    server = server_and_patch
    server.handle("tools/list", {"tools": [{"name": "scan", "description": ""}]})
    server.handle("tools/call", {
        "content": [{"type": "image", "data": "abc", "mimeType": "image/png"}],
        "structuredContent": {"objects": ["invoice", "total"]},
        "isError": False,
    })
    cfg = _FakeConfig({"mcp": {"servers": {"x": {"command": "echo"}}}})
    clients = mcp_registry.load_and_register(cfg)
    try:
        result = _TOOLS["x__scan"]().run()
        assert result.ok is True
        assert "[image content omitted]" in result.output
        assert json.loads(result.output.split("\n", 1)[1]) == {"objects": ["invoice", "total"]}
    finally:
        for c in clients:
            c.stop()
        mcp_registry._stop_existing()


def test_real_text_suppresses_structured_duplicate(server_and_patch) -> None:
    server = server_and_patch
    server.handle("tools/list", {"tools": [{"name": "echo", "description": ""}]})
    server.handle("tools/call", {
        "content": [{"type": "text", "text": "pong"}],
        "structuredContent": {"reply": "pong"},
        "isError": False,
    })
    cfg = _FakeConfig({"mcp": {"servers": {"x": {"command": "echo"}}}})
    clients = mcp_registry.load_and_register(cfg)
    try:
        result = _TOOLS["x__echo"]().run()
        assert result.output == "pong"
    finally:
        for c in clients:
            c.stop()
        mcp_registry._stop_existing()


def test_load_and_register_resolves_env_from_profile_dotenv(
    monkeypatch, tmp_path,
) -> None:
    """End-to-end: a server's env:VAR ref resolves from the profile's own
    .env (never loaded into os.environ) and reaches the spawned subprocess."""
    monkeypatch.delenv("BITBUCKET_TOKEN", raising=False)
    (tmp_path / ".env").write_text('BITBUCKET_TOKEN="secret-from-profile"\n')

    server = _FakeServer()
    server.handle("initialize", {"protocolVersion": "2024-11-05"})
    server.handle("tools/list", {"tools": [{"name": "list_prs", "description": ""}]})

    captured: dict[str, dict] = {}

    def factory(args, env=None, **kw):
        captured["env"] = env
        return _FakePopen(server)

    monkeypatch.setattr(mcp_client.subprocess, "Popen", factory)
    cfg = _FakeConfig(
        {"mcp": {"servers": {"bb": {
            "command": "echo",
            "env": {"BITBUCKET_TOKEN": "env:BITBUCKET_TOKEN"},
        }}}},
        home=tmp_path,
    )
    clients = mcp_registry.load_and_register(cfg)
    try:
        assert captured["env"]["BITBUCKET_TOKEN"] == "secret-from-profile"
        assert "bb__list_prs" in _TOOLS
    finally:
        for c in clients:
            c.stop()
        mcp_registry._stop_existing()


def test_registry_isolates_failing_server(monkeypatch) -> None:
    """A server that fails to start must not abort the rest."""
    # First server fails (FileNotFound), second succeeds.
    working_server = _FakeServer()
    working_server.handle("initialize", {"protocolVersion": "2024-11-05"})
    working_server.handle("tools/list", {"tools": [{"name": "ok", "description": ""}]})

    class _Factory:
        def __init__(self) -> None:
            self.calls = 0

        def __call__(self, args, **kw):
            self.calls += 1
            if self.calls == 1:
                raise FileNotFoundError(2, "boom")
            return _FakePopen(working_server)

    monkeypatch.setattr(mcp_client.subprocess, "Popen", _Factory())
    cfg = _FakeConfig({
        "mcp": {"servers": {
            "broken": {"command": "missing"},
            "works":  {"command": "echo"},
        }},
    })
    clients = mcp_registry.load_and_register(cfg)
    try:
        names = [c.name for c in clients]
        assert names == ["works"]
        assert "works__ok" in _TOOLS
        assert "broken__ok" not in _TOOLS
    finally:
        for c in clients:
            c.stop()
        mcp_registry._stop_existing()


def test_drain_stderr_survives_proc_nulled_mid_loop() -> None:
    c = mcp_client.MCPClient("x", "echo")
    lines = iter(["first\n", "second\n", ""])
    seen = {"calls": 0}

    class _Stderr:
        def readline(self) -> str:
            seen["calls"] += 1
            if seen["calls"] == 1:
                c._proc = None
            return next(lines)

    class _Proc:
        stderr = _Stderr()

    c._proc = _Proc()
    c._drain_stderr()
    assert seen["calls"] == 3
    assert "first" in c._stderr_buf and "second" in c._stderr_buf


def test_drain_stderr_returns_when_readline_raises_oserror() -> None:
    c = mcp_client.MCPClient("x", "echo")

    class _Stderr:
        def readline(self) -> str:
            raise OSError("stream closed by stop()")

    class _Proc:
        stderr = _Stderr()

    c._proc = _Proc()
    c._drain_stderr()
    assert c._stderr_buf == []


# --------------------------------------------------------------------
# Content rendering
# --------------------------------------------------------------------


def test_render_content_collapses_text_blocks() -> None:
    out = mcp_registry._render_content([
        {"type": "text", "text": "a"},
        {"type": "text", "text": "b"},
    ])
    assert out == "a\nb"


def test_render_content_marks_non_text_blocks() -> None:
    out = mcp_registry._render_content([
        {"type": "text", "text": "see attachment:"},
        {"type": "image", "data": "..."},
    ])
    assert "see attachment:" in out
    assert "image" in out.lower()


def test_render_content_handles_empty() -> None:
    assert mcp_registry._render_content([]) == ""


# --------------------------------------------------------------------
# Config default
# --------------------------------------------------------------------


def test_config_default_has_empty_mcp_servers(tmp_home_no_env: Path) -> None:
    from alpi import config
    cfg = config.load(tmp_home_no_env)
    assert cfg.raw.get("mcp", {}).get("servers", {}) == {}
