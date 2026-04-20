"""Config loader — reads ~/.alf/config.yaml and ~/.alf/.env."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

DEFAULT_CONFIG: dict[str, Any] = {
    "model": "openrouter/xiaomi/mimo-v2-flash",
    "fallback_models": [],
    # Optional: lock alf's filesystem scope to this directory regardless of
    # where it was launched. Useful for role-based profiles (work points at
    # ~/git, personal at ~/Documents, etc.) and for headless gateways.
    # Empty / unset → sandbox uses ``os.getcwd()`` at launch instead.
    "workspace": "",
    "providers": {"custom": []},
    "tools": {
        "max_steps_per_turn": 40,
        "web_extract": {
            # Empty → use the main `model`. Override with a cheap/fast model
            # (e.g. openrouter/google/gemini-2.0-flash-exp:free) to save cost.
            "model": "",
        },
    },
    "tui": {
        "show_cost": True,
        "show_tokens": True,
        # Any Textual/CSS color value: named ("orange"), hex ("#ff8800"),
        # rgb("..."). Empty = inherit from the current Textual theme.
        "accent": "#ff8800",
    },
    # MCP (Model Context Protocol) servers the user has opted into.
    # Blank by default — alf ships with zero pre-connected MCPs.
    # Users add them via ``alf setup → MCPs`` or by editing this file
    # directly. Secrets go in ``.env`` and are referenced here with
    # the ``env:VAR_NAME`` placeholder.
    "mcp": {
        "servers": {},
    },
    # Gateway configuration is namespaced per platform so each channel
    # can carry its own knobs without collisions. Flat keys under
    # ``gateway`` would force us to rename fields the day another
    # platform wanted a flag with the same name.
    "gateway": {
        "telegram": {
            # Relay tool-call traces to Telegram as they happen (one
            # short message per tool). Set to false to only deliver the
            # final reply.
            "show_tool_trace": True,
            # Keep a "typing…" indicator on in the chat while alf is
            # working.
            "typing_indicator": True,
        },
        "email": {
            # Seconds between IMAP polls for new inbound mail. Hermes
            # runs on 15s; 60s is a sensible personal-use default that
            # keeps CPU/network noise low.
            "poll_interval": 60,
            # Mark processed messages as \Seen in IMAP after alf has
            # replied, so your regular mail client treats them as read.
            "mark_as_read": True,
            # Tool-trace streaming defaults OFF for email — each trace
            # is its own email, which is spam if a turn touches many
            # tools. Only the final reply goes out. Users who really
            # want per-tool emails can flip this to true.
            "show_tool_trace": False,
            # No "typing…" concept in IMAP/SMTP. Kept explicit so the
            # gateway loop doesn't spawn a no-op heartbeat task.
            "typing_indicator": False,
        },
    },
}


@dataclass
class WebExtractToolConfig:
    model: str = ""  # empty = use main model


@dataclass
class ToolsConfig:
    max_steps_per_turn: int = 40   # ceiling on tool-calls per user turn
    web_extract: WebExtractToolConfig = field(default_factory=WebExtractToolConfig)


@dataclass
class Config:
    home: Path
    model: str
    fallback_models: list[str] = field(default_factory=list)
    providers: dict[str, Any] = field(default_factory=dict)
    tools: ToolsConfig = field(default_factory=ToolsConfig)
    tui: dict[str, Any] = field(default_factory=dict)
    gateway: dict[str, Any] = field(default_factory=dict)
    workspace: str = ""      # "" → fall back to cwd
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def workspace_path(self) -> Path | None:
        """Return the workspace as a resolved Path, or None if unset."""
        w = (self.workspace or "").strip()
        if not w:
            return None
        return Path(w).expanduser().resolve()

    @property
    def personality_path(self) -> Path:
        from alf.home import personality_path as _pp
        return _pp(self.home)

    @property
    def env_path(self) -> Path:
        return self.home / ".env"

    @property
    def config_path(self) -> Path:
        return self.home / "config.yaml"


def _deep_merge(defaults: dict, user: dict | None) -> dict:
    """Recursive merge: nested dicts merge key-by-key, everything else
    lets the user value win. Needed because ``gateway`` is now a
    two-level map (platform → flags) and a shallow merge would drop
    the ``email`` defaults the moment the user writes a ``telegram``
    block, or vice-versa."""
    merged = dict(defaults)
    for key, value in (user or {}).items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load(home: Path) -> Config:
    """Load config from ~/.alf/config.yaml and load .env into process env."""
    cfg_path = home / "config.yaml"
    env_path = home / ".env"

    if env_path.exists():
        load_dotenv(env_path, override=False)

    data: dict[str, Any] = dict(DEFAULT_CONFIG)
    if cfg_path.exists():
        user_data = yaml.safe_load(cfg_path.read_text()) or {}
        data.update(user_data)

    tools_raw = data.get("tools") or {}
    web_extract_raw = tools_raw.get("web_extract") or {}
    tools_cfg = ToolsConfig(
        max_steps_per_turn=int(tools_raw.get(
            "max_steps_per_turn", DEFAULT_CONFIG["tools"]["max_steps_per_turn"]
        )),
        web_extract=WebExtractToolConfig(
            model=str(web_extract_raw.get("model", "") or ""),
        ),
    )

    return Config(
        home=home,
        model=data.get("model", DEFAULT_CONFIG["model"]),
        fallback_models=data.get("fallback_models", []),
        providers=data.get("providers", DEFAULT_CONFIG["providers"]),
        tools=tools_cfg,
        tui=data.get("tui", DEFAULT_CONFIG["tui"]),
        gateway=_deep_merge(DEFAULT_CONFIG["gateway"], data.get("gateway")),
        workspace=str(data.get("workspace", "") or ""),
        raw=data,
    )


def save(cfg: Config) -> None:
    """Persist the given Config back to ~/.alf/config.yaml."""
    data: dict[str, Any] = dict(cfg.raw)
    data["model"] = cfg.model
    data["providers"] = cfg.providers
    data["fallback_models"] = cfg.fallback_models
    data["tools"] = {
        "max_steps_per_turn": cfg.tools.max_steps_per_turn,
        "web_extract": {"model": cfg.tools.web_extract.model},
    }
    data["tui"] = cfg.tui
    data["gateway"] = cfg.gateway
    if cfg.workspace:
        data["workspace"] = cfg.workspace
    else:
        data.pop("workspace", None)
    cfg.config_path.write_text(yaml.safe_dump(data, sort_keys=False))


def resolve_model(cfg: Config) -> dict[str, Any]:
    """Return the litellm.completion kwargs for the currently selected model.

    Handles custom OpenAI-compatible endpoints by turning a model id of the
    form ``<custom_name>/<model>`` into ``openai/<model>`` + ``api_base``.
    """
    import os

    model_str = cfg.model
    custom_eps = {c.get("name"): c for c in cfg.providers.get("custom", [])}

    head, _, rest = model_str.partition("/")
    if head in custom_eps:
        ep = custom_eps[head]
        extras: dict[str, Any] = {
            "model": f"openai/{rest}",
            "api_base": ep.get("base_url", ""),
        }
        key_env = ep.get("api_key_env") or ""
        extras["api_key"] = os.environ.get(key_env, "dummy") if key_env else "dummy"
        return extras

    return {"model": model_str}


def seed_defaults(home: Path) -> None:
    """Write starter config.yaml and .env.example on first run."""
    cfg_path = home / "config.yaml"
    if not cfg_path.exists():
        cfg_path.write_text(yaml.safe_dump(DEFAULT_CONFIG, sort_keys=False))

    example_env = home / ".env.example"
    if not example_env.exists():
        example_env.write_text(
            "# Copy to .env and fill in the keys you use.\n"
            "ANTHROPIC_API_KEY=\n"
            "OPENAI_API_KEY=\n"
            "OPENROUTER_API_KEY=\n"
            "OLLAMA_BASE_URL=http://localhost:11434\n"
            "# Gateway (optional). Allowlists are fail-closed — an empty\n"
            "# list means nothing inbound is processed on that platform.\n"
            "TELEGRAM_BOT_TOKEN=\n"
            "TELEGRAM_ALLOWED_CHAT_IDS=\n"
            "EMAIL_ADDRESS=\n"
            "EMAIL_PASSWORD=\n"
            "EMAIL_IMAP_HOST=\n"
            "EMAIL_SMTP_HOST=\n"
            "EMAIL_ALLOWED_SENDERS=\n"
            "WEBHOOK_ALLOWED_CHAT_IDS=\n"
        )
