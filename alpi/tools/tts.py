"""tts — synthesize speech from text via Edge TTS (Microsoft, local, no API key)."""

from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path

from alpi import config as cfg_mod
from alpi.home import get_home
from alpi.tools import _state as tool_state_mod
from alpi.tools.base import Tool, ToolResult


MAX_CHARS = 1000


def _cache_dir(home: Path) -> Path:
    p = home / "cache" / "tts"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _cache_key(text: str, voice: str, rate: str, pitch: str) -> str:
    blob = f"{voice}\x00{rate}\x00{pitch}\x00mp3\x00{text}".encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


def _normalize_prosody(raw: str) -> str:
    r = (raw or "").strip()
    if not r or r[0] in "+-":
        return r
    return "+" + r


async def _synthesize(text: str, voice: str, out_path: Path,
                      rate: str = "", pitch: str = "") -> None:
    import edge_tts
    kwargs: dict[str, str] = {}
    if rate:
        kwargs["rate"] = rate
    if pitch:
        kwargs["pitch"] = pitch
    communicate = edge_tts.Communicate(text, voice, **kwargs)
    await communicate.save(str(out_path))


class Tts(Tool):
    name = "tts"
    description = (
        "Synthesize speech from text (Microsoft Edge TTS, free, no API key). "
        "Returns the path to a cached MP3 — the daemon does NOT play audio.\n"
        "\n"
        "Pass `voice` to override the configured default for one call "
        "(e.g. `voice=\"es-ES-ElviraNeural\"`). Rate and pitch are NOT "
        "tool args — they live in `tools.tts.rate` / `tools.tts.pitch` in "
        "config. If the user asks to change speed or pitch, tell them to "
        "edit config; don't try to pass it here.\n"
        "\n"
        "Text limit: 1000 chars.\n"
        "\n"
        "Delivery is up to the caller: the alpi mobile / desktop apps stream "
        "the file directly; to send it to someone else attach it with the "
        "`email` tool after this tool.\n"
        "\n"
        "After delivering audio, don't restate the path, format, or tool "
        "result in your follow-up text."
    )
    parameters = {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "The text to speak. Plain text only.",
            },
            "voice": {
                "type": "string",
                "description": "Edge TTS voice id (e.g. 'es-ES-ElviraNeural'). Defaults to `tools.tts.voice`.",
            },
        },
        "required": ["text"],
    }

    @classmethod
    def check(cls) -> tuple[bool, str]:
        import importlib.util
        if importlib.util.find_spec("edge_tts") is None:
            return False, "edge-tts not installed"
        return True, ""

    def run(self, text: str, voice: str = "") -> ToolResult:
        if not text or not text.strip():
            return ToolResult(ok=False, output="", error="text is empty")
        from alpi.tools._sandbox import require_network
        blocked = require_network("tts")
        if blocked is not None:
            return blocked
        if len(text) > MAX_CHARS:
            return ToolResult(
                ok=False, output="",
                error=(
                    f"text too long ({len(text):,} chars > {MAX_CHARS:,}). "
                    f"Summarise or split — tts produces ~1-minute clips only."
                ),
            )

        home = get_home()
        cfg = cfg_mod.load(home)
        chosen_voice = (voice or cfg.tools.tts.voice).strip()
        chosen_rate = _normalize_prosody(cfg.tools.tts.rate)
        chosen_pitch = _normalize_prosody(cfg.tools.tts.pitch)

        cache = _cache_dir(home)
        key = _cache_key(text, chosen_voice, chosen_rate, chosen_pitch)
        out_path = cache / f"{key}.mp3"

        if not (out_path.exists() and out_path.stat().st_size > 0):
            tool_state_mod.emit_state(f"synthesizing ({chosen_voice})…")
            try:
                asyncio.run(_synthesize(
                    text, chosen_voice, out_path,
                    rate=chosen_rate, pitch=chosen_pitch,
                ))
            except Exception as e:  # noqa: BLE001
                if out_path.exists():
                    try: out_path.unlink()
                    except OSError: pass
                return ToolResult(ok=False, output="", error=f"edge-tts failed: {e}")
            if not out_path.exists() or out_path.stat().st_size == 0:
                return ToolResult(ok=False, output="", error="edge-tts produced empty file")

        return ToolResult(ok=True, output=f"saved → {out_path}")


TOOL = Tts
