"""Tests for the tts tool — edge-tts mocked, no network."""

from __future__ import annotations

from pathlib import Path

import pytest

from alpi.tools import tts as tts_mod
from alpi.tools.tts import Tts


@pytest.fixture(autouse=True)
def _isolate_home(monkeypatch, tmp_path: Path) -> None:
    import alpi.home as home_mod
    monkeypatch.setattr(home_mod, "_ROOT", tmp_path)
    monkeypatch.setattr(tts_mod, "_play_blocking", lambda p: (True, "stub"))
    monkeypatch.delenv("ALPI_GATEWAY", raising=False)


def _make_fake_synthesize(calls: list, fail: bool = False, empty: bool = False):
    async def _fake(text: str, voice: str, out_path: Path,
                    rate: str = "", pitch: str = "") -> None:
        calls.append({
            "text": text, "voice": voice, "out_path": out_path,
            "rate": rate, "pitch": pitch,
        })
        if fail:
            raise RuntimeError("simulated edge-tts failure")
        if empty:
            out_path.write_bytes(b"")
        else:
            out_path.write_bytes(b"\xff\xfbfake-mp3")
    return _fake


def test_rejects_empty_text() -> None:
    r = Tts().run(text="   ")
    assert not r.ok
    assert "empty" in (r.error or "").lower()


def test_writes_to_cache_and_autoplays(monkeypatch) -> None:
    calls: list = []
    monkeypatch.setattr(tts_mod, "_synthesize", _make_fake_synthesize(calls))
    r = Tts().run(text="hola mundo")
    assert r.ok
    assert "played via stub" in r.output
    assert r.output.endswith(".mp3")
    assert calls[0]["voice"] == "en-US-AriaNeural"


def test_cache_hit_skips_synthesis(monkeypatch) -> None:
    calls: list = []
    monkeypatch.setattr(tts_mod, "_synthesize", _make_fake_synthesize(calls))
    Tts().run(text="misma frase")
    Tts().run(text="misma frase")
    assert len(calls) == 1


def test_different_voice_different_cache(monkeypatch) -> None:
    calls: list = []
    monkeypatch.setattr(tts_mod, "_synthesize", _make_fake_synthesize(calls))
    Tts().run(text="same", voice="es-ES-AlvaroNeural")
    Tts().run(text="same", voice="en-US-GuyNeural")
    assert len(calls) == 2


def test_refuses_oversized_text(monkeypatch) -> None:
    calls: list = []
    monkeypatch.setattr(tts_mod, "_synthesize", _make_fake_synthesize(calls))
    r = Tts().run(text="x" * 1001)
    assert not r.ok
    assert "too long" in (r.error or "").lower()
    assert calls == []


def test_rate_pitch_come_from_config(monkeypatch, tmp_path: Path) -> None:
    calls: list = []
    monkeypatch.setattr(tts_mod, "_synthesize", _make_fake_synthesize(calls))
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        "tools:\n  tts:\n    rate: '20%'\n    pitch: '-5Hz'\n"
    )
    Tts().run(text="hola")
    assert calls[0]["rate"] == "+20%"
    assert calls[0]["pitch"] == "-5Hz"


def test_tui_produces_mp3(monkeypatch) -> None:
    calls: list = []
    monkeypatch.setattr(tts_mod, "_synthesize", _make_fake_synthesize(calls))
    r = Tts().run(text="tui")
    assert r.output.endswith(".mp3")


def test_gateway_produces_ogg(monkeypatch, tmp_path: Path) -> None:
    calls: list = []
    monkeypatch.setattr(tts_mod, "_synthesize", _make_fake_synthesize(calls))
    monkeypatch.setattr(
        tts_mod, "_convert_mp3_to_ogg",
        lambda src, dst: (dst.write_bytes(b"OggS"), (True, "ffmpeg"))[1],
    )
    monkeypatch.setenv("ALPI_GATEWAY", "1")
    r = Tts().run(text="gw")
    assert r.ok, r.error
    assert r.output.endswith(".ogg")


def test_gateway_ogg_conversion_failure(monkeypatch) -> None:
    calls: list = []
    monkeypatch.setattr(tts_mod, "_synthesize", _make_fake_synthesize(calls))
    monkeypatch.setattr(
        tts_mod, "_convert_mp3_to_ogg",
        lambda src, dst: (False, "ffmpeg not installed"),
    )
    monkeypatch.setenv("ALPI_GATEWAY", "1")
    r = Tts().run(text="hi")
    assert not r.ok
    assert "ffmpeg not installed" in (r.error or "")


def test_synthesis_failure_reported(monkeypatch) -> None:
    calls: list = []
    monkeypatch.setattr(
        tts_mod, "_synthesize", _make_fake_synthesize(calls, fail=True),
    )
    r = Tts().run(text="boom")
    assert not r.ok
    assert "edge-tts failed" in (r.error or "")


def test_empty_output_reported(monkeypatch) -> None:
    calls: list = []
    monkeypatch.setattr(
        tts_mod, "_synthesize", _make_fake_synthesize(calls, empty=True),
    )
    r = Tts().run(text="hi", voice="bogus")
    assert not r.ok
    assert "empty" in (r.error or "").lower()


def test_autoplay_failure_still_ok(monkeypatch) -> None:
    calls: list = []
    monkeypatch.setattr(tts_mod, "_synthesize", _make_fake_synthesize(calls))
    monkeypatch.setattr(tts_mod, "_play_blocking", lambda p: (False, "no speaker"))
    r = Tts().run(text="silent")
    assert r.ok
    assert "autoplay failed" in r.output
