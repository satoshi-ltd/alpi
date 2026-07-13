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


def test_usage_includes_agent_with_advisory_limit(store: memory.MemoryStore) -> None:
    store.agent_path.write_text("I am a helpful assistant.")
    usage = store.usage()
    assert set(usage) == {"AGENT.md", "USER.md", "MEMORY.md"}
    used, limit = usage["AGENT.md"]
    assert limit == memory.AGENT_CHAR_LIMIT
    assert used == len("I am a helpful assistant.")


def test_replace_writes_and_bumps_revision(store: memory.MemoryStore) -> None:
    rev0 = store.revision("AGENT.md")
    rev1 = store.replace("AGENT.md", "I am helpful.")
    assert store.read_with_rev("AGENT.md")[0] == "I am helpful."
    assert rev1 != rev0 and rev1 == store.revision("AGENT.md")


def test_replace_rejects_stale_revision(store: memory.MemoryStore) -> None:
    store.replace("USER.md", "first")
    stale = store.revision("USER.md")
    store.replace("USER.md", "second")
    with pytest.raises(memory.MemoryConflict):
        store.replace("USER.md", "third", expected_rev=stale)
    assert store.read_with_rev("USER.md")[0] == "second"


def test_replace_enforces_user_memory_caps_but_not_agent(store: memory.MemoryStore) -> None:
    with pytest.raises(ValueError):
        store.replace("USER.md", "x" * (memory.USER_CHAR_LIMIT + 1))
    store.replace("AGENT.md", "y" * (memory.AGENT_CHAR_LIMIT + 500))
    assert len(store.read_with_rev("AGENT.md")[0]) == memory.AGENT_CHAR_LIMIT + 500


def test_replace_refuses_symlink(tmp_path, store: memory.MemoryStore) -> None:
    import os
    target = tmp_path / "outside.txt"
    target.write_text("secret")
    store.agent_path.unlink(missing_ok=True)
    os.symlink(target, store.agent_path)
    with pytest.raises(ValueError):
        store.replace("AGENT.md", "hijack")
    assert target.read_text() == "secret"


def test_symlinked_file_is_never_read_or_written(tmp_path, store: memory.MemoryStore) -> None:
    import os
    outside = tmp_path / "outside.txt"
    outside.write_text("SECRET")
    store.user_path.unlink(missing_ok=True)
    os.symlink(outside, store.user_path)

    assert store.snapshot()["USER.md"] == ""
    assert store.usage()["USER.md"][0] == 0
    with pytest.raises(ValueError):
        store.add("USER.md", "hi")
    store.prune_low_confidence(max_age_days=30)
    assert outside.read_text() == "SECRET"


def test_seed_defaults_skips_symlinked_leaf(tmp_path) -> None:
    import os
    home = tmp_path / "h"
    (home / "memories").mkdir(parents=True)
    outside = tmp_path / "out.md"
    outside.write_text("KEEP")
    os.symlink(outside, home / "memories" / "USER.md")
    memory.MemoryStore(home=home).seed_defaults()
    assert outside.read_text() == "KEEP"
    assert (home / "memories" / "MEMORY.md").exists()


def test_seed_defaults_skips_symlinked_dir(tmp_path) -> None:
    import os
    home = tmp_path / "h"
    home.mkdir()
    evil = tmp_path / "evil"
    evil.mkdir()
    os.symlink(evil, home / "memories")
    memory.MemoryStore(home=home).seed_defaults()
    assert list(evil.iterdir()) == []


def test_memory_lock_symlink_is_refused_without_truncating(tmp_path) -> None:
    import os
    home = tmp_path / "h"
    (home / "memories").mkdir(parents=True)
    outside = tmp_path / "keep.txt"
    outside.write_text("KEEP")
    os.symlink(outside, home / "memories" / ".memory.lock")
    with pytest.raises(OSError):
        memory.MemoryStore(home=home).read_with_rev("USER.md")
    assert outside.read_text() == "KEEP"


def test_backup_does_not_follow_symlink(tmp_path) -> None:
    import os
    home = tmp_path / "h"
    (home / "memories").mkdir(parents=True)
    store = memory.MemoryStore(home=home)
    store.replace("USER.md", "first")
    outside = tmp_path / "keep.txt"
    outside.write_text("KEEP")
    bak = home / "memories" / "USER.md.bak"
    bak.unlink(missing_ok=True)
    os.symlink(outside, bak)
    store.replace("USER.md", "second")
    assert outside.read_text() == "KEEP"
    assert store.read_with_rev("USER.md")[0] == "second"


def test_replace_rejects_unknown_file(store: memory.MemoryStore) -> None:
    with pytest.raises(ValueError):
        store.replace("SECRETS.md", "x")


def test_tool_emits_memory_changed_on_write(store: memory.MemoryStore, monkeypatch) -> None:
    import alpi.host.events as host_events
    import alpi.tools.memory as mem_tool

    events: list[tuple] = []
    monkeypatch.setattr(host_events, "emit", lambda kind, data=None: events.append((kind, data)))
    monkeypatch.setattr(mem_tool, "get_home", lambda: store.home)

    res = mem_tool.Memory().run("add", "USER.md", "Javi likes espresso")
    assert res.ok
    assert any(k == "memory_changed" for k, _ in events)


def test_agent_state_reports_advisory_pct() -> None:
    from alpi.tools.memory import _agent_state

    out = _agent_state("y" * 4000)
    assert "50% (4,000/8,000 chars)" in out


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
