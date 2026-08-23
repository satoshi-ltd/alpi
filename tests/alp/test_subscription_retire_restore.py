from __future__ import annotations

import threading
import time
from pathlib import Path

from alpi.alp import subscription as sub_mod

HUB_PK = "H" * 44


def _sub(versions: list[int]) -> sub_mod.Subscription:
    sub = sub_mod.Subscription(
        wg_id="wg_a", name="site", hub_id="hub", hub_pubkey=HUB_PK, last_seq=5,
    )
    for v in versions:
        sub.upsert_key(v, f"SEALED_V{v}")
    return sub


def _versions(sub: sub_mod.Subscription | None) -> list[int]:
    assert sub is not None
    return sorted(sk.version for sk in sub.sealed_keys)


def test_rejoining_after_a_retirement_recovers_the_archived_keys(
    tmp_path: Path,
) -> None:
    home = tmp_path / "member"
    sub_mod.save(home, [_sub([1, 2])])
    assert sub_mod.retire(home, "wg_a")
    assert sub_mod.get(home, "wg_a") is None
    assert sub_mod.retired(home) == {"wg_a"}

    sub_mod.upsert(home, _sub([3]))

    assert _versions(sub_mod.get(home, "wg_a")) == [1, 2, 3]
    assert sub_mod.retired(home) == set()


def test_a_recovered_key_still_decrypts_older_history(tmp_path: Path) -> None:
    home = tmp_path / "member"
    sub_mod.save(home, [_sub([1, 2])])
    sub_mod.retire(home, "wg_a")
    sub_mod.upsert(home, _sub([3]))
    restored = sub_mod.get(home, "wg_a")
    assert restored is not None
    assert restored.sealed_for(1) == "SEALED_V1"
    assert restored.sealed_for(2) == "SEALED_V2"


def test_the_live_key_wins_over_an_archived_one_at_the_same_version(
    tmp_path: Path,
) -> None:
    home = tmp_path / "member"
    sub_mod.save(home, [_sub([1])])
    sub_mod.retire(home, "wg_a")
    fresh = _sub([1])
    fresh.upsert_key(1, "ROTATED_V1")
    sub_mod.upsert(home, fresh)
    restored = sub_mod.get(home, "wg_a")
    assert restored is not None
    assert restored.sealed_for(1) == "ROTATED_V1"


def _archived_versions(home: Path, wg_id: str) -> list[int]:
    for entry in sub_mod._archive_entries(sub_mod.retired_path(home)):
        if str(entry.get("wg_id") or "") == wg_id:
            return sorted(
                int(k["version"]) for k in (entry.get("sealed_keys") or [])
            )
    return []


def test_the_archive_survives_a_crash_before_the_active_save_lands(
    tmp_path: Path, monkeypatch,
) -> None:
    home = tmp_path / "member"
    sub_mod.save(home, [_sub([1, 2])])
    sub_mod.retire(home, "wg_a")

    def boom(*_a, **_k):
        raise RuntimeError("crash before the active save lands")

    monkeypatch.setattr(sub_mod, "_save_unsafe", boom)
    try:
        sub_mod.upsert(home, _sub([3]))
    except RuntimeError:
        pass
    assert sub_mod.retired(home) == {"wg_a"}
    assert _archived_versions(home, "wg_a") == [1, 2]


def test_a_retire_racing_a_restore_never_loses_both_copies(
    tmp_path: Path, monkeypatch,
) -> None:
    home = tmp_path / "member"
    sub_mod.save(home, [_sub([1, 2])])
    sub_mod.retire(home, "wg_a")

    inside = threading.Event()
    real_save = sub_mod._save_unsafe

    def slow_save(h, subs):
        real_save(h, subs)
        inside.set()
        time.sleep(0.3)

    monkeypatch.setattr(sub_mod, "_save_unsafe", slow_save)
    errors: list[BaseException] = []

    def retire_mid_restore() -> None:
        inside.wait(3.0)
        try:
            sub_mod.retire(home, "wg_a")
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    racer = threading.Thread(target=retire_mid_restore)
    racer.start()
    sub_mod.upsert(home, _sub([3]))
    racer.join(10.0)
    assert not racer.is_alive()
    assert not errors

    active = sub_mod.get(home, "wg_a")
    live = _versions(active) if active is not None else []
    survived = set(live) | set(_archived_versions(home, "wg_a"))
    assert {1, 2} <= survived


def test_upsert_without_an_archive_entry_still_plainly_replaces(
    tmp_path: Path,
) -> None:
    home = tmp_path / "member"
    sub_mod.save(home, [_sub([1])])
    sub_mod.upsert(home, _sub([2]))
    assert _versions(sub_mod.get(home, "wg_a")) == [2]
    assert not sub_mod.retired_path(home).exists()
