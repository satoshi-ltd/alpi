from pathlib import Path

import pytest

from alpi import memory


@pytest.fixture
def store(tmp_home_no_env: Path) -> memory.MemoryStore:
    (tmp_home_no_env / "memories").mkdir(exist_ok=True)
    s = memory.MemoryStore(home=tmp_home_no_env)
    s.seed_defaults()
    return s


def test_seed_creates_empty_files(store: memory.MemoryStore) -> None:
    assert store.user_path.read_text() == ""
    assert store.memory_path.read_text() == ""


def test_add_basic(store: memory.MemoryStore) -> None:
    store.add("USER.md", "Javi vive en Hua Hin.")
    assert "Hua Hin" in store.user_path.read_text()


def test_add_reinforces_exact_duplicate(store: memory.MemoryStore) -> None:
    assert store.add("USER.md", "Javi tiene 44 años") == "added"
    assert store.add("USER.md", "Javi tiene 44 años") == "reinforced"
    # Only one visible entry; reinforcement bumped the counter, not the body.
    snap = store.snapshot()
    assert snap["USER.md"].count("Javi tiene 44 años") == 1


def test_add_reinforces_case_insensitive_duplicate(store: memory.MemoryStore) -> None:
    assert store.add("USER.md", "Javi vive en Hua Hin") == "added"
    assert store.add("USER.md", "JAVI VIVE EN HUA HIN") == "reinforced"


def test_add_reinforces_trailing_punctuation_variant(store: memory.MemoryStore) -> None:
    assert store.add("USER.md", "Javi vive en Hua Hin") == "added"
    assert store.add("USER.md", "Javi vive en Hua Hin.") == "reinforced"


def test_add_strips_headers_and_template(store: memory.MemoryStore) -> None:
    store.add("USER.md", "# header\n(alpi will fill...)\nReal fact.")
    text = store.user_path.read_text()
    assert "# header" not in text
    assert "alpi will fill" not in text
    assert "Real fact" in text


def test_add_rejects_over_limit(store: memory.MemoryStore) -> None:
    with pytest.raises(ValueError):
        store.add("USER.md", "x" * (memory.USER_CHAR_LIMIT + 1))


def test_snapshot_returns_both_files(store: memory.MemoryStore) -> None:
    snap = store.snapshot()
    assert set(snap.keys()) == {"USER.md", "MEMORY.md"}


def test_usage_reports_pct(store: memory.MemoryStore) -> None:
    store.add("USER.md", "x" * 100)
    used, limit = store.usage()["USER.md"]
    assert used > 0 and limit == memory.USER_CHAR_LIMIT


def test_add_writes_meta_marker(store: memory.MemoryStore) -> None:
    store.add("USER.md", "Javi prefers concise answers", confidence="low")
    raw = store.user_path.read_text()
    assert "alpi-meta" in raw
    assert "conf=low" in raw
    assert "reinforced=0" in raw


def test_snapshot_strips_meta(store: memory.MemoryStore) -> None:
    store.add("USER.md", "Javi prefers concise answers", confidence="low")
    snap = store.snapshot()
    assert "alpi-meta" not in snap["USER.md"]
    assert "Javi prefers concise answers" in snap["USER.md"]


def test_reinforcement_bumps_counter(store: memory.MemoryStore) -> None:
    store.add("USER.md", "Javi works with Python", confidence="low")
    store.add("USER.md", "Javi works with Python")
    raw = store.user_path.read_text()
    assert "reinforced=1" in raw


def test_reinforcement_upgrades_low_to_normal(store: memory.MemoryStore) -> None:
    store.add("USER.md", "Javi works with Python", confidence="low")
    store.add("USER.md", "Javi works with Python")
    store.add("USER.md", "Javi works with Python")
    raw = store.user_path.read_text()
    assert "conf=normal" in raw
    assert "reinforced=2" in raw


def test_add_rejects_invalid_confidence(store: memory.MemoryStore) -> None:
    with pytest.raises(ValueError):
        store.add("USER.md", "fact", confidence="medium")


def _utc_today():
    """memory._today() uses UTC; tests must match or the str-replace silently no-ops at UTC-day boundaries."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).date()


def test_prune_drops_old_low_confidence(store: memory.MemoryStore) -> None:
    from datetime import timedelta

    store.add("USER.md", "ephemeral fact", confidence="low")
    raw = store.user_path.read_text()
    old_date = (_utc_today() - timedelta(days=45)).isoformat()
    store.user_path.write_text(raw.replace("captured=" + _utc_today().isoformat(),
                                            f"captured={old_date}"))
    removed = store.prune_low_confidence(max_age_days=30)
    assert removed == 1
    assert "ephemeral fact" not in store.user_path.read_text()


def test_prune_keeps_reinforced_low_confidence(store: memory.MemoryStore) -> None:
    from datetime import timedelta

    store.add("USER.md", "durable fact", confidence="low")
    store.add("USER.md", "durable fact")
    raw = store.user_path.read_text()
    old_date = (_utc_today() - timedelta(days=45)).isoformat()
    store.user_path.write_text(raw.replace("captured=" + _utc_today().isoformat(),
                                            f"captured={old_date}"))
    removed = store.prune_low_confidence(max_age_days=30)
    assert removed == 0
    assert "durable fact" in store.user_path.read_text()


def test_prune_keeps_normal_and_high(store: memory.MemoryStore) -> None:
    from datetime import timedelta

    store.add("USER.md", "normal fact", confidence="normal")
    store.add("USER.md", "core fact", confidence="high")
    raw = store.user_path.read_text()
    old_date = (_utc_today() - timedelta(days=365)).isoformat()
    store.user_path.write_text(raw.replace("captured=" + _utc_today().isoformat(),
                                            f"captured={old_date}"))
    removed = store.prune_low_confidence(max_age_days=30)
    assert removed == 0
    assert "normal fact" in store.user_path.read_text()
    assert "core fact" in store.user_path.read_text()


def test_prune_skips_legacy_entries_without_meta(store: memory.MemoryStore) -> None:
    # Legacy file (written before this feature) has no alpi-meta comments.
    store.user_path.write_text("legacy fact written long ago\n")
    removed = store.prune_low_confidence(max_age_days=30)
    assert removed == 0
    assert "legacy fact" in store.user_path.read_text()


def test_prune_disabled_when_max_age_zero(store: memory.MemoryStore) -> None:
    store.add("USER.md", "fact", confidence="low")
    assert store.prune_low_confidence(max_age_days=0) == 0
