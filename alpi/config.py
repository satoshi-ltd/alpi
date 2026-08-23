"""Config loader — reads ~/.alpi/config.yaml and ~/.alpi/.env."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from alpi import yamlfast

DEFAULT_CONFIG: dict[str, Any] = {
    "model": "",
    "fallback_models": [],
    "tiers": {
        "fast": {"model": "", "effort": ""},
        "deep": {"model": "", "effort": ""},
    },
    "workspace": "",
    "providers": {"ollama": []},
    "tools": {
        "max_steps_per_turn": 100,
        "deny": [],
        "web_extract": {"model": ""},
        "read_image": {"model": ""},
        "browser": {"vision": False, "allow_local": False},
        "terminal": {
            "sandbox": False,
            "allow_network": False,
            "approval": {"allowlist": []},
        },
        "tts": {
            "voice": "en-US-AriaNeural",
            "rate": "",
            "pitch": "",
            "auto_read": False,
        },
        "stt": {"model": "base", "language": ""},
        "attachments": {"max_text_tokens": 0},
    },
    "tui": {
        "show_cost": True,
        "show_tokens": True,
        "show_reasoning": True,
        "accent": "#c8a24e",
        "theme": "dark",
        "auto_resume": False,
    },
    "mcp": {
        "servers": {},
    },
    "email": {
        "accounts": {},
    },
    "runtime": {
        "first_byte_timeout_s": 300,
        "stream_idle_timeout_s": 120,
        "stream_max_duration_s": 600,
        "max_retries": 2,
        "retry_backoff_s": 1.5,
        "prefetch": "",
    },
}


SEED_CONFIG: dict[str, Any] = {
    "model": DEFAULT_CONFIG["model"],
    "providers": {"ollama": []},
    "mcp": {"servers": {}},
    "email": DEFAULT_CONFIG["email"],
}


@dataclass
class WebExtractToolConfig:
    model: str = ""  # empty = use main model


@dataclass
class ReadImageToolConfig:
    model: str = ""  # empty = use main model


@dataclass
class ApprovalConfig:
    allowlist: list[str] = field(default_factory=list)


@dataclass
class TerminalToolConfig:
    sandbox: bool = False
    allow_network: bool = False
    approval: ApprovalConfig = field(default_factory=ApprovalConfig)


@dataclass
class BrowserToolConfig:
    vision: bool = False
    allow_local: bool = False


@dataclass
class TtsToolConfig:
    voice: str = "en-US-AriaNeural"
    rate: str = ""  # "+10%" / "-20%" / "" = neutral
    pitch: str = ""  # "+5Hz" / "-10Hz" / "" = neutral
    auto_read: bool = False


@dataclass
class SttToolConfig:
    model: str = "base"  # tiny | base | small | medium | large-v3
    language: str = ""  # "" → auto-detect


@dataclass
class AttachmentsToolConfig:
    max_text_tokens: int = 0


@dataclass
class ToolsConfig:
    max_steps_per_turn: int = 100  # ceiling on tool-calls per user turn
    # Tool names hidden from the LLM schema AND refused by the executor; unknown names are no-ops so typos are harmless.
    deny: list[str] = field(default_factory=list)
    web_extract: WebExtractToolConfig = field(default_factory=WebExtractToolConfig)
    read_image: ReadImageToolConfig = field(default_factory=ReadImageToolConfig)
    terminal: TerminalToolConfig = field(default_factory=TerminalToolConfig)
    browser: BrowserToolConfig = field(default_factory=BrowserToolConfig)
    tts: TtsToolConfig = field(default_factory=TtsToolConfig)
    stt: SttToolConfig = field(default_factory=SttToolConfig)
    attachments: AttachmentsToolConfig = field(default_factory=AttachmentsToolConfig)


@dataclass
class MemoryConfig:
    # Post-turn reviewer cadence. 0 disables the reviewer entirely (default;
    # opt-in). N > 0 fires a daemon-thread reviewer every N user turns that
    # snapshots the conversation and writes durable facts via the memory tool.
    review_interval: int = 0


@dataclass
class ModelReasoningConfig:
    # "" | "low" | "medium" | "high" — applied only to cfg.model, never to mid-chat overrides or tool sub-models. "" = no reasoning param sent ("off" coerces to "" on save).
    effort: str = ""


TIER_NAMES = ("fast", "deep")


@dataclass
class TierConfig:
    model: str = ""  # empty = tier unconfigured, resolve to main model
    effort: str = ""


@dataclass
class TiersConfig:
    fast: TierConfig = field(default_factory=TierConfig)
    deep: TierConfig = field(default_factory=TierConfig)


@dataclass
class RuntimeConfig:
    # LLM provider stale-call hardening (RT.1). A timeout of 0 disables that watchdog.
    # first_byte is generous so slow reasoning models aren't killed before their first token.
    first_byte_timeout_s: float = 300.0
    stream_idle_timeout_s: float = 120.0
    stream_max_duration_s: float = 600.0
    max_retries: int = 2
    retry_backoff_s: float = 1.5
    prefetch: str = ""


@dataclass
class Config:
    home: Path
    model: str
    fallback_models: list[str] = field(default_factory=list)
    tiers: TiersConfig = field(default_factory=TiersConfig)
    providers: dict[str, Any] = field(default_factory=dict)
    tools: ToolsConfig = field(default_factory=ToolsConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    model_reasoning: ModelReasoningConfig = field(default_factory=ModelReasoningConfig)
    runtime: RuntimeConfig = field(default_factory=RuntimeConfig)
    tui: dict[str, Any] = field(default_factory=dict)
    email: dict[str, Any] = field(default_factory=dict)
    alp: dict[str, Any] = field(default_factory=dict)
    host: dict[str, Any] = field(default_factory=dict)
    # Shared "address other machines reach this profile at" — feeds both the
    # host control plane (device pairing) and the ALP peer listener. Empty =
    # auto-detect (Tailscale then LAN). Ports stay per-plane (host.tcp_port,
    # alp.tcp_port). See docs/ALP.md → Transport and docs/CONFIG.md → network.
    network: dict[str, Any] = field(default_factory=dict)
    budget: dict[str, Any] = field(default_factory=dict)
    relay: dict[str, Any] = field(default_factory=dict)
    workspace: str = ""  # "" → fall back to cwd
    # One-line public tag-line broadcast to every workgroup this
    # profile joins. Source of truth for ``Member.bio`` on the hub.
    # Empty string = don't publish anything (peers see name only).
    # AGENT.md stays private; this is the deliberate cross-agent
    # introduction the user opts into.
    public_bio: str = ""
    paused: bool = False
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def workspace_path(self) -> Path | None:
        """Return the workspace as a resolved Path, or None if unset."""
        w = (self.workspace or "").strip()
        if not w:
            return None
        return Path(w).expanduser().resolve()

    @property
    def agent_path(self) -> Path:
        from alpi.home import agent_path as _ap

        return _ap(self.home)

    @property
    def env_path(self) -> Path:
        return self.home / ".env"

    @property
    def config_path(self) -> Path:
        return self.home / "config.yaml"


_REMOVED_SERVICE_SWITCHES = ("schedule", "alp", "workgroups", "host")


def legacy_service_switches(cfg: Config) -> dict[str, Any]:
    raw = cfg.raw.get("service")
    if not isinstance(raw, dict):
        return {}
    return {name: raw[name] for name in _REMOVED_SERVICE_SWITCHES if name in raw}


def _non_negative_float(value: Any, default: float) -> float:
    try:
        n = float(value)
    except (TypeError, ValueError):
        return float(default)
    return n if n >= 0 else float(default)


def _non_negative_int(value: Any, default: int) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return int(default)
    return n if n >= 0 else int(default)


def _normalize_deny(raw: Any) -> list[str]:
    """Tolerate hand-written ``tools.deny`` shapes: must be a list, items get ``strip()``, duplicates dropped, order preserved. A bare string (``deny: terminal``) collapses to ``[]`` rather than iterating chars."""
    if not isinstance(raw, list):
        return []
    seen: set[str] = set()
    out: list[str] = []
    for item in raw:
        name = str(item).strip()
        if name and name not in seen:
            seen.add(name)
            out.append(name)
    return out


def _parse_tier(raw: Any) -> TierConfig:
    if not isinstance(raw, dict):
        return TierConfig()
    effort = str(raw.get("effort", "") or "").strip().lower()
    return TierConfig(
        model=str(raw.get("model", "") or "").strip(),
        effort=effort if effort in {"low", "medium", "high"} else "",
    )


def _normalize_fallbacks(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    seen: set[str] = set()
    out: list[str] = []
    for item in raw:
        name = str(item).strip()
        if name and name not in seen:
            seen.add(name)
            out.append(name)
    return out


def _deep_merge(defaults: dict, user: dict | None) -> dict:
    """Recursive merge — user wins per-key. Defaults are deep-copied so a caller mutating ``cfg.providers["ollama"].append(...)`` can never pollute ``DEFAULT_CONFIG``; the daemon supervises many profiles in one process and a shared mutable default would leak between them."""
    import copy
    merged = copy.deepcopy(defaults)
    for key, value in (user or {}).items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load(home: Path) -> Config:
    """Read ``<home>/config.yaml`` only. ``<home>/.env`` is NOT loaded into ``os.environ`` — daemon supervises many profiles, so per-profile secrets are pulled on demand via ``home.read_profile_env`` (see ``resolve_model``)."""
    cfg_path = home / "config.yaml"

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
    att_raw = tools_raw.get("attachments") or {}
    tools_cfg = ToolsConfig(
        max_steps_per_turn=int(
            tools_raw.get("max_steps_per_turn", DEFAULT_CONFIG["tools"]["max_steps_per_turn"])
        ),
        deny=_normalize_deny(tools_raw.get("deny")),
        web_extract=WebExtractToolConfig(
            model=str(web_extract_raw.get("model", "") or ""),
        ),
        read_image=ReadImageToolConfig(
            model=str(read_image_raw.get("model", "") or ""),
        ),
        terminal=TerminalToolConfig(
            sandbox=bool(terminal_raw.get("sandbox", False)),
            allow_network=bool(terminal_raw.get("allow_network", False)),
            approval=ApprovalConfig(
                allowlist=[
                    str(x) for x in (
                        (terminal_raw.get("approval") or {}).get("allowlist") or []
                    )
                ],
            ),
        ),
        browser=BrowserToolConfig(
            vision=bool(browser_raw.get("vision", False)),
            allow_local=bool(browser_raw.get("allow_local", False)),
        ),
        tts=TtsToolConfig(
            voice=str(tts_raw.get("voice", "en-US-AriaNeural") or "en-US-AriaNeural"),
            rate=str(tts_raw.get("rate", "") or ""),
            pitch=str(tts_raw.get("pitch", "") or ""),
            auto_read=bool(tts_raw.get("auto_read", False)),
        ),
        stt=SttToolConfig(
            model=str(stt_raw.get("model", "base") or "base"),
            language=str(stt_raw.get("language", "") or ""),
        ),
        attachments=AttachmentsToolConfig(
            max_text_tokens=_non_negative_int(
                att_raw.get("max_text_tokens"),
                DEFAULT_CONFIG["tools"]["attachments"]["max_text_tokens"],
            ),
        ),
    )

    mem_raw = data.get("memory") or {}
    memory_cfg = MemoryConfig(
        review_interval=int(mem_raw.get("review_interval", 0) or 0),
    )

    tiers_raw = data.get("tiers") or {}
    tiers_cfg = TiersConfig(
        fast=_parse_tier(tiers_raw.get("fast")),
        deep=_parse_tier(tiers_raw.get("deep")),
    )

    reasoning_raw = data.get("model_reasoning") or {}
    # "off" persisted on disk normalises to "" on load — keeps the dataclass canonical (empty string = no param).
    effort_in = str(reasoning_raw.get("effort", "") or "").strip().lower()
    reasoning_cfg = ModelReasoningConfig(
        effort=effort_in if effort_in in {"low", "medium", "high"} else "",
    )

    rt_raw = data.get("runtime") or {}
    legacy_service = user_data.get("service") or {}
    if not isinstance(legacy_service, dict):
        legacy_service = {}
    rt_defaults = DEFAULT_CONFIG["runtime"]
    runtime_cfg = RuntimeConfig(
        first_byte_timeout_s=_non_negative_float(rt_raw.get("first_byte_timeout_s"), rt_defaults["first_byte_timeout_s"]),
        stream_idle_timeout_s=_non_negative_float(rt_raw.get("stream_idle_timeout_s"), rt_defaults["stream_idle_timeout_s"]),
        stream_max_duration_s=_non_negative_float(rt_raw.get("stream_max_duration_s"), rt_defaults["stream_max_duration_s"]),
        max_retries=_non_negative_int(rt_raw.get("max_retries"), rt_defaults["max_retries"]),
        retry_backoff_s=_non_negative_float(rt_raw.get("retry_backoff_s"), rt_defaults["retry_backoff_s"]),
        prefetch=str(
            rt_raw.get("prefetch") or legacy_service.get("prefetch") or ""
        ).strip().lower(),
    )

    return Config(
        home=home,
        model=data.get("model", DEFAULT_CONFIG["model"]),
        fallback_models=_normalize_fallbacks(data.get("fallback_models")),
        tiers=tiers_cfg,
        providers=data.get("providers", DEFAULT_CONFIG["providers"]),
        tools=tools_cfg,
        memory=memory_cfg,
        model_reasoning=reasoning_cfg,
        runtime=runtime_cfg,
        tui=data.get("tui", DEFAULT_CONFIG["tui"]),
        email=data.get("email", DEFAULT_CONFIG["email"]),
        alp=dict(data.get("alp") or {}),
        host=dict(data.get("host") or {}),
        network=dict(data.get("network") or {}),
        budget=dict(data.get("budget") or {}),
        relay=dict(data.get("relay") or {}),
        workspace=str(data.get("workspace", "") or ""),
        public_bio=str(data.get("public_bio", "") or ""),
        paused=bool(data.get("paused", False)),
        raw=user_data,
    )


def save(cfg: Config) -> None:
    """Persist cfg to ~/.alpi/config.yaml. Only non-default values survive."""
    data: dict[str, Any] = {
        "model": cfg.model,
        "providers": cfg.providers,
        "mcp": cfg.raw.get("mcp", {"servers": {}}),
        "email": _sanitize_email(cfg.email),
    }
    if cfg.workspace:
        data["workspace"] = cfg.workspace
    if cfg.relay:
        data["relay"] = cfg.relay
    if cfg.public_bio:
        data["public_bio"] = cfg.public_bio
    if cfg.paused:
        data["paused"] = True
    if cfg.fallback_models:
        data["fallback_models"] = cfg.fallback_models

    tiers_delta: dict[str, Any] = {}
    for tier_name in TIER_NAMES:
        tcfg: TierConfig = getattr(cfg.tiers, tier_name)
        if tcfg.model:
            row: dict[str, Any] = {"model": tcfg.model}
            if tcfg.effort:
                row["effort"] = tcfg.effort
            tiers_delta[tier_name] = row
    if tiers_delta:
        data["tiers"] = tiers_delta

    tools_delta = _tools_delta(cfg)
    if tools_delta:
        data["tools"] = tools_delta

    if cfg.model_reasoning.effort:
        data["model_reasoning"] = {"effort": cfg.model_reasoning.effort}

    tui_delta = {k: v for k, v in (cfg.tui or {}).items() if v != DEFAULT_CONFIG["tui"].get(k)}
    if tui_delta:
        data["tui"] = tui_delta

    if cfg.alp:
        data["alp"] = cfg.alp

    if cfg.host:
        data["host"] = cfg.host

    if cfg.network:
        data["network"] = cfg.network

    if cfg.budget:
        data["budget"] = cfg.budget

    rt_defaults = RuntimeConfig()
    runtime_delta = {
        k: getattr(cfg.runtime, k)
        for k in (
            "first_byte_timeout_s", "stream_idle_timeout_s", "stream_max_duration_s", "max_retries",
            "retry_backoff_s", "prefetch",
        )
        if getattr(cfg.runtime, k) != getattr(rt_defaults, k)
    }
    if runtime_delta:
        data["runtime"] = runtime_delta

    atomic_write_yaml(cfg.config_path, data)


def atomic_write_yaml(path: Path, data: dict[str, Any] | list[Any]) -> None:
    import tempfile
    path.parent.mkdir(parents=True, exist_ok=True)
    # Never yaml.safe_dump here: the pure emitter loses an embedded U+0085 and escapes lone surrogates into files no loader accepts.
    text = yamlfast.safe_dump(data, sort_keys=False, allow_unicode=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp",
    )
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, 0o600)
        os.replace(str(tmp), str(path))
    except Exception:
        try:
            tmp.unlink()
        except FileNotFoundError:
            pass
        raise
    if hasattr(os, "O_DIRECTORY"):
        try:
            dir_fd = os.open(str(path.parent), os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except OSError:
            pass


_EMAIL_ALLOWED_KEYS: dict[str, frozenset[str]] = {
    "imap": frozenset({"type", "address", "imap_host", "imap_port", "smtp_host", "smtp_port"}),
    "gmail": frozenset({"type", "address"}),
}


def _sanitize_email(email: dict) -> dict:
    from alpi.mail.accounts import valid_id
    accounts_in = (email or {}).get("accounts") or {}
    accounts_out: dict[str, Any] = {}
    for account_id, row in accounts_in.items():
        if not isinstance(row, dict) or not valid_id(str(account_id)):
            continue
        allowed = _EMAIL_ALLOWED_KEYS.get(str(row.get("type") or "imap"), _EMAIL_ALLOWED_KEYS["imap"])
        accounts_out[str(account_id)] = {k: v for k, v in row.items() if k in allowed}
    return {"accounts": accounts_out}


def _tools_delta(cfg: Config) -> dict:
    out: dict[str, Any] = {}
    d = DEFAULT_CONFIG["tools"]
    if cfg.tools.max_steps_per_turn != d["max_steps_per_turn"]:
        out["max_steps_per_turn"] = cfg.tools.max_steps_per_turn
    if cfg.tools.deny:
        out["deny"] = list(cfg.tools.deny)
    if cfg.tools.web_extract.model != d["web_extract"]["model"]:
        out["web_extract"] = {"model": cfg.tools.web_extract.model}
    ri_out: dict[str, Any] = {}
    if cfg.tools.read_image.model != d["read_image"]["model"]:
        ri_out["model"] = cfg.tools.read_image.model
    if ri_out:
        out["read_image"] = ri_out
    term_d = d["terminal"]
    term_out: dict[str, Any] = {}
    if cfg.tools.terminal.sandbox != term_d["sandbox"]:
        term_out["sandbox"] = cfg.tools.terminal.sandbox
    if cfg.tools.terminal.allow_network != term_d["allow_network"]:
        term_out["allow_network"] = cfg.tools.terminal.allow_network
    if cfg.tools.terminal.approval.allowlist:
        term_out["approval"] = {"allowlist": list(cfg.tools.terminal.approval.allowlist)}
    if term_out:
        out["terminal"] = term_out
    browser_out: dict[str, Any] = {}
    if cfg.tools.browser.vision != d["browser"]["vision"]:
        browser_out["vision"] = cfg.tools.browser.vision
    if cfg.tools.browser.allow_local != d["browser"]["allow_local"]:
        browser_out["allow_local"] = cfg.tools.browser.allow_local
    if browser_out:
        out["browser"] = browser_out
    tts_out: dict[str, Any] = {}
    if cfg.tools.tts.voice != d["tts"]["voice"]:
        tts_out["voice"] = cfg.tools.tts.voice
    if cfg.tools.tts.rate != d["tts"]["rate"]:
        tts_out["rate"] = cfg.tools.tts.rate
    if cfg.tools.tts.pitch != d["tts"]["pitch"]:
        tts_out["pitch"] = cfg.tools.tts.pitch
    if cfg.tools.tts.auto_read != d["tts"]["auto_read"]:
        tts_out["auto_read"] = cfg.tools.tts.auto_read
    if tts_out:
        out["tts"] = tts_out
    stt_out: dict[str, Any] = {}
    if cfg.tools.stt.model != d["stt"]["model"]:
        stt_out["model"] = cfg.tools.stt.model
    if cfg.tools.stt.language != d["stt"]["language"]:
        stt_out["language"] = cfg.tools.stt.language
    if stt_out:
        out["stt"] = stt_out
    if cfg.tools.attachments.max_text_tokens != d["attachments"]["max_text_tokens"]:
        out["attachments"] = {"max_text_tokens": cfg.tools.attachments.max_text_tokens}
    return out


_CLOUD_API_KEY_ENV = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "groq": "GROQ_API_KEY",
}


def tier_model(cfg: Config, tier: str | None) -> str:
    """Return the model configured for ``tier``, or "" when the tier is unset/unknown."""
    if tier not in TIER_NAMES:
        return ""
    return getattr(cfg.tiers, tier).model


def resolve_model(
    cfg: Config, *, model: str | None = None, tier: str | None = None,
    include_reasoning: bool = True,
) -> dict[str, Any]:
    """Return the litellm.completion kwargs for the currently selected model.

    Cloud api keys are read from the profile's ``<home>/.env`` (never
    ``os.environ``) so two profiles in the same daemon process can hold
    different keys for the same provider without cross-contamination.

    ``model`` override: when an explicit ``model`` is passed, the helper
    resolves THAT model's api_base / api_key and does NOT attach the
    profile's reasoning_effort (the override is a different model, not
    a different reasoning preference). The default-model path keeps
    reasoning when ``cfg.model_reasoning.effort`` is set and the model
    supports it.

    ``tier`` routing: ``"fast"`` / ``"deep"`` resolve the tier's model and
    the tier's OWN effort (never the profile effort). An unconfigured tier,
    ``"main"``, or any unknown value falls back to the default-model path,
    so profiles without ``tiers`` in config.yaml behave exactly as before.
    An explicit ``model`` wins over ``tier``.
    """
    if model is None and tier in TIER_NAMES:
        tcfg: TierConfig = getattr(cfg.tiers, tier)
        if tcfg.model:
            out = resolve_model(cfg, model=tcfg.model, include_reasoning=False)
            if tcfg.effort:
                from alpi.providers.reasoning import merge_into_kwargs, reasoning_kwargs
                extra = reasoning_kwargs(tcfg.model, tcfg.effort)
                if extra:
                    out = merge_into_kwargs(out, extra)
            return out

    model_str = model or cfg.model
    head, _, rest = model_str.partition("/")
    is_default_model = model is None or model == cfg.model

    ollama_eps = {c.get("name"): c for c in cfg.providers.get("ollama", [])}
    if head in ollama_eps:
        ep = ollama_eps[head]
        return {
            "model": f"openai/{rest}",
            "api_base": ep.get("url", "").rstrip("/") + "/v1",
            "api_key": "dummy",
        }

    out: dict[str, Any] = {"model": model_str}
    env_var = _CLOUD_API_KEY_ENV.get(head)
    if env_var:
        from alpi.home import read_profile_env
        key = read_profile_env(cfg.home).get(env_var, "").strip()
        if key:
            out["api_key"] = key
    if include_reasoning and is_default_model and cfg.model_reasoning.effort:
        from alpi.providers.reasoning import merge_into_kwargs, reasoning_kwargs
        extra = reasoning_kwargs(model_str, cfg.model_reasoning.effort)
        if extra:
            out = merge_into_kwargs(out, extra)
    return out


def seed_defaults(home: Path) -> None:
    """Write a starter config.yaml on first run.

    ``.env`` is the wizard's output (``alpi setup``) — no starter
    template is shipped. The canonical list of keys lives in
    ``docs/CONFIG.md``; non-interactive deployments (CI, devcontainers)
    can populate ``.env`` directly from there.
    """
    cfg_path = home / "config.yaml"
    if not cfg_path.exists():
        cfg_path.write_text(
            yamlfast.safe_dump(SEED_CONFIG, sort_keys=False, allow_unicode=True),
        )
