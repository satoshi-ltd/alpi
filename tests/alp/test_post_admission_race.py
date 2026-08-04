from __future__ import annotations

import asyncio
import json
import multiprocessing as mp
from pathlib import Path

import pytest

from alpi.alp import workgroup as wg_mod


def _meta(wg_id: str = "wg_mp") -> wg_mod.Meta:
    return wg_mod.Meta(
        id=wg_id, name="site", hub_pubkey="HUB",
        created_at="2026-08-01T00:00:00Z",
    )


def _mp_admit_worker(d_str: str, who: str, barrier) -> None:
    meta = _meta()
    barrier.wait()
    for i in range(25):
        entry = {"seq": 0, "ts": "t", "from": who,
                 "key_version": 1, "nonce": f"{who}-{i}", "ciphertext": "c"}
        wg_mod.admit_post(
            Path(d_str), meta, entry, 0.01, 100,
            enforce_cap=who.startswith("mem"),
            reject_nonce_reuse=who.startswith("mem"),
        )


def test_multiprocess_admissions_keep_totals_exact(tmp_path: Path) -> None:
    d = tmp_path / "wgdir"
    ctx = mp.get_context("spawn")
    barrier = ctx.Barrier(4)
    procs = [
        ctx.Process(target=_mp_admit_worker, args=(str(d), who, barrier))
        for who in ("hub", "mem1", "hub2", "mem2")
    ]
    for p in procs:
        p.start()
    for p in procs:
        p.join(timeout=120)
    for p in procs:
        assert p.exitcode == 0, f"worker pid={p.pid} exitcode={p.exitcode}"

    seqs = [
        json.loads(line)["seq"]
        for line in (d / "transcript.jsonl").read_text().splitlines()
        if line.strip()
    ]
    assert sorted(seqs) == list(range(1, 101))
    ledger = wg_mod._load_ledger(d)
    assert ledger["posts"] == 100
    assert ledger["usd"] == pytest.approx(1.00)
    assert ledger["tokens"] == 10_000


def _mp_hub_post_worker(home_str: str, wg_id: str, body: str, barrier, q) -> None:
    from alpi.alp import workgroup_client as wc

    barrier.wait()
    try:
        out = asyncio.run(wc.post(Path(home_str), wg_id, body.encode()))
        q.put(("ok", int(out["seq"])))
    except ValueError as e:
        q.put(("err", str(e)))


def test_incompatible_hub_posts_only_one_survives(tmp_path: Path) -> None:
    from alpi.alp.keys import load_or_generate

    home = tmp_path / "profiles" / "mira"
    home.mkdir(parents=True)
    kp = load_or_generate(home)
    member_home = tmp_path / "profiles" / "scout"
    member_home.mkdir(parents=True)
    member_pk = load_or_generate(member_home).pubkey_b64()
    wg = wg_mod.create(home, name="site", hub_kp=kp, member_pubkeys=[member_pk])

    ctx = mp.get_context("spawn")
    barrier = ctx.Barrier(2)
    q = ctx.Queue()
    procs = [
        ctx.Process(
            target=_mp_hub_post_worker,
            args=(str(home), wg.meta.id, body, barrier, q),
        )
        for body in ("first concurrent hub note", "second concurrent hub note")
    ]
    for p in procs:
        p.start()
    outcomes = [q.get(timeout=120) for _ in procs]
    for p in procs:
        p.join(timeout=120)
        assert p.exitcode == 0

    kinds = sorted(kind for kind, _ in outcomes)
    assert kinds == ["err", "ok"], f"exactly one must land, got {outcomes}"
    rejected = next(detail for kind, detail in outcomes if kind == "err")
    assert "turn-rotation" in rejected

    d = home / "alp" / "workgroups" / wg.meta.id
    lines = [
        line for line in (d / "transcript.jsonl").read_text().splitlines()
        if line.strip()
    ]
    assert len(lines) == 1
    assert wg_mod._load_ledger(d)["posts"] == 1
