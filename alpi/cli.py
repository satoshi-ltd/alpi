"""alpi — CLI entry point."""

from __future__ import annotations

import os
import sys
from importlib import resources
from pathlib import Path
from typing import Any

import click

from alpi import __version__, config, home, memory
from alpi.engine import AgentEvent, Engine


def _suggest(name: str, candidates: list[str]) -> str:
    import difflib

    hit = difflib.get_close_matches(name, candidates, n=1, cutoff=0.6)
    return f". Did you mean {hit[0]!r}?" if hit else ""


def _bootstrap(h: Path) -> None:
    home.ensure_home(h)
    config.seed_defaults(h)
    memory.MemoryStore(h).seed_defaults()
    agent = home.agent_path(h)
    if not agent.exists():
        default = resources.files("alpi.prompts").joinpath("default_agent.md").read_text()
        agent.write_text(default)


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
            "\033[?1000l"  # disable X10 mouse reporting
            "\033[?1002l"  # disable button-event mouse tracking
            "\033[?1003l"  # disable any-event mouse tracking
            "\033[?1006l"  # disable SGR mouse extension
            "\033[?2004l"  # disable bracketed paste
            "\033[?25h"  # show cursor
            "\033[?1049l"  # leave alternate screen
        )
        sys.stdout.write(seqs)
        sys.stdout.flush()
    except Exception:
        pass


def _continue_last_session(engine: Engine, h: Path, console=None) -> bool:
    sessions_dir = h / "sessions"
    if not sessions_dir.exists():
        return False
    candidates = sorted(
        (p for p in sessions_dir.glob("*.json") if not p.name.startswith("_")),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        return False
    return _hydrate_from_path(engine, candidates[0], console=console)


def _continue_specific_session(engine: Engine, h: Path, session_id: str) -> bool:
    """Resume a session by its exact id. Used by gateway per-chat threading."""
    path = h / "sessions" / f"{session_id}.json"
    if not path.exists():
        return False
    return _hydrate_from_path(engine, path)


def _hydrate_from_path(engine: Engine, path: Path, console=None) -> bool:
    import json
    from alpi.session import load_turns

    try:
        data = json.loads(path.read_text())
    except Exception as e:  # noqa: BLE001
        if console is not None:
            console.print(f"could not load session {path.name}: {e}")
        return False

    turns = load_turns(data)
    if not turns:
        return False

    engine.session.messages.append(
        {
            "role": "system",
            "content": (
                "NOTE: the conversation below is a previous session that was "
                "resumed. You already have this context — do not call "
                "`session_search` to recover it. Refer to the messages directly."
            ),
        }
    )
    for t in turns:
        if t.user:
            engine.session.messages.append({"role": "user", "content": t.user})
        if t.assistant:
            engine.session.messages.append({"role": "assistant", "content": t.assistant})
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
        total_chars = sum(len(m.get("content", "") or "") for m in engine.session.messages)
        engine.session.last_ctx_tokens = max(1, total_chars // 4)
    return True


def _run_once(
    h: Path,
    user_text: str,
    emit_events: bool = False,
    resume_chat_id: str | None = None,
) -> None:
    import json
    from alpi import session_map

    _bootstrap(h)
    cfg = config.load(h)
    engine = Engine(home=h, cfg=cfg)

    # Gateway per-chat threading: if the spawner passed a chat id, look up
    # the pointer and resume that session. Missing pointer = fresh session,
    # which we'll bind to the chat after the turn saves.
    if resume_chat_id:
        existing = session_map.get(h, resume_chat_id)
        if existing:
            _continue_specific_session(engine, h, existing)

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
        # Errors go to the reply (so gateway users see them) instead of
        # the event stream — emitting both duplicates the message when
        # the gateway runs with show_tool_trace.
        if emit_events and ev.kind != "error":
            _emit_event_line(ev)
        if ev.kind == "assistant_done" and ev.text.strip():
            parts.append(ev.text)
        elif ev.kind == "error":
            parts.append(ev.text if emit_events else f"[error] {ev.text}")

    engine.run_turn(user_text, emit=sink)
    try:
        engine.save_session()
    except Exception:  # noqa: BLE001
        pass

    # Bind (or refresh) the chat-id → session-id pointer after save, so a
    # follow-up inbound from the same chat picks up the same session.
    if resume_chat_id:
        try:
            session_map.set(h, resume_chat_id, engine.session.id)
        except Exception:  # noqa: BLE001
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

    _ORDER = [
        "chat",
        "setup",
        "doctor",
        "logs",
        "profile",
        "peers",
        "alp",
        "gateway",
        "schedule",
        "release",
    ]

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
@click.option(
    "-c", "--continue", "continue_last", is_flag=True, help="Resume from the last session."
)
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
    # the ``memory`` tool was editing ``~/.alpi/AGENT.md`` when the
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
        # Honour ``tui.auto_resume`` for bare ``alpi`` — if the user opted
        # in via config, resume even without ``-c``. Explicit ``-c`` stays
        # as a manual override. The chat subcommand does NOT auto-resume;
        # it's used by the gateway and by anyone who wants explicit
        # control, so the flag has to stay opt-in there.
        resume = continue_last
        if not resume:
            try:
                cfg = config.load(h)
                resume = bool((cfg.tui or {}).get("auto_resume"))
            except Exception:  # noqa: BLE001
                pass
        _run_chat(h, continue_last=resume)


@main.command()
@click.option(
    "--once", "input_text", default=None, help="Run one turn and print the reply to stdout."
)
# Internal gateway-subprocess contract. Hidden from ``--help`` so the
# public surface stays minimal; users who need one-shot mode use
# ``--once`` alone. The gateway sets this flag when spawning so it
# can parse tool activity from the agent's stdout.
@click.option("--emit-events", is_flag=True, default=False, hidden=True)
@click.option(
    "--resume-chat",
    "resume_chat",
    default=None,
    hidden=True,
    help="Gateway-only: resume the per-chat session for this id.",
)
@click.option(
    "-c", "--continue", "continue_last", is_flag=True, help="Resume from the last session."
)
@click.pass_context
def chat(
    ctx: click.Context,
    input_text: str | None,
    emit_events: bool,
    resume_chat: str | None,
    continue_last: bool,
) -> None:
    """Launch the TUI, or run one turn with ``--once "text"``."""
    h: Path = ctx.obj["home"]
    if input_text is not None:
        _run_once(h, input_text, emit_events=emit_events, resume_chat_id=resume_chat)
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
    from alpi.gateway.run import pid_path

    h: Path = ctx.obj["home"]
    profile: str = ctx.obj.get("profile") or "default"
    _stop_daemon("gateway", h, profile, pid_path(h))


@gateway.command("restart")
@click.pass_context
def gateway_restart(ctx: click.Context) -> None:
    """Stop the gateway and wait for the service to bring it back up.

    Typical use: after ``uv tool install --reinstall``, a restart makes
    the process load the new binary. Only useful when the gateway runs
    under launchd/systemd — if it doesn't, the daemon stays stopped.
    """
    from alpi.gateway.run import pid_path

    h: Path = ctx.obj["home"]
    profile: str = ctx.obj.get("profile") or "default"
    _restart_daemon("gateway", h, profile, pid_path(h))


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
    from alpi.scheduler.run import pid_path

    h: Path = ctx.obj["home"]
    profile: str = ctx.obj.get("profile") or "default"
    _stop_daemon("schedule", h, profile, pid_path(h))


@schedule.command("restart")
@click.pass_context
def schedule_restart(ctx: click.Context) -> None:
    """Stop the schedule daemon and wait for the service to bring it back."""
    from alpi.scheduler.run import pid_path

    h: Path = ctx.obj["home"]
    profile: str = ctx.obj.get("profile") or "default"
    _restart_daemon("schedule", h, profile, pid_path(h))


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


@schedule.command("fire")
@click.argument("job_id")
@click.pass_context
def schedule_fire(ctx: click.Context, job_id: str) -> None:
    """Fire one specific job ad-hoc — same path as the daemon tick.

    Bypasses the schedule check (time / inactivity / once). Useful to
    test a newly-added cron without waiting for its window to hit.
    Does not delete ``once`` jobs — testing doesn't consume them.
    """
    from alpi.scheduler.run import fire_by_id

    h: Path = ctx.obj["home"]
    _bootstrap(h)
    ok, msg = fire_by_id(h, job_id)
    click.echo(f"{'OK' if ok else 'FAIL'}  {msg}")
    if not ok:
        ctx.exit(1)


# Release — auto-generate CHANGELOG sections from git history


@main.group()
def release() -> None:
    """Release-cycle helpers (changelog, tagging)."""


@release.command("notes")
@click.option("--since", default=None, help="Git rev to start from (default: entire history).")
@click.option(
    "-o",
    "--output",
    "output",
    type=click.Path(dir_okay=False, writable=True),
    default=None,
    help="Write to this file instead of stdout (overwrites).",
)
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
@click.option(
    "--source",
    type=click.Choice(["gateway", "schedule", "agent", "approval"]),
    default=None,
    help="Restrict to one subsystem.",
)
@click.option(
    "-n",
    "--tail",
    "tail_n",
    default=100,
    help="Number of most recent lines to show (default: 100).",
)
@click.option(
    "-f", "--follow", is_flag=True, default=False, help="Follow the logs as new lines arrive."
)
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


def _stop_daemon(name: str, home: Path, profile: str, pid_file: Path) -> None:
    """SIGTERM the running ``name`` daemon. If a service is registered,
    warn the user that launchd/systemd will restart the process within
    a few seconds — it's useful for bouncing a stale binary, but the
    wrong tool for actually stopping the daemon. Permanent stop lives
    in ``alpi setup → {Gateway,Schedule} service → Uninstall``."""
    import signal
    from alpi import service

    pid = _read_live_pid(pid_file)
    if pid is None:
        click.echo(f"{name}: not running")
        return

    backend = service.installed(name, profile)
    if backend:
        click.echo(
            f"{name}: managed by {backend}; KeepAlive will restart the "
            f"process in a few seconds. To stop it permanently, "
            f"uninstall from `alpi setup → "
            f"{name.capitalize()} service`."
        )

    try:
        os.kill(pid, signal.SIGTERM)
        click.echo(f"{name}: sent SIGTERM to pid {pid}")
    except ProcessLookupError:
        pid_file.unlink(missing_ok=True)
        click.echo(f"{name}: process {pid} was already gone")


def _restart_daemon(name: str, home: Path, profile: str, pid_file: Path) -> None:
    """Stop + wait for launchd/systemd to bring the process back. When
    no service is installed this degrades to a plain stop — there's
    nothing to restart it and we say so instead of silently waiting
    for a bounce that will never come."""
    import signal
    import time
    from alpi import service

    backend = service.installed(name, profile)
    old_pid = _read_live_pid(pid_file)

    if old_pid is not None:
        try:
            os.kill(old_pid, signal.SIGTERM)
        except ProcessLookupError:
            old_pid = None

    if not backend:
        msg = (
            f"{name}: stopped. No service registered, so nothing will "
            f"relaunch it — install via `alpi setup → {name.capitalize()} service`."
        )
        click.echo(msg)
        return

    # Poll for up to 15s waiting for the service to spawn a replacement.
    deadline = time.time() + 15.0
    new_pid: int | None = None
    while time.time() < deadline:
        candidate = _read_live_pid(pid_file)
        if candidate and candidate != old_pid:
            new_pid = candidate
            break
        time.sleep(0.5)

    if new_pid is None:
        click.echo(
            f"{name}: sent SIGTERM to pid {old_pid}, but no replacement "
            f"appeared within 15s. Check `alpi logs --source {name}`."
        )
        return
    click.echo(f"{name}: restarted via {backend} (pid {old_pid} → {new_pid})")


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
        items: list = [
            ui.Heading("Agent"),
            ("Model / Provider", "model", cfg.model or "(not set)"),
            ("Voice", "voice", _voice_status(cfg)),
            ("MCPs", "mcps", _mcp_status(h)),

            ui.Heading("Boundaries"),
            ("Workspace", "workspace", _workspace_status(cfg)),
            ("Sandbox", "sandbox", _sandbox_status(cfg)),
            ("Budget", "budget", _budget_status(cfg)),

            ui.Heading("Messaging"),
            ("Gateways", "gateways", _gateways_status(h)),
            ("Gateway service", "gateway-service", _gateway_service_status(h)),

            ui.Heading("ALP (Alpi Link Protocol)"),
            ("Peers", "peers", _peers_status(h)),
            ("Workgroups", "workgroups", _workgroups_status(h)),
            ("ALP service", "alp-service", _alp_service_status(h)),

            ui.Heading("Maintenance"),
            ("Schedule service", "schedule-service", _schedule_service_status(h)),
            ("Health check", "doctor", _doctor_status(h, profile_name)),
            ("Cleanup", "cleanup", _cleanup_status(h)),
        ]
        if profile_name != "default":
            items.append(
                ("Delete profile", "delete-profile", _delete_profile_status(h, profile_name))
            )
        # Every title starts with ``alpi`` as a lightweight brand +
        # "you are here" marker. The active profile goes in the
        # subtitle so the user always knows which one they're
        # configuring without it bloating the title itself.
        choice = ui.menu(
            ui.crumb("setup"),
            items,
            subtitle=f"profile: {profile_name}",
            home=h,
            close="Exit",
        )
        if choice is None:
            _setup_farewell(profile_name, h)
            return
        if choice == "model":
            from alpi import model_selector

            model_selector.run(config.load(h))
        elif choice == "workspace":
            _workspace_setup(h)
        elif choice == "gateways":
            _gateways_setup(h)
        elif choice == "mcps":
            from alpi.mcp.setup import run as mcp_setup_run

            mcp_setup_run(h)
        elif choice == "budget":
            _budget_setup(h)
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
        elif choice == "alp-service":
            _alp_service_setup(h)
        elif choice == "peers":
            from alpi.alp.setup import run as alp_setup_run

            alp_setup_run(h)
        elif choice == "workgroups":
            from alpi.alp.workgroup_setup import run as wg_setup_run

            wg_setup_run(h)
        elif choice == "doctor":
            _doctor_wizard(h, profile_name)
        elif choice == "delete-profile":
            if _delete_profile_wizard(h, profile_name):
                return  # profile gone — nothing left to edit


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
            home=h,
            close="Back",
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
        "Keeps the gateway running on boot so Telegram / IMAP / Gmail "
        "stay reachable. Uninstall to run `alpi gateway start` manually."
    ),
    "schedule": (
        "Keeps cron jobs and reminders firing when the TUI is closed. "
        "Uninstall to run `alpi schedule start` manually."
    ),
    "alp": (
        "Keeps the ALP listener up across reboots so peers can reach "
        "this profile. Uninstall to run `alpi alp start` manually."
    ),
}


def _daemon_service_setup(h: Path, name: str) -> None:
    """Install / uninstall the service for one daemon (`gateway` or `schedule`)."""
    from alpi import service, ui

    if name == "gateway" and not _any_gateway_ready(h):
        ui.fail_and_wait("no gateway configured yet — set up Telegram, IMAP, or Gmail first")
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


def _alp_service_setup(h: Path) -> None:
    """ALP service — install/uninstall the launchd/systemd unit, plus
    inter-machine TCP port configuration."""
    from alpi import config as cfg_mod
    from alpi import service, ui

    while True:
        profile_name = _profile_from_home(h)
        backend = service.installed("alp", profile_name)
        svc_label = f"running via {backend}" if backend else "not installed"

        cfg = cfg_mod.load(h)
        tcp_port = (cfg.alp or {}).get("tcp_port")
        tcp_host = (cfg.alp or {}).get("tcp_host") or "127.0.0.1"
        if tcp_port:
            tcp_label = f"{tcp_host}:{tcp_port} (Noise_XK)"
        else:
            tcp_label = "not bound (Unix only)"

        ui.banner(
            ui.crumb("setup", "alp-service"),
            subtitle=svc_label,
            home=h,
        )
        ui.dim(_DAEMON_WIZARD_COPY["alp"])
        ui._console.print("")

        items: list = []
        if backend:
            items.append(("Uninstall service", "remove-service", svc_label))
        else:
            items.append(("Install service", "add-service", "register + start now"))
        items.append(None)
        items.append(("TCP port (inter-machine)", "tcp", tcp_label))

        choice = ui.menu("", items, home=h, close="Back")
        if choice is None:
            return
        try:
            if choice == "add-service":
                kind = service.install("alp", h, profile_name)
                ui.ok_and_wait(f"alp service installed via {kind}")
            elif choice == "remove-service":
                kind = service.uninstall("alp", h, profile_name)
                ui.ok_and_wait(f"alp service uninstalled ({kind})")
            elif choice == "tcp":
                _alp_tcp_port_setup(h)
        except Exception as e:  # noqa: BLE001
            ui.fail_and_wait(str(e))


def _alp_tcp_port_setup(h: Path) -> None:
    """Configure the optional TCP listener for inter-machine ALP links."""
    from alpi import config as cfg_mod
    from alpi import ui

    cfg = cfg_mod.load(h)
    current_port = (cfg.alp or {}).get("tcp_port")
    current_host = (cfg.alp or {}).get("tcp_host") or "127.0.0.1"

    ui.banner(
        ui.crumb("setup", "alp-service", "tcp"),
        subtitle="Noise_XK over TCP — inter-machine peers",
        home=h,
    )
    ui.dim(
        "Sets a TCP port so other machines can dial this profile (Noise_XK,\n"
        "peers.yaml-pinned only). Host 127.0.0.1 = loopback; set a Tailscale\n"
        "/ VPN IP for remote peers. Avoid 0.0.0.0 without a VPN in front.\n"
        "Empty port = disable TCP, keep the Unix socket only."
    )
    ui._console.print("")

    host = ui.text(
        f"Bind host — e.g. 127.0.0.1, a Tailscale IP, or 0.0.0.0 [{current_host}]:",
        default=current_host,
    )
    if host is None:
        return ui.cancelled()
    host = (host or current_host).strip() or "127.0.0.1"

    if host == "0.0.0.0":
        if not ui.confirm(
            "0.0.0.0 exposes the port to every interface. Continue?",
            default=False,
        ):
            return ui.cancelled()

    port_default = str(current_port) if current_port else ""
    port_hint = f"[{port_default}]" if port_default else "[empty = disable TCP]"
    port_s = ui.text(
        f"Port number (1-65535) {port_hint}:",
        default=port_default,
    )
    if port_s is None:
        return ui.cancelled()
    port_s = (port_s or "").strip()

    alp_cfg = dict(cfg.alp or {})

    if not port_s:
        alp_cfg.pop("tcp_port", None)
        alp_cfg.pop("tcp_host", None)
        cfg.alp = alp_cfg
        cfg_mod.save(cfg)
        ui.ok_and_wait("TCP disabled — Unix socket only")
        return

    try:
        port = int(port_s)
    except ValueError:
        ui.fail_and_wait(f"not a valid port: {port_s!r} (did you mean to set it as host?)")
        return
    if not (1 <= port <= 65535):
        ui.fail_and_wait(f"port out of range: {port} (expected 1-65535)")
        return

    alp_cfg["tcp_port"] = port
    alp_cfg["tcp_host"] = host
    cfg.alp = alp_cfg
    cfg_mod.save(cfg)
    ui.ok_and_wait(f"TCP bound to {host}:{port} — restart the alp service to pick it up")


def _schedule_service_status(h: Path) -> str:
    from alpi import service

    backend = service.installed("schedule", _profile_from_home(h))
    return f"running via {backend}" if backend else "not installed"


def _alp_service_status(h: Path) -> str:
    from alpi import service
    from alpi import config as cfg_mod

    backend = service.installed("alp", _profile_from_home(h))
    cfg = cfg_mod.load(h)
    port = (cfg.alp or {}).get("tcp_port")
    base = f"running via {backend}" if backend else "not installed"
    if port:
        return f"{base} · tcp :{port}"
    return base


def _workgroups_status(h: Path) -> str:
    from alpi.alp import subscription as sub_mod
    from alpi.alp import workgroup as wg_mod

    hub_n = len(wg_mod.list_workgroups(h))
    sub_n = len(sub_mod.load(h))
    if hub_n == 0 and sub_n == 0:
        return "none"
    parts = []
    if hub_n:
        parts.append(f"{hub_n} hosting")
    if sub_n:
        parts.append(f"{sub_n} joined")
    return " · ".join(parts)


def _peers_status(h: Path) -> str:
    from alpi.alp import peers as peers_mod

    count = len(peers_mod.load(h))
    if count == 0:
        return "none pinned"
    return f"{count} pinned"


def _doctor_status(h: Path, profile: str) -> str:
    """Menu row hint. The real checks are live network probes (Telegram /
    IMAP / Gmail / MCPs) that take 5–10s — running them on every menu
    render made the wizard feel slow. Run on-demand when the user opens
    the page instead; the health-check screen already has spinners."""
    return "open to run checks"


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


def _budget_status(cfg: config.Config) -> str:
    b = cfg.budget or {}
    usd = b.get("daily_usd")
    tokens = b.get("daily_tokens")
    if isinstance(usd, (int, float)) and usd > 0:
        return f"${float(usd):.2f}/day"
    if isinstance(tokens, int) and tokens > 0:
        return f"{tokens:,} tokens/day"
    return "unlimited"


def _budget_setup(h: Path) -> None:
    from alpi import ui

    cfg = config.load(h)
    b = dict(cfg.budget or {})
    current_usd = b.get("daily_usd") or ""
    current_tokens = b.get("daily_tokens") or ""

    ui.banner(
        ui.crumb("setup", "budget"),
        subtitle="daily spend cap for this profile",
        home=h,
    )
    ui.dim(
        "Paid models → USD cap. Local / free models → token cap. Empty = no\n"
        "ceiling. Cap covers every turn this profile runs (interactive,\n"
        "gateway, scheduled, sub-agents, ALP). Resets at UTC midnight."
    )
    ui._console.print("")

    usd_s = ui.text(
        f"Daily USD cap (empty to skip) [{current_usd}]:",
        default=str(current_usd),
    )
    if usd_s is None:
        return ui.cancelled()
    usd_s = (usd_s or "").strip()

    tokens_s = ui.text(
        f"Daily token cap (empty to skip) [{current_tokens}]:",
        default=str(current_tokens),
    )
    if tokens_s is None:
        return ui.cancelled()
    tokens_s = (tokens_s or "").strip()

    new_budget: dict[str, Any] = {}
    if usd_s:
        try:
            v = float(usd_s)
        except ValueError:
            ui.fail_and_wait(f"not a number: {usd_s!r}")
            return
        if v <= 0:
            ui.fail_and_wait("USD cap must be > 0")
            return
        new_budget["daily_usd"] = v

    if tokens_s:
        try:
            v_int = int(tokens_s)
        except ValueError:
            ui.fail_and_wait(f"not an integer: {tokens_s!r}")
            return
        if v_int <= 0:
            ui.fail_and_wait("token cap must be > 0")
            return
        new_budget["daily_tokens"] = v_int

    cfg.budget = new_budget
    config.save(cfg)
    if not new_budget:
        ui.ok_and_wait("budget cleared — unlimited")
    elif "daily_usd" in new_budget and "daily_tokens" in new_budget:
        ui.ok_and_wait(
            f"cap: ${new_budget['daily_usd']:.2f}/day · "
            f"{new_budget['daily_tokens']:,} tokens/day"
        )
    elif "daily_usd" in new_budget:
        ui.ok_and_wait(f"cap: ${new_budget['daily_usd']:.2f}/day")
    else:
        ui.ok_and_wait(f"cap: {new_budget['daily_tokens']:,} tokens/day")


def _workspace_status(cfg: config.Config) -> str:
    if cfg.workspace_path is not None:
        return str(cfg.workspace_path)
    return "not set · falls back to cwd"


def _workspace_setup(h: Path) -> None:
    """Pick the workspace directory for the current profile.

    The workspace is the default root for relative paths in file tools
    and the shell sandbox. Not a wall — absolute paths still reach
    outside, with the sensitive-path denylist as the only hard stop.
    Stored as ``workspace:`` in the profile's ``config.yaml``.
    """
    from alpi import ui

    cfg = config.load(h)

    ui.banner(
        ui.crumb("setup", "workspace"),
        subtitle=_workspace_status(cfg),
        home=h,
    )
    ui.dim(
        "Default root for relative paths in file tools and terminal.\n"
        "Unset → falls back to the cwd at launch. Not a wall: real\n"
        "isolation is the opt-in Sandbox.\n\n"
        "Empty = keep current; type `clear` to unset."
    )
    ui._console.print("")

    current = cfg.workspace or ""
    raw = ui.text("Workspace directory", default=current)
    if raw is None:
        return ui.cancelled()
    raw = raw.strip()
    if not raw:
        ui.ok_and_wait("workspace unchanged")
        return
    if raw.lower() == "clear":
        cfg.workspace = ""
        config.save(cfg)
        ui.ok_and_wait("workspace cleared — will use cwd at launch")
        return
    try:
        p = Path(raw).expanduser().resolve()
    except Exception as e:  # noqa: BLE001
        ui.fail_and_wait(f"bad path: {e}")
        return
    if not p.is_dir():
        ui.fail_and_wait(f"not a directory (or doesn't exist): {p}")
        return
    cfg.workspace = str(p)
    config.save(cfg)
    ui.ok_and_wait(f"workspace set to {p}")


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
            "Wraps shell commands in sandbox-exec (macOS) or bubblewrap (Linux):\n"
            "kernel blocks writes outside workspace + ~/.alpi, network denied\n"
            "unless opted in.\n\n"
            "Recommended for unattended profiles (gateway, scheduler, sub-agents).\n"
            "Trade-offs: SSH push, Homebrew on Apple Silicon, and docker may break\n"
            "— keep off in your main dev profile."
        )
        ui._console.print("")

        choice = ui.menu(
            "",
            [
                ("Enable sandbox", "enable"),
                ("Disable sandbox", "disable"),
            ],
            home=h,
            close="Back",
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
            home=h,
            close="Back",
        )
        if net is None:
            return
        cfg.tools.terminal.allow_network = net == "allow"
        config.save(cfg)
        ui.ok_and_wait(
            f"sandbox enabled · network {'on' if cfg.tools.terminal.allow_network else 'off'}"
        )
        return


_VOICE_SHORTLIST: list[tuple[str, str, str]] = [
    ("en-US-AriaNeural", "Aria", "English (US) · female"),
    ("en-US-GuyNeural", "Guy", "English (US) · male"),
    ("en-GB-SoniaNeural", "Sonia", "English (UK) · female"),
    ("es-ES-AlvaroNeural", "Alvaro", "Spanish (Spain) · male"),
    ("es-ES-ElviraNeural", "Elvira", "Spanish (Spain) · female"),
    ("es-MX-DaliaNeural", "Dalia", "Spanish (Mexico) · female"),
    ("fr-FR-DeniseNeural", "Denise", "French (France) · female"),
    ("de-DE-KatjaNeural", "Katja", "German · female"),
    ("it-IT-ElsaNeural", "Elsa", "Italian · female"),
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
        collected.append(
            (
                "Autoplay: " + ("on" if cfg.tools.tts.autoplay else "off"),
                "toggle speaker playback",
                "__autoplay__",
                False,
            )
        )
        width = max(len(lab) for lab, _s, _v, _a in collected)

        items: list = []
        for label, status, value, active in collected:
            if active:
                items.append(
                    (
                        ui.row_accent(label, status, accent, width=width),
                        value,
                    )
                )
            else:
                items.append(
                    (
                        ui.row(label, status, width=width),
                        value,
                    )
                )

        choice = ui.menu("", items, home=h, close="Back")
        if choice is None:
            return

        if choice == "__autoplay__":
            cfg.tools.tts.autoplay = not cfg.tools.tts.autoplay
            config.save(cfg)
            ui.ok_and_wait(f"autoplay {'on' if cfg.tools.tts.autoplay else 'off'}")
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
            "label": f"Stale sessions (>{_SESSION_STALE_DAYS} days old)",
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
            home=h,
            close="Back",
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
            Path.home() / ".alpi"
            if name == "default"
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
        rows.append(
            [
                f"[{accent}]{glyph}[/{accent}]",
                name_cell,
                model,
                home_mod.profile_size_label(home_path),
                home_mod.shorten_home(home_path),
            ]
        )

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
    click.echo(
        f"  alpi -p {name} setup                          # interactive (API keys + gateway)"
    )
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
        from alpi.home import _ROOT

        profiles_root = _ROOT / "profiles"
        available = (
            [p.name for p in profiles_root.iterdir() if p.is_dir()]
            if profiles_root.exists()
            else []
        )
        raise click.ClickException(
            f"profile {name!r} does not exist{_suggest(name, available)}",
        )

    # Safety: refuse if the profile has a registered system service.
    # Uninstalling them is an explicit step the user has to take so
    # they understand what's being torn down.
    installed = [
        daemon
        for daemon in ("gateway", "schedule", "alp")
        if service.installed(daemon, profile=name)
    ]
    if installed:
        svc_list = ", ".join(installed)
        raise click.ClickException(
            f"profile {name!r} has installed service(s): {svc_list}.\n"
            f"Run `alpi -p {name} setup → Delete profile` to uninstall "
            f"services and delete in one step."
        )

    # Summary — user wants to see what they're losing before saying yes.
    summary = _profile_summary(h)
    ui.banner(f"Remove profile · {name}", subtitle=str(h))
    for line in summary:
        click.echo(f"  {line}")
    click.echo("")
    if not ui.confirm(f"Remove profile {name!r}? This cannot be undone.", default=False):
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


def _delete_profile_status(h: Path, profile_name: str) -> str:
    from alpi import service

    installed = [
        d for d in ("gateway", "schedule", "alp") if service.installed(d, profile=profile_name)
    ]
    if installed:
        return f"Remove all data & {len(installed)} service(s)"
    return "Remove all data"


def _delete_profile_wizard(h: Path, profile_name: str) -> bool:
    """Return True if the profile was deleted — the caller must exit the
    setup loop because there is nothing left to edit."""
    import shutil
    from alpi import service, ui

    ui.banner(ui.crumb("setup", "danger", f"delete {profile_name}"), subtitle=str(h), home=h)
    ui._console.print("")

    summary = _profile_summary(h)
    for line in summary:
        ui._console.print(f"  {line}")

    installed = [
        d for d in ("gateway", "schedule", "alp") if service.installed(d, profile=profile_name)
    ]
    if installed:
        ui._console.print("")
        ui.warn(f"installed services: {', '.join(installed)} — will be uninstalled")
    ui._console.print("")

    if not ui.confirm(
        f"Delete profile '{profile_name}' — this cannot be undone. Continue?",
        default=False,
    ):
        ui.cancelled()
        return False

    typed = ui.text(f"Type '{profile_name}' to confirm")
    if (typed or "").strip() != profile_name:
        ui.cancelled()
        return False

    for daemon in installed:
        try:
            kind = service.uninstall(daemon, h, profile_name)
            ui.ok(f"uninstalled {daemon} service ({kind})")
        except Exception as e:  # noqa: BLE001
            ui.fail(f"failed to uninstall {daemon}: {e}")
            ui.warn("aborting delete — address the service issue and retry.")
            ui.press_enter()
            return False

    try:
        shutil.rmtree(h)
    except Exception as e:  # noqa: BLE001
        ui.fail_and_wait(f"rmtree failed: {e}")
        return False

    ui.ok_and_wait(f"profile '{profile_name}' deleted.")
    return True


# ALP (Alpi Link Protocol) — peer management + dev listener
#
# ``alpi peers`` covers the day-to-day: generate / inspect this
# profile's keypair, add or remove peers, send a ping. The eventual
# UX home for add/remove is the ``alpi setup → Peers`` wizard;
# these commands stay as the scriptable surface.
#
# ``alpi alp start`` runs the Unix-socket listener in the
# foreground. It's hidden: in the final wiring it folds into the
# gateway daemon (one always-on process per profile). Exposed for
# now so a developer can stand up two profiles in two terminals
# and watch them ping each other before the gateway integration
# lands.


@main.group()
def peers() -> None:
    """Manage ALP peer identities (spec: docs/ALP.md)."""


@peers.command("key")
@click.pass_context
def peers_key(ctx: click.Context) -> None:
    """Print this profile's ALP public key. Paste the line into the
    other peer's ``peers add`` to pin it."""
    from alpi.alp.keys import load_or_generate

    h: Path = ctx.obj["home"]
    kp = load_or_generate(h)
    click.echo(kp.pubkey_b64())


@peers.command("list")
@click.pass_context
def peers_list(ctx: click.Context) -> None:
    """Show pinned peers for this profile."""
    from alpi import ui
    from alpi.alp import peers as peers_mod

    h: Path = ctx.obj["home"]
    entries = peers_mod.load(h)
    if not entries:
        click.echo("no peers pinned. `alpi peers add <id> <pubkey>` to add one.")
        return
    rows: list[list[str]] = []
    for p in entries:
        addr = p.address or "local"
        allow = ", ".join(p.allow) or "—"
        rows.append([p.id, p.pubkey[:12] + "…", addr, allow])
    click.echo(f"{len(entries)} peer(s):")
    ui.columns(rows)


@peers.command("add")
@click.argument("peer_id")
@click.argument("pubkey_b64")
@click.option(
    "--allow",
    default="link.ping,link.ask",
    help="Comma-separated method allowlist (default: link.ping,link.ask).",
)
@click.option(
    "--address", default=None, help="host:port for inter-machine peers; omit for intra-machine."
)
@click.option("--alias", default="", help="Optional display label.")
@click.pass_context
def peers_add(
    ctx: click.Context,
    peer_id: str,
    pubkey_b64: str,
    allow: str,
    address: str | None,
    alias: str,
) -> None:
    """Pin a peer's pubkey + capabilities."""
    from alpi.alp import peers as peers_mod

    h: Path = ctx.obj["home"]
    peer = peers_mod.Peer(
        id=peer_id,
        pubkey=pubkey_b64.strip(),
        alias=alias,
        address=address,
        allow=[m.strip() for m in allow.split(",") if m.strip()],
    )
    try:
        peers_mod.add(h, peer)
    except ValueError as e:
        raise click.ClickException(str(e))
    click.echo(f"added peer {peer_id!r} ({len(peer.allow)} method(s) allowed)")


@peers.command("remove")
@click.argument("peer_id")
@click.pass_context
def peers_remove(ctx: click.Context, peer_id: str) -> None:
    """Remove a peer. Does not touch the pinned pubkey file on the
    other side — the remote profile still has you in its list until
    they drop you too."""
    from alpi.alp import peers as peers_mod

    h: Path = ctx.obj["home"]
    if peers_mod.remove(h, peer_id):
        click.echo(f"removed peer {peer_id!r}")
    else:
        available = [p.id for p in peers_mod.load(h)]
        raise click.ClickException(f"no peer {peer_id!r}{_suggest(peer_id, available)}")


@peers.command("ping")
@click.argument("peer_id")
@click.pass_context
def peers_ping(ctx: click.Context, peer_id: str) -> None:
    """Send a link.ping to a pinned peer and print the response."""
    import asyncio
    from alpi.alp import client as alp_client
    from alpi.alp import peers as peers_mod
    from alpi.alp.keys import load_or_generate

    h: Path = ctx.obj["home"]
    peer = peers_mod.get_by_id(h, peer_id)
    if peer is None:
        available = [p.id for p in peers_mod.load(h)]
        raise click.ClickException(
            f"no peer {peer_id!r}{_suggest(peer_id, available)} (see `alpi peers list`)",
        )

    sender = load_or_generate(h)
    try:
        if peer.address:
            host, _, port_s = peer.address.rpartition(":")
            if not host or not port_s.isdigit():
                raise click.ClickException(
                    f"peer {peer_id!r} has an invalid address {peer.address!r}; expected host:port",
                )
            transport = f"tcp://{host}:{port_s}"
            result = asyncio.run(
                alp_client.call_tcp(
                    host=host,
                    port=int(port_s),
                    sender=sender,
                    recipient_pubkey_b64=peer.pubkey,
                    method="link.ping",
                    params={"nonce": "cli"},
                )
            )
        else:
            if peer_id == "default":
                target_home = Path.home() / ".alpi"
            else:
                target_home = Path.home() / ".alpi" / "profiles" / peer_id
            socket_path = target_home / "alp" / "alp.sock"
            if not socket_path.exists():
                raise click.ClickException(
                    f"target socket not found: {socket_path}\n"
                    f"Start the peer's listener first: "
                    f"`alpi -p {peer_id} alp start`",
                )
            transport = str(socket_path)
            result = asyncio.run(
                alp_client.call(
                    socket_path=socket_path,
                    sender=sender,
                    recipient_pubkey_b64=peer.pubkey,
                    method="link.ping",
                    params={"nonce": "cli"},
                )
            )
    except alp_client.TargetOffline as e:
        raise click.ClickException(f"target-offline: {e}")
    except alp_client.ClientError as e:
        raise click.ClickException(f"transport-error: {e}")
    except alp_client.RemoteError as e:
        raise click.ClickException(f"remote-error: {e}")
    click.echo(
        f"pong from {result.get('agent_name', '?')} "
        f"· version={result.get('version', '?')} "
        f"· nonce={result.get('nonce', '?')} "
        f"· via {transport}"
    )


@main.group()
def alp() -> None:
    """ALP listener controls (install as a service via ``alpi setup``)."""


def _alp_pid_path(home: Path) -> Path:
    return home / "alp" / "alp.pid"


@alp.command("start")
@click.option(
    "--port",
    type=int,
    default=None,
    help="TCP port for inter-machine peers (Noise_XK). Overrides config.alp.tcp_port.",
)
@click.option(
    "--host",
    type=str,
    default=None,
    help="TCP bind host (default 127.0.0.1; set 0.0.0.0 or a VPN IP to accept remote peers).",
)
@click.pass_context
def alp_start(ctx: click.Context, port: int | None, host: str | None) -> None:
    """Run the ALP listener (Unix socket + optional TCP) for this profile."""
    import asyncio
    import logging
    from alpi.alp import handlers as alp_handlers
    from alpi.alp.server import Server
    from alpi import config as cfg_mod

    h: Path = ctx.obj["home"]
    profile: str = ctx.obj.get("profile") or "default"
    _bootstrap(h)
    _check_not_running(_alp_pid_path(h))

    cfg = cfg_mod.load(h)
    cfg_alp = cfg.alp or {}
    tcp_port = port if port is not None else cfg_alp.get("tcp_port")
    tcp_host = host if host is not None else cfg_alp.get("tcp_host")
    if tcp_port is not None and not isinstance(tcp_port, int):
        raise click.ClickException(
            f"alp.tcp_port in config.yaml must be an int, got {type(tcp_port).__name__}"
        )

    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    srv_log = logging.getLogger("alpi.alp.server")
    srv_log.setLevel(logging.INFO)
    srv_log.addHandler(handler)

    server = Server(
        home=h,
        agent_name=profile,
        tcp_host=tcp_host,
        tcp_port=tcp_port,
    )
    alp_handlers.register_link_ask(server, h)
    from alpi.alp import workgroup as alp_workgroup
    alp_workgroup.register(server, h)

    pid_file = _alp_pid_path(h)
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    pid_file.write_text(str(os.getpid()))

    async def _run() -> None:
        await server.start()
        lines = [f"alp: {profile} listening on {server.socket_path()}"]
        if tcp_port is not None:
            bind = tcp_host or "127.0.0.1"
            lines.append(f"     tcp:    Noise_XK on {bind}:{tcp_port}")
        lines.append(f"     pubkey: {server.pubkey_b64}")
        lines.append("     (Ctrl-C to stop)")
        click.echo("\n".join(lines))
        try:
            await server.serve_forever()
        finally:
            await server.stop()

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        click.echo("\nalp: stopped")
    finally:
        if pid_file.exists():
            pid_file.unlink(missing_ok=True)


@alp.command("stop")
@click.pass_context
def alp_stop(ctx: click.Context) -> None:
    """Stop a running ALP listener (SIGTERM)."""
    h: Path = ctx.obj["home"]
    profile: str = ctx.obj.get("profile") or "default"
    _stop_daemon("alp", h, profile, _alp_pid_path(h))


@alp.command("restart")
@click.pass_context
def alp_restart(ctx: click.Context) -> None:
    """Stop the listener and wait for the service to bring it back."""
    h: Path = ctx.obj["home"]
    profile: str = ctx.obj.get("profile") or "default"
    _restart_daemon("alp", h, profile, _alp_pid_path(h))


# Workgroups (ALP.3)


@main.group()
def workgroup() -> None:
    """Manage ALP workgroups (multi-party shared transcripts).

    Verbs split by role: as a hub you `create` / `kick` / inspect
    locally-hosted workgroups; as a member you `join` / `post` /
    `pull` / `pause` / `resume` / `leave` ones a peer is hosting.
    Both flows share `list` and `show`.
    """


@workgroup.command("list")
@click.pass_context
def workgroup_list(ctx: click.Context) -> None:
    """Show workgroups this profile is hub of and member of."""
    from alpi import ui as ui_mod
    from alpi.alp import subscription as sub_mod
    from alpi.alp import workgroup as wg_mod

    h: Path = ctx.obj["home"]
    hub = wg_mod.list_workgroups(h)
    sub = sub_mod.load(h)
    if not hub and not sub:
        click.echo("no workgroups. `alpi workgroup create` or `alpi workgroup join`.")
        return
    if hub:
        click.echo("hub of:")
        for w in hub:
            paused = " [paused]" if w.meta.paused else ""
            click.echo(f"  {w.meta.id}  {w.meta.name}  ({len(w.members)} members){paused}")
    if sub:
        click.echo("member of:")
        for s in sub:
            click.echo(f"  {s.wg_id}  {s.name}  via @{s.hub_id}  (seq {s.last_seq})")


@workgroup.command("show")
@click.argument("wg_id")
@click.pass_context
def workgroup_show(ctx: click.Context, wg_id: str) -> None:
    """Print workgroup detail + decrypted transcript."""
    from alpi.alp import subscription as sub_mod
    from alpi.alp import workgroup as wg_mod
    from alpi.alp.keys import load_or_generate

    h: Path = ctx.obj["home"]
    wg = wg_mod.load(h, wg_id)
    if wg is not None:
        kp = load_or_generate(h)
        click.echo(f"{wg.meta.name}  ({wg.meta.id})")
        click.echo(f"  role     hub")
        click.echo(f"  members  {len(wg.members)}")
        click.echo(f"  paused   {wg.meta.paused}")
        click.echo(f"  key v    {wg.meta.current_key_version}")
        if wg.meta.budget:
            click.echo(f"  budget   {wg.meta.budget}")
        # Decrypt with hub's own key
        member = wg.member(kp.pubkey_b64())
        if member is None:
            return
        try:
            from alpi.alp.workgroup import open_sealed_group_key, decrypt_post
            gk = open_sealed_group_key(member.sealed_key, kp)
        except Exception:  # noqa: BLE001
            gk = None
        click.echo("transcript:")
        for p in _read_local_transcript(h, wg_id):
            text = "[v" + str(p.get("key_version", 1)) + " key gone]"
            if gk is not None and int(p.get("key_version", 1)) == member.key_version:
                try:
                    text = decrypt_post(gk, p["nonce"], p["ciphertext"]).decode()
                except Exception as e:  # noqa: BLE001
                    text = f"[decrypt failed: {e}]"
            click.echo(f"  #{p['seq']}  {p['from'][:12]}…  {text}")
        return

    s = sub_mod.get(h, wg_id)
    if s is None:
        raise click.ClickException(f"workgroup {wg_id!r} not found")
    click.echo(f"{s.name}  ({s.wg_id})")
    click.echo(f"  role     member")
    click.echo(f"  hub      @{s.hub_id}")
    click.echo(f"  cursor   seq {s.last_seq}")
    click.echo(f"  keys     v{s.latest_version()} cached")
    click.echo("(use `alpi workgroup pull` to fetch + decrypt the transcript)")


def _read_local_transcript(h: Path, wg_id: str) -> list[dict]:
    p = h / "alp" / "workgroups" / wg_id / "transcript.jsonl"
    if not p.exists():
        return []
    out = []
    import json as _json
    for line in p.read_text().splitlines():
        line = line.strip()
        if line:
            try:
                out.append(_json.loads(line))
            except _json.JSONDecodeError:
                continue
    return out


@workgroup.command("create")
@click.argument("name")
@click.option("--member", "members", multiple=True,
              help="Member pubkey or pinned peer id. Repeat for multiple.")
@click.option("--budget-usd", type=float, default=None,
              help="Lifetime USD cap (paid models).")
@click.option("--budget-tokens", type=int, default=None,
              help="Lifetime token cap (local / free models).")
@click.pass_context
def workgroup_create(
    ctx: click.Context, name: str,
    members: tuple[str, ...], budget_usd: float | None, budget_tokens: int | None,
) -> None:
    """Create a workgroup; you become the hub. Members are pubkeys or
    pinned peer ids (the latter resolve via this profile's peers.yaml)."""
    from alpi.alp import peers as peers_mod
    from alpi.alp import workgroup as wg_mod
    from alpi.alp.keys import load_or_generate

    h: Path = ctx.obj["home"]
    pubkeys: list[str] = []
    for m in members:
        m = m.strip()
        if not m:
            continue
        peer = peers_mod.get_by_id(h, m)
        pubkeys.append(peer.pubkey if peer else m)

    budget: dict = {}
    if budget_usd is not None and budget_tokens is not None:
        raise click.ClickException("--budget-usd and --budget-tokens are mutually exclusive")
    if budget_usd is not None:
        budget["max_usd"] = budget_usd
    if budget_tokens is not None:
        budget["max_tokens"] = budget_tokens

    try:
        wg = wg_mod.create(
            h, name=name, hub_kp=load_or_generate(h),
            member_pubkeys=pubkeys, budget=budget,
        )
    except ValueError as e:
        raise click.ClickException(str(e))
    click.echo(f"created {wg.meta.id} · {len(wg.members)} members")


@workgroup.command("join")
@click.argument("hub_peer_id")
@click.argument("wg_id")
@click.pass_context
def workgroup_join(ctx: click.Context, hub_peer_id: str, wg_id: str) -> None:
    """Subscribe to a remote workgroup. ``hub_peer_id`` must be a
    pinned peer in this profile's peers.yaml."""
    from alpi.alp import workgroup_client as wc

    h: Path = ctx.obj["home"]
    try:
        sub = asyncio.run(wc.join(h, hub_peer_id, wg_id))
    except alp_client.RemoteError as e:
        raise click.ClickException(f"hub rejected: {e.code} {e.message}")
    except (ValueError, alp_client.ClientError) as e:
        raise click.ClickException(str(e))
    click.echo(f"joined {sub.name or sub.wg_id} via @{sub.hub_id}")


@workgroup.command("post")
@click.argument("wg_id")
@click.argument("text")
@click.pass_context
def workgroup_post_cmd(ctx: click.Context, wg_id: str, text: str) -> None:
    """Encrypt and post a message to a workgroup we are subscribed to."""
    from alpi.alp import workgroup_client as wc

    h: Path = ctx.obj["home"]
    try:
        result = asyncio.run(wc.post(h, wg_id, text.encode("utf-8")))
    except alp_client.RemoteError as e:
        raise click.ClickException(f"hub rejected: {e.code} {e.message}")
    except (ValueError, alp_client.ClientError) as e:
        raise click.ClickException(str(e))
    click.echo(f"posted seq {result.get('seq')}")


@workgroup.command("pull")
@click.argument("wg_id")
@click.option("--since", type=int, default=None,
              help="Override the local cursor (default: pick up where we left off).")
@click.pass_context
def workgroup_pull(ctx: click.Context, wg_id: str, since: int | None) -> None:
    """Fetch new posts and decrypt them. Advances the cursor."""
    from alpi.alp import workgroup_client as wc

    h: Path = ctx.obj["home"]
    try:
        posts, head = asyncio.run(wc.pull(h, wg_id, since=since))
    except alp_client.RemoteError as e:
        raise click.ClickException(f"hub rejected: {e.code} {e.message}")
    except (ValueError, alp_client.ClientError) as e:
        raise click.ClickException(str(e))
    if not posts:
        click.echo(f"(no new posts; head={head})")
        return
    for p in posts:
        click.echo(f"  #{p['seq']}  {p['from'][:12]}…  {p['text']}")
    click.echo(f"head={head}")


@workgroup.command("pause")
@click.argument("wg_id")
@click.pass_context
def workgroup_pause(ctx: click.Context, wg_id: str) -> None:
    """Pause a workgroup (any member can; idempotent)."""
    _wg_simple(ctx, wg_id, "pause", "paused")


@workgroup.command("resume")
@click.argument("wg_id")
@click.pass_context
def workgroup_resume(ctx: click.Context, wg_id: str) -> None:
    """Resume a paused workgroup."""
    _wg_simple(ctx, wg_id, "resume", "resumed")


@workgroup.command("leave")
@click.argument("wg_id")
@click.pass_context
def workgroup_leave(ctx: click.Context, wg_id: str) -> None:
    """Leave a workgroup. The hub rotates the group key on remaining
    members; we drop our subscription locally."""
    _wg_simple(ctx, wg_id, "leave", "left")


def _wg_simple(ctx, wg_id: str, verb: str, ok_msg: str) -> None:
    from alpi.alp import workgroup_client as wc

    h: Path = ctx.obj["home"]
    fn = getattr(wc, verb)
    try:
        asyncio.run(fn(h, wg_id))
    except alp_client.RemoteError as e:
        raise click.ClickException(f"hub rejected: {e.code} {e.message}")
    except (ValueError, alp_client.ClientError) as e:
        raise click.ClickException(str(e))
    click.echo(f"{ok_msg} {wg_id}")


@workgroup.command("kick")
@click.argument("wg_id")
@click.argument("member_pubkey")
@click.pass_context
def workgroup_kick(ctx: click.Context, wg_id: str, member_pubkey: str) -> None:
    """Hub-side: drop a member and rotate the group key."""
    from alpi.alp import peers as peers_mod
    from alpi.alp import workgroup as wg_mod

    h: Path = ctx.obj["home"]
    # Allow kicking by peer id too
    peer = peers_mod.get_by_id(h, member_pubkey)
    target = peer.pubkey if peer else member_pubkey
    try:
        updated = wg_mod.kick(h, wg_id, target)
    except ValueError as e:
        raise click.ClickException(str(e))
    click.echo(f"kicked + rekeyed · v{updated.meta.current_key_version} "
               f"({len(updated.members)} members remaining)")


if __name__ == "__main__":
    main(obj={})
    sys.exit(0)
