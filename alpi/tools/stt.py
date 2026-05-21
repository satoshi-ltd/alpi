"""stt — transcribe audio to text via faster-whisper (local, no API key)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from alpi import config as cfg_mod
from alpi.home import get_home
from alpi.tools._paths import resolve_path
from alpi.tools import _state as tool_state_mod
from alpi.tools.base import Tool, ToolResult


AUDIO_EXTENSIONS = {
    ".wav", ".mp3", ".m4a", ".mp4", ".ogg", ".oga", ".opus",
    ".flac", ".webm", ".aac", ".wma",
}

MAX_BYTES = 200 * 1024 * 1024

_WORKER_SCRIPT = """
import json, sys
from faster_whisper import WhisperModel
model_name, audio_path, language = sys.argv[1], sys.argv[2], sys.argv[3]
model = WhisperModel(model_name, device='cpu', compute_type='int8')
segs, info = model.transcribe(
    audio_path,
    language=language or None,
    vad_filter=True,
)
text = ' '.join(s.text.strip() for s in segs).strip()
json.dump({'text': text, 'language': info.language}, sys.stdout)
"""


def _transcribe(audio_path: Path, model_name: str, language: str) -> tuple[dict | None, str]:
    try:
        proc = subprocess.run(
            [sys.executable, "-c", _WORKER_SCRIPT, model_name, str(audio_path), language],
            capture_output=True, text=True, timeout=600,
        )
    except subprocess.TimeoutExpired:
        return None, "whisper worker timed out after 10 minutes"
    if proc.returncode != 0:
        tail = (proc.stderr or "").strip().splitlines()[-1:] or [""]
        return None, tail[0]
    try:
        return json.loads(proc.stdout), ""
    except json.JSONDecodeError:
        return None, f"worker output not JSON: {proc.stdout[:200]!r}"


class Stt(Tool):
    name = "stt"
    description = (
        "Transcribe audio to text using faster-whisper locally. Use when "
        "the user shares a voice note or audio file and you need the "
        "transcript before replying. No API key, no cloud calls — runs on "
        "CPU. First call downloads the model weights (~150 MB for `base`) "
        "into `~/.cache/huggingface/`; subsequent calls are fast. "
        "Supported: WAV, MP3, M4A, OGG, Opus, FLAC, WebM, AAC. Language "
        "auto-detected; pass `language` (ISO code) only to override."
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Local audio file path (relative to workspace or absolute).",
            },
            "language": {
                "type": "string",
                "description": "Optional ISO language code ('en', 'es', ...). Default: auto-detect.",
            },
        },
        "required": ["path"],
    }

    @classmethod
    def check(cls) -> tuple[bool, str]:
        import importlib.util
        if importlib.util.find_spec("faster_whisper") is None:
            return False, "faster-whisper not installed"
        return True, ""

    def run(self, path: str, language: str = "") -> ToolResult:
        try:
            resolved = resolve_path(path)
        except ValueError as e:
            return ToolResult(ok=False, output="", error=str(e))
        if not resolved.exists():
            return ToolResult(ok=False, output="", error=f"no such file: {path}")
        if not resolved.is_file():
            return ToolResult(ok=False, output="", error=f"not a file: {path}")
        if resolved.suffix.lower() not in AUDIO_EXTENSIONS:
            return ToolResult(
                ok=False, output="",
                error=(
                    f"not an audio extension ({resolved.suffix}). "
                    f"Supported: {sorted(AUDIO_EXTENSIONS)}"
                ),
            )
        size = resolved.stat().st_size
        if size > MAX_BYTES:
            return ToolResult(
                ok=False, output="",
                error=f"audio too large ({size:,} bytes > {MAX_BYTES:,})",
            )

        cfg = cfg_mod.load(get_home())
        model_name = (cfg.tools.stt.model or "base").strip()
        lang = (language or cfg.tools.stt.language or "").strip()

        tool_state_mod.emit_state(f"transcribing ({model_name})…")
        data, err = _transcribe(resolved, model_name, lang)
        if err:
            return ToolResult(ok=False, output="", error=f"transcription failed: {err}")
        text = (data or {}).get("text", "").strip()
        detected = (data or {}).get("language", "")
        if not text:
            return ToolResult(ok=True, output=f"(no speech detected; lang={detected})")
        return ToolResult(ok=True, output=f"[lang={detected}]\n{text}")


TOOL = Stt
