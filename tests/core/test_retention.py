from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path

import pytest

from alpi import cleanup, config, runs, service
from alpi.core.run_context import RunContext
from alpi.home import profile_name
from alpi.host import chat as host_chat

DAY = 86_400


def _ctx(home: Path, run_id: str) -> RunContext:
    return RunContext(run_id, home, home, "default", "user", "s", "host")


def _age(path: Path, days: float) -> None:
    stamp = time.time() - days * DAY
    os.utime(path, (stamp, stamp))


def _finished_journal(home: Path, run_id: str, *, days: float) -> Path:
    ctx = _ctx(home, run_id)
    runs.start(ctx)
    runs.finish(ctx, "completed")
    path = runs.run_path(home, run_id)
    _age(path, days)
    return path


def _session(home: Path, sid: str, *, days: float, first_user: str = "") -> Path:
    d = home / "sessions"
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{sid}.json"
    at = time.time() - days * DAY
    payload = {"started_at": at}
    if first_user:
        payload["turns"] = [{"at": at, "ended_at": at, "user": first_user, "assistant": "ok", "tools": []}]
    path.write_text(json.dumps(payload))
    _age(path, days)
    return path


def _write_config(home: Path, block: str = "") -> None:
    home.mkdir(parents=True, exist_ok=True)
    (home / "config.yaml").write_text("model: test\n" + block)


# --------------------------------------------------------------------
# run journals
# --------------------------------------------------------------------


def test_journals_past_the_window_go_and_everything_else_stays(tmp_path: Path, monkeypatch) -> None:
    _write_config(tmp_path, "retention:\n  runs_days: 30\n")
    old = _finished_journal(tmp_path, "old", days=31)
    inside = _finished_journal(tmp_path, "inside", days=29)
    active = _finished_journal(tmp_path, "active", days=40)
    hung = _ctx(tmp_path, "hung")
    runs.start(hung)                                  # never finished: still "running"
    _age(runs.run_path(tmp_path, "hung"), 40)
    (tmp_path / "runs" / "corrupt.jsonl").write_text("not a journal\n")
    _age(tmp_path / "runs" / "corrupt.jsonl", 40)
    ledger = tmp_path / "logs" / "runs.jsonl"
    ledger.parent.mkdir()
    ledger.write_text('{"run_id": "old", "usd": 1.5}\n')
    _age(ledger, 400)

    runs.register_active(_ctx(tmp_path, "active"), object())
    try:
        result = cleanup.retention_sweep(tmp_path)
    finally:
        runs.unregister_active(_ctx(tmp_path, "active"))

    assert result["runs_removed"] == 1 and result["errors"] == []
    assert not old.exists()
    for path in (inside, active, runs.run_path(tmp_path, "hung"), tmp_path / "runs" / "corrupt.jsonl"):
        assert path.exists(), path.name
    assert ledger.exists() and ledger.read_text().startswith('{"run_id": "old"')


def test_a_swept_journal_takes_its_child_registry_with_it(tmp_path: Path, monkeypatch) -> None:
    _write_config(tmp_path, "retention:\n  runs_days: 30\n")
    monkeypatch.setattr(runs, "proc_starttime", lambda pid: f"start-{pid}")
    ctx = _ctx(tmp_path, "orphaned")
    runs.start(ctx)
    runs.append(tmp_path, "orphaned", "run.finished", {"outcome": "interrupted"})
    runs.record_child(ctx, 4242)                      # a registry the close never got to forget
    sidecar = runs.children_path(tmp_path, "orphaned")
    assert sidecar.exists()
    _age(runs.run_path(tmp_path, "orphaned"), 31)

    cleanup.retention_sweep(tmp_path)

    assert not runs.run_path(tmp_path, "orphaned").exists()
    assert not sidecar.exists()


def test_the_manual_size_cap_never_applies_to_the_daily_sweep(tmp_path: Path, monkeypatch) -> None:
    _write_config(tmp_path, "retention:\n  runs_days: 30\n")
    _finished_journal(tmp_path, "recent-big", days=5)
    monkeypatch.setattr(cleanup, "RUNS_KEEP_BYTES", 0)

    result = cleanup.retention_sweep(tmp_path)

    # Only age decides here; the byte cap belongs to `setup → Cleanup`.
    assert result["runs_removed"] == 0
    assert runs.run_path(tmp_path, "recent-big").exists()


def test_a_journal_that_cannot_be_deleted_is_reported_and_the_sweep_goes_on(
    tmp_path: Path, monkeypatch,
) -> None:
    _write_config(tmp_path, "retention:\n  runs_days: 30\n")
    stuck = _finished_journal(tmp_path, "stuck", days=40)
    other = _finished_journal(tmp_path, "other", days=40)
    real_unlink = Path.unlink

    def refuse_one(self: Path, *a, **kw):
        if self.name == "stuck.jsonl":
            raise PermissionError("read-only")
        return real_unlink(self, *a, **kw)

    monkeypatch.setattr(Path, "unlink", refuse_one)

    result = cleanup.retention_sweep(tmp_path)

    assert result["runs_removed"] == 1 and not other.exists() and stuck.exists()
    assert result["errors"] == ["runs/stuck.jsonl: read-only"]


def test_zero_keeps_journals_forever(tmp_path: Path) -> None:
    _write_config(tmp_path, "retention:\n  runs_days: 0\n  sessions_days: 0\n")
    ancient = _finished_journal(tmp_path, "ancient", days=3000)
    old_session = _session(tmp_path, "s-old", days=3000)

    result = cleanup.retention_sweep(tmp_path)

    assert result == {
        "runs_removed": 0, "runs_freed": 0, "sessions_removed": 0, "sessions_freed": 0,
        "workgroup_sessions_kept": 0, "running_sessions_kept": 0, "sessions_kept_fresh": 0,
        "errors": [],
    }
    assert ancient.exists() and old_session.exists()


def test_a_profile_without_the_block_is_never_swept(tmp_path: Path) -> None:
    _write_config(tmp_path)
    assert (config.load(tmp_path).retention.runs_days, config.load(tmp_path).retention.sessions_days) == (0, 0)
    ancient_run = _finished_journal(tmp_path, "ancient", days=3000)
    ancient_session = _session(tmp_path, "s-ancient", days=3000)

    result = cleanup.retention_sweep(tmp_path)

    # Retention is opt-in: no block, no deletions, ever.
    assert result["runs_removed"] == 0 and result["sessions_removed"] == 0
    assert ancient_run.exists() and ancient_session.exists()


def test_the_window_is_honoured_to_the_day_once_set(tmp_path: Path) -> None:
    _write_config(tmp_path, "retention:\n  runs_days: 90\n  sessions_days: 90\n")
    just_inside = _finished_journal(tmp_path, "inside", days=89)
    just_past = _finished_journal(tmp_path, "past", days=91)
    _session(tmp_path, "s-inside", days=89)
    _session(tmp_path, "s-past", days=91)

    result = cleanup.retention_sweep(tmp_path)

    assert result["runs_removed"] == 1 and result["sessions_removed"] == 1
    assert just_inside.exists() and not just_past.exists()
    assert (tmp_path / "sessions" / "s-inside.json").exists()
    assert not (tmp_path / "sessions" / "s-past.json").exists()


# --------------------------------------------------------------------
# sessions
# --------------------------------------------------------------------


def test_sessions_past_the_window_go_unless_busy(tmp_path: Path) -> None:
    _write_config(tmp_path, "retention:\n  sessions_days: 7\n")
    old = _session(tmp_path, "old", days=8)
    fresh = _session(tmp_path, "fresh", days=6)
    busy = _session(tmp_path, "busy", days=8)
    key = host_chat.session_key(profile_name(tmp_path), "busy")
    with host_chat._active_lock:
        host_chat._session_active[key] = object()
    try:
        result = cleanup.retention_sweep(tmp_path)
    finally:
        with host_chat._active_lock:
            host_chat._session_active.pop(key, None)

    assert result["sessions_removed"] == 1
    assert not old.exists() and fresh.exists() and busy.exists()


def test_a_session_of_a_workgroup_that_still_exists_survives(tmp_path: Path) -> None:
    _write_config(tmp_path, "retention:\n  sessions_days: 7\n")
    (tmp_path / "alp" / "workgroups" / "abc123").mkdir(parents=True)
    live = _session(
        tmp_path, "wg-live", days=30,
        first_user="[workgroup-pipeline] '#site' (wg_id=abc123). Phase content opened.",
    )
    gone = _session(
        tmp_path, "wg-gone", days=30,
        first_user="[workgroup-continuation] '#site' (wg_id=zzz999). Next phase.",
    )
    plain = _session(tmp_path, "plain", days=30, first_user="hola")

    result = cleanup.retention_sweep(tmp_path)

    assert live.exists(), "the workgroup is still there; its session is still referenced"
    assert not gone.exists() and not plain.exists()
    assert result["sessions_removed"] == 2 and result["workgroup_sessions_kept"] == 1


def test_a_long_workgroup_name_cannot_push_the_id_out_of_reach(tmp_path: Path) -> None:
    _write_config(tmp_path, "retention:\n  sessions_days: 7\n")
    (tmp_path / "alp" / "workgroups" / "abc123").mkdir(parents=True)
    # The listing keeps 140 chars of the first message; the id sits well past that here.
    name = "hotel-" + "x" * 160
    live = _session(tmp_path, "wg-long", days=30,
                    first_user=f"[workgroup-pipeline] '#{name}' (wg_id=abc123). Phase content opened.")

    from alpi.host import sessions as host_sessions
    row = next(r for r in host_sessions.list_sessions(tmp_path) if r["id"] == "wg-long")
    assert "wg_id=" not in row["first_user"], "precondition: the id really is truncated away"

    result = cleanup.retention_sweep(tmp_path)

    assert live.exists() and result["workgroup_sessions_kept"] == 1


def test_the_full_id_is_what_lets_a_long_named_vanished_workgroup_go(tmp_path: Path) -> None:
    _write_config(tmp_path, "retention:\n  sessions_days: 7\n")
    name = "hotel-" + "x" * 160
    # No `alp/workgroups/zzz999`: read whole, the id says the workgroup is gone and the session may go;
    # read truncated, the id is missing and the fail-closed rule would keep it for nothing.
    gone = _session(tmp_path, "wg-long-gone", days=30,
                    first_user=f"[workgroup-pipeline] '#{name}' (wg_id=zzz999). Phase content opened.")

    result = cleanup.retention_sweep(tmp_path)

    assert not gone.exists()
    assert result["sessions_removed"] == 1 and result["workgroup_sessions_kept"] == 0


def test_a_workgroup_session_with_no_readable_identity_is_kept_not_guessed(tmp_path: Path) -> None:
    _write_config(tmp_path, "retention:\n  sessions_days: 7\n")
    unlabelled = _session(tmp_path, "wg-noid", days=30, first_user="[workgroup-pipeline] '#x' no id here")

    result = cleanup.retention_sweep(tmp_path)

    assert unlabelled.exists() and result["workgroup_sessions_kept"] == 1


def test_a_session_with_a_run_still_open_is_kept_whoever_is_running_it(tmp_path: Path) -> None:
    _write_config(tmp_path, "retention:\n  sessions_days: 7\n")
    old = _session(tmp_path, "cli-old", days=30)
    # A CLI/TUI or scheduled child never registers in host.chat; its open journal is the trail.
    ctx = RunContext("r1", tmp_path, tmp_path, "default", "user", "cli-old", "host")
    runs.start(ctx)

    first = cleanup.retention_sweep(tmp_path)
    assert old.exists() and first["running_sessions_kept"] == 1

    runs.finish(ctx, "completed")
    second = cleanup.retention_sweep(tmp_path)
    assert not old.exists() and second["sessions_removed"] == 1


def test_a_turn_that_lands_after_selection_saves_the_session(tmp_path: Path, monkeypatch) -> None:
    _write_config(tmp_path, "retention:\n  sessions_days: 7\n")
    path = _session(tmp_path, "racy", days=30)
    original = cleanup._old_sessions

    def select_then_a_turn_lands(h, keep_days=None):
        ids, size = original(h, keep_days)
        now = time.time()
        path.write_text(json.dumps({"started_at": now - 30 * DAY,
                                    "turns": [{"at": now, "ended_at": now, "user": "hi", "assistant": "ok", "tools": []}]}))
        os.utime(path, (now, now))
        return ids, size

    monkeypatch.setattr(cleanup, "_old_sessions", select_then_a_turn_lands)

    result = cleanup.retention_sweep(tmp_path)

    assert path.exists()
    assert result["sessions_removed"] == 0 and result["sessions_kept_fresh"] == 1 and result["errors"] == []


def test_the_manual_cleanup_revalidates_age_under_the_claim_too(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "h"
    path = _session(home, "racy", days=cleanup.SESSIONS_KEEP_DAYS + 5)
    original = cleanup._old_sessions

    def select_then_a_turn_lands(h, keep_days=None):
        # apply() re-selects internally; the turn has to land after that and before the delete.
        ids, size = original(h, keep_days)
        now = time.time()
        path.write_text(json.dumps({"started_at": now}))
        os.utime(path, (now, now))
        return ids, size

    monkeypatch.setattr(cleanup, "_old_sessions", select_then_a_turn_lands)

    out = cleanup.apply(home, "sessions")

    assert path.exists() and out["removed"] == 0 and out["skipped_fresh"] == ["racy"]


def test_every_dispatch_prompt_shape_names_its_workgroup() -> None:
    shapes = [
        "[workgroup-routing] '#x' (wg_id=a1b2). r.",
        "[workgroup-continuation] '#x' (wg_id=a1b2). r.",
        "[workgroup-gate-final] '#x' (wg_id=a1b2). r.",
        "[workgroup-watchdog] '#x' (wg_id=a1b2). r.",
        "[workgroup-pipeline] '#x' (wg_id=a1b2). r.",
        "[workgroup-poller] new activity in workgroup '#x' (wg_id=a1b2). Reason: r.",
    ]
    assert [cleanup._workgroup_of(s) for s in shapes] == ["a1b2"] * len(shapes)
    assert cleanup._workgroup_of("[workgroup-pipeline] without an id") is None
    assert cleanup._workgroup_of("") is None


def test_a_deleted_sessions_cost_is_archived_first(tmp_path: Path) -> None:
    _write_config(tmp_path, "retention:\n  sessions_days: 7\n")
    d = tmp_path / "sessions"
    d.mkdir()
    at = time.time() - 30 * DAY
    (d / "paid.json").write_text(json.dumps({
        "started_at": at, "cost_usd": 0.42, "input_tokens": 100, "output_tokens": 50,
        "turns": [{"at": at, "ended_at": at, "user": "hi", "assistant": "ok", "tools": []}],
    }))
    _age(d / "paid.json", 30)

    cleanup.retention_sweep(tmp_path)

    from alpi import ledger
    rows = [json.loads(line) for line in ledger.archive_path(tmp_path).read_text().splitlines()]
    assert [(r["kind"], r["id"], r["cost_usd"]) for r in rows] == [("session", "paid", 0.42)]


def test_unknown_busy_state_skips_sessions_but_still_sweeps_runs(tmp_path: Path, monkeypatch) -> None:
    _write_config(tmp_path, "retention:\n  runs_days: 7\n  sessions_days: 7\n")
    old_run = _finished_journal(tmp_path, "old", days=30)
    old_session = _session(tmp_path, "old", days=30)
    monkeypatch.setattr(cleanup, "_busy_session_ids", lambda h: None)

    result = cleanup.retention_sweep(tmp_path)

    # Fail closed on sessions, never on the whole sweep.
    assert not old_run.exists() and old_session.exists()
    assert result["errors"] == ["sessions: cannot verify busy sessions; skipped"]


# --------------------------------------------------------------------
# the daemon's daily gate
# --------------------------------------------------------------------


def test_the_sweep_is_due_once_and_then_a_day_later() -> None:
    rt = {"next_retention_at": 1_000.0}
    assert service._retention_due(rt, 999.0) is False
    assert service._retention_due(rt, 1_000.0) is True
    assert rt["next_retention_at"] == 1_000.0 + service._RETENTION_SWEEP_SECONDS
    assert service._retention_due(rt, 1_001.0) is False
    assert service._RETENTION_SWEEP_SECONDS == 86_400.0


def test_a_new_profile_is_scheduled_shortly_after_start_not_immediately() -> None:
    # Startup has enough to do; deletions wait for the first quiet moment, then daily.
    assert 30.0 <= service._RETENTION_FIRST_DELAY_SECONDS < service._RETENTION_SWEEP_SECONDS


def test_the_daemon_logs_only_when_the_sweep_did_something(tmp_path: Path, caplog) -> None:
    _write_config(tmp_path, "retention:\n  runs_days: 7\n")
    caplog.set_level(logging.INFO, logger="alpi.service")

    service._sweep_retention(tmp_path, "quiet")
    assert not [r for r in caplog.records if "retention sweep" in r.getMessage()]

    _finished_journal(tmp_path, "old", days=30)
    service._sweep_retention(tmp_path, "busy")
    lines = [r.getMessage() for r in caplog.records if "retention sweep" in r.getMessage()]
    assert len(lines) == 1 and lines[0].startswith("profile busy: retention sweep — 1 run journal(s)")


def test_a_sweep_that_raises_is_contained_by_the_loop(tmp_path: Path, monkeypatch, caplog) -> None:
    import asyncio

    caplog.set_level(logging.ERROR, logger="alpi.service")
    monkeypatch.setattr(service, "_sweep_retention", lambda home, profile: 1 / 0)
    monkeypatch.setattr(service, "_sweep_runs", lambda home, profile: None)
    monkeypatch.setattr(service, "_reload_fingerprints", lambda home: {"alp": "x"})
    root = tmp_path
    (root / "config.yaml").write_text("model: test\n")
    registry = {"default": {"tasks": {}, "fps": {"alp": "x"}, "next_sweep_at": 0.0, "next_retention_at": 0.0}}

    asyncio.run(service._reconcile_profiles(root, registry))

    assert any("retention sweep raised" in r.getMessage() for r in caplog.records)
    assert registry["default"]["next_retention_at"] > time.time() + 80_000, "a raise must not re-fire every tick"


def test_a_session_whose_file_cannot_be_read_under_the_claim_is_kept(tmp_path: Path, monkeypatch) -> None:
    _write_config(tmp_path, "retention:\n  sessions_days: 7\n")
    path = _session(tmp_path, "murky", days=30)
    armed = {"on": False}
    original_select = cleanup._old_sessions
    real_read_text = Path.read_text

    def select_then_disk_goes_bad(h, keep_days=None):
        out = original_select(h, keep_days)
        armed["on"] = True                       # from here on, the file itself cannot be read
        return out

    def read_text(self: Path, *a, **kw):
        if armed["on"] and self == path:
            raise OSError("I/O error")
        return real_read_text(self, *a, **kw)

    monkeypatch.setattr(cleanup, "_old_sessions", select_then_disk_goes_bad)
    monkeypatch.setattr(Path, "read_text", read_text)

    result = cleanup.retention_sweep(tmp_path)

    # The listing's reader would have fallen back to mtime and called it old; the delete must not.
    assert path.exists() and result["sessions_removed"] == 0 and result["sessions_kept_fresh"] == 1


def test_a_run_that_starts_after_the_scan_still_saves_its_session(tmp_path: Path, monkeypatch) -> None:
    _write_config(tmp_path, "retention:\n  sessions_days: 7\n")
    path = _session(tmp_path, "late", days=30)
    original_running = cleanup._running_session_ids
    calls = {"n": 0}

    def scan_then_a_run_starts(h):
        seen = original_running(h)
        calls["n"] += 1
        if calls["n"] == 1:                      # the selection scan: a CLI run opens right after it
            runs.start(RunContext("r-late", h, h, "default", "user", "late", "host"))
        return seen

    monkeypatch.setattr(cleanup, "_running_session_ids", scan_then_a_run_starts)

    result = cleanup.retention_sweep(tmp_path)

    assert path.exists()
    assert result["sessions_removed"] == 0 and result["running_sessions_kept"] == 1
    assert calls["n"] == 2, "the open-run check must be repeated under the lock, not trusted from the scan"


def _hold_exclusive(sessions_dir: Path, seconds: float):
    import threading

    from alpi.session import sessions_lock

    held = threading.Event()

    def hold() -> None:
        with sessions_lock(sessions_dir, exclusive=True):
            held.set()
            time.sleep(seconds)

    t = threading.Thread(target=hold, daemon=True)
    t.start()
    held.wait(timeout=5)
    return t


def test_a_session_save_waits_for_a_delete_in_progress(tmp_path: Path) -> None:
    from alpi.session import Session

    sess = Session(home=tmp_path, model="m")
    sess.log_turn(user="hi", assistant="ok", tools=[])
    hold = _hold_exclusive(tmp_path / "sessions", 0.4)

    started = time.monotonic()
    sess.save()
    waited = time.monotonic() - started
    hold.join(timeout=5)

    assert waited >= 0.3, f"save did not wait for the exclusive holder ({waited:.2f}s)"
    assert (tmp_path / "sessions" / f"{sess.id}.json").exists()


def test_a_run_start_waits_for_a_delete_in_progress(tmp_path: Path) -> None:
    hold = _hold_exclusive(tmp_path / "sessions", 0.4)

    started = time.monotonic()
    runs.start(RunContext("r1", tmp_path, tmp_path, "default", "user", "s1", "host"))
    waited = time.monotonic() - started
    hold.join(timeout=5)

    assert waited >= 0.3, f"runs.start did not wait for the exclusive holder ({waited:.2f}s)"
    assert runs.run_path(tmp_path, "r1").exists()


def test_two_writers_share_the_lock_without_waiting_on_each_other(tmp_path: Path) -> None:
    import threading

    from alpi.session import sessions_lock

    inside = threading.Event()
    released = threading.Event()

    def writer() -> None:
        with sessions_lock(tmp_path / "sessions", exclusive=False):
            inside.set()
            released.wait(timeout=5)

    t = threading.Thread(target=writer, daemon=True)
    t.start()
    inside.wait(timeout=5)
    started = time.monotonic()
    with sessions_lock(tmp_path / "sessions", exclusive=False):
        pass
    released.set()
    t.join(timeout=5)

    assert time.monotonic() - started < 0.2, "a shared holder must not block another writer"


def test_a_delete_waits_for_a_writer_holding_the_shared_lock(tmp_path: Path) -> None:
    import threading

    from alpi.session import sessions_lock

    _write_config(tmp_path, "retention:\n  sessions_days: 7\n")
    path = _session(tmp_path, "old", days=30)
    inside = threading.Event()

    def writer_mid_save() -> None:
        with sessions_lock(tmp_path / "sessions", exclusive=False):
            inside.set()
            time.sleep(0.4)

    t = threading.Thread(target=writer_mid_save, daemon=True)
    t.start()
    inside.wait(timeout=5)

    started = time.monotonic()
    result = cleanup.retention_sweep(tmp_path)
    waited = time.monotonic() - started
    t.join(timeout=5)

    assert waited >= 0.3, f"the delete did not wait for the writer ({waited:.2f}s)"
    assert result["sessions_removed"] == 1 and not path.exists()


def test_a_session_file_that_is_not_an_object_is_kept_not_crashed_on(tmp_path: Path) -> None:
    _write_config(tmp_path, "retention:\n  sessions_days: 7\n")
    d = tmp_path / "sessions"
    d.mkdir()
    odd = d / "odd.json"
    odd.write_text("[]")
    _age(odd, 30)

    result = cleanup.retention_sweep(tmp_path)

    assert odd.exists() and result["errors"] == []


@pytest.mark.parametrize("during_delete", [False, True])
@pytest.mark.parametrize("manual", [False, True])
def test_unreadable_run_inventory_never_authorizes_session_deletion(
    tmp_path: Path, monkeypatch, during_delete: bool, manual: bool,
) -> None:
    _write_config(tmp_path, "retention:\n  sessions_days: 7\n")
    session = _session(tmp_path, "live", days=100)
    ctx = RunContext("live-run", tmp_path, tmp_path, "default", "user", "live", "cli")
    runs.start(ctx)
    # Closing initially lets selection reach the locked recheck, where a new run may exist.
    if during_delete:
        runs.finish(ctx, "completed")
    journal = runs.run_path(tmp_path, "live-run")
    original_apply = cleanup._apply_sessions
    original_open = Path.open
    armed = not during_delete

    def fail_read(path, *args, **kwargs):
        if armed and path == journal:
            raise PermissionError("journal cannot be read")
        return original_open(path, *args, **kwargs)

    def arm_before_delete(home, target):
        nonlocal armed
        if during_delete:
            runs.start(ctx)
            armed = True
        return original_apply(home, target)

    monkeypatch.setattr(Path, "open", fail_read)
    monkeypatch.setattr(cleanup, "_apply_sessions", arm_before_delete)
    result = cleanup.apply(tmp_path, "sessions") if manual else cleanup.retention_sweep(tmp_path)

    assert session.exists()
    assert result["errors"] and "journal cannot be read" in str(result["errors"])
    from alpi import ledger
    assert not ledger.archive_path(tmp_path).exists()
    key = host_chat.session_key(profile_name(tmp_path), "live")
    assert key not in host_chat._session_active

    armed = False
    runs.finish(ctx, "completed")
    monkeypatch.setattr(cleanup, "_apply_sessions", original_apply)
    recovered = cleanup.apply(tmp_path, "sessions") if manual else cleanup.retention_sweep(tmp_path)
    assert not session.exists() and recovered["errors"] == []


@pytest.mark.parametrize("broken", ["corrupt", "missing-session", "directory", "symlink", "unscannable"])
def test_unverifiable_run_inventory_preserves_sessions(tmp_path: Path, monkeypatch, broken: str) -> None:
    _write_config(tmp_path, "retention:\n  sessions_days: 7\n")
    session = _session(tmp_path, "old", days=100)
    root = tmp_path / "runs"
    if broken == "directory":
        root.write_text("not a directory")
    elif broken == "symlink":
        root.symlink_to(tmp_path / "missing", target_is_directory=True)
    else:
        root.mkdir()
        if broken == "corrupt":
            (root / "broken.jsonl").write_bytes(b"\xff\x00")
        elif broken == "missing-session":
            runs.start(RunContext("unknown", tmp_path, tmp_path, "default", "user", "", "cli"))
        else:
            original = Path.iterdir

            def refuse(path):
                if path == root:
                    raise PermissionError("cannot scan runs")
                return original(path)

            monkeypatch.setattr(Path, "iterdir", refuse)
    result = cleanup.retention_sweep(tmp_path)
    assert session.exists() and result["sessions_removed"] == 0
    assert result["errors"]


@pytest.mark.parametrize("value", ["true", "false", "1.5", ".inf", ".nan", "-1", "'7'"])
def test_invalid_retention_values_never_enable_deletion(tmp_path: Path, value: str) -> None:
    _write_config(tmp_path, f"retention:\n  runs_days: {value}\n  sessions_days: {value}\n")
    session = _session(tmp_path, "old", days=100)
    journal = _finished_journal(tmp_path, "old", days=100)
    result = cleanup.retention_sweep(tmp_path)
    assert config.load(tmp_path).retention == config.RetentionConfig()
    assert session.exists() and journal.exists() and result["errors"] == []


@pytest.mark.parametrize("value", ["true", "[]", "text"])
def test_non_mapping_retention_block_is_disabled(tmp_path: Path, value: str) -> None:
    _write_config(tmp_path, f"retention: {value}\n")
    assert config.load(tmp_path).retention == config.RetentionConfig()


def test_workgroup_created_after_selection_protects_its_session(tmp_path: Path, monkeypatch) -> None:
    _write_config(tmp_path, "retention:\n  sessions_days: 7\n")
    session = _session(tmp_path, "wg", days=100, first_user="[workgroup-pipeline] '#x' (wg_id=abc).")
    original = cleanup._apply_sessions

    def create_before_delete(home, target):
        (home / "alp" / "workgroups" / "abc").mkdir(parents=True)
        return original(home, target)

    monkeypatch.setattr(cleanup, "_apply_sessions", create_before_delete)
    result = cleanup.retention_sweep(tmp_path)
    assert session.exists() and result["workgroup_sessions_kept"] == 1


def test_unverifiable_workgroup_directory_preserves_session(tmp_path: Path, monkeypatch) -> None:
    _write_config(tmp_path, "retention:\n  sessions_days: 7\n")
    session = _session(tmp_path, "wg", days=100, first_user="[workgroup-pipeline] '#x' (wg_id=abc).")
    wg = tmp_path / "alp" / "workgroups" / "abc"
    original = Path.stat

    def unreadable(path, *args, **kwargs):
        if path == wg:
            raise PermissionError("workgroup unavailable")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", unreadable)
    result = cleanup.retention_sweep(tmp_path)
    assert session.exists() and result["workgroup_sessions_kept"] == 1
