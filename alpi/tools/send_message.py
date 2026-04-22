"""send_message — deliver a message to a paired chat on an external platform."""

from __future__ import annotations

from alpi.gateway import delivery
from alpi.tools.base import Tool, ToolResult


class SendMessage(Tool):
    name = "send_message"
    description = (
        "Send a text message to a paired external chat (Telegram). CALL "
        "this tool — saying \"message sent\" without invoking it "
        "sends nothing. Use for proactive messages outside the current "
        "session — scheduled reminders, long-job completion pings, "
        "inactivity check-ins.\n"
        "\n"
        "Not for replying inside the active conversation — just write "
        "the reply directly.\n"
        "\n"
        "Target must be on the allowlist (`TELEGRAM_ALLOWED_CHAT_IDS`). "
        "Omit `platform`/`chat_id` to default to the first allowed chat."
    )
    parameters = {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "The message body. Plain text.",
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
        },
        "required": ["text"],
    }

    def run(self, text: str, platform: str = "telegram",
            chat_id: str | None = None) -> ToolResult:
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
            delivery.send_to(platform, target, text)
        except delivery.DeliveryError as e:
            return ToolResult(ok=False, output="", error=str(e))
        return ToolResult(ok=True, output=f"sent to {platform}:{target}")


TOOL = SendMessage
