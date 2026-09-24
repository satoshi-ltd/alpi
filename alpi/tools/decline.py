from __future__ import annotations

from typing import Any

from alpi.tools.base import Tool, ToolResult


class DeclineTool(Tool):
    name = "decline"
    description = (
        "Relay mode only: refuse the current request without consulting the peer. "
        "Use it when the request asks for something this relay must not forward — a "
        "change, an action, anything beyond a question the peer can answer. `reason` "
        "is shown to the user verbatim: write it in the user's language, say why the "
        "request is declined, and never answer the question from your own knowledge."
    )
    parameters = {
        "type": "object",
        "properties": {
            "reason": {
                "type": "string",
                "description": "Short refusal shown to the user, in the user's language.",
            },
        },
        "required": ["reason"],
    }

    def run(self, **kwargs: Any) -> ToolResult:
        reason = str(kwargs.get("reason") or "").strip()
        if not reason:
            return ToolResult(ok=False, output="", error="reason required")
        return ToolResult(ok=True, output=reason)


TOOL = DeclineTool
