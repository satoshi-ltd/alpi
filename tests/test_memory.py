from pathlib import Path

import pytest

from alf import memory


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


def test_add_rejects_exact_duplicate(store: memory.MemoryStore) -> None:
    store.add("USER.md", "Javi tiene 44 años")
    with pytest.raises(ValueError):
        store.add("USER.md", "Javi tiene 44 años")


def test_add_rejects_case_insensitive_duplicate(store: memory.MemoryStore) -> None:
    store.add("USER.md", "Javi vive en Hua Hin")
    with pytest.raises(ValueError):
        store.add("USER.md", "JAVI VIVE EN HUA HIN")


def test_add_rejects_trailing_punctuation_variant(store: memory.MemoryStore) -> None:
    store.add("USER.md", "Javi vive en Hua Hin")
    with pytest.raises(ValueError):
        store.add("USER.md", "Javi vive en Hua Hin.")


def test_add_strips_headers_and_template(store: memory.MemoryStore) -> None:
    store.add("USER.md", "# header\n(alf will fill...)\nReal fact.")
    text = store.user_path.read_text()
    assert "# header" not in text
    assert "alf will fill" not in text
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
