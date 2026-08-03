"""A phase owned by the hub profile itself — the web factory's `review` chain — is worked by the hub."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest

from alpi.alp import workgroup as wg_mod
from alpi.alp import workgroup_client as wc
from alpi.alp.keys import load_or_generate
from alpi.alp.peers import Peer
from alpi.host import workgroup as host_wg


@pytest.fixture
def short_tmp() -> Path:
    d = Path(tempfile.mkdtemp(prefix="alp-hubphase-", dir="/tmp"))
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


def _factory(short_tmp: Path, monkeypatch):
    from alpi import home as home_mod
    from alpi.alp import peers as peers_mod

    root = short_tmp / "root"
    home = root / "profiles" / "mira"
    home.mkdir(parents=True)
    monkeypatch.setattr(home_mod, "_ROOT", root)
    kp = load_or_generate(home)

    scout_home = root / "profiles" / "scout"
    scout_home.mkdir(parents=True)
    scout_pk = load_or_generate(scout_home).pubkey_b64()
    peers_mod.add(home, Peer(id="scout", pubkey=scout_pk, allow=["workgroup.post"]))

    wg = wg_mod.create(
        home, name="site", hub_kp=kp, member_pubkeys=[scout_pk],
        pipelines={"review": ["review", "review-config"]},
        launch_pipeline=None,
        pipeline_steps={
            "review": {"owner": "mira", "task": "materialize and triage the order"},
            "review-config": {"owner": "scout", "task": "apply the config notes"},
        },
    )
    return home, wg


@pytest.mark.asyncio
async def test_hub_can_work_and_close_a_phase_it_owns(short_tmp: Path, monkeypatch) -> None:
    home, wg = _factory(short_tmp, monkeypatch)
    await wc.trigger_pipeline(home, wg.meta.id, "review")
    await wc.post(home, wg.meta.id, b"REV-1-01 -> review-config; REV-1-02 -> template-gap")
    await wc.post(home, wg.meta.id, b"#done review triaged - 2 notes")

    bodies = [p["body"] for p in host_wg.decrypt_transcript(home, wg.meta.id)]
    assert bodies == [
        "@mira #task #review · materialize and triage the order",
        "REV-1-01 -> review-config; REV-1-02 -> template-gap",
        "#done review triaged - 2 notes",
    ]
    run = host_wg.fold_task_state(home, wg.meta.id)["pipeline_run"]
    assert run["status"] == "between"
    assert run["phases"][0]["state"] == "completed"


@pytest.mark.asyncio
async def test_hub_still_cannot_close_a_phase_it_owns_with_no_delivery(
    short_tmp: Path, monkeypatch,
) -> None:
    home, wg = _factory(short_tmp, monkeypatch)
    await wc.trigger_pipeline(home, wg.meta.id, "review")
    with pytest.raises(ValueError, match="phase-owner-missing"):
        await wc.post(home, wg.meta.id, b"#done review triaged")


@pytest.mark.asyncio
async def test_a_member_owned_phase_keeps_the_rotation_rule(
    short_tmp: Path, monkeypatch,
) -> None:
    home, wg = _factory(short_tmp, monkeypatch)
    await wc.trigger_pipeline(home, wg.meta.id, "review")
    await wc.post(home, wg.meta.id, b"triage: REV-1-01 -> review-config")
    await wc.post(home, wg.meta.id, b"#done review triaged")
    with pytest.raises(ValueError, match="turn-rotation"):
        await wc.post(home, wg.meta.id, b"and one more thought")


@pytest.mark.asyncio
async def test_starting_a_chain_stops_the_one_in_flight(short_tmp: Path, monkeypatch) -> None:
    home, wg = _factory(short_tmp, monkeypatch)
    await wc.trigger_pipeline(home, wg.meta.id, "review")
    await wc.post(home, wg.meta.id, b"triage: REV-1-01 -> review-config")
    await wc.post(home, wg.meta.id, b"#done review triaged")

    between = host_wg.fold_task_state(home, wg.meta.id)["pipeline_run"]
    assert between["status"] == "between"

    out = await wc.trigger_pipeline(home, wg.meta.id, "review")
    assert out["stopped"] == {
        "pipeline": "review", "phase": "review", "status": "between",
        "open_task": None, "same_pipeline": True,
    }
    run = host_wg.fold_task_state(home, wg.meta.id)["pipeline_run"]
    assert run["pipeline"] == "review" and run["status"] == "running"
    assert run["phases"][0]["state"] == "current"
