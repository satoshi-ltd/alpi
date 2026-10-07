from __future__ import annotations

import json
from pathlib import Path

import pytest

from alpi import attention, memory as mem_mod, outputs
from alpi.host import events as host_events
from alpi.host import server as host_server
from alpi.scheduler import jobs_store
from alpi.scheduler import run as scheduler
from alpi.tools.schedule import DESCRIPTION_MAX, Schedule

_PAST = "2000-01-01T00:00:00+00:00"


def _skill(home: Path, name: str, front: str, category: str = "software") -> None:
    folder = home / "skills" / category / name
    folder.mkdir(parents=True)
    (folder / "SKILL.md").write_text(f"---\n{front}\n---\n\nBody\n")


def _memory(home: Path, name: str, size: int) -> None:
    (home / "memories").mkdir(parents=True, exist_ok=True)
    (home / "memories" / name).write_text("x" * size)


def _job(job_id: str = "j1", **extra) -> dict:
    return {"id": job_id, "kind": "cron", "expression": "* * * * *", "prompt": "do it", "last_run_at": _PAST, **extra}


@pytest.fixture
def emitted(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, dict]]:
    seen: list[tuple[str, dict]] = []
    monkeypatch.setattr(host_events, "emit", lambda kind, data=None, **_kw: seen.append((kind, data or {})))
    return seen


def test_a_healthy_profile_has_nothing_flagged(tmp_home_no_env: Path) -> None:
    _memory(tmp_home_no_env, "USER.md", 100)
    _skill(tmp_home_no_env, "fine", "name: fine\ndescription: A working skill\ncategory: software")

    data = attention.collect(tmp_home_no_env)

    assert data["total"] == 0
    assert data["counts"] == {"memory": 0, "skills": 0, "schedules": 0}


def test_memory_is_flagged_over_the_limit_and_from_ninety_percent(tmp_home_no_env: Path) -> None:
    _memory(tmp_home_no_env, "USER.md", mem_mod.USER_CHAR_LIMIT * 90 // 100)
    _memory(tmp_home_no_env, "MEMORY.md", mem_mod.MEMORY_CHAR_LIMIT + 10)
    _memory(tmp_home_no_env, "AGENT.md", mem_mod.AGENT_CHAR_LIMIT * 89 // 100)

    flagged = {i["file"]: i for i in attention.collect(tmp_home_no_env)["memory"]}

    assert set(flagged) == {"USER.md", "MEMORY.md"}
    assert flagged["MEMORY.md"]["over"] is True
    assert flagged["USER.md"]["over"] is False
    assert flagged["USER.md"]["pct"] == 90


def test_a_skill_that_fails_lint_or_lacks_its_environment_is_flagged(tmp_home_no_env: Path) -> None:
    _skill(tmp_home_no_env, "broken", "name: Not Kebab\ndescription: x\ncategory: software")
    _skill(tmp_home_no_env, "needs-token", "name: needs-token\ndescription: Uses a token\ncategory: software\nrequires_env: ['ATTN_TEST_TOKEN']")
    _skill(tmp_home_no_env, "fine", "name: fine\ndescription: A working skill\ncategory: software")

    items = {i["name"]: i for i in attention.collect(tmp_home_no_env)["skills"]}

    assert set(items) == {"broken", "needs-token"}
    assert items["broken"]["problem"] == "lint"
    assert items["broken"]["message"]
    assert items["needs-token"]["problem"] == "missing"
    assert "ATTN_TEST_TOKEN" in items["needs-token"]["message"]


def test_a_job_whose_last_run_failed_is_flagged_with_its_failure_and_last_good_run(tmp_home_no_env: Path) -> None:
    jobs_store.update(tmp_home_no_env, lambda _old: [
        _job("bad", title="Digest", last_run_status="error", last_run_message="timeout", last_run_at="2026-10-07T07:30:00+00:00", last_ok_at="2026-10-06T07:30:00+00:00"),
        _job("good", last_run_status="ok"),
        _job("held", last_run_status="error", paused=True),
    ])

    items = attention.collect(tmp_home_no_env)["schedules"]

    assert items == [{
        "id": "bad", "title": "Digest", "message": "timeout",
        "at": "2026-10-07T07:30:00+00:00", "last_ok_at": "2026-10-06T07:30:00+00:00",
    }]


def test_a_tick_records_the_failure_message_and_the_last_good_run(monkeypatch, tmp_home_no_env: Path) -> None:
    jobs_store.update(tmp_home_no_env, lambda _old: [_job()])
    outcomes = iter([scheduler.JobOutcome(False, "boom " + "x" * 600), scheduler.JobOutcome(True, "ok")])
    monkeypatch.setattr(scheduler, "run_job", lambda job, home: next(outcomes))

    scheduler.tick(tmp_home_no_env)
    failed = jobs_store.read(tmp_home_no_env)[0]
    jobs_store.update(tmp_home_no_env, lambda jobs: [{**jobs[0], "last_run_at": _PAST}])
    scheduler.tick(tmp_home_no_env)
    recovered = jobs_store.read(tmp_home_no_env)[0]

    assert failed["last_run_status"] == "error"
    assert len(failed["last_run_message"]) == scheduler.FAILURE_MESSAGE_CAP
    assert "last_ok_at" not in failed
    assert recovered["last_run_status"] == "ok"
    assert "last_run_message" not in recovered
    assert recovered["last_ok_at"] == recovered["last_run_at"]


def test_the_stored_failure_message_is_redacted(monkeypatch, tmp_home_no_env: Path) -> None:
    jobs_store.update(tmp_home_no_env, lambda _old: [_job()])
    monkeypatch.setattr(scheduler, "run_job", lambda job, home: scheduler.JobOutcome(False, "token sk-abcdefghijklmnopqrstuvwx leaked"))

    scheduler.tick(tmp_home_no_env)

    assert "sk-abcdefghijklmnopqrstuvwx" not in jobs_store.read(tmp_home_no_env)[0]["last_run_message"]


def test_reconcile_files_one_warning_per_new_item_and_never_repeats_it(tmp_home_no_env: Path, emitted) -> None:
    _memory(tmp_home_no_env, "AGENT.md", mem_mod.AGENT_CHAR_LIMIT + 100)

    attention.reconcile(tmp_home_no_env)
    attention.reconcile(tmp_home_no_env)

    rows = outputs.list_outputs(tmp_home_no_env) if hasattr(outputs, "list_outputs") else []
    warnings = [r for r in rows if r.get("type") == "warning"]
    assert len(warnings) == 1
    assert "AGENT.md" in warnings[0]["title"]
    assert [k for k, _ in emitted].count("attention.changed") == 1
    assert emitted[-1][1]["counts"]["memory"] == 1


def test_a_resolved_item_that_breaks_again_files_a_new_warning(tmp_home_no_env: Path, emitted) -> None:
    _memory(tmp_home_no_env, "AGENT.md", mem_mod.AGENT_CHAR_LIMIT + 100)
    attention.reconcile(tmp_home_no_env)
    _memory(tmp_home_no_env, "AGENT.md", 10)
    attention.reconcile(tmp_home_no_env)
    _memory(tmp_home_no_env, "AGENT.md", mem_mod.AGENT_CHAR_LIMIT + 100)
    attention.reconcile(tmp_home_no_env)

    warnings = [r for r in outputs.list_outputs(tmp_home_no_env) if r.get("type") == "warning"]
    assert len(warnings) == 2
    assert [k for k, _ in emitted].count("attention.changed") == 3


def test_a_failed_job_changes_the_event_but_adds_no_second_notification(tmp_home_no_env: Path, emitted) -> None:
    attention.reconcile(tmp_home_no_env)
    jobs_store.update(tmp_home_no_env, lambda _old: [_job(last_run_status="error", last_run_message="boom")])

    attention.reconcile(tmp_home_no_env)

    assert emitted[-1] == ("attention.changed", {"profile": "default", "counts": {"memory": 0, "skills": 0, "schedules": 1}, "total": 1})
    assert [r for r in outputs.list_outputs(tmp_home_no_env) if r.get("type") == "warning"] == []


def test_the_lines_say_what_needs_you(tmp_home_no_env: Path) -> None:
    _memory(tmp_home_no_env, "AGENT.md", mem_mod.AGENT_CHAR_LIMIT + 100)
    jobs_store.update(tmp_home_no_env, lambda _old: [_job(title="Digest", last_run_status="error", last_run_message="boom")])

    text = "\n".join(attention.lines(attention.collect(tmp_home_no_env)))

    assert "AGENT.md over its limit" in text
    assert "Digest failed — boom" in text


def test_the_verb_and_the_event_are_closed_to_members() -> None:
    assert "host.profile.attention" in host_server._ADMIN_METHODS
    assert host_server._is_member_blocked_event("attention.changed")


def test_the_status_rows_carry_what_needs_you(tmp_home_no_env: Path) -> None:
    from alpi.status import status_rows

    _memory(tmp_home_no_env, "AGENT.md", mem_mod.AGENT_CHAR_LIMIT + 100)

    rows = status_rows(session_id="s", model="m", turns=0, elapsed_seconds=None, input_tokens=0, output_tokens=0, cost_usd=0.0, home=tmp_home_no_env)

    assert any(label == "needs you" and "AGENT.md" in value for label, value in rows)


def test_a_job_takes_a_description_that_updates_and_clears(tmp_home_no_env: Path) -> None:
    added = Schedule().run(action="add", kind="cron", expression="0 6 * * 1", prompt="refresh", title="Weekly refresh", description="  Compares every listing with its intake.  ")
    assert added.ok
    job = jobs_store.read(tmp_home_no_env)[0]
    assert job["description"] == "Compares every listing with its intake."

    updated = Schedule().run(action="update", id=job["id"], description="Posts the differences to the hub.")
    assert updated.ok
    assert jobs_store.read(tmp_home_no_env)[0]["description"] == "Posts the differences to the hub."

    cleared = Schedule().run(action="update", id=job["id"], description="")
    assert cleared.ok
    assert "description" not in jobs_store.read(tmp_home_no_env)[0]


def test_a_description_over_the_limit_or_on_two_lines_is_refused(tmp_home_no_env: Path) -> None:
    too_long = Schedule().run(action="add", kind="cron", expression="0 6 * * 1", prompt="refresh", description="x" * (DESCRIPTION_MAX + 1))
    two_lines = Schedule().run(action="add", kind="cron", expression="0 6 * * 1", prompt="refresh", description="one\ntwo")

    assert not too_long.ok and str(DESCRIPTION_MAX) in too_long.error
    assert not two_lines.ok and "one line" in two_lines.error
    assert jobs_store.read(tmp_home_no_env) == []


def test_a_job_without_a_description_lists_as_before(tmp_home_no_env: Path) -> None:
    Schedule().run(action="add", kind="cron", expression="0 6 * * 1", prompt="refresh")

    assert "description" not in jobs_store.read(tmp_home_no_env)[0]


def test_the_console_list_shows_the_description_and_the_failure(tmp_home_no_env: Path) -> None:
    from click.testing import CliRunner

    from alpi.cli import main

    jobs_store.update(tmp_home_no_env, lambda _old: [_job(title="Digest", description="Summarises new reviews.", last_run_status="error", last_run_message="timeout")])

    result = CliRunner().invoke(main, ["schedule", "list"])

    assert "Summarises new reviews." in result.output
    assert "last: error (timeout)" in result.output


def test_profile_show_prints_what_needs_you(tmp_home_no_env: Path) -> None:
    from click.testing import CliRunner

    from alpi.cli import main

    from alpi import home as home_mod

    _memory(home_mod.home_for("default"), "AGENT.md", mem_mod.AGENT_CHAR_LIMIT + 100)

    result = CliRunner().invoke(main, ["profile", "show"])

    assert "AGENT.md over its limit" in result.output


@pytest.mark.asyncio
async def test_the_verb_returns_the_collected_sections(tmp_home_no_env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from alpi.host import device_state, handlers

    _memory(tmp_home_no_env, "AGENT.md", mem_mod.AGENT_CHAR_LIMIT + 100)
    monkeypatch.setattr(handlers, "_resolve_home", lambda profile: tmp_home_no_env)
    srv = host_server.Server(home=tmp_home_no_env)
    device_state.register(srv)

    resp = await srv._dispatch({"id": "a", "method": "host.profile.attention", "params": {"profile": "default"}})

    assert resp["result"]["counts"]["memory"] == 1
    assert resp["result"]["memory"][0]["file"] == "AGENT.md"
    assert json.dumps(resp["result"])


def test_a_skill_that_cannot_be_read_is_flagged_and_does_not_hide_the_rest(tmp_home_no_env: Path) -> None:
    folder = tmp_home_no_env / "skills" / "software" / "garbled"
    folder.mkdir(parents=True)
    (folder / "SKILL.md").write_bytes(b"---\nname: garbled\n\xff\xfe\n---\n")
    _memory(tmp_home_no_env, "AGENT.md", mem_mod.AGENT_CHAR_LIMIT + 100)

    data = attention.collect(tmp_home_no_env)

    assert [(i["name"], i["problem"]) for i in data["skills"]] == [("garbled", "lint")]
    assert data["counts"]["memory"] == 1


def test_a_skill_message_and_a_job_title_are_redacted_and_capped(tmp_home_no_env: Path) -> None:
    _skill(tmp_home_no_env, "leaky", "name: leaky\ndescription: x\ncategory: software\nrequires_env: ['sk-abcdefghijklmnopqrstuvwx=1']")
    jobs_store.update(tmp_home_no_env, lambda _old: [_job(title="T" * 500, last_run_status="error", last_run_message="sk-abcdefghijklmnopqrstuvwx " + "m" * 500)])

    data = attention.collect(tmp_home_no_env)

    assert "sk-abcdefghijklmnopqrstuvwx" not in json.dumps(data)
    assert len(data["skills"][0]["message"]) <= attention.MESSAGE_CAP
    assert len(data["schedules"][0]["title"]) == attention.TITLE_CAP
    assert len(data["schedules"][0]["message"]) <= attention.MESSAGE_CAP


def test_an_unwritable_state_files_nothing_instead_of_repeating_every_tick(tmp_home_no_env: Path, monkeypatch, emitted) -> None:
    _memory(tmp_home_no_env, "AGENT.md", mem_mod.AGENT_CHAR_LIMIT + 100)
    monkeypatch.setattr(attention, "_save_state", lambda home, keys: False)

    attention.reconcile(tmp_home_no_env)
    attention.reconcile(tmp_home_no_env)

    assert [r for r in outputs.list_outputs(tmp_home_no_env) if r.get("type") == "warning"] == []
    assert [k for k, _ in emitted] == ["attention.changed", "attention.changed"]


def test_many_new_items_collapse_into_one_warning(tmp_home_no_env: Path, emitted) -> None:
    for index in range(attention.FLOOD_LIMIT + 2):
        _skill(tmp_home_no_env, f"broken-{index}", "name: Not Kebab\ndescription: x\ncategory: software", category=f"cat{index}")

    attention.reconcile(tmp_home_no_env)

    warnings = [r for r in outputs.list_outputs(tmp_home_no_env) if r.get("type") == "warning"]
    assert len(warnings) == 1
    assert f"{attention.FLOOD_LIMIT + 2} items need you" in warnings[0]["title"]
    assert "alpi profile show" in warnings[0]["body"]


def test_two_skills_with_one_name_in_two_categories_each_get_their_own_warning(tmp_home_no_env: Path, emitted) -> None:
    _skill(tmp_home_no_env, "twin", "name: Not Kebab\ndescription: x\ncategory: software", category="software")
    _skill(tmp_home_no_env, "twin", "name: twin\ndescription: x\ncategory: research\nrequires_env: ['ATTN_TWIN_TOKEN']", category="research")

    attention.reconcile(tmp_home_no_env)

    titles = sorted(r["title"] for r in outputs.list_outputs(tmp_home_no_env) if r.get("type") == "warning")
    assert titles == ["Skill does not pass lint: software/twin", "Skill is missing what it requires: research/twin"]


def test_a_description_that_is_not_a_string_or_spans_unicode_lines_is_refused(tmp_home_no_env: Path) -> None:
    number = Schedule().run(action="add", kind="cron", expression="0 6 * * 1", prompt="refresh", description=5)
    separator = Schedule().run(action="add", kind="cron", expression="0 6 * * 1", prompt="refresh", description="one two")

    assert not number.ok and "string" in number.error
    assert not separator.ok and "one line" in separator.error


def test_one_unreadable_skill_does_not_break_the_skills_listing(tmp_home_no_env: Path) -> None:
    from alpi.host.device_state import _skills_overview

    folder = tmp_home_no_env / "skills" / "software" / "garbled"
    folder.mkdir(parents=True)
    (folder / "SKILL.md").write_bytes(b"---\nname: garbled\n\xff\xfe\n---\n")
    _skill(tmp_home_no_env, "fine", "name: fine\ndescription: A working skill\ncategory: software")

    rows = _skills_overview(tmp_home_no_env, False)

    assert sorted(r["name"] for r in rows) == ["fine", "garbled"]


def test_a_warning_that_cannot_be_filed_is_logged_not_swallowed(tmp_home_no_env: Path, monkeypatch, caplog, emitted) -> None:
    _memory(tmp_home_no_env, "AGENT.md", mem_mod.AGENT_CHAR_LIMIT + 100)

    def broken(*_args, **_kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(outputs, "append", broken)

    with caplog.at_level("WARNING", logger="alpi.attention"):
        attention.reconcile(tmp_home_no_env)

    assert "could not file the attention warning" in caplog.text


def test_a_warning_that_failed_to_file_is_retried_once_the_write_recovers(tmp_home_no_env: Path, monkeypatch, emitted) -> None:
    _memory(tmp_home_no_env, "AGENT.md", mem_mod.AGENT_CHAR_LIMIT + 100)
    real_append = outputs.append
    state = {"fail": True}

    def flaky(*args, **kwargs):
        if state["fail"]:
            raise OSError("disk full")
        return real_append(*args, **kwargs)

    monkeypatch.setattr(outputs, "append", flaky)
    attention.reconcile(tmp_home_no_env)
    assert [r for r in outputs.list_outputs(tmp_home_no_env) if r.get("type") == "warning"] == []

    state["fail"] = False
    attention.reconcile(tmp_home_no_env)
    attention.reconcile(tmp_home_no_env)

    warnings = [r for r in outputs.list_outputs(tmp_home_no_env) if r.get("type") == "warning"]
    assert len(warnings) == 1
    assert "AGENT.md" in warnings[0]["title"]


def test_a_collapsed_warning_that_failed_to_file_retries_every_item_it_covered(tmp_home_no_env: Path, monkeypatch, emitted) -> None:
    for index in range(attention.FLOOD_LIMIT + 2):
        _skill(tmp_home_no_env, f"broken-{index}", "name: Not Kebab\ndescription: x\ncategory: software", category=f"cat{index}")
    real_append = outputs.append
    state = {"fail": True}

    def flaky(*args, **kwargs):
        if state["fail"]:
            raise OSError("disk full")
        return real_append(*args, **kwargs)

    monkeypatch.setattr(outputs, "append", flaky)
    attention.reconcile(tmp_home_no_env)
    state["fail"] = False
    attention.reconcile(tmp_home_no_env)

    warnings = [r for r in outputs.list_outputs(tmp_home_no_env) if r.get("type") == "warning"]
    assert [w["title"] for w in warnings] == [f"{attention.FLOOD_LIMIT + 2} items need you"]


def test_a_skill_the_daemon_may_not_read_is_flagged_and_does_not_hide_the_rest(tmp_home_no_env: Path, monkeypatch) -> None:
    from alpi.tools import skill as skill_mod

    _skill(tmp_home_no_env, "locked", "name: locked\ndescription: x\ncategory: software")
    _memory(tmp_home_no_env, "AGENT.md", mem_mod.AGENT_CHAR_LIMIT + 100)
    real = skill_mod._frontmatter

    def deny(path):
        if "locked" in str(path):
            raise PermissionError("denied")
        return real(path)

    monkeypatch.setattr(skill_mod, "_frontmatter", deny)

    data = attention.collect(tmp_home_no_env)

    assert [(i["name"], i["problem"]) for i in data["skills"]] == [("locked", "lint")]
    assert "PermissionError" in data["skills"][0]["message"]
    assert data["counts"]["memory"] == 1


def test_a_skill_with_a_stray_byte_lists_and_lints_from_the_same_text(tmp_home_no_env: Path) -> None:
    from alpi.host.device_state import _skills_overview

    folder = tmp_home_no_env / "skills" / "software" / "stray"
    folder.mkdir(parents=True)
    (folder / "SKILL.md").write_bytes(b"---\nname: stray\ndescription: Reads a stray \xff byte\ncategory: software\n---\n\nBody\n")

    row = _skills_overview(tmp_home_no_env, False)[0]

    assert "stray" in row["description"] and row["status"] == "active"
    assert attention.collect(tmp_home_no_env)["skills"] == []
