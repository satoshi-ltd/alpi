"""Host-side ``pipeline_run`` fold — the canonical view of a declared chain."""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

import pytest

from alpi.alp import subscription as sub_mod
from alpi.alp import workgroup as wg_mod
from alpi.alp.keys import load_or_generate
from alpi.host import workgroup as data_workgroup


@pytest.fixture
def short_tmp() -> Path:
    d = Path(tempfile.mkdtemp(prefix="alp-host-wgrun-", dir="/tmp"))
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


_CHAIN = {"intake": ["intake", "content", "build", "qa"]}
_STEPS = {
    "intake": {"owner": "scout", "task": "gather the brief"},
    "content": {"owner": "quill"},
    "build": {"owner": "pixel"},
    "qa": {"owner": "mira"},
}


def _hub(
    home: Path,
    *,
    pipelines: dict | None = None,
    launch: str | None = None,
    steps: dict | None = None,
    member_pubkeys: list[str] | None = None,
):
    home.mkdir(parents=True, exist_ok=True)
    kp = load_or_generate(home)
    return wg_mod.create(
        home,
        name="factory",
        hub_kp=kp,
        member_pubkeys=list(member_pubkeys or []),
        briefing="",
        pipelines=pipelines,
        launch_pipeline=launch,
        pipeline_steps=steps,
    )


def _append(home: Path, wg_id: str, body: str) -> int:
    kp = load_or_generate(home)
    wg = wg_mod.load(home, wg_id)
    assert wg is not None
    me = wg.member(kp.pubkey_b64())
    assert me is not None
    group_key = wg_mod.open_sealed_group_key(me.sealed_key, kp)
    p = home / "alp" / "workgroups" / wg_id / "transcript.jsonl"
    existing = [
        line for line in p.read_text(encoding="utf-8").splitlines() if line.strip()
    ] if p.exists() else []
    seq = len(existing) + 1
    nonce_b64, ct_b64 = wg_mod.encrypt_post(group_key, body.encode("utf-8"))
    entry = {
        "seq": seq,
        "ts": f"2026-05-01T00:00:{seq:02d}Z",
        "from": kp.pubkey_b64(),
        "key_version": me.key_version,
        "nonce": nonce_b64,
        "ciphertext": ct_b64,
    }
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, separators=(",", ":")) + "\n")
    return seq


def _transcript(home: Path, wg_id: str, bodies: list[str]) -> None:
    for body in bodies:
        _append(home, wg_id, body)


def _states(run: dict) -> dict[str, str]:
    return {p["slug"]: p["state"] for p in run["phases"]}


def _seqs(run: dict) -> dict[str, int | None]:
    return {p["slug"]: p["seq"] for p in run["phases"]}


def test_pipeline_run_running_marks_current_and_pending(short_tmp: Path) -> None:
    home = short_tmp / "hub"
    wg = _hub(home, pipelines=_CHAIN, launch="intake", steps=_STEPS)
    _transcript(home, wg.meta.id, ["@scout #task #intake gather the brief"])

    run = data_workgroup.fold_task_state(home, wg.meta.id)["pipeline_run"]
    assert run["pipeline"] == "intake"
    assert run["status"] == "running"
    assert run["current_phase"] == "intake"
    assert run["started_seq"] == 1
    assert run["phases"] == [
        {"slug": "intake", "state": "current", "seq": 1},
        {"slug": "content", "state": "pending", "seq": None},
        {"slug": "build", "state": "pending", "seq": None},
        {"slug": "qa", "state": "pending", "seq": None},
    ]


def test_pipeline_run_running_after_handoff_to_next_phase(short_tmp: Path) -> None:
    home = short_tmp / "hub"
    wg = _hub(home, pipelines=_CHAIN, launch="intake", steps=_STEPS)
    _transcript(home, wg.meta.id, [
        "@scout #task #intake gather the brief",
        "#done intake ready",
        "@quill #task #content write the copy",
    ])

    run = data_workgroup.fold_task_state(home, wg.meta.id)["pipeline_run"]
    assert run["status"] == "running"
    assert run["current_phase"] == "content"
    assert run["started_seq"] == 1
    assert _states(run) == {
        "intake": "completed", "content": "current",
        "build": "pending", "qa": "pending",
    }


def test_pipeline_run_between_when_no_successor_is_open(short_tmp: Path) -> None:
    home = short_tmp / "hub"
    wg = _hub(home, pipelines=_CHAIN, launch="intake", steps=_STEPS)
    _transcript(home, wg.meta.id, [
        "@scout #task #intake gather the brief",
        "#done intake ready",
    ])

    state = data_workgroup.fold_task_state(home, wg.meta.id)
    assert state["active"] is None
    run = state["pipeline_run"]
    assert run["status"] == "between"
    assert run["current_phase"] == "intake"
    assert _states(run) == {
        "intake": "completed", "content": "pending",
        "build": "pending", "qa": "pending",
    }
    assert _seqs(run)["intake"] == 2


def test_pipeline_run_blocked_keeps_the_phase_current(short_tmp: Path) -> None:
    home = short_tmp / "hub"
    wg = _hub(home, pipelines=_CHAIN, launch="intake", steps=_STEPS)
    _transcript(home, wg.meta.id, [
        "@scout #task #intake gather the brief",
        "#done BLOCKED intake · the hotel never answered",
    ])

    state = data_workgroup.fold_task_state(home, wg.meta.id)
    assert state["blocked"]["slug"] == "intake"
    run = state["pipeline_run"]
    assert run["status"] == "blocked"
    assert run["current_phase"] == "intake"
    assert _states(run)["intake"] == "current"
    assert _states(run)["content"] == "pending"


def test_pipeline_run_completed_when_terminal_phase_closed(short_tmp: Path) -> None:
    home = short_tmp / "hub"
    wg = _hub(
        home,
        pipelines={"intake": ["intake", "qa"]},
        launch="intake",
        steps={"intake": {"owner": "scout", "task": "gather"}, "qa": {"owner": "mira"}},
    )
    _transcript(home, wg.meta.id, [
        "@scout #task #intake gather the brief",
        "#done intake ready",
        "@mira #task #qa audit the build",
        "#done qa PASS",
    ])

    run = data_workgroup.fold_task_state(home, wg.meta.id)["pipeline_run"]
    assert run["status"] == "completed"
    assert run["current_phase"] == "qa"
    assert _states(run) == {"intake": "completed", "qa": "completed"}


def test_pipeline_run_skipped_phase_is_not_completed_and_advances(
    short_tmp: Path,
) -> None:
    home = short_tmp / "hub"
    wg = _hub(home, pipelines=_CHAIN, launch="intake", steps=_STEPS)
    _transcript(home, wg.meta.id, [
        "@scout #task #intake gather the brief",
        "#done intake ready",
        "@quill #task #content write the copy",
        "#done skipped · the client supplies the copy",
        "@pixel #task #build wire it",
    ])

    run = data_workgroup.fold_task_state(home, wg.meta.id)["pipeline_run"]
    assert _states(run)["content"] == "skipped"
    assert _states(run)["content"] != "completed"
    assert run["status"] == "running"
    assert run["current_phase"] == "build"
    assert _states(run) == {
        "intake": "completed", "content": "skipped",
        "build": "current", "qa": "pending",
    }


def test_second_named_pipeline_replaces_the_visible_run(short_tmp: Path) -> None:
    home = short_tmp / "hub"
    wg = _hub(
        home,
        pipelines={"intake": ["intake", "content"], "media": ["media", "publish"]},
        launch="intake",
        steps={
            "intake": {"owner": "scout", "task": "gather"},
            "content": {"owner": "quill"},
            "media": {"owner": "muse", "task": "shoot the rooms"},
            "publish": {"owner": "pixel"},
        },
    )
    _transcript(home, wg.meta.id, [
        "@scout #task #intake gather the brief",
        "#done intake ready",
        "@quill #task #content write the copy",
        "#done content shipped",
        "@muse #task #media shoot the rooms",
    ])

    run = data_workgroup.fold_task_state(home, wg.meta.id)["pipeline_run"]
    assert run["pipeline"] == "media"
    assert run["status"] == "running"
    assert run["started_seq"] == 5
    assert _states(run) == {"media": "current", "publish": "pending"}
    assert "content" not in _states(run)


def test_same_pipeline_triggered_again_starts_a_fresh_run(short_tmp: Path) -> None:
    home = short_tmp / "hub"
    wg = _hub(
        home,
        pipelines={"intake": ["intake", "content"]},
        launch="intake",
        steps={"intake": {"owner": "scout", "task": "gather"}, "content": {"owner": "quill"}},
    )
    _transcript(home, wg.meta.id, [
        "@scout #task #intake gather the brief",
        "#done intake ready",
        "@quill #task #content write the copy",
        "#done content shipped",
        "@scout #task #intake gather the next brief",
    ])

    run = data_workgroup.fold_task_state(home, wg.meta.id)["pipeline_run"]
    assert run["pipeline"] == "intake"
    assert run["started_seq"] == 5
    assert run["status"] == "running"
    assert _states(run) == {"intake": "current", "content": "pending"}
    assert _seqs(run) == {"intake": 5, "content": None}


def test_same_slug_reopen_stays_in_the_run_and_keeps_earlier_phases(
    short_tmp: Path,
) -> None:
    home = short_tmp / "hub"
    wg = _hub(home, pipelines=_CHAIN, launch="intake", steps=_STEPS)
    _transcript(home, wg.meta.id, [
        "@scout #task #intake gather the brief",
        "#done intake ready",
        "@quill #task #content write the copy",
        "#done BLOCKED content · the assets never arrived",
        "@quill #task #content-fix redo the copy",
    ])

    run = data_workgroup.fold_task_state(home, wg.meta.id)["pipeline_run"]
    assert run["started_seq"] == 1
    assert run["status"] == "running"
    assert run["current_phase"] == "content"
    assert _states(run) == {
        "intake": "completed", "content": "current",
        "build": "pending", "qa": "pending",
    }
    # The latest attempt owns the visible seq, not the blocked close it repaired.
    assert _seqs(run)["content"] == 5


def test_first_phase_reopen_on_the_first_phase_stays_in_the_run(
    short_tmp: Path,
) -> None:
    home = short_tmp / "hub"
    wg = _hub(home, pipelines=_CHAIN, launch="intake", steps=_STEPS)
    _transcript(home, wg.meta.id, [
        "@scout #task #intake gather the brief",
        "#done BLOCKED intake · the hotel never answered",
        "@scout #task #intake retry the outreach",
    ])

    run = data_workgroup.fold_task_state(home, wg.meta.id)["pipeline_run"]
    assert run["started_seq"] == 1
    assert run["status"] == "running"
    assert run["current_phase"] == "intake"
    assert _states(run)["intake"] == "current"
    assert _seqs(run)["intake"] == 3


def test_first_phase_reopen_from_a_later_phase_is_a_restart(short_tmp: Path) -> None:
    home = short_tmp / "hub"
    wg = _hub(home, pipelines=_CHAIN, launch="intake", steps=_STEPS)
    _transcript(home, wg.meta.id, [
        "@scout #task #intake gather the brief",
        "#done intake ready",
        "@quill #task #content write the copy",
        "@scout #task #intake start over from the brief",
    ])

    run = data_workgroup.fold_task_state(home, wg.meta.id)["pipeline_run"]
    assert run["started_seq"] == 4
    assert run["current_phase"] == "intake"
    assert _states(run) == {
        "intake": "current", "content": "pending",
        "build": "pending", "qa": "pending",
    }


def test_preempted_attempt_is_not_completed(short_tmp: Path) -> None:
    home = short_tmp / "hub"
    wg = _hub(home, pipelines=_CHAIN, launch="intake", steps=_STEPS)
    _transcript(home, wg.meta.id, [
        "@scout #task #intake gather the brief",
        "@quill #task #content write the copy",
    ])

    run = data_workgroup.fold_task_state(home, wg.meta.id)["pipeline_run"]
    assert run["started_seq"] == 1
    assert run["status"] == "running"
    assert _states(run)["intake"] != "completed"
    assert _states(run)["intake"] == "pending"
    assert _states(run)["content"] == "current"


def test_ad_hoc_task_after_a_run_hides_the_pipeline_run(short_tmp: Path) -> None:
    home = short_tmp / "hub"
    wg = _hub(home, pipelines=_CHAIN, launch="intake", steps=_STEPS)
    _transcript(home, wg.meta.id, [
        "@scout #task #intake gather the brief",
        "#done intake ready",
        "@pixel #task #hotfix patch the nav",
    ])

    state = data_workgroup.fold_task_state(home, wg.meta.id)
    assert state["active"]["slug"] == "hotfix"
    assert state["pipeline_run"] is None


def test_deliberation_workgroup_has_no_pipeline_run(short_tmp: Path) -> None:
    home = short_tmp / "hub"
    wg = _hub(home)
    _transcript(home, wg.meta.id, ["@quill #task #content write the copy"])

    state = data_workgroup.fold_task_state(home, wg.meta.id)
    assert state["active"]["slug"] == "content"
    assert state["pipeline_run"] is None


def test_subscriber_fold_uses_the_subscription_definitions(short_tmp: Path) -> None:
    member_home = short_tmp / "member"
    member_home.mkdir(parents=True, exist_ok=True)
    member_kp = load_or_generate(member_home)

    hub_home = short_tmp / "hub"
    wg = _hub(
        hub_home,
        pipelines=_CHAIN,
        launch="intake",
        steps=_STEPS,
        member_pubkeys=[member_kp.pubkey_b64()],
    )
    _transcript(hub_home, wg.meta.id, [
        "@scout #task #intake gather the brief",
        "#done intake ready",
        "@quill #task #content write the copy",
    ])

    hub_kp = load_or_generate(hub_home)
    sub = sub_mod.Subscription(
        wg_id=wg.meta.id,
        name=wg.meta.name,
        hub_id="hub",
        hub_pubkey=hub_kp.pubkey_b64(),
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
        (hub_home / "alp" / "workgroups" / wg.meta.id / "transcript.jsonl").read_text(
            encoding="utf-8",
        ),
        encoding="utf-8",
    )

    defs = data_workgroup.pipeline_defs(member_home, wg.meta.id)
    assert defs.pipelines == {"intake": ("intake", "content", "build", "qa")}
    assert defs.launch_pipeline == "intake"
    assert defs.pipeline_steps == sub.phase_map

    run = data_workgroup.fold_task_state(member_home, wg.meta.id)["pipeline_run"]
    assert run["pipeline"] == "intake"
    assert run["status"] == "running"
    assert run["current_phase"] == "content"
    assert _states(run) == {
        "intake": "completed", "content": "current",
        "build": "pending", "qa": "pending",
    }


def test_fold_is_cached_and_a_definitions_edit_invalidates_it(
    short_tmp: Path, monkeypatch,
) -> None:
    home = short_tmp / "hub"
    wg = _hub(
        home,
        pipelines={"intake": ["intake", "content"]},
        launch="intake",
        steps={"intake": {"owner": "scout", "task": "gather"}, "content": {"owner": "quill"}},
    )
    _transcript(home, wg.meta.id, ["@scout #task #intake gather the brief"])

    real = data_workgroup.decrypt_transcript
    calls = {"n": 0}

    def counting(*args, **kwargs):
        calls["n"] += 1
        return real(*args, **kwargs)

    monkeypatch.setattr(data_workgroup, "decrypt_transcript", counting)

    first = data_workgroup.fold_task_state(home, wg.meta.id)
    second = data_workgroup.fold_task_state(home, wg.meta.id)
    assert calls["n"] == 1
    assert second is first
    assert [p["slug"] for p in first["pipeline_run"]["phases"]] == ["intake", "content"]

    loaded = wg_mod.load(home, wg.meta.id)
    loaded.meta.pipelines = {"intake": ("intake", "content", "build")}
    wg_mod._save_meta(wg_mod._wg_dir(home, wg.meta.id), loaded.meta)

    third = data_workgroup.fold_task_state(home, wg.meta.id)
    assert calls["n"] == 2
    assert [p["slug"] for p in third["pipeline_run"]["phases"]] == [
        "intake", "content", "build",
    ]
