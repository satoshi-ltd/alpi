"""CL.1 smoke — confirm LiteLLM accepts our ``cache_control_injection_points``
kwarg against a real Anthropic-routed model.

We don't measure cache hits (one-shot turn against a fresh prefix never
hits anything anyway). We're only checking that:

  - ``litellm.utils.supports_prompt_caching`` returns True for the model.
  - The Engine forwards the kwarg without crashing inside LiteLLM.
  - The provider returns a normal reply.

A future LiteLLM that renames the kwarg or changes the marker shape
would fail this smoke even though every unit test still passes.

Run with: ``pytest tests/llm/test_prompt_cache_llm.py --llm``.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.llm


_MODEL = "anthropic/claude-haiku-4-5"
_ENV_VAR = "ANTHROPIC_API_KEY"


def _load_anthropic_env(monkeypatch: pytest.MonkeyPatch) -> bool:
    """Pull ``ANTHROPIC_API_KEY`` from one of the user's known ``.env`` paths into the test environment. Returns True if a non-empty key landed."""
    if os.environ.get(_ENV_VAR):
        return True
    for env_path in (
        Path(__file__).resolve().parents[2] / "alpi" / ".env",
        Path.home() / ".alpi" / ".env",
    ):
        if not env_path.exists():
            continue
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            value = value.strip().strip('"').strip("'")
            if key.strip() == _ENV_VAR and value:
                monkeypatch.setenv(_ENV_VAR, value)
                return True
    return False


def test_anthropic_accepts_cache_control_injection_points(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    if not _load_anthropic_env(monkeypatch):
        pytest.skip(f"{_ENV_VAR} not set — skipping CL.1 LLM smoke")

    from litellm.utils import supports_prompt_caching
    assert supports_prompt_caching(model=_MODEL), (
        f"{_MODEL} is no longer in LiteLLM's prompt-cache allowlist; pick another"
    )

    from alpi import config, home as home_mod, memory
    from alpi.engine import AgentEvent, Engine

    home = tmp_path / "alpi-home"
    home.mkdir()
    monkeypatch.setenv("ALPI_HOME", str(home))
    home_mod.ensure_home(home)
    config.seed_defaults(home)
    memory.MemoryStore(home).seed_defaults()
    (home / "config.yaml").write_text(f"model: {_MODEL}\n")
    (home / ".env").write_text(f"{_ENV_VAR}={os.environ[_ENV_VAR]}\n")

    cfg = config.load(home)
    engine = Engine(home=home, cfg=cfg)

    captured: list[str] = []
    def sink(ev: AgentEvent) -> None:
        if ev.kind == "assistant_done" and ev.final:
            captured.append(ev.text)

    engine.run_turn("Reply with the exact two characters: OK", sink)

    assert captured, "Anthropic call returned no assistant_done frame — the cache kwarg likely tripped LiteLLM or the provider"
    assert captured[0].strip(), "assistant_done was empty"
