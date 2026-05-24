"""``alpi_knowledge`` tool — index + view actions over packaged docs."""

from __future__ import annotations

from alpi import knowledge
from alpi.tools.knowledge import TOOL


def test_index_lists_every_topic() -> None:
    r = TOOL().run(action="index")
    assert r.ok, r.error
    for topic in knowledge.topics():
        assert topic in r.output


def test_view_returns_the_packaged_reference() -> None:
    r = TOOL().run(action="view", topic="install")
    assert r.ok, r.error
    assert r.output == knowledge.read("install")


def test_view_without_topic_is_a_clear_error() -> None:
    r = TOOL().run(action="view")
    assert not r.ok
    assert "topic" in r.error.lower()
    assert "index" in r.error.lower()


def test_view_unknown_topic_lists_valid_topics() -> None:
    r = TOOL().run(action="view", topic="ghost")
    assert not r.ok
    assert "ghost" in r.error
    assert "readme" in r.error


def test_unknown_action_rejected() -> None:
    r = TOOL().run(action="wibble")
    assert not r.ok
    assert "wibble" in r.error or "unknown action" in r.error


def test_schema_topic_enum_matches_knowledge_topics() -> None:
    # Schema must be in lockstep with the runtime enum; otherwise the LLM could submit a topic the tool rejects.
    schema_enum = TOOL.parameters["properties"]["topic"]["enum"]
    assert schema_enum == knowledge.topics()


def test_tool_is_registered_in_the_tool_index() -> None:
    from alpi import tools
    assert tools.get("alpi_knowledge") is TOOL
