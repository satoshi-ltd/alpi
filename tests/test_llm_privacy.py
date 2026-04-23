"""Privacy guards on the litellm wrapper."""

from __future__ import annotations


def test_litellm_telemetry_is_disabled_on_import() -> None:
    """alpi's principle is no telemetry. LiteLLM defaults to
    ``telemetry = True``; ``_silence_litellm()`` runs at import time
    and must flip it off before any LLM call is made."""
    import alpi.llm  # noqa: F401 — side-effectful import triggers the guard
    import litellm
    assert litellm.telemetry is False, (
        "litellm.telemetry must be False. alpi sends zero telemetry; the "
        "LLM wrapper is the one place that could accidentally leak."
    )
