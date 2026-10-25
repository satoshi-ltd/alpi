"""notify — push a native notification to the owner's own Alpi apps."""

from __future__ import annotations

from alpi.outputs import _suppress_native_emit, create_output_and_emit_message, text_arg
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
        "goes to YOUR user's own apps, NOT a third party; to email someone "
        "else use the `email` tool. The only thing to avoid is firing "
        "it just to duplicate an answer the user is already reading in the live "
        "chat and never asked to be pushed.\n"
        "\n"
        "A notification has three parts, in this order everywhere it shows: "
        "`title` says what happened (at most 60 characters, no markdown); "
        "`summary` is one or two plain sentences with the outcome (at most 200 "
        "characters, never ending on a colon) that the banner and the inbox row "
        "show; `text` is the detail the user opens, in `## Section` headings, "
        "`**Label:**` lines, `- ` bullets and 🔴🟡🟢 for status. Do not repeat the "
        "title or the summary in `text`. When `text` carries three or more values "
        "over time, or three or more categories measured the same way, add a "
        "```chart block (syntax in ENVIRONMENT): the apps draw it, while the "
        "banner and the inbox row show the summary. Tables draw as tables; deeper "
        "headings, rules and other emoji are simplified automatically — don't "
        "fuss over format."
    )
    parameters = {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "The body: the detail the user reads when they open the notification, without the title or the summary."},
            "title": {"type": "string", "description": "What happened, at most 60 characters, plain text. The push, the inbox row and the reader lead with it."},
            "summary": {"type": "string", "description": "One or two plain sentences with the outcome, at most 200 characters. The push and the inbox row show it under the title; omitted, the daemon takes the body's first paragraph."},
            "type": {
                "type": "string",
                "description": (
                    "info | warning | error (default: info). warning and error pin "
                    "the notification under Needs you until it is read: set them "
                    "only when the owner has to act."
                ),
                "default": "info",
            },
        },
        "required": ["text"],
    }

    def run(
        self, text: str = "", title: str = "", type: str = "info", summary: str = "",
    ) -> ToolResult:
        text = text_arg(text, "\n")
        if not text.strip():
            return ToolResult(ok=False, output="", error="notify requires non-empty text")
        type = text_arg(type).strip().lower() or "info"
        if type not in VALID_TYPE:
            type = "info"
        # Schedule children defer to the parent: it parses tool_end and files the single canonical output.
        if not _suppress_native_emit():
            create_output_and_emit_message(
                text=text, title=text_arg(title), type=type,
                delivered_to=["alpi"], summary=text_arg(summary),
            )
        return ToolResult(ok=True, output="delivered: alpi")


TOOL = Notify
