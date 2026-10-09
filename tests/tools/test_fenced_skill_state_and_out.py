from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from alpi import tools
from alpi.core.run_context import RunContext
from alpi.core.tool_executor import ToolExecutor
from alpi.core.tool_executor import use as use_executor
from alpi.host.connection_context import ConnectionContext
from alpi.host.connection_context import use as use_connection
from alpi.tools import _policy, _state
from alpi.tools._paths import PEER_HISTORY_TOOLS

ADMIN = ConnectionContext(connection_id="c1", device_id="d1", source="remote", role="admin")
MEMBER = ConnectionContext(connection_id="c2", device_id="d2", source="remote", role="member")
PEER = ConnectionContext(connection_id="peer:carol", source="peer")

OTHER = "ANOTHER-CONNECTIONS-REPORT"
ROW = "ANOTHER-CONNECTIONS-ROW"


def _as_peer(allow):
    return _policy.use(allow, "peer 'carol'", PEER_HISTORY_TOOLS, fence_without_policy=True)


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
    (root / "out" / "theirs.md").write_text(OTHER)
    (root / "out" / "theirs.json").write_text(json.dumps({"v": OTHER}))
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


def _db_names() -> set[str]:
    return {item["function"]["name"] for item in tools.schemas()}


def test_an_admin_reads_and_writes_a_skill_database(skill_db: Path) -> None:
    with use_connection(ADMIN):
        assert "db" in _db_names()
        assert ROW in _query().output
        assert tools.execute("db", {"action": "exec", "skill": "ledger", "sql": "DELETE FROM notes"}).ok


def test_a_member_has_no_db_tool_and_cannot_call_it(skill_db: Path) -> None:
    with use_connection(MEMBER):
        assert "db" not in _db_names()
        for action, sql in (("query", "SELECT body FROM notes"), ("exec", "DELETE FROM notes")):
            result = tools.execute("db", {"action": action, "skill": "ledger", "sql": sql})
            assert not result.ok and ROW not in f"{result.output}{result.error}"
            assert "cannot use db" in result.error
    with sqlite3.connect(skill_db) as conn:
        assert conn.execute("SELECT count(*) FROM notes").fetchone() == (1,)


def test_a_peer_without_a_tool_policy_has_no_db_tool_and_a_granting_policy_restores_it(skill_db: Path) -> None:
    with use_connection(PEER), _as_peer(None):
        assert "db" not in _db_names()
        assert not _query().ok
    with use_connection(PEER), _as_peer(frozenset({"db"})):
        assert "db" in _db_names()
        assert ROW in _query().output


def test_a_member_under_a_tool_list_still_has_no_db(skill_db: Path) -> None:
    with use_connection(MEMBER), _policy.use(frozenset({"db"}), "listed"):
        assert not _query().ok


def test_a_member_cannot_reach_db_through_a_workflow(skill_db: Path, home: Path) -> None:
    context = RunContext("run", home, home.parent / "ws", "default", "peer", "s", "c2")
    step = {"id": "a", "tool": "db", "arguments": {"action": "query", "skill": "ledger", "sql": "SELECT body FROM notes"}}
    with use_connection(MEMBER), use_executor(ToolExecutor(context)):
        result = tools.execute("workflow", {"steps": [step]})
    assert ROW not in f"{result.output}{result.error}"


def test_a_member_cannot_read_search_or_overwrite_files_it_did_not_create_in_out(home: Path) -> None:
    theirs = home / "out" / "theirs.md"
    with use_connection(MEMBER):
        assert OTHER not in _text(tools.execute("read_file", {"path": str(theirs)}))
        assert OTHER not in _text(tools.execute("search", {"pattern": OTHER, "path": str(home / "out")}))
        assert OTHER not in _text(tools.execute("search", {"pattern": "theirs", "path": str(home), "target": "files"}))
        assert not tools.execute("write_file", {"path": str(theirs), "content": "taken over"}).ok
        assert not tools.execute("edit_file", {"path": str(theirs), "old_string": OTHER, "new_string": "x"}).ok
        assert not tools.execute("delete_file", {"path": str(theirs)}).ok
    assert theirs.read_text() == OTHER


def test_a_member_works_on_the_files_it_creates_in_out_for_the_rest_of_the_turn(home: Path) -> None:
    mine = home / "out" / "mine.json"
    _state.reset_turn_outputs()
    with use_connection(MEMBER):
        assert tools.execute("write_file", {"path": str(mine), "content": '{"v": "draft"}'}).ok
        assert "draft" in tools.execute("read_file", {"path": str(mine)}).output
        assert tools.execute("edit_file", {"path": str(mine), "old_string": "draft", "new_string": "final"}).ok
        assert tools.execute("attach_file", {"path": str(mine)}).ok
        _state.reset_turn_outputs()
        assert not tools.execute("read_file", {"path": str(mine)}).ok
        assert not tools.execute("write_file", {"path": str(mine), "content": "{}"}).ok
    assert "final" in mine.read_text()


def test_a_member_cannot_create_a_file_in_out_through_a_link_into_another_area(home: Path) -> None:
    (home / "out" / "door").symlink_to(home / "sessions" / "planted.json")
    with use_connection(MEMBER):
        result = tools.execute("write_file", {"path": str(home / "out" / "door"), "content": "{}"})
    assert not result.ok
    assert not (home / "sessions" / "planted.json").exists()


def test_any_writer_that_creates_a_file_in_out_gives_the_turn_its_file_back(home: Path) -> None:
    from alpi.tools._paths import resolve_path

    saved = home / "out" / "download.md"
    _state.reset_turn_outputs()
    with use_connection(MEMBER):
        resolve_path(str(saved), for_write=True)
        saved.write_text("from a mail attachment")
        assert "mail attachment" in tools.execute("read_file", {"path": str(saved)}).output
        with pytest.raises(ValueError, match="choose a new file name"):
            resolve_path(str(home / "out" / "theirs.md"), for_write=True)


def test_a_member_cannot_plant_a_file_in_another_profiles_out(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "data"
    mine = root / "profiles" / "a"
    other = root / "profiles" / "b"
    for profile in (mine, other):
        (profile / "out").mkdir(parents=True)
    workspace = tmp_path / "ws"
    workspace.mkdir()
    monkeypatch.setenv("ALPI_HOME", str(mine))
    monkeypatch.chdir(workspace)
    (mine / "config.yaml").write_text(f"workspace: {workspace}\n")
    _state.reset_turn_outputs()
    with use_connection(MEMBER):
        assert tools.execute("write_file", {"path": str(mine / "out" / "ok.md"), "content": "ok"}).ok
        assert not tools.execute("write_file", {"path": str(other / "out" / "planted.md"), "content": "x"}).ok
    assert not (other / "out" / "planted.md").exists()


def test_a_peer_without_a_tool_policy_has_the_same_out_fence(home: Path) -> None:
    with use_connection(PEER), _as_peer(None):
        assert OTHER not in _text(tools.execute("read_file", {"path": str(home / "out" / "theirs.md")}))
        assert tools.execute("write_file", {"path": str(home / "out" / "peer.md"), "content": "ok"}).ok
    with use_connection(PEER), _as_peer(frozenset({"read_file"})):
        assert OTHER in tools.execute("read_file", {"path": str(home / "out" / "theirs.md")}).output


def test_an_admin_reads_and_overwrites_any_file_in_out(home: Path) -> None:
    with use_connection(ADMIN):
        assert OTHER in tools.execute("read_file", {"path": str(home / "out" / "theirs.md")}).output
        assert tools.execute("write_file", {"path": str(home / "out" / "theirs.md"), "content": "mine now"}).ok


def _text(result) -> str:
    return f"{result.output}{result.error}"
