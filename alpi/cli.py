"""alpi — CLI entry point."""

from __future__ import annotations

import asyncio
import os
import re
import sys
from importlib import resources
from pathlib import Path
from typing import Any

import click

from alpi import __version__, config, home, memory, runtime
from alpi.alp import client as alp_client
from alpi.engine import AgentEvent, Engine


def _is_local_chat_session_payload(data: dict[str, Any]) -> bool:
    turns = data.get("turns") or []
    first = ""
    if turns:
        first = str((turns[0] or {}).get("user") or "").lstrip()
    if not first:
        return True
    if first.startswith("[workgroup-poller]") or first.startswith("[workgroup "):
        return False
    if first.startswith("[SCHEDULED:") or first.startswith("[CRON"):
        return False
    if first.startswith("[INBOUND "):
        return False
    if first.startswith("["):
        return False
    return True


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




def _run_chat(h: Path, continue_last: bool = False) -> None:
    _bootstrap(h)
    from alpi.tui import AlpiApp

    try:
        AlpiApp(home_dir=h, continue_last=continue_last).run()
    finally:
        _restore_terminal()
        # os._exit, not return: atexit would .join() a worker still blocked on the LLM HTTP call.
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
        (
            p for p in sessions_dir.glob("*.json")
            if not p.name.startswith("_") and _is_local_chat_session_path(p)
        ),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        return False
    return _hydrate_from_path(engine, candidates[0], console=console)


def _is_local_chat_session_path(path: Path) -> bool:
    import json
    try:
        data = json.loads(path.read_text())
    except Exception:
        return False
    return _is_local_chat_session_payload(data)


_SAFE_SESSION_ID = re.compile(r"^[A-Za-z0-9_-]+$")


def _continue_specific_session(
    engine: Engine, h: Path, session_id: str, subdir: str = "sessions",
) -> bool:
    """Resume a session by id."""
    if not _SAFE_SESSION_ID.match(session_id or ""):
        return False
    path = h / subdir / f"{session_id}.json"
    if not path.exists():
        return False
    return _hydrate_from_path(engine, path)


def _hydrate_from_path(engine: Engine, path: Path, console=None) -> bool:
    import json
    from alpi.session import load_turns, turn_replayable

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
    from alpi import attachments as _att
    for t in turns:
        if not turn_replayable(t):
            continue
        if t.user or t.attachments:
            marker = _att.describe_meta(t.attachments)
            text = f"{t.user}\n{marker}".strip() if marker else t.user
            engine.session.messages.append({"role": "user", "content": text})
        if t.assistant or t.output_attachments:
            produced = _att.describe_produced(t.output_attachments)
            atext = f"{t.assistant}\n{produced}".strip() if produced else t.assistant
            if atext:
                engine.session.messages.append({"role": "assistant", "content": atext})
    engine.session.turns = list(turns)

    if data.get("id"):
        engine.session.id = data["id"]
    engine.session.connection_id = str(data.get("connection_id") or "host")
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


def _resume_once(
    engine: Engine, h: Path, *,
    session_id: str | None = None,
    continue_last: bool = False,
) -> None:
    if session_id:
        if not _continue_specific_session(engine, h, session_id):
            raise click.ClickException(f"session not found: {session_id}")
    elif continue_last:
        _continue_last_session(engine, h, None)


def _run_once(
    h: Path,
    user_text: str,
    emit_events: bool = False,
    persist: bool = True,
    attach: tuple[str, ...] = (),
    session_id: str | None = None,
    continue_last: bool = False,
) -> None:
    import json

    _bootstrap(h)
    cfg = config.load(h)
    engine = Engine(home=h, cfg=cfg)

    attachments = (
        [{"path": str(Path(p).expanduser().resolve()), "name": Path(p).name} for p in attach]
        or None
    )

    _resume_once(
        engine, h, session_id=session_id, continue_last=continue_last,
    )

    from alpi.alp import mention as alp_mention
    parsed = alp_mention.parse(user_text, home=h)
    if parsed is not None:
        import asyncio as _aio
        import time as _t
        from alpi.tui.formatting import arg_hint as _arg_hint
        from alpi.session import ToolLog as _ToolLog
        started = _t.time()
        if emit_events:
            sys.stdout.write(json.dumps({
                "kind": "tool_start",
                "name": "peer",
                "preview": _arg_hint("peer", {
                    "peer_id": parsed.peer_id, "prompt": parsed.prompt,
                }),
            }) + "\n")
            sys.stdout.flush()
        result = _aio.run(alp_mention.execute(h, parsed.peer_id, parsed.prompt))
        reply = result.reply if result.ok else f"[error] {result.error}"
        if emit_events:
            sys.stdout.write(json.dumps({
                "kind": "tool_end", "name": "peer", "ok": result.ok,
            }) + "\n")
            sys.stdout.flush()
        engine.session.messages.append({"role": "user", "content": user_text})
        engine.session.messages.append({"role": "assistant", "content": reply})
        engine.session.log_turn(
            user=user_text, assistant=reply,
            tools=[_ToolLog(
                at=started, name="peer",
                args={"peer_id": parsed.peer_id, "prompt": parsed.prompt},
                result=reply, ok=result.ok, duration_s=_t.time() - started,
            )],
            started_at=started,
        )
        if persist:
            try:
                engine.save_session()
            except Exception:  # noqa: BLE001
                pass
        if emit_events:
            sys.stdout.write(json.dumps({"kind": "reply", "text": reply}) + "\n")
        else:
            sys.stdout.write(reply + "\n")
        sys.stdout.flush()
        return

    parts: list[str] = []
    produced: list[dict] = []

    from alpi.tui.formatting import arg_hint

    def _emit_event_line(ev: AgentEvent) -> None:
        if ev.kind == "tool_start":
            payload = {
                "kind": "tool_start",
                "name": ev.name,
                "preview": arg_hint(ev.name, ev.args or {}),
            }
            if ev.name == "notify":
                args = ev.args or {}
                payload["args"] = {
                    k: args[k] for k in (
                        "text", "title", "type", "channel",
                    ) if k in args
                }
        elif ev.kind == "tool_end":
            payload = {"kind": "tool_end", "name": ev.name, "ok": ev.ok}
        elif ev.kind == "tool_state":
            # Mid-tool progress = sign-of-life for the daemon idle-turn timeout (a long tool ≠ a hung one).
            payload = {"kind": "tool_state", "name": ev.name}
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
        if ev.kind == "assistant_done" and ev.final:
            if ev.attachments:
                produced.extend(ev.attachments)
            if ev.text.strip():
                parts.append(ev.text)
        elif ev.kind == "error" and not emit_events:
            parts.append(f"[error] {ev.text}")

    import signal as _signal

    def _on_sigint(_signum, _frame):
        engine.request_interrupt("cli-sigint")

    prev_handler = _signal.signal(_signal.SIGINT, _on_sigint)
    from alpi.tools import _clarification as _clar
    from alpi.tui.clarification_inline import inline_handler as _inline_clarify
    prev_clarify = _clar.get_handler()
    _clar.set_handler(_inline_clarify)
    try:
        extra = {"attachments": attachments} if attachments else {}
        engine.run_turn(user_text, emit=sink, persist_inflight=persist, **extra)
    finally:
        _signal.signal(_signal.SIGINT, prev_handler)
        _clar.set_handler(prev_clarify)
    if persist:
        try:
            engine.save_session()
        except Exception:  # noqa: BLE001
            pass

    final = "\n\n".join(parts).strip()
    if emit_events:
        import json as _json

        payload = {"kind": "reply", "text": final}
        if produced:
            payload["attachments"] = produced
        sys.stdout.write(_json.dumps(payload, ensure_ascii=False) + "\n")
    else:
        from alpi.attachments import render_output_attachments
        listing = render_output_attachments(produced)
        out = "\n\n".join(x for x in (final, listing) if x)
        sys.stdout.write(out + "\n")
    sys.stdout.flush()


class _OrderedGroup(click.Group):
    """List subcommands in _ORDER (user-frequency) instead of Click's default alphabetical."""

    _ORDER = [
        "chat",
        "setup",
        "doctor",
        "audit",
        "update",
        "diff",
        "logs",
        "profile",
        "peers",
        "alp",
        "email",
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
    try:
        h = home.get_home(profile)
    except home.InvalidProfileName as e:
        raise click.BadParameter(str(e), param_hint="-p / --profile")
    ctx.obj["home"] = h
    ctx.obj["profile"] = profile or "default"
    ctx.obj["continue_last"] = continue_last
    # ALPI_PROFILE env var is the source of truth for downstream get_home() calls; without it tools silently write to the default profile.
    if profile:
        os.environ["ALPI_PROFILE"] = profile
    if ctx.invoked_subcommand != "update":
        from alpi import updater
        updater.trigger_background_check_if_enabled()
    _bootstrap(h)
    if ctx.invoked_subcommand is None:
        resume = continue_last
        if not resume:
            try:
                cfg = config.load(h)
                resume = bool((cfg.tui or {}).get("auto_resume"))
            except Exception:  # noqa: BLE001
                pass
        _run_chat(h, continue_last=resume)


@main.command("ctx")
@click.argument("model")
@click.pass_context
def cmd_ctx(ctx: click.Context, model: str) -> None:
    """Print the context window (tokens) for model under this profile."""
    from alpi import ctx_window

    h: Path = ctx.obj["home"]
    cfg = config.load(h)
    click.echo(ctx_window.resolve(h, cfg, model))


@main.command()
@click.option(
    "--once", "input_text", default=None, help="Run one turn and print the reply to stdout."
)
@click.option("--emit-events", is_flag=True, default=False, hidden=True)
@click.option("--no-save", is_flag=True, default=False, hidden=True)
@click.option(
    "-c", "--continue", "continue_last", is_flag=True, help="Resume from the last session."
)
@click.option(
    "--attach", "attach", multiple=True, type=click.Path(exists=True, dir_okay=False),
    help="Attach a file to the --once turn (repeatable). Images/PDFs/text the model can read.",
)
@click.option(
    "--session", "session", default=None,
    help="With --once, resume a specific session id (robust under concurrency; --continue resumes the last).",
)
@click.pass_context
def chat(
    ctx: click.Context,
    input_text: str | None,
    emit_events: bool,
    no_save: bool,
    continue_last: bool,
    session: str | None,
    attach: tuple[str, ...],
) -> None:
    """Launch the TUI, or run one turn with ``--once "text"``."""
    h: Path = ctx.obj["home"]
    resume_last = continue_last or bool(ctx.obj.get("continue_last"))
    if input_text is not None or attach:
        _run_once(
            h,
            input_text or "",
            emit_events=emit_events,
            persist=not no_save,
            attach=attach,
            session_id=session,
            continue_last=resume_last,
        )
    else:
        _run_chat(h, continue_last=resume_last)


@main.command("diff")
@click.option(
    "--since",
    default="24h",
    show_default=True,
    help="Cutoff: ``Nh``/``Nd``/``Nm``/``Nw`` or an ISO-8601 timestamp.",
)
@click.option("--json", "as_json", is_flag=True, help="Emit the raw report dict as JSON.")
@click.pass_context
def cmd_diff(ctx: click.Context, since: str, as_json: bool) -> None:
    """List what changed in this profile since the cutoff (mtime-driven, side-effect free)."""
    from alpi import diff as diff_mod

    h: Path = ctx.obj["home"]
    profile: str = ctx.obj["profile"]
    try:
        cutoff = diff_mod.parse_since(since)
    except ValueError as e:
        raise click.UsageError(str(e)) from None
    report = diff_mod.compute(h, cutoff)
    if as_json:
        import json as _json
        click.echo(_json.dumps(report, indent=2, sort_keys=True))
        return
    click.echo(diff_mod.render(report, profile=profile))


@main.command("backup")
@click.option(
    "--out", "out_path", type=click.Path(dir_okay=False, path_type=Path), default=None,
    help="Output file. Defaults to ``./alpi.<YYYY-MM-DD>.alpi-backup``.",
)
@click.option(
    "--passphrase-stdin", is_flag=True, default=False,
    help="Read the passphrase from stdin instead of prompting (one line, no echo).",
)
@click.option(
    "--force", is_flag=True, default=False,
    help="Overwrite ``--out`` if it already exists.",
)
@click.pass_context
def cmd_backup(
    ctx: click.Context, out_path: Path | None, passphrase_stdin: bool, force: bool,
) -> None:
    """Encrypt the whole alpi home into a single passphrase-protected file (Scrypt-derived key, whole-home)."""
    from alpi import backup as backup_mod

    root: Path = home.alpi_root()
    if out_path is None:
        out_path = Path.cwd() / backup_mod.default_filename()
    if out_path.exists():
        if not force:
            raise click.UsageError(
                f"{out_path} already exists; pass --force to overwrite."
            )
        out_path.unlink()

    try:
        pv = backup_mod.preview(root)
    except backup_mod.BackupError as e:
        raise click.ClickException(str(e)) from None
    click.echo(f"preview:  {pv.home}")
    click.echo(f"  files:    {pv.total_files}")
    click.echo(f"  size:     {home.format_bytes(pv.total_size)}")
    all_entries = pv.default_entries + pv.profile_entries
    name_width = max((len(e.name) for e in all_entries), default=0)
    if pv.default_entries:
        click.echo("  default:")
        for e in pv.default_entries:
            click.echo(
                f"    {e.name:<{name_width}}  "
                f"{home.format_bytes(e.size):>9}  "
                f"({e.file_count} files)"
            )
    if pv.profile_entries:
        click.echo(f"  profiles ({len(pv.profile_entries)}):")
        for e in pv.profile_entries:
            click.echo(
                f"    {e.name:<{name_width}}  "
                f"{home.format_bytes(e.size):>9}  "
                f"({e.file_count} files)"
            )
    if pv.largest_files:
        click.echo("  largest files:")
        fwidth = max(len(f.path) for f in pv.largest_files)
        for f in pv.largest_files:
            click.echo(
                f"    {f.path:<{fwidth}}  {home.format_bytes(f.size):>9}"
            )

    if passphrase_stdin:
        passphrase = sys.stdin.readline().rstrip("\n")
    else:
        passphrase = click.prompt(
            "Passphrase", hide_input=True, confirmation_prompt=True,
        )
    if not passphrase:
        raise click.UsageError("passphrase must not be empty")

    try:
        info = backup_mod.create_backup(root, out_path, passphrase)
    except backup_mod.BackupError as e:
        raise click.ClickException(str(e)) from None

    click.echo(
        f"backup: {info.path}\n"
        f"  files:      {info.file_count}\n"
        f"  plaintext:  {home.format_bytes(info.plaintext_bytes)}\n"
        f"  archive:    {home.format_bytes(info.archive_bytes)}"
    )


@main.command("restore")
@click.argument("archive", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--passphrase-stdin", is_flag=True, default=False,
    help="Read the passphrase from stdin instead of prompting.",
)
@click.option(
    "--force", is_flag=True, default=False,
    help="Wipe the target alpi home before extracting (only after the archive's AEAD tag verifies).",
)
@click.pass_context
def cmd_restore(
    ctx: click.Context, archive: Path, passphrase_stdin: bool, force: bool,
) -> None:
    """Decrypt an alpi backup into ``~/.alpi/``; refuses to overwrite a non-empty home without --force."""
    from alpi import backup as backup_mod

    root: Path = home.alpi_root()
    try:
        header = backup_mod.inspect(archive)
    except backup_mod.BackupError as e:
        raise click.ClickException(str(e)) from None

    click.echo(
        f"archive:  {archive}\n"
        f"  created:  {header.get('created_at', '?')}\n"
        f"  files:    {header.get('file_count', '?')}\n"
        f"target:   {root}"
    )

    if passphrase_stdin:
        passphrase = sys.stdin.readline().rstrip("\n")
    else:
        passphrase = click.prompt("Passphrase", hide_input=True)
    if not passphrase:
        raise click.UsageError("passphrase must not be empty")

    try:
        info = backup_mod.restore_backup(archive, root, passphrase, force=force)
    except backup_mod.BackupError as e:
        raise click.ClickException(str(e)) from None

    click.echo(
        f"restored: {info.target}\n"
        f"  files:    {info.file_count}\n"
        f"  created:  {info.created_at}"
    )


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
def daemon() -> None:
    """The alpi daemon — one supervisor for every profile under ``~/.alpi``."""


def _root() -> Path:
    """Daemon commands always operate on the machine root."""
    return home._ROOT


@daemon.command("start")
def daemon_start() -> None:
    """Run the daemon in the foreground."""
    from alpi import service as svc

    root = _root()
    _bootstrap(root)
    if svc.daemon_running_pid(root) is not None:
        raise click.ClickException(
            f"daemon already running (pid {svc.daemon_running_pid(root)}). "
            "Use `alpi daemon stop` first.",
        )
    svc.serve_all(root)


@daemon.command("stop")
def daemon_stop() -> None:
    """SIGTERM the daemon."""
    from alpi import service as svc

    if not svc.stop_daemon(_root()):
        click.echo("daemon is not running")
        return
    click.echo("daemon stopped")


@daemon.command("restart")
def daemon_restart() -> None:
    """Stop the daemon and let the supervisor respawn it."""
    from alpi import service as svc
    import subprocess
    import shutil

    root = _root()
    if svc.daemon_running_pid(root) is None:
        click.echo("daemon is not running")
        return
    svc.stop_daemon(root)
    if svc.daemon_installed():
        click.echo("daemon stopped — supervisor will respawn it shortly")
        return
    alpi_bin = shutil.which("alpi") or "alpi"
    subprocess.Popen(
        [alpi_bin, "daemon", "start"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    click.echo("daemon restarting (on-demand)")


@daemon.command("status")
def daemon_status_cmd() -> None:
    """Print PID, uptime, and per-profile service state."""
    from alpi import service as svc

    info = svc.daemon_status(_root())
    if info["running"]:
        up = info.get("uptime_seconds")
        up_s = f"  · uptime {up}s" if up is not None else ""
        click.echo(f"running  · pid {info['pid']}{up_s}")
    else:
        click.echo("not running")
    backend = info["installed_via"]
    click.echo(f"installed via {backend}" if backend else "not installed")
    profiles = info["profiles"]
    click.echo(f"profiles: {len(profiles)}")
    for name, subs in profiles.items():
        on = [k for k, v in subs.items() if v]
        line = ", ".join(on) if on else "(none)"
        click.echo(f"  {name}: {line}")


@daemon.command("install")
def daemon_install() -> None:
    """Register the daemon with launchd / systemd."""
    from alpi import service as svc

    kind = svc.install_daemon(_root())
    click.echo(f"daemon installed via {kind}")


@daemon.command("uninstall")
def daemon_uninstall() -> None:
    """Unregister the daemon from launchd / systemd."""
    from alpi import service as svc

    if not svc.daemon_installed():
        click.echo("daemon not installed")
        return
    kind = svc.uninstall_daemon()
    click.echo(f"daemon uninstalled ({kind})")


@main.group()
def schedule() -> None:
    """Schedule operations."""


@schedule.command("list")
@click.option("--json", "as_json", is_flag=True, help="Emit machine-readable JSON.")
@click.pass_context
def schedule_list(ctx: click.Context, as_json: bool) -> None:
    """List this profile's scheduled jobs with status and next fire time."""
    import json as json_mod

    from alpi.scheduler import run as scheduler_run
    from alpi.scheduler import jobs_store

    h: Path = ctx.obj["home"]
    _bootstrap(h)
    try:
        jobs = jobs_store.read(h)
    except jobs_store.CorruptJobsFile as e:
        click.echo(f"jobs.json corrupt: {e}", err=True)
        ctx.exit(1)

    def _fire_state(job: dict) -> tuple[str, "object"]:
        # Delegate to the daemon's own semantics so console and scheduler never disagree.
        if job.get("paused"):
            return "paused", None
        if scheduler_run.is_due(job, home=h):
            return "due", scheduler_run.next_fire(job, home=h)
        nxt = scheduler_run.next_fire(job, home=h)
        if nxt is None:
            if job.get("kind") == "inactivity":
                return "idle-gated", None
            return "none", None
        return "scheduled", nxt

    def _next_fire(job: dict) -> str:
        status, nxt = _fire_state(job)
        if status == "paused":
            return "paused"
        if status == "due":
            return "due now"
        if status == "idle-gated":
            return f"after {job.get('after_hours')}h idle"
        if nxt is None:
            return "—"
        return nxt.strftime("%Y-%m-%d %H:%M")

    if as_json:
        rows = []
        for j in jobs:
            status, nxt = _fire_state(j)
            rows.append({
                **j,
                "status": status,
                "next_fire": nxt.isoformat() if nxt is not None else None,
            })
        click.echo(json_mod.dumps(rows, indent=2))
        return
    if not jobs:
        click.echo("no scheduled jobs — add one via chat (`schedule` tool) or the apps")
        return
    for j in jobs:
        jid = j.get("id", "?")
        kind = j.get("kind", "cron")
        when = j.get("expression") or j.get("run_at") or f"{j.get('after_hours')}h idle"
        title = j.get("title") or (j.get("prompt") or "")[:60].replace("\n", " ")
        flags = []
        if j.get("paused"):
            flags.append("paused")
        if j.get("notify"):
            flags.append("notify")
        if j.get("tier"):
            flags.append(f"tier:{j['tier']}")
        if j.get("no_agent"):
            flags.append("no_agent")
        last = j.get("last_run_status") or "never ran"
        click.echo(f"{jid}  [{kind}] {when}  → next {_next_fire(j)}")
        click.echo(f"        {title}")
        click.echo(f"        last: {last}{' · ' + ', '.join(flags) if flags else ''}")


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
    """Fire one specific job ad-hoc; bypasses schedule checks but does not delete ``once`` jobs."""
    from alpi.scheduler.run import fire_by_id

    h: Path = ctx.obj["home"]
    _bootstrap(h)
    ok, msg = fire_by_id(h, job_id)
    click.echo(f"{'OK' if ok else 'FAIL'}  {msg}")
    if not ok:
        ctx.exit(1)


@main.group("outputs")
def outputs_group() -> None:
    """Browse the outputs inbox (notifications, cron replies, produced files)."""


@outputs_group.command("list")
@click.option("-n", "limit", default=20, show_default=True, help="Max rows.")
@click.option("--unread", is_flag=True, help="Only unread outputs.")
@click.option("--all-profiles", "all_profiles", is_flag=True, help="Merge every profile's inbox, newest first, tagged by profile.")
@click.option("--json", "as_json", is_flag=True, help="Emit machine-readable JSON.")
@click.pass_context
def outputs_list(ctx: click.Context, limit: int, unread: bool, all_profiles: bool, as_json: bool) -> None:
    """List recent outputs, newest first."""
    import json as json_mod
    from datetime import datetime

    from alpi import outputs as outputs_mod

    h: Path = ctx.obj["home"]
    _bootstrap(h)
    status = "unread" if unread else None
    if all_profiles:
        from alpi import home as home_mod

        root = home_mod.alpi_root()
        rows = []
        for name in home_mod.list_profiles(root):
            profile_home = root if name == "default" else root / "profiles" / name
            for it in outputs_mod.list_outputs(profile_home, status=status, limit=limit):
                if not it.get("profile"):
                    it["profile"] = name
                rows.append(it)
        rows.sort(key=lambda it: float(it.get("created_at") or 0.0), reverse=True)
        rows = rows[:limit]
    else:
        rows = outputs_mod.list_outputs(h, status=status, limit=limit)
    if as_json:
        click.echo(json_mod.dumps(rows, indent=2))
        return
    if not rows:
        click.echo("no outputs" + (" unread" if unread else ""))
        return
    for it in rows:
        dot = "●" if it.get("status") == "unread" else "○"
        ts = datetime.fromtimestamp(float(it.get("created_at") or 0)).strftime("%m-%d %H:%M")
        prof = f" @{it.get('profile')}" if all_profiles else ""
        title = it.get("title") or (it.get("body") or "")[:60].replace("\n", " ")
        click.echo(f"{dot} {ts}  [{it.get('type', 'info')}] {it.get('id')}{prof}  {title}")


@outputs_group.command("show")
@click.argument("output_id")
@click.pass_context
def outputs_show(ctx: click.Context, output_id: str) -> None:
    """Print one output in full and mark it read."""
    from datetime import datetime

    from alpi import outputs as outputs_mod

    h: Path = ctx.obj["home"]
    _bootstrap(h)
    it = outputs_mod.read(h, output_id)
    if it is None:
        click.echo(f"no output with id {output_id!r}", err=True)
        ctx.exit(1)
    outputs_mod.mark_read(h, output_id)
    ts = datetime.fromtimestamp(float(it.get("created_at") or 0)).strftime("%Y-%m-%d %H:%M")
    click.echo(f"{it.get('title') or '(untitled)'}")
    click.echo(f"{ts} · {it.get('type', 'info')} · {it.get('id')}")
    click.echo("")
    click.echo(it.get("body") or "")


@outputs_group.command("read-all")
@click.pass_context
def outputs_read_all(ctx: click.Context) -> None:
    """Mark every unread output as read."""
    from alpi import outputs as outputs_mod

    h: Path = ctx.obj["home"]
    _bootstrap(h)
    touched = outputs_mod.mark_all_read(h)
    click.echo(f"marked {touched} output(s) read")


@main.group("email")
def email_group() -> None:
    """Inspect the profile's email accounts (by id; any mix of IMAP / Gmail)."""


@email_group.command("probe")
@click.argument("account_id")
@click.pass_context
def email_probe(ctx: click.Context, account_id: str) -> None:
    """Probe an email account by id and print JSON ``{status, reason?}``."""
    import json

    from alpi.mail import accounts as accounts_mod

    h: Path = ctx.obj["home"]
    account = accounts_mod.get_account(h, account_id)
    if account is None:
        click.echo(json.dumps({"status": "error", "reason": f"unknown account {account_id!r}"}))
        ctx.exit(1)
    from alpi.host.probes import _email_probe_blocking
    click.echo(json.dumps(_email_probe_blocking(h, account_id, account)))


@email_group.command("remove")
@click.argument("account_id")
@click.option("--yes", is_flag=True, default=False,
              help="Skip the confirmation prompt.")
@click.pass_context
def email_remove(ctx: click.Context, account_id: str, yes: bool) -> None:
    """Drop config + secret (and Gmail token file) for one email account."""
    from alpi.mail import accounts as accounts_mod

    h: Path = ctx.obj["home"]
    if not yes:
        if not click.confirm(
            f"Remove {account_id} email account? You can re-add later.",
            default=False,
        ):
            click.echo("aborted")
            return
    existed = accounts_mod.remove_account(h, account_id)
    if not existed:
        click.echo(f"no email account {account_id!r}")
        return
    click.echo(f"removed {account_id} email account · restart daemon to apply")


@main.group()
def mcp() -> None:
    """Manage MCP (Model Context Protocol) servers for this profile."""


@mcp.command("add")
@click.argument("name")
@click.option("--command", "command", required=True,
              help="Executable that spawns the MCP server (e.g. npx, uvx).")
@click.option("--args", "args_str", default="",
              help="Space-separated arguments. Use shell-style quoting.")
@click.option("--env", "env_pairs", multiple=True,
              help="KEY=VALUE env var. Repeat for multiple.")
@click.pass_context
def mcp_add(
    ctx: click.Context, name: str, command: str,
    args_str: str, env_pairs: tuple[str, ...],
) -> None:
    """Add (or replace) an MCP server entry."""
    import shlex

    name = name.strip()
    if ":" in name or "/" in name or name.startswith("."):
        raise click.ClickException(f"invalid name: {name!r}")
    if not command.strip():
        raise click.ClickException("--command required")
    args = shlex.split(args_str) if args_str else []
    env: dict[str, str] = {}
    for pair in env_pairs:
        if "=" not in pair:
            raise click.ClickException(
                f"invalid --env entry {pair!r} (expected KEY=VALUE)"
            )
        k, v = pair.split("=", 1)
        env[k.strip()] = v.strip()

    h: Path = ctx.obj["home"]
    cfg = config.load(h)
    cfg.raw.setdefault("mcp", {}).setdefault("servers", {})[name] = {
        "command": command.strip(),
        "args": args,
        "env": env,
    }
    config.save(cfg)
    click.echo(f"added MCP {name!r}")


@mcp.command("remove")
@click.argument("name")
@click.pass_context
def mcp_remove(ctx: click.Context, name: str) -> None:
    """Drop an MCP server entry."""
    h: Path = ctx.obj["home"]
    cfg = config.load(h)
    servers = cfg.raw.setdefault("mcp", {}).setdefault("servers", {})
    if name not in servers:
        raise click.ClickException(f"no MCP named {name!r}")
    servers.pop(name)
    config.save(cfg)
    click.echo(f"removed MCP {name!r}")


@main.group()
def voice() -> None:
    """Configure TTS voice for this profile."""


@voice.command("set-voice")
@click.argument("voice_id")
@click.pass_context
def voice_set_voice(ctx: click.Context, voice_id: str) -> None:
    """Set the TTS voice id (e.g. ``en-US-AriaNeural``)."""
    h: Path = ctx.obj["home"]
    cfg = config.load(h)
    cfg.tools.tts.voice = voice_id.strip()
    config.save(cfg)
    click.echo(f"voice set to {cfg.tools.tts.voice}")


_VOICE_TEST_PHRASES = {
    "en": "Hello, I'm Alpi.",
    "es": "Hola, soy Alpi.",
    "fr": "Bonjour, je suis Alpi.",
    "de": "Hallo, ich bin Alpi.",
    "it": "Ciao, sono Alpi.",
    "pt": "Olá, sou Alpi.",
}


def _voice_player_cmd() -> list[str] | None:
    import platform
    import shutil
    system = platform.system()
    if system == "Darwin" and shutil.which("afplay"):
        return ["afplay"]
    if system == "Linux":
        for name in ("paplay", "aplay", "ffplay"):
            if shutil.which(name):
                if name == "ffplay":
                    return ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet"]
                return [name]
    if system == "Windows":
        return [
            "powershell", "-NoProfile", "-Command",
            "(New-Object Media.SoundPlayer $args[0]).PlaySync()",
        ]
    return None


@voice.command("test")
@click.option("--voice", "voice_override", default=None,
              help="Override the configured voice id for this preview.")
@click.pass_context
def voice_test(ctx: click.Context, voice_override: str | None) -> None:
    """Synthesize a short greeting in the voice's locale; play it if a local player is available, otherwise print the saved file path."""
    import asyncio
    import subprocess as _sp
    import tempfile
    from alpi.tools.tts import _synthesize

    h: Path = ctx.obj["home"]
    cfg = config.load(h)
    voice_id = (voice_override or cfg.tools.tts.voice or "en-US-AriaNeural").strip()
    lang = voice_id.split("-", 1)[0].lower() if "-" in voice_id else "en"
    phrase = _VOICE_TEST_PHRASES.get(lang, _VOICE_TEST_PHRASES["en"])

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        out = Path(tmp.name)
    asyncio.run(_synthesize(phrase, voice_id, out))

    cmd = _voice_player_cmd()
    if cmd is None:
        click.echo(f"saved: {out}")
        return
    reason = ""
    try:
        proc = _sp.run([*cmd, str(out)], capture_output=True, timeout=30)
        if proc.returncode != 0:
            reason = f"exit {proc.returncode}"
    except _sp.TimeoutExpired:
        reason = "timed out"
    except FileNotFoundError as e:
        reason = f"player missing: {e}"
    if not reason:
        try:
            out.unlink()
        except OSError:
            pass
        click.echo(f"played: {phrase}")
        return
    click.echo(f"saved: {out} (player failed: {reason})")


@main.group()
def sandbox() -> None:
    """Configure the terminal sandbox for this profile."""


@sandbox.command("set")
@click.argument("state", type=click.Choice(["on", "off"]))
@click.pass_context
def sandbox_set(ctx: click.Context, state: str) -> None:
    """Toggle the terminal sandbox. Disabling also resets allow-network."""
    h: Path = ctx.obj["home"]
    cfg = config.load(h)
    if state == "on":
        cfg.tools.terminal.sandbox = True
    else:
        cfg.tools.terminal.sandbox = False
        cfg.tools.terminal.allow_network = False
    config.save(cfg)
    click.echo(f"sandbox {state}")


@sandbox.command("network")
@click.argument("state", type=click.Choice(["on", "off"]))
@click.pass_context
def sandbox_network(ctx: click.Context, state: str) -> None:
    """Allow / deny network for sandboxed shell commands."""
    h: Path = ctx.obj["home"]
    cfg = config.load(h)
    if not cfg.tools.terminal.sandbox:
        raise click.ClickException(
            "sandbox is off — enable it first with `alpi sandbox set on`"
        )
    cfg.tools.terminal.allow_network = state == "on"
    config.save(cfg)
    click.echo(f"sandbox network {state}")


@main.group()
def providers() -> None:
    """Manage provider credentials (.env) and Ollama connections."""


@providers.command("set-key")
@click.argument("key")
@click.argument("value")
@click.pass_context
def providers_set_key(ctx: click.Context, key: str, value: str) -> None:
    """Write or replace ``KEY=VALUE`` in this profile's .env (mode 0600)."""
    from alpi.model_selector import _append_env

    h: Path = ctx.obj["home"]
    cfg = config.load(h)
    _append_env(cfg.env_path, key.strip(), value)
    click.echo(f"set {key} in {cfg.env_path}")


@providers.command("unset-key")
@click.argument("key")
@click.pass_context
def providers_unset_key(ctx: click.Context, key: str) -> None:
    """Remove ``KEY`` from this profile's .env."""
    from alpi.model_selector import unset_provider_key

    h: Path = ctx.obj["home"]
    cfg = config.load(h)
    if unset_provider_key(cfg, key.strip()):
        click.echo(f"unset {key}; cleared active model (pointed at this provider)")
    else:
        click.echo(f"unset {key}")


@providers.command("add-ollama")
@click.argument("name")
@click.argument("url")
@click.pass_context
def providers_add_ollama(ctx: click.Context, name: str, url: str) -> None:
    """Pin a new Ollama server under ``NAME`` at ``URL``."""
    h: Path = ctx.obj["home"]
    cfg = config.load(h)
    name = name.strip()
    url = url.strip().rstrip("/")
    if not name:
        raise click.ClickException("name required")
    if not url:
        raise click.ClickException("url required")
    taken = {e.get("name") for e in cfg.providers.get("ollama", []) or []}
    if name in taken:
        raise click.ClickException(f"name {name!r} already exists")
    cfg.providers.setdefault("ollama", []).append({"name": name, "url": url})
    config.save(cfg)
    click.echo(f"added ollama {name!r} -> {url}")


@providers.command("remove-ollama")
@click.argument("name")
@click.pass_context
def providers_remove_ollama(ctx: click.Context, name: str) -> None:
    """Remove the Ollama server registered under ``NAME``."""
    h: Path = ctx.obj["home"]
    cfg = config.load(h)
    name = name.strip()
    items = cfg.providers.get("ollama", []) or []
    remaining = [e for e in items if e.get("name") != name]
    if len(remaining) == len(items):
        raise click.ClickException(f"no ollama server named {name!r}")
    cfg.providers["ollama"] = remaining
    if cfg.model.startswith(f"{name}/"):
        cfg.model = ""
    config.save(cfg)
    click.echo(f"removed ollama {name!r}")


@providers.command("add-openrouter-model")
@click.argument("model")
@click.pass_context
def providers_add_openrouter_model(ctx: click.Context, model: str) -> None:
    """Add MODEL (suffix only) to providers.openrouter.models, most-recent-first."""
    h: Path = ctx.obj["home"]
    cfg = config.load(h)
    suffix = model.strip()
    if suffix.startswith("openrouter/"):
        suffix = suffix.split("/", 1)[1]
    if not suffix:
        raise click.ClickException("model required")
    or_cfg = cfg.providers.setdefault("openrouter", {})
    models = or_cfg.setdefault("models", [])
    if suffix in models:
        models.remove(suffix)
    models.insert(0, suffix)
    config.save(cfg)
    click.echo(f"added openrouter model {suffix!r}")


@providers.command("remove-openrouter-model")
@click.argument("model")
@click.pass_context
def providers_remove_openrouter_model(ctx: click.Context, model: str) -> None:
    """Drop ``MODEL`` from ``providers.openrouter.models``."""
    h: Path = ctx.obj["home"]
    cfg = config.load(h)
    suffix = model.strip()
    if suffix.startswith("openrouter/"):
        suffix = suffix.split("/", 1)[1]
    or_cfg = cfg.providers.get("openrouter") or {}
    models = list(or_cfg.get("models") or [])
    if suffix not in models:
        raise click.ClickException(f"no openrouter model {suffix!r}")
    models.remove(suffix)
    or_cfg["models"] = models
    cfg.providers["openrouter"] = or_cfg
    config.save(cfg)
    click.echo(f"removed openrouter model {suffix!r}")


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


@main.group()
def curator() -> None:
    """Review and apply skill-library cleanup. See ``alpi curator review|apply --help``."""


@curator.command("review")
@click.option(
    "--window-days",
    type=float,
    default=None,
    help="Treat a skill as stale when its last_seen is older than this many days (defaults to skills_usage.STALE_DAYS = 30).",
)
@click.option(
    "--profile",
    "profile_name",
    default=None,
    help="Profile to inspect (defaults to the active alpi home).",
)
@click.pass_context
def curator_review(
    ctx: click.Context,
    window_days: float | None,
    profile_name: str | None,
) -> None:
    """Inspect the skills library and write a markdown + json report under ``<home>/logs/curator/<UTC-timestamp>/``. The curator never mutates skills."""
    from alpi import curator as _curator
    if profile_name:
        h = home.home_for(profile_name)
    else:
        h = ctx.obj["home"]
    findings = _curator.review(h, window_days=window_days)
    out_dir = _curator.write_report(h, findings)
    s = findings["summary"]
    click.echo(f"report: {out_dir / 'report.md'}")
    click.echo(
        f"stale={s['stale']} cold={s['cold']} clusters={s['prefix_clusters']} "
        f"(of {s['skills_on_disk']} skills, {s['skills_with_usage']} with telemetry)"
    )


@curator.command("list")
@click.option("--profile", "profile_name", default=None,
              help="Profile to inspect (defaults to the active alpi home).")
@click.pass_context
def curator_list(ctx: click.Context, profile_name: str | None) -> None:
    """List past curator reports, newest first."""
    from alpi import curator as _curator
    if profile_name:
        h = home.home_for(profile_name)
    else:
        h = ctx.obj["home"]
    reports = _curator.list_reports(h)
    if not reports:
        click.echo("(no curator reports yet)")
        return
    for p in reports:
        click.echo(str(p / "report.md"))


@curator.command("apply")
@click.option("--report", "report_id", default=None,
              help="Report dir name to apply (defaults to the latest).")
@click.option("--yes", "-y", is_flag=True, help="Apply without the confirmation prompt.")
@click.option("--dry-run", is_flag=True, help="Show what would be archived without moving anything.")
@click.option("--profile", "profile_name", default=None,
              help="Profile to inspect (defaults to the active alpi home).")
@click.pass_context
def curator_apply(
    ctx: click.Context,
    report_id: str | None,
    yes: bool,
    dry_run: bool,
    profile_name: str | None,
) -> None:
    """Archive the stale/cold skills a curator report flagged, after preview + confirm."""
    from alpi import curator_apply as _apply
    h = home.home_for(profile_name) if profile_name else ctx.obj["home"]
    try:
        report_dir, report = _apply.load_report(h, report_id)
    except FileNotFoundError as e:
        raise click.ClickException(str(e))
    actions = _apply.archive_actions(report)
    if not actions:
        click.echo("nothing to apply (no archive actions in report)")
        return
    click.echo(f"report: {report_dir.name}")
    for a in actions:
        click.echo(f"  archive {a['skill']} ({a.get('category', '?')}) — {a.get('reason', '')}")
    if dry_run:
        result = _apply.apply_report(h, report, dry_run=True)
        c = result["counts"]
        click.echo(f"dry-run: would archive {c.get('would-archive', 0)}, skip {c.get('skipped', 0)}")
        return
    if not yes:
        click.confirm(f"Archive {len(actions)} skill(s) to skills/.archive/?", abort=True)
    result = _apply.apply_report(h, report, dry_run=False)
    out_path = _apply.write_apply_report(report_dir, result)
    c = result["counts"]
    click.echo(f"archived={c.get('archived', 0)} skipped={c.get('skipped', 0)} → {out_path}")


@main.command("doctor")
@click.pass_context
def doctor_cmd(ctx: click.Context) -> None:
    """Read-only health check of the current profile."""
    from alpi import doctor, ui

    h: Path = ctx.obj["home"]
    profile: str = ctx.obj.get("profile") or "default"
    checks = doctor.run_and_render(ui._console, h, profile, __version__)
    ctx.exit(doctor.exit_code(checks))


@main.command("audit")
@click.option("--offline", is_flag=True, help="Skip network checks (OSV CVE lookup).")
@click.pass_context
def audit_cmd(ctx: click.Context, offline: bool) -> None:
    """Read-only security posture scan of the whole install (every profile)."""
    from alpi import audit, home, ui

    root = home.alpi_root()
    checks = audit.run_all(root, offline=offline)
    audit.render(ui._console, checks, __version__)
    ctx.exit(audit.exit_code(checks))


@main.command("logs")
@click.option(
    "--source",
    type=click.Choice(["service", "schedule", "agent", "approval"]),
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
    """Show the tail of every log this profile writes, merged by timestamp.

    `--source service` always reads the daemon-wide root log
    `~/.alpi/logs/service.log` regardless of the active profile —
    it is one file per installation, not one per profile.
    """
    from alpi import home as home_mod, logs as logs_mod, ui

    h: Path = ctx.obj["home"] if source != "service" else home_mod.alpi_root()
    lines = logs_mod.tail(h, source, tail_n)
    if not lines and not follow:
        ui._console.print("[dim]no logs yet — run `alpi setup` to get started.[/dim]")
        return
    logs_mod.print_tail(ui._console, lines)
    if follow:
        logs_mod.follow(h, source, ui._console)


@main.command("update")
@click.option(
    "--check", "check_only", is_flag=True,
    help="Check for a new version; don't install.",
)
@click.option(
    "--yes", "-y", "assume_yes", is_flag=True,
    help="Skip the confirmation prompt before installing.",
)
@click.pass_context
def update_cmd(ctx: click.Context, check_only: bool, assume_yes: bool) -> None:
    """Check PyPI for a newer alpi-agent and install it."""
    from alpi import updater
    rc = updater.do_update(check_only=check_only, yes=assume_yes)
    ctx.exit(rc)




@main.command("setup")
@click.pass_context
def setup_cmd(ctx: click.Context) -> None:
    """Interactive setup — model, email, MCPs."""
    from alpi import ui

    h: Path = ctx.obj["home"]
    _bootstrap(h)
    _ensure_daemon_installed(home._ROOT)

    profile_name = ctx.obj.get("profile") or "default"
    while True:
        cfg = config.load(h)
        items: list = [
            ui.Heading("Agent"),
            ("Model / Provider", "model", cfg.model or "(not set)"),
            ("Routing tiers", "tiers", _tiers_status(cfg)),
            ("Voice", "voice", _voice_status(cfg)),
            ("MCPs", "mcps", _mcp_status(h)),
            ("Emails", "email", _email_accounts_status(h)),

            ui.Heading("Boundaries"),
            ("Workspace", "workspace", _workspace_status(cfg)),
            ("Sandbox", "sandbox", _sandbox_status(cfg)),
            ("Budget", "budget", _budget_status(cfg)),

            ui.Heading("ALP (Alpi Link Protocol)"),
            ("Identity", "identity", _identity_status(cfg)),
            ("Peers", "peers", _peers_status(h)),
            ("Workgroups", "workgroups", _workgroups_status(h)),

            ui.Heading("Services"),
        ]
        if profile_name == "default" and not runtime.is_docker():
            items.append(("Daemon", "daemon", _daemon_lifecycle_status()))
        items += [
            ("Subsystems", "subsystems", _subsystems_summary(h)),
            ("Schedules", "schedules", _schedules_status(h)),
        ]
        if profile_name == "default":
            items.append(("Connections", "connections", _devices_status(h)))
        items += [
            ui.Heading("Maintenance"),
            ("Health check", "doctor", _doctor_status(h, profile_name)),
            ("Cleanup", "cleanup", _cleanup_status(h)),
        ]
        if profile_name != "default":
            items.append(
                ("Delete profile", "delete-profile", _delete_profile_status(h, profile_name))
            )
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
        elif choice == "tiers":
            from alpi import model_selector

            model_selector.run_tiers(config.load(h))
        elif choice == "workspace":
            _workspace_setup(h)
        elif choice == "email":
            _email_accounts_setup(h)
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
        elif choice == "subsystems":
            _subsystems_wizard(h, profile_name)
        elif choice == "schedules":
            _schedules_setup(h)
        elif choice == "daemon":
            _daemon_lifecycle_wizard(h)
        elif choice == "identity":
            _identity_setup(h)
        elif choice == "peers":
            from alpi.alp.setup import run as alp_setup_run

            alp_setup_run(h)
        elif choice == "workgroups":
            from alpi.alp.workgroup_setup import run as wg_setup_run

            wg_setup_run(h)
        elif choice == "connections":
            _devices_setup(h)
        elif choice == "doctor":
            _doctor_wizard(h, profile_name)
        elif choice == "delete-profile":
            if _delete_profile_wizard(h, profile_name):
                return  # profile gone — nothing left to edit


def _setup_farewell(profile: str, h: Path) -> None:
    from alpi import ui as ui_mod

    prefix = f"alpi -p {profile}" if profile != "default" else "alpi"
    ui_mod._console.print(f"\n[dim]next:[/dim] {prefix}\n")


def _email_accounts_setup(h: Path) -> None:
    from alpi import ui
    from alpi.mail import accounts as accounts_mod

    while True:
        rows = accounts_mod.list_accounts(h)
        items: list = []
        for row in rows:
            items.append((
                f"{row['address'] or row['id']} ({row['type']})",
                row["id"],
                "configured" if row["configured"] else "not authorized",
            ))
        if rows:
            items.append(None)
        items.append(("Add account", "__add__", "connect a new IMAP or Gmail mailbox"))
        choice = ui.menu(
            ui.crumb("setup", "email"),
            items,
            subtitle="email accounts the agent can read and send from",
            home=h,
            close="Back",
        )
        if choice is None:
            return
        if choice == "__add__":
            _add_email_account_flow(h)
        else:
            _email_account_actions(h, choice)


def _add_email_account_flow(h: Path) -> None:
    from alpi import ui

    kind = ui.menu(
        ui.crumb("setup", "email", "add"),
        [("IMAP + SMTP", "imap", ""), ("Gmail (OAuth)", "gmail", "")],
        subtitle="pick the mailbox type",
        home=h,
        close="Back",
    )
    if kind is None:
        return
    if kind == "imap":
        from alpi.mail.setup import run as email_setup
        email_setup(h)
    elif kind == "gmail":
        from alpi.mail.gmail_setup import run as gmail_setup
        gmail_setup(h)


def _email_account_actions(h: Path, account_id: str) -> None:
    from alpi import ui
    from alpi.mail import accounts as accounts_mod

    if not ui.confirm(
        f"Remove {account_id} email account? You can re-add later.",
        default=False,
    ):
        return ui.cancelled()
    accounts_mod.remove_account(h, account_id)
    ui.ok_and_wait(
        f"removed {account_id} — restart the service for the change to take effect",
    )


def _subsystems_summary(h: Path) -> str:
    """Compact roll-up of enabled subsystems for this profile."""
    from alpi import service as svc

    on = svc.enabled_subsystems(h)
    enabled = [k for k, v in on.items() if v]
    if not enabled:
        return "all off"
    return ", ".join(enabled)


def _daemon_lifecycle_status() -> str:
    """One-line label for the daemon row on default's setup menu."""
    from alpi import service as svc

    pid = svc.daemon_running_pid(home._ROOT)
    installed = svc.daemon_installed()
    if pid is not None:
        base = f"running · pid {pid}"
    elif installed:
        base = "installed · stopped"
    else:
        base = "not installed"
    return base


_DAEMON_LIFECYCLE_COPY = (
    "The alpi daemon: one supervisor for every profile under ~/.alpi.\n"
    "Install once → autostarts on boot → hosts default plus every\n"
    "profile you create. Per-profile services are configured from\n"
    "each profile's `Services` row."
)


def _daemon_lifecycle_wizard(h: Path) -> None:
    """Daemon lifecycle UI for the machine."""
    from alpi import service as svc
    from alpi import ui

    if runtime.is_docker():
        label = "Docker"
        ui.banner(
            ui.crumb("setup", "daemon"), subtitle=f"managed by {label}", home=h,
        )
        ui.dim(
            f"On {label} the container entrypoint starts and supervises the "
            "daemon. Use the container restart or update flow instead of "
            "systemd or launchd controls here.",
        )
        ui.ok_and_wait(f"daemon lifecycle is managed by {label}")
        return

    root = home._ROOT
    while True:
        installed = svc.daemon_installed()
        running_pid = svc.daemon_running_pid(root)
        if running_pid is not None:
            head = f"running · pid {running_pid}"
        elif installed:
            head = "installed · stopped"
        else:
            head = "not installed"

        ui.banner(ui.crumb("setup", "daemon"), subtitle=head, home=h)
        ui.dim(_DAEMON_LIFECYCLE_COPY)
        ui._console.print("")

        items: list = [ui.Heading("Lifecycle")]
        if installed:
            if running_pid is not None:
                items.append(("Restart", "restart",
                              "stop + supervisor respawns"))
                items.append(("Stop", "stop",
                              "SIGTERM (supervisor will respawn)"))
            else:
                items.append(("Start", "start",
                              "ask the supervisor to launch it now"))
            items.append(("Uninstall", "uninstall",
                          "unregister + stop the daemon"))
        else:
            items.append(("Install", "install",
                          "register the daemon + start now"))

        choice = ui.menu("", items, home=h, close="Back")
        if choice is None:
            return
        try:
            if choice == "install":
                kind = svc.install_daemon(root)
                _wait_for_daemon(root, up=True)
                ui.ok_and_wait(f"daemon installed via {kind} · running")
            elif choice == "uninstall":
                svc.stop_daemon(root)
                kind = svc.uninstall_daemon()
                ui.ok_and_wait(f"daemon uninstalled ({kind})")
            elif choice == "start":
                _kickstart_daemon()
                if _wait_for_daemon(root, up=True):
                    ui.ok_and_wait("daemon running")
                else:
                    ui.fail_and_wait("did not come up within 10s — check log")
            elif choice == "restart":
                svc.stop_daemon(root)
                if _wait_for_daemon(root, up=True):
                    ui.ok_and_wait("daemon restarted")
                else:
                    ui.fail_and_wait(
                        "supervisor did not respawn within 10s — check log",
                    )
            elif choice == "stop":
                svc.stop_daemon(root)
                if svc.daemon_running_pid(root) is None:
                    ui.ok_and_wait("stopped")
                else:
                    ui.ok_and_wait(
                        "SIGTERM sent — supervisor respawned it (KeepAlive)",
                    )
        except Exception as e:  # noqa: BLE001
            ui.fail_and_wait(str(e))


def _wait_for_daemon(root: Path, *, up: bool, timeout: float = 10.0) -> bool:
    """Poll the central PID file until it matches ``up``."""
    from alpi import service as svc
    import time

    deadline = time.time() + timeout
    while time.time() < deadline:
        running = svc.daemon_running_pid(root) is not None
        if running == up:
            return True
        time.sleep(0.2)
    return False


def _kickstart_daemon() -> None:
    """Ask the OS supervisor to start the central unit."""
    import subprocess

    if sys.platform == "darwin":
        uid = os.getuid()
        subprocess.run(
            ["launchctl", "kickstart", "-k", f"gui/{uid}/com.alpi.daemon"],
            capture_output=True, text=True, check=False,
        )
    elif sys.platform.startswith("linux"):
        subprocess.run(
            ["systemctl", "--user", "start", "alpi-daemon.service"],
            capture_output=True, text=True, check=False,
        )


def _restart_daemon_for_apply(root: Path) -> str:
    """SIGTERM the running daemon so supervisor respawns it with fresh config; returns suffix for the success line."""
    from alpi import service as svc

    if svc.daemon_running_pid(root) is None:
        return ""
    svc.stop_daemon(root, timeout=2.0)
    return " · daemon restarting"


def _ensure_daemon_installed(root: Path) -> None:
    """First-run hook: install the daemon if it is missing."""
    from alpi import service as svc

    if runtime.is_docker():
        return

    try:
        if svc.daemon_installed():
            return
        kind = svc.install_daemon(root)
        click.echo(f"alpi: daemon installed via {kind}")
    except svc.ServiceError as e:
        click.echo(f"alpi: service install skipped — {e}", err=True)


def _service_status(h: Path, profile: str) -> str:
    """Status line for the daemon entry in the setup menu."""
    from alpi import service as svc

    root = home._ROOT
    pid = svc.daemon_running_pid(root)
    if runtime.is_docker():
        label = "Docker"
        return f"managed by {label} · pid {pid}" if pid is not None else f"managed by {label}"
    installed = svc.daemon_installed()
    running = f"running (pid {pid})" if pid is not None else "stopped"
    return (
        f"{running} · installed" if installed
        else f"{running} · not installed"
    )


_SERVICES_WIZARD_COPY = (
    "Which services the alpi daemon runs for THIS profile. The daemon\n"
    "itself is global (one per machine, see Setup → Daemon on default);\n"
    "these flags only decide what it activates here. A daemon restart\n"
    "picks up changes: `alpi daemon restart`."
)

_SERVICES_WIZARD_COPY_MANAGED = (
    "Which services the Alpi daemon runs for THIS profile.\n"
    "In a container the entrypoint manages the daemon itself;\n"
    "these flags only decide what it activates here."
)


def _subsystems_wizard(h: Path, profile: str) -> None:
    """Per-profile subsystem toggles; daemon lifecycle lives in ``alpi daemon``."""
    from alpi import config as cfg_mod
    from alpi import service as svc
    from alpi import ui

    while True:
        on_subsystems = svc.enabled_subsystems(h)
        running_pid = svc.daemon_running_pid(home._ROOT)
        if runtime.is_docker():
            label = "Docker"
            head = (
                f"daemon: managed by {label} · pid {running_pid}" if running_pid
                else f"daemon: managed by {label}"
            )
            copy = _SERVICES_WIZARD_COPY_MANAGED
        else:
            head = (
                f"daemon: running · pid {running_pid}" if running_pid
                else "daemon: stopped"
            )
            copy = _SERVICES_WIZARD_COPY

        ui.banner(ui.crumb("setup", "services"), subtitle=head, home=h)
        ui.dim(copy)
        ui._console.print("")

        items: list = [
            ui.Heading(f"Services · profile: {profile}"),
            (("Scheduler · " + _on_off(on_subsystems["schedule"])),
             "toggle-schedule", "cron jobs"),
            (("ALP listener · " + _on_off(on_subsystems["alp"])),
             "toggle-alp", _alp_subsystem_status(h)),
            (("Workgroups · " + _on_off(on_subsystems["workgroups"])),
             "toggle-workgroups", "ALP.3 outbound poller"),
        ]
        if profile == "default":
            items.append((
                ("Host API · " + _on_off(on_subsystems["host"])),
                "toggle-host",
                "control plane for desktop / mobile clients",
            ))
        items.append(ui.Heading("Network"))
        items.append(("Accessible address", "network", _network_host_label(h)))
        items.append(ui.Heading("ALP"))
        items.append(("Peer TCP listener", "tcp",
                      _alp_tcp_label(h)))

        choice = ui.menu("", items, home=h, close="Back")
        if choice is None:
            return
        try:
            if choice in (
                "toggle-schedule", "toggle-alp",
                "toggle-host", "toggle-workgroups",
            ):
                key = choice.split("-", 1)[1]
                cfg = cfg_mod.load(h)
                svc_cfg = dict(cfg.service or {})
                svc_cfg[key] = not on_subsystems[key]
                cfg.service = svc_cfg
                cfg_mod.save(cfg)
                msg = _restart_daemon_for_apply(home._ROOT)
                ui.ok_and_wait(f"{key}: {_on_off(svc_cfg[key])}{msg}")
            elif choice == "network":
                _network_host_setup(h)
            elif choice == "tcp":
                _alp_tcp_port_setup(h)
        except Exception as e:  # noqa: BLE001
            ui.fail_and_wait(str(e))


_service_wizard = _subsystems_wizard


def _on_off(b: bool) -> str:
    return "on" if b else "off"


def _alp_subsystem_status(h: Path) -> str:
    from alpi import config as cfg_mod
    from alpi.service import DEFAULT_ALP_TCP_PORT
    cfg = cfg_mod.load(h)
    port = (cfg.alp or {}).get("tcp_port") or DEFAULT_ALP_TCP_PORT
    return f"unix + tcp :{port}"


def _alp_tcp_label(h: Path) -> str:
    from alpi import config as cfg_mod
    from alpi.service import DEFAULT_ALP_TCP_PORT
    cfg = cfg_mod.load(h)
    port = (cfg.alp or {}).get("tcp_port") or DEFAULT_ALP_TCP_PORT
    host = str((cfg.network or {}).get("host") or "").strip() or "auto"
    return f"{host}:{port} (Noise_XK)"


def _network_host_label(h: Path) -> str:
    from alpi import config as cfg_mod
    cfg = cfg_mod.load(h)
    host = str((cfg.network or {}).get("host") or "").strip()
    return host or "auto-detect (Tailscale → LAN)"


def _alp_tcp_port_setup(h: Path) -> None:
    """Set the ALP peer TCP port. ALP TCP is always-on (default 7423) whenever a
    safe address resolves; the address is the shared accessible address
    (Network). To turn ALP off entirely, disable it in Services."""
    from alpi import config as cfg_mod
    from alpi import ui
    from alpi.service import DEFAULT_ALP_TCP_PORT

    cfg = cfg_mod.load(h)
    current_port = (cfg.alp or {}).get("tcp_port") or DEFAULT_ALP_TCP_PORT
    net_host = str((cfg.network or {}).get("host") or "").strip() or "auto-detect"

    ui.banner(
        ui.crumb("setup", "alp-tcp", "tcp"),
        subtitle="Noise_XK over TCP — remote Alpi peers",
        home=h,
    )
    ui.dim(
        "Remote Alpi peers reach this profile over Noise_XK TCP\n"
        "(peers.yaml-pinned only). The address is the shared accessible\n"
        f"address (Network · {net_host}); here you set only the port.\n"
        f"Empty = default {DEFAULT_ALP_TCP_PORT}. ALP TCP is always on when an\n"
        "address resolves — to turn ALP off, disable it in Services."
    )
    ui._console.print("")

    port_hint = f"[empty = {DEFAULT_ALP_TCP_PORT}]"
    port_s = ui.text(f"Port number (1-65535) {port_hint}:", default=str(current_port))
    if port_s is None:
        return ui.cancelled()
    port_s = (port_s or "").strip()

    alp_cfg = dict(cfg.alp or {})
    alp_cfg.pop("tcp_host", None)  # legacy — address is network.host now

    if not port_s or port_s == str(DEFAULT_ALP_TCP_PORT):
        # Default → drop the key (config stays minimal); still binds the default.
        alp_cfg.pop("tcp_port", None)
        cfg.alp = alp_cfg
        cfg_mod.save(cfg)
        msg = _restart_daemon_for_apply(home._ROOT)
        ui.ok_and_wait(f"ALP TCP on {net_host}:{DEFAULT_ALP_TCP_PORT} (default){msg}")
        return

    try:
        port = int(port_s)
    except ValueError:
        ui.fail_and_wait(f"not a valid port: {port_s!r}")
        return
    if not (1 <= port <= 65535):
        ui.fail_and_wait(f"port out of range: {port} (expected 1-65535)")
        return

    alp_cfg["tcp_port"] = port
    cfg.alp = alp_cfg
    cfg_mod.save(cfg)
    msg = _restart_daemon_for_apply(home._ROOT)
    ui.ok_and_wait(f"ALP TCP on {net_host}:{port}{msg}")


def _network_host_setup(h: Path) -> None:
    """Set the shared accessible address (network.host) — the address other
    machines/devices reach this profile at, for both device pairing and ALP."""
    from alpi import config as cfg_mod
    from alpi import ui

    cfg = cfg_mod.load(h)
    current = str((cfg.network or {}).get("host") or "").strip()

    ui.banner(ui.crumb("setup", "network"), subtitle="accessible address", home=h)
    ui.dim(
        "The address other machines and your devices use to reach this\n"
        "profile — shared by device pairing and ALP peers. Empty = auto-detect\n"
        "(Tailscale, then LAN). Any reachable host works: Tailscale / LAN IP,\n"
        "private hostname, VPN address, or 0.0.0.0. A public IP also needs\n"
        "host.allow_public_bind: true, set by hand in config.yaml (not here) —\n"
        "without it neither plane binds TCP. Ports stay per-plane."
    )
    ui._console.print("")

    host = ui.text(
        f"Accessible address (empty = auto-detect) [{current or 'auto'}]:",
        default=current,
    )
    if host is None:
        return ui.cancelled()
    host = (host or "").strip()

    net_cfg = dict(cfg.network or {})
    if host:
        net_cfg["host"] = host
    else:
        net_cfg.pop("host", None)
    cfg.network = net_cfg
    cfg_mod.save(cfg)
    msg = _restart_daemon_for_apply(home._ROOT)
    ui.ok_and_wait(f"accessible address: {host or 'auto-detect'}{msg}")


def _devices_status(h: Path) -> str:
    from alpi.host import connections as connections_mod
    from alpi.host.network import resolve_host_endpoint

    if resolve_host_endpoint(h) is None:
        return "no network"
    n = len(connections_mod.list_connections())
    return f"{n} paired" if n else "ready"


def _devices_setup(h: Path) -> None:
    from alpi import ui
    from alpi.host import connections as connections_mod
    from alpi.host.network import resolve_host_endpoint
    from alpi.host.usage import connections_summary

    query = ""
    while True:
        endpoint = resolve_host_endpoint(h)
        items: list = [
            ui.Heading("Connections"),
        ]
        rows = connections_mod.list_connections()
        summary_by_id = {
            row["id"]: row for row in connections_summary()["connections"]
        }
        if not rows:
            items.append(("(no connections yet)", "noop", ""))
        else:
            ranked = []
            for connection in rows:
                public = connections_mod.public_connection(connection)
                summary = summary_by_id.get(public["id"], {})
                last_seen = summary.get("last_seen") or public.get("last_seen")
                search_text = " ".join([
                    public["label"],
                    public["role"],
                    public["status"],
                    *[
                        str(value)
                        for device in public["devices"]
                        for value in (
                            device.get("name"), device.get("client"),
                            device.get("app_version"), device.get("token_id"),
                        )
                        if value
                    ],
                ]).casefold()
                if query and query.casefold() not in search_text:
                    continue
                ranked.append((int(last_seen or 0), public, summary))
            ranked.sort(key=lambda item: (-item[0], item[1]["label"].casefold()))
            shown = ranked[:20]
            search_hint = (
                f"{len(ranked)} matches · {query}"
                if query else f"{len(rows)} total · showing {len(shown)} recent"
            )
            items.append(("Search connections…", "search", search_hint))
            items.append(None)
            for last_seen, public, summary in shown:
                state = " · disabled" if public["status"] == "disabled" else ""
                hint = (
                    f"{public['role']}{state} · {len(public['devices'])} devices · "
                    f"{int(summary.get('sessions') or 0)} sessions · "
                    f"${float(summary.get('cost_14d') or 0):.2f} / 14d · "
                    f"{_format_last_seen(last_seen)}"
                )
                items.append((public["label"], ("device", public["id"]), hint))
            if not shown:
                items.append(("(no matching connections)", "noop", ""))

        items.append(None)
        items.append(("+ New connection", "add", "label, access and first device"))
        items.append(("Network", "network",
                      _network_row_status(h, endpoint)))

        choice = ui.menu(
            ui.crumb("setup", "connections"),
            items,
            subtitle=_devices_subtitle(h, endpoint),
            home=h,
            close="Done",
        )
        if choice is None:
            return
        if choice == "noop":
            continue
        if choice == "search":
            value = ui.text("Search by connection or device:", default=query)
            if value is not None:
                query = value.strip()
            continue
        if choice == "add":
            _device_add(h, endpoint)
            continue
        if choice == "network":
            _devices_network_setup(h)
            continue
        if isinstance(choice, tuple) and choice[0] == "device":
            _device_detail(h, choice[1])
            continue


def _devices_subtitle(h: Path, endpoint) -> str:
    from alpi.host.network import resolve_host_tcp_port

    if endpoint is None:
        if runtime.is_docker():
            return "remote access not configured — set ALPI_NETWORK_HOST"
        return "no network — install Tailscale or connect to a LAN"
    host, scope = endpoint
    return f"{scope} · {host}:{resolve_host_tcp_port(h)}"


def _network_row_status(h: Path, endpoint) -> str:
    from alpi.host.network import resolve_host_tcp_port

    if endpoint is None:
        if runtime.is_docker():
            return "set ALPI_NETWORK_HOST"
        return "auto-detect Tailscale or LAN"
    host, _scope = endpoint
    return f"{host}:{resolve_host_tcp_port(h)}"


def _format_last_seen(epoch) -> str:
    if not epoch:
        return "never"
    import time as _time
    delta = int(_time.time()) - int(epoch)
    if delta < 60:
        return "just now"
    if delta < 3600:
        return f"{delta // 60}m ago"
    if delta < 86400:
        return f"{delta // 3600}h ago"
    return f"{delta // 86400}d ago"


def _connection_profile_scope(h: Path, current: list[str] | None = None) -> list[str] | None:
    from alpi import home as home_mod
    from alpi import ui

    available = home_mod.list_profiles(h)
    available_set = set(available)
    while True:
        ui.dim(
            "Restrict this connection to a subset of profiles, or leave blank for\n"
            f"all (available: {', '.join(available)})."
        )
        raw = ui.text(
            "Profiles (comma-separated, blank = all):",
            default=", ".join(current or []),
        )
        if raw is None:
            return None
        candidates = [name.strip() for name in raw.split(",") if name.strip()]
        unknown = [name for name in candidates if name not in available_set]
        if unknown:
            ui.fail(f"unknown profile(s): {', '.join(unknown)}")
            continue
        return list(dict.fromkeys(candidates))


def _device_add(h: Path, endpoint) -> None:
    from alpi import ui
    from alpi.host import connections as connections_mod
    from alpi.host.network import resolve_host_pairing_name, resolve_host_tcp_port

    if endpoint is None:
        ui.banner(
            ui.crumb("setup", "connections", "new"),
            subtitle="cannot pair — no network",
            home=h,
        )
        if runtime.is_docker():
            ui.fail(
                "Set the advertised host first.\n"
                "Set ALPI_NETWORK_HOST to the host's Tailscale IP /\n"
                "MagicDNS name (or a LAN hostname) so clients can reach the container."
            )
        else:
            ui.fail(
                "Neither Tailscale nor a LAN address detected.\n"
                "Install Tailscale (https://tailscale.com/download) or connect to Wi-Fi."
            )
        ui.press_enter()
        return

    host, scope = endpoint
    port = resolve_host_tcp_port(h)

    ui.banner(
        ui.crumb("setup", "connections", "new"),
        subtitle=f"create connection · {scope} · {host}:{port}",
        home=h,
    )
    ui._console.print("")
    label = ui.text("Label (e.g. Javi, Support):", default="")
    if label is None:
        return ui.cancelled()

    grant_admin = ui.confirm(
        "Grant admin access? — can manage profiles and connections",
        default=False,
    )
    role = "admin" if grant_admin else "member"

    profile_scope: list[str] = []
    if role == "member":
        selected = _connection_profile_scope(h)
        if selected is None:
            return ui.cancelled()
        profile_scope = selected

    connection, device = connections_mod.create_connection(
        label=label or "connection", role=role, profile_scope=profile_scope,
    )

    import io
    import json
    from urllib.parse import urlencode

    import qrcode

    pairing_name = resolve_host_pairing_name(h)

    payload = {
        "i": host,
        "p": port,
        "n": pairing_name,
        "t": device["token"],
    }
    link = "alpi://device?" + urlencode({
        "host": payload["i"],
        "port": payload["p"],
        "name": payload["n"],
        "token": payload["t"],
    })

    ui.banner(
        ui.crumb("setup", "connections", "new", connection["label"]),
        subtitle=f"scan once · {scope} · {host}:{port}",
        home=h,
    )
    ui._console.print("")
    with ui.activity("generating pairing QR…"):
        qr = qrcode.QRCode(
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            border=1,
        )
        qr.add_data(json.dumps(payload, separators=(",", ":")))
        qr.make(fit=True)
        buf = io.StringIO()
        qr.print_ascii(out=buf, invert=True)
    ui._console.print(buf.getvalue())
    ui._console.print(f"[dim]label:    [/dim] {connection['label']}")
    ui._console.print(f"[dim]role:     [/dim] {connection['role']}")
    ui._console.print(f"[dim]token id:[/dim] …{device['token'][-8:]}")
    ui._console.print(f"[dim]desktop:  [/dim] {link}")
    ui._console.print("")
    ui.dim(
        "Scan the QR from mobile or paste the desktop link into the desktop app.\n"
        "This pairing link adds the first device to the connection.\n"
        "If the QR or link is exposed to anyone else, revoke and generate a new one."
    )
    ui.press_enter()


def _devices_network_setup(h: Path) -> None:
    from alpi import config as cfg_mod
    from alpi import ui
    from alpi.host.network import (
        _advertise_host_hint,
        detect_bind_ip,
        resolve_host_tcp_port,
    )

    cfg = cfg_mod.load(h)
    host_cfg = dict(cfg.host or {})
    net_cfg = dict(cfg.network or {})
    current = str(net_cfg.get("host") or "").strip()
    current_name = str(host_cfg.get("device_name") or "").strip()
    detected = detect_bind_ip()
    managed = runtime.is_docker()
    auto_host = (
        (_advertise_host_hint() or "")
        if managed
        else (detected[0] if detected else "")
    )
    default = current or auto_host
    port = resolve_host_tcp_port(h)

    subtitle = (
        "how mobile and desktop clients reach this container"
        if managed
        else "how mobile and desktop clients reach this machine"
    )
    ui.banner(
        ui.crumb("setup", "connections", "network"),
        subtitle=subtitle,
        home=h,
    )
    if managed:
        ui.dim(
            "Clients talk to the host API on TCP/WS.\n"
            "Inside a container, Alpi cannot see the host's Tailscale interface\n"
            "directly, so set the address clients should dial here (a 100.x\n"
            f"Tailscale IP / MagicDNS name, or a LAN hostname). Port {port} is\n"
            "published by the container."
        )
    else:
        ui.dim(
            "Clients talk to the host API on TCP/WS.\n"
            "Leave this blank to auto-detect Tailscale first, then LAN.\n"
            "Set a specific host only if you want to advertise a stable hostname,\n"
            "MagicDNS name, VPN IP, or other explicit endpoint."
        )
    ui._console.print("")

    host = ui.text(
        "Advertised host [blank = auto]:",
        default=default,
    )
    if host is None:
        return ui.cancelled()
    host = (host or "").strip()

    if host:
        net_cfg["host"] = host  # shared accessible address (network.host)
    else:
        net_cfg.pop("host", None)

    pairing_name = ui.text(
        "Pairing name [blank = auto]:",
        default=current_name,
    )
    if pairing_name is None:
        return ui.cancelled()
    pairing_name = pairing_name.strip()

    if pairing_name:
        host_cfg["device_name"] = pairing_name
    else:
        host_cfg.pop("device_name", None)

    cfg.host = host_cfg
    cfg.network = net_cfg
    cfg_mod.save(cfg)
    msg = _restart_daemon_for_apply(home._ROOT)
    target = host or auto_host or "auto-detect"
    name_target = pairing_name or "auto"
    ui.ok_and_wait(f"remote access target: {target}:{port}, pairing name: {name_target}{msg}")


def _device_detail(h: Path, connection_id: str) -> None:
    from alpi import ui
    from alpi.host import connections as connections_mod
    from alpi.host.network import resolve_host_endpoint
    from alpi.host.usage import connections_summary

    while True:
        target = next(
            (row for row in connections_mod.list_connections() if row["id"] == connection_id),
            None,
        )
        if target is None:
            return
        public = connections_mod.public_connection(target)
        summary = next(
            (
                row for row in connections_summary()["connections"]
                if row["id"] == connection_id
            ),
            {},
        )
        scope = public.get("profile_scope") or []
        profiles_display = "all" if public["role"] == "admin" or not scope else ", ".join(scope)
        entries: list = [
            ("Role", "noop", public["role"]),
            ("Profiles", "noop", profiles_display),
            ("Status", "noop", public["status"]),
            ("Last seen", "noop", _format_last_seen(public.get("last_seen"))),
            ("Sessions", "noop", str(int(summary.get("sessions") or 0))),
            (
                "Usage (14 days)",
                "noop",
                f"${float(summary.get('cost_14d') or 0):.2f} · "
                f"{int(summary.get('tokens_14d') or 0):,} tokens",
            ),
            None,
            ui.Heading("Devices"),
            *[
                (
                    device.get("name") or f"{device.get('client', 'unknown')} device",
                    ("revoke_device", device["id"]),
                    " · ".join(filter(None, (
                        device.get("client", "unknown"),
                        device.get("app_version"),
                        _format_last_seen(device.get("last_seen")),
                    ))),
                )
                for device in public["devices"]
                if device.get("status") != "deleted"
            ],
            ("+ Add device", "add_device", "generate another pairing link"),
            None,
            ("Rename", "rename", ""),
        ]
        if public["role"] != "admin":
            entries.append(("Edit profiles", "scope", "blank = all"))
        entries.extend([
            ("Toggle role", "role", "admin / member"),
            ("Enable" if public["status"] == "disabled" else "Disable", "status", "keeps sessions and usage"),
            ("Delete", "delete", "revokes every linked device"),
        ])
        choice = ui.menu(
            ui.crumb("setup", "connections", public["label"]),
            entries,
            subtitle="connection detail",
            home=None,
            close="Back",
        )
        if choice is None:
            return
        if choice == "rename":
            label = ui.text("New label:", default=public["label"])
            if label:
                connections_mod.update_connection(connection_id, label=label)
        elif choice == "add_device":
            endpoint = resolve_host_endpoint(h)
            if endpoint is None:
                ui.fail("No advertised host is available.")
                ui.press_enter()
                continue
            connection, device = connections_mod.add_device(connection_id)
            _show_connection_pairing(h, endpoint, connection, device)
        elif isinstance(choice, tuple) and choice[0] == "revoke_device":
            device = next(
                (row for row in public["devices"] if row["id"] == choice[1]),
                None,
            )
            if device and ui.confirm(
                f"Revoke {device.get('name') or device.get('client') or 'device'}? "
                "This device loses access immediately; other devices keep working.",
                default=False,
            ):
                connections_mod.revoke_device(connection_id, choice[1])
        elif choice == "scope" and public["role"] != "admin":
            selected = _connection_profile_scope(h, scope)
            if selected is not None:
                connections_mod.update_connection(
                    connection_id,
                    profile_scope=selected,
                )
        elif choice == "role":
            role = "member" if public["role"] == "admin" else "admin"
            if ui.confirm(f"Change {public['label']} to {role}?", default=False):
                connections_mod.update_connection(connection_id, role=role)
        elif choice == "status":
            status = "active" if public["status"] == "disabled" else "disabled"
            if status == "active" or ui.confirm(
                f"Disable {public['label']}? Its {len(public['devices'])} linked devices "
                "will go offline. Sessions and usage remain.",
                default=False,
            ):
                connections_mod.update_connection(connection_id, status=status)
        elif choice == "delete":
            if ui.confirm(f"Delete {public['label']} and revoke all devices?", default=False):
                typed = ui.text(f"Type '{public['label']}' to confirm")
                if (typed or "").strip() == public["label"]:
                    connections_mod.delete_connection(connection_id)
                    ui.ok_and_wait("connection deleted")
                    return
                ui.cancelled()


def _show_connection_pairing(h: Path, endpoint, connection, device) -> None:
    from alpi import ui
    from alpi.host.network import resolve_host_pairing_name, resolve_host_tcp_port
    import io
    import json
    from urllib.parse import urlencode
    import qrcode

    host, scope = endpoint
    port = resolve_host_tcp_port(h)
    name = resolve_host_pairing_name(h)
    payload = {"i": host, "p": port, "n": name, "t": device["token"]}
    link = "alpi://device?" + urlencode({
        "host": host, "port": port, "name": name, "token": device["token"],
    })
    ui.banner(
        ui.crumb("setup", "connections", connection["label"], "add device"),
        subtitle=f"scan once · {scope} · {host}:{port}",
        home=h,
    )
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_L, border=1)
    qr.add_data(json.dumps(payload, separators=(",", ":")))
    qr.make(fit=True)
    buf = io.StringIO()
    qr.print_ascii(out=buf, invert=True)
    ui._console.print(buf.getvalue())
    ui._console.print(f"[dim]desktop:[/dim] {link}")
    ui.press_enter()


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
    from alpi.alp import pending as pending_mod

    count = len(peers_mod.load(h))
    pending = len(pending_mod.load(h))
    base = "none pinned" if count == 0 else f"{count} pinned"
    if pending:
        word = "invite" if pending == 1 else "invites"
        return f"{base} · {pending} {word} pending"
    return base


def _doctor_status(h: Path, profile: str) -> str:
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


def _email_accounts_status(h: Path) -> str:
    from alpi.mail import accounts as accounts_mod

    rows = accounts_mod.list_accounts(h)
    configured = [r["address"] or r["id"] for r in rows if r["configured"]]
    return ", ".join(configured) if configured else "none"


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
    usd = (cfg.budget or {}).get("daily_usd")
    if isinstance(usd, (int, float)) and usd > 0:
        return f"${float(usd):.2f}/day"
    return "unlimited"


def _budget_setup(h: Path) -> None:
    from alpi import ui

    cfg = config.load(h)
    current_usd = (cfg.budget or {}).get("daily_usd")
    current_kind = "usd" if current_usd is not None else "unlimited"

    items = [
        (
            ("● " if current_kind == "unlimited" else "  ") + "Unlimited",
            "unlimited",
            "no daily ceiling",
        ),
        (
            ("● " if current_kind == "usd" else "  ") + "Daily USD cap",
            "usd",
            "measured in dollars — the only spend cap",
        ),
    ]
    kind = ui.menu(
        ui.crumb("setup", "budget"),
        items,
        subtitle="daily spend cap for this profile · USD or unlimited",
        home=h,
        close="Back",
    )
    if kind is None:
        return
    if kind == "unlimited":
        cfg.budget = {}
        config.save(cfg)
        ui.ok_and_wait("budget cleared — unlimited")
        return

    default_s = str(current_usd) if current_usd is not None else ""
    raw = ui.text(
        "Daily USD cap (must be > 0):",
        default=default_s,
    )
    if raw is None:
        return ui.cancelled()
    raw = (raw or "").strip()
    if not raw:
        ui.fail_and_wait("USD cap required (or pick Unlimited)")
        return
    try:
        v = float(raw)
    except ValueError:
        ui.fail_and_wait(f"not a number: {raw!r}")
        return
    if v <= 0:
        ui.fail_and_wait("USD cap must be > 0")
        return
    cfg.budget = {"daily_usd": v}
    config.save(cfg)
    ui.ok_and_wait(f"cap: ${v:.2f}/day")


def _identity_status(cfg: config.Config) -> str:
    bio = (cfg.public_bio or "").strip()
    if not bio:
        return "not set · peers see handle only"
    if len(bio) <= 60:
        return bio
    return bio[:59] + "…"


def _identity_setup(h: Path) -> None:
    """Edit the public_bio; next workgroup.join carries the new value."""
    from alpi import ui

    cfg = config.load(h)

    ui.banner(
        ui.crumb("setup", "identity"),
        subtitle=_identity_status(cfg),
        home=h,
    )
    ui.dim(
        "Public bio is your one-line tag-line ('product engineer —\n"
        "velocity, ships fast'). It is sent on every workgroup.join\n"
        "and rendered in other members' agent prompts so they know\n"
        "what you do without having to ask.\n\n"
        "AGENT.md stays private — this is the deliberate cross-agent\n"
        "introduction. Visible to anyone who joins a workgroup with\n"
        "you (so think 'business card', not personal notes).\n\n"
        "Empty = keep current · `clear` = unset · `draft` = synthesize\n"
        "a draft from your AGENT.md (one LLM call, you can edit it)."
    )
    ui._console.print("")

    current = cfg.public_bio or ""
    raw = ui.text("Public bio", default=current)
    if raw is None:
        return ui.cancelled()
    raw = raw.strip()
    if not raw:
        ui.ok_and_wait("bio unchanged")
        return
    if raw.lower() == "clear":
        cfg.public_bio = ""
        config.save(cfg)
        ui.ok_and_wait("bio cleared — peers will see handle only")
        return
    if raw.lower() == "draft":
        drafted = _draft_bio_from_agent(h, cfg)
        if drafted is None:
            return
        edited = ui.text("Edit the draft (Enter to accept):", default=drafted)
        if edited is None:
            return ui.cancelled()
        raw = (edited or "").strip()
        if not raw:
            ui.ok_and_wait("bio unchanged")
            return
    if len(raw) > 200:
        raw = raw[:200]
        ui.dim("(truncated to 200 chars)")
    cfg.public_bio = raw
    config.save(cfg)
    ui.ok_and_wait(f"bio set: {raw}")


def _draft_bio_from_agent(h: Path, cfg: config.Config) -> str | None:
    """TUI wrapper around ``alpi.identity.draft_bio_from_agent``."""
    from alpi import identity, ui

    if not cfg.model:
        ui.fail_and_wait("no model configured — set one in setup → Model")
        return None
    ui.dim("synthesizing one-line bio from AGENT.md…")
    try:
        return identity.draft_bio_from_agent(h, cfg)
    except ValueError as e:
        ui.fail_and_wait(str(e))
        return None
    except Exception as e:  # noqa: BLE001
        ui.fail_and_wait(f"draft failed: {e}")
        return None


def _workspace_status(cfg: config.Config) -> str:
    if cfg.workspace_path is not None:
        return str(cfg.workspace_path)
    return "not set · falls back to cwd"


def _workspace_setup(h: Path) -> None:
    """Pick the workspace directory; default root for relative paths in file tools and the shell sandbox."""
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
            "Recommended for unattended profiles (scheduler, sub-agents).\n"
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
    ("en-US-JennyNeural", "Jenny", "English (US) · female"),
    ("en-GB-SoniaNeural", "Sonia", "English (UK) · female"),
    ("en-GB-RyanNeural", "Ryan", "English (UK) · male"),
    ("en-AU-NatashaNeural", "Natasha", "English (AU) · female"),
    ("en-AU-WilliamNeural", "William", "English (AU) · male"),
    ("es-ES-ElviraNeural", "Elvira", "Spanish (Spain) · female"),
    ("es-ES-AlvaroNeural", "Alvaro", "Spanish (Spain) · male"),
    ("es-MX-DaliaNeural", "Dalia", "Spanish (Mexico) · female"),
    ("fr-FR-DeniseNeural", "Denise", "French (France) · female"),
    ("fr-FR-HenriNeural", "Henri", "French (France) · male"),
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
    return _voice_display(cfg.tools.tts.voice)


def _tiers_status(cfg: config.Config) -> str:
    from alpi.model_selector import tiers_status
    return tiers_status(cfg)


def _voice_setup(h: Path) -> None:
    """Pick the Edge TTS voice for the `tts` tool."""
    from alpi import ui

    while True:
        cfg = config.load(h)

        ui.banner(
            ui.crumb("setup", "voice"),
            subtitle=_voice_status(cfg),
            home=h,
        )
        ui.dim(
            "Default voice for audio output. Any pick is permanent until "
            "you change it here."
        )
        ui._console.print("")

        accent = (cfg.tui or {}).get("accent", "") or ""
        collected: list[tuple[str, str, str, bool]] = []
        for vid, name, desc in _VOICE_SHORTLIST:
            collected.append((name, desc, vid, vid == cfg.tools.tts.voice))
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

        cfg.tools.tts.voice = choice
        config.save(cfg)
        ui.ok_and_wait(f"voice set to {_voice_display(cfg.tools.tts.voice)}")
        return


def _cleanup_categories(h: Path) -> list[dict]:
    from alpi.cleanup import categories
    return categories(h)


def _schedules_status(h: Path) -> str:
    from alpi.scheduler import jobs_store

    try:
        jobs = jobs_store.read(h)
    except Exception:  # noqa: BLE001
        return "jobs.json unreadable"
    if not jobs:
        return "no jobs"
    paused = sum(1 for j in jobs if j.get("paused"))
    label = f"{len(jobs)} job{'s' if len(jobs) != 1 else ''}"
    return f"{label} · {paused} paused" if paused else label


def _schedules_setup(h: Path) -> None:
    from alpi import ui
    from alpi.scheduler import jobs_store

    while True:
        try:
            jobs = jobs_store.read(h)
        except jobs_store.CorruptJobsFile as e:
            ui.fail(f"jobs.json corrupt: {e}")
            return
        if not jobs:
            ui.ok_and_wait("no scheduled jobs — add one via chat (`schedule` tool)")
            return
        items: list = []
        for j in jobs:
            when = j.get("expression") or j.get("run_at") or f"{j.get('after_hours')}h idle"
            title = j.get("title") or (j.get("prompt") or "")[:50].replace("\n", " ")
            flags = " · paused" if j.get("paused") else ""
            items.append((title, j.get("id"), f"[{j.get('kind', 'cron')}] {when}{flags}"))
        choice = ui.menu(
            ui.crumb("setup", "schedules"), items, home=h, close="Back",
        )
        if choice is None:
            return
        job = next((j for j in jobs if j.get("id") == choice), None)
        if job is None:
            continue
        actions = [
            ("Fire now", "fire", "run this job immediately"),
            ("Resume" if job.get("paused") else "Pause", "toggle",
             "auto-fire stays off while paused"),
            ("Delete", "delete", "remove the job permanently"),
        ]
        action = ui.menu(
            job.get("title") or str(job.get("id")), actions, home=h, close="Back",
        )
        if action == "fire":
            from alpi.scheduler.run import fire_by_id
            ok, msg = fire_by_id(h, str(job.get("id")))
            ui.ok_and_wait(f"{'OK' if ok else 'FAIL'} — {msg}")
        elif action == "toggle":
            # Mirrors host.schedule.set_paused exactly: flip the flag, never touch last_run_at.
            def _toggle(current: list[dict]) -> list[dict] | None:
                for row in current:
                    if row.get("id") == job.get("id"):
                        row["paused"] = not job.get("paused")
                        return current
                return None
            jobs_store.update(h, _toggle)
            ui.ok_and_wait("job updated")
        elif action == "delete":
            if not ui.confirm(f"  Delete job {job.get('id')}?", default=False):
                continue
            def _drop(current: list[dict]) -> list[dict] | None:
                kept = [row for row in current if row.get("id") != job.get("id")]
                return kept if len(kept) != len(current) else None
            jobs_store.update(h, _drop)
            ui.ok_and_wait("job deleted")


def _cleanup_status(h: Path) -> str:
    from alpi import home as home_mod

    cats = _cleanup_categories(h)
    total = sum(c["size"] for c in cats)
    if total == 0:
        return "nothing to clean"
    return f"{home_mod.format_bytes(total)} reclaimable"


def _cleanup_setup(h: Path) -> None:
    from alpi import home as home_mod, ui

    from alpi.cleanup import apply as cleanup_apply, item_count

    while True:
        cats = [c for c in _cleanup_categories(h) if item_count(c) > 0]
        safe_cats = [c for c in cats if not c.get("destructive")]
        destructive_cats = [c for c in cats if c.get("destructive")]
        safe_size = sum(c["size"] for c in safe_cats)

        items: list = []
        if safe_cats:
            items.append((
                "Clean all safe", "__safe__",
                f"{home_mod.format_bytes(safe_size)} · caches, logs, knowledge",
            ))
        for c in destructive_cats:
            n = item_count(c)
            items.append((f"{c['label']} ⚠", c["key"], f"{home_mod.format_bytes(c['size'])} · {n} item{'s' if n != 1 else ''}"))

        choice = ui.menu(
            ui.crumb("setup", "cleanup"),
            items,
            subtitle=f"profile: {home_mod.shorten_home(h)}" if items else "nothing to reclaim",
            home=h,
            close="Back",
        )
        if choice is None:
            return

        if choice == "__safe__":
            targets, verb = safe_cats, f"Reclaim {home_mod.format_bytes(safe_size)} of safe storage?"
        else:
            target = next((c for c in destructive_cats if c["key"] == choice), None)
            if target is None:
                continue
            targets = [target]
            n = item_count(target)
            verb = (
                f"Delete {n} item(s) · {home_mod.format_bytes(target['size'])} "
                f"from {target['label']}? This cannot be undone."
            )

        ui._console.print("")
        if not ui.confirm(f"  {verb}", default=False):
            continue

        removed = freed = 0
        errors: list = []
        for c in targets:
            result = cleanup_apply(h, c["key"])
            errors += result.get("errors", [])
            removed += result.get("removed", 0)
            freed += result.get("freed_bytes", 0)
        for err in errors:
            ui.fail(f"could not delete {err}")
        ui.ok_and_wait(f"reclaimed {home_mod.format_bytes(freed)} · {removed} item(s)")


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
            accent = (cfg.tui or {}).get("accent") or "#c8a24e"
            model = cfg.model or "(no model)"
        except Exception:  # noqa: BLE001
            accent = "#c8a24e"
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
    if not name:
        raise click.ClickException("name required")
    try:
        home.validate_profile_name(name)
    except home.InvalidProfileName as e:
        raise click.ClickException(str(e))

    h = home.home_for(name)
    if h.exists() and any(h.iterdir()):
        raise click.ClickException(f"profile {name!r} already exists at {h}")

    _bootstrap(h)
    click.echo(f"created profile {name!r} at {h}")
    click.echo(f"use it with: alpi -p {name}")
    click.echo("")
    click.echo("Configure it:")
    click.echo(
        f"  alpi -p {name} setup                          # interactive (API keys + email)"
    )
    default_env = Path.home() / ".alpi" / ".env"
    if default_env.exists():
        click.echo("  # — or, to reuse the default profile's setup:")
        click.echo(f"  cp {default_env} {h / '.env'}")


@profile.command("remove")
@click.argument("name")
@click.option("--yes", is_flag=True, default=False,
              help="Skip the interactive confirmation prompt.")
@click.option("--force", is_flag=True, default=False,
              help="Uninstall an installed service first instead of refusing.")
def profile_remove(name: str, yes: bool, force: bool) -> None:
    """Permanently remove a profile directory after safety checks."""

    from alpi import ui

    if name in {"default", ""}:
        raise click.ClickException("the default profile cannot be removed")
    if "/" in name or name.startswith("."):
        raise click.ClickException(f"invalid profile name: {name!r}")

    h = home.home_for(name)
    if not h.exists():
        profiles_root = home._ROOT / "profiles"
        available = (
            [p.name for p in profiles_root.iterdir() if p.is_dir()]
            if profiles_root.exists()
            else []
        )
        raise click.ClickException(
            f"profile {name!r} does not exist{_suggest(name, available)}",
        )

    if not yes:
        summary = _profile_summary(h)
        ui.banner(f"Remove profile · {name}", subtitle=str(h))
        for line in summary:
            click.echo(f"  {line}")
        click.echo("")
        if not ui.confirm(
            f"Remove profile {name!r}? This cannot be undone.", default=False,
        ):
            ui.cancelled()
            return

    _ = force
    import time as _time
    trash_root = home._ROOT / ".trash"
    trash_root.mkdir(parents=True, exist_ok=True)
    archived = trash_root / f"{name}-{_time.strftime('%Y%m%d-%H%M%S')}"
    h.rename(archived)
    click.echo(f"archived profile {name!r} to {archived}")
    click.echo("(restore with `mv` if needed; auto-swept after 30 days from setup → Cleanup)")


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
        count = sum(1 for p in skills.rglob("SKILL.md"))
        if count:
            lines.append(f"skills:   {count} user-created")
    env = home_dir / ".env"
    if env.exists():
        lines.append(".env:     present (credentials will be deleted)")
    if not lines:
        lines.append("empty profile — nothing to lose.")
    return lines


def _delete_profile_status(h: Path, profile_name: str) -> str:
    return "Remove all data"


def _delete_profile_wizard(h: Path, profile_name: str) -> bool:
    """Return True if deleted; caller must exit the setup loop."""
    from alpi import ui

    ui.banner(ui.crumb("setup", "danger", f"delete {profile_name}"), subtitle=str(h), home=h)
    ui._console.print("")

    summary = _profile_summary(h)
    for line in summary:
        ui._console.print(f"  {line}")
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

    try:
        import time as _time
        trash_root = home._ROOT / ".trash"
        trash_root.mkdir(parents=True, exist_ok=True)
        archived = trash_root / f"{profile_name}-{_time.strftime('%Y%m%d-%H%M%S')}"
        h.rename(archived)
    except Exception as e:  # noqa: BLE001
        ui.fail_and_wait(f"rmtree failed: {e}")
        return False

    ui.ok_and_wait(f"profile '{profile_name}' deleted.")
    return True


@main.group()
def peers() -> None:
    """Manage ALP peer identities (spec: docs/ALP.md)."""


@peers.command("key")
@click.pass_context
def peers_key(ctx: click.Context) -> None:
    """Print this profile's ALP public key."""
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
    import base64

    from alpi.alp import peers as peers_mod

    original_id = peer_id
    peer_id = peer_id.strip().lower()
    if not peer_id:
        raise click.ClickException("peer id cannot be empty")
    if peer_id != original_id.strip():
        click.echo(f"id normalized to {peer_id!r}", err=True)
    pk = pubkey_b64.strip()
    try:
        raw = base64.b64decode(pk, validate=True)
    except Exception:
        raise click.ClickException(
            "invalid pubkey: expected base64-encoded Ed25519 public key"
        )
    if len(raw) != 32:
        raise click.ClickException(
            f"invalid pubkey: Ed25519 keys decode to 32 bytes (got {len(raw)})"
        )

    h: Path = ctx.obj["home"]
    peer = peers_mod.Peer(
        id=peer_id,
        pubkey=pk,
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
    """Remove a peer; one-sided — the remote profile retains its pin until they drop you too."""
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
            socket_path = peers_mod.local_socket_path(peer)
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


@peers.command("blob-put")
@click.argument("peer_id")
@click.argument("source", type=click.Path(path_type=Path, exists=True, dir_okay=False))
@click.pass_context
def peers_blob_put(ctx: click.Context, peer_id: str, source: Path) -> None:
    """Send a file to a peer and print its content hash."""
    import asyncio

    from alpi.alp import blobs
    from alpi.alp import client as alp_client

    h: Path = ctx.obj["home"]
    try:
        result = asyncio.run(blobs.put(h, peer_id, source))
    except (blobs.BlobError, alp_client.ClientError) as e:
        raise click.ClickException(str(e)) from e
    click.echo(f"{result['hash']}  {result['size']} bytes")


@peers.command("blob-get")
@click.argument("peer_id")
@click.argument("blob_hash")
@click.option("--output", "destination", required=True, type=click.Path(path_type=Path))
@click.pass_context
def peers_blob_get(
    ctx: click.Context,
    peer_id: str,
    blob_hash: str,
    destination: Path,
) -> None:
    """Retrieve a content-addressed file from a peer."""
    import asyncio

    from alpi.alp import blobs
    from alpi.alp import client as alp_client

    h: Path = ctx.obj["home"]
    try:
        result = asyncio.run(blobs.get(h, peer_id, blob_hash, destination))
    except (blobs.BlobError, alp_client.ClientError) as e:
        raise click.ClickException(str(e)) from e
    click.echo(f"{result['hash']}  {result['size']} bytes  {result['path']}")


@main.group()
def workgroup() -> None:
    """Manage ALP workgroups; hub verbs (create/kick) vs member verbs (join/post/pull/pause/resume/leave)."""


@workgroup.command("list")
@click.pass_context
def workgroup_list(ctx: click.Context) -> None:
    """Show workgroups this profile is hub of and member of."""
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
        click.echo("  role     hub")
        click.echo(f"  members  {len(wg.members)}")
        click.echo(f"  paused   {wg.meta.paused}")
        click.echo(f"  key v    {wg.meta.current_key_version}")
        if wg.meta.budget:
            click.echo(f"  budget   {wg.meta.budget}")
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
    click.echo("  role     member")
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
              help="Lifetime USD cap.")
@click.option("--briefing", default="",
              help="Initial briefing text. Hub can edit later via set-briefing.")
@click.option("--pipeline", default="",
              help="Ordered pipeline phase slugs, comma-separated "
                   "(e.g. 'intake,content,build,qa'). Empty = a normal "
                   "deliberation workgroup.")
@click.option("--quorum-timeout", type=int, default=0,
              help="Closure-quorum grace in seconds (0 = default 600). "
                   "Deterministic gate configs come from `workgroup launch`, not here.")
@click.pass_context
def workgroup_create(
    ctx: click.Context, name: str,
    members: tuple[str, ...], budget_usd: float | None,
    briefing: str, pipeline: str, quorum_timeout: int,
) -> None:
    """Create a workgroup as hub; members are pubkeys or pinned peer ids."""
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
    if budget_usd is not None:
        budget["max_usd"] = budget_usd

    hub_cfg = config.load(h)
    hub_bio = (hub_cfg.public_bio or "").strip()
    hub_voice = (hub_cfg.tools.tts.voice or "").strip()
    phases = [p.strip() for p in pipeline.split(",") if p.strip()]
    try:
        wg = wg_mod.create(
            h, name=name, hub_kp=load_or_generate(h),
            member_pubkeys=pubkeys, budget=budget,
            briefing=(briefing or "").strip(),
            pipeline=phases, quorum_timeout_seconds=quorum_timeout,
            hub_bio=hub_bio, hub_voice=hub_voice,
        )
    except ValueError as e:
        raise click.ClickException(str(e))
    pipe_note = f" · pipeline {'→'.join(wg.meta.pipeline)}" if wg.meta.pipeline else ""
    click.echo(f"created {wg.meta.id} · {len(wg.members)} members{pipe_note}")


@workgroup.command("launch")
@click.option("--recipe", "recipe_path", required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path),
              help="Path to a recipe .yaml file (git-tracked; read and sent by content).")
@click.option("--param", "param_pairs", multiple=True, metavar="KEY=VALUE",
              help="Recipe parameter. Repeat for each declared param, e.g. --param slug=casa-bahia.")
@click.option("--briefing", default=None, help="Override the recipe's briefing draft (the workgroup's meta briefing).")
@click.option("--input", "input_pairs", multiple=True, metavar="NAME=FILE",
              help="Recipe input; FILE's contents seed the declared input (e.g. --input brief=./brief.md). Repeat per input.")
@click.option("--assets", "assets_path", default=None, type=click.Path(exists=True, file_okay=False, path_type=Path),
              help="Folder of assets copied into the project's assets/ before kickoff.")
@click.pass_context
def workgroup_launch(
    ctx: click.Context, recipe_path: Path,
    param_pairs: tuple[str, ...], briefing: str | None,
    input_pairs: tuple[str, ...], assets_path: Path | None,
) -> None:
    """Launch a workgroup from a recipe file (clone+seed+create+kickoff, one operation)."""
    import asyncio

    from alpi.host import recipes as host_recipes

    h: Path = ctx.obj["home"]
    params: dict[str, str] = {}
    for pair in param_pairs:
        if "=" not in pair:
            raise click.ClickException(f"--param must be KEY=VALUE, got {pair!r}")
        k, v = pair.split("=", 1)
        params[k.strip()] = v
    inputs: dict[str, str] = {}
    for pair in input_pairs:
        name, sep, path = pair.partition("=")
        if not sep or not name.strip():
            raise click.ClickException(f"--input must be NAME=FILE, got {pair!r}")
        f = Path(path)
        if not f.is_file():
            raise click.ClickException(f"--input {name.strip()}: file not found: {path}")
        inputs[name.strip()] = f.read_text()
    try:
        result = asyncio.run(host_recipes.launch(
            h, recipe_path.read_text(), params,
            briefing_override=briefing, recipe_id=recipe_path.stem,
            inputs=inputs, assets_src=assets_path,
        ))
    except ValueError as e:
        raise click.ClickException(str(e))
    proj = f" · project {result['project_path']}" if result.get("project_path") else ""
    click.echo(f"launched {result['workgroup_id']}{proj}")


@workgroup.command("join")
@click.argument("hub_peer_id")
@click.argument("wg_id")
@click.pass_context
def workgroup_join(ctx: click.Context, hub_peer_id: str, wg_id: str) -> None:
    """Subscribe to a remote workgroup; hub_peer_id must be a pinned peer."""
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
    """Pause a workgroup (hub-only; idempotent)."""
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
    """Leave a workgroup; hub rotates the group key on remaining members."""
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
    peer = peers_mod.get_by_id(h, member_pubkey)
    target = peer.pubkey if peer else member_pubkey
    try:
        updated = wg_mod.kick(h, wg_id, target)
    except ValueError as e:
        raise click.ClickException(str(e))
    click.echo(f"kicked + rekeyed · v{updated.meta.current_key_version} "
               f"({len(updated.members)} members remaining)")


@workgroup.command("add-member")
@click.argument("wg_id")
@click.argument("member")
@click.pass_context
def workgroup_add_member(ctx: click.Context, wg_id: str, member: str) -> None:
    """Hub-side: invite a new member (pubkey or pinned peer id) and rotate the group key."""
    from alpi.alp import peers as peers_mod
    from alpi.alp import workgroup as wg_mod
    from alpi.alp import workgroup_setup as wg_setup

    h: Path = ctx.obj["home"]
    peer = peers_mod.get_by_id(h, member)
    target = peer.pubkey if peer else member
    try:
        updated = wg_mod.add_member(h, wg_id, target)
    except ValueError as e:
        raise click.ClickException(str(e))
    wg_setup._grant_workgroup_verbs(h, [target])
    click.echo(f"added + rekeyed · v{updated.meta.current_key_version} "
               f"({len(updated.members)} members)")


@workgroup.command("remove")
@click.argument("wg_id")
@click.option("--yes", is_flag=True, default=False,
              help="Skip the confirmation prompt.")
@click.pass_context
def workgroup_remove(ctx: click.Context, wg_id: str, yes: bool) -> None:
    """Hub-only: delete a workgroup permanently and purge local subscriptions."""
    from alpi.alp import workgroup as wg_mod
    from alpi.alp.keys import load_or_generate

    h: Path = ctx.obj["home"]
    wg = wg_mod.load(h, wg_id)
    if wg is None:
        raise click.ClickException(f"workgroup {wg_id!r} not found")
    own_pubkey = load_or_generate(h).pubkey_b64()
    if wg.meta.hub_pubkey != own_pubkey:
        raise click.ClickException("only the hub can remove this workgroup")
    if not yes and not click.confirm(
        f"Delete workgroup {wg.meta.name} permanently? "
        f"This wipes the transcript and all member entries.",
        default=False,
    ):
        raise click.ClickException("aborted")
    try:
        purged = wg_mod.remove(h, wg_id)
    except OSError as e:
        raise click.ClickException(str(e))

    click.echo(f"removed {wg_id}")
    if purged:
        click.echo(
            f"  also purged subscriptions on: {', '.join(sorted(set(purged)))}"
        )


@workgroup.command("update")
@click.argument("wg_id")
@click.option("--briefing", default=None,
              help="Replace the briefing text.")
@click.option("--budget-usd", type=float, default=None,
              help="Set the lifetime USD cap.")
@click.option("--clear-budget", is_flag=True, default=False,
              help="Remove any lifetime budget.")
@click.option("--pipeline", default=None,
              help="Replace ordered pipeline phase slugs, comma-separated. "
                   "Pass an empty string to clear.")
@click.pass_context
def workgroup_update(
    ctx: click.Context, wg_id: str, briefing: str | None,
    budget_usd: float | None, clear_budget: bool, pipeline: str | None,
) -> None:
    """Hub-only: edit a workgroup's mutable metadata."""
    from alpi.alp import workgroup as wg_mod
    from alpi.alp.keys import load_or_generate

    h: Path = ctx.obj["home"]
    wg = wg_mod.load(h, wg_id)
    if wg is None:
        raise click.ClickException(f"workgroup {wg_id!r} not found")
    own_pubkey = load_or_generate(h).pubkey_b64()
    if wg.meta.hub_pubkey != own_pubkey:
        raise click.ClickException("only the hub can edit this workgroup")
    if budget_usd is not None and clear_budget:
        raise click.ClickException(
            "--budget-usd and --clear-budget are mutually exclusive"
        )
    changes: list[str] = []
    if briefing is not None:
        wg.meta.briefing = (briefing or "").strip()
        changes.append(f"briefing={len(wg.meta.briefing)} chars")
    if pipeline is not None:
        try:
            wg.meta.pipeline = wg_mod._normalize_pipeline(
                [p.strip() for p in pipeline.split(",") if p.strip()],
            )
        except ValueError as e:
            raise click.ClickException(str(e))
        changes.append(
            "pipeline=" + ("→".join(wg.meta.pipeline) if wg.meta.pipeline else "cleared"),
        )
    if clear_budget:
        wg.meta.budget = {}
        changes.append("budget cleared")
    elif budget_usd is not None:
        if budget_usd <= 0:
            raise click.ClickException("--budget-usd must be > 0")
        wg.meta.budget = wg_mod._validate_budget({"max_usd": budget_usd})
        changes.append(f"budget=${budget_usd:.2f}")
    if not changes:
        raise click.ClickException(
            "nothing to update — pass --briefing, --pipeline, --budget-usd or --clear-budget"
        )
    wg_mod._save_meta(wg_mod._wg_dir(h, wg_id), wg.meta)
    click.echo(f"updated {wg_id} · {' · '.join(changes)}")


@workgroup.command("turns")
@click.argument("wg_id", required=False)
@click.option("-n", "--limit", type=int, default=20,
              help="Show only the last N events.")
@click.option("-f", "--follow", is_flag=True,
              help="Stream new events as they're appended (like tail -f).")
@click.pass_context
def workgroup_turns(
    ctx: click.Context, wg_id: str | None, limit: int, follow: bool,
) -> None:
    """Show the workgroup turn telemetry log for this profile."""
    import json
    import time as _time
    from alpi import service as svc

    h: Path = ctx.obj["home"]
    p = svc.turn_log_path(h)
    if not p.exists():
        click.echo("no turn log yet (no workgroup turn has been dispatched).")
        return

    def _read_all() -> list[dict]:
        out = []
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            if wg_id and e.get("wg_id") != wg_id:
                continue
            out.append(e)
        return out

    def _fmt(e: dict) -> str:
        ts = e.get("ts", "")
        ev = e.get("event", "?")
        wg = e.get("wg_name") or e.get("wg_id", "?")
        col = {"start": "\033[36m", "end": "\033[32m",
               "timeout": "\033[31m", "spawn-failed": "\033[31m"}.get(ev, "")
        rst = "\033[0m" if col else ""
        bits = [f"{ts}  {col}{ev:<7}{rst}  {wg}"]
        if "reason" in e:
            bits.append(f"reason={e['reason']}")
        if "pid" in e:
            bits.append(f"pid={e['pid']}")
        if "duration_s" in e:
            bits.append(f"{e['duration_s']}s")
        if "posts_added" in e:
            bits.append(f"+{e['posts_added']} posts")
        if "rc" in e and e["rc"] != 0:
            bits.append(f"rc={e['rc']}")
        if e.get("killed"):
            bits.append("KILLED")
        if "error" in e and e["error"]:
            bits.append(f"err={e['error'][:80]}")
        return " · ".join(bits)

    events = _read_all()
    for e in events[-limit:]:
        click.echo(_fmt(e))

    if not follow:
        return

    seen = len(events)
    try:
        while True:
            _time.sleep(1)
            cur = _read_all()
            if len(cur) > seen:
                for e in cur[seen:]:
                    click.echo(_fmt(e))
                seen = len(cur)
    except KeyboardInterrupt:
        click.echo("")


@main.group("memory")
def memory_group() -> None:
    """Operator-facing memory tooling — review and promote durable facts."""


@memory_group.command("promote")
@click.option(
    "--apply-all", is_flag=True, default=False,
    help="Apply every pending candidate without prompting (CI use; risky).",
)
@click.option(
    "--discard-all", is_flag=True, default=False,
    help="Drop every pending candidate without prompting.",
)
@click.pass_context
def cmd_memory_promote(ctx: click.Context, apply_all: bool, discard_all: bool) -> None:
    """Interactively review the memory promotion queue."""
    from alpi import promotion as _promotion
    from alpi.tools.memory import Memory

    h: Path = ctx.obj["home"]
    pending = _promotion.list_pending(h)
    if not pending:
        click.echo("(no pending promotion candidates)")
        return

    if apply_all and discard_all:
        raise click.ClickException("pass --apply-all OR --discard-all, not both")

    click.echo(
        f"{len(pending)} pending candidate(s) "
        f"(cap={_promotion.MAX_PENDING}, expire after {_promotion.MAX_AGE_DAYS}d)"
    )
    applied = discarded = skipped = 0

    for cand in pending:
        click.echo("")
        click.echo(f"  [{cand.id}] {cand.target}  conf={cand.confidence}  "
                   f"source={cand.source}  session={cand.session_id[:8]}")
        click.echo(f"    text: {cand.text}")
        if cand.warnings:
            click.echo(f"    warnings: {'; '.join(cand.warnings)}")

        if apply_all:
            choice = "a"
        elif discard_all:
            choice = "d"
        else:
            choice = click.prompt(
                "  [a]pply / [d]iscard / [s]kip / [q]uit",
                type=click.Choice(["a", "d", "s", "q"], case_sensitive=False),
                default="s",
                show_default=False,
            ).lower()

        if choice == "q":
            click.echo("quit")
            break
        if choice == "s":
            skipped += 1
            continue
        if choice == "d":
            _promotion.discard(h, cand.id)
            discarded += 1
            click.echo(f"  discarded {cand.id}")
            continue
        if choice == "a":
            r = Memory().run(
                action="add",
                target=cand.target,
                content=cand.text,
                confidence=cand.confidence,
            )
            if r.ok:
                _promotion.remove_and_return(h, cand.id)
                applied += 1
                click.echo(f"  applied {cand.id} → {cand.target}")
            else:
                click.echo(f"  ERROR not applied: {r.error}")

    click.echo("")
    click.echo(f"applied={applied}  discarded={discarded}  skipped={skipped}")


@memory_group.command("audit")
@click.option(
    "--json", "as_json", is_flag=True, default=False,
    help="Emit the full report as JSON (machine-readable for memory audit tooling).",
)
@click.pass_context
def cmd_memory_audit(ctx: click.Context, as_json: bool) -> None:
    """Read-only memory quality report: usage pressure, low-confidence
    stale entries, near-duplicate clusters at multiple thresholds,
    operational-state leaks, promotion-queue backlog, compaction stats."""
    from alpi import memory_audit, ui

    h: Path = ctx.obj["home"]
    report = memory_audit.run_audit(h)

    if as_json:
        click.echo(_audit_to_json(report))
        return

    _render_audit(report, ui._console)


def _audit_to_json(report) -> str:
    """Serialise an ``AuditReport`` to JSON. Frozen schema for OPS.1."""
    import json
    from dataclasses import asdict
    return json.dumps(asdict(report), indent=2, default=str)


def _render_audit(report, console) -> None:
    """Rich-formatted audit. Keep concise so the operator can scan it whole."""
    from rich.table import Table

    console.print("[b]memory audit[/b]")
    console.print("")

    # Usage
    console.print("[dim]Usage[/dim]")
    t = Table(show_header=True, header_style="dim", box=None, padding=(0, 1))
    t.add_column("file")
    t.add_column("used", justify="right")
    t.add_column("limit", justify="right")
    t.add_column("%", justify="right")
    for u in report.usage:
        pct = "—" if u.percent is None else f"{u.percent * 100:.0f}%"
        limit = "—" if u.limit is None else str(u.limit)
        style = "yellow" if u.percent is not None and u.percent >= 0.80 else ""
        t.add_row(u.name, str(u.used), limit, pct, style=style)
    console.print(t)
    console.print("")

    # Stale / low-confidence
    console.print(f"[dim]Low-confidence stale ({len(report.stale)})[/dim]")
    if report.stale:
        for s in report.stale[:10]:
            console.print(f"  [yellow]·[/yellow] {s.file}#{s.index} "
                          f"captured={s.captured} — {s.text}")
        if len(report.stale) > 10:
            console.print(f"  [dim]… {len(report.stale) - 10} more[/dim]")
    else:
        console.print("  [green]none[/green]")
    console.print("")

    # Duplicate clusters per threshold
    console.print("[dim]Duplicate clusters (token-overlap threshold sweep)[/dim]")
    for d in report.duplicates:
        n = len(d.clusters)
        affected = sum(len(c.members) for c in d.clusters)
        ending = "y" if affected == 1 else "ies"
        summary = f"{n} cluster(s), {affected} entr{ending}"
        line = f"  threshold={d.threshold:.1f} → "
        if n == 0:
            line += f"[green]{summary}[/green]"
        else:
            line += summary
        console.print(line)
        for c in d.clusters[:3]:
            ids = ", ".join("#" + str(i) for i, _ in c.members)
            console.print(f"      [dim]{c.file}: {ids}[/dim]")
        if len(d.clusters) > 3:
            console.print(f"      [dim]… {len(d.clusters) - 3} more clusters[/dim]")
    console.print("")

    # Operational state
    console.print(f"[dim]Operational-state leaks ({len(report.operational)})[/dim]")
    if report.operational:
        for op in report.operational[:10]:
            console.print(f"  [yellow]·[/yellow] {op.file}#{op.index} "
                          f"({op.warning}) — {op.text}")
        if len(report.operational) > 10:
            console.print(f"  [dim]… {len(report.operational) - 10} more[/dim]")
    else:
        console.print("  [green]none[/green]")
    console.print("")

    # Promotion queue
    p = report.promotion
    console.print("[dim]Promotion queue[/dim]")
    if p.pending == 0:
        console.print("  [green]empty[/green]")
    else:
        age = f"oldest {p.oldest_age_days:.1f}d" if p.oldest_age_days is not None else "unknown age"
        by = ", ".join(f"{k}={v}" for k, v in sorted(p.by_target.items()))
        console.print(f"  {p.pending} pending · {age} · {by}")
    console.print("")

    # Compaction
    c = report.compaction
    console.print("[dim]Compaction[/dim]")
    if c.events_30d == 0:
        console.print("  [dim]no events in last 30d[/dim]")
    else:
        ratio = "—" if c.avg_ratio is None else f"{c.avg_ratio * 100:.0f}%"
        fired = "—" if c.fired_pct is None else f"{c.fired_pct * 100:.0f}%"
        console.print(
            f"  {c.events_7d} in 7d / {c.events_30d} in 30d · "
            f"avg ratio after/before={ratio} · fired={fired}"
        )
    console.print("")

    # Warnings footer
    if report.pressure_warnings:
        console.print("[yellow]pressure[/yellow]")
        for w in report.pressure_warnings:
            console.print(f"  · {w}")
    else:
        console.print("[green]no pressure warnings[/green]")


@main.command("digest")
@click.option(
    "--since", "window", default="7d",
    help="time window for stats: e.g. 7d, 24h, 30m (default 7d).",
)
@click.option(
    "--json", "as_json", is_flag=True, default=False,
    help="emit the full report as JSON for automation / chaining.",
)
@click.pass_context
def cmd_digest(ctx: click.Context, window: str, as_json: bool) -> None:
    """Read-only evidence digest aggregating existing on-disk signals:
    broken tools, skill usage, memory backlog, compaction
    rate. Sibling to ``alpi doctor`` — doctor is "is this healthy now?",
    digest is "what happened in the last N days?". No LLM, no dashboard,
    no recommendations."""
    from alpi import ops_digest, ui

    try:
        window_days = ops_digest.parse_window(window)
    except ValueError as e:
        raise click.ClickException(str(e))

    h: Path = ctx.obj["home"]
    report = ops_digest.run_digest(h, window_days=window_days)

    if as_json:
        click.echo(_digest_to_json(report))
        return

    _render_digest(report, ui._console)


def _digest_to_json(report) -> str:
    """Stable schema for downstream consumers — future OPS automation or external dashboards parsing the JSON output."""
    import json
    from dataclasses import asdict
    return json.dumps(asdict(report), indent=2, default=str)


def _render_digest(report, console) -> None:
    """Rich-formatted digest, organised so the operator can decide what to act on in a single scan."""

    console.print(f"[b]digest[/b] · window: {report.window_days:.1f}d")
    console.print("")

    # Tools
    t = report.tools
    console.print("[dim]Tools[/dim]")
    if t.unavailable:
        for name, reason in t.unavailable:
            console.print(f"  [yellow]·[/yellow] {name} — {reason}")
        console.print(f"  [dim]{t.total - len(t.unavailable)} other tools available[/dim]")
    else:
        console.print(f"  [green]{t.total} tools available[/green]")
    console.print("")

    # Skills
    s = report.skills
    console.print("[dim]Skills[/dim]")
    if s.total == 0:
        console.print("  [dim]no usage recorded[/dim]")
    else:
        bs = s.by_state
        console.print(
            f"  {s.total} tracked · "
            f"{bs.get('active', 0)} active / "
            f"{bs.get('stale', 0)} stale / "
            f"{bs.get('archived', 0)} archived"
        )
        if s.top_used:
            top = ", ".join(f"{n} ({c})" for n, c in s.top_used)
            console.print(f"  [dim]top used: {top}[/dim]")
        for name, state in s.pinned_cold:
            console.print(
                f"  [yellow]·[/yellow] {name} — pinned but {state}"
            )
    console.print("")

    # Memory
    m = report.memory
    console.print("[dim]Memory[/dim]")
    if m.promotion_pending == 0:
        console.print("  [dim]no pending promotions[/dim]")
    else:
        age = (
            f"oldest {m.promotion_oldest_age_days:.1f}d"
            if m.promotion_oldest_age_days is not None else "unknown age"
        )
        by = ", ".join(
            f"{k}={v}" for k, v in sorted(m.promotion_by_target.items())
        )
        console.print(f"  {m.promotion_pending} pending · {age} · {by}")
    for w in m.pressure_warnings:
        console.print(f"  [yellow]·[/yellow] {w}")
    console.print("")

    # Compaction
    c = report.compaction
    console.print("[dim]Compaction[/dim]")
    if c.events_in_window == 0:
        console.print(f"  [dim]no events in last {report.window_days:.1f}d[/dim]")
    else:
        ratio = "—" if c.avg_ratio is None else f"{c.avg_ratio * 100:.0f}%"
        fired = "—" if c.fired_pct is None else f"{c.fired_pct * 100:.0f}%"
        console.print(
            f"  {c.events_in_window} event(s) · "
            f"avg ratio after/before={ratio} · fired={fired}"
        )

    # Runs
    r = report.runs
    console.print("")
    console.print("[dim]Runs[/dim]")
    if r.total == 0:
        console.print("  [dim]no run records yet[/dim]")
    else:
        by_kind = ", ".join(f"{k}={v}" for k, v in sorted(r.by_kind.items()))
        not_ok = sum(v for o, v in r.by_outcome.items() if o != "ok")
        console.print(f"  {r.total} recorded · {by_kind} · {not_ok} not-ok")
        for f in r.recent_failures:
            reason = f.get("timeout_reason") or f.get("last_tool") or f.get("output_tail") or ""
            console.print(
                f"  [red]·[/red] {f.get('kind')} {f.get('outcome')}"
                f"{(' — ' + reason) if reason else ''}"
            )
        for sl in r.slowest:
            tail = sl.get("last_tool") or sl.get("timeout_reason") or ""
            console.print(
                f"  [yellow]·[/yellow] slow {sl.get('kind')} "
                f"{float(sl.get('elapsed_s') or 0.0):.0f}s"
                f"{(' — ' + tail) if tail else ''}"
            )


if __name__ == "__main__":
    main(obj={})
    sys.exit(0)
