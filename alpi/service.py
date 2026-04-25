"""Single per-profile service: orchestrator + install.

One process per profile runs every enabled subsystem (gateway,
scheduler, ALP listener) on the same asyncio event loop. The PID,
log, and OS-level service registration (launchd plist on macOS,
systemd-user unit on Linux) all share the single ``service`` name —
no more three-process / three-plist sprawl per profile.

Subsystems are toggled per profile in ``config.yaml``::

    service:
      gateway: true     # Telegram / IMAP / Gmail polling
      schedule: true    # cron jobs
      alp: true         # peer listener (Unix socket + optional TCP)

Default if the section is missing: all three on, since that matches
the previous (split-services) behaviour.

Lifecycle commands live under ``alpi service`` in the CLI:
``start`` (foreground), ``stop`` (signal a running process),
``restart``, ``status`` (PID + uptime + which subsystems are active).
``install`` and ``uninstall`` are reached from the wizard
(``alpi setup → Service``) — they register one plist / unit per
profile that supervises the same ``alpi service start`` command.
"""

from __future__ import annotations

import asyncio
import logging
import os
import platform
import shutil
import signal
import subprocess
import sys
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any


log = logging.getLogger("alpi.service")


# Public — orchestration


def pid_path(home: Path) -> Path:
    return home / "service.pid"


def log_path(home: Path) -> Path:
    return home / "logs" / "service.log"


def running_pid(home: Path) -> int | None:
    """Return the PID of the live service or ``None`` if nothing is
    running. Stale PID files (process gone) are cleaned up on the way."""
    p = pid_path(home)
    if not p.exists():
        return None
    try:
        pid = int(p.read_text().strip())
    except (ValueError, OSError):
        return None
    try:
        os.kill(pid, 0)
    except OSError:
        try:
            p.unlink()
        except OSError:
            pass
        return None
    return pid


def is_running(home: Path) -> bool:
    return running_pid(home) is not None


def enabled_subsystems(home: Path) -> dict[str, bool]:
    """Read which subsystems this profile wants. Missing config →
    everything on (matches pre-refactor default).

    ``workgroups`` is a separate subsystem (PR 5) — the background
    poller that pulls subscribed workgroups and dispatches a turn
    when there's new content addressed at us. Defaults to True; set
    to False on a profile that participates in no workgroups (cheap
    no-op anyway, but silences a wasted log line at start)."""
    from alpi import config as cfg_mod
    cfg = cfg_mod.load(home)
    raw = getattr(cfg, "service", None) or {}
    return {
        "gateway": bool(raw.get("gateway", True)),
        "schedule": bool(raw.get("schedule", True)),
        "alp": bool(raw.get("alp", True)),
        "workgroups": bool(raw.get("workgroups", True)),
    }


def serve(home: Path, profile: str = "default") -> None:
    """Foreground entry point — boots every enabled subsystem on a
    single asyncio loop, writes the PID, sets the process title to
    ``alpi (<profile>)``, and waits until SIGTERM / SIGINT."""
    _configure_logging(home)
    _load_env(home)
    _set_proctitle(profile)
    _write_pid(home)

    subsystems = enabled_subsystems(home)
    log.info(
        "service starting · profile=%s · subsystems=%s",
        profile,
        ",".join(name for name, on in subsystems.items() if on) or "(none)",
    )

    try:
        asyncio.run(_main(home, profile, subsystems))
    except KeyboardInterrupt:
        pass
    finally:
        _clear_pid(home)
        log.info("service stopped · profile=%s", profile)


async def _main(
    home: Path, profile: str, subsystems: dict[str, bool],
) -> None:
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:
            # Windows / restricted env — fall back to KeyboardInterrupt.
            pass

    tasks: list[asyncio.Task] = []
    if subsystems.get("gateway"):
        tasks.append(asyncio.create_task(
            _supervise(_run_gateway, home, profile, "gateway"),
            name="gateway",
        ))
    if subsystems.get("schedule"):
        tasks.append(asyncio.create_task(
            _supervise(_run_scheduler, home, profile, "schedule"),
            name="schedule",
        ))
    if subsystems.get("alp"):
        tasks.append(asyncio.create_task(
            _supervise(_run_alp, home, profile, "alp"),
            name="alp",
        ))
    if subsystems.get("workgroups"):
        tasks.append(asyncio.create_task(
            _supervise(_run_workgroup_poller, home, profile, "workgroups"),
            name="workgroups",
        ))

    if not tasks:
        log.warning("no subsystems enabled — service will idle")
        await stop.wait()
        return

    # Wait until SIGTERM/SIGINT — subsystems are independently
    # supervised inside ``_supervise`` so a crash in one no longer
    # collapses the rest. Only the explicit stop signal shuts the
    # service down.
    await stop.wait()
    for t in tasks:
        t.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)


async def _supervise(coro_fn, home: Path, profile: str, name: str) -> None:
    """Wrap a subsystem's run loop so a crash doesn't take down the
    whole service. The crashed subsystem stays dead (we don't auto-
    restart yet — would risk tight loops on a persistent failure
    like a missing config); the others keep running. Operator sees
    the traceback in the log and can fix + restart manually."""
    try:
        # Subsystems that need the profile name take it as a second
        # arg; the simple ones only need the home path. Pass both
        # uniformly, let each function declare what it accepts.
        if name in ("alp", "workgroups"):
            await coro_fn(home, profile)
        else:
            await coro_fn(home)
    except asyncio.CancelledError:
        raise
    except Exception:  # noqa: BLE001
        log.exception("subsystem %s crashed — staying down, "
                      "other subsystems unaffected", name)


async def _run_gateway(home: Path) -> None:
    from alpi.gateway.run import serve as gw_serve
    await gw_serve(home)


async def _run_scheduler(home: Path) -> None:
    from alpi.scheduler.run import serve as sch_serve
    await sch_serve(home)


async def _run_workgroup_poller(home: Path, profile: str) -> None:
    """Watch every workgroup this profile participates in (subscriptions
    AND hub-of) and dispatch an autonomous agent turn when something
    arrives we should react to: a post tagging this profile, or a new
    ``#task`` opening. Hub-of workgroups read the transcript locally
    (no network); subscribed workgroups go through ``wc.pull`` so the
    cache + cursor advance.

    Per-workgroup cooldown (``DISPATCH_COOLDOWN_SECONDS``) prevents
    tight ping-pong between two alpis. Profile / workgroup budgets are
    the ultimate stop — every spawned turn admits against the profile
    ledger and every ``workgroup_post`` it produces declares cost
    against the workgroup ledger.
    """
    from alpi.alp import subscription as sub_mod
    from alpi.alp import workgroup as wg_mod
    from alpi.alp import workgroup_client as wc

    log.info("workgroup poller running (tick=%ss)", WORKGROUP_TICK_SECONDS)
    while True:
        try:
            # Member-of workgroups — pull (advances cursor + fills the
            # cache), then check the cache for "do I owe a response?"
            # via _should_dispatch. We always check, even when no new
            # posts arrived this tick, so a missed cooldown window
            # doesn't lose the trigger.
            for sub in sub_mod.load(home):
                try:
                    await wc.pull(home, sub.wg_id)
                except Exception as e:  # noqa: BLE001
                    log.debug("wg poller pull(%s) failed: %s", sub.wg_id, e)
                    continue
                # Re-load to pick up the freshly-saved cache.
                refreshed = sub_mod.get(home, sub.wg_id)
                if refreshed is None:
                    continue
                await _maybe_dispatch_for_sub(home, profile, refreshed)

            # Hub-of workgroups — local transcript, hub is also a member
            for wg in wg_mod.list_workgroups(home):
                try:
                    recent = _all_hub_posts_decrypted(home, wg)
                except Exception as e:  # noqa: BLE001
                    log.debug("wg poller hub scan(%s) failed: %s", wg.meta.id, e)
                    continue
                if not recent:
                    continue
                await _maybe_dispatch_for_hub(home, profile, wg, recent)
        except Exception:  # noqa: BLE001
            log.exception("workgroup poller tick crashed")
        await asyncio.sleep(WORKGROUP_TICK_SECONDS)


async def _maybe_dispatch_for_sub(
    home: Path, profile: str, sub,
) -> None:
    """Member-side dispatch decision. Reads ``sub.recent_posts`` (cache
    refreshed by the most recent pull) and ``sub.last_responded_seq``
    so a missed cooldown window doesn't lose the trigger. Persists
    ``last_responded_seq`` only on actual dispatch."""
    from alpi.alp import keys as _keys
    from alpi.alp import subscription as sub_mod

    own_pubkey = _keys.load_or_generate(home).pubkey_b64()
    trigger, new_responded = _should_dispatch(
        profile, own_pubkey, sub.recent_posts or [], sub.last_responded_seq,
    )
    # Pointer-only update (latest post is our own → no dispatch but
    # advance the responded pointer so we don't keep re-checking).
    if not trigger:
        if new_responded > sub.last_responded_seq:
            sub.last_responded_seq = new_responded
            sub_mod.upsert(home, sub)
        return
    if _in_cooldown_str(sub.last_dispatch_at):
        log.info(
            "wg poller: %s skipped (cooldown, reason=%s)",
            sub.wg_id, trigger,
        )
        return
    log.info(
        "wg poller: %s dispatching turn (reason=%s, member-of)",
        sub.wg_id, trigger,
    )
    await _dispatch_workgroup_turn(home, profile, sub.wg_id, sub.name, trigger)
    sub.last_responded_seq = new_responded
    sub.last_dispatch_at = _utcnow_iso()
    sub_mod.upsert(home, sub)


async def _maybe_dispatch_for_hub(
    home: Path, profile: str, wg, recent: list[dict],
) -> None:
    """Hub-side dispatch decision. ``recent`` is the full decrypted
    transcript window for this workgroup; ``hub_last_responded_seq``
    in the poller state file gates re-dispatch of the same content
    independently of the cooldown so a missed window doesn't drop
    the trigger."""
    from alpi.alp import keys as _keys

    own_pubkey = _keys.load_or_generate(home).pubkey_b64()
    last_responded = _get_hub_responded_seq(home, wg.meta.id)
    trigger, new_responded = _should_dispatch(
        profile, own_pubkey, recent, last_responded,
    )
    if not trigger:
        if new_responded > last_responded:
            _set_hub_responded_seq(home, wg.meta.id, new_responded)
        return
    state = _load_poller_state(home)
    last = state.get("hub_last_dispatch_at", {}).get(wg.meta.id, "")
    if _in_cooldown_str(last):
        log.info(
            "wg poller: %s skipped (cooldown, reason=%s)",
            wg.meta.id, trigger,
        )
        return
    log.info(
        "wg poller: %s dispatching turn (reason=%s, hub-of)",
        wg.meta.id, trigger,
    )
    await _dispatch_workgroup_turn(home, profile, wg.meta.id, wg.meta.name, trigger)
    _set_hub_responded_seq(home, wg.meta.id, new_responded)
    _mark_hub_dispatched(home, wg.meta.id)


def _all_hub_posts_decrypted(home: Path, wg) -> list[dict]:
    """Full decrypted recent transcript for hub workgroups — used by
    the active-task participant trigger. Mirrors ``_new_hub_posts``
    but ignores the cursor (we want context, not new-post detection)
    and includes the hub's own posts (active-task lookup needs to
    see all participants' contributions)."""
    import json
    from alpi.alp import workgroup as wg_mod
    from alpi.alp.keys import load_or_generate

    kp = load_or_generate(home)
    own = wg.member(kp.pubkey_b64())
    if own is None:
        return []
    try:
        group_key = wg_mod.open_sealed_group_key(own.sealed_key, kp)
    except Exception:  # noqa: BLE001
        return []
    transcript_path = home / "alp" / "workgroups" / wg.meta.id / "transcript.jsonl"
    if not transcript_path.exists():
        return []
    out: list[dict] = []
    for line in transcript_path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if int(entry.get("key_version", 1)) != own.key_version:
            continue
        try:
            text = wg_mod.decrypt_post(
                group_key, entry["nonce"], entry["ciphertext"],
            ).decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            continue
        out.append({**entry, "text": text})
    return out


def _new_hub_posts(home: Path, wg) -> list[dict]:
    """Read the local transcript, decrypt with the hub's own sealed key,
    return posts with ``seq`` greater than the last cursor we saved.
    The hub is always a member of its own workgroup, so it holds a
    sealed copy of the current group key."""
    import json
    from alpi.alp import workgroup as wg_mod
    from alpi.alp.keys import load_or_generate

    kp = load_or_generate(home)
    own = wg.member(kp.pubkey_b64())
    if own is None:
        return []
    try:
        group_key = wg_mod.open_sealed_group_key(own.sealed_key, kp)
    except Exception:  # noqa: BLE001
        return []

    cursor = _get_hub_cursor(home, wg.meta.id)
    transcript_path = home / "alp" / "workgroups" / wg.meta.id / "transcript.jsonl"
    if not transcript_path.exists():
        return []

    out: list[dict] = []
    for line in transcript_path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        seq = int(entry.get("seq", 0))
        if seq <= cursor:
            continue
        # Skip posts we (the hub) authored — we don't react to ourselves.
        if str(entry.get("from") or "") == kp.pubkey_b64():
            continue
        if int(entry.get("key_version", 1)) != own.key_version:
            continue  # past keys not openable on the hub
        try:
            text = wg_mod.decrypt_post(
                group_key, entry["nonce"], entry["ciphertext"],
            ).decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            continue
        out.append({**entry, "text": text})
    return out


# Hub-side cursor + cooldown state, stored under the profile root.


def _poller_state_path(home: Path) -> Path:
    return home / "alp" / "poller_state.json"


def _load_poller_state(home: Path) -> dict:
    import json
    p = _poller_state_path(home)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text()) or {}
    except json.JSONDecodeError:
        return {}


def _save_poller_state(home: Path, state: dict) -> None:
    import json
    p = _poller_state_path(home)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, separators=(",", ":")))


def _get_hub_cursor(home: Path, wg_id: str) -> int:
    state = _load_poller_state(home)
    return int(state.get("hub_cursors", {}).get(wg_id, 0))


def _set_hub_cursor(home: Path, wg_id: str, seq: int) -> None:
    state = _load_poller_state(home)
    cursors = state.setdefault("hub_cursors", {})
    if int(seq) > int(cursors.get(wg_id, 0)):
        cursors[wg_id] = int(seq)
        _save_poller_state(home, state)


def _mark_hub_dispatched(home: Path, wg_id: str) -> None:
    state = _load_poller_state(home)
    last = state.setdefault("hub_last_dispatch_at", {})
    last[wg_id] = _utcnow_iso()
    _save_poller_state(home, state)


def _get_hub_responded_seq(home: Path, wg_id: str) -> int:
    state = _load_poller_state(home)
    return int(state.get("hub_last_responded_seq", {}).get(wg_id, 0))


def _set_hub_responded_seq(home: Path, wg_id: str, seq: int) -> None:
    state = _load_poller_state(home)
    table = state.setdefault("hub_last_responded_seq", {})
    if int(seq) > int(table.get(wg_id, 0)):
        table[wg_id] = int(seq)
        _save_poller_state(home, state)


def _utcnow_iso() -> str:
    import datetime as _dt
    return _dt.datetime.now(tz=_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _mark_sub_dispatched(home: Path, wg_id: str) -> None:
    """Persist the dispatch timestamp on the subscription itself so the
    cooldown survives across poller ticks."""
    import datetime as _dt
    from alpi.alp import subscription as sub_mod
    sub = sub_mod.get(home, wg_id)
    if sub is None:
        return
    sub.last_dispatch_at = _dt.datetime.now(tz=_dt.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ",
    )
    sub_mod.upsert(home, sub)


def _in_cooldown_str(stamp: str) -> bool:
    """``True`` when ``stamp`` is within ``DISPATCH_COOLDOWN_SECONDS`` of
    now. Robust to malformed / missing timestamps."""
    import datetime as _dt
    from alpi.alp.subscription import DISPATCH_COOLDOWN_SECONDS
    if not stamp:
        return False
    try:
        last = _dt.datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return False
    last = last.replace(tzinfo=_dt.timezone.utc)
    elapsed = (_dt.datetime.now(tz=_dt.timezone.utc) - last).total_seconds()
    return elapsed < DISPATCH_COOLDOWN_SECONDS


def _should_dispatch(
    profile: str, own_pubkey: str,
    recent_posts: list[dict],
    last_responded_seq: int,
) -> tuple[str | None, int]:
    """Decide whether the poller should wake the local agent — looks
    at the cache, not at the per-tick delta, so a missed dispatch
    (cooldown skip) doesn't lose the trigger. Three triggers ordered
    by priority:

    1. **Direct @-mention** in the most recent post — always wakes.
    2. **Collective `#task`** (a `#task` post with NO specific peers
       tagged) — wakes every member; it's a workgroup-wide call.
    3. **Participant in the active task** — if there's an active
       `#task` whose opening post tagged us by name, the latest
       post being from someone else wakes us so the conversation
       stays alive without forcing peers to spam @-mentions every
       reply.

    Returns ``(reason, new_responded_seq)``. When ``reason`` is None
    no dispatch is warranted; ``new_responded_seq`` is what the
    caller should persist anyway when the latest post is our own
    (housekeeping — we already covered up to that seq).

    A targeted `#task` aimed at OTHER peers (``#task @bob ...``
    when we're carol) does NOT wake us — only the explicit mention
    does, which trigger 1 handles directly.

    Cooldown is checked by the caller after this returns; persisting
    ``new_responded_seq`` only happens on actual dispatch, so a
    cooldown skip leaves the pointer untouched and the next tick
    re-evaluates against the same cache."""
    from alpi.alp import tasks as wg_tasks

    if not recent_posts:
        return None, last_responded_seq

    latest = max(recent_posts, key=lambda p: int(p.get("seq", 0)))
    latest_seq = int(latest.get("seq", 0))
    if latest_seq <= last_responded_seq:
        return None, last_responded_seq
    # Latest post is our own — bump the pointer so we don't keep
    # re-checking, but don't dispatch (we don't react to ourselves).
    if str(latest.get("from") or "") == own_pubkey:
        return None, latest_seq

    text = str(latest.get("text") or "")
    mentions = wg_tasks.mentions_in(text)

    # Trigger 1 — explicit @-mention.
    if profile in mentions:
        return f"@{profile} mentioned (seq #{latest_seq})", latest_seq

    # Trigger 2 — collective #task (no peer-specific @-targets).
    events = wg_tasks.parse_post(
        text, latest_seq, str(latest.get("from") or ""),
    )
    if any(e.kind == "task" for e in events) and not mentions:
        return f"collective #task opened (seq #{latest_seq})", latest_seq

    # Trigger 3 — we're a named participant in the active task and
    # someone else just posted.
    active = wg_tasks.active_task(recent_posts)
    if active is None:
        return None, last_responded_seq
    for p in recent_posts:
        if int(p.get("seq", 0)) != active.opened_seq:
            continue
        if profile in wg_tasks.mentions_in(str(p.get("text") or "")):
            return (
                f"new content in active task "
                f"(you're a named participant; seq #{latest_seq})",
                latest_seq,
            )
        break
    return None, last_responded_seq


async def _dispatch_workgroup_turn(
    home: Path, profile: str, wg_id: str, wg_name: str, reason: str,
) -> None:
    """Spawn ``alpi -p <profile> chat --once <synthetic prompt>`` so the
    agent runs a turn out-of-band. The engine's pre-turn hook injects
    the workgroup context block; the agent reads it, decides whether
    to engage, and posts via the ``workgroup_post`` tool when useful.
    Same subprocess pattern as the gateway uses for inbound messages."""
    prompt = (
        f"[workgroup-poller] new activity in workgroup "
        f"'#{wg_name or wg_id}' (wg_id={wg_id}). Reason: {reason}. "
        "\n\nYou are running ALONE — no human is reading this turn. "
        "Assistant text goes NOWHERE; the only way to contribute is "
        f"to call `workgroup_post(wg_id=\"{wg_id}\", text=\"…\")`. "
        "Do NOT ask permission, do NOT describe what you would post. "
        "\n\nBefore choosing an action, re-read the BRIEFING and the "
        "ACTIVE TASK in your workgroup context block. If the task "
        "asks for evidence (cite sources, search the web, "
        "benchmarks, etc.), you MUST do that work BEFORE posting "
        "anything substantive — use `web_search` / `web_fetch` / "
        "`research` first, then post citing what you found. "
        "\n\nFollow your `Workgroup engagement rules` exactly. The "
        "default posture is OBSERVER. Valid actions, in priority:"
        "\n  1. If the discussion has had multiple peer "
        "contributions AND converged on a recommendation, "
        f"post `workgroup_post(wg_id=\"{wg_id}\", "
        "text=\"#done <one-line result summary>\")` to close. "
        "Do NOT close as the first peer to respond — that's a "
        "unilateral decision, not convergence.\n"
        "  2. If you have a SUBSTANTIVE new contribution (a fact, "
        "evidence, concern, or option not raised yet), post it. A "
        "paraphrase of the latest post is NOT a contribution.\n"
        "  3. Otherwise, end the turn without posting. Silence is "
        "the right output more often than you expect."
    )
    env = dict(os.environ)
    env["ALPI_HOME"] = str(home)
    env["ALPI_WORKGROUP_DISPATCH"] = wg_id
    argv = [
        sys.executable, "-m", "alpi", "-p", profile,
        "chat", "--once", prompt,
    ]
    try:
        proc = await asyncio.create_subprocess_exec(
            *argv,
            env=env,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
    except OSError as e:
        log.warning("wg poller: subprocess spawn failed: %s", e)
        return

    rc = await proc.wait()
    if rc != 0 and proc.stderr is not None:
        err = (await proc.stderr.read()).decode(errors="replace")[:300]
        log.warning(
            "wg poller: turn for %s exited rc=%s: %s",
            wg_id, rc, err,
        )


WORKGROUP_TICK_SECONDS = 30


async def _run_alp(home: Path, profile: str) -> None:
    from alpi import config as cfg_mod
    from alpi.alp import handlers as alp_handlers
    from alpi.alp import workgroup as alp_workgroup
    from alpi.alp.server import Server

    cfg = cfg_mod.load(home)
    cfg_alp = cfg.alp or {}
    server = Server(
        home=home,
        agent_name=profile,
        tcp_host=cfg_alp.get("tcp_host"),
        tcp_port=cfg_alp.get("tcp_port"),
    )
    alp_handlers.register_link_ask(server, home)
    alp_workgroup.register(server, home)
    await server.start()
    try:
        await server.serve_forever()
    finally:
        await server.stop()


# Helpers


def _set_proctitle(profile: str) -> None:
    try:
        import setproctitle
        setproctitle.setproctitle(f"alpi ({profile})")
    except Exception:  # noqa: BLE001
        pass


def _configure_logging(home: Path) -> None:
    """Root logger goes to ``service.log``. Add a stderr stream only
    when running interactively (TTY) — under launchd / systemd the
    plist already redirects stderr to the same log file, and a
    second handler would write every line twice."""
    from alpi._log import FORMAT, MAX_BYTES

    p = log_path(home)
    p.parent.mkdir(parents=True, exist_ok=True)
    handlers: list[logging.Handler] = [
        RotatingFileHandler(p, maxBytes=MAX_BYTES, backupCount=0),
    ]
    if sys.stderr.isatty():
        handlers.append(logging.StreamHandler())
    logging.basicConfig(
        level=logging.INFO,
        format=FORMAT,
        handlers=handlers,
        force=True,
    )


def _load_env(home: Path) -> None:
    env_path = home / ".env"
    if env_path.exists():
        from dotenv import load_dotenv
        load_dotenv(env_path, override=False)


def _write_pid(home: Path) -> None:
    p = pid_path(home)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(str(os.getpid()))


def _clear_pid(home: Path) -> None:
    p = pid_path(home)
    if p.exists():
        try:
            p.unlink()
        except OSError:
            pass


# OS-level service install — single per profile


class ServiceError(Exception):
    """Surface install/uninstall failures to the CLI."""


def install(home: Path, profile: str = "default") -> str:
    """Register a per-profile launchd plist (macOS) or systemd-user unit
    (Linux) that supervises ``alpi -p <profile> service start``. Returns
    the backend used."""
    backend = _detect_backend()
    alpi_bin = _locate_alpi()
    if backend == "launchd":
        _launchd_install(home, profile, alpi_bin)
        return "launchd"
    if backend == "systemd":
        _systemd_install(home, profile, alpi_bin)
        return "systemd"
    raise ServiceError(f"unsupported platform: {platform.system()}")


def uninstall(home: Path, profile: str = "default") -> str:
    backend = _detect_backend()
    if backend == "launchd":
        _launchd_uninstall(profile)
        return "launchd"
    if backend == "systemd":
        _systemd_uninstall(profile)
        return "systemd"
    raise ServiceError(f"unsupported platform: {platform.system()}")


def installed(profile: str = "default") -> str | None:
    """Return the backend name if a service unit exists on disk, else None."""
    backend = _detect_backend()
    if backend == "launchd" and _launchd_plist_path(profile).exists():
        return "launchd"
    if backend == "systemd" and _systemd_unit_path(profile).exists():
        return "systemd"
    return None


def label(profile: str) -> str:
    """Public label used in messages + ps output."""
    if _detect_backend() == "launchd":
        return f"com.alpi.service.{profile}"
    return f"alpi-service-{profile}"


def _detect_backend() -> str | None:
    system = platform.system()
    if system == "Darwin":
        return "launchd"
    if system == "Linux":
        return "systemd"
    return None


def _locate_alpi() -> str:
    path = shutil.which("alpi")
    if not path:
        return f"{sys.executable} -m alpi"
    return path


# launchd (macOS)


_PLIST_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>{label}</string>
  <key>ProgramArguments</key>
  <array>
{program_args}
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>ALPI_HOME</key>
    <string>{home}</string>
    <key>PATH</key>
    <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
  </dict>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>{log}</string>
  <key>StandardErrorPath</key>
  <string>{log}</string>
</dict>
</plist>
"""


def _launchd_plist_path(profile: str) -> Path:
    return (
        Path.home() / "Library" / "LaunchAgents"
        / f"com.alpi.service.{profile}.plist"
    )


def _launchd_install(home: Path, profile: str, alpi_bin: str) -> None:
    lbl = f"com.alpi.service.{profile}"
    plist = _launchd_plist_path(profile)
    plist.parent.mkdir(parents=True, exist_ok=True)
    log_p = log_path(home)
    log_p.parent.mkdir(parents=True, exist_ok=True)

    plist.write_text(_PLIST_TEMPLATE.format(
        label=lbl,
        program_args=_program_args_xml(alpi_bin, profile),
        home=str(home),
        log=str(log_p),
    ))

    uid = os.getuid()
    _run(["launchctl", "bootout", f"gui/{uid}", str(plist)], check=False)
    res = _run(["launchctl", "bootstrap", f"gui/{uid}", str(plist)], check=False)
    if res.returncode != 0:
        raise ServiceError(
            f"launchctl bootstrap failed (rc={res.returncode}): "
            f"{(res.stderr or res.stdout).strip()}"
        )


def _launchd_uninstall(profile: str) -> None:
    plist = _launchd_plist_path(profile)
    if not plist.exists():
        raise ServiceError(f"service is not installed (no plist at {plist})")
    uid = os.getuid()
    _run(["launchctl", "bootout", f"gui/{uid}", str(plist)], check=False)
    plist.unlink(missing_ok=True)


# systemd --user (Linux)


_UNIT_TEMPLATE = """[Unit]
Description=alpi service ({profile})
After=network-online.target

[Service]
Type=simple
Environment=ALPI_HOME={home}
ExecStart={exec_start}
Restart=on-failure
RestartSec=5
StandardOutput=append:{log}
StandardError=append:{log}

[Install]
WantedBy=default.target
"""


def _systemd_unit_path(profile: str) -> Path:
    return (
        Path.home() / ".config" / "systemd" / "user"
        / f"alpi-service-{profile}.service"
    )


def _systemd_install(home: Path, profile: str, alpi_bin: str) -> None:
    unit = _systemd_unit_path(profile)
    unit.parent.mkdir(parents=True, exist_ok=True)
    log_p = log_path(home)
    log_p.parent.mkdir(parents=True, exist_ok=True)

    unit.write_text(_UNIT_TEMPLATE.format(
        profile=profile,
        home=str(home),
        exec_start=f"{alpi_bin} -p {profile} service start",
        log=str(log_p),
    ))

    unit_id = f"alpi-service-{profile}.service"
    res = _run(["systemctl", "--user", "daemon-reload"], check=False)
    if res.returncode != 0:
        raise ServiceError(
            f"systemctl daemon-reload failed (rc={res.returncode}): "
            f"{(res.stderr or res.stdout).strip()}{_systemd_hint(res)}"
        )
    res = _run(["systemctl", "--user", "enable", "--now", unit_id], check=False)
    if res.returncode != 0:
        raise ServiceError(
            f"systemctl enable --now failed (rc={res.returncode}): "
            f"{(res.stderr or res.stdout).strip()}{_systemd_hint(res)}"
        )


def _systemd_uninstall(profile: str) -> None:
    unit = _systemd_unit_path(profile)
    if not unit.exists():
        raise ServiceError(f"service is not installed (no unit at {unit})")
    unit_id = f"alpi-service-{profile}.service"
    _run(["systemctl", "--user", "disable", "--now", unit_id], check=False)
    unit.unlink(missing_ok=True)
    _run(["systemctl", "--user", "daemon-reload"], check=False)


def _systemd_hint(result: subprocess.CompletedProcess) -> str:
    combined = (result.stderr or "") + (result.stdout or "")
    if "Failed to connect to bus" in combined or "No such file" in combined:
        return (
            "\nNote: `systemd --user` must be available. On WSL without "
            "`systemd=true` in /etc/wsl.conf, or in minimal containers, "
            "run `alpi service start` in a tmux/screen session instead."
        )
    return ""


def _program_args_xml(alpi_bin: str, profile: str) -> str:
    parts = alpi_bin.split() + ["-p", profile, "service", "start"]
    return "\n".join(f"    <string>{x}</string>" for x in parts)


def _run(cmd: list[str], *, check: bool) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


# Stop / restart helpers used by the CLI


def stop(home: Path, profile: str, *, timeout: float = 5.0) -> bool:
    """Send SIGTERM to the service. Returns True if a process was
    signalled, False if nothing was running."""
    pid = running_pid(home)
    if pid is None:
        return False
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        return False
    deadline = time.time() + timeout
    while time.time() < deadline:
        if running_pid(home) is None:
            return True
        time.sleep(0.1)
    # Last-ditch — SIGKILL if it ignored SIGTERM
    try:
        os.kill(pid, signal.SIGKILL)
    except OSError:
        pass
    return True


def status(home: Path, profile: str) -> dict[str, Any]:
    """Snapshot for ``alpi service status``."""
    pid = running_pid(home)
    info: dict[str, Any] = {
        "profile": profile,
        "pid": pid,
        "running": pid is not None,
        "installed_via": installed(profile),
        "subsystems": enabled_subsystems(home),
    }
    if pid is not None:
        info["uptime_seconds"] = _uptime_seconds(pid)
    return info


def _uptime_seconds(pid: int) -> int | None:
    """Best-effort process uptime via ``ps -o lstart``. Returns None on
    failure — uptime is observability, not load-bearing."""
    try:
        res = subprocess.run(
            ["ps", "-o", "etime=", "-p", str(pid)],
            capture_output=True, text=True, check=False, timeout=2,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    out = res.stdout.strip()
    if not out:
        return None
    return _parse_etime(out)


def _parse_etime(s: str) -> int | None:
    """Parse `ps -o etime` output like ``[[dd-]hh:]mm:ss``."""
    days = 0
    if "-" in s:
        d, _, s = s.partition("-")
        try:
            days = int(d)
        except ValueError:
            return None
    parts = [p for p in s.split(":") if p]
    try:
        nums = [int(p) for p in parts]
    except ValueError:
        return None
    if len(nums) == 2:
        h, m, sec = 0, nums[0], nums[1]
    elif len(nums) == 3:
        h, m, sec = nums
    else:
        return None
    return days * 86400 + h * 3600 + m * 60 + sec
