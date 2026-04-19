"""send_message — deliver a message to a paired chat on an external platform.

Used for proactive outreach: scheduled reminders from the schedule daemon,
"I'm done with that long research" pings after a delegate, or the agent
volunteering a check-in when it has something useful to say.

Autosuficiente: the tool posts directly to the platform's API using the
bot credentials in ``~/.alf/.env``. It does NOT require the gateway
listener to be running — sending an outbound message with your own
token adds zero inbound attack surface, so there's no reason to route
through the gateway process.

Safety:
- Only chat IDs in ``{PLATFORM}_ALLOWED_CHAT_IDS`` can receive messages.
- Empty / missing allowlist → every send is rejected (fail closed).
- No ``platform`` argument → defaults to telegram if it has an allowlist.
- No ``chat_id`` argument → defaults to the first allowed chat on that
  platform (single-user ergonomic; explicit is still recommended).
"""

from __future__ import annotations

from alf.gateway import delivery
from alf.tools.base import Tool, ToolResult


class SendMessage(Tool):
    name = "send_message"
    description = (
        "Send a text message to a paired external chat (Telegram today; "
        "webhook and future platforms reuse the same call). Use for "
        "proactive messages the user should see outside the current "
        "session — scheduled reminders, long-job completion pings, "
        "inactivity check-ins. DO NOT use to reply inside the active "
        "conversation: just write the reply directly. The target must be "
        "on the allowlist (TELEGRAM_ALLOWED_CHAT_IDS etc.), otherwise "
        "this fails. If you omit platform/chat_id the tool picks the "
        "first allowed Telegram chat."
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
                "description": "telegram | webhook. Defaults to telegram.",
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
                    f"(set {platform.upper()}_ALLOWED_CHAT_IDS in ~/.alf/.env)"
                ),
            )
        try:
            delivery.send_to(platform, target, text)
        except delivery.DeliveryError as e:
            return ToolResult(ok=False, output="", error=str(e))
        return ToolResult(ok=True, output=f"sent to {platform}:{target}")


TOOL = SendMessage
