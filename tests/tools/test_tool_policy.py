from __future__ import annotations

import contextvars
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from alpi import tools
from alpi.core.run_context import RunContext
from alpi.core.tool_executor import ToolCall, ToolExecutor
from alpi.tools import _policy
from alpi.tools.base import Tool, ToolResult


class _Kb(Tool):
    name = "kb"
    description = "x"
    parameters = {
        "type": "object",
        "properties": {"action": {"type": "string", "enum": ["search", "ingest", "maintain"]}},
        "required": ["action"],
    }

    def run(self, **kwargs):
        return ToolResult(ok=True, output=f"kb {kwargs.get('action')}")


class _Free(Tool):
    name = "free"
    description = "x"
    parameters = {"type": "object", "properties": {"action": {"type": "string"}}}

    def run(self, **kwargs):
        return ToolResult(ok=True, output=f"free {kwargs.get('action')}")


class _Plain(Tool):
    name = "plain"
    description = "x"
    parallel_safe = True

    def run(self, **kwargs):
        return ToolResult(ok=True, output=threading.current_thread().name)


class _Other(_Plain):
    name = "other"


class _Bare(_Plain):
    name = "bare"
    parameters = None


class _Loose(Tool):
    name = "loose"
    description = "x"
    calls: list[dict] = []

    def run(self, **kwargs):
        _Loose.calls.append(kwargs)
        return ToolResult(ok=True, output="ran")


FAKES = {cls.name: cls for cls in (_Kb, _Free, _Plain, _Other, _Bare, _Loose)}


def _schemas(deny=None) -> dict[str, dict]:
    return {s["function"]["name"]: s for s in tools.schemas(deny=deny)}


def _enum(schema: dict) -> list[str]:
    return schema["function"]["parameters"]["properties"]["action"]["enum"]


def _refused(result: ToolResult) -> bool:
    return result.ok is False and "tool policy for peer 'p'" in (result.error or "")


def test_is_denied_matches_exact_names_and_star_patterns() -> None:
    assert _policy.is_denied("write_file", {"write_file"})
    assert not _policy.is_denied("read_file", {"write_file"})
    assert _policy.is_denied("github__create_issue", {"github__*"})
    assert not _policy.is_denied("gitlab__create_issue", {"github__*"})
    assert not _policy.is_denied("anything", None)
    assert not _policy.is_denied("anything", set())


def test_without_a_policy_every_tool_and_action_is_permitted() -> None:
    assert _policy.allowed() is None
    assert _policy.permits(tools.get("write_file").schema(), {"path": "x"})
    with tools.use_mcp_tools(FAKES):
        assert _enum(_schemas()["kb"]) == ["search", "ingest", "maintain"]
        assert tools.execute("kb", {"action": "ingest"}).output == "kb ingest"
    assert "write_file" in _schemas()


def test_policy_is_bound_to_the_block_and_reset_afterwards() -> None:
    with _policy.use([" read_file ", "", "kb:search"], "peer 'alexandra'"):
        assert _policy.allowed() == frozenset({"read_file", "kb:search"})
        assert "peer 'alexandra'" in _policy.refusal("terminal")
    assert _policy.allowed() is None
    with _policy.use(None, "peer 'carol'"):
        assert _policy.allowed() is None


def test_an_allowlist_hides_every_other_tool_and_refuses_it() -> None:
    with _policy.use({"read_file"}, "peer 'p'"):
        assert set(_schemas()) == {"read_file"}
        refused = tools.execute("write_file", {"path": "x.md", "content": "y"})
        assert _refused(refused) and "write_file" in refused.error and "tools.allow" in refused.error
        assert _refused(tools.execute("terminal", {"command": "true"}))
        assert not _refused(tools.execute("read_file", {"path": "missing.md"}))
    assert "write_file" in _schemas()


def test_an_empty_allowlist_leaves_no_tool() -> None:
    with _policy.use([], "peer 'p'"):
        assert _schemas() == {}
        assert _refused(tools.execute("read_file", {"path": "x"}))


def test_action_entries_trim_the_enum_and_refuse_every_other_action() -> None:
    with tools.use_mcp_tools(FAKES):
        with _policy.use({"kb:search"}, "peer 'p'"):
            assert _enum(_schemas()["kb"]) == ["search"]
            assert _schemas()["kb"]["function"]["parameters"]["required"] == ["action"]
            assert tools.execute("kb", {"action": "search"}).output == "kb search"
            ingest = tools.execute("kb", {"action": "ingest"})
            assert _refused(ingest) and "kb:ingest" in ingest.error
            assert _refused(tools.execute("kb", {}))
            assert _refused(tools.execute("kb", {"action": ["search"]}))
        with _policy.use({"kb:maintain", "kb:search"}, "peer 'p'"):
            assert _enum(_schemas()["kb"]) == ["search", "maintain"]
        with _policy.use({"kb:search", "kb"}, "peer 'p'"):
            assert _enum(_schemas()["kb"]) == ["search", "ingest", "maintain"]
            assert tools.execute("kb", {"action": "ingest"}).ok is True
        with _policy.use({"kb:purge"}, "peer 'p'"):
            assert "kb" not in _schemas()
        assert _enum(_schemas()["kb"]) == ["search", "ingest", "maintain"]


def test_an_action_entry_never_runs_a_tool_that_declares_no_action() -> None:
    _Loose.calls.clear()
    with tools.use_mcp_tools(FAKES):
        with _policy.use({"plain:run", "bare:run", "loose:read"}, "peer 'p'"):
            names = _schemas()
            assert not {"plain", "bare", "loose"} & set(names)
            assert _refused(tools.execute("plain", {"action": "run"}))
            assert _refused(tools.execute("bare", {"action": "run"}))
            assert _refused(tools.execute("loose", {"action": "read"}))
    assert _Loose.calls == []


def test_a_real_tool_is_not_reachable_through_an_invented_action(monkeypatch) -> None:
    from alpi.tools import peer as peer_tool

    sent: list[str] = []

    async def fake_execute(home, peer_id, prompt, **kwargs):  # noqa: ANN001
        sent.append(prompt)
        raise AssertionError("the transport must not be reached")

    monkeypatch.setattr(peer_tool.alp_mention, "execute", fake_execute)
    with _policy.use({"peer:read"}, "peer 'p'"):
        assert "peer" not in _schemas()
        refused = tools.execute("peer", {"peer_id": "agora", "prompt": "hi", "action": "read"})
        assert _refused(refused)
    assert sent == []


def test_an_optional_free_action_becomes_a_required_enum_of_the_allowed_actions() -> None:
    original = _Free.schema()
    with tools.use_mcp_tools(FAKES):
        with _policy.use({"free:read", "free:list"}, "peer 'p'"):
            offered = _schemas()["free"]["function"]["parameters"]
            assert offered["properties"]["action"]["enum"] == ["list", "read"]
            assert offered["required"] == ["action"]
            assert tools.execute("free", {"action": "read"}).output == "free read"
            assert _refused(tools.execute("free", {"action": "write"}))
            assert _refused(tools.execute("free", {}))
    assert _Free.schema() == original
    assert "enum" not in _Free.parameters["properties"]["action"] and "required" not in _Free.parameters
    assert _Kb.parameters["properties"]["action"]["enum"] == ["search", "ingest", "maintain"]


def test_a_pattern_allows_every_tool_of_an_mcp_server() -> None:
    class _CreateIssue(Tool):
        name = "github__create_issue"
        description = "x"

        def run(self, **kwargs):
            return ToolResult(ok=True, output="created")

    class _GitlabIssue(_CreateIssue):
        name = "gitlab__create_issue"

    with tools.use_mcp_tools({_CreateIssue.name: _CreateIssue, _GitlabIssue.name: _GitlabIssue}):
        with _policy.use({"github__*"}, "peer 'p'"):
            assert set(_schemas()) == {"github__create_issue"}
            assert tools.execute("github__create_issue", {}).ok is True
            assert _refused(tools.execute("gitlab__create_issue", {}))


def test_profile_denies_still_apply_inside_an_allowlist() -> None:
    with _policy.use({"read_file", "write_file"}, "peer 'p'"):
        assert set(_schemas(deny={"write_file"})) == {"read_file"}
        refused = tools.execute("write_file", {"path": "x", "content": "y"}, deny={"write_file"})
        assert refused.ok is False and "config.yaml" in refused.error


def test_effective_denies_no_longer_carries_the_peer_policy() -> None:
    with _policy.use({"read_file"}, "peer 'p'"):
        assert _policy.effective_denies(["email"]) == frozenset({"email"}) | _policy.effective_denies([])


def test_the_policy_reaches_parallel_calls_and_sub_agent_threads(tmp_path: Path) -> None:
    context = RunContext.create(
        home=tmp_path, workspace=tmp_path, profile="default", source="user",
        session_id="s", connection_id="host",
    )
    executor = ToolExecutor(context, max_workers=2)
    with tools.use_mcp_tools(FAKES), _policy.use({"plain"}, "peer 'p'"):
        outcomes = executor.execute_parallel([
            ToolCall("1", "plain", {}), ToolCall("2", "other", {}),
        ])
        assert outcomes[0].result.ok is True and outcomes[0].result.output.startswith("alpi-tool")
        assert _refused(outcomes[1].result)

        def in_thread() -> tuple[set[str], ToolResult]:
            return set(_schemas()), tools.execute("other", {})

        with ThreadPoolExecutor(max_workers=1) as pool:
            names, result = pool.submit(contextvars.copy_context().run, in_thread).result()
        assert names == {"plain"} and _refused(result)
