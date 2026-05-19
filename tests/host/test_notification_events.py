"""Daemon-emitted notification events: budget/schedule/wg. Rust dispatcher tested separately."""

from __future__ import annotations

from pathlib import Path

import pytest

from alpi import ledger
from alpi.alp import workgroup as wg_mod
from alpi.alp import workgroup_client as wc
from alpi.alp.keys import load_or_generate
from alpi.host import events as host_events
from alpi.scheduler import run as sched_run


@pytest.fixture
def home(tmp_path: Path) -> Path:
    h = tmp_path / "h"
    h.mkdir()
    return h


@pytest.fixture
def captured(monkeypatch):
    """Stand-in subscriber that bypasses the asyncio queue path."""
    captured: list[tuple[str, dict]] = []

    def fake_emit(kind: str, data=None):
        captured.append((kind, dict(data or {})))

    monkeypatch.setattr(host_events, "emit", fake_emit)
    return captured


def _profile_home(tmp_path: Path, name: str) -> Path:
    """Lay out a path that mirrors ~/.alpi/profiles/<name>, so profile_name() resolves correctly instead of returning the parent dir's name."""
    h = tmp_path / "profiles" / name
    h.mkdir(parents=True)
    return h


def test_budget_threshold_emits_at_80(tmp_path: Path, captured: list) -> None:
    home = _profile_home(tmp_path, "vera")
    ledger.record(home, usd=4.05, tokens=0, cfg_budget={"daily_usd": 5.0})
    hits = [d for k, d in captured if k == "budget.threshold"]
    assert len(hits) == 1 and hits[0]["level"] == "80"
    assert hits[0]["profile"] == "vera"


def test_budget_threshold_emits_at_100(tmp_path: Path, captured: list) -> None:
    home = _profile_home(tmp_path, "echo")
    ledger.record(home, usd=4.0, tokens=0, cfg_budget={"daily_usd": 5.0})
    ledger.record(home, usd=1.5, tokens=0, cfg_budget={"daily_usd": 5.0})
    hits = [d for k, d in captured if k == "budget.threshold"]
    levels = [d["level"] for d in hits]
    assert "80" in levels and "100" in levels
    assert all(d["profile"] == "echo" for d in hits)


def test_budget_threshold_does_not_repeat(home: Path, captured: list) -> None:
    ledger.record(home, usd=4.5, tokens=0, cfg_budget={"daily_usd": 5.0})
    ledger.record(home, usd=0.1, tokens=0, cfg_budget={"daily_usd": 5.0})
    crossings = [d for k, d in captured if k == "budget.threshold"]
    assert len(crossings) == 1 and crossings[0]["level"] == "80"


def test_budget_threshold_jumps_past_80_emits_only_100(
    home: Path, captured: list,
) -> None:
    ledger.record(home, usd=6.0, tokens=0, cfg_budget={"daily_usd": 5.0})
    crossings = [d for k, d in captured if k == "budget.threshold"]
    assert len(crossings) == 1 and crossings[0]["level"] == "100"


def test_budget_threshold_silent_without_cap(home: Path, captured: list) -> None:
    ledger.record(home, usd=100.0, tokens=0)
    assert not [k for k, _ in captured if k == "budget.threshold"]


def test_budget_threshold_profile_default_for_root_home(
    tmp_path: Path, captured: list, monkeypatch,
) -> None:
    """Root home must resolve to ``default``, not the literal dir name."""
    home = tmp_path / ".alpi"
    home.mkdir()
    ledger.record(home, usd=4.5, tokens=0, cfg_budget={"daily_usd": 5.0})
    hits = [d for k, d in captured if k == "budget.threshold"]
    assert hits and hits[0]["profile"] == "default"


def test_schedule_tick_emits_done(tmp_path: Path, captured: list, monkeypatch) -> None:
    home = _profile_home(tmp_path, "atlas")
    sched_dir = home / "schedule"
    sched_dir.mkdir()
    (sched_dir / "jobs.json").write_text(
        '[{"id":"j1","kind":"cron","expression":"* * * * *","argv":["true"]}]'
    )
    monkeypatch.setattr(
        sched_run, "run_job",
        lambda job, h: sched_run.JobOutcome(True, "ran", reply="agent reply text"),
    )
    sched_run.tick(home)
    hits = [d for k, d in captured if k == "schedule.done"]
    assert hits and hits[0]["job_id"] == "j1"
    assert hits[0]["profile"] == "atlas"
    assert hits[0]["reply"] == "agent reply text"


def test_schedule_tick_emits_failed(tmp_path: Path, captured: list, monkeypatch) -> None:
    home = _profile_home(tmp_path, "rex")
    sched_dir = home / "schedule"
    sched_dir.mkdir()
    (sched_dir / "jobs.json").write_text(
        '[{"id":"j2","kind":"cron","expression":"* * * * *","argv":["false"]}]'
    )
    monkeypatch.setattr(sched_run, "run_job", lambda job, h: sched_run.JobOutcome(False, "boom"))
    sched_run.tick(home)
    hits = [d for k, d in captured if k == "schedule.failed"]
    assert hits and hits[0]["job_id"] == "j2" and hits[0]["message"] == "boom"
    assert hits[0]["profile"] == "rex"
    # Failed jobs carry an empty reply — no notification body to render.
    assert hits[0]["reply"] == ""


def _wg_with_hub(tmp_path: Path):
    hub_home = tmp_path / "profiles" / "hub"; hub_home.mkdir(parents=True)
    member_home = tmp_path / "profiles" / "m"; member_home.mkdir(parents=True)
    hub_kp = load_or_generate(hub_home)
    member_kp = load_or_generate(member_home)
    wg = wg_mod.create(
        hub_home, name="ntest", hub_kp=hub_kp,
        member_pubkeys=[member_kp.pubkey_b64()],
    )
    return hub_home, wg, hub_kp


@pytest.mark.asyncio
async def test_wg_done_emits_from_hub_post_unit(
    tmp_path: Path, captured: list, monkeypatch,
) -> None:
    """Both host endpoint and tool path funnel through ``wc.post``."""
    hub_home, wg, _ = _wg_with_hub(tmp_path)
    monkeypatch.setattr(
        wc, "_post_as_hub",
        lambda home, wg, kp, text, cost: {"seq": 7, "ts": "now"},
    )
    await wc.post(hub_home, wg.meta.id, b"#done shipped the v0.5 cycle")
    emits = [d for k, d in captured if k == "wg.done"]
    assert len(emits) == 1
    assert emits[0]["wg_id"] == wg.meta.id
    assert emits[0]["seq"] == 7
    assert emits[0]["summary"].startswith("#done")
    assert emits[0]["profile"] == "hub"


@pytest.mark.asyncio
async def test_wg_done_silent_for_non_done_post(
    tmp_path: Path, captured: list, monkeypatch,
) -> None:
    hub_home, wg, _ = _wg_with_hub(tmp_path)
    monkeypatch.setattr(
        wc, "_post_as_hub",
        lambda home, wg, kp, text, cost: {"seq": 1, "ts": "now"},
    )
    await wc.post(hub_home, wg.meta.id, b"regular substantive message, no markers")
    assert not [k for k, _ in captured if k == "wg.done"]


@pytest.mark.asyncio
async def test_wg_done_emits_for_handle_prefixed_marker(
    tmp_path: Path, captured: list, monkeypatch,
) -> None:
    """Protocol allows ``@alice #done <result>`` — uses ``tasks_mod.is_done`` so handle prefixes are honoured."""
    hub_home, wg, _ = _wg_with_hub(tmp_path)
    monkeypatch.setattr(
        wc, "_post_as_hub",
        lambda home, wg, kp, text, cost: {"seq": 3, "ts": "now"},
    )
    await wc.post(hub_home, wg.meta.id, b"@vera @echo #done locked v0.6 scope")
    emits = [d for k, d in captured if k == "wg.done"]
    assert len(emits) == 1 and emits[0]["wg_id"] == wg.meta.id


@pytest.mark.asyncio
async def test_wg_done_silent_when_marker_is_inline_not_line_anchored(
    tmp_path: Path, captured: list, monkeypatch,
) -> None:
    """``"I'll #done it tomorrow"`` is NOT a marker — protocol requires line-anchored."""
    hub_home, wg, _ = _wg_with_hub(tmp_path)
    monkeypatch.setattr(
        wc, "_post_as_hub",
        lambda home, wg, kp, text, cost: {"seq": 4, "ts": "now"},
    )
    await wc.post(hub_home, wg.meta.id, b"I'll #done it tomorrow when ready")
    assert not [k for k, _ in captured if k == "wg.done"]


@pytest.mark.asyncio
async def test_wg_done_emits_through_real_post_path(
    tmp_path: Path, captured: list, monkeypatch,
) -> None:
    """Real post path: no stub, full validation + encryption + transcript + ledger."""
    hub_home, wg, _ = _wg_with_hub(tmp_path)
    monkeypatch.setattr(wc, "_FULL_QUORUM_TIMEOUT_SECONDS", 0)

    await wc.post(hub_home, wg.meta.id, b"#task draft the v0.6 cycle scope")
    assert not [k for k, _ in captured if k == "wg.done"]

    result = await wc.post(
        hub_home, wg.meta.id,
        b"#done v0.6 scope locked: ORG.1 convention + AC curator",
    )

    emits = [d for k, d in captured if k == "wg.done"]
    assert len(emits) == 1
    assert emits[0]["wg_id"] == wg.meta.id
    assert emits[0]["seq"] == result["seq"]
    assert emits[0]["profile"] == "hub"
    assert "v0.6 scope locked" in emits[0]["summary"]

    from alpi.alp.workgroup import _read_transcript, _wg_dir
    raw = _read_transcript(_wg_dir(hub_home, wg.meta.id))
    assert len(raw) == 2 and raw[1]["seq"] == result["seq"]


def test_profile_name_default_for_root_home() -> None:
    """Guard against the home.name regression — default profile lives at ~/.alpi."""
    from alpi.home import profile_name
    assert profile_name(Path.home() / ".alpi") == "default"
    assert profile_name(Path.home() / ".alpi" / "profiles" / "vera") == "vera"
