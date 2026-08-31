from __future__ import annotations

import json
import multiprocessing as mp
import threading
from pathlib import Path

import pytest

from alpi.alp import subscription as sub_mod
from alpi.alp import workgroup as wg_mod
from alpi.alp.keys import load_or_generate


def _sub(wg_id: str, name: str = "site") -> sub_mod.Subscription:
    return sub_mod.Subscription(
        wg_id=wg_id, name=name, hub_id="mira", hub_pubkey="HUB",
    )


def test_stale_writeback_cannot_resurrect_a_tombstoned_id(tmp_path: Path) -> None:
    home = tmp_path / "quill"
    sub_mod.save(home, [_sub("wg_dead"), _sub("wg_live", "other")])

    snapshot = sub_mod.load(home)
    assert {s.wg_id for s in snapshot} == {"wg_dead", "wg_live"}

    sub_mod.tombstone(home, "wg_dead")
    sub_mod.remove(home, "wg_dead")

    sub_mod.save(home, snapshot)

    assert sub_mod.get(home, "wg_dead") is None
    assert sub_mod.get(home, "wg_live") is not None
    assert "wg_dead" not in sub_mod.path(home).read_text()


def test_load_hides_a_tombstoned_id_even_before_the_next_save(tmp_path: Path) -> None:
    home = tmp_path / "muse"
    sub_mod.save(home, [_sub("wg_dead")])
    sub_mod.tombstone(home, "wg_dead")
    assert sub_mod.load(home) == []


def test_upsert_of_a_tombstoned_id_is_dropped(tmp_path: Path) -> None:
    home = tmp_path / "lens"
    sub_mod.tombstone(home, "wg_dead")
    sub_mod.upsert(home, _sub("wg_dead"))
    assert sub_mod.get(home, "wg_dead") is None


def test_revive_lifts_the_tombstone_for_a_deliberate_rejoin(tmp_path: Path) -> None:
    home = tmp_path / "scout"
    sub_mod.tombstone(home, "wg_back")
    sub_mod.revive(home, "wg_back")
    sub_mod.upsert(home, _sub("wg_back"))
    assert sub_mod.get(home, "wg_back") is not None


def test_tombstones_are_never_evicted(tmp_path: Path) -> None:
    home = tmp_path / "pixel"
    for i in range(500):
        sub_mod.tombstone(home, f"wg_{i:04d}")
    ids = sub_mod.tombstones(home)
    assert len(ids) == 500
    assert "wg_0000" in ids and "wg_0499" in ids


def test_tombstones_reuse_directory_snapshot_until_it_changes(
    tmp_path: Path, monkeypatch,
) -> None:
    home = tmp_path / "profile"
    sub_mod.tombstone(home, "wg_a")
    real_listdir = sub_mod.os.listdir
    calls = 0

    def counted_listdir(path):
        nonlocal calls
        calls += 1
        return real_listdir(path)

    monkeypatch.setattr(sub_mod.os, "listdir", counted_listdir)

    assert sub_mod.tombstones(home) == {"wg_a"}
    assert sub_mod.tombstones(home) == {"wg_a"}
    assert calls == 1

    sub_mod.tombstone(home, "wg_b")
    assert sub_mod.tombstones(home) == {"wg_a", "wg_b"}
    assert calls == 2


def test_concurrent_tombstones_all_survive(tmp_path: Path) -> None:
    home = tmp_path / "quill"
    errors: list[Exception] = []

    def mark(prefix: str) -> None:
        try:
            for i in range(50):
                sub_mod.tombstone(home, f"wg_{prefix}{i:03d}")
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    threads = [threading.Thread(target=mark, args=(p,)) for p in ("a", "b", "c", "d")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    assert len(sub_mod.tombstones(home)) == 200


def test_concurrent_tombstone_and_revive_touch_only_their_ids(tmp_path: Path) -> None:
    home = tmp_path / "lens"
    sub_mod.tombstone(home, "wg_keep")

    def marker() -> None:
        for i in range(80):
            sub_mod.tombstone(home, f"wg_m{i:03d}")

    def reviver() -> None:
        for i in range(80):
            sub_mod.tombstone(home, f"wg_r{i:03d}")
            sub_mod.revive(home, f"wg_r{i:03d}")

    threads = [threading.Thread(target=marker), threading.Thread(target=reviver)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    ids = sub_mod.tombstones(home)
    assert "wg_keep" in ids
    assert {i for i in ids if i.startswith("wg_m")} == {f"wg_m{i:03d}" for i in range(80)}
    assert not {i for i in ids if i.startswith("wg_r")}


def _mp_writeback_worker(home_str: str, barrier) -> None:
    home = Path(home_str)
    snapshot = [_sub("wg_dead"), _sub("wg_live", "other")]
    barrier.wait()
    for _ in range(200):
        sub_mod.save(home, snapshot)


def _mp_upsert_worker(home_str: str, index: int, barrier) -> None:
    barrier.wait()
    sub_mod.upsert(Path(home_str), _sub(f"wg_{index:02d}", f"site-{index}"))


def _mp_compact_worker(home_str: str, barrier) -> None:
    barrier.wait()
    for _ in range(50):
        sub_mod.compact(Path(home_str))


def test_multiprocess_upserts_do_not_lose_subscriptions(tmp_path: Path) -> None:
    home = tmp_path / "scout"
    count = 16
    ctx = mp.get_context("spawn")
    barrier = ctx.Barrier(count)
    procs = [
        ctx.Process(target=_mp_upsert_worker, args=(str(home), i, barrier))
        for i in range(count)
    ]
    for proc in procs:
        proc.start()
    for proc in procs:
        proc.join(timeout=120)
        assert proc.exitcode == 0

    assert {sub.wg_id for sub in sub_mod.load(home)} == {
        f"wg_{i:02d}" for i in range(count)
    }


def test_compaction_does_not_erase_concurrent_upserts(tmp_path: Path) -> None:
    home = tmp_path / "scout"
    sub_mod.upsert(home, _sub("wg_existing"))
    count = 12
    ctx = mp.get_context("spawn")
    barrier = ctx.Barrier(count + 1)
    procs = [
        ctx.Process(target=_mp_upsert_worker, args=(str(home), i, barrier))
        for i in range(count)
    ]
    procs.append(ctx.Process(target=_mp_compact_worker, args=(str(home), barrier)))
    for proc in procs:
        proc.start()
    for proc in procs:
        proc.join(timeout=120)
        assert proc.exitcode == 0

    assert {sub.wg_id for sub in sub_mod.load(home)} == {
        "wg_existing", *(f"wg_{i:02d}" for i in range(count)),
    }


def test_multiprocess_writeback_cannot_resurrect_a_tombstoned_id(tmp_path: Path) -> None:
    home = tmp_path / "quill"
    sub_mod.save(home, [_sub("wg_dead"), _sub("wg_live", "other")])

    ctx = mp.get_context("spawn")
    barrier = ctx.Barrier(2)
    proc = ctx.Process(target=_mp_writeback_worker, args=(str(home), barrier))
    proc.start()
    barrier.wait()
    sub_mod.tombstone(home, "wg_dead")
    sub_mod.remove(home, "wg_dead")
    proc.join(timeout=120)
    assert proc.exitcode == 0

    assert sub_mod.get(home, "wg_dead") is None
    assert sub_mod.get(home, "wg_live") is not None
    assert "wg_dead" in sub_mod.tombstones(home)
    sub_mod.save(home, sub_mod.load(home))
    assert "wg_dead" not in sub_mod.path(home).read_text()


def test_purge_tombstones_every_profile(tmp_path: Path, monkeypatch) -> None:
    from alpi import home as home_mod

    root = tmp_path / "root"
    monkeypatch.setattr(home_mod, "_ROOT", root)
    quill = root / "profiles" / "quill"
    muse = root / "profiles" / "muse"
    sub_mod.save(quill, [_sub("wg_gone")])
    sub_mod.save(muse, [_sub("wg_gone")])

    stale_quill = sub_mod.load(quill)
    purged = wg_mod._purge_after_delete(root / "profiles" / "mira", "wg_gone")
    assert set(purged) == {"quill", "muse"}

    sub_mod.save(quill, stale_quill)
    assert sub_mod.get(quill, "wg_gone") is None
    assert sub_mod.get(muse, "wg_gone") is None
    # A profile that never subscribed is protected too: the write-back may come later.
    assert "wg_gone" in sub_mod.tombstones(muse)


def test_append_with_seq_never_mints_a_duplicate(tmp_path: Path) -> None:
    d = tmp_path / "wgdir"
    errors: list[Exception] = []

    def writer(n: int) -> None:
        try:
            for _ in range(25):
                wg_mod.append_with_seq(d, {"seq": 0, "ts": "t", "from": f"W{n}"})
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    threads = [threading.Thread(target=writer, args=(i,)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
    seqs = [
        json.loads(line)["seq"]
        for line in (d / "transcript.jsonl").read_text().splitlines()
        if line.strip()
    ]
    assert sorted(seqs) == list(range(1, 101))
    assert len(set(seqs)) == 100


def _meta(budget: dict | None = None) -> wg_mod.Meta:
    return wg_mod.Meta(
        id="wg_ledger", name="site", hub_pubkey="HUB",
        created_at="2026-08-01T00:00:00Z", budget=budget or {},
    )


def test_concurrent_admissions_keep_seqs_and_ledger_exact(tmp_path: Path) -> None:
    d = tmp_path / "wgdir"
    meta = _meta()
    errors: list[Exception] = []

    def writer(who: str) -> None:
        try:
            for i in range(25):
                entry = {"seq": 0, "ts": "t", "from": who,
                         "key_version": 1, "nonce": f"{who}-{i}", "ciphertext": "c"}
                wg_mod.admit_post(
                    d, meta, entry, 0.01, 100,
                    enforce_cap=who.startswith("mem"),
                    reject_nonce_reuse=who.startswith("mem"),
                )
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    threads = [threading.Thread(target=writer, args=(w,))
               for w in ("hub", "mem1", "hub2", "mem2")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
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


def test_concurrent_admissions_cannot_overshoot_the_budget_cap(tmp_path: Path) -> None:
    d = tmp_path / "wgdir"
    meta = _meta({"max_usd": 0.10})
    admitted, rejected = [], []
    lock = threading.Lock()

    def writer(who: str) -> None:
        for i in range(10):
            entry = {"seq": 0, "ts": "t", "from": who,
                     "key_version": 1, "nonce": f"{who}{i}", "ciphertext": "c"}
            try:
                wg_mod.admit_post(d, meta, entry, 0.01, 0)
                with lock:
                    admitted.append(who)
            except Exception:  # noqa: BLE001
                with lock:
                    rejected.append(who)

    threads = [threading.Thread(target=writer, args=(w,)) for w in ("a", "b", "c")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    ledger = wg_mod._load_ledger(d)
    assert ledger["usd"] <= 0.10 + 1e-9
    assert ledger["posts"] == len(admitted)
    assert len(admitted) == 10 and len(rejected) == 20


def test_admit_post_truncates_the_append_when_the_ledger_write_fails(
    tmp_path: Path, monkeypatch,
) -> None:
    d = tmp_path / "wgdir"
    meta = _meta()
    for i in range(2):
        wg_mod.admit_post(
            d, meta,
            {"seq": 0, "ts": "t", "from": "M", "key_version": 1,
             "nonce": f"N{i}", "ciphertext": "c"},
            0.01, 100,
        )
    transcript_before = (d / "transcript.jsonl").read_bytes()
    ledger_before = (d / "ledger.json").read_bytes()

    def boom(*a, **kw):
        raise OSError("simulated ledger write failure")

    with pytest.MonkeyPatch.context() as mp_ctx:
        mp_ctx.setattr("alpi.alp.workgroup._save_ledger", boom)
        with pytest.raises(OSError, match="simulated ledger write failure"):
            wg_mod.admit_post(
                d, meta,
                {"seq": 0, "ts": "t", "from": "M", "key_version": 1,
                 "nonce": "N9", "ciphertext": "c"},
                0.01, 100,
            )

    assert (d / "transcript.jsonl").read_bytes() == transcript_before
    assert (d / "ledger.json").read_bytes() == ledger_before

    out = wg_mod.admit_post(
        d, meta,
        {"seq": 0, "ts": "t", "from": "M", "key_version": 1,
         "nonce": "N9", "ciphertext": "c"},
        0.01, 100,
    )
    assert out["seq"] == 3
    assert wg_mod._load_ledger(d)["posts"] == 3


def test_save_ledger_preserves_the_original_when_replace_fails(
    tmp_path: Path, monkeypatch,
) -> None:
    import os

    d = tmp_path / "wgdir"
    wg_mod._save_ledger(d, {"usd": 1.0, "tokens": 2, "posts": 3})
    original = (d / "ledger.json").read_bytes()

    def boom(*a, **kw):
        raise OSError("simulated rename failure")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError):
        wg_mod._save_ledger(d, {"usd": 9.0, "tokens": 9, "posts": 9})
    assert (d / "ledger.json").read_bytes() == original
    leftovers = [p for p in d.glob(".ledger.json.*") if p.is_file()]
    assert not leftovers


def test_admit_post_rejects_nonce_reuse_and_cap(tmp_path: Path) -> None:
    d = tmp_path / "wgdir"
    meta = _meta()
    first = {"seq": 0, "ts": "t", "from": "M", "key_version": 1,
             "nonce": "N1", "ciphertext": "c"}
    wg_mod.admit_post(d, meta, dict(first), reject_nonce_reuse=True)
    with pytest.raises(Exception, match="invalid-params"):
        wg_mod.admit_post(d, meta, dict(first), reject_nonce_reuse=True)

    monkey_cap = wg_mod._MAX_TRANSCRIPT_POSTS
    try:
        wg_mod._MAX_TRANSCRIPT_POSTS = 1
        with pytest.raises(Exception, match="workgroup-full"):
            wg_mod.admit_post(
                d, meta,
                {"seq": 0, "ts": "t", "from": "M", "key_version": 1,
                 "nonce": "N2", "ciphertext": "c"},
                enforce_cap=True,
            )
    finally:
        wg_mod._MAX_TRANSCRIPT_POSTS = monkey_cap
