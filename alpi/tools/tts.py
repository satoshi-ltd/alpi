"""tts — synthesize speech from text via Edge TTS (Microsoft, local, no API key)."""

from __future__ import annotations

import asyncio
import hashlib
import os
import platform
import shutil
import subprocess
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


def _cache_key(text: str, voice: str, rate: str, pitch: str, fmt: str) -> str:
    blob = f"{voice}\x00{rate}\x00{pitch}\x00{fmt}\x00{text}".encode("utf-8")
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


def _convert_mp3_to_ogg(src: Path, dst: Path) -> tuple[bool, str]:
    if shutil.which("ffmpeg") is None:
        return False, "ffmpeg not installed"
    try:
        proc = subprocess.run(
            [
                "ffmpeg", "-y", "-loglevel", "error",
                "-i", str(src),
                "-c:a", "libopus", "-b:a", "32k",
                "-ac", "1", "-ar", "48000",
                "-vn", str(dst),
            ],
            capture_output=True, text=True, timeout=60,
        )
    except subprocess.TimeoutExpired:
        return False, "ffmpeg timed out"
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-1:] or [""]
        return False, f"ffmpeg exited {proc.returncode}: {tail[0]}"
    return True, "ffmpeg"


def _player_cmd() -> list[str] | None:
    system = platform.system()
    if system == "Darwin" and shutil.which("afplay"):
        return ["afplay"]
    if system == "Linux":
        for name in ("paplay", "aplay", "ffplay"):
            if shutil.which(name):
                if name == "ffplay":
                    return ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet"]
                return [name]
    if system == "Windows":
        return [
            "powershell", "-NoProfile", "-Command",
            "(New-Object Media.SoundPlayer $args[0]).PlaySync()",
        ]
    return None


def _play_blocking(path: Path) -> tuple[bool, str]:
    cmd = _player_cmd()
    if cmd is None:
        return False, f"no audio player found on {platform.system()}"
    try:
        proc = subprocess.run([*cmd, str(path)], capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        return False, "player timed out"
    except FileNotFoundError as e:
        return False, f"player not found: {e}"
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-1:] or [""]
        return False, f"player exited {proc.returncode}: {tail[0]}"
    return True, cmd[0]


class Tts(Tool):
    name = "tts"
    description = (
        "Synthesize speech from text (Microsoft Edge TTS, free, no API key). "
        "Autoplays locally when `tools.tts.autoplay` is on (default). "
        "Returns the audio file path.\n"
        "\n"
        "Pass `voice` to override the configured default for one call "
        "(e.g. `voice=\"es-ES-ElviraNeural\"`). Rate and pitch are NOT "
        "tool args — they live in `tools.tts.rate` / `tools.tts.pitch` in "
        "config. If the user asks to change speed or pitch, tell them to "
        "edit config; don't try to pass it here.\n"
        "\n"
        "Text limit: 1000 chars. Output format is picked automatically.\n"
        "\n"
        "If the user asks you to deliver the audio to an external chat "
        "(e.g. 'send it as a voice note on Telegram'), chain `send_message"
        "(attachment=<path>)` after this tool. Otherwise autoplay is the "
        "delivery — no chain needed.\n"
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
        is_gateway = os.environ.get("ALPI_GATEWAY") == "1"
        fmt = "ogg" if is_gateway else "mp3"

        cache = _cache_dir(home)
        key = _cache_key(text, chosen_voice, chosen_rate, chosen_pitch, fmt)
        out_path = cache / f"{key}.{fmt}"

        if not (out_path.exists() and out_path.stat().st_size > 0):
            tool_state_mod.emit_state(f"synthesizing ({chosen_voice})…")
            mp3_tmp = cache / f"{key}.mp3" if fmt == "ogg" else out_path
            try:
                asyncio.run(_synthesize(
                    text, chosen_voice, mp3_tmp,
                    rate=chosen_rate, pitch=chosen_pitch,
                ))
            except Exception as e:  # noqa: BLE001
                if mp3_tmp.exists():
                    try: mp3_tmp.unlink()
                    except OSError: pass
                return ToolResult(ok=False, output="", error=f"edge-tts failed: {e}")
            if not mp3_tmp.exists() or mp3_tmp.stat().st_size == 0:
                return ToolResult(ok=False, output="", error="edge-tts produced empty file")
            if fmt == "ogg":
                tool_state_mod.emit_state("converting to ogg…")
                ok_conv, detail = _convert_mp3_to_ogg(mp3_tmp, out_path)
                if not ok_conv:
                    return ToolResult(
                        ok=False, output="",
                        error=f"ogg conversion failed ({detail})",
                    )
                try: mp3_tmp.unlink()
                except OSError: pass

        if is_gateway or not cfg.tools.tts.autoplay:
            return ToolResult(ok=True, output=f"saved → {out_path}")

        tool_state_mod.emit_state("playing…")
        ok, detail = _play_blocking(out_path)
        if ok:
            return ToolResult(ok=True, output=f"played via {detail} → {out_path}")
        return ToolResult(ok=True, output=f"saved → {out_path} (autoplay failed: {detail})")


TOOL = Tts
