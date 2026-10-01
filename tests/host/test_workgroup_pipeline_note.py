from __future__ import annotations

from pathlib import Path

from alpi.alp import pipeline_queue
from alpi.host import workgroup as data_workgroup
from alpi.host.device_state import _hub_workgroups
from tests.host.test_workgroup_pipeline_run import _append, _hub, short_tmp  # noqa: F401

_PIPELINES = {"intake": ["intake", "content"], "shoot": ["shoot", "edit"]}
_STEPS = {
    "intake": {"owner": "scout"}, "content": {"owner": "quill"},
    "shoot": {"owner": "pixel"}, "edit": {"owner": "mira"},
}


def _wg(home: Path, bodies: list[str]):
    wg = _hub(home, pipelines=_PIPELINES, launch="intake", steps=_STEPS)
    for body in bodies:
        _append(home, wg.meta.id, body)
    return wg


def test_a_row_with_nothing_finished_has_no_note(short_tmp: Path) -> None:
    home = short_tmp / "hub"
    wg = _wg(home, ["@scout #task #intake gather the brief"])

    assert data_workgroup.pipeline_note(home, wg.meta.id) == ""


def test_a_workgroup_without_a_run_has_no_note(short_tmp: Path) -> None:
    home = short_tmp / "hub"
    wg = _wg(home, [])

    assert data_workgroup.pipeline_note(home, wg.meta.id) == ""


def test_a_running_row_names_what_finished_and_no_next_phase(short_tmp: Path) -> None:
    home = short_tmp / "hub"
    wg = _wg(home, ["@scout #task #intake brief", "#done ready", "@quill #task #content copy"])

    assert data_workgroup.pipeline_note(home, wg.meta.id) == "intake done"


def test_a_row_between_phases_names_the_phase_that_waits(short_tmp: Path) -> None:
    home = short_tmp / "hub"
    wg = _wg(home, ["@scout #task #intake brief", "#done ready"])

    assert data_workgroup.pipeline_note(home, wg.meta.id) == "intake done · content next"


def test_a_queued_row_counts_a_long_list_of_finished_phases_and_keeps_the_waiting_one(short_tmp: Path) -> None:
    home = short_tmp / "hub"
    wg = _wg(home, [
        "@scout #task #intake brief", "#done ready",
        "@quill #task #content copy", "#done written",
    ])

    assert data_workgroup.pipeline_note(home, wg.meta.id, "shoot") == "2 done · shoot next"


def test_a_completed_run_names_what_finished_and_nothing_next(short_tmp: Path) -> None:
    home = short_tmp / "hub"
    wg = _wg(home, [
        "@scout #task #intake brief", "#done ready",
        "@quill #task #content copy", "#done written",
    ])

    assert data_workgroup.pipeline_note(home, wg.meta.id) == "intake, content done"


def test_a_note_that_fits_names_every_finished_phase(short_tmp: Path) -> None:
    home = short_tmp / "hub"
    wg = _wg(home, ["@scout #task #intake brief", "#done ready"])

    assert data_workgroup.pipeline_note(home, wg.meta.id, "shoot") == "intake done · shoot next"


def test_a_skipped_phase_is_not_counted_as_finished(short_tmp: Path) -> None:
    home = short_tmp / "hub"
    wg = _wg(home, [
        "@scout #task #intake brief", "#done ready",
        "@quill #task #content copy", "#done skipped · nothing to write",
    ])

    assert data_workgroup.pipeline_note(home, wg.meta.id) == "intake done"


def test_the_list_row_carries_the_note_for_a_queued_workgroup(short_tmp: Path) -> None:
    home = short_tmp / "hub"
    wg = _wg(home, [
        "@scout #task #intake brief", "#done ready",
        "@quill #task #content copy", "#done written",
    ])
    pipeline_queue.enqueue(home, wg.meta.id, "shoot")

    row = _hub_workgroups(home, "default", include_pipeline_status=True)[0]

    assert row["pipeline_status"] == "queued"
    assert row["pipeline_note"] == "2 done · shoot next"


def test_the_list_row_has_no_note_field_when_nothing_finished(short_tmp: Path) -> None:
    home = short_tmp / "hub"
    _wg(home, ["@scout #task #intake brief"])

    row = _hub_workgroups(home, "default", include_pipeline_status=True)[0]

    assert "pipeline_note" not in row


def test_the_lean_list_does_not_compute_the_note(short_tmp: Path) -> None:
    home = short_tmp / "hub"
    _wg(home, ["@scout #task #intake brief", "#done ready"])

    assert "pipeline_note" not in _hub_workgroups(home, "default")[0]


def test_the_cross_profile_list_carries_the_note_for_a_queued_hub_row(short_tmp: Path, monkeypatch) -> None:
    from alpi.host import device_state

    hub_home = short_tmp / "hub"
    wg = _wg(hub_home, ["@scout #task #intake brief", "#done ready"])
    pipeline_queue.enqueue(hub_home, wg.meta.id, "shoot")
    monkeypatch.setattr(device_state, "_profiles", lambda: [{"name": "hub", "home": str(hub_home), "is_default": False}])
    monkeypatch.setattr(device_state, "_resolve_home", lambda _name: hub_home)

    rows = device_state._aggregate_workgroups(None, include_pipeline_status=True)

    assert [r["pipeline_note"] for r in rows] == ["intake done · shoot next"]


def test_a_subscribed_row_carries_the_note_for_one_profile(short_tmp: Path) -> None:
    from alpi.alp import subscription as sub_mod
    from alpi.alp import workgroup as wg_mod
    from alpi.alp.keys import load_or_generate
    from alpi.host import device_state

    member_home = short_tmp / "member"
    member_home.mkdir()
    member_kp = load_or_generate(member_home)
    hub_home = short_tmp / "hub"
    wg = _hub(hub_home, pipelines=_PIPELINES, launch="intake", steps=_STEPS, member_pubkeys=[member_kp.pubkey_b64()])
    for body in ("@scout #task #intake brief", "#done ready"):
        _append(hub_home, wg.meta.id, body)
    sub = sub_mod.Subscription(
        wg_id=wg.meta.id, name=wg.meta.name, hub_id="hub",
        hub_pubkey=load_or_generate(hub_home).pubkey_b64(),
    )
    sub.upsert_key(1, wg.member(member_kp.pubkey_b64()).sealed_key)
    sub.absorb_pipeline_state({
        "pipelines": {k: list(v) for k, v in wg.meta.pipelines.items()},
        "launch_pipeline": wg.meta.launch_pipeline,
        "pipeline_mode": True,
        "phase_map": wg_mod.safe_phase_map(wg.meta),
    })
    sub_mod.upsert(member_home, sub)
    member_dir = member_home / "alp" / "workgroups" / wg.meta.id
    member_dir.mkdir(parents=True, exist_ok=True)
    (member_dir / "transcript.jsonl").write_text(
        (hub_home / "alp" / "workgroups" / wg.meta.id / "transcript.jsonl").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    rows = device_state._subscribed_workgroups(member_home, "member", include_pipeline_status=True)

    assert [r["pipeline_note"] for r in rows] == ["intake done · content next"]
