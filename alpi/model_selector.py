"""Interactive model selector."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from alpi import config as cfg_mod
from alpi import providers as prov_mod
from alpi import ui
from alpi.providers.base import Provider


_MANAGE_SAVED = "__manage_saved__"
_ADD_OLLAMA = "__add_ollama__"
_ENTER_CUSTOM_MODEL = "__custom_model__"


# Back-compat re-export for callers that still import from here.
def accent_style(accent: str):
    return ui.accent_style(accent)


def _ask(question):
    return ui._ask(question)



def run(cfg: cfg_mod.Config) -> None:
    """Block until the user selects a model or cancels."""
    provider = _pick_provider(cfg)
    if provider is None:
        ui.dim("No change.")
        return

    _ensure_key(cfg, provider)

    model_id = _pick_model(provider, cfg)
    if model_id is None:
        ui.dim("No change.")
        return

    cfg.model = model_id
    _remember_openrouter_model(cfg, model_id)
    _pick_reasoning_effort(cfg, model_id)
    cfg_mod.save(cfg)
    ui.ok_and_wait(f"model set to [b]{model_id}[/b]")


def _pick_reasoning_effort(cfg: cfg_mod.Config, model_id: str) -> None:
    """Prompt for reasoning effort only on models that declare support."""
    from alpi.providers.reasoning import supports_reasoning
    if not supports_reasoning(model_id):
        cfg.model_reasoning.effort = ""
        return
    current = cfg.model_reasoning.effort or "medium"
    items = [
        ("Default", "",       "use provider default"),
        ("Low",     "low",    "fastest, cheapest"),
        ("Medium",  "medium", "balanced"),
        ("High",    "high",   "slower, more thorough"),
    ]
    choice = ui.menu(
        f"Reasoning effort for {model_id}",
        items,
        subtitle=f"current: {current}",
        home=cfg.home,
    )
    if choice is None:
        return
    cfg.model_reasoning.effort = choice


def _remember_openrouter_model(cfg: cfg_mod.Config, model_id: str) -> None:
    if not model_id.startswith("openrouter/"):
        return
    suffix = model_id.split("/", 1)[1]
    if not suffix:
        return
    or_cfg = cfg.providers.setdefault("openrouter", {})
    models = or_cfg.setdefault("models", [])
    if suffix in models:
        models.remove(suffix)
    models.insert(0, suffix)



def _pick_provider(cfg: cfg_mod.Config) -> Provider | None:
    from alpi.home import effective_profile_env
    env = effective_profile_env(cfg.home)

    builtin = prov_mod.builtin()
    ollamas = prov_mod.ollama(cfg.providers.get("ollama", []))
    active_head = cfg.model.split("/", 1)[0]
    accent = (cfg.tui or {}).get("accent", "") or ""

    local: list[tuple[str, str, Any, bool]] = []
    for p in ollamas:
        local.append((p.name, f"ollama · {p.url}", p, p.name == active_head))
    local.append(("Add Ollama", "local or remote — private, offline-first",
                  _ADD_OLLAMA, False))

    cloud: list[tuple[str, str, Any, bool]] = []
    for p in builtin:
        parts = []
        if p.api_key_env and p.has_key(env):
            parts.append("key saved")
        parts.append(p.description)
        if p.api_key_env and not p.has_key(env):
            parts.append("[key needed]")
        cloud.append((p.display, " · ".join(parts), p, p.name == active_head))

    manage: list[tuple[str, str, Any, bool]] = []
    if ollamas or _any_saved_keys(builtin, env):
        manage.append(("Remove keys", "delete API keys or Ollama servers",
                       _MANAGE_SAVED, False))

    all_rows = local + cloud + manage
    width = max((len(lab) for lab, status, _v, _a in all_rows if status), default=0)

    def _render_row(label: str, status: str, value: Any, active: bool):
        if active:
            return (ui.row_accent(label, status, accent, width=width), value)
        return (ui.row(label, status, width=width), value)

    items: list = [ui.Heading("Local")]
    for label, status, value, active in local:
        items.append(_render_row(label, status, value, active))
    items.append(ui.Heading("Cloud"))
    for label, status, value, active in cloud:
        items.append(_render_row(label, status, value, active))
    if manage:
        items.append(ui.Heading("Manage"))
        for label, status, value, active in manage:
            items.append(_render_row(label, status, value, active))

    result = ui.menu(
        ui.crumb("setup", "model"),
        items,
        subtitle=f"active: {cfg.model or 'none'}",
        home=cfg.home,
        close="Back",
    )

    if result is None:
        return None
    if result == _ADD_OLLAMA:
        new_ep = _add_ollama_connection(cfg)
        if new_ep is None:
            return None
        cfg_mod.save(cfg)
        return new_ep
    if result == _MANAGE_SAVED:
        _manage_saved(cfg)
        cfg_mod.save(cfg)
        return None
    return result



def _pick_model(provider: Provider, cfg: cfg_mod.Config) -> str | None:
    ui.dim(f"Fetching models from {provider.display}…")
    models = provider.list_models()

    current_suffix = ""
    if cfg.model.startswith(f"{provider.name}/"):
        current_suffix = cfg.model.split("/", 1)[1]

    # If no models come back, skip the menu and prompt directly.
    if not models:
        return _prompt_custom_model(provider, current_suffix)

    accent = (cfg.tui or {}).get("accent", "") or ""

    collected: list[tuple[str, str, str, bool]] = []
    for m in models:
        qualified = m.id if "/" in m.id else f"{provider.name}/{m.id}"
        collected.append((
            m.display, m.note or "", m.id, qualified == cfg.model,
        ))
    collected.append(("Custom model name", "type it yourself",
                      _ENTER_CUSTOM_MODEL, False))

    width = max((len(lab) for lab, status, _v, _a in collected if status), default=0)

    items: list = []
    for label, status, value, active in collected:
        if active:
            items.append((
                ui.row_accent(label, status, accent, width=width), value,
            ))
        else:
            items.append((
                ui.row(label, status, width=width), value,
            ))

    result = ui.menu(
        ui.crumb("setup", "model", provider.name),
        items,
        subtitle=f"pick a {provider.display} model",
        home=cfg.home,
        close="Back",
    )

    if result is None:
        return None
    if result == _ENTER_CUSTOM_MODEL:
        return _prompt_custom_model(provider, current_suffix)
    return result  # litellm-ready id


def _prompt_custom_model(provider: Provider, current: str) -> str | None:
    raw = ui.text("Model name", default=current)
    if not raw:
        return None
    raw = raw.strip()
    if not raw.startswith(f"{provider.name}/"):
        raw = f"{provider.name}/{raw}"
    return raw



def _ensure_key(cfg: cfg_mod.Config, provider: Provider) -> None:
    from alpi.home import effective_profile_env
    env = effective_profile_env(cfg.home)
    if not provider.api_key_env or provider.has_key(env):
        return
    value = ui.password(f"Enter {provider.api_key_env} for {provider.display}:")
    if not value:
        return
    _append_env(cfg.env_path, provider.api_key_env, value)


def _add_ollama_connection(cfg: cfg_mod.Config):
    from alpi.providers.ollama import DEFAULT_URL, OllamaProvider
    ui.banner(
        ui.crumb("setup", "model", "ollama"),
        subtitle="add an Ollama server",
        home=cfg.home,
    )
    name = ui.text("Server name (short id, e.g. 'local', 'home-gpu')")
    if not name:
        return None
    name = name.strip()
    taken = {e.get("name") for e in cfg.providers.get("ollama", []) or []}
    if name in taken:
        ui.fail(f"a connection named {name!r} already exists")
        ui.press_enter()
        return None
    url = ui.text("URL", default=DEFAULT_URL)
    if not url:
        return None
    url = url.strip().rstrip("/")
    entry = {"name": name, "url": url}
    cfg.providers.setdefault("ollama", []).append(entry)
    return OllamaProvider(name=name, url=url)


def _atomic_write_env(env_path: Path, content: str) -> None:
    from alpi.secrets_io import safe_write_secret
    safe_write_secret(env_path, content)


def _append_env(env_path: Path, key: str, value: str) -> None:
    lines = env_path.read_text().splitlines() if env_path.exists() else []
    out, replaced = [], False
    for line in lines:
        if line.startswith(f"{key}="):
            out.append(f"{key}={value}")
            replaced = True
        else:
            out.append(line)
    if not replaced:
        out.append(f"{key}={value}")
    _atomic_write_env(env_path, "\n".join(out) + "\n")


def _remove_env_key(env_path: Path, key: str) -> None:
    if not env_path.exists():
        return
    lines = [ln for ln in env_path.read_text().splitlines()
             if not ln.startswith(f"{key}=")]
    _atomic_write_env(env_path, "\n".join(lines) + ("\n" if lines else ""))


def model_prefix_for_env_key(key: str) -> str:
    for p in prov_mod.builtin():
        if p.api_key_env == key:
            return p.model_prefix or p.name
    return ""


# Dual-write: edits .env AND saves config.yaml when the active model pointed at the removed provider (returns True in that case).
def unset_provider_key(cfg: cfg_mod.Config, key: str) -> bool:
    _remove_env_key(cfg.env_path, key)
    prefix = model_prefix_for_env_key(key)
    if prefix and cfg.model.split("/", 1)[0] == prefix:
        cfg.model = ""
        cfg_mod.save(cfg)
        return True
    return False


def _any_saved_keys(builtin: list[Provider], env: dict[str, str] | None = None) -> bool:
    return any(p.has_key(env) for p in builtin if p.api_key_env)


# Saved keys submenu.
def _manage_saved(cfg: cfg_mod.Config) -> None:
    from alpi.home import effective_profile_env
    env = effective_profile_env(cfg.home)

    builtin = prov_mod.builtin()

    items: list = []
    for p in builtin:
        if p.api_key_env and env.get(p.api_key_env):
            items.append((p.api_key_env, ("key", p.api_key_env), "API key in .env"))
    for entry in cfg.providers.get("ollama", []) or []:
        name = entry.get("name", "")
        items.append((name, ("ollama", name), f"ollama · {entry.get('url', '')}"))

    if not items:
        ui.dim("Nothing saved to remove.")
        return

    choice = ui.menu(
        ui.crumb("setup", "model", "saved"),
        items,
        subtitle="remove an API key or Ollama server",
        home=cfg.home,
        close="Back",
    )
    if not choice or not isinstance(choice, tuple):
        return
    kind, target = choice
    if kind == "key":
        if unset_provider_key(cfg, target):
            ui.ok_and_wait(f"removed {target} from .env; cleared active model")
        else:
            ui.ok_and_wait(f"removed {target} from .env")
    elif kind == "ollama":
        cfg.providers["ollama"] = [
            e for e in cfg.providers.get("ollama", [])
            if e.get("name") != target
        ]
        if cfg.model.startswith(f"{target}/"):
            cfg.model = ""
        ui.ok_and_wait(f"removed ollama server '{target}'")
