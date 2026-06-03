from __future__ import annotations

BLOCKS: dict[str, str] = {
    "tool_discipline": (
        "# GUIDANCE: reach for tools before answering\n"
        "When the answer depends on real state — files, the workspace, code, "
        "docs, command output, anything on disk — call a tool to read it "
        "first. Don't guess a file's contents or assume what a command would "
        "print; run it and use the result."
    ),
    "verify_before_done": (
        "# GUIDANCE: verify before you call it done\n"
        "If you said you would edit, build, run, or test something, do it and "
        "check the result before reporting it complete. Writing a diff is not "
        "the same as applying it — confirm the change landed and the relevant "
        "check passed."
    ),
}

# Keyed by observed behaviour of the family, not by provider. Strong families
# (anthropic, full-size openai/gemini, unknown) get nothing extra on purpose.
FAMILY_GUIDANCE: dict[str, list[str]] = {
    "local": ["tool_discipline", "verify_before_done"],
    "openai_mini": ["tool_discipline", "verify_before_done"],
    "gemini_flash": ["tool_discipline", "verify_before_done"],
}


# Ollama endpoints are user-named (`home/llama3`, `mistral-box/qwen`), so the
# id head won't contain "ollama". Match it against the configured endpoints.
def model_family(model: str, providers: dict | None = None) -> str:
    m = (model or "").lower()
    if not m:
        return "unknown"
    head = m.split("/", 1)[0]
    ollama_names = {
        str(e.get("name", "")).lower()
        for e in (providers or {}).get("ollama", [])
        if isinstance(e, dict)
    }
    if "ollama" in m or head in ollama_names:
        return "local"
    if "claude" in m or "anthropic" in m:
        return "anthropic"
    if "gemini" in m:
        return "gemini_flash" if "flash" in m else "gemini"
    if "gpt" in m or "openai" in m:
        return "openai_mini" if "mini" in m else "openai"
    return "unknown"


def guidance_blocks_for_model(model: str, providers: dict | None = None) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for block in FAMILY_GUIDANCE.get(model_family(model, providers), []):
        if block in BLOCKS and block not in seen:
            seen.add(block)
            out.append(block)
    return out


def render_guidance(model: str, providers: dict | None = None) -> str:
    return "\n\n".join(BLOCKS[b] for b in guidance_blocks_for_model(model, providers))
