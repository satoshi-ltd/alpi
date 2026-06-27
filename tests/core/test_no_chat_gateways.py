"""v0.10 contract: chat-app gateways are gone; email is an on-demand tool."""

from __future__ import annotations

import importlib.util


def test_gateway_package_is_removed() -> None:
    assert importlib.util.find_spec("alpi.gateway") is None


def test_send_message_tool_is_gone_email_remains() -> None:
    from alpi import tools

    assert tools.get("send_message") is None
    assert tools.get("email") is not None


def test_email_is_multi_account() -> None:
    from alpi.config import DEFAULT_CONFIG
    from alpi.host import config as host_config

    assert DEFAULT_CONFIG["email"] == {"accounts": {}}
    assert host_config._is_email_env_key("EMAIL__ME_WORK_COM__PASSWORD")
    assert host_config._is_email_env_key("GMAIL_CLIENT_ID")
    assert not host_config._is_email_env_key("OPENAI_API_KEY")


def test_child_outputs_have_no_send_message_helpers() -> None:
    import alpi.outputs as outputs_mod

    assert not hasattr(outputs_mod, "normalize_send_message_args")
    assert not hasattr(outputs_mod, "record_child_send_message")
    assert hasattr(outputs_mod, "normalize_native_notification_args")
    assert hasattr(outputs_mod, "record_child_native_message")


def test_host_rpcs_are_email_namespaced_not_gateway() -> None:
    from alpi.host import server as host_server

    allowed = set(host_server._ADMIN_METHODS)
    assert not any(m.startswith("host.gateway.") for m in allowed)
    assert "host.email.status" in allowed
    assert "host.email.add" in allowed
    assert "host.email.gmail.exchange" in allowed


def test_cli_exposes_email_group_not_gateway() -> None:
    from alpi import cli

    assert "email" in cli.main.commands
    assert "gateway" not in cli.main.commands


def test_no_live_gateway_or_send_message_references() -> None:
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[2] / "alpi"
    forbidden = (
        "gateway/sessions", "host.gateway", "alpi.gateway",
        "normalize_send_message_args", "record_child_send_message",
    )
    hits = []
    for p in root.rglob("*.py"):
        text = p.read_text(encoding="utf-8", errors="ignore")
        for token in forbidden:
            if token in text:
                hits.append(f"{p.relative_to(root)}: {token}")
    assert not hits, "live gateway / send_message references:\n" + "\n".join(hits)


def test_no_chat_platform_surface_hints() -> None:
    from alpi.prompt_cache import PLATFORM_HINTS

    assert set(PLATFORM_HINTS) == {"cron"}
