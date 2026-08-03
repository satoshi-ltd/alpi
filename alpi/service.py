"""Central daemon for all profiles under ``~/.alpi``."""

from __future__ import annotations

import asyncio
import hashlib
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

_PROFILE_RESCAN_SECONDS = 5.0


# Public — orchestration


def enabled_subsystems(home: Path) -> dict[str, bool]:
    """Read which subsystems this profile wants; missing config means all on."""
    from alpi import config as cfg_mod
    return _subsystem_flags(cfg_mod.load(home))


def _subsystem_flags(cfg) -> dict[str, bool]:
    raw = getattr(cfg, "service", None) or {}
    return {
        "schedule": bool(raw.get("schedule", True)),
        "alp": bool(raw.get("alp", True)),
        "workgroups": bool(raw.get("workgroups", True)),
        "host": bool(raw.get("host", True)),
    }


def daemon_pid_path(root: Path) -> Path:
    return root / "service.pid"


def daemon_log_path(root: Path) -> Path:
    return root / "logs" / "service.log"


def _acquire_singleton_lock(root: Path):
    # OS-held lock beats the pidfile check: a stale pid + a TOCTOU race let two daemons start at once; freed on exit/crash.
    lock_path = root / "service.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = open(lock_path, "w")  # noqa: SIM115 — held for the daemon's lifetime
    try:
        if sys.platform == "win32":
            import msvcrt
            msvcrt.locking(fd.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        fd.close()
        return None
    return fd


def _proc_starttime(pid: int) -> str | None:
    # /proc/<pid>/stat field 22 — survives container PID reuse. None on non-Linux.
    try:
        with open(f"/proc/{pid}/stat", "rb") as f:
            data = f.read()
    except OSError:
        return None
    rparen = data.rfind(b")")
    if rparen < 0:
        return None
    tail = data[rparen + 1:].split()
    if len(tail) < 20:
        return None
    try:
        return tail[19].decode("ascii")
    except UnicodeDecodeError:
        return None


def _unlink_stale_pidfile(p: Path) -> None:
    try:
        p.unlink()
    except OSError as e:
        log.warning("stale pidfile %s could not be removed: %s", p, e)


def daemon_running_pid(root: Path) -> int | None:
    # starttime check guards against PID reuse across container restarts; os.kill alone trusts any squatter.
    p = daemon_pid_path(root)
    if not p.exists():
        return None
    try:
        raw = p.read_text().strip()
    except OSError:
        return None
    if not raw:
        return None
    parts = raw.split()
    try:
        pid = int(parts[0])
    except ValueError:
        return None
    expected_start = parts[1] if len(parts) >= 2 else None
    try:
        os.kill(pid, 0)
    except OSError:
        _unlink_stale_pidfile(p)
        return None
    if expected_start is not None:
        actual_start = _proc_starttime(pid)
        # actual_start is None on non-Linux — can't verify → trust the weak check.
        if actual_start is not None and actual_start != expected_start:
            _unlink_stale_pidfile(p)
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
    lock = _acquire_singleton_lock(root)
    if lock is None:
        log.warning(
            "another alpi daemon already holds %s — refusing to start a second",
            root / "service.lock",
        )
        return
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
        lock.close()
        log.info("central service stopped")


# Delayed past the boot reconnection storm on purpose: a chromium unzip + ONNX load at boot+5s starved small Docker hosts right while clients were re-pairing, which read as "the machine is blocked".
_PREFETCH_DELAY_S = 600.0


def _prefetch_mode(root: Path) -> str:
    from alpi import config as cfg_mod
    from alpi import runtime

    try:
        raw = str(((cfg_mod.load(root).service or {}).get("prefetch")) or "").strip().lower()
    except Exception:  # noqa: BLE001
        raw = ""
    if raw in ("off", "all", "auto"):
        return raw
    return "off" if runtime.is_docker() else "auto"


def _profile_homes(root: Path) -> list[Path]:
    from alpi import home as home_mod

    return [_profile_home(root, p) for p in home_mod.list_profiles(root)]


def _any_profile_allows_browser(root: Path) -> bool:
    from alpi import config as cfg_mod

    for home in _profile_homes(root):
        try:
            if "browser" not in (cfg_mod.load(home).tools.deny or ()):
                return True
        except Exception:  # noqa: BLE001
            continue
    return False


def _any_profile_uses_knowledge_index(root: Path) -> bool:
    from alpi.core import store

    for home in _profile_homes(root):
        try:
            if store.store_path(home).is_file():
                return True
        except OSError:
            continue
    return False


def _prefetch_assets(root: Path) -> None:
    import threading

    mode = _prefetch_mode(root)
    if mode == "off":
        log.info("prefetch: off — heavy assets fetched on first use")
        return

    def _run() -> None:
        from alpi.core import embed
        from alpi.core._playwright import ensure_chromium

        steps: list[tuple[str, Any]] = []
        if mode == "all" or _any_profile_uses_knowledge_index(root):
            steps.append(("embedder", embed.ensure_weights_cached))
        if mode == "all" or _any_profile_allows_browser(root):
            steps.append(("chromium", ensure_chromium))
        if not steps:
            log.info("prefetch: nothing to do (no knowledge index, browser denied everywhere)")
            return
        for label, fn in steps:
            started = time.monotonic()
            try:
                fn()
                log.info("prefetch %s: done in %.1fs", label, time.monotonic() - started)
            except Exception:  # noqa: BLE001
                log.exception("prefetch %s failed (non-fatal)", label)

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
    loop.call_later(_PREFETCH_DELAY_S, _prefetch_assets, root)

    # Load only the root .env once for daemon-wide vars (ALPI_PLATFORM, telemetry). Per-profile secrets stay out of os.environ — read on-demand by resolve_model.
    _load_env(home_mod.alpi_root())

    registry: dict[str, dict[str, Any]] = {}
    _start_new_profiles(root, profiles, registry)

    if not any(rt["tasks"] for rt in registry.values()):
        log.warning(
            "no profile subsystems enabled at boot — central will rescan every %.0fs",
            _PROFILE_RESCAN_SECONDS,
        )

    while not stop.is_set():
        try:
            await asyncio.wait_for(stop.wait(), timeout=_PROFILE_RESCAN_SECONDS)
        except asyncio.TimeoutError:
            pass
        if stop.is_set():
            break
        _start_new_profiles(root, home_mod.list_profiles(root), registry)
        await _reconcile_profiles(root, registry)

    all_tasks = [
        t for rt in registry.values() for ts in rt["tasks"].values() for t in ts
    ]
    for t in all_tasks:
        t.cancel()
    await asyncio.gather(*all_tasks, return_exceptions=True)


def _profile_home(root: Path, profile: str) -> Path:
    """Resolve a profile's home against the daemon's ``root``, not ``home_mod._ROOT``."""
    if not profile or profile == "default":
        return root
    return root / "profiles" / profile


def _start_new_profiles(
    root: Path,
    profiles: list[str],
    registry: dict[str, dict[str, Any]],
) -> None:
    """Start subsystems for new profiles; per-profile errors do not block the rest."""
    for profile in profiles:
        if profile in registry:
            continue
        home = _profile_home(root, profile)
        try:
            subsystems = enabled_subsystems(home)
            fps = _reload_fingerprints(home)
        except Exception:  # noqa: BLE001
            log.exception(
                "profile %s: cannot read config — retry next tick", profile,
            )
            continue
        task_map = _profile_tasks(home, profile, subsystems)
        registry[profile] = {"tasks": task_map, "fps": fps}
        count = sum(len(ts) for ts in task_map.values())
        if count:
            log.info(
                "profile %s: started %d subsystem task(s)",
                profile, count,
            )
        else:
            log.info("profile %s: no subsystems enabled", profile)


# Hot-reloadable per profile; "host" is deliberately absent — restarting it would drop every paired client, so it only moves on explicit daemon restart.
_RELOADABLE_SUBSYSTEMS = ("schedule", "alp", "workgroups")


def _reload_fingerprints(home: Path) -> dict[str, str]:
    # Only inputs a subsystem task caches at startup belong here — schedule jobs and workgroup subscriptions are re-read every tick and must never force a restart.
    from alpi import config as cfg_mod

    cfg = cfg_mod.load(home)
    return {
        "flags": repr(sorted(_subsystem_flags(cfg).items())),
        "alp": repr((
            (cfg.alp or {}).get("tcp_port"),
            (cfg.network or {}).get("host"),
            (getattr(cfg, "host", None) or {}).get("allow_public_bind"),
        )),
    }


async def _stop_subsystem_tasks(rt: dict[str, Any], name: str) -> None:
    tasks = rt["tasks"].pop(name, [])
    for t in tasks:
        t.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


# In-place reload replaces "every settings save restarts the daemon" — on Docker that was a full container restart dropping both listeners.
async def _reconcile_profiles(
    root: Path, registry: dict[str, dict[str, Any]],
) -> None:
    for profile, rt in list(registry.items()):
        home = _profile_home(root, profile)
        if not home.exists():
            for name in list(rt["tasks"]):
                await _stop_subsystem_tasks(rt, name)
            del registry[profile]
            log.info("profile %s: home gone — subsystems stopped", profile)
            continue
        try:
            fps = _reload_fingerprints(home)
        except Exception:  # noqa: BLE001
            log.exception(
                "profile %s: reload fingerprint failed — keeping current tasks",
                profile,
            )
            continue
        if fps == rt["fps"]:
            continue
        try:
            flags = enabled_subsystems(home)
        except Exception:  # noqa: BLE001
            continue
        for name in _RELOADABLE_SUBSYSTEMS:
            want = bool(flags.get(name))
            have = bool(rt["tasks"].get(name))
            input_changed = fps.get(name) != rt["fps"].get(name)
            if want == have and not (want and input_changed):
                continue
            await _stop_subsystem_tasks(rt, name)
            if want:
                rt["tasks"][name] = _subsystem_tasks(home, profile, name)
            log.info(
                "profile %s: %s %s (hot reload)",
                profile, name,
                "restarted" if want and have
                else "started" if want else "stopped",
            )
        rt["fps"] = fps


def _profile_tasks(
    home: Path, profile: str, subsystems: dict[str, bool],
) -> dict[str, list[asyncio.Task]]:
    out: dict[str, list[asyncio.Task]] = {}
    for name, enabled in subsystems.items():
        if not enabled:
            continue
        tasks = _subsystem_tasks(home, profile, name)
        if tasks:
            out[name] = tasks
    return out


def _subsystem_tasks(home: Path, profile: str, name: str) -> list[asyncio.Task]:
    if name == "schedule":
        return [asyncio.create_task(
            _supervise(_run_scheduler, home, profile, "schedule"),
            name=f"{profile}/schedule",
        )]
    if name == "alp":
        return [asyncio.create_task(
            _supervise(_run_alp, home, profile, "alp"),
            name=f"{profile}/alp",
        )]
    # Host plane is default-only.
    if name == "host" and profile == "default":
        return [asyncio.create_task(
            _supervise(_run_host, home, profile, "host"),
            name=f"{profile}/host",
        )]
    if name == "workgroups":
        return [
            asyncio.create_task(
                _supervise(_run_workgroup_poller, home, profile, "workgroups"),
                name=f"{profile}/workgroups",
            ),
            asyncio.create_task(
                _supervise(_run_preempt_watcher, home, profile, "workgroup-preempt"),
                name=f"{profile}/workgroup-preempt",
            ),
        ]
    return []


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


async def _run_scheduler(home: Path) -> None:
    from alpi.scheduler.run import serve as sch_serve
    await sch_serve(home)


def _poller_start_offset(profile: str) -> float:
    # Stagger pollers so they don't all fire at once and saturate the host-shared loop.
    h = int.from_bytes(hashlib.sha1(profile.encode("utf-8")).digest()[:4], "big")
    return (h % (WORKGROUP_TICK_SECONDS * 1000)) / 1000.0


# Failed pulls back off to 15 min; successful empty pulls immediately reopen the held request.
_WG_POLL_STEADY_TICKS = 3
_WG_POLL_BACKOFF_MAX = 30
_WG_HOT_WINDOW_SECONDS = 120.0
_WG_HOT_TICK_SECONDS = 5.0
_WG_LONG_POLL_SECONDS = 25.0
_HOT_DISPATCH_COOLDOWN_SECONDS = 10


def _wg_backoff_mult(idle_ticks: int) -> int:
    if idle_ticks < _WG_POLL_STEADY_TICKS:
        return 1
    return min(_WG_POLL_BACKOFF_MAX, 1 << (idle_ticks - _WG_POLL_STEADY_TICKS + 1))


def _wg_is_hot(wid: str, hot_until: dict[str, float], now: float) -> bool:
    if now < hot_until.get(wid, 0.0):
        return True
    return any(key[0] == wid for key in _INFLIGHT)


def _sub_stays_hot(new_posts: list, sub) -> bool:
    # An open task (in-progress pipeline / awaited peer reply / un-handed-off #working) must keep base cadence — backing it off would delay the peer wakeup and the #working recovery watchdog.
    if new_posts:
        return True
    from alpi.alp import tasks as wg_tasks
    # hub_pubkey is required: without it a member's own #done text would falsely close the task and let it back off.
    return wg_tasks.active_task(
        getattr(sub, "recent_posts", None) or [],
        hub_pubkey=getattr(sub, "hub_pubkey", None),
    ) is not None


def _wg_is_pipeline(wg) -> bool:
    from alpi.alp import workgroup as wg_mod

    return wg_mod.is_pipeline_workgroup(wg.meta)


def _hub_phase_turn_budget(wg, recent: list) -> int:
    from alpi.alp import workgroup as wg_mod

    return _phase_turn_budget(
        wg_mod.safe_phase_map(wg.meta), recent, wg.meta.hub_pubkey,
    )


def _phase_turn_budget(phase_map: dict, posts: list, hub_pubkey: str) -> int:
    from alpi.alp import tasks as wg_tasks

    try:
        active = wg_tasks.active_task(posts or [], hub_pubkey=hub_pubkey or None)
    except Exception:  # noqa: BLE001
        return 0
    if active is None or not active.slug:
        return 0
    spec = (phase_map or {}).get(active.slug) or {}
    try:
        return int(spec.get("turn_budget_s") or 0)
    except (TypeError, ValueError):
        return 0


def _gate_opened_active_task(posts: list[dict], hub_pubkey: str) -> bool:
    from alpi.alp import tasks as wg_tasks

    active = wg_tasks.active_task(posts, hub_pubkey=hub_pubkey)
    if active is None:
        return False
    opener_index = next((
        i for i, post in enumerate(posts)
        if int(post.get("seq", 0)) == active.opened_seq
        and str(post.get("from") or "") == hub_pubkey
    ), -1)
    if opener_index <= 0:
        return False
    previous = next((
        post for post in reversed(posts[:opener_index])
        if str(post.get("from") or "") == hub_pubkey
    ), None)
    text = str((previous or {}).get("text") or "")
    return wg_tasks.is_done(text) and "· gate:" in text


def _hub_stays_hot(fresh: bool, wg, recent: list[dict]) -> bool:
    if fresh:
        return True
    from alpi.alp import tasks as wg_tasks

    active = wg_tasks.active_task(recent, hub_pubkey=wg.meta.hub_pubkey)
    if active is not None:
        return True
    if not _pipeline_continuation_due(wg, recent, active):
        return False
    next_phase, _latest, known = _next_pipeline_phase(wg, recent)
    return known and next_phase is not None


async def _run_subscription_poller(home: Path, profile: str, wg_id: str) -> None:
    """Keep one held pull open for a subscription; only transport failures back off."""
    from alpi.alp import subscription as sub_mod
    from alpi.alp import workgroup_client as wc

    failures = 0
    hot_until = 0.0
    while True:
        if sub_mod.get(home, wg_id) is None:
            return
        started = time.monotonic()
        try:
            new_posts, _head = await wc.pull(
                home, wg_id, wait_s=_WG_LONG_POLL_SECONDS,
            )
            refreshed = sub_mod.get(home, wg_id)
            if refreshed is None:
                return
            now = time.monotonic()
            if new_posts:
                hot_until = now + _WG_HOT_WINDOW_SECONDS
            hot = (
                now < hot_until
                or _sub_stays_hot(new_posts, refreshed)
                or _wg_is_hot(wg_id, {}, now)
            )
            await _maybe_dispatch_for_sub(home, profile, refreshed, hot=hot)
            failures = 0
            # A pre-long-poll hub ignores wait_s and answers empty immediately.
            if not new_posts and time.monotonic() - started < 1.0:
                await asyncio.sleep(_WG_HOT_TICK_SECONDS)
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001
            failures += 1
            delay = WORKGROUP_TICK_SECONDS * _wg_backoff_mult(failures)
            log.debug("wg poller pull(%s) failed; retry in %.0fs: %s", wg_id, delay, e)
            await asyncio.sleep(delay)


async def _run_workgroup_poller(home: Path, profile: str) -> None:
    """Watch workgroups for new triggers and dispatch turns."""
    from alpi.alp import subscription as sub_mod
    from alpi.alp import workgroup as wg_mod

    log.info("workgroup poller running (tick=%ss)", WORKGROUP_TICK_SECONDS)
    await asyncio.sleep(_poller_start_offset(profile))
    sub_workers: dict[str, asyncio.Task] = {}
    hot_until: dict[str, float] = {}
    hub_seen: dict[str, int] = {}

    from alpi.alp import wakes
    wake = asyncio.Event()

    def _on_post(wid: str) -> None:
        hot_until[wid] = time.monotonic() + _WG_HOT_WINDOW_SECONDS
        wake.set()

    wakes.register(home, _on_post)
    try:
        while True:
            try:
                subscriptions = {sub.wg_id for sub in sub_mod.load(home)}
                removed = [wid for wid in sub_workers if wid not in subscriptions]
                for wid in removed:
                    sub_workers[wid].cancel()
                if removed:
                    await asyncio.gather(
                        *(sub_workers.pop(wid) for wid in removed),
                        return_exceptions=True,
                    )
                for wid in subscriptions:
                    worker = sub_workers.get(wid)
                    if worker is None or worker.done():
                        if worker is not None:
                            try:
                                worker.result()
                            except asyncio.CancelledError:
                                pass
                            except Exception as e:  # noqa: BLE001
                                log.error("wg pull worker %s exited: %s", wid, e)
                        sub_workers[wid] = asyncio.create_task(
                            _run_subscription_poller(home, profile, wid),
                            name=f"wg-pull-{profile}-{wid}",
                        )

                workgroups = wg_mod.list_workgroups(home)
                active_hubs = {wg.meta.id for wg in workgroups}
                for state in (hot_until, hub_seen):
                    for wid in list(state):
                        if wid not in active_hubs:
                            state.pop(wid, None)

                now = time.monotonic()
                for wg in workgroups:
                    await asyncio.sleep(0)
                    wid = wg.meta.id
                    try:
                        recent = _all_hub_posts_decrypted(home, wg)
                    except Exception as e:  # noqa: BLE001
                        log.debug("wg poller hub scan(%s) failed: %s", wid, e)
                        continue
                    if not recent:
                        continue
                    head = int(recent[-1].get("seq", 0))
                    fresh = head > hub_seen.get(wid, 0)
                    hub_seen[wid] = head
                    if fresh:
                        hot_until[wid] = now + _WG_HOT_WINDOW_SECONDS
                    hot = (
                        _wg_is_hot(wid, hot_until, now)
                        or _hub_stays_hot(fresh, wg, recent)
                    )
                    await _maybe_dispatch_for_hub(home, profile, wg, recent, hot=hot)
            except Exception:  # noqa: BLE001
                log.exception("workgroup poller tick crashed")
            try:
                await asyncio.wait_for(wake.wait(), timeout=_WG_HOT_TICK_SECONDS)
            except asyncio.TimeoutError:
                pass
            wake.clear()
    finally:
        wakes.unregister(home)
        for worker in sub_workers.values():
            worker.cancel()
        if sub_workers:
            await asyncio.gather(*sub_workers.values(), return_exceptions=True)


async def _maybe_dispatch_for_sub(
    home: Path, profile: str, sub, hot: bool = False,
) -> None:
    """Decide whether a member-side workgroup should dispatch."""
    from alpi.alp import keys as _keys
    from alpi.alp import subscription as sub_mod

    if getattr(sub, "paused", False):  # paused hub → no automatic member turns
        return
    own_pubkey = _keys.load_or_generate(home).pubkey_b64()
    trigger, new_responded = _should_dispatch(
        profile, own_pubkey, sub.recent_posts or [], sub.last_responded_seq,
        hub_pubkey=str(getattr(sub, "hub_pubkey", "") or ""),
        pipeline=bool(getattr(sub, "pipeline_mode", False)),
    )
    if not trigger:
        trigger = _working_redispatch_reason(
            profile, own_pubkey, sub.recent_posts or [], sub.last_dispatch_at,
            sub.hub_pubkey,
        )
        if trigger:
            new_responded = sub.last_responded_seq
    # Advance the pointer when the latest post is ours.
    if not trigger:
        if new_responded > sub.last_responded_seq:
            sub.last_responded_seq = new_responded
            sub_mod.upsert(home, sub)
        return
    gate_opened = _gate_opened_active_task(
        sub.recent_posts or [], sub.hub_pubkey,
    )
    if (
        not gate_opened
        and _in_cooldown_str(
            sub.last_dispatch_at,
            _HOT_DISPATCH_COOLDOWN_SECONDS if hot else None,
        )
    ):
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
    if _budget_blocks_dispatch(home, profile, sub.wg_id, sub.name):
        return
    started_against = _latest_hub_task_seq_for(home, sub.wg_id, sub.hub_pubkey)
    # Cooldown stamp only; last_responded_seq advances on completion so a crash re-dispatches.
    sub.last_dispatch_at = _utcnow_iso()
    sub_mod.upsert(home, sub)
    # Spawn dispatch in the background so polling and preemption keep moving.
    _spawn_dispatch(
        sub.wg_id,
        _dispatch_workgroup_turn(
            home, profile, sub.wg_id, sub.name, trigger,
            pipeline=bool(getattr(sub, "pipeline_mode", False)),
            round_hub_seq=round_seq,
            hub_pubkey=sub.hub_pubkey,
            started_against_task_seq=started_against,
            turn_budget_s=_phase_turn_budget(
                getattr(sub, "phase_map", None) or {},
                sub.recent_posts or [], sub.hub_pubkey,
            ),
            member_responded_seq=new_responded,
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


# (wg_id, owner_post_seq) pairs whose gate already ran — reruns wait for a NEWER owner post, so a failing gate can't spin on every 5s scan.
_GATE_ATTEMPTED: dict[tuple[str, str, int], bool] = {}
_GATE_ATTEMPTED_CAP = 512
# Daemon-authored repair rounds per (home, wg, phase, opener seq); past the cap the hub is woken for judgment.
_GATE_REPAIR_ROUNDS = 3
_GATE_REPAIRS: dict[tuple[str, str, str, int], int] = {}
_GATE_REPAIRS_CAP = 512


async def _maybe_gate_advance(
    home: Path, wg, recent: list[dict], own_pubkey: str,
) -> bool | str | None:
    """True = phase advanced mechanically; str = gate failed (reason for the LLM wake); None = no gate applies."""
    from alpi import config as cfg_mod
    from alpi.alp import peers as peers_mod
    from alpi.alp import pipeline_gates as gates
    from alpi.alp import tasks as wg_tasks
    from alpi.alp import workgroup_client as wc

    if not getattr(wg.meta, "pipeline_steps", None) or not recent:
        return None
    active = wg_tasks.active_task(recent, hub_pubkey=wg.meta.hub_pubkey)
    if active is None:
        return None
    step = gates.step_for(wg.meta, active.slug)
    if step is None:
        return None
    owner_peer = next(
        (p for p in peers_mod.load(home) if p.id.lower() == step.owner.lower()),
        None,
    )
    if owner_peer is None:
        return None
    # Only the opener bounds the round: a later hub note must not hide the delivery.
    latest_seq = gates.owner_post_under_gate(
        recent, {owner_peer.pubkey}, own_pubkey, int(active.opened_seq),
    )
    if latest_seq is None:
        return None
    key = (str(home), wg.meta.id, latest_seq)
    if key in _GATE_ATTEMPTED:
        return None
    workspace = cfg_mod.load(home).workspace_path or home
    # Marked here, not earlier: anything that fails before the run must stay retryable.
    if len(_GATE_ATTEMPTED) >= _GATE_ATTEMPTED_CAP:
        _GATE_ATTEMPTED.pop(next(iter(_GATE_ATTEMPTED)))
    _GATE_ATTEMPTED[key] = True
    passed, output = await asyncio.to_thread(gates.run_gate, step, workspace)
    try:
        gates.write_gate_log(
            home / "alp" / "workgroups" / wg.meta.id,
            step, latest_seq, passed, output,
        )
    except OSError as e:
        return f"GATE {step.phase} audit FAILED: {e}"
    if not passed:
        log.info("wg gate %s/%s FAILED (seq %s)", wg.meta.id, step.phase, latest_seq)
        rkey = (str(home), wg.meta.id, step.phase, int(active.opened_seq))
        rounds = _GATE_REPAIRS.get(rkey, 0) + 1
        if len(_GATE_REPAIRS) >= _GATE_REPAIRS_CAP:
            _GATE_REPAIRS.pop(next(iter(_GATE_REPAIRS)))
        _GATE_REPAIRS[rkey] = rounds
        if rounds <= _GATE_REPAIR_ROUNDS:
            note = (
                f"@{step.owner} gate red on #{step.phase} "
                f"(repair round {rounds}/{_GATE_REPAIR_ROUNDS}) — fix these and "
                f"re-deliver on this same task:\n{output[-900:]}"
            )
            try:
                res = await wc.post(home, wg.meta.id, note.encode())
                if isinstance(res, dict):
                    _set_hub_responded_seq(home, wg.meta.id, int(res.get("seq", latest_seq)))
                log.info(
                    "wg gate %s/%s repair note posted (round %d)",
                    wg.meta.id, step.phase, rounds,
                )
                return True
            except Exception as e:  # noqa: BLE001
                log.error("wg gate %s/%s repair note failed: %s", wg.meta.id, step.phase, e)
        return (
            f"GATE {step.phase} FAILED after {rounds} repair rounds: {output[-300:]} — "
            f"RE-TASK @{step.owner} with #{step.phase} so the check re-runs on their "
            f"next post, close `#done skipped · <reason>` if the phase is judged "
            f"complete without it, or halt with `#done BLOCKED · <reason>`."
        )
    last_posted = latest_seq
    try:
        res = await wc.post(home, wg.meta.id, gates.done_text(step, output).encode())
        if isinstance(res, dict):
            last_posted = int(res.get("seq", last_posted))
        nxt = gates.next_task_text(step)
        if nxt:
            res = await wc.post(home, wg.meta.id, nxt.encode())
            if isinstance(res, dict):
                last_posted = int(res.get("seq", last_posted))
    except Exception as e:  # noqa: BLE001
        log.error("wg gate %s/%s advance post failed: %s", wg.meta.id, step.phase, e)
        return f"GATE {step.phase} passed but the advance post failed: {e}"
    # Cursor past our own advance posts, or the poller wakes the hub over them and it may duplicate the opener.
    _set_hub_responded_seq(home, wg.meta.id, last_posted)
    log.info("wg gate %s/%s PASSED → %s (seq %s)", wg.meta.id, step.phase, step.next_phase or "end", latest_seq)
    return True


async def _maybe_dispatch_for_hub(
    home: Path, profile: str, wg, recent: list[dict], hot: bool = False,
) -> None:
    """Decide whether a hub-side workgroup should dispatch."""
    from alpi.alp import keys as _keys

    if getattr(wg.meta, "paused", False):  # paused → no activity dispatch, no watchdog, no burn
        return
    own_pubkey = _keys.load_or_generate(home).pubkey_b64()
    gate_fail = await _maybe_gate_advance(home, wg, recent, own_pubkey)
    if gate_fail is True:
        return
    if gate_fail is None:
        _warn_gate_overdue(home, wg, recent, own_pubkey)
    last_responded = _get_hub_responded_seq(home, wg.meta.id)
    trigger, new_responded = _should_dispatch(
        profile, own_pubkey, recent, last_responded,
        hub_pubkey=wg.meta.hub_pubkey,
        pipeline=_wg_is_pipeline(wg),
    )
    if trigger and isinstance(gate_fail, str):
        trigger = f"{trigger} · {gate_fail}"
    if not trigger:
        if new_responded > last_responded:
            _set_hub_responded_seq(home, wg.meta.id, new_responded)
        await _maybe_watchdog_close(home, profile, wg, recent)
        return
    state = _load_poller_state(home)
    last = state.get("hub_last_dispatch_at", {}).get(wg.meta.id, "")
    if _in_cooldown_str(last, _HOT_DISPATCH_COOLDOWN_SECONDS if hot else None):
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
    if _budget_blocks_dispatch(home, profile, wg.meta.id, wg.meta.name):
        return
    _set_hub_responded_seq(home, wg.meta.id, new_responded)
    _mark_hub_dispatched(home, wg.meta.id)
    _spawn_dispatch(
        wg.meta.id,
        _dispatch_workgroup_turn(
            home, profile, wg.meta.id, wg.meta.name, trigger,
            pipeline=_wg_is_pipeline(wg),
            hub_pubkey=wg.meta.hub_pubkey,
            started_against_task_seq=started_against,
            turn_budget_s=_hub_phase_turn_budget(wg, recent),
        ),
    )


_HUB_WATCHDOG_REFIRE_SECONDS = 5 * 60  # 5 min between re-fires


def _pipeline_continuation_due(wg, recent: list[dict], active) -> bool:
    """True when a `pipeline` workgroup just closed a phase — the hub's
    own `#done` is the last post and no successor task is open — so the
    hub should get one continuation wake to open the next phase. False
    for non-pipeline workgroups (a `#done` there is terminal), or when a
    member spoke last, or when the last post wasn't a `#done`."""
    from alpi.alp import tasks as wg_tasks
    from alpi.alp import workgroup as wg_mod

    if active is not None or not recent:
        return False
    if not wg_mod.is_pipeline_workgroup(wg.meta):
        return False
    last_post = recent[-1]
    if str(last_post.get("from") or "") != wg.meta.hub_pubkey:
        return False
    return wg_tasks.is_done(str(last_post.get("text") or ""))


def _canonical_pipeline_slug(slug: str, pipeline: list[str]) -> str | None:
    """Closed recovery mapping inside ONE chain: exact phase, else exactly one `-fix`/`-recheck` suffix."""
    from alpi.alp import workgroup as wg_mod

    if slug in pipeline:
        return slug
    for suffix in wg_mod._RECOVERY_SUFFIXES:
        if slug.endswith(suffix):
            base = slug[: -len(suffix)]
            if base in pipeline:
                return base
    return None


def _is_success_result(result: str) -> bool:
    # Conservative pass-detector for a terminal-phase close; negatives win so "did
    # not pass" / "FAIL: pass criteria not met" never read as success.
    text = (result or "").strip().lower()
    if any(w in text for w in ("fail", "blocked", "error", "not pass")):
        return False
    return (
        "pass" in text
        or "green" in text
        or "verde" in text
        or text.startswith("ok")
        or text.startswith("verified")
        or text.startswith("verificado")
    )


def _next_pipeline_phase(wg, recent: list[dict]) -> tuple[str | None, str, bool]:
    """Given a pipeline workgroup's ordered phase list and the transcript,
    return ``(next_slug, latest_closed_slug, known)``:

    - ``("<slug>", latest, True)`` — the phase after the most recently
      closed one; the hub should open `#task #<slug>`.
    - ``(None, latest, True)`` — the last phase just closed; pipeline
      complete, nothing to open.
    - ``(None, latest, False)`` — the closed slug isn't in the pipeline
      (misconfigured); the core must NOT guess a next phase.
    """
    from alpi.alp import tasks as wg_tasks
    from alpi.alp import workgroup as wg_mod

    if not wg_mod.is_pipeline_workgroup(wg.meta):
        return None, "", True
    events: list = []
    for p in recent:
        events += wg_tasks.parse_post(
            str(p.get("text") or ""), int(p.get("seq", 0)),
            str(p.get("from") or ""), hub_pubkey=wg.meta.hub_pubkey,
        )
    closed = [t for t in wg_tasks.fold_tasks(events) if not t.is_open]
    if not closed:
        return None, "", True
    # The LATEST close alone picks the chain, or an ad-hoc `#done` resurrects finished work.
    latest_overall = max(closed, key=lambda t: t.closed_seq or 0)
    canonical = wg_mod.canonical_pipeline_phase(wg.meta, latest_overall.slug)
    if canonical is None:
        return None, latest_overall.slug, False
    pipeline = list(wg.meta.pipelines[canonical[0]])
    # BLOCKED halts a DECLARED chain; an unknown slug stays unknown (checked above).
    if (latest_overall.result or "").strip().upper().startswith("BLOCKED"):
        return None, latest_overall.slug, True
    in_pipeline = [t for t in closed if t.slug in pipeline]
    if not in_pipeline:
        return None, latest_overall.slug, False
    term = max(in_pipeline, key=lambda t: t.closed_seq or 0)
    latest = term.slug
    idx = pipeline.index(latest)
    if idx + 1 < len(pipeline):
        return wg_mod.pipeline_successor(wg.meta, latest), latest, True
    # Terminal phase closed. The latest close mapping to it — canonical OR a
    # `<phase>-*` fix/recheck variant — decides: a green recheck COMPLETES the
    # pipeline (don't reopen build→qa after a passed qa-recheck). Only when the
    # terminal's latest close still isn't a success AND a fix is in flight do we
    # rebuild (re-run the phase before the terminal so it re-audits a fresh
    # artifact); the continuation cap bounds the loop.
    terminal_closes = [
        t for t in closed if _canonical_pipeline_slug(t.slug, pipeline) == latest
    ]
    latest_terminal = max(terminal_closes, key=lambda t: t.closed_seq or 0)
    if _is_success_result(latest_terminal.result or ""):
        return None, latest, True
    # A repair of THIS chain or an ad-hoc slug is a fix in flight; a dormant chain's own phase is not.
    def _is_fix(slug: str) -> bool:
        if slug in pipeline:
            return False
        canon = wg_mod.canonical_pipeline_phase(wg.meta, slug)
        return canon is None or canon[0] == canonical[0]

    fix_after = any(
        _is_fix(t.slug) and (t.opened_seq or 0) > (term.opened_seq or 0)
        for t in closed
    )
    if fix_after:
        return (pipeline[idx - 1] if idx >= 1 else latest), latest, True
    return None, latest, True


_GATE_OVERDUE_WARNED: set[tuple[str, str, int]] = set()


def _warn_gate_overdue(home: Path, wg, recent: list[dict], own_pubkey: str) -> None:
    from alpi.alp import peers as peers_mod
    from alpi.alp import pipeline_gates as gates
    from alpi.alp import tasks as wg_tasks
    from alpi.alp import workgroup as wg_mod

    active = wg_tasks.active_task(recent, hub_pubkey=wg.meta.hub_pubkey)
    if active is None or not active.slug:
        return
    step = gates.step_for(wg.meta, active.slug)
    if step is None:
        return
    owner = next(
        (p for p in peers_mod.load(home) if p.id.lower() == step.owner.lower()), None,
    )
    if owner is None:
        key = (wg.meta.id, active.slug, 0)
        if key in _GATE_OVERDUE_WARNED:
            return
        _GATE_OVERDUE_WARNED.add(key)
        log.warning(
            "wg poller: %s gate cannot start — `#%s` declares `%s` but its owner "
            "@%s is not pinned as a peer, so no post can be attributed to it",
            wg.meta.id, active.slug, " ".join(step.argv), step.owner,
        )
        return
    seq = gates.owner_post_under_gate(
        recent, {owner.pubkey}, own_pubkey, int(active.opened_seq),
    )
    if seq is None:
        return
    wg_dir = wg_mod._wg_dir(home, wg.meta.id)
    # A verdict either way means the gate ran; only a missing log is the anomaly.
    if gates.gate_log_verdict(wg_dir, active.slug, seq) is not None:
        return
    key = (wg.meta.id, active.slug, seq)
    if key in _GATE_OVERDUE_WARNED:
        return
    _GATE_OVERDUE_WARNED.add(key)
    attempted = (str(home), wg.meta.id, seq) in _GATE_ATTEMPTED
    log.warning(
        "wg poller: %s gate overdue — `#%s` declares `%s` but it never ran on "
        "@%s's post (seq #%d); %s. The phase cannot close until it does.",
        wg.meta.id, active.slug, " ".join(step.argv), step.owner, seq,
        "the run was started and left no log, so it died mid-flight"
        if attempted else
        "it was never started, so a precondition declined it",
    )


# Per-(wg, slug) dedup so a misconfigured pipeline emits `wg.blocked` once,
# not every poll. Daemon-lifetime only — fine for an operator alert.
_BLOCKED_EMITTED: set[tuple[str, str]] = set()


def _emit_wg_blocked_once(home: Path, wg_id: str, slug: str, nudges: int) -> None:
    key = (wg_id, slug)
    if key in _BLOCKED_EMITTED:
        return
    _BLOCKED_EMITTED.add(key)
    _emit_wg_blocked(home, wg_id, 0, nudges)


async def _maybe_watchdog_close(
    home: Path, profile: str, wg, recent: list[dict],
) -> None:
    """Re-poke stalled hub workgroups.

    Two modes:
    - **closure** (a task is open): nudge the hub to `#done` or stay
      silent — never re-task. The deliberation default.
    - **continuation** (no open task, at least one declared chain):
      after a `#done` with no successor, give the hub a bounded number of
      normal wakes to open the next phase's `#task` — the next slug is
      computed from the ordered list. Off for non-pipeline workgroups
      (empty `pipeline`), where a `#done` is terminal.
    """
    from alpi.alp import tasks as wg_tasks

    if getattr(wg.meta, "paused", False):  # paused workgroups run no watchdog/repair/continuation
        return
    if not recent:
        return
    active = wg_tasks.active_task(recent, hub_pubkey=wg.meta.hub_pubkey)
    continuation = active is None
    next_phase = ""
    if continuation:
        if not _pipeline_continuation_due(wg, recent, active):
            return
        nxt, latest_slug, known = _next_pipeline_phase(wg, recent)
        if not known:
            # Alert only when a launch chain was driving; an idle workgroup does ad-hoc work by design.
            if getattr(wg.meta, "launch_pipeline", None):
                _emit_wg_blocked_once(home, wg.meta.id, latest_slug, 0)
            return
        if nxt is None:
            return  # last phase done — pipeline complete, nothing to open
        next_phase = nxt
        last_post = recent[-1]
    else:
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
    # A member `#working` is a sign-of-life: it earns the full turn-timeout of
    # grace before the hub treats silence as a stall (a long local write posts
    # nothing while it runs). Any other last post uses the short threshold.
    last_is_member_working = (
        str(last_post.get("from") or "") != wg.meta.hub_pubkey
        and "#working" in str(last_post.get("text") or "")
    )
    stale_threshold = (
        _turn_timeout_for(_wg_is_pipeline(wg))
        if last_is_member_working
        else _HUB_FOLLOWUP_STALE_SECONDS
    )
    if age < stale_threshold:
        return

    if continuation:
        cont_seq, cont_count = _continuation_state(home, wg.meta.id)
        fired_seq = cont_seq if cont_count >= 1 else 0
    else:
        cont_seq = cont_count = 0
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
    if _budget_blocks_dispatch(home, profile, wg.meta.id, wg.meta.name):
        return

    started_against = _latest_hub_task_seq_for(
        home, wg.meta.id, wg.meta.hub_pubkey,
    )

    if continuation:
        # Bounded retry per `#done` seq: the hub gets a few continuation
        # wakes (refire-interval apart) to open the next phase, recovering
        # from a wake that whiffed (searched but didn't post). Read the
        # count FIRST — once at the cap, return without writing (no
        # per-tick `poller_state.json` churn) until the transcript moves.
        cur = cont_count if cont_seq == last_seq else 0
        if cur >= _CONTINUATION_MAX_FIRES:
            # All attempts spent on this `#done` seq and the transcript
            # never moved (a new post would reset the seq). NOW we know it's
            # stuck — surface `wg.blocked` once, then return without writing.
            _emit_wg_blocked_once(home, wg.meta.id, f"seq{last_seq}", cur)
            return
        cnt = _bump_hub_continuation_count(home, wg.meta.id, last_seq)
        reason = (
            f"watchdog: task closed (seq #{last_seq}), open next phase "
            f"`#{next_phase}` — pipeline continuation (attempt {cnt})"
        )
        log.info(
            "wg poller: %s dispatching continuation (reason=%s)",
            wg.meta.id, reason,
        )
        _mark_hub_dispatched(home, wg.meta.id)
        _spawn_dispatch(
            wg.meta.id,
            _dispatch_workgroup_turn(
                home, profile, wg.meta.id, wg.meta.name, reason,
                continuation=True, next_phase=next_phase,
                pipeline=_wg_is_pipeline(wg),
                hub_pubkey=wg.meta.hub_pubkey,
                started_against_task_seq=started_against,
            ),
        )
        return

    # An in-flight turn is progress the transcript cannot show yet; a nudge here re-tasks over live work and the preempt watcher kills it.
    if any(key[0] == wg.meta.id for key in _INFLIGHT):
        return
    last_author_is_hub = str(
        last_post.get("from") or ""
    ) == wg.meta.hub_pubkey
    count = _bump_hub_watchdog_count(home, wg.meta.id, last_seq)
    is_pipeline = _wg_is_pipeline(wg)
    repair = is_pipeline and count == 2
    final_repair = is_pipeline and count == 3
    if count == 2:
        _emit_wg_blocked(home, wg.meta.id, last_seq, count)
    if count >= 2:
        log.warning(
            "wg poller: %s task stalled — %d closure nudges on seq #%d, "
            "no progress%s", wg.meta.id, count, last_seq,
            " → final repair" if final_repair
            else (" → repair mode" if repair else " → blocked alert"),
        )
    # Pipeline hub gets TWO recovery wakes — REPAIR then a close-or-BLOCK FINAL
    # REPAIR — before abandon (the final one recovers a lost-handoff: green
    # artifact on disk, member's handoff missing). Non-pipeline stops after one.
    if (is_pipeline and count >= 4) or (not is_pipeline and count >= 3):
        # All recovery attempts spent and the transcript never moved.
        # `wg.blocked` stays the visible state until a new post resets the
        # seq. Stop waking the hub — repeating burns turns for nothing.
        return
    if final_repair:
        # Last automatic wake on this seq. Force a deterministic resolution
        # rather than another soft nudge: verify disk, close if the
        # deliverable is there (handoff or not), else post BLOCKED.
        reason = (
            f"watchdog: task open (seq #{last_seq}), {count} nudges no "
            f"progress for {int(age)}s — FINAL REPAIR (last automatic wake "
            "on this task): verify the on-disk artifact YOURSELF. If the "
            "phase deliverable exists (e.g. a green `dist/` with every "
            "declared locale), CLOSE it now with `#done`. If it genuinely "
            "cannot pass without human/factory help, CLOSE it with "
            "`#done BLOCKED · <phase> · <reason>` — a `#done` whose result "
            "starts with BLOCKED closes the task and halts the pipeline "
            "cleanly (plain `BLOCKED` text leaves the task open and hung). "
            "Either way, do not end the turn silent — this task will not be "
            "woken again."
        )
    elif repair:
        # A pipeline hub that nudged twice with no progress is likely
        # stuck on its own bad task (wrong path/spec/order). Wake it in
        # NORMAL mode so it can re-verify on-disk state and re-task or
        # preempt — not just `#done`-or-silence.
        reason = (
            f"watchdog: task open (seq #{last_seq}), {count} nudges no "
            f"progress for {int(age)}s — REPAIR: re-verify the on-disk "
            "state, then RE-TASK the owner: post a NEW "
            "`@<owner> #task #<same-phase> <correct path/spec>` — opening "
            "a `#task` is always allowed even though you (hub) spoke "
            "last, so never fall back to a plain reply. Close with "
            "`#done` ONLY if the deliverable is actually done; a `#done` "
            "on a phase whose owner never delivered is forbidden"
        )
    else:
        stall_kind = (
            "hub talked last" if last_author_is_hub else "member talked last"
        )
        reason = (
            f"watchdog: {stall_kind} (seq #{last_seq}), nothing new for "
            f"{int(age)}s — closure-or-silence only"
        )
    log.info(
        "wg poller: %s dispatching %s (reason=%s)",
        wg.meta.id,
        "final-repair" if final_repair else ("repair" if repair else "watchdog"),
        reason,
    )
    _set_hub_watchdog_seq(home, wg.meta.id, last_seq)
    _mark_hub_dispatched(home, wg.meta.id)
    _spawn_dispatch(
        wg.meta.id,
        _dispatch_workgroup_turn(
            home, profile, wg.meta.id, wg.meta.name, reason,
            closure_only=not (repair or final_repair),
            pipeline=_wg_is_pipeline(wg),
            hub_pubkey=wg.meta.hub_pubkey,
            started_against_task_seq=started_against,
        ),
    )


_HUB_DECRYPT_CACHE: dict[str, tuple[tuple[int, int, int], list[dict]]] = {}


def _all_hub_posts_decrypted(home: Path, wg) -> list[dict]:
    """Return the decrypted hub transcript."""
    import json
    from alpi.alp import workgroup as wg_mod
    from alpi.alp.keys import load_or_generate

    kp = load_or_generate(home)
    own = wg.member(kp.pubkey_b64())
    if own is None:
        return []
    # All versions the hub can open (current + rekey history) so a task opened
    # before a leave/kick rotation isn't blanked out of the fold.
    keys = wg_mod.hub_group_keys(home, wg, kp)
    if not keys:
        return []
    transcript_path = home / "alp" / "workgroups" / wg.meta.id / "transcript.jsonl"
    if not transcript_path.exists():
        return []
    try:
        st = transcript_path.stat()
        sig = (st.st_mtime_ns, st.st_size, len(keys))
    except OSError:
        sig = None
    cache_key = str(transcript_path)
    if sig is not None:
        cached = _HUB_DECRYPT_CACHE.get(cache_key)
        # Unchanged transcript decrypts to the same posts — skip the per-tick full re-decrypt that dominated idle-hub CPU.
        if cached is not None and cached[0] == sig:
            return cached[1]
    out: list[dict] = []
    for line in transcript_path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        group_key = keys.get(int(entry.get("key_version", 1)))
        if group_key is None:
            continue
        try:
            text = wg_mod.decrypt_post(
                group_key, entry["nonce"], entry["ciphertext"],
            ).decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            continue
        out.append({**entry, "text": text})
    if sig is not None:
        _HUB_DECRYPT_CACHE[cache_key] = (sig, out)
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


def _budget_blocks_dispatch(
    home: Path, profile: str, wg_id: str, wg_name: str,
) -> bool:
    from alpi import config as cfg_mod
    from alpi import ledger as ledger_mod

    try:
        ledger_mod.check(home, cfg_mod.load(home).budget)
        return False
    except ledger_mod.BudgetExceeded as exc:
        used, cap = exc.used, exc.cap
    except Exception:  # noqa: BLE001
        return False

    state = _load_poller_state(home)
    seen = state.setdefault("budget_blocked", {})
    today = _utcnow_iso()[:10]
    if seen.get(wg_id) != today:
        seen[wg_id] = today
        _save_poller_state(home, state)
        log.warning(
            "wg poller: %s blocked — profile '%s' is over its daily budget "
            "($%.2f / $%.2f); turns resume at UTC midnight or when the cap is raised",
            wg_id, profile, used, cap,
        )
        _append_turn_event(home, {
            "ts": _utcnow_iso(), "event": "budget-exhausted",
            "profile": profile, "wg_id": wg_id, "wg_name": wg_name,
            "used": round(used, 4), "cap": cap,
        })
    return True


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


# wg_id-keyed poller guards that mean "already handled this seq" — cleared on
# resume so a paused-then-resumed workgroup is re-evaluated from scratch next
# tick. NOT hub_cursors (the read cursor; clearing it would re-process the
# whole transcript).
_RESUMABLE_POLLER_TABLES = (
    "hub_last_responded_seq", "hub_watchdog_fired_seq", "hub_watchdog_fire_count",
    "hub_continuation_fire_count", "hub_last_dispatch_at",
)


def reset_workgroup_poller_state(home: Path, wg_id: str) -> None:
    """Drop the per-wg poller guards for ``wg_id`` so resume re-opens normal
    dispatch/watchdog evaluation. No auto-post — the next tick decides."""
    state = _load_poller_state(home)
    changed = False
    for table in _RESUMABLE_POLLER_TABLES:
        t = state.get(table)
        if isinstance(t, dict) and wg_id in t:
            del t[wg_id]
            changed = True
    if changed:
        _save_poller_state(home, state)


# Continuation gets a few bounded retries per `#done` seq — enough to
# recover from a wake that whiffed (read/searched but didn't open the next
# task), never the unbounded every-5-min re-fire of the original bug.
_CONTINUATION_MAX_FIRES = 3


def _continuation_state(home: Path, wg_id: str) -> tuple[int, int]:
    """``(seq, count)`` of continuation wakes already fired for the most
    recent `#done` close, or ``(0, 0)``. Single source of truth for
    continuation: ``seq`` doubles as the 'already fired' marker for the
    refire guard; ``count`` enforces the bounded-retry cap. Read-only."""
    state = _load_poller_state(home)
    entry = state.get("hub_continuation_fire_count", {}).get(wg_id)
    if not entry:
        return 0, 0
    return int(entry[0]), int(entry[1])


def _bump_hub_continuation_count(home: Path, wg_id: str, seq: int) -> int:
    """Increment and persist the continuation fire count for `seq` (resets
    to 1 when the closed seq changes). Call ONLY when under the cap — the
    capped path must not write `poller_state.json` on every poll tick."""
    state = _load_poller_state(home)
    table = state.setdefault("hub_continuation_fire_count", {})
    entry = table.get(wg_id)
    if not entry or int(entry[0]) != int(seq):
        table[wg_id] = [int(seq), 1]
    else:
        table[wg_id] = [int(seq), int(entry[1]) + 1]
    _save_poller_state(home, state)
    return int(table[wg_id][1])


def _bump_hub_watchdog_count(home: Path, wg_id: str, seq: int) -> int:
    """Increment and return how many times the closure watchdog has fired
    on this stalled `seq`. Resets to 1 when the stalled seq changes."""
    state = _load_poller_state(home)
    table = state.setdefault("hub_watchdog_fire_count", {})
    entry = table.get(wg_id)
    if not entry or int(entry[0]) != int(seq):
        table[wg_id] = [int(seq), 1]
    else:
        table[wg_id] = [int(seq), int(entry[1]) + 1]
    _save_poller_state(home, state)
    return int(table[wg_id][1])


def _emit_wg_blocked(home: Path, wg_id: str, seq: int, nudges: int) -> None:
    """Emit ``wg.blocked`` for a stuck task (repeated closure nudges, no
    progress). Same host-event family as ``wg.post``/``wg.done``: appended
    to the durable event history AND pushed to live subscribers, so a
    client/operator can surface or replay it. Desktop/mobile card
    rendering for it is follow-up — the persisted event is the contract."""
    try:
        from alpi.home import profile_name
        from alpi.host import events as host_events
        host_events.emit("wg.blocked", {
            "profile": profile_name(home), "wg_id": wg_id,
            "seq": seq, "nudges": nudges,
        })
    except Exception:  # noqa: BLE001
        pass


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


def _in_cooldown_str(stamp: str, window: float | None = None) -> bool:
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
    return elapsed < (window if window is not None else DISPATCH_COOLDOWN_SECONDS)


def _should_dispatch(
    profile: str, own_pubkey: str,
    recent_posts: list[dict],
    last_responded_seq: int,
    hub_pubkey: str = "",
    pipeline: bool = False,
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
            # Pipeline: a non-hub post's mentions wake only the hub — routing goes up, never sideways.
            author = str(post.get("from") or "")
            if pipeline and hub_pubkey and author != hub_pubkey and own_pubkey != hub_pubkey:
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
            # Targeted task (opener named participants) wakes only those
            # peers; a collective task (no participants) wakes everyone.
            if not active.participants or profile in active.participants:
                return (
                    f"new content in active task (seq #{seq})",
                    high_seq,
                )

    return None, high_seq


def _working_redispatch_reason(
    profile: str, own_pubkey: str, recent_posts: list[dict],
    last_dispatch_at: str, hub_pubkey: str = "",
) -> str | None:
    # #working is a heartbeat, not a handoff: the member's seq is consumed at first
    # dispatch, so a child that exits after only #working never wakes again (recovery
    # left to the hub watchdog). Re-dispatch it once per #working posted after last dispatch.
    from alpi.alp import tasks as wg_tasks

    # hub_pubkey so non-hub markers in the member transcript aren't folded as task events.
    active = wg_tasks.active_task(recent_posts, hub_pubkey=hub_pubkey or None)
    if active is None:
        return None
    if active.opened_by == own_pubkey:
        return None
    if active.participants and profile not in active.participants:
        return None

    own_posts = [
        p for p in recent_posts
        if int(p.get("seq", 0)) >= active.opened_seq
        and str(p.get("from") or "") == own_pubkey
    ]
    if not own_posts:
        return None
    latest_own = max(own_posts, key=lambda p: int(p.get("seq", 0)))
    text = str(latest_own.get("text") or "")
    if not wg_tasks.is_working(text):
        return None
    working_ts = str(latest_own.get("ts") or "")
    # >= not > : timestamps are second-granular, so a turn that posts #working in
    # the same second its dispatch was stamped must still re-dispatch.
    if (
        working_ts and last_dispatch_at
        and not _stamp_at_or_after(working_ts, last_dispatch_at)
    ):
        return None
    return (
        "resume after #working without handoff "
        f"(seq #{int(latest_own.get('seq', 0))})"
    )


def _stamp_at_or_after(left: str, right: str) -> bool:
    import datetime as _dt

    try:
        ldt = _dt.datetime.strptime(left, "%Y-%m-%dT%H:%M:%SZ")
        rdt = _dt.datetime.strptime(right, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return False
    return ldt >= rdt


_TURN_TIMEOUT_SECONDS = 300
# Absolute wall-clock backstop (pipeline phases run longer than deliberation); idle kills sooner.
_PIPELINE_TURN_TIMEOUT_SECONDS = 900
_TURN_SIGTERM_GRACE_SECONDS = 5
# Idle (no-progress) kill. Activity = child's `--emit-events` stdout (tool start/end + mid-tool
# `tool_state`, incl. terminal's foreground heartbeat) + stderr; a lone LLM generation > idle trips it.
_TURN_IDLE_TIMEOUT_SECONDS = 180
_PIPELINE_TURN_IDLE_TIMEOUT_SECONDS = 300


def _turn_timeout_for(pipeline: bool) -> int:
    return _PIPELINE_TURN_TIMEOUT_SECONDS if pipeline else _TURN_TIMEOUT_SECONDS


def _turn_idle_timeout_for(pipeline: bool) -> int:
    return _PIPELINE_TURN_IDLE_TIMEOUT_SECONDS if pipeline else _TURN_IDLE_TIMEOUT_SECONDS


async def _kill_proc(proc: Any, wait_task: "asyncio.Future[int]") -> int:
    # wait_task is shielded so our own timeout/cancel can't cancel the single in-flight proc.wait().
    try:
        proc.terminate()
    except ProcessLookupError:
        pass
    try:
        return await asyncio.wait_for(
            asyncio.shield(wait_task), timeout=_TURN_SIGTERM_GRACE_SECONDS,
        )
    except asyncio.TimeoutError:
        pass
    try:
        proc.kill()
    except ProcessLookupError:
        pass
    try:
        return await asyncio.shield(wait_task)
    except Exception:  # noqa: BLE001
        return -9


async def _supervise_turn(
    proc: Any,
    last_activity: list[float],
    *,
    idle_timeout: float,
    backstop: float,
    started_at: float,
) -> tuple[int, bool, str | None]:
    # Kill on idle (now - last_activity[0] > idle_timeout) or backstop; returns (rc, timed_out, "idle"|"backstop"|None).
    wait_task: "asyncio.Future[int]" = asyncio.ensure_future(proc.wait())
    try:
        while True:
            now = time.monotonic()
            idle_deadline = last_activity[0] + idle_timeout
            abs_deadline = started_at + backstop
            slice_s = min(idle_deadline, abs_deadline) - now
            if slice_s <= 0:
                reason = "idle" if idle_deadline <= abs_deadline else "backstop"
                rc = await _kill_proc(proc, wait_task)
                return rc, True, reason
            done, _ = await asyncio.wait({wait_task}, timeout=slice_s)
            if wait_task in done:
                return wait_task.result(), False, None
    except asyncio.CancelledError:
        await _kill_proc(proc, wait_task)
        raise


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
    *, closure_only: bool = False, continuation: bool = False,
    next_phase: str = "",
    pipeline: bool = False,
    round_hub_seq: int | None = None,
    hub_pubkey: str = "", started_against_task_seq: int = 0,
    member_responded_seq: int | None = None,
    turn_budget_s: int = 0,
) -> None:
    """Spawn a background ``chat --once`` turn for a workgroup."""
    turn_timeout = turn_budget_s or _turn_timeout_for(pipeline)
    if continuation:
        nxt = next_phase or "<next>"
        prompt = (
            f"[workgroup-continuation] '#{wg_name or wg_id}' "
            f"(wg_id={wg_id}). {reason}.\n\n"
            "You just closed a phase with `#done`. The pipeline order is "
            f"fixed and the NEXT phase is `#{nxt}`. The `#done` already "
            "verified the finished phase — do NOT re-verify or re-read "
            "files. Your one job this turn is to OPEN THE NEXT PHASE.\n\n"
            f"Open EXACTLY ONE targeted task for `#{nxt}`'s owner — a single "
            f"`workgroup_post(wg_id=\"{wg_id}\", text=\"@<owner> #task "
            f"#{nxt} <what to produce>\")`. You know which agent owns "
            f"`#{nxt}` from your role/skill. If your briefing tracks any "
            "project/org state, update it in the same turn. Then you're "
            "done.\n\n"
            "Posting anything other than that one targeted `#task` — "
            "searching, re-reading, prose, another `#done` — is a FAILED "
            "turn that leaves the pipeline stuck. Open the task and stop."
        )
        env_extra: dict[str, str] = {}
    elif closure_only:
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
            "anything substantive — use `web_search` to find URLs and "
            "`web_extract` to read them (`web_fetch` returns a whole page and "
            "is only for when you need one verbatim), then post citing what "
            "you found. "
            "\n\nFollow your `Workgroup engagement rules` exactly. "
            "Valid actions, in priority:"
            "\n  1. [hub only] If the deliverable is in the "
            "transcript AND quorum is reached, post "
            f"`workgroup_post(wg_id=\"{wg_id}\", "
            "text=\"#done <one-line result summary>\")` to close. "
            "QUORUM IS SCOPED TO THE TASK'S PARTICIPANTS: for a "
            "TARGETED task (the opener `@`-mentioned specific "
            "members) only those named participants need to have "
            "posted (substantive or `#skip`, ≥1 substantive) — do "
            "NOT wait on the rest of the roster; `@canvas #task "
            "#design` closes the moment canvas delivers. For a "
            "COLLECTIVE task (no `@`-mentions) every member must "
            "have posted.\n"
            "  2. [member, >30s before your handoff] If your next "
            "step will take more than ~30s before you can post "
            "something substantive — slow tools (web_fetch / "
            "research / delegate) OR, as the named participant on a "
            "production task, a long pass of LOCAL file work "
            "(writing/translating many files, an npm build) — FIRST "
            "post "
            f"`workgroup_post(wg_id=\"{wg_id}\", text=\"#working "
            "<concrete deliverable> (<tool>)\")` to signal the hub "
            "to wait. The reason MUST name what you're producing and "
            "the tool, e.g. \"#working writing Spanish source "
            "content under src/content/** (write_file)\". A bare "
            "\"#working\" wastes the only signal the hub has. Then "
            "do the work and come back to post substantive. Without "
            "this, the hub reads your silence as a stall and "
            "re-tasks you.\n"
            "  3. [member, your FIRST post on this active task] "
            "Find your angle from YOUR role's identity (your "
            "public_bio + memories) and post substantive content. "
            "Even a single concrete sentence is value. The hub "
            "assembled this workgroup specifically for the listed "
            "members — if you're here, your lens applies. Default "
            "to substantive, NOT to `#skip`. When your deliverable is "
            "ready, hand off with a PLAIN status line (e.g. \"content "
            "complete · 5 rooms + page copy\", \"build green · dist/ "
            "generated\"). NEVER post `#done` or `#task` — those are "
            "hub-only markers; the hub reads your plain handoff and "
            "closes the task. A member `#task` is rejected and a member "
            "`#done` is stripped to plain text, so the marker is wasted "
            "effort either way.\n"
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
            "`#working` reasons, `#skip` reasons, handoff and result "
            "summaries — "
            "in the same language as the active `#task`. If the "
            "task is in Spanish, post in Spanish. If French, French. "
            "Match the user, do not default to English."
        )
        env_extra = {}
    from alpi.home import effective_profile_env as _effective_profile_env, workspace_env
    env = _effective_profile_env(home, extra={
        "ALPI_HOME": str(home),
        "ALPI_WORKGROUP_DISPATCH": wg_id,
        **workspace_env(home),
        **({"ALPI_WORKGROUP_ROUND_HUB_SEQ": str(round_hub_seq)} if (round_hub_seq is not None and round_hub_seq > 0) else {}),
        **env_extra,
    })
    # `--emit-events`: child prints JSON event lines to stdout = the idle-timeout's sign-of-life (tail discarded).
    argv = [
        sys.executable, "-m", "alpi", "-p", profile,
        "chat", "--emit-events", "--once", prompt,
    ]
    posts_before = _post_count_for_role(home, wg_id)
    started_at = time.monotonic()
    try:
        proc = await asyncio.create_subprocess_exec(
            *argv,
            env=env,
            stdout=asyncio.subprocess.PIPE,
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
    last_activity = [started_at]

    def _bump() -> None:
        last_activity[0] = time.monotonic()

    # Bounded drain (full pipe + memory cap); every line bumps last_activity.
    stdout_task = asyncio.create_task(drain_tail(proc.stdout, on_activity=_bump))
    stderr_task = asyncio.create_task(drain_tail(proc.stderr, on_activity=_bump))

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
    kill_reason: str | None = None
    try:
        idle_timeout = _turn_idle_timeout_for(pipeline)
        rc, timed_out, kill_reason = await _supervise_turn(
            proc, last_activity,
            idle_timeout=idle_timeout,
            backstop=turn_timeout,
            started_at=started_at,
        )
        if timed_out:
            log.warning(
                "wg poller: turn for %s killed (%s) — idle>%ss or backstop>%ss",
                wg_id, kill_reason, idle_timeout, turn_timeout,
            )
    finally:
        info = _INFLIGHT.pop((wg_id, profile), {})
    preempted = bool(info.get("preempted"))
    preempted_by_seq = int(info.get("preempted_by_seq", 0))

    duration_s = round(time.monotonic() - started_at, 2)
    posts_after = _post_count_for_role(home, wg_id)
    posts_added = max(0, posts_after - posts_before)
    err_preview = ""
    event_tail = ""
    try:
        stderr_tail = await stderr_task
    except Exception:  # noqa: BLE001
        stderr_tail = ""
    try:
        event_tail = await stdout_task  # child `--emit-events` tail for post-mortem
    except Exception:  # noqa: BLE001
        pass
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
        extra = {"killed": True, "kill_reason": kill_reason}
    else:
        event = "end"
        extra = {"error": err_preview} if err_preview else {}
    if event_tail:
        # Cap bytes too (drain caps lines): keep turns.jsonl small + avoid stashing a huge/sensitive payload.
        extra["event_tail"] = event_tail[-2000:]
    _append_turn_event(home, {
        "ts": _utcnow_iso(),
        "event": event,
        "profile": profile, "wg_id": wg_id, "wg_name": wg_name,
        "duration_s": duration_s, "rc": rc,
        "posts_added": posts_added,
        **extra,
    })
    if member_responded_seq is not None and _should_advance_cursor(
        rc, posts_added, preempted, timed_out,
    ):
        _advance_member_cursor(home, wg_id, int(member_responded_seq))


def _should_advance_cursor(
    rc: int, posts_added: int, preempted: bool, timed_out: bool,
) -> bool:
    """Deliberate silence (rc 0) or a delivered post counts as responded; crash/timeout/preempt re-dispatches. A killed turn can exit rc 0 via a SIGTERM handler, so timed_out gates on delivery, not rc."""
    if preempted:
        return False
    if timed_out:
        return posts_added > 0
    return rc == 0 or posts_added > 0


def _advance_member_cursor(home: Path, wg_id: str, responded_seq: int) -> None:
    from alpi.alp import subscription as sub_mod
    try:
        sub = sub_mod.get(home, wg_id)
        if sub is None:
            return
        if responded_seq > int(sub.last_responded_seq or 0):
            sub.last_responded_seq = responded_seq
            sub_mod.upsert(home, sub)
    except Exception as e:  # noqa: BLE001
        log.warning("wg poller: cursor advance failed for %s: %s", wg_id, e)


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


DEFAULT_ALP_TCP_PORT = 7423


def _resolve_alp_tcp(cfg, managed: bool, is_default: bool = True) -> tuple[str | None, int | None]:
    # ALP TCP (bind_host, port) or (None, None) for Unix-only. Always-on:
    # binds whenever resolve_bind_host yields a local-safe address from the
    # advertised network.host (env ALPI_NETWORK_HOST wins).
    from alpi.host.network import resolve_bind_host

    configured = str((cfg.network or {}).get("host") or "").strip() or None
    env_host = str(os.environ.get("ALPI_NETWORK_HOST") or "").strip()
    if env_host:
        configured = env_host
    configured_port = (cfg.alp or {}).get("tcp_port")
    # Only default (or a profile with its own tcp_port) binds ALP TCP — else every profile fights the same default port.
    if configured_port is None and not is_default:
        return None, None
    tcp_port = configured_port or DEFAULT_ALP_TCP_PORT
    env_port = str(os.environ.get("ALPI_ALP_TCP_PORT") or "").strip()
    if env_port:
        try:
            tcp_port = int(env_port)
        except ValueError:
            pass
    allow_public = bool((getattr(cfg, "host", None) or {}).get("allow_public_bind") or False)
    tcp_host = resolve_bind_host(configured, is_docker=managed, allow_public=allow_public)
    if tcp_host is None:
        return None, None
    return tcp_host, tcp_port


async def _run_alp(home: Path, profile: str) -> None:
    from alpi import config as cfg_mod
    from alpi import runtime
    from alpi.alp import blobs as alp_blobs
    from alpi.alp import handlers as alp_handlers
    from alpi.alp import workgroup as alp_workgroup
    from alpi.alp.server import Server

    cfg = cfg_mod.load(home)
    # Network detection blocks (Tailscale CLI); off-loop so one slow profile can't starve host.sock + the others.
    tcp_host, tcp_port = await asyncio.to_thread(
        _resolve_alp_tcp, cfg, runtime.is_docker(), profile == "default",
    )
    server = Server(
        home=home,
        agent_name=profile,
        tcp_host=tcp_host,
        tcp_port=tcp_port,
    )
    alp_handlers.register_link_ask(server, home)
    alp_blobs.register(server, home)
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
    from alpi.host import attachments_rpc as host_attachments
    from alpi.host import chat as host_chat
    from alpi.host import clarification as host_clarification
    from alpi.host import config as host_config
    from alpi.host import daemon as host_daemon
    from alpi.host import device_state as host_device_state
    from alpi.host import events as host_events
    from alpi.host import handlers as host_handlers
    from alpi.host import connections as host_connections
    from alpi.host import network_rpc as host_network
    from alpi.host import outputs as host_outputs
    from alpi.host import probes as host_probes
    from alpi.host import schedule as host_schedule
    from alpi.host import tools as host_tools
    from alpi.host import usage as host_usage
    from alpi import runtime
    from alpi.host import recipes as host_recipes
    from alpi.host import workgroup_admin as host_wg_admin
    from alpi.host.network import host_allow_public_bind, resolve_host_tcp_bind
    from alpi.host.server import Server as HostServer

    server = HostServer(
        home=home,
        tcp_bind=None,
        allow_public_bind=host_allow_public_bind(home),
    )
    try:
        host_connections.load_store()
    except host_connections.StoreUnavailable:
        log.warning(
            "connections store unavailable at boot; remote authentication will fail closed",
            exc_info=True,
        )
    host_handlers.register(server)
    host_chat.register(server)
    host_config.register(server)
    host_device_state.register(server)
    host_daemon.register(server)
    host_events.register(server)
    host_approval.register(server)
    host_clarification.register(server)
    host_schedule.register(server)
    host_wg_admin.register(server)
    host_recipes.register(server)
    host_probes.register(server)
    host_connections.register(server)
    host_network.register(server)
    host_outputs.register(server)
    host_tools.register(server)
    host_usage.register(server)
    host_attachments.register(server)
    await server.start()  # host.sock up immediately — never blocked on network detection
    try:
        # TCP bind needs network detection (slow under launchd); resolve off-loop, and a bind failure must NOT take down host.sock.
        try:
            tcp_bind = await asyncio.to_thread(resolve_host_tcp_bind, home)
            if tcp_bind is None:
                log.info(
                    "no reachable address auto-detected; host TCP listener disabled "
                    "(Unix socket still up). Set network.host to expose it explicitly.",
                )
            else:
                host, port = tcp_bind
                log.info("host TCP bind chosen: %s:%d (%s)", host, port, runtime.platform_id() or "auto")
                await server.enable_tcp(tcp_bind)
        except Exception:  # noqa: BLE001
            log.warning("host TCP listener disabled — bind/detection failed; Unix socket still serving", exc_info=True)
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
    pid = os.getpid()
    start = _proc_starttime(pid)
    p.write_text(f"{pid} {start}" if start else str(pid))


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
  <key>SoftResourceLimits</key>
  <dict>
    <key>NumberOfFiles</key>
    <integer>8192</integer>
  </dict>
  <key>HardResourceLimits</key>
  <dict>
    <key>NumberOfFiles</key>
    <integer>8192</integer>
  </dict>
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
LimitNOFILE=8192
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
