from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from alpi import yamlfast
from alpi.alp import subscription as sub_mod


@pytest.fixture(autouse=True)
def _clear_raw_cache():
    sub_mod._raw_cache.clear()
    sub_mod._warned_skipped.clear()
    yield
    sub_mod._raw_cache.clear()
    sub_mod._warned_skipped.clear()


def _entry(wg_id: str, **extra: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "wg_id": wg_id,
        "name": f"name-{wg_id}",
        "hub_id": "hub",
        "hub_pubkey": "H" * 44,
        "last_seq": 4,
        "sealed_keys": [{"version": 1, "sealed": "SEALED"}],
        "roster": {"PK_A": "2026-08-22T10:00:00Z"},
        "roster_bios": {"PK_A": "engineer"},
        "recent_posts": [{"seq": 4, "text": "hi", "from": "H" * 44}],
    }
    row.update(extra)
    return row


def _write(home: Path, raw: list[Any]) -> None:
    p = sub_mod.path(home)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(yamlfast.safe_dump(raw, sort_keys=False, allow_unicode=True))
    sub_mod._raw_cache.clear()


def _first(home: Path, wg_id: str) -> sub_mod.Subscription | None:
    return next((s for s in sub_mod.load(home) if s.wg_id == wg_id), None)


def _assert_agrees(home: Path, wg_id: str) -> sub_mod.Subscription | None:
    got = sub_mod.get(home, wg_id)
    expected = _first(home, wg_id)
    assert got == expected
    return got


def test_get_matches_load_for_a_plain_entry(tmp_path: Path) -> None:
    home = tmp_path / "member"
    _write(home, [_entry("wg_a"), _entry("wg_b")])
    for wg_id in ("wg_a", "wg_b"):
        sub = _assert_agrees(home, wg_id)
        assert sub is not None
        assert sub.wg_id == wg_id
        assert sub.sealed_keys[0].sealed == "SEALED"
        assert sub.recent_posts == [{"seq": 4, "text": "hi", "from": "H" * 44}]


def test_get_returns_none_for_unknown_and_missing_file(tmp_path: Path) -> None:
    home = tmp_path / "member"
    assert sub_mod.get(home, "wg_a") is None
    assert sub_mod.load(home) == []
    _write(home, [_entry("wg_a")])
    assert _assert_agrees(home, "wg_missing") is None


def test_get_hides_a_tombstoned_id_exactly_like_load(tmp_path: Path) -> None:
    home = tmp_path / "member"
    _write(home, [_entry("wg_a"), _entry("wg_b")])
    sub_mod.tombstone(home, "wg_a")
    assert _assert_agrees(home, "wg_a") is None
    assert _assert_agrees(home, "wg_b") is not None
    sub_mod.revive(home, "wg_a")
    assert _assert_agrees(home, "wg_a") is not None


def test_get_skips_a_malformed_entry_exactly_like_load(tmp_path: Path) -> None:
    home = tmp_path / "member"
    _write(home, [_entry("wg_a", operations=["build"]), _entry("wg_b")])
    assert _assert_agrees(home, "wg_a") is None
    assert _assert_agrees(home, "wg_b") is not None


def test_get_skips_an_entry_missing_required_keys(tmp_path: Path) -> None:
    home = tmp_path / "member"
    no_hub = _entry("wg_a")
    no_hub.pop("hub_id")
    _write(home, [no_hub, _entry("wg_b")])
    assert _assert_agrees(home, "wg_a") is None
    assert _assert_agrees(home, "wg_b") is not None


def test_get_skips_non_dict_rows(tmp_path: Path) -> None:
    home = tmp_path / "member"
    _write(home, ["junk", None, 7, _entry("wg_a")])
    assert _assert_agrees(home, "wg_a") is not None


def test_get_returns_the_first_usable_duplicate(tmp_path: Path) -> None:
    home = tmp_path / "member"
    _write(home, [
        _entry("wg_dup", name="first", last_seq=1),
        _entry("wg_dup", name="second", last_seq=2),
    ])
    sub = _assert_agrees(home, "wg_dup")
    assert sub is not None
    assert sub.name == "first"
    assert len([s for s in sub_mod.load(home) if s.wg_id == "wg_dup"]) == 2


def test_get_skips_a_malformed_duplicate_and_takes_the_next(tmp_path: Path) -> None:
    home = tmp_path / "member"
    _write(home, [
        _entry("wg_dup", name="broken", pipeline=["a"]),
        _entry("wg_dup", name="usable"),
    ])
    sub = _assert_agrees(home, "wg_dup")
    assert sub is not None
    assert sub.name == "usable"


def test_get_builds_only_the_requested_subscription(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "member"
    _write(home, [_entry(f"wg_{i}") for i in range(40)])
    built: list[str] = []
    real = sub_mod._from_entry

    def counting(home_: Path, entry: Any, dead: set[str]):
        sub = real(home_, entry, dead)
        if sub is not None:
            built.append(sub.wg_id)
        return sub

    monkeypatch.setattr(sub_mod, "_from_entry", counting)
    assert sub_mod.get(home, "wg_39") is not None
    assert built == ["wg_39"]


def test_get_returns_detached_copies(tmp_path: Path) -> None:
    home = tmp_path / "member"
    _write(home, [_entry("wg_a")])
    first = sub_mod.get(home, "wg_a")
    assert first is not None
    first.recent_posts[0]["text"] = "mutated"
    first.roster["PK_A"] = "clobbered"
    second = sub_mod.get(home, "wg_a")
    assert second is not None
    assert second.recent_posts[0]["text"] == "hi"
    assert second.roster["PK_A"] == "2026-08-22T10:00:00Z"


def test_get_matches_load_on_a_falsy_but_real_id(tmp_path: Path) -> None:
    home = tmp_path / "member"
    entry = _entry("wg_a")
    entry["wg_id"] = 0
    _write(home, [entry])
    from_load = next((s for s in sub_mod.load(home) if s.wg_id == "0"), None)
    assert from_load is not None
    assert sub_mod.get(home, "0") == from_load
