"""Stable prompt-prefix assembly.

CL.1 — name and order every contributor to the LLM system prompt so the
rendered text stays byte-identical across calls. Providers that
auto-cache (OpenAI, Gemini, OpenRouter on supported models) hit for
free when the prefix is stable. For providers that need an explicit
marker (Anthropic Claude, Bedrock Claude, Vertex / AI Studio Gemini),
``cache_kwargs_for_model`` asks LiteLLM to inject ``cache_control`` on
``messages[0]`` via its native ``cache_control_injection_points`` —
Alpi never mutates provider payloads itself.

``build_parts(home, cfg)`` is the single source of truth for the
cacheable system-prompt content. ``Engine._build_system_prompt`` calls
it and joins the values in canonical ``PART_ORDER``. Per-turn volatile
additions (``# NOW``, workgroup ctx, skill keyword hint) are appended
as separate system messages by the engine and are NOT parts.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

PART_ORDER: tuple[str, ...] = (
    "agent_profile",
    "base_prompt",
    "env",
    "system_time",
    "surface",
    "guidance",
    "knowledge_rule",
    "skills_index",
    "user_md",
    "memory_md",
)


PLATFORM_HINTS: dict[str, str] = {
    "cron": (
        "# SURFACE: scheduled job\n"
        "You are running as a scheduled job. No user is present — you "
        "cannot ask questions, request clarification, or wait for "
        "follow-up. Execute the task fully and autonomously, making "
        "reasonable decisions where needed. Your reply is "
        "auto-delivered to the job's configured destination; put the "
        "primary content directly in your response."
    ),
    "telegram": (
        "# SURFACE: Telegram\n"
        "You are replying on Telegram. Plain Markdown is auto-converted "
        "to Telegram's MarkdownV2 (bold, italic, inline code, code "
        "blocks, links, headers). Tables, blockquotes, and deeply "
        "nested lists do NOT render — prefer flat text. Keep replies "
        "chat-friendly: short paragraphs, no sign-offs. Attach files "
        "via `send_message(attachment=…)`, not by inlining paths."
    ),
    "email": (
        "# SURFACE: email\n"
        "You are replying by email. Plain text only — no Markdown, it "
        "shows as literal asterisks and backticks. Keep replies "
        "concise. The subject line is preserved for threading. Skip "
        "greetings and sign-offs unless the user's message warranted "
        "them (business tone vs casual)."
    ),
    "gmail": (
        "# SURFACE: email\n"
        "You are replying by email. Plain text only — no Markdown, it "
        "shows as literal asterisks and backticks. Keep replies "
        "concise. The subject line is preserved for threading. Skip "
        "greetings and sign-offs unless the user's message warranted "
        "them (business tone vs casual)."
    ),
}


def _platform_hint() -> str:
    platform = (os.environ.get("ALPI_PLATFORM") or "").strip().lower()
    return PLATFORM_HINTS.get(platform, "")


def _env_block(home: Path, workspace) -> str:
    parts = ["# ENVIRONMENT"]
    parts.append(
        f"- **host Python**: `{sys.version_info.major}.{sys.version_info.minor}` — a scripted "
        "skill's `scripts/run.py` runs on exactly this interpreter, so target it (e.g. no "
        "`X | Y` type unions or `match` below 3.10). A `terminal` `python3` is resolved from "
        "PATH and may differ — check `python3 --version` when the exact version matters."
    )
    if workspace is not None:
        parts.append(f"- **workspace** (default root for relative paths): `{workspace}`")
        parts.append(f"- **profile home** (memory/skills/config): `{home}`")
        parts.append(
            "- **Path rule**: relative paths (`foo/`, `my-project`) "
            f"resolve from the workspace (`{workspace}/foo/`). Absolute "
            "paths work anywhere the OS lets you read/write — including "
            "`~/Documents`, `/tmp`, other project dirs — except sensitive "
            "system locations (`/etc`, SSH keys, credentials) which are "
            "denied. Prefer the workspace for the user's main context; "
            "reach outside only when they ask for a specific path."
        )
    else:
        cwd = os.getcwd()
        parts.append(
            f"- **workspace**: NOT SET — falling back to your current "
            f"working directory: `{cwd}`. Relative paths resolve from "
            "there. Absolute paths work anywhere except sensitive "
            "system locations. Suggest `/workspace <path>` to the user "
            "if they want a stable root."
        )
        parts.append(f"- **profile home** (memory/skills/config): `{home}`")
    return "\n".join(parts)


def build_parts(home: Path, cfg) -> dict[str, str]:
    """Assemble the cacheable system-prompt contributors as a name→content map. Mirrors ``Engine._build_system_prompt`` byte-for-byte after the ``"\\n\\n".join`` step."""
    from importlib import resources

    from alpi import clock, memory
    from alpi.prompts import guidance
    from alpi.tools.knowledge import PROMPT_RULE as _ALPI_KNOWLEDGE_RULE
    from alpi.tools.skill import skills_index_block

    parts: dict[str, str] = {name: "" for name in PART_ORDER}

    parts["agent_profile"] = (
        cfg.agent_path.read_text().strip()
        if cfg.agent_path.exists() else ""
    )
    parts["base_prompt"] = (
        resources.files("alpi.prompts").joinpath("system_prompt.md").read_text().strip()
    )
    parts["env"] = _env_block(home, cfg.workspace_path)
    parts["system_time"] = clock.system_time_section()
    parts["surface"] = _platform_hint()
    parts["guidance"] = guidance.render_guidance(cfg.model, cfg.providers)
    parts["knowledge_rule"] = _ALPI_KNOWLEDGE_RULE

    skills_block = skills_index_block(home, cfg_raw=cfg.raw)
    parts["skills_index"] = skills_block or ""

    mem = memory.MemoryStore(home=home)
    try:
        mem.prune_low_confidence(max_age_days=memory.LOW_CONFIDENCE_MAX_AGE_DAYS)
    except Exception:  # noqa: BLE001
        pass
    snap = mem.snapshot()
    user_md = snap["USER.md"].strip()
    memory_md = snap["MEMORY.md"].strip()
    parts["user_md"] = ("# USER PROFILE\n" + user_md) if user_md else ""
    parts["memory_md"] = ("# AGENT MEMORY\n" + memory_md) if memory_md else ""
    return parts


def render_cacheable(parts: dict[str, str]) -> str:
    """Join non-empty parts in canonical order with ``\\n\\n``. Output stays identical to the legacy ``_build_system_prompt`` so cache prefixes pinned by past sessions still hash the same."""
    ordered = [parts.get(name, "") for name in PART_ORDER]
    return "\n\n".join(p for p in ordered if p)


def cache_kwargs_for_model(model: str) -> dict:
    """Ask LiteLLM to inject a ``cache_control`` marker on ``messages[0]`` for models known to support prompt caching. Target index 0 (not role=system) because the engine appends several volatile system messages per turn — ``# NOW``, workgroup ctx, skill keyword hint — and only ``messages[0]`` is the stable prefix. Returns ``{}`` on any failure: a missing helper, a raise, or an unsupported model. Caching never breaks a call."""
    if not model:
        return {}
    try:
        from litellm.utils import supports_prompt_caching
        if not supports_prompt_caching(model=model):
            return {}
    except Exception:  # noqa: BLE001
        return {}
    return {
        "cache_control_injection_points": [
            {"location": "message", "index": 0},
        ],
    }


__all__ = [
    "PART_ORDER",
    "PLATFORM_HINTS",
    "build_parts",
    "cache_kwargs_for_model",
    "render_cacheable",
]
