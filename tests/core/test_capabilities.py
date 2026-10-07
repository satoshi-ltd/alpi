from __future__ import annotations

import pytest

from alpi.providers.capabilities import forced_tool_choice


@pytest.mark.parametrize("model", [
    "anthropic/claude-opus-5-5",
    "anthropic/claude-sonnet-5-5",
    "anthropic/claude-fable-5-1",
    "anthropic/claude-mythos-5-1",
    "openrouter/anthropic/claude-opus-5.5",
    "openrouter/anthropic/claude-fable-5.1",
    "bedrock/anthropic.claude-opus-5-5",
    "anthropic/claude-opus-6",
    "anthropic/claude-sonnet-6-1",
    "anthropic/claude-fable-5",
    "anthropic/claude-mythos-5",
])
def test_models_that_reject_forced_tool_use(model) -> None:
    assert forced_tool_choice(model) is False


@pytest.mark.parametrize("model", [
    "anthropic/claude-opus-5",
    "anthropic/claude-sonnet-5",
    "anthropic/claude-opus-4-8",
    "anthropic/claude-haiku-4-5",
    "anthropic/claude-opus-4-20250514",
    "openai/gpt-6.1-sol",
    "openrouter/deepseek/deepseek-v4.1-flash",
    "",
])
def test_models_that_accept_forced_tool_use(model) -> None:
    assert forced_tool_choice(model) is True


@pytest.mark.parametrize("kwargs", [
    {"reasoning_effort": "low"},
    {"extra_body": {"reasoning": {"effort": "high"}}},
])
def test_a_claude_call_that_asks_for_reasoning_is_never_forced(kwargs) -> None:
    assert forced_tool_choice("anthropic/claude-sonnet-5", kwargs) is False
    assert forced_tool_choice("openrouter/anthropic/claude-haiku-4.5", kwargs) is False


def test_a_claude_call_without_reasoning_and_other_providers_keep_forcing() -> None:
    assert forced_tool_choice("anthropic/claude-haiku-4-5", {"reasoning_effort": ""}) is True
    assert forced_tool_choice("openai/gpt-6.1-sol", {"reasoning_effort": "high"}) is True
