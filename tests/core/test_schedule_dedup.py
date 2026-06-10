"""Tests for the duplicate-prevention guard on ``schedule(action="add")``.

Why this exists: a real session ended up with two near-identical
schedules ("daily summary at 12:00 weekdays" twice) because each
``add`` call was treated independently. The guard fingerprints the
prompt + cron and rejects the second add unless ``force=true``.
"""

from __future__ import annotations

import json
from pathlib import Path

from alpi.tools.schedule import Schedule


def _add(**kw) -> object:
    kw.setdefault("kind", "cron")
    kw.setdefault("expression", "0 12 * * 1-5")
    kw.setdefault("prompt", "Send the daily summary for core, synapse, lobby")
    return Schedule().run(action="add", **kw)


def test_first_add_succeeds(tmp_home_no_env: Path) -> None:
    r = _add()
    assert r.ok


def test_second_identical_add_is_blocked(tmp_home_no_env: Path) -> None:
    _add()
    r = _add()
    assert not r.ok
    assert "similar job" in r.error.lower()
    jobs = json.loads((tmp_home_no_env / "schedule" / "jobs.json").read_text())
    assert len(jobs) == 1


def test_near_duplicate_with_minor_wording_change_is_still_blocked(
    tmp_home_no_env: Path,
) -> None:
    """Fingerprint takes the first 80 chars normalised. Two prompts that
    share their first 80 chars but diverge after — e.g. the second adds
    a delivery hint at the end — fingerprint to the same prefix and
    trip the guard."""
    long_prefix = (
        "Send the daily activity summary for the three Bitbucket repos "
        "core, synapse, and lobby; include open PRs only."
    )
    _add(prompt=long_prefix)
    r = _add(prompt=long_prefix + " — and post the result to Telegram.")
    assert not r.ok


def test_force_flag_bypasses_dedup(tmp_home_no_env: Path) -> None:
    _add()
    r = _add(force=True)
    assert r.ok
    jobs = json.loads((tmp_home_no_env / "schedule" / "jobs.json").read_text())
    assert len(jobs) == 2


def test_different_cron_is_not_a_duplicate(tmp_home_no_env: Path) -> None:
    _add(expression="0 12 * * 1-5")
    r = _add(expression="0 9 * * 1-5")
    assert r.ok


def test_different_kind_is_not_a_duplicate(tmp_home_no_env: Path) -> None:
    _add()
    r = _add(kind="once", run_at="2099-01-01T12:00:00", expression="")
    assert r.ok


def test_update_changes_existing_job_without_creating_duplicate(
    tmp_home_no_env: Path,
) -> None:
    _add(prompt="Summarize pending PRs for core, synapse, and lobby")
    jobs = json.loads((tmp_home_no_env / "schedule" / "jobs.json").read_text())
    job_id = jobs[0]["id"]

    r = Schedule().run(
        action="update",
        id=job_id,
        prompt="Run the Bitbucket daily activity summary skill",
    )

    assert r.ok, r.error
    jobs = json.loads((tmp_home_no_env / "schedule" / "jobs.json").read_text())
    assert len(jobs) == 1
    assert jobs[0]["id"] == job_id
    assert jobs[0]["prompt"] == "Run the Bitbucket daily activity summary skill"


def test_update_can_pause_existing_job(tmp_home_no_env: Path) -> None:
    _add()
    jobs = json.loads((tmp_home_no_env / "schedule" / "jobs.json").read_text())
    job_id = jobs[0]["id"]

    r = Schedule().run(action="update", id=job_id, paused=True)

    assert r.ok, r.error
    jobs = json.loads((tmp_home_no_env / "schedule" / "jobs.json").read_text())
    assert jobs[0]["paused"] is True


def test_add_allows_third_party_delivery_in_prompt(tmp_home_no_env: Path) -> None:
    # The old auto-delivery guard is gone: a prompt may tell the agent to send
    # to a third party via send_message (e.g. "post to Telegram") — that's an
    # explicit action, not a double-send.
    r = _add(prompt="Generate the daily summary and send it to Telegram.")
    assert r.ok, r.error
