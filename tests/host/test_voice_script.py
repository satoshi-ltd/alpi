from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from alpi import config as cfg_mod
from alpi.host import config as host_config
from alpi.host import handlers as host_handlers
from alpi.host import server as host_server
from alpi.host import voice as host_voice


def _bootstrap(home: Path, model: str = "openai/gpt-5.4-mini") -> Path:
    home.mkdir(parents=True, exist_ok=True)
    cfg = cfg_mod.Config(home=home, model=model)
    cfg_mod.save(cfg)
    return home


def _count_llm(monkeypatch: pytest.MonkeyPatch, reply: str) -> dict[str, int]:
    calls = {"n": 0}

    def fake_complete(messages, **kwargs):  # noqa: ARG001
        calls["n"] += 1
        return SimpleNamespace(content=reply)

    monkeypatch.setattr("alpi.llm.complete", fake_complete)
    return calls


def test_script_for_calls_llm_once_then_serves_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = _bootstrap(tmp_path / "h")
    calls = _count_llm(monkeypatch, "I checked the tests and everything passes.")

    first, source1 = host_voice.script_for(home, "Done ✅ all 3500 tests pass 🎉")
    second, source2 = host_voice.script_for(home, "Done ✅ all 3500 tests pass 🎉")

    assert calls["n"] == 1
    assert (source1, source2) == ("llm", "cache")
    assert second == first == "I checked the tests and everything passes."


def test_script_output_is_sanitized_even_when_llm_misbehaves(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = _bootstrap(tmp_path / "h")
    _count_llm(monkeypatch, "All good 🚀 see **notes** at https://github.com/soyjavi/alf")

    script, source = host_voice.script_for(home, "whatever")

    assert source == "llm"
    assert script == "All good see notes at github.com"


def test_llm_failure_falls_back_and_is_not_cached(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = _bootstrap(tmp_path / "h")
    calls = {"n": 0}

    def flaky_complete(messages, **kwargs):  # noqa: ARG001
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("provider down")
        return SimpleNamespace(content="Now it works.")

    monkeypatch.setattr("alpi.llm.complete", flaky_complete)

    first, source1 = host_voice.script_for(home, "Hola ✅ **listo** → https://x.dev/a|b")
    assert source1 == "fallback"
    assert first == "Hola listo x.dev"

    second, source2 = host_voice.script_for(home, "Hola ✅ **listo** → https://x.dev/a|b")
    assert (source2, second) == ("llm", "Now it works.")
    assert calls["n"] == 2


def test_profile_without_model_uses_fallback_without_llm(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = _bootstrap(tmp_path / "h", model="")
    calls = _count_llm(monkeypatch, "never")

    script, source = host_voice.script_for(home, "# Título\n- uno\n- dos ⭐")

    assert calls["n"] == 0
    assert source == "fallback"
    assert script == "Título uno dos"


def test_huge_inputs_keep_head_and_tail_for_the_briefing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = _bootstrap(tmp_path / "h")
    seen = {}

    def spy_complete(messages, **kwargs):  # noqa: ARG001
        seen["user"] = messages[-1]["content"]
        return SimpleNamespace(content="Briefing.")

    monkeypatch.setattr("alpi.llm.complete", spy_complete)

    huge = "INTRO the outcome. " + ("filler sentence. " * 2000) + "FINAL conclusion."
    script, source = host_voice.script_for(home, huge)

    assert (script, source) == ("Briefing.", "llm")
    assert len(seen["user"]) <= host_voice._MAX_INPUT_CHARS + 10
    assert seen["user"].startswith("INTRO the outcome.")
    assert seen["user"].endswith("FINAL conclusion.")


def test_long_scripts_are_truncated_at_word_boundary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = _bootstrap(tmp_path / "h")
    _count_llm(monkeypatch, "word " * 400)

    script, _ = host_voice.script_for(home, "long")

    assert len(script) <= host_voice.SCRIPT_MAX_CHARS + 1
    assert script.endswith("…")
    assert " wor…" not in script


def test_script_llm_spend_lands_in_the_ledger(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from alpi import ledger

    home = _bootstrap(tmp_path / "h")

    def fake_complete(messages, **kwargs):  # noqa: ARG001
        return SimpleNamespace(
            content="Briefing.", cost_usd=0.0123, input_tokens=800, output_tokens=120,
        )

    monkeypatch.setattr("alpi.llm.complete", fake_complete)

    _, source = host_voice.script_for(home, "some long reply")
    assert source == "llm"

    data = ledger.load(home)
    assert data["profile"]["usd"] == pytest.approx(0.0123)
    assert data["profile"]["tokens"] == 920

    host_voice.script_for(home, "some long reply")
    assert ledger.load(home)["profile"]["tokens"] == 920


def test_script_respects_the_daily_budget_cap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from alpi import ledger

    home = _bootstrap(tmp_path / "h")
    cfg = cfg_mod.load(home)
    cfg.budget = {"daily_usd": 1.0}
    cfg_mod.save(cfg)
    ledger.record(home, usd=1.0, tokens=1000)

    calls = _count_llm(monkeypatch, "never spoken")
    script, source = host_voice.script_for(home, "Hola ✅ **listo**")

    assert calls["n"] == 0
    assert (script, source) == ("Hola listo", "fallback")


@pytest.mark.asyncio
async def test_voice_script_rpc_roundtrip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = _bootstrap(tmp_path / "h")
    monkeypatch.setattr(host_handlers, "_resolve_home", lambda profile: home)
    _count_llm(monkeypatch, "Spoken version.")

    srv = host_server.Server(home=home)
    host_config.register(srv)
    resp = await srv._dispatch({
        "id": "vs",
        "method": "host.voice.script",
        "params": {"profile": "doc", "text": "Hello ✅ world"},
    })

    assert resp["result"] == {"script": "Spoken version.", "source": "llm"}


@pytest.mark.asyncio
async def test_voice_script_rpc_requires_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = _bootstrap(tmp_path / "h")
    monkeypatch.setattr(host_handlers, "_resolve_home", lambda profile: home)

    srv = host_server.Server(home=home)
    host_config.register(srv)
    resp = await srv._dispatch({
        "id": "vs",
        "method": "host.voice.script",
        "params": {"profile": "doc", "text": "  "},
    })

    assert resp["error"]["code"] == -32602
