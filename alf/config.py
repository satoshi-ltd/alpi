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
        workspace=str(data.get("workspace", "") or ""),
        raw=data,
    )


def save(cfg: Config) -> None:
    """Persist the given Config back to ~/.alf/config.yaml."""
    data: dict[str, Any] = dict(cfg.raw)
    data["model"] = cfg.model
    data["providers"] = cfg.providers
    data["fallback_models"] = cfg.fallback_models
    data.pop("reflect", None)  # legacy key — no longer used
    data["tools"] = {
        "max_steps_per_turn": cfg.tools.max_steps_per_turn,
        "web_extract": {"model": cfg.tools.web_extract.model},
    }
    data["tui"] = cfg.tui
    if cfg.workspace:
        data["workspace"] = cfg.workspace
    else:
        data.pop("workspace", None)
    # Remove legacy keys if still present.
    data.pop("extract_model", None)
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
            "# Gateway (optional)\n"
            "TELEGRAM_BOT_TOKEN=\n"
            "TELEGRAM_ALLOWED_CHAT_IDS=\n"
        )
