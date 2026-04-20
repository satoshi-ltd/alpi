"""Interactive setup for MCP servers.

Pattern mirrors the Telegram/Email wizards: ``alf setup`` menu →
"MCPs" → list + add/remove. Writes to ``config.yaml`` under
``mcp.servers.<name>``. Secrets go in ``.env`` — we never write a
raw secret into config.yaml; env vars are referenced with the
``env:VAR_NAME`` placeholder resolved at spawn time.

The wizard tries to spawn the new server and list its tools before
committing the config change. If the handshake fails we don't
write anything — same contract as the email wizard (connection
test guards the save).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import questionary
import yaml
from rich.console import Console

from alf import config as cfg_mod
from alf.mcp.client import MCPClient, MCPError
from alf.model_selector import _append_env, _ask, accent_style

_console = Console()


def run(home: Path) -> None:
    """Top-level entry — list loop with add/remove/test/exit."""
    while True:
        cfg = cfg_mod.load(home)
        servers = (cfg.raw.get("mcp") or {}).get("servers") or {}
        style = accent_style((cfg.tui or {}).get("accent", ""))

        choices = []
        for name in sorted(servers.keys()):
            choices.append(questionary.Choice(
                title=f"{name:<14} {_summarize(servers[name])}",
                value=("use", name),
            ))
        if servers:
            choices.append(questionary.Separator(" "))
        choices.append(questionary.Choice(title="+ Add a server", value=("add", None)))
        if servers:
            choices.append(questionary.Choice(title="- Remove a server", value=("remove", None)))
        choices.append(questionary.Choice(title="  ← Back", value=("back", None)))

        result = _ask(questionary.select(
            "MCP servers:",
            choices=choices,
            qmark="",
            pointer="◆",
            style=style,
            instruction="(↑↓ navigate  ENTER select  ESC cancel)",
        ))
        if result is None:
            return
        action, target = result
        if action == "back":
            return
        if action == "use":
            _edit(home, target, servers[target])
        elif action == "add":
            _wizard(home, existing_name=None, existing_spec=None)
        elif action == "remove":
            _remove(home, servers)


# ----------------------------------------------------------------------
# Actions
# ----------------------------------------------------------------------


def _edit(home: Path, name: str, spec: dict) -> None:
    """Re-enter the wizard for an existing server with fields prefilled."""
    _wizard(home, existing_name=name, existing_spec=spec)


def _wizard(
    home: Path,
    existing_name: str | None,
    existing_spec: dict | None,
) -> None:
    """Unified add/edit wizard. Hydrates from ``existing_spec`` when
    editing an existing server; otherwise asks for a fresh name.

    Contract: we ALWAYS spawn + handshake before persisting. If the
    server can't start with the new values, nothing in config.yaml
    changes — the previous spec is left untouched on edit.
    """
    editing = existing_spec is not None

    if editing:
        _console.print(
            f"\n[b]Edit MCP server[/b]  [dim]{existing_name}[/dim]\n"
            "[dim]Existing values show as defaults — press ENTER to "
            "keep them. Env var mappings below let you keep or "
            "replace each one individually.[/dim]\n"
        )
        name = existing_name  # rename not supported; remove+re-add instead
        current_command = str(existing_spec.get("command") or "")
        current_args = _join_args(list(existing_spec.get("args") or []))
        current_env = dict(existing_spec.get("env") or {})
    else:
        _console.print(
            "\n[dim]Add an MCP server. Alf will spawn it and list its "
            "tools before saving — if the handshake fails nothing is "
            "written to config.yaml.\n"
            "Secrets should go in ~/.alf/.env; reference them here as "
            "'env:VAR_NAME'.[/dim]\n"
        )
        name = _ask(questionary.text("Short name (e.g. github, notion):"))
        if not name:
            return _cancelled()
        if ":" in name or "/" in name or name.startswith("."):
            _console.print(f"[red]invalid name: {name!r}[/red]")
            return
        current_command = ""
        current_args = ""
        current_env = {}

    command = _ask(questionary.text(
        "Command to run the server (e.g. npx, uvx, python):",
        default=current_command,
    ))
    if not command:
        return _cancelled()

    args_raw = _ask(questionary.text(
        "Arguments (space-separated; use quotes for multi-word):",
        default=current_args,
    ))
    args = _split_args(args_raw)

    env_vars = _ask_env_vars(existing=current_env)

    _console.print("\n[dim]Spawning and handshaking with the server…[/dim]")
    client = MCPClient(name=name, command=command, args=args, env=env_vars)
    try:
        client.start()
    except MCPError as e:
        _console.print(f"[red]✗[/red] {e}")
        _console.print(
            "[yellow]Not saving anything. Check the command/args or "
            "the env vars in .env.[/yellow]"
        )
        return
    tools = client.list_tools()
    client.stop()

    _console.print(
        f"[green]✓[/green] {name}: ready ({len(tools)} tool{'s' if len(tools) != 1 else ''})"
    )
    for t in tools[:10]:
        _console.print(f"  [dim]·[/dim] {name}:{t.name}")
    if len(tools) > 10:
        _console.print(f"  [dim]… and {len(tools) - 10} more[/dim]")

    _persist(home, name, command, args, env_vars)
    _console.print(
        f"[dim]{'Updated' if editing else 'Saved'} config.yaml. "
        f"Restart alf to load the tools.[/dim]"
    )


def _remove(home: Path, servers: dict) -> None:
    choices = [questionary.Choice(title=n, value=n) for n in sorted(servers)]
    choices.append(questionary.Choice(title="  ← Cancel", value=None))
    name = _ask(questionary.select(
        "Remove which server?", choices=choices, qmark="", pointer="◆",
    ))
    if not name:
        return
    _unpersist(home, name)
    _console.print(f"[green]✓[/green] removed {name} from config.yaml")


def _join_args(args: list[str]) -> str:
    """Re-quote args with spaces so the prefill survives a round-trip
    through shlex when the user just presses Enter."""
    import shlex
    return " ".join(shlex.quote(a) for a in args)


# ----------------------------------------------------------------------
# Env var collection — multi-value
# ----------------------------------------------------------------------


def _ask_env_vars(existing: dict[str, str] | None = None) -> dict[str, str]:
    """Collect env var references for the server.

    On edit, iterate over ``existing`` first: for each mapping, offer
    keep / replace / drop. Then enter the add loop to introduce new
    vars. On add (no ``existing``), skip straight to the add loop.
    """
    existing = existing or {}
    out: dict[str, str] = {}

    # Step 1 — walk existing mappings (edit mode only).
    for var, ref in existing.items():
        action = _ask(questionary.select(
            f"Env var {var} (current: {ref}):",
            choices=[
                questionary.Choice(title="keep", value="keep"),
                questionary.Choice(title="replace value", value="replace"),
                questionary.Choice(title="drop", value="drop"),
            ],
            qmark="",
            pointer="◆",
            instruction="(↑↓ navigate  ENTER select)",
        ))
        if action in (None, "keep"):
            out[var] = ref
        elif action == "drop":
            continue
        elif action == "replace":
            value = _ask(questionary.password(
                f"New value for {var} (will update .env):",
            ))
            if value:
                out[f"__inline__:{var}"] = value
                out[var] = f"env:{var}"
            else:
                # User aborted mid-replace → keep the old one rather
                # than dropping it silently.
                out[var] = ref

    # Step 2 — add loop for new vars (runs in both add and edit modes).
    while True:
        var = _ask(questionary.text(
            "Add another environment variable "
            "(name, blank to finish):",
        ))
        if not var:
            return out
        var = var.strip()
        if not var or var in out:
            continue

        existing_value = _ref_lookup(var)
        if existing_value:
            _console.print(f"  [dim]Found {var} in .env (ends …{existing_value[-4:]}).[/dim]")
            if questionary.confirm(
                f"Use the existing {var} from .env?",
                default=True, qmark="",
            ).ask():
                out[var] = f"env:{var}"
                continue

        value = _ask(questionary.password(
            f"Value for {var} (will be appended to .env):",
        ))
        if value is not None and value:
            out[f"__inline__:{var}"] = value
            out[var] = f"env:{var}"


def _ref_lookup(var: str) -> str:
    import os
    return os.environ.get(var, "")


# ----------------------------------------------------------------------
# Persistence
# ----------------------------------------------------------------------


def _persist(
    home: Path, name: str, command: str, args: list[str],
    env_vars: dict[str, str],
) -> None:
    # Write inline-provided secrets to .env first.
    env_path = home / ".env"
    inline = {
        k[len("__inline__:"):]: v
        for k, v in env_vars.items() if k.startswith("__inline__:")
    }
    for var, val in inline.items():
        _append_env(env_path, var, val)
        import os
        os.environ[var] = val

    # Strip inline markers from the spec written to config.yaml.
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
    if name in servers:
        del servers[name]
    cfg_path.write_text(yaml.safe_dump(data, sort_keys=False))


# ----------------------------------------------------------------------
# Misc
# ----------------------------------------------------------------------


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
    """Shell-style tokenization without running anything."""
    import shlex
    try:
        return shlex.split(raw or "")
    except ValueError:
        # Unterminated quote or similar — fall back to a naive split.
        return (raw or "").split()


def _cancelled() -> None:
    _console.print("[yellow]cancelled[/yellow]")
