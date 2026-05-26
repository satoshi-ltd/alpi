"""Central daemon for all profiles under ``~/.alpi``."""

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

from alpi._proc_io import drain_tail


log = logging.getLogger("alpi.service")


# Public — orchestration


def enabled_subsystems(home: Path) -> dict[str, bool]:
    """Read which subsystems this profile wants; missing config means all on."""
    from alpi import config as cfg_mod
    cfg = cfg_mod.load(home)
    raw = getattr(cfg, "service", None) or {}
    return {
        "gateway": bool(raw.get("gateway", True)),
        "schedule": bool(raw.get("schedule", True)),
        "alp": bool(raw.get("alp", True)),
        "workgroups": bool(raw.get("workgroups", True)),
        "host": bool(raw.get("host", True)),
    }


def daemon_pid_path(root: Path) -> Path:
    return root / "service.pid"


def daemon_log_path(root: Path) -> Path:
    return root / "logs" / "service.log"


def daemon_running_pid(root: Path) -> int | None:
    """Liveness check for the central PID file."""
    p = daemon_pid_path(root)
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


def stop_daemon(root: Path, *, timeout: float = 5.0) -> bool:
    """SIGTERM the central daemon."""
    pid = daemon_running_pid(root)
    if pid is None:
        return False
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        return False
    deadline = time.time() + timeout
    while time.time() < deadline:
        if daemon_running_pid(root) is None:
            return True
        time.sleep(0.1)
    try:
        os.kill(pid, signal.SIGKILL)
    except OSError:
        pass
    return True


def serve_all(root: Path) -> None:
    """Foreground entry point for the central daemon."""
    from alpi import home as home_mod

    _configure_logging_daemon(root)
    profiles = home_mod.list_profiles(root)
    log.info("central service starting · profiles=%s", ",".join(profiles))
    _set_proctitle_daemon(len(profiles))
    _write_daemon_pid(root)
    try:
        asyncio.run(_main_all(root, profiles))
    except KeyboardInterrupt:
        pass
    finally:
        _clear_daemon_pid(root)
        log.info("central service stopped")


def _prefetch_assets() -> None:
    """Spawn a daemon thread that pre-warms heavy assets.

    Pre-loads the fastembed ONNX session and ensures the Chromium
    binary so the first user-visible RAG/browser call doesn't pay the
    cold-cache lag. Each step has its own try/except so one failure
    doesn't take down the other.
    """
    import threading

    def _run() -> None:
        from alpi.core import embed
        from alpi.core._playwright import ensure_chromium

        for label, fn in (("embedder", embed.ensure_weights_cached),
                           ("chromium", ensure_chromium)):
            try:
                fn()
            except Exception:
                log.exception("prefetch %s failed (non-fatal)", label)
        log.info("prefetch: done")

    threading.Thread(target=_run, name="alpi-prefetch", daemon=True).start()


async def _main_all(root: Path, profiles: list[str]) -> None:
    from alpi import home as home_mod

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:
            pass
    loop.call_later(5.0, _prefetch_assets)

    # Load only the root .env once for daemon-wide vars (ALPI_PLATFORM, telemetry). Per-profile secrets stay out of os.environ — read on-demand by resolve_model.
    _load_env(home_mod.alpi_root())

    tasks: list[asyncio.Task] = []
    for profile in profiles:
        home = home_mod.home_for(profile)
        try:
            subsystems = enabled_subsystems(home)
        except Exception:  # noqa: BLE001
            log.exception("profile %s: cannot read config — skipping boot", profile)
            continue
        tasks.extend(_profile_tasks(home, profile, subsystems))

    if not tasks:
        log.warning("no profile subsystems enabled — central will idle")
        await stop.wait()
        return

    await stop.wait()
    for t in tasks:
        t.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)


def _profile_tasks(
    home: Path, profile: str, subsystems: dict[str, bool],
) -> list[asyncio.Task]:
    """Build the supervised task set for one profile."""
    out: list[asyncio.Task] = []
    if subsystems.get("gateway"):
        out.append(asyncio.create_task(
            _supervise(_run_gateway, home, profile, "gateway"),
            name=f"{profile}/gateway",
        ))
    if subsystems.get("schedule"):
        out.append(asyncio.create_task(
            _supervise(_run_scheduler, home, profile, "schedule"),
            name=f"{profile}/schedule",
        ))
    if subsystems.get("alp"):
        out.append(asyncio.create_task(
            _supervise(_run_alp, home, profile, "alp"),
            name=f"{profile}/alp",
        ))
    # Host plane is default-only.
    if subsystems.get("host") and profile == "default":
        out.append(asyncio.create_task(
            _supervise(_run_host, home, profile, "host"),
            name=f"{profile}/host",
        ))
    if subsystems.get("workgroups"):
        out.append(asyncio.create_task(
            _supervise(_run_workgroup_poller, home, profile, "workgroups"),
            name=f"{profile}/workgroups",
        ))
        out.append(asyncio.create_task(
            _supervise(_run_preempt_watcher, home, profile, "workgroup-preempt"),
            name=f"{profile}/workgroup-preempt",
        ))
    return out


async def _supervise(coro_fn, home: Path, profile: str, name: str) -> None:
    """Wrap a subsystem so one crash does not take down the others."""
    try:
        # Some subsystems need the profile name; others only need home.
        if name in ("alp", "workgroups", "workgroup-preempt", "host"):
            await coro_fn(home, profile)
        else:
            await coro_fn(home)
    except asyncio.CancelledError:
        raise
    except Exception:  # noqa: BLE001
        log.exception("subsystem %s crashed — staying down, other subsystems unaffected", name)


async def _run_gateway(home: Path) -> None:
    from alpi.gateway.run import serve as gw_serve
    await gw_serve(home)


async def _run_scheduler(home: Path) -> None:
    from alpi.scheduler.run import serve as sch_serve
    await sch_serve(home)


async def _run_workgroup_poller(home: Path, profile: str) -> None:
    """Watch workgroups for new triggers and dispatch turns."""
    from alpi.alp import subscription as sub_mod
    from alpi.alp import workgroup as wg_mod
    from alpi.alp import workgroup_client as wc

    log.info("workgroup poller running (tick=%ss)", WORKGROUP_TICK_SECONDS)
    while True:
        try:
            # Pull member workgroups, then check whether they need a response.
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

            # Hub workgroups use the local transcript.
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
    """Decide whether a member-side workgroup should dispatch."""
    from alpi.alp import keys as _keys
    from alpi.alp import subscription as sub_mod

    own_pubkey = _keys.load_or_generate(home).pubkey_b64()
    trigger, new_responded = _should_dispatch(
        profile, own_pubkey, sub.recent_posts or [], sub.last_responded_seq,
    )
    # Advance the pointer when the latest post is ours.
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
    if (sub.wg_id, profile) in _INFLIGHT:
        log.info(
            "wg poller: %s skipped (in-flight dispatch, reason=%s)",
            sub.wg_id, trigger,
        )
        return
    log.info(
        "wg poller: %s dispatching turn (reason=%s, member-of)",
        sub.wg_id, trigger,
    )
    # Snapshot the round identity so stale reactions can be rejected.
    round_seq = max(
        (
            int(p.get("seq", 0))
            for p in (sub.recent_posts or [])
            if str(p.get("from") or "") == sub.hub_pubkey
        ),
        default=0,
    )
    started_against = _latest_hub_task_seq_for(home, sub.wg_id, sub.hub_pubkey)
    sub.last_responded_seq = new_responded
    sub.last_dispatch_at = _utcnow_iso()
    sub_mod.upsert(home, sub)
    # Spawn dispatch in the background so polling and preemption keep moving.
    _spawn_dispatch(
        sub.wg_id,
        _dispatch_workgroup_turn(
            home, profile, sub.wg_id, sub.name, trigger,
            round_hub_seq=round_seq,
            hub_pubkey=sub.hub_pubkey,
            started_against_task_seq=started_against,
        ),
    )


# Members stay silent after a hub follow-up; the watchdog re-pokes the hub.
_HUB_FOLLOWUP_STALE_SECONDS = 60


_INFLIGHT: dict[tuple[str, str], dict] = {}


# Strong refs for fire-and-forget dispatch tasks.
_BG_TASKS: set[asyncio.Task] = set()


def _spawn_dispatch(wg_id: str, coro) -> asyncio.Task:
    """Schedule a dispatch coroutine and keep a strong task reference."""
    task = asyncio.create_task(coro, name=f"wg-dispatch-{wg_id}")
    _BG_TASKS.add(task)
    task.add_done_callback(_BG_TASKS.discard)
    return task


def _latest_hub_task_seq_for(
    home: Path, wg_id: str, hub_pubkey: str,
) -> int:
    """Highest task seq seen for the hub pubkey."""
    from alpi.alp import subscription as sub_mod
    from alpi.alp import tasks as wg_tasks
    from alpi.alp import workgroup as wg_mod

    posts: list[dict] = []
    wg = wg_mod.load(home, wg_id)
    if wg is not None and wg.meta.hub_pubkey == hub_pubkey:
        try:
            posts = _all_hub_posts_decrypted(home, wg)
        except Exception:  # noqa: BLE001
            posts = []
    else:
        sub = sub_mod.get(home, wg_id)
        if sub is not None:
            posts = list(sub.recent_posts or [])

    best = 0
    for p in posts:
        if str(p.get("from") or "") != hub_pubkey:
            continue
        evs = wg_tasks.parse_post(
            str(p.get("text") or ""),
            int(p.get("seq", 0)),
            str(p.get("from") or ""),
        )
        if any(e.kind == "task" for e in evs):
            seq = int(p.get("seq", 0))
            if seq > best:
                best = seq
    return best


async def _maybe_dispatch_for_hub(
    home: Path, profile: str, wg, recent: list[dict],
) -> None:
    """Decide whether a hub-side workgroup should dispatch."""
    from alpi.alp import keys as _keys

    own_pubkey = _keys.load_or_generate(home).pubkey_b64()
    last_responded = _get_hub_responded_seq(home, wg.meta.id)
    trigger, new_responded = _should_dispatch(
        profile, own_pubkey, recent, last_responded,
    )
    if not trigger:
        if new_responded > last_responded:
            _set_hub_responded_seq(home, wg.meta.id, new_responded)
        await _maybe_watchdog_close(home, profile, wg, recent)
        return
    state = _load_poller_state(home)
    last = state.get("hub_last_dispatch_at", {}).get(wg.meta.id, "")
    if _in_cooldown_str(last):
        log.info(
            "wg poller: %s skipped (cooldown, reason=%s)",
            wg.meta.id, trigger,
        )
        return
    if (wg.meta.id, profile) in _INFLIGHT:
        log.info(
            "wg poller: %s skipped (in-flight dispatch, reason=%s)",
            wg.meta.id, trigger,
        )
        return
    log.info(
        "wg poller: %s dispatching turn (reason=%s, hub-of)",
        wg.meta.id, trigger,
    )
    started_against = _latest_hub_task_seq_for(
        home, wg.meta.id, wg.meta.hub_pubkey,
    )
    _set_hub_responded_seq(home, wg.meta.id, new_responded)
    _mark_hub_dispatched(home, wg.meta.id)
    _spawn_dispatch(
        wg.meta.id,
        _dispatch_workgroup_turn(
            home, profile, wg.meta.id, wg.meta.name, trigger,
            hub_pubkey=wg.meta.hub_pubkey,
            started_against_task_seq=started_against,
        ),
    )


_HUB_WATCHDOG_REFIRE_SECONDS = 5 * 60  # 5 min between re-fires


async def _maybe_watchdog_close(
    home: Path, profile: str, wg, recent: list[dict],
) -> None:
    """Re-poke stalled hub workgroups so they can close or keep waiting."""
    from alpi.alp import tasks as wg_tasks

    if not recent:
        return
    active = wg_tasks.active_task(recent, hub_pubkey=wg.meta.hub_pubkey)
    if active is None:
        return
    posts_in_task = [
        p for p in recent if int(p.get("seq", 0)) >= active.opened_seq
    ]
    if not posts_in_task:
        return
    last_post = posts_in_task[-1]
    last_seq = int(last_post.get("seq", 0))

    last_post_ts = str(last_post.get("ts", "")).strip()
    if not last_post_ts:
        return
    import datetime as _dt
    try:
        last_dt = _dt.datetime.strptime(last_post_ts, "%Y-%m-%dT%H:%M:%SZ")
        last_dt = last_dt.replace(tzinfo=_dt.timezone.utc)
    except ValueError:
        return
    age = (_dt.datetime.now(tz=_dt.timezone.utc) - last_dt).total_seconds()
    if age < _HUB_FOLLOWUP_STALE_SECONDS:
        return

    fired_seq = _get_hub_watchdog_seq(home, wg.meta.id)
    state = _load_poller_state(home)
    last_dispatch_str = state.get("hub_last_dispatch_at", {}).get(
        wg.meta.id, ""
    )
    if last_seq <= fired_seq:
        # Allow re-fire only after a substantial gap.
        if not last_dispatch_str:
            return
        try:
            last_dispatch_dt = _dt.datetime.strptime(
                last_dispatch_str, "%Y-%m-%dT%H:%M:%SZ",
            ).replace(tzinfo=_dt.timezone.utc)
        except ValueError:
            return
        elapsed_since_fire = (
            _dt.datetime.now(tz=_dt.timezone.utc) - last_dispatch_dt
        ).total_seconds()
        if elapsed_since_fire < _HUB_WATCHDOG_REFIRE_SECONDS:
            return

    if _in_cooldown_str(last_dispatch_str):
        return
    if (wg.meta.id, profile) in _INFLIGHT:
        return
    last_author_is_hub = str(
        last_post.get("from") or ""
    ) == wg.meta.hub_pubkey
    stall_kind = (
        "hub talked last" if last_author_is_hub else "member talked last"
    )
    reason = (
        f"watchdog: {stall_kind} (seq #{last_seq}), nothing new for "
        f"{int(age)}s — closure-or-silence only"
    )
    log.info(
        "wg poller: %s dispatching watchdog (reason=%s)",
        wg.meta.id, reason,
    )
    started_against = _latest_hub_task_seq_for(
        home, wg.meta.id, wg.meta.hub_pubkey,
    )
    _set_hub_watchdog_seq(home, wg.meta.id, last_seq)
    _mark_hub_dispatched(home, wg.meta.id)
    _spawn_dispatch(
        wg.meta.id,
        _dispatch_workgroup_turn(
            home, profile, wg.meta.id, wg.meta.name, reason,
            closure_only=True,
            hub_pubkey=wg.meta.hub_pubkey,
            started_against_task_seq=started_against,
        ),
    )


def _all_hub_posts_decrypted(home: Path, wg) -> list[dict]:
    """Return the decrypted hub transcript."""
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
    """Return new decrypted hub posts after the saved cursor."""
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


# Hub-side cursor and cooldown state live under the profile root.


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


def _get_hub_watchdog_seq(home: Path, wg_id: str) -> int:
    """Latest hub seq for which the watchdog already fired."""
    state = _load_poller_state(home)
    return int(state.get("hub_watchdog_fired_seq", {}).get(wg_id, 0))


def _set_hub_watchdog_seq(home: Path, wg_id: str, seq: int) -> None:
    state = _load_poller_state(home)
    table = state.setdefault("hub_watchdog_fired_seq", {})
    table[wg_id] = int(seq)
    _save_poller_state(home, state)


def _utcnow_iso() -> str:
    import datetime as _dt
    return _dt.datetime.now(tz=_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _mark_sub_dispatched(home: Path, wg_id: str) -> None:
    """Persist the subscription dispatch timestamp."""
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
    """Return ``True`` when ``stamp`` is still inside the cooldown."""
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
    """Decide whether the poller should wake the local agent."""
    from alpi.alp import tasks as wg_tasks

    if not recent_posts:
        return None, last_responded_seq

    unprocessed = sorted(
        (p for p in recent_posts if int(p.get("seq", 0)) > last_responded_seq),
        key=lambda p: int(p.get("seq", 0)),
    )
    if not unprocessed:
        return None, last_responded_seq
    high_seq = int(unprocessed[-1].get("seq", 0))

    skip_through = last_responded_seq
    for p in unprocessed:
        if str(p.get("from") or "") != own_pubkey:
            continue
        events = wg_tasks.parse_post(
            str(p.get("text") or ""),
            int(p.get("seq", 0)),
            str(p.get("from") or ""),
        )
        if not any(e.kind == "task" for e in events):
            skip_through = int(p.get("seq", 0))
    actionable = [
        p for p in unprocessed if int(p.get("seq", 0)) > skip_through
    ]
    active = wg_tasks.active_task(recent_posts)

    for post in actionable:
        seq = int(post.get("seq", 0))
        text = str(post.get("text") or "")
        mentions = wg_tasks.mentions_in(text)
        is_self = str(post.get("from") or "") == own_pubkey
        events = wg_tasks.parse_post(text, seq, str(post.get("from") or ""))
        has_task = any(e.kind == "task" for e in events)

        if is_self and not has_task:
            continue
        if not is_self and profile in mentions:
            # `@` inside `#done` is synthesis, not handoff.
            if any(e.kind == "done" for e in events):
                continue
            return f"@{profile} mentioned (seq #{seq})", high_seq
        if has_task and not mentions:
            if active is None or active.opened_seq != seq:
                continue
            return f"collective #task opened (seq #{seq})", high_seq
        if not is_self and active is not None:
            # The hub of the active task always stays in the loop.
            if active.opened_by == own_pubkey:
                return (
                    f"new content in active task we opened (seq #{seq})",
                    high_seq,
                )
            opener_mentions: list[str] = []
            for p in recent_posts:
                if int(p.get("seq", 0)) != active.opened_seq:
                    continue
                opener_mentions = wg_tasks.mentions_in(
                    str(p.get("text") or "")
                )
                break
            if not opener_mentions or profile in opener_mentions:
                return (
                    f"new content in active task (seq #{seq})",
                    high_seq,
                )

    return None, high_seq


_TURN_TIMEOUT_SECONDS = 300
_TURN_SIGTERM_GRACE_SECONDS = 5


def turn_log_path(home: Path) -> Path:
    return home / "alp" / "turns.jsonl"


def _append_turn_event(home: Path, event: dict[str, Any]) -> None:
    import json
    p = turn_log_path(home)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        is_new = not p.exists()
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, separators=(",", ":")) + "\n")
            f.flush()
        if is_new:
            try:
                os.chmod(p, 0o600)
            except OSError:
                pass
    except Exception as e:  # noqa: BLE001
        log.warning("turn-log append failed: %s", e)


def _hub_post_count(home: Path, wg_id: str) -> int:
    try:
        from alpi.alp import workgroup as wg_mod
        wg = wg_mod.load(home, wg_id)
        if wg is None:
            return 0
        d = home / "alp" / "workgroups" / wg_id
        from alpi.alp.workgroup import _read_transcript
        return len(_read_transcript(d))
    except Exception:
        return 0


def _sub_post_count(home: Path, wg_id: str) -> int:
    try:
        from alpi.alp import subscription as sub_mod
        sub = sub_mod.get(home, wg_id)
        if sub is None:
            return 0
        return int(sub.last_seq or 0)
    except Exception:
        return 0


def _post_count_for_role(home: Path, wg_id: str) -> int:
    n = _hub_post_count(home, wg_id)
    if n > 0:
        return n
    return _sub_post_count(home, wg_id)


# Previous role-aware addendum removed; rotation checks enforce it now.


async def _dispatch_workgroup_turn(
    home: Path, profile: str, wg_id: str, wg_name: str, reason: str,
    *, closure_only: bool = False, round_hub_seq: int | None = None,
    hub_pubkey: str = "", started_against_task_seq: int = 0,
) -> None:
    """Spawn a background ``chat --once`` turn for a workgroup."""
    if closure_only:
        prompt = (
            f"[workgroup-watchdog] '#{wg_name or wg_id}' "
            f"(wg_id={wg_id}). {reason}.\n\n"
            "You are the HUB and you were the most recent poster in "
            "this task. Members have stayed silent — that is "
            "intentional, the engagement rules tell them not to "
            "back-and-forth with the hub.\n\n"
            "TURN-ROTATION RULE: the hub never speaks twice in a "
            "row about content. Your only valid outcomes this turn "
            "are:\n"
            "  (A) Close the task. If the transcript already "
            "contains enough material to answer the active `#task`, "
            f"call `workgroup_post(wg_id=\"{wg_id}\", text=\"#done "
            "<one-line synthesis of the recommendation>\")` and "
            "stop.\n"
            "  (B) End the turn WITHOUT posting. If you genuinely "
            "need more from the members but they have not "
            "delivered, just end the turn — a future member post "
            "will wake you again. Do NOT post more analysis, more "
            "caveats, more questions, or another @-mention. Silence "
            "preserves the rotation.\n\n"
            "DO NOT invent option C. Posting any non-`#done` "
            "message here is a protocol violation: it monopolises "
            "the transcript and burns budget."
        )
        env_extra = {"ALPI_WORKGROUP_CLOSURE_ONLY": "1"}
    else:
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
            "\n\nFollow your `Workgroup engagement rules` exactly. "
            "Valid actions, in priority:"
            "\n  1. [hub only] If the deliverable is in the "
            "transcript AND full quorum is reached (every member "
            "has posted substantive content or `#skip`; at least "
            "one member's post is substantive), post "
            f"`workgroup_post(wg_id=\"{wg_id}\", "
            "text=\"#done <one-line result summary>\")` to close.\n"
            "  2. [member, you'll use slow tools next] If your "
            "next step is web_fetch / research / multi-step "
            "delegate that will take >30s, FIRST post "
            f"`workgroup_post(wg_id=\"{wg_id}\", text=\"#working "
            "<one-line reason>\")` to signal the hub to wait, then "
            "do the tools, then come back and post substantive. "
            "Without this, the hub may close around you.\n"
            "  3. [member, your FIRST post on this active task] "
            "Find your angle from YOUR role's identity (your "
            "public_bio + memories) and post substantive content. "
            "Even a single concrete sentence is value. The hub "
            "assembled this workgroup specifically for the listed "
            "members — if you're here, your lens applies. Default "
            "to substantive, NOT to `#skip`.\n"
            "  4. [member, follow-up rounds] Post a NEW "
            "contribution (fact, evidence, blocker not raised "
            "yet). Paraphrase of earlier content is NOT a "
            "contribution.\n"
            "  5. [member, last resort] Post `#skip <reason>` "
            "ONLY if your identity has zero overlap with this "
            "task, OR you already said your piece on this task: "
            f"`workgroup_post(wg_id=\"{wg_id}\", text=\"#skip "
            "<one-line reason>\")`.\n"
            "  6. Otherwise, end the turn without posting "
            "(genuine silence — not your turn, no slot left, or "
            "still working from a prior `#working`)."
            "\n\nLANGUAGE: write every post — your contribution, "
            "`#working` reasons, `#skip` reasons, `#done` results — "
            "in the same language as the active `#task`. If the "
            "task is in Spanish, post in Spanish. If French, French. "
            "Match the user, do not default to English."
        )
        env_extra = {}
    from alpi.home import effective_profile_env as _effective_profile_env
    env = _effective_profile_env(home, extra={
        "ALPI_HOME": str(home),
        "ALPI_WORKGROUP_DISPATCH": wg_id,
        **({"ALPI_WORKGROUP_ROUND_HUB_SEQ": str(round_hub_seq)} if (round_hub_seq is not None and round_hub_seq > 0) else {}),
        **env_extra,
    })
    argv = [
        sys.executable, "-m", "alpi", "-p", profile,
        "chat", "--once", prompt,
    ]
    posts_before = _post_count_for_role(home, wg_id)
    started_at = time.monotonic()
    try:
        proc = await asyncio.create_subprocess_exec(
            *argv,
            env=env,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
    except OSError as e:
        log.warning("wg poller: subprocess spawn failed: %s", e)
        _append_turn_event(home, {
            "ts": _utcnow_iso(), "event": "spawn-failed",
            "profile": profile, "wg_id": wg_id, "wg_name": wg_name,
            "reason": reason, "error": str(e),
        })
        return
    # Bounded drain — full pipe + memory cap.
    stderr_task = asyncio.create_task(drain_tail(proc.stderr))

    _append_turn_event(home, {
        "ts": _utcnow_iso(), "event": "start",
        "profile": profile, "wg_id": wg_id, "wg_name": wg_name,
        "reason": reason, "pid": proc.pid,
    })

    # Register in-flight state so the preempt watcher can SIGTERM us.
    _INFLIGHT[(wg_id, profile)] = {
        "proc": proc,
        "profile": profile,
        "wg_name": wg_name,
        "hub_pubkey": hub_pubkey,
        "started_against_task_seq": int(started_against_task_seq),
        "started_at": started_at,
    }

    timed_out = False
    try:
        try:
            rc = await asyncio.wait_for(
                proc.wait(), timeout=_TURN_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            timed_out = True
            try:
                proc.terminate()  # SIGTERM
            except ProcessLookupError:
                pass
            try:
                rc = await asyncio.wait_for(
                    proc.wait(), timeout=_TURN_SIGTERM_GRACE_SECONDS,
                )
            except asyncio.TimeoutError:
                try:
                    proc.kill()  # SIGKILL
                except ProcessLookupError:
                    pass
                try:
                    rc = await proc.wait()
                except Exception:  # noqa: BLE001
                    rc = -9
            log.warning(
                "wg poller: turn for %s exceeded %ss — killed",
                wg_id, _TURN_TIMEOUT_SECONDS,
            )
        except asyncio.CancelledError:
            # Cancellation doesn't kill the child — terminate explicitly to avoid orphan.
            try:
                proc.terminate()
            except ProcessLookupError:
                pass
            try:
                # Use a bounded shielded wait because we're already cancelled.
                rc = await asyncio.shield(asyncio.wait_for(
                    proc.wait(), timeout=_TURN_SIGTERM_GRACE_SECONDS,
                ))
            except (asyncio.TimeoutError, asyncio.CancelledError):
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass
                try:
                    rc = await asyncio.shield(proc.wait())
                except Exception:  # noqa: BLE001
                    rc = -9
            raise
    finally:
        info = _INFLIGHT.pop((wg_id, profile), {})
    preempted = bool(info.get("preempted"))
    preempted_by_seq = int(info.get("preempted_by_seq", 0))

    duration_s = round(time.monotonic() - started_at, 2)
    posts_after = _post_count_for_role(home, wg_id)
    posts_added = max(0, posts_after - posts_before)
    err_preview = ""
    try:
        stderr_tail = await stderr_task
    except Exception:  # noqa: BLE001
        stderr_tail = ""
    if rc != 0:
        err_preview = stderr_tail[-300:]
        if not (timed_out or preempted):
            log.warning(
                "wg poller: turn for %s exited rc=%s: %s",
                wg_id, rc, err_preview,
            )

    if preempted:
        event = "preempted"
        extra = {"preempted_by_seq": preempted_by_seq, "killed": True}
    elif timed_out:
        event = "timeout"
        extra = {"killed": True}
    else:
        event = "end"
        extra = {"error": err_preview} if err_preview else {}
    _append_turn_event(home, {
        "ts": _utcnow_iso(),
        "event": event,
        "profile": profile, "wg_id": wg_id, "wg_name": wg_name,
        "duration_s": duration_s, "rc": rc,
        "posts_added": posts_added,
        **extra,
    })


WORKGROUP_TICK_SECONDS = 30
_PREEMPT_TICK_SECONDS = 5


async def _run_preempt_watcher(home: Path, profile: str) -> None:
    """Watch for new hub tasks and preempt in-flight dispatches."""
    log.info("workgroup preempt watcher running (tick=%ss)", _PREEMPT_TICK_SECONDS)
    while True:
        try:
            for key in list(_INFLIGHT.keys()):
                info = _INFLIGHT.get(key)
                if info is None or info.get("preempted"):
                    continue
                # Cross-profile reads use the wrong home → false closure.
                if info.get("profile") != profile:
                    continue
                proc = info.get("proc")
                if proc is None or proc.returncode is not None:
                    continue
                hub_pubkey = str(info.get("hub_pubkey") or "")
                if not hub_pubkey:
                    continue
                wg_id = key[0] if isinstance(key, tuple) else key
                started_against = int(info.get("started_against_task_seq", 0))
                latest = _latest_hub_task_seq_for(home, wg_id, hub_pubkey)
                if latest <= started_against:
                    continue
                # ALP.md: only fresh `#task` preempts; `#done` is caught by
                # `_check_member_round_fresh` (SDK `stale-round`).
                info["preempted"] = True
                info["preempted_by_seq"] = latest
                try:
                    proc.terminate()
                except ProcessLookupError:
                    pass
                log.info(
                    "wg preempt: %s SIGTERM (new #task seq #%d, dispatch "
                    "started against #%d)",
                    wg_id, latest, started_against,
                )
        except Exception:  # noqa: BLE001
            log.exception("preempt watcher tick failed")
        await asyncio.sleep(_PREEMPT_TICK_SECONDS)


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


async def _run_host(home: Path, profile: str) -> None:
    if profile != "default":
        log.warning("host subsystem requested for %r — only default can host", profile)
        return

    from alpi.host import approval as host_approval
    from alpi.host import chat as host_chat
    from alpi.host import config as host_config
    from alpi.host import daemon as host_daemon
    from alpi.host import device_state as host_device_state
    from alpi.host import events as host_events
    from alpi.host import handlers as host_handlers
    from alpi.host import devices as host_devices
    from alpi.host import network_rpc as host_network
    from alpi.host import outputs as host_outputs
    from alpi.host import probes as host_probes
    from alpi.host import schedule as host_schedule
    from alpi.host import tools as host_tools
    from alpi.host import workgroup_admin as host_wg_admin
    from alpi.host.network import resolve_host_tcp_bind
    from alpi.host.server import Server as HostServer

    tcp_bind = resolve_host_tcp_bind(home)
    if tcp_bind is None:
        log.info(
            "no Tailscale or LAN address found; "
            "host TCP listener disabled (Unix socket still up)",
        )
    else:
        host, port = tcp_bind
        detail = "umbrel" if os.environ.get("ALPI_PLATFORM") == "umbrel" else "auto"
        log.info("host TCP bind chosen: %s:%d (%s)", host, port, detail)

    server = HostServer(home=home, tcp_bind=tcp_bind)
    host_handlers.register(server)
    host_chat.register(server)
    host_config.register(server)
    host_device_state.register(server)
    host_daemon.register(server)
    host_events.register(server)
    host_approval.register(server)
    host_schedule.register(server)
    host_wg_admin.register(server)
    host_probes.register(server)
    host_devices.register(server)
    host_network.register(server)
    host_outputs.register(server)
    host_tools.register(server)
    await server.start()
    try:
        await server.serve_forever()
    finally:
        await server.stop()


# Helpers


def _set_proctitle_daemon(n_profiles: int) -> None:
    try:
        import setproctitle
        setproctitle.setproctitle(f"alpi (daemon, {n_profiles} profiles)")
    except Exception:  # noqa: BLE001
        pass


def _configure_logging_daemon(root: Path) -> None:
    from alpi._log import BACKUP_COUNT, FORMAT, MAX_BYTES

    p = daemon_log_path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    handlers: list[logging.Handler] = [
        RotatingFileHandler(p, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT),
    ]
    if sys.stderr.isatty():
        handlers.append(logging.StreamHandler())
    logging.basicConfig(
        level=logging.INFO,
        format=FORMAT,
        handlers=handlers,
        force=True,
    )


def _write_daemon_pid(root: Path) -> None:
    p = daemon_pid_path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(str(os.getpid()))


def _clear_daemon_pid(root: Path) -> None:
    p = daemon_pid_path(root)
    if p.exists():
        try:
            p.unlink()
        except OSError:
            pass


def _load_env(home: Path) -> None:
    env_path = home / ".env"
    if env_path.exists():
        from dotenv import load_dotenv
        load_dotenv(env_path, override=False)


# OS-level daemon install (single supervisor, every profile under one process)


_DAEMON_LABEL = "com.alpi.daemon"


def daemon_installed() -> bool:
    backend = _detect_backend()
    if backend == "launchd":
        return _daemon_plist_path().exists()
    if backend == "systemd":
        return _daemon_unit_path().exists()
    return False


def daemon_running(root: Path) -> bool:
    return daemon_running_pid(root) is not None


def install_daemon(root: Path) -> str:
    """Register the central daemon unit."""
    backend = _detect_backend()
    alpi_bin = _locate_alpi()
    if backend == "launchd":
        _launchd_install_daemon(root, alpi_bin)
        return "launchd"
    if backend == "systemd":
        _systemd_install_daemon(root, alpi_bin)
        return "systemd"
    raise ServiceError(f"unsupported platform: {platform.system()}")


def uninstall_daemon() -> str:
    backend = _detect_backend()
    if backend == "launchd":
        _launchd_uninstall_daemon()
        return "launchd"
    if backend == "systemd":
        _systemd_uninstall_daemon()
        return "systemd"
    raise ServiceError(f"unsupported platform: {platform.system()}")


def daemon_status(root: Path) -> dict[str, Any]:
    """Return the daemon status snapshot."""
    from alpi import home as home_mod

    pid = daemon_running_pid(root)
    backend = "launchd" if (
        _detect_backend() == "launchd" and _daemon_plist_path().exists()
    ) else "systemd" if (
        _detect_backend() == "systemd" and _daemon_unit_path().exists()
    ) else None

    profiles: dict[str, dict[str, bool]] = {}
    for name in home_mod.list_profiles(root):
        try:
            profiles[name] = enabled_subsystems(home_mod.home_for(name))
        except Exception:  # noqa: BLE001
            profiles[name] = {}

    info: dict[str, Any] = {
        "pid": pid,
        "running": pid is not None,
        "installed_via": backend,
        "profiles": profiles,
    }
    if pid is not None:
        info["uptime_seconds"] = _uptime_seconds(pid)
    return info


class ServiceError(Exception):
    """Surface install/uninstall failures to the CLI."""


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


_DAEMON_PLIST_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
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


def _daemon_plist_path() -> Path:
    return (
        Path.home() / "Library" / "LaunchAgents" / "com.alpi.daemon.plist"
    )


def _daemon_program_args_xml(alpi_bin: str) -> str:
    parts = alpi_bin.split() + ["daemon", "start"]
    return "\n".join(f"    <string>{x}</string>" for x in parts)


def _launchd_install_daemon(root: Path, alpi_bin: str) -> None:
    plist = _daemon_plist_path()
    plist.parent.mkdir(parents=True, exist_ok=True)
    log_p = daemon_log_path(root)
    log_p.parent.mkdir(parents=True, exist_ok=True)

    plist.write_text(_DAEMON_PLIST_TEMPLATE.format(
        label=_DAEMON_LABEL,
        program_args=_daemon_program_args_xml(alpi_bin),
        log=str(log_p),
    ))

    uid = os.getuid()
    # Reinstall by booting out first so template changes apply.
    _run(["launchctl", "bootout", f"gui/{uid}", str(plist)], check=False)
    res = _run(["launchctl", "bootstrap", f"gui/{uid}", str(plist)], check=False)
    if res.returncode != 0:
        raise ServiceError(
            f"launchctl bootstrap failed (rc={res.returncode}): "
            f"{(res.stderr or res.stdout).strip()}"
        )


def _launchd_uninstall_daemon() -> None:
    plist = _daemon_plist_path()
    if not plist.exists():
        return
    uid = os.getuid()
    _run(["launchctl", "bootout", f"gui/{uid}", str(plist)], check=False)
    plist.unlink(missing_ok=True)


def _daemon_unit_path() -> Path:
    return (
        Path.home() / ".config" / "systemd" / "user" / "alpi-daemon.service"
    )


_DAEMON_UNIT_TEMPLATE = """[Unit]
Description=alpi central service (all profiles)
After=network-online.target

[Service]
Type=simple
ExecStart={exec_start}
Restart=on-failure
RestartSec=5
StandardOutput=append:{log}
StandardError=append:{log}

[Install]
WantedBy=default.target
"""


def _systemd_install_daemon(root: Path, alpi_bin: str) -> None:
    unit = _daemon_unit_path()
    unit.parent.mkdir(parents=True, exist_ok=True)
    log_p = daemon_log_path(root)
    log_p.parent.mkdir(parents=True, exist_ok=True)

    unit.write_text(_DAEMON_UNIT_TEMPLATE.format(
        exec_start=f"{alpi_bin} daemon start",
        log=str(log_p),
    ))

    # Best-effort linger keeps the user manager alive after logout.
    linger = _run(["loginctl", "enable-linger", _current_user()], check=False)
    if linger.returncode != 0:
        log.warning(
            "loginctl enable-linger failed (rc=%s) — service may not "
            "survive logout: %s",
            linger.returncode,
            (linger.stderr or linger.stdout).strip(),
        )

    res = _run(["systemctl", "--user", "daemon-reload"], check=False)
    if res.returncode != 0:
        raise ServiceError(
            f"systemctl daemon-reload failed (rc={res.returncode}): "
            f"{(res.stderr or res.stdout).strip()}{_systemd_hint(res)}"
        )
    res = _run(
        ["systemctl", "--user", "enable", "--now", "alpi-daemon.service"],
        check=False,
    )
    if res.returncode != 0:
        raise ServiceError(
            f"systemctl enable --now failed (rc={res.returncode}): "
            f"{(res.stderr or res.stdout).strip()}{_systemd_hint(res)}"
        )


def _current_user() -> str:
    import getpass
    return getpass.getuser()


def _systemd_uninstall_daemon() -> None:
    unit = _daemon_unit_path()
    if not unit.exists():
        return
    _run(
        ["systemctl", "--user", "disable", "--now", "alpi-daemon.service"],
        check=False,
    )
    unit.unlink(missing_ok=True)
    _run(["systemctl", "--user", "daemon-reload"], check=False)


def _systemd_hint(result: subprocess.CompletedProcess) -> str:
    combined = (result.stderr or "") + (result.stdout or "")
    if "Failed to connect to bus" in combined or "No such file" in combined:
        return (
            "\nNote: `systemd --user` must be available. On WSL without "
            "`systemd=true` in /etc/wsl.conf, or in minimal containers, "
            "run `alpi daemon start` in a tmux/screen session instead."
        )
    return ""


def _run(cmd: list[str], *, check: bool) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def _uptime_seconds(pid: int) -> int | None:
    """Best-effort process uptime."""
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
    """Parse ``ps -o etime`` output."""
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
