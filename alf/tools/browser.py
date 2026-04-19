"""Headless browser tool — STUB, NOT REGISTERED.

This file exists but is intentionally left out of the tool registry
(``alf/tools/__init__.py``) until the Playwright implementation lands.
An agent that can see the tool declaration but always gets an error back
only wastes prompt budget and reasoning steps.

When we're ready to ship v0.2:
  1. Replace :class:`Browser.run` with a Playwright-backed implementation
     (headless Chrome, persistent context under ``~/.alf/browser/``,
     actions: text / screenshot / click / fill / navigate).
  2. Add ``playwright`` to ``pyproject.toml``.
  3. Re-add ``browser`` to the registry import + for-loop in
     ``alf/tools/__init__.py``.
  4. Document in ``docs/CONTEXT.md``.
"""

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
