"""Tests for the ``tools:`` frontmatter validator accepting MCP names.

Why this exists: a real session lost a turn fighting the validator
because MCP tools come back as ``bitbucket__getPullRequests``
(double-underscore + camelCase suffix), but the validator only
accepted ``snake_case``. The fix widens the regex to accept
``name__method`` patterns as well as plain snake_case.
"""

from __future__ import annotations

from alpi.tools._skill_schema import _check_tools


def _meta(tools: str) -> dict[str, str]:
    return {"tools": tools}


def test_plain_snake_case_passes() -> None:
    assert _check_tools(_meta("[memory, schedule, terminal]")) == []


def test_mcp_double_underscore_camel_case_passes() -> None:
    """``bitbucket__getPullRequests`` is the format MCP returns — not a
    typo, accept it."""
    assert _check_tools(_meta(
        "[bitbucket__getPullRequests, bitbucket__getRepository]"
    )) == []


def test_mixed_snake_and_mcp_both_pass() -> None:
    assert _check_tools(_meta(
        "[memory, bitbucket__getPullRequests, schedule]"
    )) == []


def test_caps_at_start_still_warns() -> None:
    """Tool names must still start lowercase."""
    issues = _check_tools(_meta("[Memory]"))
    assert len(issues) == 1
    assert "naming" in issues[0].message


def test_dashes_still_warn() -> None:
    """Underscores yes, dashes no — keep typo detection useful."""
    issues = _check_tools(_meta("[my-tool]"))
    assert len(issues) == 1


def test_empty_tools_no_warnings() -> None:
    assert _check_tools(_meta("")) == []
    assert _check_tools(_meta("[]")) == []
