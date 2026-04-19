"""alf — CLI entry point.

The interactive chat runs in a Textual app (see ``alf.tui.app``). This module
keeps the click-based CLI (subcommands + bootstrap + gateway + --once mode
for the Telegram gateway subprocess).
"""

from __future__ import annotations

import os
import sys
from importlib import resources
from pathlib import Path

import click

from alf import __version__, config, home, memory
from alf.engine import AgentEvent, Engine


# ----------------------------------------------------------------------
# Bootstrap
# ----------------------------------------------------------------------

def _bootstrap(h: Path) -> None:
    home.ensure_home(h)
    config.seed_defaults(h)
    memory.MemoryStore(h).seed_defaults()
    # Resolve PERSONALITY.md (with migration of legacy personality.md / SOUL.md).
    personality = home.personality_path(h)
    if not personality.exists():
        default = resources.files("alf.prompts").joinpath("default_personality.md").read_text()
        personality.write_text(default)


# ----------------------------------------------------------------------
# Chat entry point
# ----------------------------------------------------------------------

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
    """Send escape codes to disable any mouse / paste modes that Textual may
    have left behind when it exited (or crashed).

    Without this, the user's terminal keeps printing raw ANSI escape bytes
    every time they move the mouse or paste.
    """
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
    """Load the most recent saved session into ``engine``.

    Reads the turns log and rebuilds a lean OpenAI message list
    (``system + [user, assistant] × N``) for the LLM. Tool messages are
    NOT reconstructed — the assistant's reply already carries the
    conclusions from its tool use, and reproducing raw tool outputs
    would bloat the resumed context for no added value.

    Imported by :class:`alf.tui.app.AlfApp` (interactive resume) and
    used directly in tests.
    """
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
    """Non-interactive turn. Prints the final assistant text to stdout.

    Used by the Telegram gateway, which spawns ``alf chat --once ...`` per
    incoming message. When ``emit_events`` is set, the gateway gets a live
    JSON-lines stream (one event per line) instead of only the final reply —
    used to surface tool activity in Telegram. Each line is flushed so the
    gateway can react in real time.
    """
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




# ----------------------------------------------------------------------
# Click subcommands
# ----------------------------------------------------------------------

@click.group(invoke_without_command=True)
@click.option("-p", "--profile", default=None, help="Profile name (default: default).")
@click.option("-c", "--continue", "continue_last", is_flag=True,
              help="Continue from the last session.")
@click.version_option(__version__, prog_name="alf")
@click.pass_context
def main(ctx: click.Context, profile: str | None, continue_last: bool) -> None:
    """alf — a slim AI agent."""
    ctx.ensure_object(dict)
    h = home.get_home(profile)
    ctx.obj["home"] = h
    ctx.obj["profile"] = profile or "default"
    ctx.obj["continue_last"] = continue_last
    _bootstrap(h)
    if ctx.invoked_subcommand is None:
        _run_chat(h, continue_last=continue_last)


@main.command()
@click.option("--once", "input_text", default=None,
              help="Run a single non-interactive turn and print the reply.")
@click.option("--emit-events", is_flag=True, default=False,
              help="With --once: stream JSON event lines to stdout (for the gateway).")
@click.option("-c", "--continue", "continue_last", is_flag=True,
              help="Continue from the last session.")
@click.pass_context
def chat(ctx: click.Context, input_text: str | None, emit_events: bool,
         continue_last: bool) -> None:
    """Start an interactive chat session (or --once for one-shot mode)."""
    h: Path = ctx.obj["home"]
    if input_text is not None:
        _run_once(h, input_text, emit_events=emit_events)
    else:
        _run_chat(h, continue_last=continue_last)


@main.command("model")
@click.pass_context
def model_cmd(ctx: click.Context) -> None:
    """Select the default model interactively."""
    from alf import model_selector
    h: Path = ctx.obj["home"]
    _bootstrap(h)
    cfg = config.load(h)
    model_selector.run(cfg)


# ----------------------------------------------------------------------
# Gateway subcommands
# ----------------------------------------------------------------------

@main.group()
def gateway() -> None:
    """Gateway commands (separate process for external channels)."""


@gateway.command("setup")
@click.pass_context
def gateway_setup(ctx: click.Context) -> None:
    """Interactively configure the Telegram gateway."""
    from alf.gateway.setup import run as setup_run
    h: Path = ctx.obj["home"]
    _bootstrap(h)
    setup_run(h)


@gateway.command("start")
@click.pass_context
def gateway_start(ctx: click.Context) -> None:
    """Start the gateway process (blocking)."""
    from alf.gateway.run import run as gw_run, pid_path
    h: Path = ctx.obj["home"]
    _bootstrap(h)
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


# ----------------------------------------------------------------------
# Schedule daemon
# ----------------------------------------------------------------------

@main.group()
def schedule() -> None:
    """Schedule daemon (separate process that fires scheduled jobs)."""


@schedule.command("start")
@click.pass_context
def schedule_start(ctx: click.Context) -> None:
    """Start the schedule daemon (blocking)."""
    from alf.scheduler.run import run as sch_run, pid_path
    h: Path = ctx.obj["home"]
    _bootstrap(h)
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


# ----------------------------------------------------------------------
# Shared install / uninstall / status helpers
# ----------------------------------------------------------------------

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


# ----------------------------------------------------------------------
# setup / profile
# ----------------------------------------------------------------------

@main.command("setup")
@click.pass_context
def setup_cmd(ctx: click.Context) -> None:
    """Interactive setup — model, gateway, etc."""
    import questionary
    from alf.model_selector import _ask
    h: Path = ctx.obj["home"]
    _bootstrap(h)
    while True:
        choice = _ask(questionary.select(
            "Configure:",
            choices=[
                questionary.Choice(title="Model / Provider", value="model"),
                questionary.Choice(title="Gateway (Telegram)", value="gateway"),
                questionary.Choice(title="Exit", value="exit"),
            ],
            qmark="",
            instruction="(↑↓ navigate  ENTER select  ESC cancel)",
        ))
        if choice in (None, "exit"):
            return
        if choice == "model":
            from alf import model_selector
            cfg = config.load(h)
            model_selector.run(cfg)
        elif choice == "gateway":
            from alf.gateway.setup import run as setup_run
            setup_run(h)


@main.group()
def profile() -> None:
    """Profile management (stub in v0)."""


@profile.command("list")
def profile_list() -> None:
    root = Path.home() / ".alf" / "profiles"
    if not root.exists():
        click.echo("default")
        return
    click.echo("default")
    for p in sorted(root.iterdir()):
        if p.is_dir():
            click.echo(p.name)


if __name__ == "__main__":
    main(obj={})
    sys.exit(0)
