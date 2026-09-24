from __future__ import annotations

from types import SimpleNamespace

from alpi import tools
from alpi.tools import _policy
from alpi.tools import delegate
from alpi.tools.base import Tool, ToolResult


def _names(deny) -> set[str]:
    return {s["function"]["name"] for s in tools.schemas(deny=deny)}


def test_is_denied_matches_exact_names_and_star_patterns() -> None:
    assert _policy.is_denied("write_file", {"write_file"})
    assert not _policy.is_denied("read_file", {"write_file"})
    assert _policy.is_denied("github__create_issue", {"github__*"})
    assert not _policy.is_denied("gitlab__create_issue", {"github__*"})
    assert not _policy.is_denied("anything", None)
    assert not _policy.is_denied("anything", set())


def test_policy_is_bound_to_the_block_and_reset_afterwards() -> None:
    assert _policy.denies() == frozenset()
    with _policy.use([" write_file ", "", "terminal"], "peer 'alexandra'"):
        assert _policy.denies() == frozenset({"write_file", "terminal"})
        assert "peer 'alexandra'" in _policy.reason_for("terminal")
        assert _policy.reason_for("read_file") == ""
    assert _policy.denies() == frozenset()
    assert _policy.reason_for("terminal") == ""


def test_policy_hides_denied_tools_from_schemas_and_refuses_execution() -> None:
    with _policy.use({"write_file", "terminal"}, "peer 'alexandra'"):
        names = _names(_policy.denies())
        assert "write_file" not in names and "terminal" not in names
        assert "read_file" in names
        refused = tools.execute(
            "write_file", {"path": "x.md", "content": "y"}, deny=_policy.denies(),
        )
        assert refused.ok is False
        assert "peer 'alexandra'" in refused.error and "write_file" in refused.error
    assert "write_file" in _names(None)


def test_policy_pattern_covers_every_tool_of_an_mcp_server() -> None:
    class _CreateIssue(Tool):
        name = "github__create_issue"
        description = "x"

        def run(self, **kwargs):
            return ToolResult(ok=True, output="created")

    with tools.use_mcp_tools({_CreateIssue.name: _CreateIssue}):
        with _policy.use({"github__*"}, "peer 'p'"):
            assert "github__create_issue" not in _names(_policy.denies())
            refused = tools.execute("github__create_issue", {}, deny=_policy.denies())
            assert refused.ok is False and "peer 'p'" in refused.error
        assert tools.execute("github__create_issue", {}).ok is True


def test_delegated_sub_agents_inherit_the_turn_policy() -> None:
    cfg = SimpleNamespace(tools=SimpleNamespace(deny=["email"]))
    with _policy.use({"write_file"}, "peer 'p'"):
        assert delegate._turn_denies(cfg) >= {"email", "write_file"}
    assert "write_file" not in delegate._turn_denies(cfg)
    assert "email" in delegate._turn_denies(cfg)


def test_effective_denies_unions_profile_and_turn_policy() -> None:
    with _policy.use({"write_file"}, "peer 'p'"):
        assert _policy.effective_denies(["email"]) >= {"email", "write_file"}
    assert "write_file" not in _policy.effective_denies(["email"])


def test_research_sub_agent_schema_honours_the_turn_policy(tmp_path, monkeypatch) -> None:
    import pytest

    from alpi.tools import research

    (tmp_path / "config.yaml").write_text("model: gpt-5.4-mini\n")
    monkeypatch.setattr(research, "get_home", lambda: tmp_path)
    captured: dict = {}

    def fake_schemas(deny=None):
        captured["deny"] = frozenset(deny or ())
        raise RuntimeError("stop before any model call")

    monkeypatch.setattr("alpi.tools.schemas", fake_schemas)
    with _policy.use({"read_file"}, "peer 'p'"):
        with pytest.raises(RuntimeError):
            research.TOOL()._run_single("what is alpi")

    assert "read_file" in captured["deny"]
