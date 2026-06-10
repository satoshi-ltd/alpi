"""notify — push a native notification to the owner's own Alpi apps."""

from __future__ import annotations

from alpi.outputs import _suppress_native_emit, create_output_and_emit_message
from alpi.tools.base import Tool, ToolResult

VALID_TYPE = ("info", "warning", "error")


class Notify(Tool):
    name = "notify"
    description = (
        "Notify the USER on their own paired Alpi apps (native push). Call it "
        "whenever the user asks to be notified / pinged / alerted / reminded / "
        "messaged — even mid-chat, that request is an order to call this tool — "
        "and proactively when you have deferred or async news for them (a "
        "reminder coming due, a long task finished, 'I noticed X'). The message "
        "goes to YOUR user's own apps, NOT a third party; to message someone "
        "else use `send_message` (a gateway). The only thing to avoid is firing "
        "it just to duplicate an answer the user is already reading in the live "
        "chat and never asked to be pushed."
    )
    parameters = {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "The notification body."},
            "title": {"type": "string", "description": "Short headline for the notification."},
            "type": {
                "type": "string",
                "description": (
                    "info | warning | error (default: info). info = neutral; "
                    "warning = prominent; error = red alert styling."
                ),
                "default": "info",
            },
        },
        "required": ["text"],
    }

    def run(
        self, text: str = "", title: str = "", type: str = "info",
    ) -> ToolResult:
        text = text or ""
        if not text.strip():
            return ToolResult(ok=False, output="", error="notify requires non-empty text")
        type = (type or "info").strip().lower()
        if type not in VALID_TYPE:
            type = "info"
        # Schedule/gateway children defer to the parent: it parses tool_end and files the single canonical output.
        if not _suppress_native_emit():
            create_output_and_emit_message(
                text=text, title=title or "", type=type,
                source="send_message", source_id="",
                delivered_to=["alpi"],
            )
        return ToolResult(ok=True, output="delivered: alpi")


TOOL = Notify
