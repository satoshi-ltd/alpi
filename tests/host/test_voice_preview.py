"""host.voice.preview — daemon-side TTS for mobile/desktop voice picker preview."""

from __future__ import annotations

import base64
from pathlib import Path

import pytest

from alpi import config as cfg_mod
from alpi.host import config as host_config
from alpi.host import handlers as host_handlers
from alpi.host import server as host_server


def _bootstrap(home: Path) -> Path:
    home.mkdir()
    cfg = cfg_mod.Config(home=home, model="openai/gpt-5.4-mini")
    cfg_mod.save(cfg)
    return home


@pytest.mark.asyncio
async def test_voice_preview_returns_base64_audio(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = _bootstrap(tmp_path / "h")
    monkeypatch.setattr(host_handlers, "_resolve_home", lambda profile: home)

    # Stub edge_tts at the helper layer — we don't want real network calls in tests.
    async def fake_synth(text, voice, out_path, rate="", pitch=""):  # noqa: ARG001
        Path(out_path).write_bytes(b"FAKE-MP3-BYTES")

    monkeypatch.setattr("alpi.tools.tts._synthesize", fake_synth)

    srv = host_server.Server(home=home)
    host_config.register(srv)
    resp = await srv._dispatch({
        "id": "vp",
        "method": "host.voice.preview",
        "params": {"voice_id": "es-MX-DaliaNeural"},
    })

    result = resp["result"]
    assert result["voice_id"] == "es-MX-DaliaNeural"
    assert result["mime"] == "audio/mpeg"
    # Default phrase picks "es" branch because the voice id starts with es-.
    assert result["text"] == "Hola, soy Alpi."
    assert base64.b64decode(result["audio_b64"]) == b"FAKE-MP3-BYTES"


@pytest.mark.asyncio
async def test_voice_preview_rejects_missing_voice_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = _bootstrap(tmp_path / "h")
    monkeypatch.setattr(host_handlers, "_resolve_home", lambda profile: home)

    srv = host_server.Server(home=home)
    host_config.register(srv)
    resp = await srv._dispatch({
        "id": "vp",
        "method": "host.voice.preview",
        "params": {},
    })

    assert "error" in resp
    assert resp["error"]["data"]["detail"] == "voice_id required"


@pytest.mark.asyncio
async def test_voice_preview_surfaces_tts_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = _bootstrap(tmp_path / "h")
    monkeypatch.setattr(host_handlers, "_resolve_home", lambda profile: home)

    async def boom(text, voice, out_path, rate="", pitch=""):  # noqa: ARG001
        raise RuntimeError("edge_tts dead")

    monkeypatch.setattr("alpi.tools.tts._synthesize", boom)

    srv = host_server.Server(home=home)
    host_config.register(srv)
    resp = await srv._dispatch({
        "id": "vp",
        "method": "host.voice.preview",
        "params": {"voice_id": "en-US-AriaNeural"},
    })

    assert "error" in resp
    assert "edge_tts dead" in resp["error"]["data"]["detail"]


@pytest.mark.asyncio
async def test_voice_preview_handles_missing_edge_tts_cleanly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing edge_tts → controlled `tts-unavailable` handler error, not a bubbled ImportError."""
    home = _bootstrap(tmp_path / "h")
    monkeypatch.setattr(host_handlers, "_resolve_home", lambda profile: home)

    # Handler imports edge_tts lazily; patching sys.modules forces the ImportError path.
    import sys
    monkeypatch.setitem(sys.modules, "edge_tts", None)

    srv = host_server.Server(home=home)
    host_config.register(srv)
    resp = await srv._dispatch({
        "id": "vp",
        "method": "host.voice.preview",
        "params": {"voice_id": "en-US-AriaNeural"},
    })

    assert "error" in resp
    assert resp["error"]["message"] == "tts-unavailable"
    assert "edge_tts" in resp["error"]["data"]["detail"]


@pytest.mark.asyncio
async def test_voice_preview_caps_text_length(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Text past `_VOICE_PREVIEW_MAX_CHARS` is rejected before synthesis runs (DoS guard)."""
    home = _bootstrap(tmp_path / "h")
    monkeypatch.setattr(host_handlers, "_resolve_home", lambda profile: home)

    synth_calls = []

    async def fake_synth(text, voice, out_path, rate="", pitch=""):  # noqa: ARG001
        synth_calls.append(text)
        Path(out_path).write_bytes(b"x")

    monkeypatch.setattr("alpi.tools.tts._synthesize", fake_synth)

    srv = host_server.Server(home=home)
    host_config.register(srv)
    resp = await srv._dispatch({
        "id": "vp",
        "method": "host.voice.preview",
        "params": {
            "voice_id": "en-US-AriaNeural",
            "text": "a" * 281,  # one char past the cap
        },
    })

    assert "error" in resp
    assert "exceeds" in resp["error"]["data"]["detail"]
    assert synth_calls == []  # rejection must happen before synth fires
