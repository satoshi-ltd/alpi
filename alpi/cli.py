"""alpi — CLI entry point."""

from __future__ import annotations

import asyncio
import os
import sys
from importlib import resources
from pathlib import Path
from typing import Any

import click

from alpi import __version__, config, home, memory
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


def _continue_specific_session(
    engine: Engine, h: Path, session_id: str, subdir: str = "sessions",
) -> bool:
    """Resume a session by id; subdir splits desktop ('sessions/') from gateway ('gateway/sessions/')."""
    path = h / subdir / f"{session_id}.json"
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
    persist: bool = True,
) -> None:
    import json
    from alpi import session_map

    _bootstrap(h)
    cfg = config.load(h)
    engine = Engine(home=h, cfg=cfg)

    if resume_chat_id:
        engine.session.subdir = "gateway/sessions"
        existing = session_map.get(h, resume_chat_id)
        if existing:
            _continue_specific_session(
                engine, h, existing, subdir="gateway/sessions",
            )

    from alpi.alp import mention as alp_mention
    parsed = alp_mention.parse(user_text, home=h)
    if parsed is not None:
        import asyncio as _aio, time as _t
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
        if persist and resume_chat_id:
            try:
                session_map.set(h, resume_chat_id, engine.session.id)
            except Exception:  # noqa: BLE001
                pass
        if emit_events:
            sys.stdout.write(json.dumps({"kind": "reply", "text": reply}) + "\n")
        else:
            sys.stdout.write(reply + "\n")
        sys.stdout.flush()
        return

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
        if ev.kind == "assistant_done" and ev.final and ev.text.strip():
            parts.append(ev.text)
        elif ev.kind == "error" and not emit_events:
            parts.append(f"[error] {ev.text}")

    import signal as _signal

    def _on_sigint(_signum, _frame):
        engine.request_interrupt()

    prev_handler = _signal.signal(_signal.SIGINT, _on_sigint)
    try:
        engine.run_turn(user_text, emit=sink)
    finally:
        _signal.signal(_signal.SIGINT, prev_handler)
    if persist:
        try:
            engine.save_session()
        except Exception:  # noqa: BLE001
            pass

    if persist and resume_chat_id:
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


class _OrderedGroup(click.Group):
    """List subcommands in _ORDER (user-frequency) instead of Click's default alphabetical."""

    _ORDER = [
        "chat",
        "setup",
        "doctor",
        "update",
        "diff",
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
    no_save: bool,
    resume_chat: str | None,
    continue_last: bool,
) -> None:
    """Launch the TUI, or run one turn with ``--once "text"``."""
    h: Path = ctx.obj["home"]
    if input_text is not None:
        _run_once(
            h,
            input_text,
            emit_events=emit_events,
            resume_chat_id=resume_chat,
            persist=not no_save,
        )
    else:
        _run_chat(h, continue_last=continue_last)


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


@main.group()
def gateway() -> None:
    """Inspect external messaging gateways."""


@gateway.command("probe")
@click.argument("name", type=click.Choice(["telegram", "imap", "gmail", "matrix"]))
@click.pass_context
def gateway_probe(ctx: click.Context, name: str) -> None:
    """Probe a gateway and print JSON ``{status, reason?}``."""
    import json
    from alpi import home as home_mod

    h: Path = ctx.obj["home"]
    env = _read_profile_env(h)
    out: dict[str, str] = {}
    if name == "telegram":
        token = env.get("TELEGRAM_BOT_TOKEN", "").strip()
        if not token:
            out = {"status": "off"}
        else:
            try:
                import urllib.request as _ur
                with _ur.urlopen(
                    f"https://api.telegram.org/bot{token}/getMe", timeout=2.0
                ) as resp:
                    body = json.loads(resp.read().decode("utf-8"))
                if body.get("ok"):
                    out = {"status": "on"}
                else:
                    out = {"status": "error", "reason": "token rejected"}
            except Exception as e:  # noqa: BLE001
                out = {"status": "error", "reason": str(e)[:80]}
    elif name == "imap":
        addr = env.get("IMAP_ADDRESS", "").strip()
        if not addr:
            out = {"status": "off"}
        else:
            host = env.get("IMAP_HOST", "").strip() or "imap.gmail.com"
            port = int(env.get("IMAP_PORT", "993").strip() or "993")
            try:
                import socket as _s
                with _s.create_connection((host, port), timeout=2.0):
                    out = {"status": "on"}
            except Exception as e:  # noqa: BLE001
                out = {"status": "error", "reason": str(e)[:80]}
    elif name == "gmail":
        client_id = env.get("GMAIL_CLIENT_ID", "").strip()
        token_path = h / "secrets" / "gmail_token.json"
        if not client_id and not token_path.exists():
            out = {"status": "off"}
        elif not token_path.exists():
            out = {"status": "error", "reason": "no token file"}
        else:
            try:
                tok = json.loads(token_path.read_text())
                expiry = tok.get("expiry") or tok.get("expires_at")
                refresh = tok.get("refresh_token")
                if not refresh and expiry:
                    import datetime as _dt
                    exp = _dt.datetime.fromisoformat(
                        expiry.replace("Z", "+00:00")
                    )
                    if exp < _dt.datetime.now(_dt.timezone.utc):
                        out = {"status": "error", "reason": "token expired"}
                    else:
                        out = {"status": "on"}
                else:
                    out = {"status": "on"}
            except Exception as e:  # noqa: BLE001
                out = {"status": "error", "reason": str(e)[:80]}
    elif name == "matrix":
        token = env.get("MATRIX_ACCESS_TOKEN", "").strip()
        url = env.get("MATRIX_HOMESERVER_URL", "").strip()
        if not token or not url:
            out = {"status": "off"}
        else:
            try:
                import urllib.request as _ur
                req = _ur.Request(
                    f"{url.rstrip('/')}/_matrix/client/r0/account/whoami",
                    headers={"Authorization": f"Bearer {token}"},
                )
                with _ur.urlopen(req, timeout=2.0) as resp:
                    body = json.loads(resp.read().decode("utf-8"))
                if body.get("user_id"):
                    out = {"status": "on"}
                else:
                    out = {"status": "error", "reason": "whoami missing user_id"}
            except Exception as e:  # noqa: BLE001
                out = {"status": "error", "reason": str(e)[:80]}
    click.echo(json.dumps(out))


@gateway.command("remove")
@click.argument("name", type=click.Choice(["telegram", "imap", "gmail", "matrix"]))
@click.option("--yes", is_flag=True, default=False,
              help="Skip the confirmation prompt.")
@click.pass_context
def gateway_remove(ctx: click.Context, name: str, yes: bool) -> None:
    """Drop env vars (and Gmail token file) for one configured gateway."""
    from alpi.model_selector import _remove_env_key

    h: Path = ctx.obj["home"]
    cfg = config.load(h)
    if not yes:
        if not click.confirm(
            f"Remove {name} gateway? Drops env vars and you can re-add later.",
            default=False,
        ):
            click.echo("aborted")
            return
    for key in _GATEWAY_ENV_KEYS.get(name, ()):
        _remove_env_key(cfg.env_path, key)
    if name == "gmail":
        token_file = h / "secrets" / "gmail_token.json"
        if token_file.exists():
            try:
                token_file.unlink()
            except OSError:
                pass
    click.echo(f"removed {name} gateway · restart daemon to apply")


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
    """Configure TTS voice + autoplay for this profile."""


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


@voice.command("autoplay")
@click.argument("state", type=click.Choice(["on", "off"]))
@click.pass_context
def voice_autoplay(ctx: click.Context, state: str) -> None:
    """Toggle speaker playback when the assistant emits TTS."""
    h: Path = ctx.obj["home"]
    cfg = config.load(h)
    cfg.tools.tts.autoplay = state == "on"
    config.save(cfg)
    click.echo(f"autoplay {state}")


_VOICE_TEST_PHRASES = {
    "en": "Hello, I'm Alpi.",
    "es": "Hola, soy Alpi.",
    "fr": "Bonjour, je suis Alpi.",
    "de": "Hallo, ich bin Alpi.",
    "it": "Ciao, sono Alpi.",
    "pt": "Olá, sou Alpi.",
}


@voice.command("test")
@click.option("--voice", "voice_override", default=None,
              help="Override the configured voice id for this preview.")
@click.pass_context
def voice_test(ctx: click.Context, voice_override: str | None) -> None:
    """Synthesize a short greeting in the voice's locale and play it."""
    import asyncio
    import tempfile
    from alpi.tools.tts import _player_cmd, _synthesize

    h: Path = ctx.obj["home"]
    cfg = config.load(h)
    voice_id = (voice_override or cfg.tools.tts.voice or "en-US-AriaNeural").strip()
    lang = voice_id.split("-", 1)[0].lower() if "-" in voice_id else "en"
    phrase = _VOICE_TEST_PHRASES.get(lang, _VOICE_TEST_PHRASES["en"])

    if _player_cmd() is None:
        raise click.ClickException(
            "no audio player found — install afplay (macOS), paplay/aplay/ffplay (Linux), or PowerShell (Windows)"
        )
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        out = Path(tmp.name)
    try:
        asyncio.run(_synthesize(phrase, voice_id, out))
        import subprocess as _sp
        cmd = _player_cmd()
        _sp.run([*cmd, str(out)], capture_output=True, timeout=30)
    finally:
        try:
            out.unlink()
        except OSError:
            pass
    click.echo(f"played: {phrase}")


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
    from alpi.model_selector import _remove_env_key

    h: Path = ctx.obj["home"]
    cfg = config.load(h)
    _remove_env_key(cfg.env_path, key.strip())
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


@main.command("doctor")
@click.pass_context
def doctor_cmd(ctx: click.Context) -> None:
    """Read-only health check of the current profile."""
    from alpi import doctor, ui

    h: Path = ctx.obj["home"]
    profile: str = ctx.obj.get("profile") or "default"
    checks = doctor.run_and_render(ui._console, h, profile, __version__)
    ctx.exit(doctor.exit_code(checks))


@main.command("logs")
@click.option(
    "--source",
    type=click.Choice(["service", "gateway", "schedule", "agent", "approval"]),
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
    """Interactive setup — model, gateways, MCPs."""
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
            ("Voice", "voice", _voice_status(cfg)),
            ("MCPs", "mcps", _mcp_status(h)),

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
        if profile_name == "default" and not _is_umbrel():
            items.append(("Daemon", "daemon", _daemon_lifecycle_status()))
        items += [
            ("Subsystems", "subsystems", _subsystems_summary(h)),
            ("Gateways", "gateways", _gateways_status(h)),
        ]
        if profile_name == "default":
            items.append(("Devices", "devices", _devices_status(h)))
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
        elif choice == "subsystems":
            _subsystems_wizard(h, profile_name)
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
        elif choice == "devices":
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


def _is_umbrel() -> bool:
    return os.environ.get("ALPI_PLATFORM") == "umbrel"


_GATEWAY_ENV_KEYS = {
    "telegram": ("TELEGRAM_BOT_TOKEN", "TELEGRAM_ALLOWED_CHAT_IDS"),
    "imap": (
        "IMAP_ADDRESS", "IMAP_PASSWORD",
        "IMAP_HOST", "IMAP_PORT",
        "SMTP_HOST", "SMTP_PORT",
        "IMAP_ALLOWED_SENDERS",
    ),
    "gmail": (
        "GMAIL_CLIENT_ID", "GMAIL_CLIENT_SECRET", "GMAIL_ALLOWED_SENDERS",
    ),
    "matrix": (
        "MATRIX_HOMESERVER_URL", "MATRIX_USER_ID", "MATRIX_ACCESS_TOKEN",
        "MATRIX_DEVICE_ID", "MATRIX_ALLOWED_ROOMS", "MATRIX_ALLOWED_SENDERS",
    ),
}


def _gateways_setup(h: Path) -> None:
    from alpi import ui

    while True:
        configured = _configured_gateways(h)
        items = [
            ("Telegram", "telegram", _telegram_status(h)),
            ("IMAP", "imap", _email_status(h)),
            ("Gmail", "gmail", _gmail_status(h)),
            ("Matrix", "matrix", _matrix_status(h)),
        ]
        if configured:
            items.append(None)
            items.append(("Remove gateway", "remove",
                          f"drop one of: {', '.join(configured)}"))
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
        elif choice == "matrix":
            from alpi.gateway.matrix_setup import run as matrix_setup

            matrix_setup(h)
        elif choice == "remove":
            _remove_gateway_flow(h, configured)


def _configured_gateways(h: Path) -> list[str]:
    """Subset of {telegram, imap, gmail} that has any state worth wiping."""
    env = _read_profile_env(h)
    out: list[str] = []
    if env.get("TELEGRAM_BOT_TOKEN"):
        out.append("telegram")
    if env.get("IMAP_ADDRESS"):
        out.append("imap")
    if env.get("GMAIL_CLIENT_ID") or (h / "secrets" / "gmail_token.json").exists():
        out.append("gmail")
    if env.get("MATRIX_ACCESS_TOKEN"):
        out.append("matrix")
    return out


def _remove_gateway_flow(h: Path, configured: list[str]) -> None:
    """Drop env vars (and Gmail token) for one configured gateway."""
    from alpi import ui
    from alpi.model_selector import _remove_env_key

    items = [(name, name, _gateway_summary(h, name)) for name in configured]
    target = ui.menu(
        ui.crumb("setup", "gateways", "remove"),
        items,
        subtitle="pick the gateway to disconnect",
        home=h,
        close="Back",
    )
    if target is None:
        return
    if not ui.confirm(
        f"Remove {target} gateway? Drops env vars; you can re-add later.",
        default=False,
    ):
        return ui.cancelled()

    for key in _GATEWAY_ENV_KEYS.get(target, ()):
        _remove_env_key(h / ".env", key)
    if target == "gmail":
        token_file = h / "secrets" / "gmail_token.json"
        if token_file.exists():
            try:
                token_file.unlink()
            except OSError:
                pass
    ui.ok_and_wait(
        f"removed {target} — restart the service for the change to take effect",
    )


def _gateway_summary(h: Path, name: str) -> str:
    if name == "telegram":
        return _telegram_status(h)
    if name == "imap":
        return _email_status(h)
    if name == "gmail":
        return _gmail_status(h)
    if name == "matrix":
        return _matrix_status(h)
    return ""


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

    if _is_umbrel():
        ui.banner(ui.crumb("setup", "daemon"), subtitle="managed by Umbrel", home=h)
        ui.dim(
            "On Umbrel the container entrypoint starts and supervises the "
            "daemon. Use the Umbrel app restart or update flow instead of "
            "systemd or launchd controls here.",
        )
        ui.ok_and_wait("daemon lifecycle is managed by Umbrel")
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

    if os.environ.get("ALPI_PLATFORM") == "umbrel":
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
    if _is_umbrel():
        return f"managed by Umbrel · pid {pid}" if pid is not None else "managed by Umbrel"
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

_SERVICES_WIZARD_COPY_UMBREL = (
    "Which services the Alpi daemon runs for THIS profile.\n"
    "On Umbrel the container entrypoint manages the daemon itself;\n"
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
        if _is_umbrel():
            head = (
                f"daemon: managed by Umbrel · pid {running_pid}" if running_pid
                else "daemon: managed by Umbrel"
            )
            copy = _SERVICES_WIZARD_COPY_UMBREL
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
            (("Gateway · " + _on_off(on_subsystems["gateway"])),
             "toggle-gateway", _gateways_status(h)),
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
        items.append(ui.Heading("ALP"))
        items.append(("Peer TCP listener", "tcp",
                      _alp_tcp_label(h)))

        choice = ui.menu("", items, home=h, close="Back")
        if choice is None:
            return
        try:
            if choice in (
                "toggle-gateway", "toggle-schedule", "toggle-alp",
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
            elif choice == "tcp":
                _alp_tcp_port_setup(h)
        except Exception as e:  # noqa: BLE001
            ui.fail_and_wait(str(e))


_service_wizard = _subsystems_wizard


def _on_off(b: bool) -> str:
    return "on" if b else "off"


def _alp_subsystem_status(h: Path) -> str:
    from alpi import config as cfg_mod
    cfg = cfg_mod.load(h)
    port = (cfg.alp or {}).get("tcp_port")
    return f"unix + tcp :{port}" if port else "unix socket only"


def _alp_tcp_label(h: Path) -> str:
    from alpi import config as cfg_mod
    cfg = cfg_mod.load(h)
    cfg_alp = cfg.alp or {}
    port = cfg_alp.get("tcp_port")
    host = cfg_alp.get("tcp_host") or "127.0.0.1"
    return f"{host}:{port} (Noise_XK)" if port else "not bound (Unix only)"


def _alp_tcp_port_setup(h: Path) -> None:
    """Configure the optional TCP listener used by remote ALP peers."""
    from alpi import config as cfg_mod
    from alpi import ui

    cfg = cfg_mod.load(h)
    current_port = (cfg.alp or {}).get("tcp_port")
    current_host = (cfg.alp or {}).get("tcp_host") or "127.0.0.1"

    ui.banner(
        ui.crumb("setup", "alp-tcp", "tcp"),
        subtitle="Noise_XK over TCP — remote Alpi peers",
        home=h,
    )
    ui.dim(
        "Sets the TCP listener used by remote Alpi peers (Noise_XK,\n"
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
        msg = _restart_daemon_for_apply(home._ROOT)
        ui.ok_and_wait(f"TCP disabled — Unix socket only{msg}")
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
    msg = _restart_daemon_for_apply(home._ROOT)
    ui.ok_and_wait(f"TCP bound to {host}:{port}{msg}")


def _devices_status(h: Path) -> str:
    from alpi.host import devices as devices_mod
    from alpi.host.network import resolve_host_endpoint

    if resolve_host_endpoint(h) is None:
        return "no network"
    n = len(devices_mod.load())
    return f"{n} paired" if n else "ready"


def _devices_setup(h: Path) -> None:
    from alpi import ui
    from alpi.host import devices as devices_mod
    from alpi.host.network import resolve_host_endpoint

    while True:
        endpoint = resolve_host_endpoint(h)
        items: list = [
            ui.Heading("Paired devices"),
        ]
        rows = devices_mod.load()
        if not rows:
            items.append(("(no devices yet)", "noop", ""))
        else:
            for d in rows:
                tid = (d["token"] or "")[-8:]
                last = _format_last_seen(d.get("last_seen"))
                items.append((d["label"] or tid, ("device", tid), last))

        items.append(None)
        items.append(("+ Add device", "add",
                      "generate a new pairing QR"))
        items.append(("Network", "network",
                      _network_row_status(h, endpoint)))

        choice = ui.menu(
            ui.crumb("setup", "devices"),
            items,
            subtitle=_devices_subtitle(h, endpoint),
            home=h,
            close="Done",
        )
        if choice is None or choice == "noop":
            return
        if choice == "add":
            _device_add(h, endpoint)
            continue
        if choice == "network":
            _devices_network_setup(h)
            continue
        if isinstance(choice, tuple) and choice[0] == "device":
            _device_detail(choice[1])
            continue


def _devices_subtitle(h: Path, endpoint) -> str:
    from alpi.host.network import resolve_host_tcp_port

    if endpoint is None:
        if _is_umbrel():
            return "remote access not configured — set a LAN or Tailscale address"
        return "no network — install Tailscale or connect to a LAN"
    host, scope = endpoint
    return f"{scope} · {host}:{resolve_host_tcp_port(h)}"


def _network_row_status(h: Path, endpoint) -> str:
    from alpi.host.network import resolve_host_tcp_port

    if endpoint is None:
        if _is_umbrel():
            return "set a LAN hostname or Tailscale address"
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


def _device_add(h: Path, endpoint) -> None:
    from alpi import ui
    from alpi.host import devices as devices_mod
    from alpi.host.network import resolve_host_pairing_name, resolve_host_tcp_port

    if endpoint is None:
        ui.banner(
            ui.crumb("setup", "devices", "add"),
            subtitle="cannot pair — no network",
            home=h,
        )
        if _is_umbrel():
            ui.fail(
                "Set the advertised host first.\n"
                "Use Umbrel's `.local` hostname for LAN access, or enter a\n"
                "Tailscale IP / MagicDNS name for remote pairing."
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
        ui.crumb("setup", "devices", "add"),
        subtitle=f"pair a new client · {scope} · {host}:{port}",
        home=h,
    )
    ui._console.print("")
    label = ui.text("Label (e.g. iPhone, MacBook):", default="")
    if label is None:
        return ui.cancelled()

    row = devices_mod.add(label=label or "device")

    import io
    import json
    from urllib.parse import urlencode

    import qrcode

    pairing_name = resolve_host_pairing_name(h)

    payload = {
        "v": 2,
        "i": host,
        "p": port,
        "n": pairing_name,
        "t": row["token"],
    }
    link = "alpi://device?" + urlencode({
        "v": payload["v"],
        "host": payload["i"],
        "port": payload["p"],
        "name": payload["n"],
        "token": payload["t"],
    })

    ui.banner(
        ui.crumb("setup", "devices", "add", row["label"]),
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
    ui._console.print(f"[dim]label:    [/dim] {row['label']}")
    ui._console.print(f"[dim]token id:[/dim] …{row['token'][-8:]}")
    ui._console.print(f"[dim]desktop:  [/dim] {link}")
    ui._console.print("")
    ui.dim(
        "Scan the QR from mobile or paste the desktop link into the desktop app.\n"
        "The token is one-shot — only this device will be paired with it.\n"
        "If the QR or link is exposed to anyone else, revoke and generate a new one."
    )
    ui.press_enter()


def _devices_network_setup(h: Path) -> None:
    from alpi import config as cfg_mod
    from alpi import ui
    from alpi.host.network import detect_bind_ip

    cfg = cfg_mod.load(h)
    host_cfg = dict(cfg.host or {})
    current = str(host_cfg.get("tcp_host") or "").strip()
    current_name = str(host_cfg.get("device_name") or "").strip()
    detected = detect_bind_ip()
    auto_host = (
        str(os.environ.get("DEVICE_DOMAIN_NAME") or "").strip()
        if _is_umbrel()
        else (detected[0] if detected else "")
    )
    default = current or auto_host
    port = int(host_cfg.get("tcp_port") or 49200)

    subtitle = (
        "how mobile clients reach this Umbrel"
        if _is_umbrel()
        else "how mobile and desktop clients reach this machine"
    )
    ui.banner(
        ui.crumb("setup", "devices", "network"),
        subtitle=subtitle,
        home=h,
    )
    if _is_umbrel():
        ui.dim(
            "The mobile companion talks to the host API on TCP/WS.\n"
            "Inside Umbrel, Alpi cannot see the host Tailscale interface directly,\n"
            "so you set the address clients should dial here.\n"
            "Use `umbrel.local` for LAN access, or a 100.x Tailscale IP / MagicDNS name\n"
            f"for remote pairing. Port {port} is published by the Umbrel package."
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
        host_cfg["tcp_host"] = host
    else:
        host_cfg.pop("tcp_host", None)

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
    cfg_mod.save(cfg)
    msg = _restart_daemon_for_apply(home._ROOT)
    target = host or auto_host or "auto-detect"
    name_target = pairing_name or "auto"
    ui.ok_and_wait(f"remote access target: {target}:{port}, pairing name: {name_target}{msg}")


def _device_detail(token_id: str) -> None:
    from alpi import ui
    from alpi.host import devices as devices_mod

    while True:
        rows = devices_mod.load()
        target = next((d for d in rows if (d["token"] or "")[-8:] == token_id), None)
        if target is None:
            return

        choice = ui.menu(
            ui.crumb("setup", "devices", target["label"] or token_id),
            [
                ("Label", "label", target["label"] or "(none)"),
                ("Token id", "noop", f"…{token_id}"),
                ("Last seen", "noop", _format_last_seen(target.get("last_seen"))),
                None,
                ("Rename", "rename", ""),
                ("Revoke", "revoke", "the device will lose access immediately"),
            ],
            subtitle="device detail",
            home=None,
            close="Back",
        )
        if choice is None or choice == "noop":
            return
        if choice == "label":
            continue
        if choice == "rename":
            new_label = ui.text("New label:", default=target["label"] or "")
            if new_label is None:
                continue
            devices_mod.rename(target["token"], new_label)
            continue
        if choice == "revoke":
            if not ui.confirm(
                f"Revoke {target['label'] or token_id}? "
                "The paired device will fail next request.",
                default=False,
            ):
                continue
            devices_mod.revoke(target["token"])
            ui.ok_and_wait("revoked")
            return


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


def _matrix_status(h: Path) -> str:
    env = _read_profile_env(h)
    if not env.get("MATRIX_ACCESS_TOKEN"):
        return "not set up"
    rooms = env.get("MATRIX_ALLOWED_ROOMS", "")
    n = len([r for r in rooms.split(",") if r.strip()])
    if n == 0:
        return "ready · no rooms allowlisted yet"
    return f"ready · {n} allowlisted room{'s' if n != 1 else ''}"


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
    current_usd = b.get("daily_usd")
    current_tokens = b.get("daily_tokens")

    if current_tokens is not None:
        current_kind = "tokens"
    elif current_usd is not None:
        current_kind = "usd"
    else:
        current_kind = "unlimited"

    items = [
        (
            ("● " if current_kind == "unlimited" else "  ") + "Unlimited",
            "unlimited",
            "no daily ceiling",
        ),
        (
            ("● " if current_kind == "usd" else "  ") + "Daily USD cap",
            "usd",
            "for paid models — measured in dollars",
        ),
        (
            ("● " if current_kind == "tokens" else "  ") + "Daily token cap",
            "tokens",
            "for local / free models — measured in tokens",
        ),
    ]
    kind = ui.menu(
        ui.crumb("setup", "budget"),
        items,
        subtitle="daily spend cap for this profile · pick one or unlimited",
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

    if kind == "usd":
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
        return

    default_s = str(current_tokens) if current_tokens is not None else ""
    raw = ui.text(
        "Daily token cap (must be > 0):",
        default=default_s,
    )
    if raw is None:
        return ui.cancelled()
    raw = (raw or "").strip()
    if not raw:
        ui.fail_and_wait("token cap required (or pick Unlimited)")
        return
    try:
        v_int = int(raw)
    except ValueError:
        ui.fail_and_wait(f"not an integer: {raw!r}")
        return
    if v_int <= 0:
        ui.fail_and_wait("token cap must be > 0")
        return
    cfg.budget = {"daily_tokens": v_int}
    config.save(cfg)
    ui.ok_and_wait(f"cap: {v_int:,} tokens/day")


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


def _cleanup_categories(h: Path) -> list[dict]:
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

    from alpi.core import store as store_mod

    tts_files = _all(_dir("cache/tts"))
    inbound_files = _all(_dir("cache/inbound"))
    session_files = _all(_dir("sessions"))
    mention_files = _all(_dir("mentions"))
    gateway_files = _all(_dir("gateway/sessions"))
    log_files = _all(_dir("logs"))
    sched_files = _all(_dir("schedule/output"))
    wg_root = _dir("alp/workgroups")
    wg_files: list[Path] = (
        [p for p in wg_root.rglob("*") if p.is_file()] if wg_root.exists() else []
    )
    turns_path = _dir("alp/turns.jsonl")
    if turns_path.is_file():
        wg_files.append(turns_path)
    rag_reclaimable = store_mod.reclaimable_bytes(h)
    rag_files: list[Path] = (
        [store_mod.store_path(h)] if rag_reclaimable > 0 else []
    )

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
            "label": "Sessions",
            "desc": "chat transcripts kept in `sessions/`",
            "files": session_files,
            "size": _sum(session_files),
        },
        {
            "key": "mentions",
            "label": "Mentions",
            "desc": "per-sender @-mention threads in `mentions/`",
            "files": mention_files,
            "size": _sum(mention_files),
        },
        {
            "key": "gateway",
            "label": "Gateway",
            "desc": "Telegram / email / webhook chats in `gateway/sessions/`",
            "files": gateway_files,
            "size": _sum(gateway_files),
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
        {
            "key": "workgroups",
            "label": "Workgroups",
            "desc": "encrypted transcripts + turn telemetry under `alp/`",
            "files": wg_files,
            "size": _sum(wg_files),
        },
        {
            "key": "rag",
            "label": "RAG store bloat",
            "desc": "SQLite freelist pages in `rag/store.sqlite` from past force-reindexes",
            "files": rag_files,
            "size": rag_reclaimable,
            "action": "vacuum",
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
        if target.get("action") == "vacuum":
            if not ui.confirm(
                f"  Compact RAG store and reclaim {size_label}?",
                default=False,
            ):
                continue
            from alpi.core import store as store_mod

            before, after = store_mod.compact(h)
            ui.ok_and_wait(
                f"compacted {target['label']}: "
                f"{home_mod.format_bytes(before)} → {home_mod.format_bytes(after)}"
            )
            continue
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
    from alpi.host.config import RESERVED_PROFILE_NAMES

    if not name:
        raise click.ClickException("name required")
    if name in RESERVED_PROFILE_NAMES:
        raise click.ClickException(f"use a real name — {name!r} is reserved")
    if "/" in name or name.startswith("."):
        raise click.ClickException(f"invalid profile name: {name!r}")

    h = home.home_for(name)
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
@click.option("--yes", is_flag=True, default=False,
              help="Skip the interactive confirmation prompt.")
@click.option("--force", is_flag=True, default=False,
              help="Uninstall an installed service first instead of refusing.")
def profile_remove(name: str, yes: bool, force: bool) -> None:
    """Permanently remove a profile directory after safety checks."""
    import shutil

    from alpi import service, ui

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
    return "Remove all data"


def _delete_profile_wizard(h: Path, profile_name: str) -> bool:
    """Return True if deleted; caller must exit the setup loop."""
    import shutil
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
def workgroup() -> None:
    """Manage ALP workgroups; hub verbs (create/kick) vs member verbs (join/post/pull/pause/resume/leave)."""


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
@click.option("--briefing", default="",
              help="Initial briefing text. Hub can edit later via set-briefing.")
@click.pass_context
def workgroup_create(
    ctx: click.Context, name: str,
    members: tuple[str, ...], budget_usd: float | None,
    budget_tokens: int | None, briefing: str,
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
    if budget_usd is not None and budget_tokens is not None:
        raise click.ClickException("--budget-usd and --budget-tokens are mutually exclusive")
    if budget_usd is not None:
        budget["max_usd"] = budget_usd
    if budget_tokens is not None:
        budget["max_tokens"] = budget_tokens

    hub_cfg = config.load(h)
    hub_bio = (hub_cfg.public_bio or "").strip()
    hub_voice = (hub_cfg.tools.tts.voice or "").strip()
    try:
        wg = wg_mod.create(
            h, name=name, hub_kp=load_or_generate(h),
            member_pubkeys=pubkeys, budget=budget,
            briefing=(briefing or "").strip(),
            hub_bio=hub_bio, hub_voice=hub_voice,
        )
    except ValueError as e:
        raise click.ClickException(str(e))
    click.echo(f"created {wg.meta.id} · {len(wg.members)} members")


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
    import shutil
    from alpi.alp import subscription as sub_mod
    from alpi.alp import workgroup as wg_mod
    from alpi.alp.keys import load_or_generate
    from alpi.home import _ROOT

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
    shutil.rmtree(h / "alp" / "workgroups" / wg_id, ignore_errors=True)

    # Hub removal orphans local subscriptions; cross-machine peers must `leave` themselves.
    profiles_root = _ROOT / "profiles"
    purged: list[str] = []
    if profiles_root.exists():
        for prof_dir in profiles_root.iterdir():
            if not prof_dir.is_dir():
                continue
            try:
                if sub_mod.get(prof_dir, wg_id) is not None:
                    sub_mod.remove(prof_dir, wg_id)
                    purged.append(prof_dir.name)
            except Exception:  # noqa: BLE001
                pass
    try:
        if sub_mod.get(_ROOT, wg_id) is not None:
            sub_mod.remove(_ROOT, wg_id)
            purged.append("default")
    except Exception:  # noqa: BLE001
        pass

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
@click.pass_context
def workgroup_update(
    ctx: click.Context, wg_id: str, briefing: str | None,
    budget_usd: float | None, clear_budget: bool,
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
            "nothing to update — pass --briefing, --budget-usd or --clear-budget"
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


if __name__ == "__main__":
    main(obj={})
    sys.exit(0)
