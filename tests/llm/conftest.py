"""LLM-in-loop fixtures for ``tests/llm/``.

Engine is invoked directly so tests can assert on tool calls and
filesystem state instead of prose. Each case runs against the configured
model matrix and skips when the matching API key is missing.

Run with: ``pytest tests/llm --llm``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import pytest


_MODELS: list[tuple[str, str, str]] = [
    ("gpt-5.4-mini", "OPENAI_API_KEY", "openai/gpt-5.4-mini"),
    ("step-3.5-flash", "OPENROUTER_API_KEY", "openrouter/stepfun/step-3.5-flash"),
]


@dataclass
class Trace:
    """Captured AgentEvent stream from a turn."""
    events: list = field(default_factory=list)

    def tool_calls(self, name: str | None = None) -> list:
        out = [e for e in self.events if e.kind == "tool_start"]
        if name is not None:
            out = [e for e in out if e.name == name]
        return out

    def tool_results(self, name: str | None = None) -> list:
        out = [e for e in self.events if e.kind == "tool_end"]
        if name is not None:
            out = [e for e in out if e.name == name]
        return out

    def assistant_text(self) -> str:
        return "\n".join(e.text for e in self.events if e.kind == "assistant_done")


def _llm_home(tmp_path: Path) -> Path:
    home = tmp_path / "alpi-home"
    home.mkdir()
    return home


def _load_real_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Restore only the API keys used by the LLM matrix."""
    candidates = [
        Path(__file__).resolve().parents[2] / "alpi" / ".env",
        Path.home() / ".alpi" / ".env",
    ]
    wanted = {env_var for _, env_var, _ in _MODELS}
    found: set[str] = set()
    for env_path in candidates:
        if not env_path.exists():
            continue
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key in wanted and key not in found and value:
                monkeypatch.setenv(key, value)
                found.add(key)


@pytest.fixture(params=_MODELS, ids=[m[0] for m in _MODELS])
def llm_engine(
    request: pytest.FixtureRequest,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Callable:
    """Return a factory for an isolated Engine using the selected model."""
    test_id, env_var, model = request.param
    _load_real_env(monkeypatch)
    if not os.environ.get(env_var):
        pytest.skip(f"{env_var} not set - skipping {test_id}")

    home = _llm_home(tmp_path)
    monkeypatch.setenv("ALPI_HOME", str(home))

    from alpi import config, home as home_mod, memory
    from alpi.engine import AgentEvent, Engine

    home_mod.ensure_home(home)
    config.seed_defaults(home)
    memory.MemoryStore(home).seed_defaults()
    # Default AGENT.md so the persona is the slim seed.
    from importlib import resources
    agent = home / "memories" / "AGENT.md"
    if not agent.exists():
        agent.write_text(
            resources.files("alpi.prompts").joinpath("default_agent.md").read_text()
        )

    cfg = config.load(home)
    cfg.model = model

    def factory(before_engine: Callable[[Path], None] | None = None):
        trace = Trace()

        def sink(ev: AgentEvent) -> None:
            trace.events.append(ev)

        if before_engine is not None:
            before_engine(home)
        engine = Engine(home=home, cfg=cfg)

        def run(prompt: str) -> Trace:
            engine.run_turn(prompt, sink)
            return trace

        return engine, home, trace, run

    return factory
