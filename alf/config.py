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
    "workspace": "",
    "providers": {"custom": []},
    "tools": {
        "max_steps_per_turn": 40,
        "web_extract": {"model": ""},
        "terminal": {
            "sandbox": False,
            "allow_network": False,
        },
    },
    "tui": {
        "show_cost": True,
        "show_tokens": True,
        "accent": "#ff8800",
    },
    "mcp": {
        "servers": {},
    },
    "gateway": {
        "telegram": {
            "show_tool_trace": True,
            "typing_indicator": True,
        },
        "email": {
            "poll_interval": 60,
            "mark_as_read": True,
            "show_tool_trace": False,
            "typing_indicator": False,
        },
    },
}


SEED_CONFIG: dict[str, Any] = {
    "model": DEFAULT_CONFIG["model"],
    "providers": {"custom": []},
    "mcp": {"servers": {}},
    "gateway": DEFAULT_CONFIG["gateway"],
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

    user_data: dict[str, Any] = {}
    if cfg_path.exists():
        user_data = yaml.safe_load(cfg_path.read_text()) or {}
    data = _deep_merge(DEFAULT_CONFIG, user_data)

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
        gateway=data.get("gateway", DEFAULT_CONFIG["gateway"]),
        workspace=str(data.get("workspace", "") or ""),
        raw=user_data,
    )


def save(cfg: Config) -> None:
    """Persist cfg to ~/.alf/config.yaml. Only non-default values survive."""
    data: dict[str, Any] = {
        "model": cfg.model,
        "providers": cfg.providers,
        "mcp": cfg.raw.get("mcp", {"servers": {}}),
        "gateway": cfg.gateway,
    }
    if cfg.workspace:
        data["workspace"] = cfg.workspace
    if cfg.fallback_models:
        data["fallback_models"] = cfg.fallback_models

    tools_delta = _tools_delta(cfg)
    if tools_delta:
        data["tools"] = tools_delta

    tui_delta = {
        k: v for k, v in (cfg.tui or {}).items()
        if v != DEFAULT_CONFIG["tui"].get(k)
    }
    if tui_delta:
        data["tui"] = tui_delta

    cfg.config_path.write_text(yaml.safe_dump(data, sort_keys=False))


def _tools_delta(cfg: Config) -> dict:
    out: dict[str, Any] = {}
    d = DEFAULT_CONFIG["tools"]
    if cfg.tools.max_steps_per_turn != d["max_steps_per_turn"]:
        out["max_steps_per_turn"] = cfg.tools.max_steps_per_turn
    if cfg.tools.web_extract.model != d["web_extract"]["model"]:
        out["web_extract"] = {"model": cfg.tools.web_extract.model}
    return out


def resolve_model(cfg: Config) -> dict[str, Any]:
    """Return the litellm.completion kwargs for the currently selected model."""
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
        cfg_path.write_text(yaml.safe_dump(SEED_CONFIG, sort_keys=False))

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
