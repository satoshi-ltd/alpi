"""send_message — deliver a message to a paired chat on an external platform."""

from __future__ import annotations

from alpi.gateway import delivery
from alpi.tools.base import Tool, ToolResult


class SendMessage(Tool):
    name = "send_message"
    description = (
        "Send a message to a paired external chat (Telegram). CALL this "
        "tool — saying \"message sent\" without invoking it sends "
        "nothing.\n"
        "\n"
        "Use for: proactive pings outside the current session (scheduled "
        "reminders, long-job completion, inactivity check-ins) AND for "
        "attaching a file to the reply — e.g. chain `tts(format=\"ogg\")` "
        "then `send_message(attachment=<path>)` to deliver a voice note.\n"
        "\n"
        "Not for plain-text replies inside the active conversation — just "
        "write the reply directly.\n"
        "\n"
        "`attachment` is a local file path. Telegram picks the endpoint "
        "from the extension: `.ogg` → voice note, `.mp3`/`.m4a`/`.wav` → "
        "audio, `.jpg`/`.png`/`.gif`/`.webp` → photo, `.mp4`/`.mov` → "
        "video, anything else → document. When both `text` and "
        "`attachment` are given, the text becomes the attachment's "
        "caption (truncated at 1024 chars by Telegram).\n"
        "\n"
        "Target must be on the allowlist (`TELEGRAM_ALLOWED_CHAT_IDS`). "
        "Omit `platform`/`chat_id` to default to the first allowed chat.\n"
        "\n"
        "After calling this tool, the message or attachment IS your "
        "reply — do NOT narrate what happened in follow-up text ('I sent "
        "you an audio', 'Hecho, enviado a Telegram', file paths, chat "
        "ids, etc.). The user already sees the message arrive. On "
        "success just stay silent or say at most one short word."
    )
    parameters = {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": (
                    "The message body (or caption when `attachment` is "
                    "set). Plain text. May be empty when sending an "
                    "attachment without a caption."
                ),
            },
            "platform": {
                "type": "string",
                "description": "telegram | email | gmail | webhook. Defaults to telegram.",
                "default": "telegram",
            },
            "chat_id": {
                "type": "string",
                "description": (
                    "Target chat id on the platform. If omitted, defaults "
                    "to the first allowlisted chat on that platform."
                ),
            },
            "attachment": {
                "type": "string",
                "description": (
                    "Local file path to send alongside the message. "
                    "Telegram-only for now; email/gmail attachments go "
                    "through the `email` tool."
                ),
            },
        },
        "required": ["text"],
    }

    def run(self, text: str, platform: str = "telegram",
            chat_id: str | None = None,
            attachment: str | None = None) -> ToolResult:
        from alpi.tools._sandbox import require_network
        blocked = require_network("send_message")
        if blocked is not None:
            return blocked
        platform = (platform or "telegram").strip().lower()
        target = (chat_id or "").strip() or delivery.default_chat_id(platform)
        if not target:
            return ToolResult(
                ok=False, output="",
                error=(
                    f"no chat_id given and no default for {platform} "
                    f"(set {platform.upper()}_ALLOWED_CHAT_IDS in ~/.alpi/.env)"
                ),
            )
        try:
            delivery.send_to(platform, target, text, attachment=attachment)
        except delivery.DeliveryError as e:
            return ToolResult(ok=False, output="", error=str(e))
        return ToolResult(ok=True, output="delivered")


TOOL = SendMessage
