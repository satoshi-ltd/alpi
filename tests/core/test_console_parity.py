"""Console-parity surfaces: cleanup module, schedule/outputs CLI, setup wizard, TUI list helpers."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from click.testing import CliRunner

from alpi import cleanup, cli, outputs


def _seed(home: Path) -> None:
    (home / "cache/tts").mkdir(parents=True)
    (home / "cache/tts/a.mp3").write_bytes(b"x" * 100)
    (home / "logs/curator/2026-01-01").mkdir(parents=True)
    (home / "logs/curator/2026-01-01/report.md").write_text("r")


def test_cleanup_plan_is_wire_safe_and_counts(tmp_path: Path) -> None:
    home = tmp_path / "h"
    home.mkdir()
    _seed(home)
    plan = cleanup.plan(home)
    keys = {c["key"] for c in plan}
    assert {"tts", "sessions", "logs", "curator", "knowledge"} <= keys
    tts = next(c for c in plan if c["key"] == "tts")
    assert tts["size"] == 100 and tts["count"] == 1 and tts["action"] == "unlink"
    assert all("files" not in c for c in plan)
    json.dumps(plan)


def test_cleanup_apply_unlink_and_rmtree(tmp_path: Path) -> None:
    home = tmp_path / "h"
    home.mkdir()
    _seed(home)
    out = cleanup.apply(home, "tts")
    assert out["ok"] and out["removed"] == 1 and out["freed_bytes"] == 100
    assert not (home / "cache/tts/a.mp3").exists()

    out = cleanup.apply(home, "curator")
    assert out["ok"] and out["removed"] == 1
    assert not (home / "logs/curator/2026-01-01").exists()

    assert cleanup.apply(home, "tts")["removed"] == 0
    bad = cleanup.apply(home, "nope")
    assert not bad["ok"] and "unknown category" in bad["errors"][0]


def test_cleanup_apply_vacuum_shrinks_sqlite(tmp_path: Path) -> None:
    home = tmp_path / "h"
    home.mkdir()
    db = home / "knowledge.sqlite"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE t(x)")
    conn.executemany("INSERT INTO t VALUES (?)", [("y" * 1000,)] * 500)
    conn.commit()
    conn.execute("DELETE FROM t")
    conn.commit()
    conn.close()
    assert next(c for c in cleanup.plan(home) if c["key"] == "knowledge")["size"] > 0
    out = cleanup.apply(home, "knowledge")
    assert out["ok"] and out["before"] > out["after"]


def test_schedule_list_cli(tmp_home_no_env: Path) -> None:
    from alpi.scheduler import jobs_store

    jobs_store.update(tmp_home_no_env, lambda _old: [
        {"id": "aa11", "kind": "cron", "expression": "0 9 * * *",
         "prompt": "morning brief", "notify": True, "tier": "fast",
         "last_run_status": "ok"},
        {"id": "bb22", "kind": "once", "run_at": "2027-01-01T09:00:00",
         "prompt": "one shot", "paused": True},
    ])
    result = CliRunner().invoke(cli.main, ["schedule", "list"])
    assert result.exit_code == 0
    assert "aa11" in result.output and "bb22" in result.output
    assert "tier:fast" in result.output and "paused" in result.output

    result = CliRunner().invoke(cli.main, ["schedule", "list", "--json"])
    rows = json.loads(result.output)
    assert rows[0]["status"] == "due"
    from datetime import datetime
    assert datetime.fromisoformat(rows[0]["next_fire"]).tzinfo is not None
    assert rows[1]["status"] == "paused" and rows[1]["next_fire"] is None


def test_outputs_cli_list_show_read_all(tmp_home_no_env: Path) -> None:
    outputs.append(tmp_home_no_env, profile="default", body="first body",
                   type="info", title="First", delivered_to=[])
    outputs.append(tmp_home_no_env, profile="default", body="second body",
                   type="error", title="Second", delivered_to=[])

    result = CliRunner().invoke(cli.main, ["outputs", "list"])
    assert result.exit_code == 0
    assert "First" in result.output and "Second" in result.output
    assert "●" in result.output

    oid = outputs.list_outputs(tmp_home_no_env)[0]["id"]
    result = CliRunner().invoke(cli.main, ["outputs", "show", oid])
    assert result.exit_code == 0
    assert "second body" in result.output
    assert outputs.read(tmp_home_no_env, oid)["status"] == "read"

    result = CliRunner().invoke(cli.main, ["outputs", "read-all"])
    assert "marked 1 output(s) read" in result.output
    assert not outputs.list_outputs(tmp_home_no_env, status="unread")


def test_outputs_cli_list_all_profiles(tmp_home_no_env: Path) -> None:
    abby = tmp_home_no_env / "profiles" / "abby"
    abby.mkdir(parents=True)
    outputs.append(tmp_home_no_env, profile="default", body="root row",
                   type="info", title="Root", delivered_to=[])
    outputs.append(abby, profile="abby", body="abby row",
                   type="info", title="Abby", delivered_to=[])

    result = CliRunner().invoke(cli.main, ["outputs", "list", "--all-profiles", "--json"])
    assert result.exit_code == 0
    rows = json.loads(result.output)
    assert [r["profile"] for r in rows] == ["abby", "default"]

    result = CliRunner().invoke(cli.main, ["outputs", "list", "--all-profiles", "-n", "1", "--json"])
    assert [r["profile"] for r in json.loads(result.output)] == ["abby"]

    result = CliRunner().invoke(cli.main, ["outputs", "list", "--all-profiles"])
    assert "@abby" in result.output and "@default" in result.output


def test_setup_schedules_wizard_fire_pause_delete(tmp_home_no_env: Path, monkeypatch) -> None:
    from alpi.scheduler import jobs_store

    jobs_store.update(tmp_home_no_env, lambda _old: [
        {"id": "job1", "kind": "cron", "expression": "0 9 * * *", "prompt": "brief"},
    ])

    menus = iter(["job1", "toggle", None])
    monkeypatch.setattr("alpi.ui.menu", lambda *a, **kw: next(menus))
    monkeypatch.setattr("alpi.ui.ok_and_wait", lambda *a, **kw: None)
    cli._schedules_setup(tmp_home_no_env)
    assert jobs_store.read(tmp_home_no_env)[0]["paused"] is True

    menus = iter(["job1", "delete", None])
    monkeypatch.setattr("alpi.ui.menu", lambda *a, **kw: next(menus))
    monkeypatch.setattr("alpi.ui.confirm", lambda *a, **kw: True)
    cli._schedules_setup(tmp_home_no_env)
    assert jobs_store.read(tmp_home_no_env) == []

    assert "no jobs" in cli._schedules_status(tmp_home_no_env)


def test_tui_session_and_output_rows(tmp_path: Path) -> None:
    from alpi.tui.screens import list_output_rows, list_session_rows

    home = tmp_path / "h"
    (home / "sessions").mkdir(parents=True)
    (home / "sessions/abc123.json").write_text(json.dumps({
        "id": "abc123",
        "turns": [{"at": 1.0, "user": "list my open tasks", "assistant": "done", "tools": []}],
    }))
    (home / "sessions/_index.json").write_text("{}")

    rows = list_session_rows(home)
    assert len(rows) == 1
    assert rows[0]["id"] == "abc123"
    assert rows[0]["turns"] == 1
    assert rows[0]["preview"].startswith("list my open tasks")

    outputs.append(home, profile="p", body="cron said hi", type="info",
                   title="Cron", delivered_to=[])
    orows = list_output_rows(home)
    assert len(orows) == 1 and orows[0]["title"] == "Cron"


def test_sessions_category_only_includes_old_transcripts(tmp_path: Path) -> None:
    import os
    import time

    home = tmp_path / "h"
    (home / "sessions").mkdir(parents=True)
    fresh = home / "sessions/fresh.json"
    fresh.write_text("{}")
    old = home / "sessions/old.json"
    old.write_text("{}")
    stale = time.time() - (cleanup.SESSIONS_KEEP_DAYS + 5) * 86_400
    os.utime(old, (stale, stale))

    cat = next(c for c in cleanup.plan(home) if c["key"] == "sessions")
    assert cat["count"] == 1
    assert cat["destructive"] is True
    out = cleanup.apply(home, "sessions")
    assert out["removed"] == 1
    assert old.exists() is False
    assert fresh.exists() is True


def test_plan_flags_destructive_categories(tmp_path: Path) -> None:
    home = tmp_path / "h"
    home.mkdir()
    plan = {c["key"]: c["destructive"] for c in cleanup.plan(home)}
    assert plan["sessions"] and plan["mentions"] and plan["workgroups"]
    assert not plan["tts"] and not plan["logs"] and not plan["knowledge"]


def test_apply_partial_failure_reports_real_freed_bytes(tmp_path: Path, monkeypatch) -> None:
    import shutil as shutil_mod

    home = tmp_path / "h"
    (home / "logs/curator/keep").mkdir(parents=True)
    (home / "logs/curator/keep/r.md").write_text("x" * 300)
    (home / "logs/curator/gone").mkdir(parents=True)
    (home / "logs/curator/gone/r.md").write_text("y" * 100)

    real_rmtree = shutil_mod.rmtree

    def flaky(p, *a, **kw):
        if p.name == "keep":
            raise OSError("busy")
        return real_rmtree(p, *a, **kw)

    monkeypatch.setattr("alpi.cleanup.shutil.rmtree", flaky)
    out = cleanup.apply(home, "curator")
    assert not out["ok"]
    assert out["removed"] == 1
    assert out["freed_bytes"] == 100
    assert "keep: busy" in out["errors"][0]


def test_setup_schedule_pause_does_not_invent_last_run_at(
    tmp_home_no_env: Path, monkeypatch,
) -> None:
    from alpi.scheduler import jobs_store

    jobs_store.update(tmp_home_no_env, lambda _old: [
        {"id": "fresh1", "kind": "cron", "expression": "0 9 * * *", "prompt": "brief"},
    ])
    menus = iter(["fresh1", "toggle", None])
    monkeypatch.setattr("alpi.ui.menu", lambda *a, **kw: next(menus))
    monkeypatch.setattr("alpi.ui.ok_and_wait", lambda *a, **kw: None)
    cli._schedules_setup(tmp_home_no_env)
    job = jobs_store.read(tmp_home_no_env)[0]
    assert job["paused"] is True
    assert "last_run_at" not in job


def test_schedule_list_marks_due_jobs(tmp_home_no_env: Path) -> None:
    from alpi.scheduler import jobs_store

    jobs_store.update(tmp_home_no_env, lambda _old: [
        {"id": "due1", "kind": "cron", "expression": "0 9 * * *", "prompt": "never ran"},
    ])
    result = CliRunner().invoke(cli.main, ["schedule", "list"])
    assert result.exit_code == 0
    assert "due now" in result.output


def test_schedule_list_json_inactivity_matches_host_contract(
    tmp_home_no_env: Path,
) -> None:
    from datetime import datetime

    from alpi.scheduler import jobs_store

    jobs_store.update(tmp_home_no_env, lambda _old: [
        {"id": "idle1", "kind": "inactivity", "after_hours": 0.0001, "prompt": "nudge"},
    ])
    result = CliRunner().invoke(cli.main, ["schedule", "list", "--json"])
    rows = json.loads(result.output)
    assert rows[0]["status"] == "due"
    assert datetime.fromisoformat(rows[0]["next_fire"]).tzinfo is not None


def test_sessions_apply_fails_closed_when_busy_state_unknown(
    tmp_path: Path, monkeypatch,
) -> None:
    import os
    import time

    home = tmp_path / "h"
    (home / "sessions").mkdir(parents=True)
    stale = time.time() - (cleanup.SESSIONS_KEEP_DAYS + 5) * 86_400
    old_file = home / "sessions/oldsid.json"
    old_file.write_text(json.dumps({"id": "oldsid", "turns": [], "started_at": stale}))
    os.utime(old_file, (stale, stale))

    def boom(_h):
        raise RuntimeError("no profile map")

    monkeypatch.setattr("alpi.home.profile_name", boom)
    cat = next(c for c in cleanup.plan(home) if c["key"] == "sessions")
    assert cat["count"] == 0

    out = cleanup.apply(home, "sessions")
    assert not out["ok"]
    assert "cannot verify busy sessions" in out["errors"][0]
    assert old_file.exists()


def test_sessions_apply_respects_busy_claim(tmp_path: Path) -> None:
    import os
    import time

    from alpi.home import profile_name
    from alpi.host import chat as host_chat

    home = tmp_path / "h"
    (home / "sessions").mkdir(parents=True)
    stale = time.time() - (cleanup.SESSIONS_KEEP_DAYS + 5) * 86_400
    busy_file = home / "sessions/busysid.json"
    busy_file.write_text(json.dumps({"id": "busysid", "turns": [], "started_at": stale}))
    os.utime(busy_file, (stale, stale))

    key = host_chat.session_key(profile_name(home), "busysid")
    host_chat._session_active[key] = object()
    try:
        out = cleanup._apply_sessions(home, {"key": "sessions", "session_ids": ["busysid"]})
        assert not out["ok"]
        assert "session-busy" in out["errors"][0]
        assert busy_file.exists()
    finally:
        host_chat._session_active.pop(key, None)


def test_sessions_cleanup_deletes_coherent_pairs_and_forgets_recall(
    tmp_path: Path, monkeypatch,
) -> None:
    import os
    import time

    home = tmp_path / "h"
    (home / "sessions").mkdir(parents=True)
    stale = time.time() - (cleanup.SESSIONS_KEEP_DAYS + 5) * 86_400
    main = home / "sessions/oldsid.json"
    main.write_text(json.dumps({"id": "oldsid", "turns": [], "started_at": stale}))
    os.utime(main, (stale, stale))
    sidecar = home / "sessions/_events_oldsid.jsonl"
    sidecar.write_text('{"seq": 1}\n')

    forgotten: list[str] = []
    monkeypatch.setattr(
        "alpi.tools.recall.forget_session",
        lambda _h, sid: forgotten.append(sid),
    )
    out = cleanup.apply(home, "sessions")
    assert out["ok"] and out["removed"] == 1
    assert not main.exists() and not sidecar.exists()
    assert forgotten == ["oldsid"]


def test_sessions_cleanup_skips_busy_sessions(tmp_path: Path) -> None:
    import os
    import time

    from alpi.home import profile_name
    from alpi.host import chat as host_chat

    home = tmp_path / "h"
    (home / "sessions").mkdir(parents=True)
    stale = time.time() - (cleanup.SESSIONS_KEEP_DAYS + 5) * 86_400
    busy_file = home / "sessions/busysid.json"
    busy_file.write_text(json.dumps({"id": "busysid", "turns": [], "started_at": stale}))
    os.utime(busy_file, (stale, stale))

    key = host_chat.session_key(profile_name(home), "busysid")
    host_chat._session_active[key] = object()
    try:
        cat = next(c for c in cleanup.plan(home) if c["key"] == "sessions")
        assert cat["count"] == 0
        assert busy_file.exists()
    finally:
        host_chat._session_active.pop(key, None)


def test_setup_cleanup_wizard_deletes_old_sessions(tmp_path: Path, monkeypatch) -> None:
    import os
    import time

    home = tmp_path / "h"
    (home / "sessions").mkdir(parents=True)
    stale = time.time() - (cleanup.SESSIONS_KEEP_DAYS + 5) * 86_400
    old_file = home / "sessions/oldsid.json"
    old_file.write_text(json.dumps({"id": "oldsid", "turns": [], "started_at": stale}))
    os.utime(old_file, (stale, stale))
    sidecar = home / "sessions/_events_oldsid.jsonl"
    sidecar.write_text('{"seq": 1}\n')

    shown: list[list] = []

    def fake_menu(_title, items, **_kw):
        shown.append([(label, key, status) for label, key, status in items])
        return "sessions" if len(shown) == 1 else None

    monkeypatch.setattr("alpi.ui.menu", fake_menu)
    monkeypatch.setattr("alpi.ui.confirm", lambda *a, **kw: True)
    monkeypatch.setattr("alpi.ui.ok_and_wait", lambda *a, **kw: None)
    cli._cleanup_setup(home)

    sessions_row = next(r for r in shown[0] if r[1] == "sessions")
    assert sessions_row[2] != "empty"
    assert not old_file.exists()
    assert not sidecar.exists()
