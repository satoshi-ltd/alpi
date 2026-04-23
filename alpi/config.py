"""Config loader — reads ~/.alpi/config.yaml and ~/.alpi/.env."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

DEFAULT_CONFIG: dict[str, Any] = {
    "model": "",
    "fallback_models": [],
    "workspace": "",
    "providers": {"ollama": []},
    "tools": {
        "max_steps_per_turn": 40,
        "web_extract": {"model": ""},
        "read_image": {"model": "", "auto_resize": True, "max_edge": 1568},
        "browser": {
            "vision": False,
            "human_typing": True,
            "typing_delay_ms": [30, 80],
        },
        "terminal": {
            "sandbox": False,
            "allow_network": False,
            "approval": {"allowlist": []},
        },
        "research": {
            "quick_steps": 8,
            "normal_steps": 15,
            "deep_steps": 30,
        },
        "tts": {
            "voice": "en-US-AriaNeural",
            "autoplay": True,
            "rate": "",
            "pitch": "",
        },
        "stt": {"model": "base", "language": ""},
    },
    "tui": {
        "show_cost": True,
        "show_tokens": True,
        "show_reasoning": True,
        "accent": "#ff8800",
        "theme": "dark",
        "auto_resume": False,
    },
    "mcp": {
        "servers": {},
    },
    "gateway": {
        "telegram": {
            "show_tool_trace": True,
            "typing_indicator": True,
        },
        "imap": {
            "poll_interval": 60,
            "mark_as_read": True,
            "show_tool_trace": False,
            "typing_indicator": False,
        },
        "gmail": {
            "poll_interval": 60,
            "mark_as_read": True,
            "show_tool_trace": False,
            "typing_indicator": False,
        },
    },
}


SEED_CONFIG: dict[str, Any] = {
    "model": DEFAULT_CONFIG["model"],
    "providers": {"ollama": []},
    "mcp": {"servers": {}},
    "gateway": DEFAULT_CONFIG["gateway"],
}


@dataclass
class WebExtractToolConfig:
    model: str = ""  # empty = use main model


@dataclass
class ReadImageToolConfig:
    model: str = ""  # empty = use main model
    auto_resize: bool = True
    max_edge: int = 1568  # pixels; Anthropic's recommended upper bound


@dataclass
class TerminalToolConfig:
    sandbox: bool = False
    allow_network: bool = False


@dataclass
class BrowserToolConfig:
    vision: bool = False
    human_typing: bool = True
    typing_delay_ms: list[int] = field(default_factory=lambda: [30, 80])


@dataclass
class TtsToolConfig:
    voice: str = "en-US-AriaNeural"
    autoplay: bool = True
    rate: str = ""               # "+10%" / "-20%" / "" = neutral
    pitch: str = ""              # "+5Hz" / "-10Hz" / "" = neutral


@dataclass
class SttToolConfig:
    model: str = "base"         # tiny | base | small | medium | large-v3
    language: str = ""          # "" → auto-detect


@dataclass
class ToolsConfig:
    max_steps_per_turn: int = 40   # ceiling on tool-calls per user turn
    web_extract: WebExtractToolConfig = field(default_factory=WebExtractToolConfig)
    read_image: ReadImageToolConfig = field(default_factory=ReadImageToolConfig)
    terminal: TerminalToolConfig = field(default_factory=TerminalToolConfig)
    browser: BrowserToolConfig = field(default_factory=BrowserToolConfig)
    tts: TtsToolConfig = field(default_factory=TtsToolConfig)
    stt: SttToolConfig = field(default_factory=SttToolConfig)


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
        from alpi.home import personality_path as _pp
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
    """Load config from ~/.alpi/config.yaml and load .env into process env."""
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
    read_image_raw = tools_raw.get("read_image") or {}
    terminal_raw = tools_raw.get("terminal") or {}
    browser_raw = tools_raw.get("browser") or {}
    tts_raw = tools_raw.get("tts") or {}
    stt_raw = tools_raw.get("stt") or {}
    tools_cfg = ToolsConfig(
        max_steps_per_turn=int(tools_raw.get(
            "max_steps_per_turn", DEFAULT_CONFIG["tools"]["max_steps_per_turn"]
        )),
        web_extract=WebExtractToolConfig(
            model=str(web_extract_raw.get("model", "") or ""),
        ),
        read_image=ReadImageToolConfig(
            model=str(read_image_raw.get("model", "") or ""),
            auto_resize=bool(read_image_raw.get("auto_resize", True)),
            max_edge=int(read_image_raw.get("max_edge", 1568)),
        ),
        terminal=TerminalToolConfig(
            sandbox=bool(terminal_raw.get("sandbox", False)),
            allow_network=bool(terminal_raw.get("allow_network", False)),
        ),
        browser=BrowserToolConfig(
            vision=bool(browser_raw.get("vision", False)),
            human_typing=bool(browser_raw.get("human_typing", True)),
            typing_delay_ms=list(browser_raw.get("typing_delay_ms", [30, 80])),
        ),
        tts=TtsToolConfig(
            voice=str(tts_raw.get("voice", "en-US-AriaNeural") or "en-US-AriaNeural"),
            autoplay=bool(tts_raw.get("autoplay", True)),
            rate=str(tts_raw.get("rate", "") or ""),
            pitch=str(tts_raw.get("pitch", "") or ""),
        ),
        stt=SttToolConfig(
            model=str(stt_raw.get("model", "base") or "base"),
            language=str(stt_raw.get("language", "") or ""),
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
    """Persist cfg to ~/.alpi/config.yaml. Only non-default values survive."""
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
    ri_out: dict[str, Any] = {}
    if cfg.tools.read_image.model != d["read_image"]["model"]:
        ri_out["model"] = cfg.tools.read_image.model
    if cfg.tools.read_image.auto_resize != d["read_image"]["auto_resize"]:
        ri_out["auto_resize"] = cfg.tools.read_image.auto_resize
    if cfg.tools.read_image.max_edge != d["read_image"]["max_edge"]:
        ri_out["max_edge"] = cfg.tools.read_image.max_edge
    if ri_out:
        out["read_image"] = ri_out
    term_d = d["terminal"]
    term_out: dict[str, Any] = {}
    if cfg.tools.terminal.sandbox != term_d["sandbox"]:
        term_out["sandbox"] = cfg.tools.terminal.sandbox
    if cfg.tools.terminal.allow_network != term_d["allow_network"]:
        term_out["allow_network"] = cfg.tools.terminal.allow_network
    if term_out:
        out["terminal"] = term_out
    browser_out: dict[str, Any] = {}
    if cfg.tools.browser.vision != d["browser"]["vision"]:
        browser_out["vision"] = cfg.tools.browser.vision
    if cfg.tools.browser.human_typing != d["browser"]["human_typing"]:
        browser_out["human_typing"] = cfg.tools.browser.human_typing
    if cfg.tools.browser.typing_delay_ms != d["browser"]["typing_delay_ms"]:
        browser_out["typing_delay_ms"] = cfg.tools.browser.typing_delay_ms
    if browser_out:
        out["browser"] = browser_out
    tts_out: dict[str, Any] = {}
    if cfg.tools.tts.voice != d["tts"]["voice"]:
        tts_out["voice"] = cfg.tools.tts.voice
    if cfg.tools.tts.autoplay != d["tts"]["autoplay"]:
        tts_out["autoplay"] = cfg.tools.tts.autoplay
    if cfg.tools.tts.rate != d["tts"]["rate"]:
        tts_out["rate"] = cfg.tools.tts.rate
    if cfg.tools.tts.pitch != d["tts"]["pitch"]:
        tts_out["pitch"] = cfg.tools.tts.pitch
    if tts_out:
        out["tts"] = tts_out
    stt_out: dict[str, Any] = {}
    if cfg.tools.stt.model != d["stt"]["model"]:
        stt_out["model"] = cfg.tools.stt.model
    if cfg.tools.stt.language != d["stt"]["language"]:
        stt_out["language"] = cfg.tools.stt.language
    if stt_out:
        out["stt"] = stt_out
    return out


def resolve_model(cfg: Config) -> dict[str, Any]:
    """Return the litellm.completion kwargs for the currently selected model."""
    model_str = cfg.model
    head, _, rest = model_str.partition("/")

    ollama_eps = {c.get("name"): c for c in cfg.providers.get("ollama", [])}
    if head in ollama_eps:
        ep = ollama_eps[head]
        return {
            "model": f"openai/{rest}",
            "api_base": ep.get("url", "").rstrip("/") + "/v1",
            "api_key": "dummy",
        }

    return {"model": model_str}


def seed_defaults(home: Path) -> None:
    """Write a starter config.yaml on first run.

    ``.env`` is the wizard's output (``alpi setup``) — no starter
    template is shipped. The canonical list of keys lives in
    ``docs/CONFIG.md``; non-interactive deployments (CI, devcontainers)
    can populate ``.env`` directly from there.
    """
    cfg_path = home / "config.yaml"
    if not cfg_path.exists():
        cfg_path.write_text(yaml.safe_dump(SEED_CONFIG, sort_keys=False))
