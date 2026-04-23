"""alpi — CLI entry point."""

from __future__ import annotations

import os
import sys
from importlib import resources
from pathlib import Path

import click

from alpi import __version__, config, home, memory
from alpi.engine import AgentEvent, Engine


def _bootstrap(h: Path) -> None:
    home.ensure_home(h)
    config.seed_defaults(h)
    memory.MemoryStore(h).seed_defaults()
    personality = home.personality_path(h)
    if not personality.exists():
        default = resources.files("alpi.prompts").joinpath("default_personality.md").read_text()
        personality.write_text(default)


def _auto_install_scheduler(h: Path, profile: str) -> None:
    """Register the schedule daemon on first run of this profile, silently.

    Once we've attempted it (successfully or not), drop a marker so
    later invocations don't re-install after the user explicitly
    uninstalled it from ``alpi setup → Schedule service``. The marker
    is per-profile so each profile gets one first-run attempt.
    """
    if os.environ.get("ALPI_SKIP_AUTO_INSTALL"):
        return
    marker = h / "schedule" / ".bootstrapped"
    if marker.exists():
        return
    try:
        from alpi import service
        if not service.installed("schedule", profile):
            service.install("schedule", h, profile)
    except Exception:  # noqa: BLE001
        pass
    finally:
        try:
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.touch()
        except OSError:
            pass


def _run_chat(h: Path, continue_last: bool = False) -> None:
    _bootstrap(h)
    from alpi.tui import AlpiApp
    try:
        AlpiApp(home_dir=h, continue_last=continue_last).run()
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
    from alpi.session import load_turns

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

    from alpi.tui.formatting import arg_hint

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

class _OrderedGroup(click.Group):
    """Display subcommands by user-frequency, not alphabetically.

    Click's default listing is alphabetical, which buries `setup` under
    `gateway` / `schedule` even though the daemon groups are for rare
    manual control. This keeps the first line of ``alpi --help`` the one
    a new user actually wants.
    """

    _ORDER = ["chat", "setup", "doctor", "logs", "profile", "gateway", "schedule", "release"]

    def list_commands(self, ctx: click.Context) -> list[str]:
        known = [c for c in self._ORDER if c in self.commands]
        extra = sorted(c for c in self.commands if c not in self._ORDER)
        return known + extra


@click.group(
    cls=_OrderedGroup,
    invoke_without_command=True,
    context_settings={"max_content_width": 100, "help_option_names": ["-h", "--help"]},
)
@click.option("-p", "--profile", default=None, help="Profile to use (default: default).")
@click.option("-c", "--continue", "continue_last", is_flag=True,
              help="Resume from the last session.")
@click.version_option(__version__, prog_name="alpi")
@click.pass_context
def main(ctx: click.Context, profile: str | None, continue_last: bool) -> None:
    """alpi — a slim personal AI agent."""
    ctx.ensure_object(dict)
    h = home.get_home(profile)
    ctx.obj["home"] = h
    ctx.obj["profile"] = profile or "default"
    ctx.obj["continue_last"] = continue_last
    # Propagate the active profile to the environment so every downstream
    # ``get_home()`` call (tools, providers, UI helpers) resolves to the
    # SAME home as this CLI invocation. Without this, the tools bypass
    # ``-p`` entirely and silently write to the default profile — e.g.
    # the ``memory`` tool was editing ``~/.alpi/PERSONALITY.md`` when the
    # user had launched ``alpi -p personal``.
    if profile:
        os.environ["ALPI_PROFILE"] = profile
    _bootstrap(h)
    # Skip auto-install when the invocation is itself the daemon (launchd
    # spawns ``alpi schedule start``) to avoid touching launchctl from
    # inside a service-spawned process.
    if ctx.invoked_subcommand not in {"schedule", "gateway"}:
        _auto_install_scheduler(h, profile or "default")
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
            "Run `alpi setup` and pick a workspace, or set "
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
    """Gateway daemon controls (configure channels via ``alpi setup``)."""


@gateway.command("start")
@click.pass_context
def gateway_start(ctx: click.Context) -> None:
    """Start the gateway process in the foreground (blocking)."""
    from alpi.gateway.run import run as gw_run, pid_path
    h: Path = ctx.obj["home"]
    _bootstrap(h)
    _require_workspace(h)
    _check_not_running(pid_path(h))
    gw_run(h)


@gateway.command("stop")
@click.pass_context
def gateway_stop(ctx: click.Context) -> None:
    """Stop a running gateway (SIGTERM)."""
    import signal
    from alpi.gateway.run import pid_path
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


# MCP servers

# Schedule daemon — auto-installs on first `alpi` run; these are for manual/debug use

@main.group()
def schedule() -> None:
    """Schedule daemon controls (auto-installs as a service on first run)."""


@schedule.command("start")
@click.pass_context
def schedule_start(ctx: click.Context) -> None:
    """Start the schedule daemon in the foreground (blocking)."""
    from alpi.scheduler.run import run as sch_run, pid_path
    h: Path = ctx.obj["home"]
    _bootstrap(h)
    _require_workspace(h)
    _check_not_running(pid_path(h))
    sch_run(h)


@schedule.command("stop")
@click.pass_context
def schedule_stop(ctx: click.Context) -> None:
    """Stop a running schedule daemon (SIGTERM)."""
    from alpi.scheduler.run import stop as sch_stop
    h: Path = ctx.obj["home"]
    if sch_stop(h):
        click.echo("schedule: SIGTERM sent")
    else:
        click.echo("schedule: not running")


@schedule.command("run-once")
@click.pass_context
def schedule_run_once(ctx: click.Context) -> None:
    """Run one tick in-process (manual fire, no daemon needed)."""
    from alpi.scheduler.run import tick
    h: Path = ctx.obj["home"]
    _bootstrap(h)
    results = tick(h)
    if not results:
        click.echo("schedule: nothing due")
        return
    for jid, ok, msg in results:
        click.echo(f"  {jid}  {'OK' if ok else 'FAIL'}  {msg}")


# Release — auto-generate CHANGELOG sections from git history

@main.group()
def release() -> None:
    """Release-cycle helpers (changelog, tagging)."""


@release.command("notes")
@click.option("--since", default=None,
              help="Git rev to start from (default: entire history).")
@click.option("-o", "--output", "output",
              type=click.Path(dir_okay=False, writable=True),
              default=None,
              help="Write to this file instead of stdout (overwrites).")
def release_notes(since: str | None, output: str | None) -> None:
    """Render a Markdown changelog from commits, grouped by version bump."""
    from alpi import changelog
    releases = changelog.collect(since=since)
    rendered = changelog.render_markdown(releases)
    if output:
        Path(output).write_text(rendered)
        click.echo(f"wrote {output} ({len(releases)} release{'s' if len(releases) != 1 else ''})")
    else:
        click.echo(rendered, nl=False)


# Doctor — health check across model, workspace, gateways, services, MCPs, security

@main.command("doctor")
@click.pass_context
def doctor_cmd(ctx: click.Context) -> None:
    """Read-only health check of the current profile."""
    from alpi import doctor, ui
    h: Path = ctx.obj["home"]
    profile: str = ctx.obj.get("profile") or "default"
    checks = doctor.run_and_render(ui._console, h, profile, __version__)
    ctx.exit(doctor.exit_code(checks))


# Logs — unified tail across every subsystem under ``{home}/*/logs/``

@main.command("logs")
@click.option("--source", type=click.Choice(["gateway", "schedule", "agent", "approval"]),
              default=None, help="Restrict to one subsystem.")
@click.option("-n", "--tail", "tail_n", default=100,
              help="Number of most recent lines to show (default: 100).")
@click.option("-f", "--follow", is_flag=True, default=False,
              help="Follow the logs as new lines arrive.")
@click.pass_context
def logs_cmd(ctx: click.Context, source: str | None, tail_n: int, follow: bool) -> None:
    """Show the tail of every log this profile writes, merged by timestamp."""
    from alpi import logs as logs_mod, ui
    h: Path = ctx.obj["home"]
    lines = logs_mod.tail(h, source, tail_n)
    if not lines and not follow:
        ui._console.print("[dim]no logs yet — run `alpi setup` to get started.[/dim]")
        return
    logs_mod.print_tail(ui._console, lines)
    if follow:
        logs_mod.follow(h, source, ui._console)


# Shared install / uninstall / status helpers

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
    from alpi import ui
    h: Path = ctx.obj["home"]
    _bootstrap(h)

    profile_name = ctx.obj.get("profile") or "default"
    while True:
        cfg = config.load(h)
        items = [
            ("Model / Provider", "model", cfg.model or "(not set)"),
            ("Gateways", "gateways", _gateways_status(h)),
            ("Voice", "voice", _voice_status(cfg)),
            ("MCPs", "mcps", _mcp_status(h)),
            None,
            ("Sandbox", "sandbox", _sandbox_status(cfg)),
            ("Gateway service", "gateway-service", _gateway_service_status(h)),
            ("Schedule service", "schedule-service", _schedule_service_status(h)),
            ("Health check", "doctor", _doctor_status(h, profile_name)),
            ("Cleanup", "cleanup", _cleanup_status(h)),
        ]
        # Every title starts with ``alpi`` as a lightweight brand +
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
            from alpi import model_selector
            model_selector.run(config.load(h))
        elif choice == "gateways":
            _gateways_setup(h)
        elif choice == "mcps":
            from alpi.mcp.setup import run as mcp_setup_run
            mcp_setup_run(h)
        elif choice == "sandbox":
            _sandbox_setup(h)
        elif choice == "voice":
            _voice_setup(h)
        elif choice == "cleanup":
            _cleanup_setup(h)
        elif choice == "gateway-service":
            _gateway_service_setup(h)
        elif choice == "schedule-service":
            _schedule_service_setup(h)
        elif choice == "doctor":
            _doctor_wizard(h, profile_name)


def _setup_farewell(profile: str, h: Path) -> None:
    from alpi import ui as ui_mod

    prefix = f"alpi -p {profile}" if profile != "default" else "alpi"
    ui_mod._console.print(f"\n[dim]next:[/dim] {prefix}\n")


def _gateways_setup(h: Path) -> None:
    from alpi import ui
    while True:
        items = [
            ("Telegram", "telegram", _telegram_status(h)),
            ("IMAP", "imap", _email_status(h)),
            ("Gmail", "gmail", _gmail_status(h)),
        ]
        choice = ui.menu(
            ui.crumb("setup", "gateways"),
            items,
            subtitle="inbound channels alpi listens on",
            home=h, close="Back",
        )
        if choice is None:
            return
        if choice == "telegram":
            from alpi.gateway.setup import run as telegram_setup
            telegram_setup(h)
        elif choice == "imap":
            from alpi.mail.setup import run as email_setup
            email_setup(h)
        elif choice == "gmail":
            from alpi.mail.gmail_setup import run as gmail_setup
            gmail_setup(h)


def _gateway_service_status(h: Path) -> str:
    from alpi import service
    if not _any_gateway_ready(h):
        return "no gateway configured"
    backend = service.installed("gateway", _profile_from_home(h))
    return f"running via {backend}" if backend else "not installed"


_DAEMON_WIZARD_COPY = {
    "gateway": (
        "Registers the gateway daemon (`alpi gateway start`) with your\n"
        "OS so it runs on boot and restarts on crash. macOS: launchd\n"
        "plist under ~/Library/LaunchAgents/. Linux: systemd --user unit\n"
        "under ~/.config/systemd/user/. The current profile is the one\n"
        "that gets wired up."
    ),
    "schedule": (
        "The scheduler auto-installs on first run so cron jobs and\n"
        "reminders fire even when you're not in the TUI. You can still\n"
        "uninstall it here if you prefer to run it manually with\n"
        "`alpi schedule start`, or reinstall after an uninstall."
    ),
}


def _daemon_service_setup(h: Path, name: str) -> None:
    """Install / uninstall the service for one daemon (`gateway` or `schedule`)."""
    from alpi import service, ui

    if name == "gateway" and not _any_gateway_ready(h):
        ui.fail_and_wait(
            "no gateway configured yet — set up Telegram, IMAP, or Gmail first"
        )
        return

    profile_name = _profile_from_home(h)
    backend = service.installed(name, profile_name)
    subtitle = f"running via {backend}" if backend else "not installed"

    ui.banner(ui.crumb("setup", f"{name}-service"), subtitle=subtitle, home=h)
    ui.dim(_DAEMON_WIZARD_COPY[name])
    ui._console.print("")

    if backend:
        items = [("Uninstall", "remove-service", f"running via {backend}")]
    else:
        items = [("Install", "add-service", "register + start now")]

    choice = ui.menu("", items, home=h, close="Back")
    if choice is None:
        return
    try:
        if choice == "add-service":
            kind = service.install(name, h, profile_name)
            ui.ok_and_wait(f"{name} service installed via {kind}")
        elif choice == "remove-service":
            kind = service.uninstall(name, h, profile_name)
            ui.ok_and_wait(f"{name} service uninstalled ({kind})")
    except Exception as e:  # noqa: BLE001
        ui.fail_and_wait(str(e))


def _gateway_service_setup(h: Path) -> None:
    _daemon_service_setup(h, "gateway")


def _schedule_service_setup(h: Path) -> None:
    _daemon_service_setup(h, "schedule")


def _schedule_service_status(h: Path) -> str:
    from alpi import service
    backend = service.installed("schedule", _profile_from_home(h))
    return f"running via {backend}" if backend else "not installed"


def _doctor_status(h: Path, profile: str) -> str:
    """Summary line for the `alpi setup` menu row."""
    try:
        from alpi import doctor
        checks = doctor.run_all(h, profile)
    except Exception:  # noqa: BLE001
        return "ready"
    fails = sum(1 for c in checks if c.status == "fail")
    warns = sum(1 for c in checks if c.status == "warn")
    if fails:
        return f"{fails} failing, {warns} warning(s)"
    if warns:
        return f"{warns} warning(s)"
    return "all green"


def _doctor_wizard(h: Path, profile: str) -> None:
    from alpi import doctor, ui
    ui.banner(ui.crumb("setup", "doctor"), subtitle="health check", home=h)
    ui._console.print("")
    doctor.run_and_render(ui._console, h, profile, __version__)
    ui._console.print("")
    ui.press_enter()


def _profile_from_home(h: Path) -> str:
    from alpi.home import _ROOT
    if h == _ROOT:
        return "default"
    try:
        return h.relative_to(_ROOT / "profiles").parts[0]
    except Exception:  # noqa: BLE001
        return h.name


def _any_gateway_ready(h: Path) -> bool:
    env = _read_profile_env(h)
    if env.get("TELEGRAM_BOT_TOKEN"):
        return True
    if env.get("IMAP_ADDRESS"):
        return True
    if (h / "secrets" / "gmail_token.json").exists():
        return True
    return False


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
    from alpi.mail.gmail_auth import token_path
    env = _read_profile_env(h)
    names = []
    if env.get("TELEGRAM_BOT_TOKEN"):
        names.append("Telegram")
    if env.get("IMAP_ADDRESS"):
        names.append("IMAP")
    if env.get("GMAIL_CLIENT_ID") and token_path(h).exists():
        names.append("Gmail")
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
    from alpi import ui
    while True:
        cfg = config.load(h)

        ui.banner(
            ui.crumb("setup", "sandbox"),
            subtitle=_sandbox_status(cfg),
            home=h,
        )
        ui.dim(
            "Wraps shell commands in sandbox-exec (macOS) or bubblewrap (Linux) so\n"
            "the kernel blocks writes outside your workspace + ~/.alpi, and denies\n"
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
            ui.ok_and_wait("sandbox disabled")
            return

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
            return
        cfg.tools.terminal.allow_network = (net == "allow")
        config.save(cfg)
        ui.ok_and_wait(
            f"sandbox enabled · network "
            f"{'on' if cfg.tools.terminal.allow_network else 'off'}"
        )
        return


_VOICE_SHORTLIST: list[tuple[str, str, str]] = [
    ("en-US-AriaNeural",      "Aria",      "English (US) · female"),
    ("en-US-GuyNeural",       "Guy",       "English (US) · male"),
    ("en-GB-SoniaNeural",     "Sonia",     "English (UK) · female"),
    ("es-ES-AlvaroNeural",    "Alvaro",    "Spanish (Spain) · male"),
    ("es-ES-ElviraNeural",    "Elvira",    "Spanish (Spain) · female"),
    ("es-MX-DaliaNeural",     "Dalia",     "Spanish (Mexico) · female"),
    ("fr-FR-DeniseNeural",    "Denise",    "French (France) · female"),
    ("de-DE-KatjaNeural",     "Katja",     "German · female"),
    ("it-IT-ElsaNeural",      "Elsa",      "Italian · female"),
    ("pt-BR-FranciscaNeural", "Francisca", "Portuguese (Brazil) · female"),
]


def _voice_display(voice_id: str) -> str:
    for vid, name, _ in _VOICE_SHORTLIST:
        if vid == voice_id:
            locale = "-".join(voice_id.split("-", 2)[:2])
            return f"{name} ({locale})"
    return voice_id


def _voice_status(cfg: config.Config) -> str:
    ap = "autoplay on" if cfg.tools.tts.autoplay else "autoplay off"
    return f"{_voice_display(cfg.tools.tts.voice)} · {ap}"


def _voice_setup(h: Path) -> None:
    """Pick the Edge TTS voice + autoplay toggle for the `tts` tool."""
    from alpi import ui
    while True:
        cfg = config.load(h)

        ui.banner(
            ui.crumb("setup", "voice"),
            subtitle=_voice_status(cfg),
            home=h,
        )
        ui.dim(
            "Default voice for audio output + autoplay toggle. Any pick is "
            "permanent until you change it here."
        )
        ui._console.print("")

        accent = (cfg.tui or {}).get("accent", "") or ""
        collected: list[tuple[str, str, str, bool]] = []
        for vid, name, desc in _VOICE_SHORTLIST:
            collected.append((name, desc, vid, vid == cfg.tools.tts.voice))
        collected.append((
            "Autoplay: " + ("on" if cfg.tools.tts.autoplay else "off"),
            "toggle speaker playback",
            "__autoplay__", False,
        ))
        width = max(len(lab) for lab, _s, _v, _a in collected)

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

        choice = ui.menu("", items, home=h, close="Back")
        if choice is None:
            return

        if choice == "__autoplay__":
            cfg.tools.tts.autoplay = not cfg.tools.tts.autoplay
            config.save(cfg)
            ui.ok_and_wait(
                f"autoplay {'on' if cfg.tools.tts.autoplay else 'off'}"
            )
            return

        cfg.tools.tts.voice = choice
        config.save(cfg)
        ui.ok_and_wait(f"voice set to {_voice_display(cfg.tools.tts.voice)}")
        return


_SESSION_STALE_DAYS = 30


def _cleanup_categories(h: Path) -> list[dict]:
    import time
    now = time.time()
    stale_cutoff = now - _SESSION_STALE_DAYS * 86400

    def _dir(name: str) -> Path:
        return h / name

    def _sum(files: list[Path]) -> int:
        total = 0
        for p in files:
            try:
                total += p.stat().st_size
            except OSError:
                pass
        return total

    def _all(d: Path) -> list[Path]:
        if not d.exists():
            return []
        return [p for p in d.iterdir() if p.is_file()]

    def _older_than(d: Path, cutoff: float) -> list[Path]:
        if not d.exists():
            return []
        out: list[Path] = []
        for p in d.iterdir():
            if not p.is_file():
                continue
            try:
                if p.stat().st_mtime < cutoff:
                    out.append(p)
            except OSError:
                continue
        return out

    tts_files = _all(_dir("cache/tts"))
    inbound_files = _all(_dir("cache/inbound"))
    session_files = _older_than(_dir("sessions"), stale_cutoff)
    log_files = _all(_dir("logs"))
    sched_files = _all(_dir("schedule/output"))

    return [
        {
            "key": "audio",
            "label": "Audio cache",
            "desc": "TTS output + inbound Telegram voice notes",
            "files": tts_files + inbound_files,
            "size": _sum(tts_files + inbound_files),
        },
        {
            "key": "sessions",
            "label": f"Sessions (+{_SESSION_STALE_DAYS}days)",
            "desc": "conversation transcripts kept in `sessions/`",
            "files": session_files,
            "size": _sum(session_files),
        },
        {
            "key": "logs",
            "label": "Subsystem logs",
            "desc": "`logs/*.log` — gateway, schedule, agent, approval",
            "files": log_files,
            "size": _sum(log_files),
        },
        {
            "key": "schedule",
            "label": "Schedule output",
            "desc": "stdout/stderr of past scheduled jobs",
            "files": sched_files,
            "size": _sum(sched_files),
        },
    ]


def _cleanup_status(h: Path) -> str:
    from alpi import home as home_mod
    cats = _cleanup_categories(h)
    total = sum(c["size"] for c in cats)
    if total == 0:
        return "nothing to clean"
    return f"{home_mod.format_bytes(total)} reclaimable"


def _cleanup_setup(h: Path) -> None:
    from alpi import home as home_mod, ui
    while True:
        cats = _cleanup_categories(h)
        items: list = []
        for c in cats:
            n = len(c["files"])
            if n == 0:
                status = "empty"
            else:
                status = f"{home_mod.format_bytes(c['size'])} · {n} file{'s' if n != 1 else ''}"
            items.append((c["label"], c["key"], status))

        choice = ui.menu(
            ui.crumb("setup", "cleanup"),
            items,
            subtitle=f"profile: {home_mod.shorten_home(h)}",
            home=h, close="Back",
        )
        if choice is None:
            return
        target = next((c for c in cats if c["key"] == choice), None)
        if target is None or not target["files"]:
            continue

        n = len(target["files"])
        size_label = home_mod.format_bytes(target["size"])
        ui._console.print("")
        if not ui.confirm(
            f"  Delete {n} file(s) · {size_label} from {target['label']}?",
            default=False,
        ):
            continue
        deleted = 0
        for p in target["files"]:
            try:
                p.unlink()
                deleted += 1
            except OSError as e:  # noqa: BLE001
                ui.fail(f"could not delete {p.name}: {e}")
        ui.ok_and_wait(f"removed {deleted} file(s) from {target['label']}")


def _email_status(h: Path) -> str:
    env = _read_profile_env(h)
    addr = env.get("IMAP_ADDRESS", "")
    if not addr:
        return "not set up"
    senders = env.get("IMAP_ALLOWED_SENDERS", "")
    n = len([s for s in senders.split(",") if s.strip()])
    if n == 0:
        return f"ready · {addr} · outbound only"
    return f"ready · {addr} · {n} allowlisted sender{'s' if n != 1 else ''}"


def _gmail_status(h: Path) -> str:
    from alpi.mail.gmail_auth import token_path
    env = _read_profile_env(h)
    if not env.get("GMAIL_CLIENT_ID") or not env.get("GMAIL_CLIENT_SECRET"):
        return "not set up"
    if not token_path(h).exists():
        return "credentials present · not authorized"
    try:
        from alpi.mail.gmail_auth import get_email
        addr = get_email(h) or "?"
    except Exception:  # noqa: BLE001
        addr = "?"
    senders = env.get("GMAIL_ALLOWED_SENDERS", "")
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
    """List available profiles with their model, size, and path."""
    from alpi import config as cfg_mod, home as home_mod, ui

    active = ctx.obj.get("profile") or "default"

    named: list[str] = []
    root = Path.home() / ".alpi" / "profiles"
    if root.exists():
        named = sorted(p.name for p in root.iterdir() if p.is_dir())

    rows: list[list[str]] = []
    for name in ["default", *named]:
        home_path = (
            Path.home() / ".alpi" if name == "default"
            else Path.home() / ".alpi" / "profiles" / name
        )
        try:
            cfg = cfg_mod.load(home_path)
            accent = (cfg.tui or {}).get("accent") or "#ff8800"
            model = cfg.model or "(no model)"
        except Exception:  # noqa: BLE001
            accent = "#ff8800"
            model = "(unreadable)"
        glyph = "◆" if name == active else "◇"
        name_cell = f"[b]{name}[/b]" if name == active else name
        rows.append([
            f"[{accent}]{glyph}[/{accent}]",
            name_cell,
            model,
            home_mod.profile_size_label(home_path),
            home_mod.shorten_home(home_path),
        ])

    ui.columns(rows)

    if not named:
        # Fresh install: nudge the user toward creating one if they want
        # to. Profiles are opt-in — most people never need more than one.
        click.echo("")
        click.echo("Only the default profile exists. Profiles are optional —")
        click.echo("useful if you want separate memories, bots, or schedules")
        click.echo("for different contexts (work vs. personal, e.g.).")
        click.echo("")
        click.echo("Create one with:")
        click.echo("  alpi profile create work")
        click.echo("  alpi profile create personal")
        click.echo("")
        click.echo("Then use it per-invocation:")
        click.echo("  alpi -p work                  # open TUI in the work profile")
        click.echo("  alias alpiw='alpi -p work'     # shell alias if you live there")


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
    click.echo(f"use it with: alpi -p {name}")
    click.echo("")
    click.echo("Configure it:")
    click.echo(f"  alpi -p {name} setup                          "
               f"# interactive (API keys + gateway)")
    default_env = Path.home() / ".alpi" / ".env"
    if default_env.exists():
        click.echo(f"  # — or, to reuse the default profile's setup:")
        click.echo(f"  cp {default_env} {h / '.env'}")


@profile.command("remove")
@click.argument("name")
def profile_remove(name: str) -> None:
    """Permanently remove a profile directory after safety checks."""
    import shutil

    from alpi import service, ui

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
            f"Open `alpi -p {name} setup → Gateway service` and uninstall first."
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
