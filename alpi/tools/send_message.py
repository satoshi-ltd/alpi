"""send_message — proactive notify the user via the alpi-native channel by default; gateways are explicit opt-in."""

from __future__ import annotations

from alpi.gateway import delivery
from alpi.tools.base import Tool, ToolResult


VALID_CHANNELS = ("alpi", "both", "telegram", "imap", "gmail", "matrix", "webhook")
VALID_SEVERITY = ("normal", "important", "urgent")
VALID_KIND = ("reminder", "result", "alert", "ack")

_GATEWAY_PLATFORMS = ("telegram", "imap", "gmail", "matrix", "webhook")


class SendMessage(Tool):
    name = "send_message"
    description = (
        "Notify the user OUTSIDE the current chat. This is the ONLY way "
        "to proactively reach them — wake their paired Alpi app, deliver "
        "a scheduled result, ping them after a long unattended task. If "
        "the user asks to be notified / pinged / alerted / reminded / "
        "messaged when something finishes, call this tool. Schedule "
        "success on its own does NOT notify; the job must invoke this "
        "tool explicitly.\n"
        "\n"
        "Do NOT use for normal replies inside the active conversation — "
        "just write the reply directly. Use ONLY for messages that need "
        "to break out of the current turn surface.\n"
        "\n"
        "Default channel is `alpi`: the message becomes a native "
        "notification on the user's paired desktop / mobile app via the "
        "host event stream — no gateway config required, no third party "
        "in the middle. Use `channel=\"telegram\"` (or imap / gmail / "
        "matrix / webhook) ONLY when the user explicitly named that "
        "platform. Use `channel=\"both\"` to reach the alpi client AND a "
        "gateway redundantly.\n"
        "\n"
        "Gateway dispatch (`telegram` / `imap` / …) requires `chat_id` or "
        "the platform's allowlist default. Attachments are still "
        "Telegram-only.\n"
        "\n"
        "After calling this tool, the message IS your reply — do NOT "
        "narrate what happened ('I sent you a notification', 'Hecho, "
        "enviado por alpi', file paths, etc.). The user already sees it."
    )
    parameters = {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": (
                    "Message body (or attachment caption). May be empty "
                    "when sending only a file via a gateway."
                ),
            },
            "title": {
                "type": "string",
                "description": (
                    "Short headline for the alpi-channel native "
                    "notification. Defaults to the profile name. Ignored "
                    "by gateway channels."
                ),
            },
            "severity": {
                "type": "string",
                "description": "normal | important | urgent (default: normal).",
                "default": "normal",
            },
            "kind": {
                "type": "string",
                "description": "reminder | result | alert | ack (default: result).",
                "default": "result",
            },
            "channel": {
                "type": "string",
                "description": (
                    "alpi | telegram | imap | gmail | matrix | webhook | "
                    "both. Defaults to `alpi` (native notification on the "
                    "user's paired app). Gateway values require chat_id "
                    "or an allowlist default. `both` emits alpi-native "
                    "AND dispatches to the gateway specified by "
                    "`platform`."
                ),
                "default": "alpi",
            },
            "platform": {
                "type": "string",
                "description": (
                    "Gateway platform when `channel=\"both\"`: telegram / "
                    "imap / gmail / matrix / webhook. Ignored when channel "
                    "is `alpi` or a gateway name (the channel itself "
                    "names the platform)."
                ),
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
                    "Local file path for gateway attachments. Telegram "
                    "picks the endpoint from the extension. Ignored on "
                    "the alpi channel — local notifications carry text "
                    "only."
                ),
            },
        },
        "required": ["text"],
    }

    def run(
        self,
        text: str,
        title: str = "",
        severity: str = "normal",
        kind: str = "result",
        channel: str = "alpi",
        platform: str = "",
        chat_id: str | None = None,
        attachment: str | None = None,
    ) -> ToolResult:
        from alpi.home import effective_profile_env, get_home

        text = text or ""
        title = title or ""
        channel = (channel or "alpi").strip().lower()
        severity = (severity or "normal").strip().lower()
        kind = (kind or "result").strip().lower()

        if channel not in VALID_CHANNELS:
            return ToolResult(
                ok=False, output="",
                error=f"invalid channel: {channel!r}. Use one of: {', '.join(VALID_CHANNELS)}",
            )
        if severity not in VALID_SEVERITY:
            return ToolResult(
                ok=False, output="",
                error=f"invalid severity: {severity!r}. Use one of: {', '.join(VALID_SEVERITY)}",
            )
        if kind not in VALID_KIND:
            return ToolResult(
                ok=False, output="",
                error=f"invalid kind: {kind!r}. Use one of: {', '.join(VALID_KIND)}",
            )
        if not text and not attachment:
            return ToolResult(
                ok=False, output="",
                error="text and attachment cannot both be empty",
            )

        emit_alpi = channel in ("alpi", "both")
        gateway_target = ""
        if channel == "both":
            gateway_target = (platform or "telegram").strip().lower()
        elif channel in _GATEWAY_PLATFORMS:
            gateway_target = channel
        if gateway_target and gateway_target not in _GATEWAY_PLATFORMS:
            return ToolResult(
                ok=False, output="",
                error=(
                    f"invalid gateway platform: {gateway_target!r}. Use one "
                    f"of: {', '.join(_GATEWAY_PLATFORMS)}"
                ),
            )
        if emit_alpi and not text.strip():
            return ToolResult(
                ok=False, output="",
                error="alpi channel requires non-empty text",
            )

        if gateway_target:
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

        delivered: list[str] = []
        delivered_to: list[str] = []

        if gateway_target:
            env = effective_profile_env(get_home())
            target = (chat_id or "").strip() or delivery.default_chat_id(
                gateway_target, env=env,
            )
            if not target:
                if not emit_alpi:
                    return ToolResult(
                        ok=False, output="",
                        error=(
                            f"no chat_id given and no default for "
                            f"{gateway_target} (set "
                            f"{gateway_target.upper()}_ALLOWED_CHAT_IDS "
                            f"in ~/.alpi/.env)"
                        ),
                    )
            else:
                try:
                    delivery.send_to(
                        gateway_target, target, text,
                        attachment=attachment, env=env,
                    )
                    delivered.append(gateway_target)
                    delivered_to.append(gateway_target)
                except delivery.DeliveryError as e:
                    if not emit_alpi:
                        return ToolResult(ok=False, output="", error=str(e))
                    delivered.append(f"{gateway_target}(failed: {e})")

        # Schedule/gateway children defer to the parent: it parses tool_end and files the single canonical output.
        if _suppress_native_emit():
            if emit_alpi:
                delivered.insert(0, "alpi")
            return ToolResult(ok=True, output=f"delivered: {', '.join(delivered)}")

        if emit_alpi:
            _create_output_and_emit_message(
                text=text, title=title,
                severity=severity, kind=kind,
                source="send_message", source_id="",
                delivered_to=["alpi", *delivered_to],
            )
            delivered.insert(0, "alpi")
        elif gateway_target and delivered_to and text.strip():
            # Attachment-only sends (TTS voice notes) skip — nothing displayable to revisit in the inbox.
            _create_output(
                text=text, severity=severity, kind=kind,
                source="send_message", source_id="",
                delivered_to=delivered_to,
            )

        return ToolResult(ok=True, output=f"delivered: {', '.join(delivered)}")


def _suppress_native_emit() -> bool:
    import os
    return (
        os.environ.get("ALPI_SCHEDULE_CHILD") == "1"
        or os.environ.get("ALPI_PARENT_EMITS_AGENT_MESSAGE") == "1"
    )


def _create_output_and_emit_message(
    *, text: str, title: str, severity: str, kind: str,
    source: str, source_id: str, delivered_to: list[str],
) -> str:
    """Callers must guard with _suppress_native_emit() — schedule/gateway children defer to the parent."""
    output = _create_output(
        text=text, severity=severity, kind=kind,
        source=source, source_id=source_id, delivered_to=delivered_to,
    )
    if output is None:
        return ""

    payload: dict = {
        "profile": output["profile"],
        "title": title or output["profile"] or "alpi",
        "body": output["body"],
        "severity": output["severity"],
        "kind": output["kind"],
        "output_id": output["id"],
        "deep_link": f"/outputs/{output['profile']}/{output['id']}",
    }
    if output.get("session_id"):
        payload["session_id"] = output["session_id"]

    try:
        from alpi.host import events as host_events
        host_events.emit("agent.message", payload)
        host_events.emit("output.created", {
            "profile": output["profile"],
            "id": output["id"],
            "source": output["source"],
            "severity": output["severity"],
            "kind": output["kind"],
        })
    except Exception:  # noqa: BLE001
        pass

    return output["id"]


def _create_output(
    *, text: str, severity: str, kind: str,
    source: str, source_id: str, delivered_to: list[str],
) -> dict | None:
    # Persistence is opportunistic — failures never block delivery.
    try:
        from alpi import outputs as outputs_mod
        from alpi.home import get_active_session, get_home, profile_name
    except Exception:  # noqa: BLE001
        return None

    try:
        home = get_home()
        prof = profile_name(home)
    except Exception:  # noqa: BLE001
        return None

    try:
        session_id = get_active_session() or ""
    except Exception:  # noqa: BLE001
        session_id = ""

    try:
        return outputs_mod.append(
            home,
            profile=prof,
            source=source,
            source_id=source_id,
            body=text,
            severity=severity,
            kind=kind,
            session_id=session_id,
            delivered_to=delivered_to,
        )
    except Exception:  # noqa: BLE001
        return None


TOOL = SendMessage
