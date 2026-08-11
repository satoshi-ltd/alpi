"""RT.1 — provider stale-call hardening: first-byte / idle watchdogs + jittered retries."""

from __future__ import annotations

import threading
from types import SimpleNamespace as NS

import pytest

import alpi.llm as llm


def _chunk(text: str = ""):
    return NS(
        choices=[NS(
            delta=NS(content=text, reasoning_content=None, reasoning=None, tool_calls=None),
            finish_reason=None,
        )],
        usage=None,
    )


def _rt(**over):
    base = dict(first_byte_timeout_s=0.1, stream_idle_timeout_s=0.1, max_retries=2, retry_backoff_s=0.0)
    base.update(over)
    return NS(**base)


@pytest.fixture(autouse=True)
def _fast(monkeypatch):
    monkeypatch.setattr(llm, "_compute_cost_detail", lambda *a, **k: (0.0, "none"))
    monkeypatch.setattr(llm, "_backoff_sleep", lambda *a, **k: None)


def _stalling_iter():
    def gen():
        threading.Event().wait(1.0)  # outlives the watchdog window
        yield from ()  # generator that produces nothing after the stall
    return gen()


# ---------- classification ----------


def test_is_transient_classification():
    class Timeout(Exception):
        pass

    assert llm._is_transient(llm.ProviderStalled("x"))
    assert llm._is_transient(Timeout())
    assert llm._is_transient(NS_exc(503))
    assert llm._is_transient(NS_exc(429))
    assert not llm._is_transient(NS_exc(401))
    assert not llm._is_transient(NS_exc(400))
    assert not llm._is_transient(ValueError("plain"))


def NS_exc(code):
    e = Exception("boom")
    e.status_code = code
    return e


# ---------- happy path ----------


def test_stream_yields_then_final(monkeypatch):
    monkeypatch.setattr(llm, "_completion_silenced", lambda kw: iter([_chunk("hello"), _chunk(" world")]))
    out = list(llm.stream(model="x", messages=[], rt=_rt()))
    assert "".join(c.get("text_delta", "") for c in out if not c.get("final")) == "hello world"
    assert out[-1]["final"] is True


# ---------- retries ----------


def test_first_byte_stall_retries_then_succeeds(monkeypatch):
    calls = {"n": 0}

    def fake(kw):
        calls["n"] += 1
        return _stalling_iter() if calls["n"] == 1 else iter([_chunk("ok")])

    monkeypatch.setattr(llm, "_completion_silenced", fake)
    out = list(llm.stream(model="x", messages=[], rt=_rt()))
    assert calls["n"] == 2
    assert "".join(c.get("text_delta", "") for c in out if not c.get("final")) == "ok"


def test_transient_error_retries_then_succeeds(monkeypatch):
    calls = {"n": 0}

    def fake(kw):
        calls["n"] += 1
        if calls["n"] == 1:
            raise NS_exc(503)
        return iter([_chunk("recovered")])

    monkeypatch.setattr(llm, "_completion_silenced", fake)
    out = list(llm.stream(model="x", messages=[], rt=_rt()))
    assert calls["n"] == 2
    assert "".join(c.get("text_delta", "") for c in out if not c.get("final")) == "recovered"


def test_retries_exhausted_raises_stalled(monkeypatch):
    calls = {"n": 0}

    def fake(kw):
        calls["n"] += 1
        return _stalling_iter()

    monkeypatch.setattr(llm, "_completion_silenced", fake)
    with pytest.raises(llm.ProviderStalled):
        list(llm.stream(model="x", messages=[], rt=_rt(max_retries=2)))
    assert calls["n"] == 3  # initial + 2 retries


# ---------- no retry once committed / on permanent errors ----------


def test_permanent_error_is_not_retried(monkeypatch):
    calls = {"n": 0}

    def fake(kw):
        calls["n"] += 1
        raise NS_exc(401)

    monkeypatch.setattr(llm, "_completion_silenced", fake)
    with pytest.raises(Exception):
        list(llm.stream(model="x", messages=[], rt=_rt()))
    assert calls["n"] == 1


def test_mid_stream_stall_surfaces_without_retry(monkeypatch):
    calls = {"n": 0}

    def fake(kw):
        calls["n"] += 1

        def gen():
            yield _chunk("partial")
            threading.Event().wait(1.0)  # stall after content already streamed

        return gen()

    monkeypatch.setattr(llm, "_completion_silenced", fake)
    got = []
    with pytest.raises(llm.ProviderStalled):
        for c in llm.stream(model="x", messages=[], rt=_rt()):
            got.append(c)
    assert calls["n"] == 1  # no retry once a token reached the consumer
    assert any(c.get("text_delta") == "partial" for c in got)


# ---------- config knobs ----------


def test_provider_stall_reason_lands_in_run_ledger(tmp_home_no_env, monkeypatch):
    from alpi import config, home, memory, run_ledger
    from alpi.engine import Engine

    home.ensure_home(tmp_home_no_env)
    config.seed_defaults(tmp_home_no_env)
    memory.MemoryStore(tmp_home_no_env).seed_defaults()
    (tmp_home_no_env / "memories" / "AGENT.md").write_text("# Identity\nYou are alpi.\n")

    def boom(messages, tools, **kwargs):
        raise llm.ProviderStalled("provider sent no first token within 300s")
        yield  # generator

    monkeypatch.setattr("alpi.llm.stream", boom)

    cfg = config.load(tmp_home_no_env)
    Engine(home=tmp_home_no_env, cfg=cfg).run_turn("hola", emit=lambda _e: None)

    rows = run_ledger.read(tmp_home_no_env, kind="agent")
    assert rows, "a run record should be written even when the turn errors"
    assert rows[0]["outcome"] == "error"
    assert "first token" in (rows[0]["output_tail"] or "")


def test_runtime_config_defaults_override_and_roundtrip(tmp_path):
    from alpi import config as cfg_mod

    c = cfg_mod.load(tmp_path)
    assert c.runtime.first_byte_timeout_s == 300.0
    assert c.runtime.stream_idle_timeout_s == 120.0
    assert c.runtime.max_retries == 2

    (tmp_path / "config.yaml").write_text(
        "runtime:\n  first_byte_timeout_s: 30\n  stream_idle_timeout_s: 0\n  max_retries: 0\n"
    )
    c2 = cfg_mod.load(tmp_path)
    assert c2.runtime.first_byte_timeout_s == 30.0
    assert c2.runtime.stream_idle_timeout_s == 0.0  # 0 disables the watchdog
    assert c2.runtime.max_retries == 0
    assert c2.runtime.retry_backoff_s == 1.5  # untouched default

    cfg_mod.save(c2)
    c3 = cfg_mod.load(tmp_path)
    assert c3.runtime.first_byte_timeout_s == 30.0
    assert c3.runtime.stream_idle_timeout_s == 0.0
    assert c3.runtime.max_retries == 0
