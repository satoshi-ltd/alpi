from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

SCRIPT_MAX_CHARS = 600
_PROMPT_VERSION = 1

_EMOJI_RE = re.compile(
    "["
    "\U0001F000-\U0001FAFF"
    "\u2190-\u21FF"
    "\u2300-\u23FF"
    "\u2460-\u24FF"
    "\u2500-\u25FF"
    "\u2600-\u27BF"
    "\u2B00-\u2BFF"
    "\u3030\u303D\u203C\u2049"
    "\uFE0F\u200D\u20E3"
    "]+"
)

_SYSTEM_PROMPT = (
    "Turn the message below into a spoken BRIEFING for text-to-speech, "
    "under one minute of audio. The listener has the full text on screen — "
    "the audio is the executive summary, never a full read-out.\n"
    "Rules:\n"
    "- Same language as the message.\n"
    "- Natural conversational prose, as if briefing the listener aloud.\n"
    "- Lead with the outcome, then the 2-3 points that matter most; drop "
    "everything else.\n"
    "- No emojis, no markdown, no bullet points, no headings.\n"
    "- Never spell out URLs, file paths, hashes or raw code; mention the site "
    "or file by name and describe what code does in one short clause.\n"
    f"- At most {SCRIPT_MAX_CHARS - 100} characters. Output ONLY the script."
)

_MAX_INPUT_CHARS = 8000
_INPUT_HEAD_CHARS = 5000


def speakable_fallback(text: str) -> str:
    s = str(text or "")
    s = re.sub(r"```[\s\S]*?```", " ", s)
    s = re.sub(r"`([^`]+)`", r"\1", s)
    s = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", s)
    s = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", s)
    s = re.sub(r"https?://(?:www\.)?([^\s/)]+)\S*", r"\1", s)
    s = re.sub(r"^\s{0,3}#{1,6}\s+", "", s, flags=re.M)
    s = re.sub(r"^\s{0,3}>\s?", "", s, flags=re.M)
    s = re.sub(r"^\s*[-*+]\s+", "", s, flags=re.M)
    s = re.sub(r"^\s*\d+\.\s+", "", s, flags=re.M)
    s = re.sub(r"(\*\*|__)(.*?)\1", r"\2", s)
    s = re.sub(r"(\*|_)(.*?)\1", r"\2", s)
    s = re.sub(r"~~(.*?)~~", r"\1", s)
    s = _EMOJI_RE.sub(" ", s)
    s = s.replace("|", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return _truncate_spoken(s)


def _truncate_spoken(s: str) -> str:
    if len(s) <= SCRIPT_MAX_CHARS:
        return s
    cut = s.rfind(" ", 0, SCRIPT_MAX_CHARS)
    return s[: cut if cut > 0 else SCRIPT_MAX_CHARS].rstrip() + "…"


def _cache_dir(home: Path) -> Path:
    p = home / "cache" / "tts-script"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _cache_key(model: str, text: str) -> str:
    blob = f"{_PROMPT_VERSION}\x00{model}\x00{text}".encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


def _clip_input(text: str) -> str:
    if len(text) <= _MAX_INPUT_CHARS:
        return text
    # keep head AND tail — the conclusion of a long reply lives at the end and must reach the briefing
    tail = _MAX_INPUT_CHARS - _INPUT_HEAD_CHARS
    return f"{text[:_INPUT_HEAD_CHARS]}\n[…]\n{text[-tail:]}"


def script_for(home: Path, text: str) -> tuple[str, str]:
    """Fallback results are never cached — a transient LLM failure must retry on the next call."""
    from alpi import config as cfg_mod

    text = _clip_input(str(text or "").strip())
    cfg = cfg_mod.load(home)
    model = cfg.model or ""
    if not model:
        return speakable_fallback(text), "fallback"

    cache = _cache_dir(home)
    path = cache / f"{_cache_key(model, text)}.json"
    if path.exists():
        try:
            cached = json.loads(path.read_text(encoding="utf-8"))
            script = str(cached.get("script") or "").strip()
            if script:
                return script, "cache"
        except Exception:  # noqa: BLE001
            pass

    try:
        from alpi import ledger, llm
        ledger.check(home, cfg.budget)
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ]
        result = llm.complete(messages=messages, **cfg_mod.resolve_model(cfg))
        ledger.record(
            home,
            usd=float(getattr(result, "cost_usd", 0.0) or 0.0),
            tokens=int(getattr(result, "input_tokens", 0) or 0)
                  + int(getattr(result, "output_tokens", 0) or 0),
            tokens_in=int(getattr(result, "input_tokens", 0) or 0),
            tokens_out=int(getattr(result, "output_tokens", 0) or 0),
            cfg_budget=cfg.budget,
        )
        script = speakable_fallback(result.content or "")
        if not script:
            raise ValueError("empty script")
    except Exception:  # noqa: BLE001
        return speakable_fallback(text), "fallback"

    try:
        path.write_text(json.dumps({"script": script}), encoding="utf-8")
    except OSError:
        pass
    return script, "llm"
