"""Telegram voice-note inbound — getFile + download + stt chain."""

from __future__ import annotations

from pathlib import Path

import pytest

from alpi.gateway.platforms import telegram as tg


class _FakeResp:
    def __init__(self, status: int, data: dict | None = None, body: bytes = b""):
        self.status_code = status
        self._data = data or {}
        self.content = body

    def json(self) -> dict:
        return self._data


class _FakeClient:
    def __init__(self, responses: list) -> None:
        self._responses = list(responses)
        self.calls: list = []

    async def get(self, url, params=None, timeout=None):  # noqa: A002
        self.calls.append({"url": url, "params": params})
        return self._responses.pop(0)


pytestmark = pytest.mark.asyncio


async def test_transcribe_voice_happy_path(monkeypatch, tmp_path: Path) -> None:
    client = _FakeClient([
        _FakeResp(200, {"ok": True, "result": {"file_path": "voice/abc.oga"}}),
        _FakeResp(200, body=b"FAKE-OGG-BYTES"),
    ])

    class _FakeStt:
        def run(self, path: str):
            from alpi.tools.base import ToolResult
            _FakeStt.received_path = path
            return ToolResult(ok=True, output="[lang=es]\nhola mundo")

    import alpi.tools.stt as stt_mod
    monkeypatch.setattr(stt_mod, "Stt", _FakeStt)

    voice = {"file_id": "AgIzz"}
    result = await tg._transcribe_voice(client, "TK", tmp_path, voice)

    assert result == "hola mundo"
    assert len(client.calls) == 2
    assert "getFile" in client.calls[0]["url"]
    assert "file/bot" in client.calls[1]["url"]
    dest = tmp_path / "cache" / "inbound" / "AgIzz.oga"
    assert dest.exists() and dest.read_bytes() == b"FAKE-OGG-BYTES"
    assert _FakeStt.received_path == str(dest)


async def test_transcribe_voice_getfile_not_ok(monkeypatch, tmp_path: Path) -> None:
    client = _FakeClient([_FakeResp(200, {"ok": False, "description": "file not found"})])
    voice = {"file_id": "x"}
    result = await tg._transcribe_voice(client, "TK", tmp_path, voice)
    assert result == ""


async def test_transcribe_voice_download_http_error(monkeypatch, tmp_path: Path) -> None:
    client = _FakeClient([
        _FakeResp(200, {"ok": True, "result": {"file_path": "voice/x.oga"}}),
        _FakeResp(500, body=b""),
    ])
    voice = {"file_id": "x"}
    result = await tg._transcribe_voice(client, "TK", tmp_path, voice)
    assert result == ""


async def test_transcribe_voice_stt_failure(monkeypatch, tmp_path: Path) -> None:
    client = _FakeClient([
        _FakeResp(200, {"ok": True, "result": {"file_path": "voice/x.oga"}}),
        _FakeResp(200, body=b"bytes"),
    ])

    class _BadStt:
        def run(self, path: str):
            from alpi.tools.base import ToolResult
            return ToolResult(ok=False, output="", error="whisper crashed")

    import alpi.tools.stt as stt_mod
    monkeypatch.setattr(stt_mod, "Stt", _BadStt)

    voice = {"file_id": "x"}
    result = await tg._transcribe_voice(client, "TK", tmp_path, voice)
    assert result == ""


async def test_transcribe_voice_missing_file_id(monkeypatch, tmp_path: Path) -> None:
    client = _FakeClient([])
    result = await tg._transcribe_voice(client, "TK", tmp_path, {})
    assert result == ""
    assert client.calls == []
