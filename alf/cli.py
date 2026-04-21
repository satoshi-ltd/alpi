"""alf — CLI entry point."""

from __future__ import annotations

import os
import sys
from importlib import resources
from pathlib import Path

import click

from alf import __version__, config, home, memory
from alf.engine import AgentEvent, Engine


def _bootstrap(h: Path) -> None:
    home.ensure_home(h)
    config.seed_defaults(h)
    memory.MemoryStore(h).seed_defaults()
    personality = home.personality_path(h)
    if not personality.exists():
        default = resources.files("alf.prompts").joinpath("default_personality.md").read_text()
        personality.write_text(default)


def _run_chat(h: Path, continue_last: bool = False) -> None:
    _bootstrap(h)
    from alf.tui import AlfApp
    try:
        AlfApp(home_dir=h, continue_last=continue_last).run()
    finally:
        _restore_terminal()
        # Force-exit: a worker thread may still be blocked on an LLM HTTP
        # call. Python's atexit would try to .join() it and hang, forcing
        # the user to Ctrl+C a second time. Session save already happened
        # inside action_quit (and after every turn), so nothing is lost.
        import os
        os._exit(0)


def _restore_terminal() -> None:
    try:
        seqs = (
            "\033[?1000l"   # disable X10 mouse reporting
            "\033[?1002l"   # disable button-event mouse tracking
            "\033[?1003l"   # disable any-event mouse tracking
            "\033[?1006l"   # disable SGR mouse extension
            "\033[?2004l"   # disable bracketed paste
            "\033[?25h"     # show cursor
            "\033[?1049l"   # leave alternate screen
        )
        sys.stdout.write(seqs)
        sys.stdout.flush()
    except Exception:
        pass


def _continue_last_session(engine: Engine, h: Path, console=None) -> bool:
    import json
    from alf.session import load_turns

    sessions_dir = h / "sessions"
    if not sessions_dir.exists():
        return False
    candidates = sorted(
        sessions_dir.glob("*.json"),
        key=lambda p: p.stat().st_mtime, reverse=True,
    )
    if not candidates:
        return False
    try:
        data = json.loads(candidates[0].read_text())
    except Exception as e:  # noqa: BLE001
        if console is not None:
            console.print(f"could not load last session: {e}")
        return False

    turns = load_turns(data)
    if not turns:
        return False

    engine.session.messages.append({
        "role": "system",
        "content": (
            "NOTE: the conversation below is a previous session that was "
            "resumed. You already have this context — do not call "
            "`session_search` to recover it. Refer to the messages directly."
        ),
    })
    for t in turns:
        if t.user:
            engine.session.messages.append({"role": "user", "content": t.user})
        if t.assistant:
            engine.session.messages.append(
                {"role": "assistant", "content": t.assistant}
            )
    engine.session.turns = list(turns)

    if data.get("id"):
        engine.session.id = data["id"]
    engine.session.input_tokens = int(data.get("input_tokens", 0))
    engine.session.output_tokens = int(data.get("output_tokens", 0))
    engine.session.cost_usd = float(data.get("cost_usd", 0.0))
    saved_ctx = int(data.get("last_ctx_tokens", 0))
    if saved_ctx:
        engine.session.last_ctx_tokens = saved_ctx
    else:
        total_chars = sum(
            len(m.get("content", "") or "") for m in engine.session.messages
        )
        engine.session.last_ctx_tokens = max(1, total_chars // 4)
    return True


def _run_once(h: Path, user_text: str, emit_events: bool = False) -> None:
    import json

    _bootstrap(h)
    cfg = config.load(h)
    engine = Engine(home=h, cfg=cfg)

    parts: list[str] = []

    from alf.tui.formatting import arg_hint

    def _emit_event_line(ev: AgentEvent) -> None:
        if ev.kind == "tool_start":
            payload = {
                "kind": "tool_start",
                "name": ev.name,
                "preview": arg_hint(ev.name, ev.args or {}),
            }
        elif ev.kind == "tool_end":
            payload = {"kind": "tool_end", "name": ev.name, "ok": ev.ok}
        elif ev.kind == "error":
            payload = {"kind": "error", "text": ev.text}
        elif ev.kind == "interrupted":
            payload = {"kind": "interrupted"}
        else:
            return
        sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
        sys.stdout.flush()

    def sink(ev: AgentEvent) -> None:
        if emit_events:
            _emit_event_line(ev)
        if ev.kind == "assistant_done" and ev.text.strip():
            parts.append(ev.text)
        elif ev.kind == "error" and not emit_events:
            parts.append(f"[error] {ev.text}")

    engine.run_turn(user_text, emit=sink)
    try:
        engine.save_session()
    except Exception:
        pass

    final = "\n\n".join(parts).strip()
    if emit_events:
        import json as _json
        sys.stdout.write(_json.dumps({"kind": "reply", "text": final}) + "\n")
    else:
        sys.stdout.write(final + "\n")
    sys.stdout.flush()




# Click subcommands

@click.group(
    invoke_without_command=True,
    context_settings={"max_content_width": 100, "help_option_names": ["-h", "--help"]},
)
@click.option("-p", "--profile", default=None, help="Profile to use (default: default).")
@click.option("-c", "--continue", "continue_last", is_flag=True,
              help="Resume from the last session.")
@click.version_option(__version__, prog_name="alf")
@click.pass_context
def main(ctx: click.Context, profile: str | None, continue_last: bool) -> None:
    """alf — a slim personal AI agent."""
    ctx.ensure_object(dict)
    h = home.get_home(profile)
    ctx.obj["home"] = h
    ctx.obj["profile"] = profile or "default"
    ctx.obj["continue_last"] = continue_last
    # Propagate the active profile to the environment so every downstream
    # ``get_home()`` call (tools, providers, UI helpers) resolves to the
    # SAME home as this CLI invocation. Without this, the tools bypass
    # ``-p`` entirely and silently write to the default profile — e.g.
    # the ``memory`` tool was editing ``~/.alf/PERSONALITY.md`` when the
    # user had launched ``alf -p personal``.
    if profile:
        os.environ["ALF_PROFILE"] = profile
    _bootstrap(h)
    if ctx.invoked_subcommand is None:
        _run_chat(h, continue_last=continue_last)


@main.command()
@click.option("--once", "input_text", default=None,
              help="Run one turn and print the reply to stdout.")
# Internal gateway-subprocess contract. Hidden from ``--help`` so the
# public surface stays minimal; users who need one-shot mode use
# ``--once`` alone. The gateway sets this flag when spawning so it
# can parse tool activity from the agent's stdout.
@click.option("--emit-events", is_flag=True, default=False, hidden=True)
@click.option("-c", "--continue", "continue_last", is_flag=True,
              help="Resume from the last session.")
@click.pass_context
def chat(ctx: click.Context, input_text: str | None, emit_events: bool,
         continue_last: bool) -> None:
    """Launch the TUI, or run one turn with ``--once "text"``."""
    h: Path = ctx.obj["home"]
    if input_text is not None:
        _run_once(h, input_text, emit_events=emit_events)
    else:
        _run_chat(h, continue_last=continue_last)



def _require_workspace(h: Path) -> None:
    cfg = config.load(h)
    wp = cfg.workspace_path
    if wp is None:
        raise click.UsageError(
            "No workspace configured for this profile. "
            "Run `alf setup` and pick a workspace, or set "
            f"`workspace:` in {cfg.config_path} before starting the daemon."
        )
    if not wp.exists():
        raise click.UsageError(
            f"Workspace {wp} does not exist. "
            "Create the directory or edit `workspace:` in "
            f"{cfg.config_path}."
        )


@main.group()
def gateway() -> None:
    """Gateway daemon (inbound channels: Telegram, Email, …)."""


@gateway.command("start")
@click.pass_context
def gateway_start(ctx: click.Context) -> None:
    """Start the gateway process (blocking)."""
    from alf.gateway.run import run as gw_run, pid_path
    h: Path = ctx.obj["home"]
    _bootstrap(h)
    _require_workspace(h)
    _check_not_running(pid_path(h))
    gw_run(h)


@gateway.command("stop")
@click.pass_context
def gateway_stop(ctx: click.Context) -> None:
    """Stop a running gateway process."""
    import signal
    from alf.gateway.run import pid_path
    h: Path = ctx.obj["home"]
    p = pid_path(h)
    if not p.exists():
        click.echo("gateway: not running")
        return
    try:
        pid = int(p.read_text().strip())
        os.kill(pid, signal.SIGTERM)
        click.echo(f"gateway: sent SIGTERM to pid {pid}")
    except (ValueError, ProcessLookupError) as e:
        click.echo(f"gateway: {e}")
        p.unlink(missing_ok=True)


@gateway.command("status")
@click.pass_context
def gateway_status(ctx: click.Context) -> None:
    """Show whether the gateway is running (and whether it's installed)."""
    from alf.gateway.run import pid_path
    h: Path = ctx.obj["home"]
    p = pid_path(h)
    _print_daemon_status("gateway", p, h, ctx.obj.get("profile") or "default")


@gateway.command("install")
@click.pass_context
def gateway_install(ctx: click.Context) -> None:
    """Install the gateway as a system service (launchd/systemd)."""
    h: Path = ctx.obj["home"]
    _bootstrap(h)
    _require_workspace(h)
    _install_daemon(ctx, "gateway")


@gateway.command("uninstall")
@click.pass_context
def gateway_uninstall(ctx: click.Context) -> None:
    """Stop + unregister the gateway system service."""
    _uninstall_daemon(ctx, "gateway")


@gateway.command("logs")
@click.option("-n", "--tail", default=50, help="Number of lines to show.")
@click.pass_context
def gateway_logs(ctx: click.Context, tail: int) -> None:
    """Show the tail of the gateway log."""
    h: Path = ctx.obj["home"]
    log_file = h / "gateway" / "logs" / "gateway.log"
    if not log_file.exists():
        click.echo("gateway: no log yet")
        return
    lines = log_file.read_text().splitlines()[-tail:]
    click.echo("\n".join(lines))


# MCP servers

@main.group()
def mcp() -> None:
    """Inspect configured MCP servers."""


@mcp.command("list")
@click.pass_context
def mcp_list(ctx: click.Context) -> None:
    """List configured MCP servers (from config.yaml)."""
    h: Path = ctx.obj["home"]
    cfg = config.load(h)
    servers = (cfg.raw.get("mcp") or {}).get("servers") or {}
    if not servers:
        click.echo("mcp: no servers configured. Run `alf setup` → MCPs.")
        return
    click.echo(f"mcp: {len(servers)} server(s)")
    for name, spec in sorted(servers.items()):
        cmd = spec.get("command", "?")
        args = " ".join(spec.get("args") or [])
        click.echo(f"  {name:<14} {cmd} {args}".rstrip())


@mcp.command("test")
@click.argument("name")
@click.pass_context
def mcp_test(ctx: click.Context, name: str) -> None:
    """Spawn one MCP server, list its tools, then stop it."""
    from alf.mcp.client import MCPClient, MCPError
    h: Path = ctx.obj["home"]
    cfg = config.load(h)
    spec = ((cfg.raw.get("mcp") or {}).get("servers") or {}).get(name)
    if not spec:
        raise click.ClickException(f"no server {name!r} in config.yaml")
    client = MCPClient(
        name=name,
        command=spec.get("command", ""),
        args=list(spec.get("args") or []),
        env=dict(spec.get("env") or {}),
    )
    try:
        client.start()
    except MCPError as e:
        raise click.ClickException(str(e))
    try:
        tools_ = client.list_tools()
        click.echo(f"{name}: ok ({len(tools_)} tool{'s' if len(tools_) != 1 else ''})")
        for t in tools_:
            click.echo(f"  {name}:{t.name}")
    finally:
        client.stop()


# Schedule daemon

@main.group()
def schedule() -> None:
    """Schedule daemon (runs cron + inactivity jobs)."""


@schedule.command("start")
@click.pass_context
def schedule_start(ctx: click.Context) -> None:
    """Start the schedule daemon (blocking)."""
    from alf.scheduler.run import run as sch_run, pid_path
    h: Path = ctx.obj["home"]
    _bootstrap(h)
    _require_workspace(h)
    _check_not_running(pid_path(h))
    sch_run(h)


@schedule.command("stop")
@click.pass_context
def schedule_stop(ctx: click.Context) -> None:
    """Stop a running schedule daemon."""
    from alf.scheduler.run import stop as sch_stop
    h: Path = ctx.obj["home"]
    if sch_stop(h):
        click.echo("schedule: SIGTERM sent")
    else:
        click.echo("schedule: not running")


@schedule.command("status")
@click.pass_context
def schedule_status(ctx: click.Context) -> None:
    """Show whether the daemon is running + list jobs."""
    import json
    from alf.scheduler.run import pid_path, jobs_path
    h: Path = ctx.obj["home"]
    _print_daemon_status("schedule", pid_path(h), h, ctx.obj.get("profile") or "default")
    jp = jobs_path(h)
    if jp.exists():
        jobs = json.loads(jp.read_text() or "[]")
        if jobs:
            click.echo(f"jobs ({len(jobs)}):")
            for j in jobs:
                descr = j.get("expression") or f"after {j.get('after_hours')}h"
                last = j.get("last_run_at") or "never"
                click.echo(
                    f"  {j.get('id', '?')}  [{j.get('kind', 'cron')}]  "
                    f"{descr}  last={last}"
                )
        else:
            click.echo("jobs: (none)")
    else:
        click.echo("jobs: (none)")


@schedule.command("install")
@click.pass_context
def schedule_install(ctx: click.Context) -> None:
    """Install the schedule daemon as a system service (launchd/systemd)."""
    h: Path = ctx.obj["home"]
    _bootstrap(h)
    _require_workspace(h)
    _install_daemon(ctx, "schedule")


@schedule.command("uninstall")
@click.pass_context
def schedule_uninstall(ctx: click.Context) -> None:
    """Stop + unregister the schedule system service."""
    _uninstall_daemon(ctx, "schedule")


@schedule.command("run-once")
@click.pass_context
def schedule_run_once(ctx: click.Context) -> None:
    """Run one tick in-process (manual fire, no daemon needed)."""
    from alf.scheduler.run import tick
    h: Path = ctx.obj["home"]
    _bootstrap(h)
    results = tick(h)
    if not results:
        click.echo("schedule: nothing due")
        return
    for jid, ok, msg in results:
        click.echo(f"  {jid}  {'OK' if ok else 'FAIL'}  {msg}")


@schedule.command("logs")
@click.option("-n", "--tail", default=50, help="Number of lines to show.")
@click.pass_context
def schedule_logs(ctx: click.Context, tail: int) -> None:
    """Show the tail of the schedule daemon log."""
    h: Path = ctx.obj["home"]
    log_file = h / "schedule" / "logs" / "scheduler.log"
    if not log_file.exists():
        click.echo("schedule: no log yet")
        return
    lines = log_file.read_text().splitlines()[-tail:]
    click.echo("\n".join(lines))


# Shared install / uninstall / status helpers

def _running_pid_for(name: str, home: Path) -> int | None:
    if name == "gateway":
        from alf.gateway.run import pid_path
        return _read_live_pid(pid_path(home))
    from alf.scheduler.run import running_pid
    return running_pid(home)


def _read_live_pid(pid_file: Path) -> int | None:
    if not pid_file.exists():
        return None
    try:
        pid = int(pid_file.read_text().strip())
        os.kill(pid, 0)
        return pid
    except (ValueError, ProcessLookupError):
        pid_file.unlink(missing_ok=True)
        return None
    except PermissionError:
        return pid


def _install_daemon(ctx: click.Context, name: str) -> None:
    from alf import service
    h: Path = ctx.obj["home"]
    profile: str = ctx.obj.get("profile") or "default"

    if _running_pid_for(name, h):
        raise click.ClickException(
            f"{name} is running manually — stop it first with "
            f"`alf {name} stop`, then re-run install."
        )
    if service.installed(name, profile):
        raise click.ClickException(
            f"{name} is already installed. "
            f"Run `alf {name} uninstall` first if you want to reinstall."
        )
    try:
        backend = service.install(name, h, profile)
    except service.ServiceError as e:
        raise click.ClickException(str(e))
    label = service.service_label(name, profile)
    click.echo(f"{name}: installed via {backend} ({label}) — auto-started")


def _uninstall_daemon(ctx: click.Context, name: str) -> None:
    from alf import service
    h: Path = ctx.obj["home"]
    profile: str = ctx.obj.get("profile") or "default"
    try:
        backend = service.uninstall(name, h, profile)
    except service.ServiceError as e:
        raise click.ClickException(str(e))
    click.echo(f"{name}: uninstalled ({backend})")


def _print_daemon_status(name: str, pid_file: Path, home: Path, profile: str) -> None:
    from alf import service
    pid = _read_live_pid(pid_file)
    state = f"running (pid {pid})" if pid else "stopped"
    backend = service.installed(name, profile)
    installed_line = (
        f"installed via {backend} ({service.service_label(name, profile)})"
        if backend else "not installed"
    )
    click.echo(f"{name}: {state} — {installed_line}")


def _check_not_running(pid_file: Path) -> None:
    if not pid_file.exists():
        return
    try:
        pid = int(pid_file.read_text().strip())
        os.kill(pid, 0)
    except (ValueError, ProcessLookupError):
        pid_file.unlink(missing_ok=True)
        return
    # Generic message — this helper is shared by gateway and schedule.
    raise click.ClickException(f"process already running (pid {pid}).")


# setup / profile

@main.command("setup")
@click.pass_context
def setup_cmd(ctx: click.Context) -> None:
    """Interactive setup — model, gateways, MCPs."""
    from alf import ui
    h: Path = ctx.obj["home"]
    _bootstrap(h)

    profile_name = ctx.obj.get("profile") or "default"
    while True:
        cfg = config.load(h)
        items = [
            (ui.row("Model / Provider", cfg.model or "(not set)"), "model"),
            (ui.row("Gateways", _gateways_status(h)), "gateways"),
            (ui.row("MCPs", _mcp_status(h)), "mcps"),
            (ui.row("Sandbox", _sandbox_status(cfg)), "sandbox"),
        ]
        # Every title starts with ``alf`` as a lightweight brand +
        # "you are here" marker. The active profile goes in the
        # subtitle so the user always knows which one they're
        # configuring without it bloating the title itself.
        choice = ui.menu(
            ui.crumb("setup"),
            items,
            subtitle=f"profile: {profile_name}",
            home=h, close="Exit",
        )
        if choice is None:
            _setup_farewell(profile_name, h)
            return
        if choice == "model":
            from alf import model_selector
            model_selector.run(config.load(h))
        elif choice == "gateways":
            _gateways_setup(h)
        elif choice == "mcps":
            from alf.mcp.setup import run as mcp_setup_run
            mcp_setup_run(h)
        elif choice == "sandbox":
            _sandbox_setup(h)


def _setup_farewell(profile: str, h: Path) -> None:
    from alf import ui as ui_mod

    prefix = f"alf -p {profile}" if profile != "default" else "alf"
    ui_mod._console.print(f"\n[dim]next:[/dim] {prefix}\n")


def _gateways_setup(h: Path) -> None:
    from alf import ui
    while True:
        items = [
            (ui.row("Telegram", _telegram_status(h)), "telegram"),
            (ui.row("Email", _email_status(h)), "email"),
        ]
        choice = ui.menu(
            ui.crumb("setup", "gateways"),
            items,
            subtitle="inbound channels alf listens on",
            home=h, close="Back",
        )
        if choice is None:
            return
        if choice == "telegram":
            from alf.gateway.setup import run as telegram_setup
            telegram_setup(h)
        elif choice == "email":
            from alf.email.setup import run as email_setup
            email_setup(h)


def _read_profile_env(h: Path) -> dict[str, str]:
    env_path = h / ".env"
    if not env_path.exists():
        return {}
    out: dict[str, str] = {}
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        out[key.strip()] = value.strip()
    return out


def _gateways_status(h: Path) -> str:
    env = _read_profile_env(h)
    names = []
    if env.get("TELEGRAM_BOT_TOKEN"):
        names.append("Telegram")
    if env.get("EMAIL_ADDRESS"):
        names.append("Email")
    return ", ".join(names) if names else "none"


def _telegram_status(h: Path) -> str:
    env = _read_profile_env(h)
    if not env.get("TELEGRAM_BOT_TOKEN"):
        return "not set up"
    chats = env.get("TELEGRAM_ALLOWED_CHAT_IDS", "")
    n = len([c for c in chats.split(",") if c.strip()])
    if n == 0:
        return "ready · no one allowlisted yet"
    return f"ready · {n} allowlisted chat{'s' if n != 1 else ''}"


def _mcp_status(h: Path) -> str:
    try:
        cfg = config.load(h)
    except Exception:  # noqa: BLE001
        return "?"
    servers = (cfg.raw.get("mcp") or {}).get("servers") or {}
    if not servers:
        return "none"
    return ", ".join(sorted(servers.keys()))


def _sandbox_status(cfg: config.Config) -> str:
    term = cfg.tools.terminal
    if not term.sandbox:
        return "off"
    net = "network on" if term.allow_network else "network off"
    return f"on · {net}"


def _sandbox_setup(h: Path) -> None:
    """Pick the desired sandbox posture for the current profile."""
    from alf import ui
    cfg = config.load(h)
    term = cfg.tools.terminal

    ui.banner(
        ui.crumb("setup", "sandbox"),
        subtitle=_sandbox_status(cfg),
        home=h,
    )
    ui.dim(
        "Wraps shell commands in sandbox-exec (macOS) or bubblewrap (Linux) so\n"
        "the kernel blocks writes outside your workspace + ~/.alf, and denies\n"
        "network unless you opt in.\n\n"
        "Recommended for profiles that run unattended — Telegram gateway,\n"
        "schedule daemon, research / delegate sub-agents. For interactive chat\n"
        "where you approve every command, the denylist (Layer 1) is already\n"
        "sufficient.\n\n"
        "Trade-offs when enabled: git push over SSH (~/.ssh denied), Homebrew\n"
        "on Apple Silicon, and docker commands may break. Keep it off in your\n"
        "main dev profile."
    )
    ui._console.print("")

    choice = ui.menu(
        "",
        [
            ("Enable sandbox", "enable"),
            ("Disable sandbox", "disable"),
        ],
        home=h, close="Back",
    )
    if choice is None:
        return
    if choice == "disable":
        cfg.tools.terminal.sandbox = False
        cfg.tools.terminal.allow_network = False
        config.save(cfg)
        return
    # choice == "enable" — ask about network next.
    cfg.tools.terminal.sandbox = True
    config.save(cfg)

    ui.banner(
        ui.crumb("setup", "sandbox", "network"),
        subtitle="allow network inside the sandbox?",
        home=h,
    )
    ui.dim(
        "Denied → sub-processes can't open sockets. Safest default; blocks any\n"
        "exfil attempt by a compromised command.\n\n"
        "Allowed → sub-processes can reach the internet. Needed for git push,\n"
        "npm / pip install, curl, docker pull, etc. Most unattended profiles\n"
        "still need this because they fetch external data."
    )
    ui._console.print("")

    net = ui.menu(
        "",
        [
            ("Deny network (isolated)", "deny"),
            ("Allow network (git push, npm, curl…)", "allow"),
        ],
        home=h, close="Back",
    )
    if net is None:
        # User ESC'd — leave sandbox enabled with the previous network value.
        return
    cfg.tools.terminal.allow_network = (net == "allow")
    config.save(cfg)


def _email_status(h: Path) -> str:
    env = _read_profile_env(h)
    addr = env.get("EMAIL_ADDRESS", "")
    if not addr:
        return "not set up"
    senders = env.get("EMAIL_ALLOWED_SENDERS", "")
    n = len([s for s in senders.split(",") if s.strip()])
    if n == 0:
        return f"ready · {addr} · outbound only"
    return f"ready · {addr} · {n} allowlisted sender{'s' if n != 1 else ''}"


@main.group()
def profile() -> None:
    """Manage profiles (list, create, remove)."""


@profile.command("list")
@click.pass_context
def profile_list(ctx: click.Context) -> None:
    """List available profiles. Marks which one this invocation resolved to."""
    active = ctx.obj.get("profile") or "default"

    named: list[str] = []
    root = Path.home() / ".alf" / "profiles"
    if root.exists():
        named = sorted(p.name for p in root.iterdir() if p.is_dir())

    profiles = ["default", *named]
    for name in profiles:
        marker = "* " if name == active else "  "
        home_path = (
            Path.home() / ".alf" if name == "default"
            else Path.home() / ".alf" / "profiles" / name
        )
        click.echo(f"{marker}{name:<12}  {home_path}")

    if not named:
        # Fresh install: nudge the user toward creating one if they want
        # to. Profiles are opt-in — most people never need more than one.
        click.echo("")
        click.echo("Only the default profile exists. Profiles are optional —")
        click.echo("useful if you want separate memories, bots, or schedules")
        click.echo("for different contexts (work vs. personal, e.g.).")
        click.echo("")
        click.echo("Create one with:")
        click.echo("  alf profile create work")
        click.echo("  alf profile create personal")
        click.echo("")
        click.echo("Then use it per-invocation:")
        click.echo("  alf -p work                  # open TUI in the work profile")
        click.echo("  alias alfw='alf -p work'     # shell alias if you live there")


@profile.command("create")
@click.argument("name")
def profile_create(name: str) -> None:
    """Bootstrap a new profile directory with default config."""
    if name in {"default", ""}:
        raise click.ClickException("use a real name — 'default' is reserved")
    if "/" in name or name.startswith("."):
        raise click.ClickException(f"invalid profile name: {name!r}")

    h = home.get_home(name)
    if h.exists() and any(h.iterdir()):
        raise click.ClickException(f"profile {name!r} already exists at {h}")

    _bootstrap(h)
    click.echo(f"created profile {name!r} at {h}")
    click.echo(f"use it with: alf -p {name}")
    click.echo("")
    click.echo("Configure it:")
    click.echo(f"  alf -p {name} setup                          "
               f"# interactive (API keys + gateway)")
    default_env = Path.home() / ".alf" / ".env"
    if default_env.exists():
        click.echo(f"  # — or, to reuse the default profile's setup:")
        click.echo(f"  cp {default_env} {h / '.env'}")


@profile.command("remove")
@click.argument("name")
def profile_remove(name: str) -> None:
    """Permanently remove a profile directory after safety checks."""
    import shutil

    from alf import service, ui

    if name in {"default", ""}:
        raise click.ClickException("the default profile cannot be removed")
    if "/" in name or name.startswith("."):
        raise click.ClickException(f"invalid profile name: {name!r}")

    h = home.get_home(name)
    if not h.exists():
        raise click.ClickException(f"profile {name!r} does not exist")

    # Safety: refuse if the profile has a registered system service.
    # Uninstalling them is an explicit step the user has to take so
    # they understand what's being torn down.
    installed = []
    for daemon in ("gateway", "schedule"):
        if service.installed(daemon, profile=name):
            installed.append(daemon)
    if installed:
        svc_list = ", ".join(installed)
        raise click.ClickException(
            f"profile {name!r} has installed service(s): {svc_list}.\n"
            f"Run `alf -p {name} {installed[0]} uninstall` first."
        )

    # Summary — user wants to see what they're losing before saying yes.
    summary = _profile_summary(h)
    ui.banner(f"Remove profile · {name}", subtitle=str(h))
    for line in summary:
        click.echo(f"  {line}")
    click.echo("")
    if not ui.confirm(f"Remove profile {name!r}? This cannot be undone.",
                      default=False):
        ui.cancelled()
        return

    shutil.rmtree(h)
    ui.ok(f"removed profile {name!r} at {h}")


def _profile_summary(home_dir: Path) -> list[str]:
    lines: list[str] = []
    sessions = home_dir / "sessions"
    if sessions.exists():
        files = list(sessions.glob("*.json"))
        lines.append(f"sessions: {len(files)} file(s)")
    memories = home_dir / "memories"
    if memories.exists():
        files = list(memories.glob("*.md"))
        lines.append(f"memories: {len(files)} file(s)")
    skills = home_dir / "skills"
    if skills.exists():
        dirs = [p for p in skills.rglob("*") if p.is_dir() and p.parent == skills]
        count = sum(1 for p in skills.rglob("SKILL.md"))
        if count:
            lines.append(f"skills:   {count} user-created")
    env = home_dir / ".env"
    if env.exists():
        lines.append(f".env:     present (credentials will be deleted)")
    if not lines:
        lines.append("empty profile — nothing to lose.")
    return lines


if __name__ == "__main__":
    main(obj={})
    sys.exit(0)
