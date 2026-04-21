"""web_extract — fetch a URL and return an LLM-summarized answer."""

from __future__ import annotations

from alpi.tools.base import Tool, ToolResult
from alpi.tools.web_fetch import WebFetch


SYSTEM_PROMPT = """You extract the most relevant information from a web page.

Input: page content in Markdown + an optional focus question.
Output: a concise Markdown answer.

Rules:
- Answer the question directly if one is given. Otherwise, give a short
  bulleted summary of the page.
- Quote short excerpts if they're the best evidence. Always include source
  URLs inline when relevant: `source: <url>`.
- Max 600 words. Be ruthlessly concise.
- If the page can't answer the question, say so briefly — don't fabricate.
"""


class WebExtract(Tool):
    name = "web_extract"
    description = (
        "Fetch a URL and return an LLM-extracted answer focused on `question` "
        "(or a concise summary if no question). Use this to ANSWER a question "
        "about a known URL — it reduces tokens 50-100× vs web_fetch + your "
        "own summarization.\n"
        "\n"
        "DO NOT use for:\n"
        "  • finding URLs  → use `web_search`\n"
        "  • showing the raw page to the user → use `web_fetch`\n"
        "  • HTTP via shell → never `terminal curl/wget`"
    )
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string"},
            "question": {
                "type": "string",
                "description": "Optional: what to look for on the page.",
                "default": "",
            },
            "max_bytes": {"type": "integer", "default": 250_000},
        },
        "required": ["url"],
    }

    def run(self, url: str, question: str = "", max_bytes: int = 250_000) -> ToolResult:
        from alpi.tools._state import emit_state

        # 1. Fetch the page as Markdown.
        emit_state("reading page…")
        fetch = WebFetch().run(url=url, max_bytes=max_bytes, strip_links=True)
        if not fetch.ok:
            return ToolResult(ok=False, output="", error=f"fetch failed: {fetch.error}")

        body = fetch.output
        if not body.strip():
            return ToolResult(ok=False, output="", error="empty page")

        # 2. Pick the extract model (configured override first, then main model).
        from alpi import config as cfg_mod
        from alpi.home import get_home
        cfg = cfg_mod.load(get_home())
        override = cfg.tools.web_extract.model
        main_kwargs = cfg_mod.resolve_model(cfg)

        # 3. Ask the LLM — try override first, fall back to main model on error.
        from alpi import llm
        user_prompt = f"# Page from {url}\n\n{body}"
        if question.strip():
            user_prompt = f"Focus question: {question.strip()}\n\n{user_prompt}"
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        first_error: str | None = None
        if override:
            try:
                emit_state("extracting…")
                out = llm.complete(messages=messages, model=override)
                content = (out.content or "").strip() or "(empty extraction)"
                return ToolResult(ok=True, output=content)
            except Exception as e:  # noqa: BLE001
                emit_state("retrying with main model…", error=True)
                first_error = f"override {override!r} failed: {e}; retrying with main model"

        try:
            emit_state("extracting…")
            out = llm.complete(messages=messages, **main_kwargs)
        except Exception as e:  # noqa: BLE001
            err = f"extract LLM call failed: {e}"
            if first_error:
                err = f"{first_error}; then {err}"
            return ToolResult(ok=False, output="", error=err)

        content = (out.content or "").strip() or "(empty extraction)"
        # If we fell back, surface that in the output prefix so the user knows.
        if first_error:
            content = f"[fallback: {override} unavailable, used main model]\n\n{content}"
        return ToolResult(ok=True, output=content)


TOOL = WebExtract
