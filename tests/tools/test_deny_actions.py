from __future__ import annotations

from alpi import tools as tools_mod
from alpi.tools import _policy


def _schema(name: str, deny):
    return next((s for s in tools_mod.schemas(deny=frozenset(deny)) if s["function"]["name"] == name), None)


def test_denied_actions_leave_the_enum_and_the_tool_stays() -> None:
    full = _schema("knowledge", [])
    trimmed = _schema("knowledge", ["knowledge:ingest", "knowledge:maintain"])
    assert "ingest" in full["function"]["parameters"]["properties"]["action"]["enum"]
    enum = trimmed["function"]["parameters"]["properties"]["action"]["enum"]
    assert "ingest" not in enum and "maintain" not in enum and "search" in enum
    assert "action" in trimmed["function"]["parameters"]["required"]


def test_a_wildcard_action_deny_drops_the_whole_tool() -> None:
    assert _schema("knowledge", ["knowledge:*"]) is None


def test_whole_tool_denies_keep_their_meaning() -> None:
    assert _schema("knowledge", ["knowledge"]) is None
    assert _schema("read_file", ["knowledge:ingest"]) is not None


def test_a_call_to_a_denied_action_is_refused_and_names_the_allowed_ones() -> None:
    result = tools_mod._execute_registered(
        "knowledge", {"action": "ingest", "source_path": "x"}, deny=frozenset({"knowledge:ingest"}),
    )
    assert result.ok is False
    assert "knowledge:ingest" in result.error and "allowed: " in result.error and "search" in result.error


def test_an_allowed_action_passes_the_deny_gate() -> None:
    assert _policy.action_denied("knowledge", {"action": "search"}, ["knowledge:ingest"]) is None
    assert _policy.action_denied("memory", {"action": "add"}, ["knowledge:ingest"]) is None


def test_denied_actions_helper() -> None:
    assert _policy.denied_actions("knowledge", ["knowledge:ingest", "knowledge:maintain", "memory:remove"]) == frozenset({"ingest", "maintain"})
    assert _policy.denied_actions("github__issues", ["github__*:create"]) == frozenset({"create"})
    assert _policy.denied_actions("knowledge", ["knowledge"]) == frozenset()


def test_a_search_only_knowledge_profile_sees_only_action_query_and_k() -> None:
    trimmed = _schema("knowledge", ["knowledge:ingest", "knowledge:maintain", "knowledge:lint", "knowledge:index"])
    assert sorted(trimmed["function"]["parameters"]["properties"]) == ["action", "k", "query"]
    assert trimmed["function"]["parameters"]["properties"]["action"]["enum"] == ["search"]


def test_a_denied_action_cannot_be_reached_by_case_or_spacing() -> None:
    for action in ("Ingest", " ingest", "INGEST "):
        result = tools_mod._execute_registered(
            "knowledge", {"action": action, "source_path": "x"}, deny=frozenset({"knowledge:ingest"}),
        )
        assert result.ok is False and "denied" in result.error, action
    assert _policy.action_denied("knowledge", {"action": "search"}, ["knowledge:ingest"], tools_mod.get("knowledge").schema()) is None
