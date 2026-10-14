from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
import yaml

from alpi import authority, tools
from alpi.core.run_context import RunContext
from alpi.core.tool_executor import ToolExecutor
from alpi.core.tool_executor import use as use_executor
from alpi.host import connections
from alpi.host.connection_context import ConnectionContext
from alpi.host.connection_context import use as use_connection
from alpi.host.server import HandlerError

ROW = "LEDGER-ROW"


def _member(allow=None) -> ConnectionContext:
    return ConnectionContext(
        connection_id="c2", device_id="d2", source="remote", role="member",
        tool_allow=None if allow is None else tuple(allow),
    )


@pytest.fixture
def home(tmp_path: Path, monkeypatch) -> Path:
    root = tmp_path / "alpi"
    workspace = tmp_path / "ws"
    (root / "out").mkdir(parents=True)
    (root / "sessions").mkdir()
    workspace.mkdir()
    monkeypatch.setenv("ALPI_HOME", str(root))
    monkeypatch.chdir(workspace)
    (root / "config.yaml").write_text(f"workspace: {workspace}\n")
    from alpi import home as home_mod
    monkeypatch.setattr(home_mod, "_ROOT", root)
    connections.invalidate_cache()
    return root


@pytest.fixture
def skill_db(home: Path) -> Path:
    state = home / "skills" / "personal" / "ledger" / "state"
    state.mkdir(parents=True)
    (home / "skills" / "personal" / "ledger" / "SKILL.md").write_text(
        "---\nname: ledger\ndescription: Keeps a ledger.\n---\n\n## When to use\nAlways.\n"
    )
    path = state / "db.sqlite"
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE notes (body TEXT)")
        conn.execute("INSERT INTO notes VALUES (?)", (ROW,))
    return path


def _query():
    return tools.execute("db", {"action": "query", "skill": "ledger", "sql": "SELECT body FROM notes"})


def _names() -> set[str]:
    return {item["function"]["name"] for item in tools.schemas()}


def test_a_member_connection_without_a_tool_list_keeps_the_fence(skill_db: Path) -> None:
    with use_connection(_member()):
        assert "db" not in _names()
        assert "cannot use db" in _query().error


def test_a_member_connection_with_a_tool_list_gets_exactly_that_list(skill_db: Path) -> None:
    with use_connection(_member(["db", "lobby__*"])):
        assert "db" in _names()
        assert ROW in _query().output
        assert "read_file" not in _names()
        refused = tools.execute("read_file", {"path": str(skill_db)})
        assert not refused.ok and ROW not in f"{refused.output}{refused.error}"


def test_a_member_tool_list_that_leaves_db_out_still_has_no_db(skill_db: Path) -> None:
    with use_connection(_member(["read_file"])):
        assert "db" not in _names()
        assert not _query().ok


def test_an_empty_tool_list_grants_nothing(skill_db: Path) -> None:
    with use_connection(_member([])):
        assert _names() == set()
        assert not _query().ok


def test_a_granted_db_works_inside_a_workflow_and_an_ungranted_one_does_not(skill_db: Path, home: Path) -> None:
    context = RunContext("run", home, home.parent / "ws", "default", "peer", "s", "c2")
    step = {"id": "a", "tool": "db", "arguments": {"action": "query", "skill": "ledger", "sql": "SELECT body FROM notes"}}
    with use_connection(_member(["db", "workflow"])), use_executor(ToolExecutor(context)):
        assert ROW in tools.execute("workflow", {"steps": [step]}).output
    with use_connection(_member(["workflow"])), use_executor(ToolExecutor(context)):
        assert ROW not in tools.execute("workflow", {"steps": [step]}).output


def test_the_authority_of_a_member_with_a_tool_list_carries_the_list_to_nested_turns(skill_db: Path) -> None:
    with use_connection(_member()):
        assert authority.current() == {"fence": "member"}
    with use_connection(_member(["db", "skill"])):
        assert authority.current() == {"fence": "allow", "allow": ["db", "skill"]}
    with authority.apply({"fence": "allow", "allow": ["db"]}):
        assert ROW in _query().output
    with authority.apply({"fence": "member"}):
        assert not _query().ok


def test_a_store_keeps_the_tool_list_and_authenticates_with_it(home: Path) -> None:
    connection, issued = connections.create_connection("lobby", role="member")
    token = issued["token"]
    assert connections.authenticate(token, min_interval=10**9).tool_allow is None
    assert connections.update_connection(connection["id"], tools_allow=["lobby__*", "db", "db"])
    connections.invalidate_cache()
    auth = connections.authenticate(token, min_interval=10**9)
    assert auth.tool_allow == ("db", "lobby__*") and auth.context.tool_allow == ("db", "lobby__*")
    row = next(c for c in connections.list_connections() if c["id"] == connection["id"])
    assert connections.public_connection(row)["tools_allow"] == ["db", "lobby__*"]
    assert connections.update_connection(connection["id"], label="renamed")
    assert connections.authenticate(token, min_interval=10**9).tool_allow == ("db", "lobby__*")
    assert connections.update_connection(connection["id"], tools_allow=None)
    assert connections.authenticate(token, min_interval=10**9).tool_allow is None


def test_an_admin_never_carries_a_tool_list(home: Path) -> None:
    connection, issued = connections.create_connection("lobby", role="member")
    assert connections.update_connection(connection["id"], tools_allow=["db"])
    assert connections.update_connection(connection["id"], role="admin")
    assert connections.authenticate(issued["token"], min_interval=10**9).tool_allow is None
    assert connections.update_connection(connection["id"], tools_allow=["db"])
    assert connections.authenticate(issued["token"], min_interval=10**9).tool_allow is None
    assert connections.update_connection(connection["id"], role="member")
    assert connections.authenticate(issued["token"], min_interval=10**9).tool_allow is None


def test_a_corrupt_tool_list_in_the_store_grants_nothing(home: Path) -> None:
    connection, issued = connections.create_connection("lobby", role="member")
    path = connections.store_path()
    data = yaml.safe_load(path.read_text())
    data["connections"][0]["tools_allow"] = "db"
    path.write_text(yaml.safe_dump(data))
    connections.invalidate_cache()
    assert connections.authenticate(issued["token"], min_interval=10**9).tool_allow == ()


def test_the_rpc_validates_the_tool_list() -> None:
    assert connections.validate_tool_allow(None) is None
    assert connections.validate_tool_allow([" db ", "lobby__*"]) == ["db", "lobby__*"]
    for bad in ("db", [1], [""], ["x" * 129], [f"t{i}" for i in range(257)]):
        with pytest.raises(HandlerError):
            connections.validate_tool_allow(bad)


def test_the_host_hands_the_tool_list_to_the_request_context(home: Path) -> None:
    from alpi.host.server import _check_token_meta
    connection, issued = connections.create_connection("lobby", role="member")
    assert connections.update_connection(connection["id"], tools_allow=["db"])
    meta = _check_token_meta({"method": "host.chat.send", "params": {"auth_token": issued["token"]}})
    assert meta.valid and meta.tool_allow == ("db",)


def test_the_store_refuses_a_tool_list_that_is_not_a_list(home: Path) -> None:
    connection, issued = connections.create_connection("lobby", role="member")
    assert not connections.update_connection(connection["id"], tools_allow="db")
    assert connections.authenticate(issued["token"], min_interval=10**9).tool_allow is None


def test_a_local_delegate_turn_runs_with_the_connection_tool_list(home: Path, monkeypatch) -> None:
    import asyncio

    from alpi.host import chat as host_chat
    from alpi.host.connection_context import current

    connection, _issued = connections.create_connection("lobby", role="member")
    assert connections.update_connection(connection["id"], tools_allow=["db"])
    seen = []

    async def fake_send(_params, _server, _send):
        seen.append(current().tool_allow)

    monkeypatch.setattr(host_chat, "_data_chat_send", fake_send)
    asyncio.run(host_chat._data_chat_delegate({"connection_id": connection["id"], "profile": "default"}, None, None))
    assert seen == [("db",)]
