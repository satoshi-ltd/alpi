"""Interactive setup for MCP servers."""

from __future__ import annotations

import shlex
from pathlib import Path
from typing import Any

import questionary
import yaml

from alf import config as cfg_mod
from alf import ui
from alf.mcp.client import MCPClient, MCPError
from alf.model_selector import _append_env


def run(home: Path) -> None:
    """Top-level entry — list loop with add/remove/inspect."""
    while True:
        cfg = cfg_mod.load(home)
        servers = (cfg.raw.get("mcp") or {}).get("servers") or {}

        # Configured servers + add/remove actions live in a single
        # list — no visual separator. Back at the bottom is already
        # muted, which is enough to set it apart from the action
        # items above it.
        items: list = []
        for name in sorted(servers.keys()):
            items.append((
                ui.row(name, _summarize(servers[name])),
                ("use", name),
            ))
        items.append(("+ Add a server", ("add", None)))
        if servers:
            items.append(("- Remove a server", ("remove", None)))

        result = ui.menu(
            ui.crumb("setup", "mcp"),
            items,
            subtitle="user-configured Model Context Protocol servers",
            home=home, close="Back",
        )
        if result is None:
            return
        action, target = result
        if action == "use":
            _edit(home, target, servers[target])
        elif action == "add":
            _wizard(home, existing_name=None, existing_spec=None)
        elif action == "remove":
            _remove(home, servers)


# Add / edit flow (shared wizard)


def _edit(home: Path, name: str, spec: dict) -> None:
    _wizard(home, existing_name=name, existing_spec=spec)


def _wizard(
    home: Path,
    existing_name: str | None,
    existing_spec: dict | None,
) -> None:
    editing = existing_spec is not None

    if editing:
        ui.banner(
            ui.crumb("setup", "mcp", existing_name),
            subtitle="edit",
            home=home,
        )
        name = existing_name  # rename not supported; remove + re-add instead
        current_command = str(existing_spec.get("command") or "")
        current_args = _join_args(list(existing_spec.get("args") or []))
        current_env = dict(existing_spec.get("env") or {})
    else:
        ui.banner(
            ui.crumb("setup", "mcp", "add"),
            subtitle="add an MCP server",
            home=home,
        )
        name = ui.text("Short name (e.g. github, notion):")
        if not name:
            return ui.cancelled()
        if ":" in name or "/" in name or name.startswith("."):
            ui.fail(f"invalid name: {name!r}")
            return
        current_command = ""
        current_args = ""
        current_env = {}

    command = ui.text(
        "Command to run the server (e.g. npx, uvx, python):",
        default=current_command,
    )
    if not command:
        return ui.cancelled()

    args_raw = ui.text(
        "Arguments (space-separated; use quotes for multi-word):",
        default=current_args,
    )
    args = _split_args(args_raw or "")

    env_vars = _ask_env_vars(existing=current_env)

    client = MCPClient(name=name, command=command, args=args, env=env_vars)
    try:
        with ui.activity(f"Spawning and handshaking with {name}…"):
            client.start()
    except MCPError as e:
        ui.fail(str(e))
        ui.warn("Not saving anything. Check the command/args or env vars in .env.")
        ui.press_enter()
        return
    tools = client.list_tools()
    client.stop()

    _persist(home, name, command, args, env_vars)
    ui.ok(f"{name}: {len(tools)} tool{'s' if len(tools) != 1 else ''}")
    ui.press_enter()



def _remove(home: Path, servers: dict) -> None:
    items = [(n, n) for n in sorted(servers.keys())]
    name = ui.menu(
        ui.crumb("setup", "mcp", "remove"), items,
        subtitle="select the one to drop from config.yaml",
        home=home, close="Back",
    )
    if not name:
        return
    _unpersist(home, name)
    ui.ok(f"removed {name} from config.yaml")


# Env var collection (walk existing, then add loop)


def _ask_env_vars(existing: dict[str, str] | None = None) -> dict[str, str]:
    import os

    existing = existing or {}
    out: dict[str, str] = {}

    # 1) Walk existing mappings. Password prompt per var: ENTER keeps
    #    the current .env value, typing replaces it.
    for var, ref in existing.items():
        current = os.environ.get(var, "")
        value = ui.password(var, current=current)
        if value is None:
            # Ctrl-C mid-wizard. Preserve what we had so far.
            out[var] = ref
            continue
        if current and value == current:
            # Kept.
            out[var] = ref
        elif value:
            # Replaced — mark for .env write + re-use the ref shape.
            out[f"__inline__:{var}"] = value
            out[var] = f"env:{var}"
        else:
            # No current, empty input — keep the ref anyway so the
            # server still sees the var name (resolves to empty).
            out[var] = ref

    # 2) Add loop for new vars. Blank name finishes.
    while True:
        var = ui.text("Add another env var (blank to finish)")
        if not var:
            return out
        var = var.strip()
        if not var or var in out:
            continue

        current = os.environ.get(var, "")
        value = ui.password(var, current=current)
        if value:
            if value != current:
                out[f"__inline__:{var}"] = value
            out[var] = f"env:{var}"



def _persist(
    home: Path, name: str, command: str, args: list[str],
    env_vars: dict[str, str],
) -> None:
    import os
    env_path = home / ".env"
    inline = {
        k[len("__inline__:"):]: v
        for k, v in env_vars.items() if k.startswith("__inline__:")
    }
    for var, val in inline.items():
        _append_env(env_path, var, val)
        os.environ[var] = val

    cleaned_env = {
        k: v for k, v in env_vars.items() if not k.startswith("__inline__:")
    }

    cfg_path = home / "config.yaml"
    data: dict[str, Any] = {}
    if cfg_path.exists():
        data = yaml.safe_load(cfg_path.read_text()) or {}
    mcp = data.setdefault("mcp", {})
    servers = mcp.setdefault("servers", {})
    servers[name] = {
        "command": command,
        "args": args,
        "env": cleaned_env,
    }
    cfg_path.write_text(yaml.safe_dump(data, sort_keys=False))


def _unpersist(home: Path, name: str) -> None:
    cfg_path = home / "config.yaml"
    if not cfg_path.exists():
        return
    data = yaml.safe_load(cfg_path.read_text()) or {}
    servers = ((data.get("mcp") or {}).get("servers") or {})
    servers.pop(name, None)
    cfg_path.write_text(yaml.safe_dump(data, sort_keys=False))



def _summarize(spec: Any) -> str:
    if not isinstance(spec, dict):
        return "[invalid entry]"
    parts = [str(spec.get("command", "?"))]
    args = spec.get("args") or []
    if args:
        parts.append(" ".join(str(a) for a in args[:3]))
        if len(args) > 3:
            parts.append("…")
    return " ".join(parts)


def _split_args(raw: str) -> list[str]:
    try:
        return shlex.split(raw or "")
    except ValueError:
        return (raw or "").split()


def _join_args(args: list[str]) -> str:
    return " ".join(shlex.quote(a) for a in args)
