"""Interactive model selector.

Two-step flow:
  1. Pick a provider (built-in + saved custom endpoints + add/remove/cancel)
  2. Pick a model within that provider (+ enter custom model name / skip)

Reads/writes ``~/.alf/config.yaml`` and ``~/.alf/.env``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import questionary
from prompt_toolkit.key_binding import KeyBindings
from rich.console import Console

from alf import config as cfg_mod
from alf import providers as prov_mod
from alf.providers.base import ModelInfo, Provider
from alf.providers.custom import CustomProvider

_console = Console()

def _ask(question) -> object:
    """Run a questionary Question after wiring ESC → cancel (returns None)."""
    try:
        app = question.application
        app.key_bindings.add("escape", eager=True)(
            lambda event: event.app.exit(result=None)
        )
    except Exception:
        pass
    try:
        return question.unsafe_ask()
    except KeyboardInterrupt:
        return None


_ADD_CUSTOM = "__add_custom__"
_REMOVE_SAVED = "__remove_saved__"
_CANCEL = "__cancel__"
_ENTER_CUSTOM_MODEL = "__custom_model__"
_SKIP = "__skip__"


@dataclass
class _Choice:
    name: str
    value: object


def run(cfg: cfg_mod.Config) -> None:
    """Entry point. Blocks until the user selects or cancels."""
    _console.print(f"[bold]Current model:[/bold] {cfg.model}")
    provider = _pick_provider(cfg)
    if provider is None:
        _console.print("[dim]No change.[/dim]")
        return

    _ensure_key(cfg, provider)

    model_id = _pick_model(provider)
    if model_id is None:
        _console.print("[dim]No change.[/dim]")
        return

    cfg.model = model_id
    cfg_mod.save(cfg)
    _console.print(f"[green]✓[/green] model set to [bold]{model_id}[/bold]")


def _pick_provider(cfg: cfg_mod.Config) -> Provider | None:
    builtin = prov_mod.builtin()
    custom = prov_mod.custom(cfg.providers.get("custom", []))

    choices: list = []
    active_head = cfg.model.split("/", 1)[0]

    for p in builtin:
        tag = ""
        if p.api_key_env and not p.has_key():
            tag = "   [key needed]"
        if p.name == active_head:
            tag = "   ← currently active" + tag
        choices.append(questionary.Choice(
            title=f"{p.display:<14} {p.description}{tag}",
            value=p,
        ))

    if custom:
        choices.append(questionary.Separator("─── custom endpoints ───"))
        for p in custom:
            tag = "   ← currently active" if p.name == active_head else ""
            choices.append(questionary.Choice(title=f"{p.display}{tag}", value=p))

    choices.append(questionary.Separator(" "))
    choices.append(questionary.Choice(title="+ Add custom endpoint", value=_ADD_CUSTOM))
    if custom or _any_saved_keys(builtin):
        choices.append(questionary.Choice(title="- Remove saved provider/key", value=_REMOVE_SAVED))
    choices.append(questionary.Choice(title="  Cancel", value=_CANCEL))

    result = _ask(questionary.select(
        "Select provider:",
        choices=choices,
        qmark="",
        instruction="(↑↓ navigate  ENTER select  ESC cancel)",
    ))

    if result is None or result == _CANCEL:
        return None
    if result == _ADD_CUSTOM:
        new_ep = _add_custom_endpoint(cfg)
        if new_ep is None:
            return None
        cfg_mod.save(cfg)
        return new_ep
    if result == _REMOVE_SAVED:
        _remove_saved(cfg)
        cfg_mod.save(cfg)
        return None
    return result  # a Provider instance


def _pick_model(provider: Provider) -> str | None:
    _console.print(f"[dim]Fetching models from {provider.display}...[/dim]")
    models = provider.list_models()
    if not models:
        _console.print("[yellow]No models returned. You can enter a name manually.[/yellow]")

    choices = []
    for m in models:
        title = f"{m.display}"
        if m.note:
            title = f"{m.display:<50} {m.note}"
        choices.append(questionary.Choice(title=title, value=m.id))

    if choices:
        choices.append(questionary.Separator(" "))
    choices.append(questionary.Choice(title="+ Enter custom model name", value=_ENTER_CUSTOM_MODEL))
    choices.append(questionary.Choice(title="  Skip (keep current)", value=_SKIP))

    result = _ask(questionary.select(
        "Select model:",
        choices=choices,
        qmark="",
        instruction="(↑↓ navigate  ENTER select  ESC cancel)",
    ))

    if result is None or result == _SKIP:
        return None
    if result == _ENTER_CUSTOM_MODEL:
        raw = _ask(questionary.text("Model name:"))
        if not raw:
            return None
        raw = raw.strip()
        # Always prefix with the provider name unless it's already there.
        if not raw.startswith(f"{provider.name}/"):
            raw = f"{provider.name}/{raw}"
        return raw
    return result  # litellm-ready id


def _ensure_key(cfg: cfg_mod.Config, provider: Provider) -> None:
    """If the provider needs an API key and none is set, ask for it and persist."""
    if not provider.api_key_env:
        return
    if provider.has_key():
        return
    value = _ask(questionary.password(
        f"Enter {provider.api_key_env} for {provider.display}:"
    ))
    if not value:
        return
    _append_env(cfg.env_path, provider.api_key_env, value)
    os.environ[provider.api_key_env] = value


def _append_env(env_path: Path, key: str, value: str) -> None:
    lines: list[str] = []
    if env_path.exists():
        lines = env_path.read_text().splitlines()
    out: list[str] = []
    replaced = False
    for line in lines:
        if line.startswith(f"{key}="):
            out.append(f"{key}={value}")
            replaced = True
        else:
            out.append(line)
    if not replaced:
        out.append(f"{key}={value}")
    env_path.write_text("\n".join(out) + "\n")


def _add_custom_endpoint(cfg: cfg_mod.Config) -> CustomProvider | None:
    name = _ask(questionary.text("Endpoint name (short id, e.g. 'my-ollama'):"))
    if not name:
        return None
    base_url = _ask(questionary.text(
        "Base URL (e.g. http://localhost:11434/v1):"
    ))
    if not base_url:
        return None
    needs_key = _ask(questionary.confirm("Does this endpoint require an API key?", default=False))
    api_key_env = ""
    if needs_key:
        api_key_env = _ask(questionary.text(
            "Env var name for the key (e.g. MY_ENDPOINT_KEY):"
        )) or ""
        if api_key_env:
            value = _ask(questionary.password(f"Value for {api_key_env} (stored in ~/.alf/.env):"))
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


def _remove_saved(cfg: cfg_mod.Config) -> None:
    builtin = prov_mod.builtin()
    rows: list[questionary.Choice] = []
    for p in builtin:
        if p.api_key_env and os.environ.get(p.api_key_env):
            rows.append(questionary.Choice(
                title=f"Remove {p.api_key_env} (from .env)",
                value=("key", p.api_key_env),
            ))
    for entry in cfg.providers.get("custom", []) or []:
        name = entry.get("name", "")
        rows.append(questionary.Choice(
            title=f"Remove custom endpoint '{name}'",
            value=("custom", name),
        ))
    if not rows:
        _console.print("[dim]Nothing saved to remove.[/dim]")
        return
    rows.append(questionary.Separator(" "))
    rows.append(questionary.Choice(title="Cancel", value=("cancel", None)))

    choice = _ask(questionary.select("Remove what?", choices=rows, qmark=""))
    if not choice or not isinstance(choice, tuple) or choice[0] == "cancel":
        return
    kind, target = choice
    if kind == "key":
        _remove_env_key(cfg.env_path, target)
        os.environ.pop(target, None)
        _console.print(f"[green]✓[/green] removed {target} from .env")
    elif kind == "custom":
        cfg.providers["custom"] = [
            e for e in cfg.providers.get("custom", [])
            if e.get("name") != target
        ]
        _console.print(f"[green]✓[/green] removed custom endpoint '{target}'")


def _remove_env_key(env_path: Path, key: str) -> None:
    if not env_path.exists():
        return
    lines = [ln for ln in env_path.read_text().splitlines() if not ln.startswith(f"{key}=")]
    env_path.write_text("\n".join(lines) + ("\n" if lines else ""))


def _any_saved_keys(builtin: list[Provider]) -> bool:
    return any(p.has_key() for p in builtin if p.api_key_env)
