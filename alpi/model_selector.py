"""Interactive model selector."""

from __future__ import annotations

import os
from pathlib import Path

from alpi import config as cfg_mod
from alpi import providers as prov_mod
from alpi import ui
from alpi.providers.base import ModelInfo, Provider


_MANAGE_SAVED = "__manage_saved__"
_ADD_OLLAMA = "__add_ollama__"
_ENTER_CUSTOM_MODEL = "__custom_model__"


# Re-exported for back-compat with existing callers (wizards import
# ``accent_style`` from here). New code should import from ``alpi.ui``.
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
    cfg_mod.save(cfg)
    ui.ok(f"model set to [b]{model_id}[/b]")


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
    builtin = prov_mod.builtin()
    ollamas = prov_mod.ollama(cfg.providers.get("ollama", []))
    active_head = cfg.model.split("/", 1)[0]
    accent = (cfg.tui or {}).get("accent", "") or ""

    def _row(label: str, status: str, active: bool):
        return ui.row_accent(label, status, accent) if active else ui.row(label, status)

    items: list = []

    for p in ollamas:
        items.append((
            _row(p.name, f"ollama · {p.url}", p.name == active_head),
            p,
        ))
    items.append((
        ui.row("Add Ollama", "local or remote — private, offline-first"),
        _ADD_OLLAMA,
    ))

    items.append(None)  # separator between local and cloud providers

    for p in builtin:
        parts = []
        if p.api_key_env and p.has_key():
            parts.append("key saved")
        parts.append(p.description)
        if p.api_key_env and not p.has_key():
            parts.append("[key needed]")
        items.append((
            _row(p.display, " · ".join(parts), p.name == active_head),
            p,
        ))

    if ollamas or _any_saved_keys(builtin):
        items.append((
            ui.row("Remove keys", "delete API keys or Ollama servers"),
            _MANAGE_SAVED,
        ))

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

    # Empty list (openrouter without registered models, fetch failed,
    # etc.) → drop the menu and prompt directly.
    if not models:
        return _prompt_custom_model(provider, current_suffix)

    accent = (cfg.tui or {}).get("accent", "") or ""
    items: list = []
    for m in models:
        qualified = m.id if "/" in m.id else f"{provider.name}/{m.id}"
        is_active = qualified == cfg.model
        status = m.note or ""
        if is_active:
            items.append((ui.row_accent(m.display, status, accent), m.id))
        elif status:
            items.append((ui.row(m.display, status), m.id))
        else:
            items.append((m.display, m.id))

    items.append(("Custom model name", _ENTER_CUSTOM_MODEL))

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
    if not provider.api_key_env or provider.has_key():
        return
    value = ui.password(f"Enter {provider.api_key_env} for {provider.display}:")
    if not value:
        return
    _append_env(cfg.env_path, provider.api_key_env, value)
    os.environ[provider.api_key_env] = value


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
    env_path.write_text("\n".join(out) + "\n")


def _remove_env_key(env_path: Path, key: str) -> None:
    if not env_path.exists():
        return
    lines = [ln for ln in env_path.read_text().splitlines()
             if not ln.startswith(f"{key}=")]
    env_path.write_text("\n".join(lines) + ("\n" if lines else ""))


def _any_saved_keys(builtin: list[Provider]) -> bool:
    return any(p.has_key() for p in builtin if p.api_key_env)



# Manage saved (submenu, out of the main picker)


def _manage_saved(cfg: cfg_mod.Config) -> None:
    builtin = prov_mod.builtin()

    items: list = []
    for p in builtin:
        if p.api_key_env and os.environ.get(p.api_key_env):
            items.append((
                ui.row(p.api_key_env, "API key in .env"),
                ("key", p.api_key_env),
            ))
    for entry in cfg.providers.get("ollama", []) or []:
        name = entry.get("name", "")
        items.append((
            ui.row(name, f"ollama · {entry.get('url', '')}"),
            ("ollama", name),
        ))

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
        _remove_env_key(cfg.env_path, target)
        os.environ.pop(target, None)
        ui.ok(f"removed {target} from .env")
    elif kind == "ollama":
        cfg.providers["ollama"] = [
            e for e in cfg.providers.get("ollama", [])
            if e.get("name") != target
        ]
        ui.ok(f"removed ollama server '{target}'")
