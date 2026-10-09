from __future__ import annotations

import json
from pathlib import Path

import pytest

from alpi import tools
from alpi.alp import handlers as alp_handlers
from alpi.host.connection_context import ConnectionContext
from alpi.host.connection_context import use as use_connection
from alpi.tools._paths import PEER_HISTORY_TOOLS
from alpi.tools.base import ToolResult

ADMIN = ConnectionContext(connection_id="c1", device_id="d1", source="remote", role="admin")
MEMBER = ConnectionContext(connection_id="c2", device_id="d2", source="remote", role="member")

LISTED = frozenset({"skill", "schedule", "db", "memory:read", "session_search", "read_file", "search", "write_file"})

CALLERS = {
    "A": "admin device",
    "M": "member device",
    "P": "peer without tools.allow",
    "L": "peer with tools.allow",
}

HISTORY_TOOLS = ("session_read", "recall_sessions", "index_sessions", "workgroup_search", "index_workgroups")

MATRIX: dict[tuple[str, str], str] = {
    **{("skill", a): "AMPL" for a in ("list", "view", "validate")},
    **{("skill", a): "AML" for a in ("run", "invoke")},
    **{("skill", a): "AL" for a in ("test", "create", "edit", "patch", "add_file", "remove_file", "delete", "reset_state", "set_meta")},
    ("memory", "read"): "AMPL",
    ("memory", "promotion_list"): "AMP",
    **{("memory", a): "A" for a in ("add", "replace", "remove", "promotion_discard")},
    ("schedule", "list"): "AMPL",
    **{("schedule", a): "AL" for a in ("add", "update", "remove", "fire")},
    ("session_search", ""): "AML",
    **{(name, ""): "AM" for name in HISTORY_TOOLS},
    ("db", "query"): "AL",
    ("db", "exec"): "AL",
    ("web_search", ""): "AMP",
    ("read_file", ""): "AMPL",
}

FENCE_TABLE_TOOLS = {"skill", "memory", "schedule"}
ACTION_TOOLS = FENCE_TABLE_TOOLS | {"db"}

SECRET = "PRIVATE-SESSION"


class _Session:
    id = "probe-session"
    messages: list = []

    def save(self) -> None:
        pass


class _ProbeEngine:
    def __init__(self, probe) -> None:
        self.probe = probe
        self.session = _Session()
        self.value = None

    def run_turn(self, prompt, emit, *, source="user", persist_inflight=True) -> None:
        self.value = self.probe()


def run_as(key: str, home: Path, monkeypatch, probe):
    if key in "AM":
        with use_connection(ADMIN if key == "A" else MEMBER):
            return probe()
    engines: list[_ProbeEngine] = []

    def factory(*, home: Path, cfg) -> _ProbeEngine:
        engines.append(_ProbeEngine(probe))
        return engines[0]

    monkeypatch.setattr(alp_handlers, "Engine", factory)
    monkeypatch.setattr(alp_handlers.cfg_mod, "load", lambda _home: object())
    alp_handlers._run_turn(home, "go", "carol", alp_handlers._ActiveTurn(), tool_allow=LISTED if key == "L" else None)
    return engines[0].value


@pytest.fixture
def home(tmp_path: Path, monkeypatch) -> Path:
    root = tmp_path / "alpi"
    workspace = tmp_path / "ws"
    (root / "sessions").mkdir(parents=True)
    workspace.mkdir()
    monkeypatch.setenv("ALPI_HOME", str(root))
    monkeypatch.chdir(workspace)
    (root / "config.yaml").write_text(f"workspace: {workspace}\n")
    (root / "sessions" / "s1.json").write_text(json.dumps({"text": SECRET}))
    (root / "sessions" / "e.json").write_text('{"v": "before"}')
    return root


@pytest.fixture
def stubbed(monkeypatch):
    monkeypatch.setattr(tools, "is_available", lambda _cls: (True, ""))
    for name in {name for name, _ in MATRIX}:
        real = tools._TOOLS[name]
        stub = type(real.__name__, (real,), {"run": lambda self, **kw: ToolResult(ok=True, output="ran")})
        monkeypatch.setitem(tools._TOOLS, name, stub)


@pytest.mark.parametrize("key", CALLERS)
def test_each_caller_class_reaches_exactly_the_tool_actions_the_table_lists(stubbed, home, monkeypatch, key: str) -> None:
    def probe():
        return {(name, action): tools.execute(name, {"action": action} if action else {}).ok for name, action in MATRIX}

    reached = run_as(key, home, monkeypatch, probe)
    assert reached == {row: key in allowed for row, allowed in MATRIX.items()}, CALLERS[key]


@pytest.mark.parametrize("key", CALLERS)
def test_each_caller_class_is_offered_exactly_the_tool_actions_it_may_call(stubbed, home, monkeypatch, key: str) -> None:
    def probe():
        return {
            item["function"]["name"]: item["function"]["parameters"]["properties"].get("action")
            for item in tools.schemas()
        }

    offered = run_as(key, home, monkeypatch, probe)
    for name in {name for name, _ in MATRIX}:
        rows = {action: key in allowed for (n, action), allowed in MATRIX.items() if n == name}
        if name in ACTION_TOOLS:
            visible = {action for action, ok in rows.items() if ok}
            assert (set(offered[name]["enum"]) if name in offered else set()) == visible, (CALLERS[key], name)
        else:
            assert (name in offered) == rows[""], (CALLERS[key], name)


@pytest.mark.parametrize("key", CALLERS)
def test_only_a_caller_the_fence_does_not_cover_touches_a_private_area_of_the_home(home: Path, monkeypatch, key: str) -> None:
    sessions = home / "sessions"

    def probe():
        read = tools.execute("read_file", {"path": str(sessions / "s1.json")})
        found = tools.execute("search", {"pattern": SECRET, "path": str(home)})
        tools.execute("write_file", {"path": str(sessions / "w.json"), "content": '{"v": "written"}'})
        tools.execute("edit_file", {"path": str(sessions / "e.json"), "old_string": "before", "new_string": "after"})
        return {
            "read_file": SECRET in read.output,
            "search": SECRET in found.output,
            "write_file": (sessions / "w.json").exists(),
            "edit_file": "after" in (sessions / "e.json").read_text(),
        }

    touched = run_as(key, home, monkeypatch, probe)
    assert touched == {
        "read_file": key in "AL",
        "search": key in "AL",
        "write_file": key in "AL",
        "edit_file": key in "A",
    }, CALLERS[key]


def test_the_table_classifies_every_action_of_every_tool_the_fence_trims() -> None:
    assert set(tools._PEER_ALLOWED_ACTIONS) == set(tools._MEMBER_ALLOWED_ACTIONS) == FENCE_TABLE_TOOLS
    assert tools._FENCED_OUT_TOOLS == {"db"}
    for name in ACTION_TOOLS:
        declared = set(tools._TOOLS[name].parameters["properties"]["action"]["enum"])
        assert {action for n, action in MATRIX if n == name} == declared, name


def test_the_withheld_history_tools_are_the_ones_the_table_names() -> None:
    assert PEER_HISTORY_TOOLS == frozenset({"session_search", *HISTORY_TOOLS})
