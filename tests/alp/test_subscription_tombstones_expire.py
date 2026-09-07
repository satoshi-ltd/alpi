"""Tombstones expire: a marker older than TOMBSTONES_KEEP_DAYS whose id nothing local references is pruned on the next write or by cleanup."""

from __future__ import annotations

import os
import time
from pathlib import Path

from alpi.alp import subscription as sub_mod

HUB_PK = "H" * 44
DAY = 86_400


def _sub(wg_id: str) -> sub_mod.Subscription:
    sub = sub_mod.Subscription(
        wg_id=wg_id, name="site", hub_id="hub", hub_pubkey=HUB_PK, last_seq=1,
    )
    sub.upsert_key(1, "SEALED_V1")
    return sub


def _marker(home: Path, wg_id: str, age_days: float) -> Path:
    d = sub_mod._tombstones_dir(home)
    d.mkdir(parents=True, exist_ok=True)
    p = d / wg_id
    p.touch()
    old = time.time() - age_days * DAY
    os.utime(p, (old, old))
    return p


def test_only_old_unreferenced_markers_expire(tmp_path: Path) -> None:
    home = tmp_path / "member"
    keep = sub_mod.TOMBSTONES_KEEP_DAYS
    _marker(home, "wg_fresh", keep - 0.5)
    old = _marker(home, "wg_old", keep + 1)
    _marker(home, "wg_hubside", keep + 1)
    (home / "alp" / "workgroups" / "wg_hubside").mkdir(parents=True)

    assert sub_mod.expired_tombstones(home) == [old]


def test_marker_hiding_a_file_entry_survives_until_compact(tmp_path: Path) -> None:
    home = tmp_path / "member"
    sub_mod.save(home, [_sub("wg_a"), _sub("wg_b")])
    _marker(home, "wg_a", sub_mod.TOMBSTONES_KEEP_DAYS + 1)
    assert sub_mod.get(home, "wg_a") is None

    assert sub_mod.expired_tombstones(home) == []

    sub_mod.compact(home)
    assert [p.name for p in sub_mod.expired_tombstones(home)] == ["wg_a"]
    assert sub_mod.prune_tombstones(home) == 1
    assert sub_mod.tombstones(home) == set()
    assert [s.wg_id for s in sub_mod.load(home)] == ["wg_b"]


def test_writing_a_tombstone_prunes_the_expired_ones(tmp_path: Path) -> None:
    home = tmp_path / "member"
    _marker(home, "wg_old", sub_mod.TOMBSTONES_KEEP_DAYS + 3)
    _marker(home, "wg_fresh", 0)

    sub_mod.tombstone(home, "wg_new")

    assert sub_mod.tombstones(home) == {"wg_fresh", "wg_new"}


def test_prune_honours_the_clock_it_is_given(tmp_path: Path) -> None:
    home = tmp_path / "member"
    _marker(home, "wg_x", 1)

    assert sub_mod.prune_tombstones(home, now=time.time()) == 0
    assert sub_mod.prune_tombstones(home, now=time.time() + 5 * DAY) == 1
    assert sub_mod.expired_tombstones(home) == []


def test_unverifiable_references_keep_every_marker(tmp_path: Path) -> None:
    home = tmp_path / "member"
    old = _marker(home, "wg_old", sub_mod.TOMBSTONES_KEEP_DAYS + 5)
    sub_mod.path(home).parent.mkdir(parents=True, exist_ok=True)

    sub_mod.path(home).write_text("wg_id: [unclosed\n")
    assert sub_mod.expired_tombstones(home) == []
    assert sub_mod.prune_tombstones(home) == 0

    sub_mod.path(home).write_text("wg_id: wg_old\n")
    assert sub_mod.expired_tombstones(home) == []

    sub_mod.path(home).write_text("")
    (home / "alp" / "workgroups").write_text("not a directory")
    assert sub_mod.expired_tombstones(home) == []

    (home / "alp" / "workgroups").unlink()
    assert sub_mod.expired_tombstones(home) == [old]
    assert sub_mod.prune_tombstones(home) == 1


def test_malformed_entries_and_undecodable_bytes_keep_every_marker(tmp_path: Path) -> None:
    home = tmp_path / "member"
    old = _marker(home, "wg_old", sub_mod.TOMBSTONES_KEEP_DAYS + 5)
    p = sub_mod.path(home)
    p.parent.mkdir(parents=True, exist_ok=True)

    for text in ("- wg_id: [wg_old]\n", "- wg_old\n", "- wg_id: 'wg old!'\n", "- name: site\n"):
        p.write_text(text)
        assert sub_mod.expired_tombstones(home) == [], text

    p.write_bytes(b"\xff\xfe\x00")
    assert sub_mod.expired_tombstones(home) == []
    assert sub_mod.prune_tombstones(home) == 0

    p.write_text("- wg_id: wg_other\n")
    assert sub_mod.expired_tombstones(home) == [old]
