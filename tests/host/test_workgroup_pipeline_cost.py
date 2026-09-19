"""Spend rolled up to the ``pipeline_run`` boundaries the fold already computes."""

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
    d = Path(tempfile.mkdtemp(prefix="alp-host-wgcost-", dir="/tmp"))
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


_CHAIN = {"intake": ["intake", "content"]}
_STEPS = {"intake": {"owner": "scout"}, "content": {"owner": "quill"}}


def _hub(home: Path):
    home.mkdir(parents=True, exist_ok=True)
    return wg_mod.create(
        home,
        name="factory",
        hub_kp=load_or_generate(home),
        member_pubkeys=[],
        briefing="",
        pipelines=_CHAIN,
        launch_pipeline="intake",
        pipeline_steps=_STEPS,
    )


def _append(
    home: Path,
    wg_id: str,
    body: str,
    *,
    cost: dict | None = None,
    turn_id: str = "",
    author: str = "",
    pipeline_trigger: bool = False,
) -> int:
    kp = load_or_generate(home)
    wg = wg_mod.load(home, wg_id)
    me = wg.member(kp.pubkey_b64())
    group_key = wg_mod.open_sealed_group_key(me.sealed_key, kp)
    p = home / "alp" / "workgroups" / wg_id / "transcript.jsonl"
    existing = (
        [ln for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
        if p.exists() else []
    )
    seq = len(existing) + 1
    nonce_b64, ct_b64 = wg_mod.encrypt_post(group_key, body.encode("utf-8"))
    entry = {
        "seq": seq,
        "ts": f"2026-05-01T00:00:{seq:02d}Z",
        "from": author or kp.pubkey_b64(),
        "key_version": me.key_version,
        "nonce": nonce_b64,
        "ciphertext": ct_b64,
    }
    if cost:
        entry["cost"] = cost
    if turn_id:
        entry["turn_id"] = turn_id
    if pipeline_trigger:
        entry["pipeline_trigger"] = True
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, separators=(",", ":")) + "\n")
    return seq


def _settle(
    home: Path, wg_id: str, turn_id: str, cost: dict, *, author: str = "PK",
) -> None:
    p = home / "alp" / "workgroups" / wg_id / "ledger.json"
    raw = json.loads(p.read_text()) if p.exists() else {}
    raw.setdefault("settlements", []).append({
        "ts": "2026-05-01T01:00:00Z", "from": author, "turn_id": turn_id, "cost": cost,
    })
    p.write_text(json.dumps(raw))


def _me(home: Path) -> str:
    return load_or_generate(home).pubkey_b64()


def _run(home: Path, wg_id: str) -> dict:
    return data_workgroup.fold_task_state(home, wg_id)["pipeline_run"]


def _costs(run: dict) -> dict[str, dict]:
    return {p["slug"]: p["cost"] for p in run["phases"]}


def test_each_phase_owns_the_spend_posted_inside_it(short_tmp: Path) -> None:
    home = short_tmp / "hub"
    wg = _hub(home)
    _append(home, wg.meta.id, "@scout #task #intake go", cost={"usd": 0.10, "tokens": 100})
    _append(home, wg.meta.id, "#intake brief ready", cost={"usd": 0.40, "tokens": 400})
    _append(home, wg.meta.id, "#done intake ready", cost={"usd": 0.05, "tokens": 50})
    _append(home, wg.meta.id, "@quill #task #content write", cost={"usd": 0.02, "tokens": 20})
    _append(home, wg.meta.id, "#content copy in", cost={"usd": 1.00, "tokens": 900})

    costs = _costs(_run(home, wg.meta.id))
    assert costs["intake"]["usd"] == pytest.approx(0.55)
    assert costs["intake"]["tokens"] == 550
    assert costs["content"]["usd"] == pytest.approx(1.02)
    assert costs["content"]["tokens"] == 920


def test_the_run_total_is_the_sum_of_its_phases(short_tmp: Path) -> None:
    home = short_tmp / "hub"
    wg = _hub(home)
    _append(home, wg.meta.id, "@scout #task #intake go", cost={"usd": 0.10, "tokens": 100})
    _append(home, wg.meta.id, "#done intake ready", cost={"usd": 0.05, "tokens": 50})
    _append(home, wg.meta.id, "@quill #task #content write", cost={"usd": 0.25, "tokens": 200})

    run = _run(home, wg.meta.id)
    assert run["cost"]["usd"] == pytest.approx(0.40)
    assert run["cost"]["tokens"] == 350
    assert run["cost"]["usd"] == pytest.approx(
        sum(p["cost"]["usd"] for p in run["phases"]),
    )


def test_a_settlement_lands_on_the_phase_its_turn_posted_in(short_tmp: Path) -> None:
    home = short_tmp / "hub"
    wg = _hub(home)
    _append(home, wg.meta.id, "@scout #task #intake go")
    _append(home, wg.meta.id, "#intake brief", cost={"usd": 0.10, "tokens": 100}, turn_id="t1")
    _append(home, wg.meta.id, "#done intake ready")
    _append(home, wg.meta.id, "@quill #task #content write")
    # The residual the member never declared on its posts belongs to intake, not content.
    _settle(home, wg.meta.id, "t1", {"usd": 0.70, "tokens": 700}, author=_me(home))

    costs = _costs(_run(home, wg.meta.id))
    assert costs["intake"]["usd"] == pytest.approx(0.80)
    assert costs["intake"]["tokens"] == 800
    assert costs["content"]["usd"] == 0.0


def test_a_settlement_with_no_post_is_left_out_rather_than_guessed(short_tmp: Path) -> None:
    home = short_tmp / "hub"
    wg = _hub(home)
    _append(home, wg.meta.id, "@scout #task #intake go", cost={"usd": 0.10, "tokens": 100})
    _settle(home, wg.meta.id, "never-posted", {"usd": 9.99, "tokens": 9999})

    run = _run(home, wg.meta.id)
    assert run["cost"]["usd"] == pytest.approx(0.10)
    assert run["cost"]["tokens"] == 100


def test_a_settlement_written_after_the_posts_is_not_served_from_the_stale_fold(
    short_tmp: Path,
) -> None:
    home = short_tmp / "hub"
    wg = _hub(home)
    _append(home, wg.meta.id, "@scout #task #intake go")
    _append(home, wg.meta.id, "#intake brief", cost={"usd": 0.10, "tokens": 100}, turn_id="t1")
    assert _run(home, wg.meta.id)["cost"]["usd"] == pytest.approx(0.10)

    _settle(home, wg.meta.id, "t1", {"usd": 0.70, "tokens": 700}, author=_me(home))
    assert _run(home, wg.meta.id)["cost"]["usd"] == pytest.approx(0.80)


def test_a_retriggered_run_costs_only_its_own_attempt(short_tmp: Path) -> None:
    home = short_tmp / "hub"
    wg = _hub(home)
    _append(home, wg.meta.id, "@scout #task #intake go", cost={"usd": 5.00, "tokens": 5000})
    _append(home, wg.meta.id, "#done intake ready")
    _append(
        home, wg.meta.id, "@scout #task #intake go again",
        cost={"usd": 0.20, "tokens": 200}, pipeline_trigger=True,
    )

    run = _run(home, wg.meta.id)
    assert run["cost"]["usd"] == pytest.approx(0.20)
    assert run["cost"]["tokens"] == 200


def test_a_rewind_keeps_every_attempt_of_the_run(short_tmp: Path) -> None:
    home = short_tmp / "hub"
    wg = _hub(home)
    # The opener carries trigger metadata, so re-opening the first phase later is read
    # as a rewind inside this run and not as the legacy "a new run started" fallback.
    _append(
        home, wg.meta.id, "@scout #task #intake go",
        cost={"usd": 1.00, "tokens": 100}, pipeline_trigger=True,
    )
    _append(home, wg.meta.id, "#done intake ready")
    _append(home, wg.meta.id, "@quill #task #content write", cost={"usd": 2.00, "tokens": 200})
    _append(home, wg.meta.id, "#done content ready")
    _append(home, wg.meta.id, "@scout #task #intake redo", cost={"usd": 3.00, "tokens": 300})

    run = _run(home, wg.meta.id)
    assert run["cost"]["usd"] == pytest.approx(6.00)
    assert run["cost"]["tokens"] == 600
    costs = _costs(run)
    assert costs["intake"]["usd"] == pytest.approx(4.00)
    assert costs["content"]["usd"] == pytest.approx(2.00)


def test_a_preemption_charges_its_post_to_one_phase_only(short_tmp: Path) -> None:
    home = short_tmp / "hub"
    wg = _hub(home)
    _append(home, wg.meta.id, "@scout #task #intake go", cost={"usd": 1.00, "tokens": 100})
    # This post closes intake and opens content on the same seq; it cannot count twice.
    _append(home, wg.meta.id, "@quill #task #content write", cost={"usd": 2.00, "tokens": 200})

    run = _run(home, wg.meta.id)
    assert run["cost"]["usd"] == pytest.approx(3.00)
    assert run["cost"]["tokens"] == 300
    costs = _costs(run)
    assert costs["intake"]["usd"] + costs["content"]["usd"] == pytest.approx(3.00)


def test_a_settlement_follows_its_author_not_just_the_turn_id(short_tmp: Path) -> None:
    home = short_tmp / "hub"
    wg = _hub(home)
    _append(home, wg.meta.id, "@scout #task #intake go")
    _append(home, wg.meta.id, "#intake brief", turn_id="t1", author="SCOUT_PK")
    _append(home, wg.meta.id, "#done intake ready")
    _append(home, wg.meta.id, "@quill #task #content write")
    # Same turn id, different author: the ledger keys a turn by (from, turn_id).
    _append(home, wg.meta.id, "#content copy", turn_id="t1", author="QUILL_PK")
    _settle(home, wg.meta.id, "t1", {"usd": 0.30, "tokens": 30}, author="SCOUT_PK")
    _settle(home, wg.meta.id, "t1", {"usd": 0.70, "tokens": 70}, author="QUILL_PK")

    costs = _costs(_run(home, wg.meta.id))
    assert costs["intake"]["usd"] == pytest.approx(0.30)
    assert costs["content"]["usd"] == pytest.approx(0.70)


def _as_member(hub_home: Path, member_home: Path, wg) -> None:
    member_kp = load_or_generate(member_home)
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
    d = member_home / "alp" / "workgroups" / wg.meta.id
    d.mkdir(parents=True, exist_ok=True)
    src = hub_home / "alp" / "workgroups" / wg.meta.id / "transcript.jsonl"
    (d / "transcript.jsonl").write_text(src.read_text(encoding="utf-8"), encoding="utf-8")


def test_a_member_marks_its_total_as_declared_only(short_tmp: Path) -> None:
    hub_home, member_home = short_tmp / "hub", short_tmp / "member"
    member_home.mkdir(parents=True, exist_ok=True)
    member_kp = load_or_generate(member_home)
    hub_home.mkdir(parents=True, exist_ok=True)
    wg = wg_mod.create(
        hub_home, name="factory", hub_kp=load_or_generate(hub_home),
        member_pubkeys=[member_kp.pubkey_b64()], briefing="",
        pipelines=_CHAIN, launch_pipeline="intake", pipeline_steps=_STEPS,
    )
    _append(hub_home, wg.meta.id, "@scout #task #intake go")
    _append(hub_home, wg.meta.id, "#intake brief", cost={"usd": 0.10, "tokens": 100},
            turn_id="t1", author=_me(hub_home))
    # The residual only ever reaches the hub's ledger; the member never holds a copy.
    _settle(hub_home, wg.meta.id, "t1", {"usd": 0.70, "tokens": 700}, author=_me(hub_home))
    _as_member(hub_home, member_home, wg)

    hub = _run(hub_home, wg.meta.id)
    mine = _run(member_home, wg.meta.id)
    assert hub["cost"]["usd"] == pytest.approx(0.80)
    assert hub["cost_complete"] is True
    assert mine["cost"]["usd"] == pytest.approx(0.10)
    assert mine["cost_complete"] is False
    assert "declared only" in data_workgroup.run_cost_label(mine)
    assert "declared only" not in data_workgroup.run_cost_label(hub)


def test_a_task_outside_the_chain_is_not_billed_to_the_phase_before_it(
    short_tmp: Path,
) -> None:
    home = short_tmp / "hub"
    wg = _hub(home)
    _append(home, wg.meta.id, "@scout #task #intake go", cost={"usd": 1.00, "tokens": 100})
    _append(home, wg.meta.id, "#done intake ready")
    # An ad-hoc task between two phases is not pipeline spend and belongs to neither.
    _append(home, wg.meta.id, "@scout #task #sidequest look into it",
            cost={"usd": 10.00, "tokens": 1000})
    _append(home, wg.meta.id, "#done sidequest nothing there")
    _append(home, wg.meta.id, "@quill #task #content write", cost={"usd": 2.00, "tokens": 200})

    run = _run(home, wg.meta.id)
    assert run["cost"]["usd"] == pytest.approx(3.00)
    costs = _costs(run)
    assert costs["intake"]["usd"] == pytest.approx(1.00)
    assert costs["content"]["usd"] == pytest.approx(2.00)


def test_spend_after_a_finished_run_is_not_billed_to_its_last_phase(short_tmp: Path) -> None:
    home = short_tmp / "hub"
    wg = _hub(home)
    _append(home, wg.meta.id, "@scout #task #intake go")
    _append(home, wg.meta.id, "#done intake ready")
    _append(home, wg.meta.id, "@quill #task #content write", cost={"usd": 2.00, "tokens": 200})
    _append(home, wg.meta.id, "#done content ready")
    _append(home, wg.meta.id, "chatter after the run", cost={"usd": 7.00, "tokens": 700})

    assert _run(home, wg.meta.id)["cost"]["usd"] == pytest.approx(2.00)


@pytest.mark.parametrize("raw", ["{ not json", "null", "[]", '"a string"'])
def test_a_ledger_it_cannot_read_is_reported_as_partial_not_complete(
    short_tmp: Path, raw: str,
) -> None:
    home = short_tmp / "hub"
    wg = _hub(home)
    _append(home, wg.meta.id, "@scout #task #intake go", cost={"usd": 0.10, "tokens": 100})
    (home / "alp" / "workgroups" / wg.meta.id / "ledger.json").write_text(raw)

    run = _run(home, wg.meta.id)
    assert run["cost"]["usd"] == pytest.approx(0.10)
    assert run["cost_complete"] is False


def test_a_hub_that_lost_its_ledger_is_partial_not_a_confident_zero(
    short_tmp: Path,
) -> None:
    home = short_tmp / "hub"
    wg = _hub(home)
    _append(home, wg.meta.id, "@scout #task #intake go", cost={"usd": 0.10, "tokens": 100})
    # A hub writes the ledger at creation, so its absence means something removed it.
    (home / "alp" / "workgroups" / wg.meta.id / "ledger.json").unlink()

    assert _run(home, wg.meta.id)["cost_complete"] is False


def test_a_task_outside_the_chain_that_preempts_a_phase_keeps_its_own_opener(
    short_tmp: Path,
) -> None:
    home = short_tmp / "hub"
    wg = _hub(home)
    _append(home, wg.meta.id, "@scout #task #intake go", cost={"usd": 1.00, "tokens": 100})
    # No #done: this opener preempts intake, and it is the ad-hoc task's own post.
    _append(home, wg.meta.id, "@scout #task #sidequest look into it",
            cost={"usd": 10.00, "tokens": 1000})
    _append(home, wg.meta.id, "#done sidequest nothing there")
    _append(home, wg.meta.id, "@quill #task #content write", cost={"usd": 2.00, "tokens": 200})

    run = _run(home, wg.meta.id)
    assert run["cost"]["usd"] == pytest.approx(3.00)
    costs = _costs(run)
    assert costs["intake"]["usd"] == pytest.approx(1.00)
    assert costs["content"]["usd"] == pytest.approx(2.00)
