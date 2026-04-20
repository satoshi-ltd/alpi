"""Interactive model selector."""

from __future__ import annotations

import os
from pathlib import Path

from alf import config as cfg_mod
from alf import providers as prov_mod
from alf import ui
from alf.providers.base import ModelInfo, Provider
from alf.providers.custom import CustomProvider


_ADD_CUSTOM = "__add_custom__"
_MANAGE_SAVED = "__manage_saved__"
_ENTER_CUSTOM_MODEL = "__custom_model__"


# Re-exported for back-compat with existing callers (wizards import
# ``accent_style`` from here). New code should import from ``alf.ui``.
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
    cfg_mod.save(cfg)
    ui.ok(f"model set to [b]{model_id}[/b]")



def _pick_provider(cfg: cfg_mod.Config) -> Provider | None:
    builtin = prov_mod.builtin()
    custom = prov_mod.custom(cfg.providers.get("custom", []))
    active_head = cfg.model.split("/", 1)[0]

    items: list = []
    for p in builtin:
        # Status reads left-to-right: configured-state first, then
        # the provider's own blurb, then any "[key needed]" warning.
        # Putting "active" at the start makes it the first thing the
        # eye catches as it scans the column.
        parts = []
        if p.name == active_head:
            parts.append("active")
        if p.api_key_env and p.has_key():
            parts.append("key saved")
        parts.append(p.description)
        if p.api_key_env and not p.has_key():
            parts.append("[key needed]")
        items.append((ui.row(p.display, " · ".join(parts)), p))

    # "Custom" inline with the built-ins — just another provider slot.
    items.append((
        ui.row("Custom", "OpenAI-compatible endpoint (add a new one)"),
        _ADD_CUSTOM,
    ))

    for p in custom:
        parts = []
        if p.name == active_head:
            parts.append("active")
        parts.append(p.base_url if hasattr(p, "base_url") else "custom endpoint")
        items.append((ui.row(p.display, " · ".join(parts)), p))

    # Manage saved keys lives in its own row directly under the
    # provider list — no separator, no submenu header. Treated as
    # just another action the user can pick, on the same level as
    # the providers themselves.
    if custom or _any_saved_keys(builtin):
        items.append((
            ui.row("⋯ Manage saved keys", "remove endpoints or API keys"),
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
    if result == _ADD_CUSTOM:
        new_ep = _add_custom_endpoint(cfg)
        if new_ep is None:
            return None
        cfg_mod.save(cfg)
        return new_ep
    if result == _MANAGE_SAVED:
        _manage_saved(cfg)
        cfg_mod.save(cfg)
        return None
    return result  # a Provider instance



def _pick_model(provider: Provider, cfg: cfg_mod.Config) -> str | None:
    ui.dim(f"Fetching models from {provider.display}…")
    models = provider.list_models()

    current_suffix = ""
    if cfg.model.startswith(f"{provider.name}/"):
        current_suffix = cfg.model.split("/", 1)[1]

    # No catalog (openrouter without API key, anthropic rate-limited,
    # etc.) → drop the menu and prompt directly; there's nothing to
    # pick from.
    if not models:
        return _prompt_custom_model(provider, current_suffix)

    items: list = []
    for m in models:
        # Mark the currently active model so the user sees at a glance
        # which row is live. Match against the fully-qualified id
        # (``<provider>/<model>``) because that's how ``cfg.model`` is
        # stored; some providers emit ``m.id`` already prefixed, others
        # don't — normalise once.
        qualified = m.id if "/" in m.id else f"{provider.name}/{m.id}"
        status_parts = []
        if qualified == cfg.model:
            status_parts.append("active")
        if m.note:
            status_parts.append(m.note)
        status = " · ".join(status_parts)
        items.append((ui.row(m.display, status) if status else m.display, m.id))

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



def _add_custom_endpoint(cfg: cfg_mod.Config) -> CustomProvider | None:
    ui.banner(
        ui.crumb("setup", "model", "custom"),
        subtitle="OpenAI-compatible endpoint",
        home=cfg.home,
    )
    name = ui.text("Endpoint name (short id, e.g. 'my-ollama')")
    if not name:
        return None
    base_url = ui.text("Base URL (e.g. http://localhost:11434/v1):")
    if not base_url:
        return None
    needs_key = ui.confirm("Does this endpoint require an API key?", default=False)
    api_key_env = ""
    if needs_key:
        api_key_env = ui.text("Env var name for the key (e.g. MY_ENDPOINT_KEY):") or ""
        if api_key_env:
            value = ui.password(f"Value for {api_key_env} (stored in ~/.alf/.env):")
            if value:
                _append_env(cfg.env_path, api_key_env, value)
                os.environ[api_key_env] = value

    entry = {"name": name, "base_url": base_url, "api_key_env": api_key_env}
    cfg.providers.setdefault("custom", []).append(entry)
    return CustomProvider(
        name=name,
        display=f"{name}  ({base_url})",
        base_url=base_url,
        api_key_env=api_key_env,
    )


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
    for entry in cfg.providers.get("custom", []) or []:
        name = entry.get("name", "")
        items.append((
            ui.row(name, "custom endpoint"),
            ("custom", name),
        ))

    if not items:
        ui.dim("Nothing saved to remove.")
        return

    choice = ui.menu(
        ui.crumb("setup", "model", "saved"),
        items,
        subtitle="remove an API key or custom endpoint",
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
    elif kind == "custom":
        cfg.providers["custom"] = [
            e for e in cfg.providers.get("custom", [])
            if e.get("name") != target
        ]
        ui.ok(f"removed custom endpoint '{target}'")
