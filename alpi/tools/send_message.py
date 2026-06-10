"""send_message — deliver to a THIRD PARTY via a gateway (telegram/email/...); to alert the owner use notify."""

from __future__ import annotations

from alpi.gateway import delivery
from alpi.outputs import _suppress_native_emit, create_output
from alpi.tools.base import Tool, ToolResult

GATEWAYS = ("telegram", "imap", "gmail", "matrix", "webhook")


class SendMessage(Tool):
    name = "send_message"
    description = (
        "Send a message to a THIRD PARTY through an external gateway — "
        "Telegram, email (imap / gmail), matrix, webhook. Use this when "
        "the user asks to forward / post / email / message someone OR a "
        "specific platform (e.g. 'send the summary to Telegram', 'email "
        "the report to the team').\n"
        "\n"
        "This NEVER reaches the owner's own Alpi apps — to alert the owner "
        "call `notify` instead (native push, no gateway). Sending to a "
        "gateway reaches whoever owns that chat / inbox, not the user.\n"
        "\n"
        "Pick the gateway with `channel`: telegram / imap / gmail / matrix "
        "/ webhook. Dispatch requires `chat_id` or the platform's allowlist "
        "default; attachments are Telegram-only.\n"
        "\n"
        "Do NOT use for normal replies inside the active conversation — "
        "just write the reply directly."
    )
    parameters = {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": (
                    "Message body (or attachment caption). May be empty "
                    "when sending only a file."
                ),
            },
            "channel": {
                "type": "string",
                "description": "telegram | imap | gmail | matrix | webhook.",
            },
            "chat_id": {
                "type": "string",
                "description": (
                    "Target chat id for the gateway. If omitted, defaults "
                    "to the first allowlisted chat on that platform."
                ),
            },
            "attachment": {
                "type": "string",
                "description": (
                    "Local file path. Telegram picks the endpoint from the "
                    "extension."
                ),
            },
        },
        "required": ["text", "channel"],
    }

    def run(
        self,
        text: str,
        channel: str = "",
        chat_id: str | None = None,
        attachment: str | None = None,
    ) -> ToolResult:
        from alpi.home import effective_profile_env, get_home

        text = text or ""
        channel = (channel or "").strip().lower()

        if channel not in GATEWAYS:
            return ToolResult(
                ok=False, output="",
                error=f"invalid channel: {channel!r}. Use one of: {', '.join(GATEWAYS)}",
            )
        if not text and not attachment:
            return ToolResult(
                ok=False, output="",
                error="text and attachment cannot both be empty",
            )

        from alpi.tools._sandbox import require_network
        blocked = require_network("send_message")
        if blocked is not None:
            return blocked

        if attachment:
            from alpi.tools._paths import resolve_path
            try:
                resolve_path(attachment)
            except ValueError as e:
                return ToolResult(ok=False, output="", error=str(e))

        env = effective_profile_env(get_home())
        target = (chat_id or "").strip() or delivery.default_chat_id(channel, env=env)
        if not target:
            return ToolResult(
                ok=False, output="",
                error=(
                    f"no chat_id given and no default for {channel} (set "
                    f"{channel.upper()}_ALLOWED_CHAT_IDS in ~/.alpi/.env)"
                ),
            )
        try:
            delivery.send_to(channel, target, text, attachment=attachment, env=env)
        except delivery.DeliveryError as e:
            return ToolResult(ok=False, output="", error=str(e))

        # Schedule/gateway children defer to the parent: it parses tool_end and files the single canonical output.
        # Attachment-only sends (voice notes) skip — nothing displayable to revisit in the inbox.
        if not _suppress_native_emit() and text.strip():
            create_output(
                text=text, type="info",
                source="send_message", source_id="",
                delivered_to=[channel],
            )

        return ToolResult(ok=True, output=f"delivered: {channel}")


TOOL = SendMessage
