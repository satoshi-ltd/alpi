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


def test_denying_write_file_or_terminal_denies_skill_authoring_but_not_running() -> None:
    for guard in ("write_file", "terminal", "write_*", "term*", "*_file"):
        denies = _policy.effective_denies([guard])
        enum = _schema("skill", denies)["function"]["parameters"]["properties"]["action"]["enum"]
        assert not set(enum) & _policy.SKILL_AUTHORING_ACTIONS, guard
        assert {"run", "view", "list", "validate", "test", "invoke"} <= set(enum), guard


def test_a_profile_without_those_denies_keeps_skill_authoring() -> None:
    enum = _schema("skill", _policy.effective_denies(["email"]))["function"]["parameters"]["properties"]["action"]["enum"]
    assert _policy.SKILL_AUTHORING_ACTIONS <= set(enum)


def test_skill_create_under_a_write_file_deny_is_refused_and_says_why(tmp_home_no_env) -> None:
    result = tools_mod._execute_registered(
        "skill",
        {"action": "create", "name": "pdf-report-builder", "category": "miscellaneous",
         "description": "d", "body": "b"},
        deny=_policy.effective_denies(["write_file"]),
    )
    assert result.ok is False
    assert "skill:create" in result.error and "write_file" in result.error and "operator" in result.error
    assert not (tmp_home_no_env / "skills" / "miscellaneous" / "pdf-report-builder").exists()


def test_an_explicit_skill_action_deny_keeps_the_generic_refusal() -> None:
    refusal = _policy.action_denied("skill", {"action": "create"}, ["skill:create"])
    assert refusal is not None and "operator" not in refusal


def test_a_workgroup_phase_scope_does_not_pose_as_a_config_deny(tmp_home_no_env, monkeypatch) -> None:
    monkeypatch.setenv("ALPI_WORKGROUP_WRITE_SCOPE", '{"phase": "build", "paths": []}')
    denies = _policy.effective_denies([])
    assert "skill:create" not in denies
    result = tools_mod._execute_registered(
        "skill",
        {"action": "create", "name": "x", "category": "miscellaneous", "description": "d", "body": "b"},
        deny=denies,
    )
    assert result.ok is False
    assert "phase boundary" in result.error and "config.yaml" not in result.error
