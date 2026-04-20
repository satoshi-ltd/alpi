"""Headless browser tool — STUB, NOT REGISTERED."""

from __future__ import annotations

from alf.tools.base import Tool, ToolResult


class Browser(Tool):
    name = "browser"
    description = "Open a URL in a headless browser and extract text/screenshot. (not implemented in v0)"
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string"},
            "action": {"type": "string", "enum": ["text", "screenshot"], "default": "text"},
        },
        "required": ["url"],
    }

    def run(self, url: str, action: str = "text") -> ToolResult:
        return ToolResult(
            ok=False,
            output="",
            error="browser tool not implemented in v0 — use web_fetch for plain HTML/JSON",
        )


TOOL = Browser
