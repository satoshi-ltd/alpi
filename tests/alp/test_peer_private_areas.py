from __future__ import annotations

import contextvars
import json
import shutil
import sys
import threading
from pathlib import Path

import pytest

from alpi import tools
from alpi.core.run_context import RunContext
from alpi.core.tool_executor import ToolExecutor
from alpi.core.tool_executor import use as use_executor
from alpi.host.connection_context import ConnectionContext
from alpi.host.connection_context import use as use_connection
from alpi.tools import _policy
from alpi.tools._paths import PEER_HISTORY_TOOLS, private_areas_fenced

SECRET = "PEER-CANNOT-SEE-THIS"
PEER = ConnectionContext(connection_id="peer:carol", source="peer")
SANDBOX = sys.platform.startswith("linux") and shutil.which("bwrap") is not None


@pytest.fixture
def home(tmp_path: Path, monkeypatch) -> Path:
    root = tmp_path / "alpi"
    ws = tmp_path / "ws"
    (root / "sessions").mkdir(parents=True)
    ws.mkdir()
    monkeypatch.setenv("ALPI_HOME", str(root))
    monkeypatch.chdir(ws)
    (root / "config.yaml").write_text(f"workspace: {ws}\n")
    (root / "sessions" / "s1.json").write_text(json.dumps({"text": SECRET}))
    (ws / "notes.md").write_text("public notes")
    return root


def _as_peer(allow):
    return _policy.use(allow, "peer 'carol'", PEER_HISTORY_TOOLS, fence_without_policy=True)


def _text(result) -> str:
    return f"{result.output}{result.error}"


def test_a_peer_without_a_tool_policy_cannot_read_search_or_write_the_private_areas(home: Path) -> None:
    session = home / "sessions" / "s1.json"
    with use_connection(PEER), _as_peer(None):
        assert private_areas_fenced()
        assert SECRET not in _text(tools.execute("read_file", {"path": str(session)}))
        assert SECRET not in _text(tools.execute("search", {"pattern": SECRET, "path": str(home)}))
        assert tools.execute("write_file", {"path": str(home / "sessions" / "x.json"), "content": "{}"}).ok is False
        assert "public notes" in tools.execute("read_file", {"path": str(home.parent / "ws" / "notes.md")}).output
    assert not private_areas_fenced()
    assert SECRET in tools.execute("read_file", {"path": str(session)}).output


def test_a_peer_policy_grants_exactly_what_it_names(home: Path) -> None:
    session = home / "sessions" / "s1.json"
    with use_connection(PEER), _as_peer(frozenset({"read_file"})):
        assert not private_areas_fenced()
        assert SECRET in tools.execute("read_file", {"path": str(session)}).output
        assert tools.execute("search", {"pattern": SECRET, "path": str(home)}).ok is False
    with use_connection(PEER), _as_peer(frozenset()):
        assert tools.execute("read_file", {"path": str(home.parent / "ws" / "notes.md")}).ok is False


def test_the_fence_follows_nested_execution(home: Path) -> None:
    session = str(home / "sessions" / "s1.json")
    context = RunContext("run", home, home.parent / "ws", "default", "peer", "s", "peer:carol")
    with use_connection(PEER), _as_peer(None), use_executor(ToolExecutor(context)):
        result = tools.execute("workflow", {"steps": [{"id": "a", "tool": "read_file", "arguments": {"path": session}}]})
        assert SECRET not in _text(result)
        seen: list[bool] = []
        copied = contextvars.copy_context()
        thread = threading.Thread(target=lambda: seen.append(copied.run(private_areas_fenced)))
        thread.start()
        thread.join()
        assert seen == [True]


@pytest.mark.integration
@pytest.mark.skipif(not SANDBOX, reason="needs bwrap (Linux)")
def test_a_peer_without_a_tool_policy_runs_terminal_only_in_the_sandbox_that_hides_the_home(home: Path) -> None:
    command = f"cat {home.resolve()}/sessions/s1.json; echo done"
    with use_connection(PEER), _as_peer(None):
        result = tools.execute("terminal", {"command": command})
    assert SECRET not in _text(result)
    with use_connection(PEER), _as_peer(frozenset({"terminal"})):
        assert SECRET in tools.execute("terminal", {"command": command}).output


def test_a_peer_without_a_tool_policy_is_refused_terminal_where_no_sandbox_exists(home: Path, monkeypatch) -> None:
    from alpi.tools import _sandbox, terminal

    monkeypatch.setattr(_sandbox.shutil, "which", lambda _name: None)
    monkeypatch.setattr(_sandbox, "sys", type("S", (), {"platform": "linux"})())
    monkeypatch.setattr(terminal.subprocess, "Popen", lambda *a, **kw: pytest.fail("spawned"))
    with use_connection(PEER), _as_peer(None):
        result = tools.execute("terminal", {"command": "true"})
    assert result.ok is False and "peers without a tool policy" in result.error


MEMBER = ConnectionContext(connection_id="c1", device_id="d1", source="remote", role="member")


def test_the_file_fence_sees_every_profile_of_a_custom_root_in_any_case_and_through_symlinks(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "data"
    a = root / "profiles" / "a"
    (a / "sessions").mkdir(parents=True)
    (root / "profiles" / "b" / "sessions").mkdir(parents=True)
    (root / "profiles" / "b" / "sessions" / "s.json").write_text(SECRET)
    elsewhere = tmp_path / "disk" / "c"
    (elsewhere / "runs").mkdir(parents=True)
    (elsewhere / "runs" / "r.jsonl").write_text(SECRET)
    (root / "profiles" / "c").symlink_to(elsewhere)
    (root / "knowledge.sqlite").write_text(SECRET)
    ws = tmp_path / "ws"
    ws.mkdir()
    monkeypatch.setenv("ALPI_HOME", str(a))
    monkeypatch.chdir(ws)
    paths = [
        root / "profiles" / "b" / "sessions" / "s.json",
        root / "profiles" / "b" / "Sessions" / "s.json",
        root / "PROFILES" / "b" / "sessions" / "s.json",
        root / "profiles" / "c" / "runs" / "r.jsonl",
        elsewhere / "runs" / "r.jsonl",
        root / "knowledge.sqlite",
    ]
    with use_connection(MEMBER):
        for path in paths:
            assert SECRET not in _text(tools.execute("read_file", {"path": str(path)})), path
    for path in paths:
        if path.exists():
            assert SECRET in tools.execute("read_file", {"path": str(path)}).output, path


def test_a_fenced_turn_cannot_rewrite_any_profile_config_or_read_alp_secrets_in_any_case(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "data"
    a = root / "profiles" / "a"
    (a / "alp" / "secrets").mkdir(parents=True)
    (a / "alp" / "secrets" / "subscriptions.yaml").write_text(SECRET)
    (root / "profiles" / "b").mkdir(parents=True)
    for home in (root, a, root / "profiles" / "b"):
        (home / "config.yaml").write_text("model: x\n")
    ws = tmp_path / "ws"
    ws.mkdir()
    monkeypatch.setenv("ALPI_HOME", str(a))
    monkeypatch.chdir(ws)
    with use_connection(PEER), _as_peer(None):
        for target in (root / "config.yaml", a / "config.yaml", root / "profiles" / "b" / "config.yaml", a / "CONFIG.yaml"):
            assert tools.execute("write_file", {"path": str(target), "content": "mcp: {}\n"}).ok is False, target
            assert tools.execute("edit_file", {"path": str(target), "old_string": "x", "new_string": "y"}).ok is False, target
        for target in (a / "alp" / "secrets" / "subscriptions.yaml", a / "ALP" / "SECRETS" / "subscriptions.yaml"):
            assert SECRET not in _text(tools.execute("read_file", {"path": str(target)})), target
    assert (a / "config.yaml").read_text() == "model: x\n"
