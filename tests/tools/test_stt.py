"""Tests for the stt tool — subprocess worker mocked."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from alpi.tools import stt as stt_mod
from alpi.tools.stt import Stt


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path: Path) -> None:
    import alpi.home as home_mod
    monkeypatch.setattr(home_mod, "_ROOT", tmp_path)


def _patch_transcribe(monkeypatch, text: str = "hello world",
                       language: str = "en", err: str = ""):
    captured: dict = {}

    def _fake(audio_path: Path, model_name: str, lang: str) -> tuple[dict | None, str]:
        captured["audio"] = audio_path
        captured["model"] = model_name
        captured["language"] = lang
        if err:
            return None, err
        return {"text": text, "language": language}, ""

    monkeypatch.setattr(stt_mod, "_transcribe", _fake)
    return captured


def _make_audio(tmp_path: Path, name: str = "clip.mp3") -> Path:
    p = tmp_path / name
    p.write_bytes(b"\x00" * 1024)
    return p


def test_rejects_missing_file(tmp_path: Path, monkeypatch) -> None:
    _patch_transcribe(monkeypatch)
    r = Stt().run(path=str(tmp_path / "nope.mp3"))
    assert not r.ok
    assert "no such file" in (r.error or "").lower()


def test_rejects_non_audio_extension(tmp_path: Path, monkeypatch) -> None:
    _patch_transcribe(monkeypatch)
    junk = tmp_path / "doc.pdf"
    junk.write_bytes(b"%PDF-")
    r = Stt().run(path=str(junk))
    assert not r.ok
    assert "not an audio extension" in (r.error or "").lower()


def test_transcribes_and_includes_language(tmp_path: Path, monkeypatch) -> None:
    captured = _patch_transcribe(monkeypatch, text="hello world", language="en")
    audio = _make_audio(tmp_path)
    r = Stt().run(path=str(audio))
    assert r.ok
    assert "hello world" in r.output
    assert "[lang=en]" in r.output
    assert captured["model"] == "base"


def test_language_override_passed_through(tmp_path: Path, monkeypatch) -> None:
    captured = _patch_transcribe(monkeypatch, language="es")
    audio = _make_audio(tmp_path)
    r = Stt().run(path=str(audio), language="es")
    assert r.ok
    assert captured["language"] == "es"


def test_empty_transcription(tmp_path: Path, monkeypatch) -> None:
    _patch_transcribe(monkeypatch, text="", language="en")
    audio = _make_audio(tmp_path)
    r = Stt().run(path=str(audio))
    assert r.ok
    assert "no speech detected" in r.output


def test_worker_failure(tmp_path: Path, monkeypatch) -> None:
    _patch_transcribe(monkeypatch, err="ImportError: faster_whisper not found")
    audio = _make_audio(tmp_path)
    r = Stt().run(path=str(audio))
    assert not r.ok
    assert "transcription failed" in (r.error or "").lower()
    assert "faster_whisper" in (r.error or "")
