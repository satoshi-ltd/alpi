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


DIFFERENT_FACTS = [
    ("Javi's flight to Madrid is on Friday", "Javi's flight to Bangkok is on Friday"),
    ("User prefers dark mode", "User prefers dark roast coffee"),
    ("User has 2 dogs", "User has 3 dogs"),
    ("Meeting with Ana is at 5", "Meeting with Ana is at 7"),
    ("Plan A is the default tier", "Plan B is the default tier"),
    ("Server runs on port 8080", "Server runs on port 80"),
    ("User owns cats", "User owns cat"),
    ("Ana reports to Luis", "Luis reports to Ana"),
    ("Javi lives in Madrid; his sister Ana lives in Bangkok", "Javi lives in Bangkok"),
    ("\u0e01\u0e34\u0e19 rice", "\u0e01\u0e31\u0e19 rice"),
    ("User's blood type is O+", "User's blood type is O-"),
    ("Uses C++ daily", "Uses C#"),
    ("temp 5 degrees outside", "temp -5"),
]


def _entries(store: memory.MemoryStore) -> list[str]:
    return [e.strip() for e in store.snapshot()["USER.md"].split(memory.ENTRY_DELIMITER) if e.strip()]


@pytest.mark.parametrize("first, second", DIFFERENT_FACTS)
def test_a_different_fact_is_never_taken_for_one_already_written(store: memory.MemoryStore, first: str, second: str) -> None:
    assert store.add("USER.md", first) == "added"
    outcome = store.add("USER.md", second)
    assert outcome in ("added", "similar")
    if outcome == "similar":
        assert _entries(store) == [first]
        assert store.add("USER.md", second, distinct=True) == "added"
    assert _entries(store) == [first, second]


@pytest.mark.parametrize("first, second", DIFFERENT_FACTS[:2])
def test_the_tool_names_the_entry_it_matched_and_stores_the_fact_when_told_it_differs(
    tmp_home_no_env: Path, first: str, second: str,
) -> None:
    from alpi.tools.memory import Memory
    (tmp_home_no_env / "memories").mkdir(exist_ok=True)
    user = tmp_home_no_env / "memories" / "USER.md"
    assert Memory().run(action="add", target="USER.md", content=first).ok

    refused = Memory().run(action="add", target="USER.md", content=second)

    assert refused.ok
    assert refused.output.startswith(f'NOT ADDED "{second}"')
    assert f'"{first}"' in refused.output and "distinct" in refused.output
    assert second not in user.read_text()

    stored = Memory().run(action="add", target="USER.md", content=second, distinct="True")

    assert stored.ok and stored.output.startswith("Added 1 entry")
    assert first in user.read_text() and second in user.read_text()


def test_distinct_on_a_first_attempt_changes_nothing(tmp_home_no_env: Path) -> None:
    from alpi.tools.memory import Memory
    (tmp_home_no_env / "memories").mkdir(exist_ok=True)
    user = tmp_home_no_env / "memories" / "USER.md"
    Memory().run(action="add", target="USER.md", content="User prefers concise answers")

    first = Memory().run(action="add", target="USER.md", content="User likes concise answers", distinct=True)
    batch = Memory().run(action="add", target="USER.md", entries=["User wants concise answers"], distinct=True)

    assert first.output.startswith("NOT ADDED") and batch.output.startswith("NOT ADDED")
    assert "likes concise" not in user.read_text() and "wants concise" not in user.read_text()


def test_a_batch_reports_each_similar_entry_and_writes_the_rest(tmp_home_no_env: Path) -> None:
    from alpi.tools.memory import Memory
    (tmp_home_no_env / "memories").mkdir(exist_ok=True)
    Memory().run(action="add", target="USER.md", content="Javi's flight to Madrid is on Friday")

    r = Memory().run(action="add", target="USER.md", entries=[
        "Javi's flight to Bangkok is on Friday", "User drinks tea",
    ])

    text = (tmp_home_no_env / "memories" / "USER.md").read_text()
    assert r.ok and 'NOT ADDED "Javi\'s flight to Bangkok is on Friday"' in r.output and "Madrid" in r.output
    assert "User drinks tea" in text and "Bangkok" not in text


@pytest.mark.parametrize("repeat", ["likes tea with milk", "THE USER LIKES TEA WITH MILK.", "tea"])
def test_words_already_written_in_that_order_only_reinforce(store: memory.MemoryStore, repeat: str) -> None:
    assert store.add("USER.md", "The user likes tea with milk") == "added"
    assert store.add("USER.md", repeat, distinct=True) == "reinforced"
    assert store.snapshot()["USER.md"].count("tea") == 1


@pytest.mark.parametrize("existing, contained", [
    ("\u0e1c\u0e39\u0e49\u0e43\u0e0a\u0e49\u0e0a\u0e2d\u0e1a\u0e01\u0e32\u0e41\u0e1f\u0e14\u0e33", "\u0e0a\u0e2d\u0e1a\u0e01\u0e32\u0e41\u0e1f\u0e14\u0e33"),
    ("\u7528\u6237\u559c\u6b22\u5496\u5561", "\u559c\u6b22\u5496\u5561"),
    ("Server runs on port 8080", "port 80"),
])
def test_text_inside_an_entry_but_not_as_whole_words_is_reported_not_appended(
    store: memory.MemoryStore, existing: str, contained: str,
) -> None:
    assert store.add("USER.md", existing) == "added"
    assert store.add("USER.md", contained) == "similar"
    assert store.last_matched == existing
    assert _entries(store) == [existing]


def test_the_reviewer_cannot_force_an_entry_it_was_never_told_was_similar(tmp_home_no_env: Path) -> None:
    import json

    from alpi import review
    from alpi.tools.memory import Memory
    (tmp_home_no_env / "memories").mkdir(exist_ok=True)
    Memory().run(action="add", target="USER.md", content="User prefers concise answers")

    review._apply_calls([{"name": "memory", "arguments": json.dumps({
        "action": "add", "target": "USER.md", "content": "User likes concise answers", "distinct": True,
    })}])

    assert "likes concise" not in (tmp_home_no_env / "memories" / "USER.md").read_text()


def test_a_similar_entry_still_keeps_a_low_confidence_one_alive(store: memory.MemoryStore) -> None:
    store.add("USER.md", "User prefers concise answers", confidence="low")
    assert store.add("USER.md", "User likes concise answers") == "similar"
    assert "reinforced=1" in store.user_path.read_text()


def test_a_different_fact_in_the_other_file_can_be_stored(tmp_home_no_env: Path) -> None:
    from alpi.tools.memory import Memory
    (tmp_home_no_env / "memories").mkdir(exist_ok=True)
    assert Memory().run(action="add", target="USER.md", content="Javi's flight to Madrid is on Friday").ok

    refused = Memory().run(action="add", target="MEMORY.md", content="Javi's flight to Bangkok is on Friday")
    stored = Memory().run(action="add", target="MEMORY.md", content="Javi's flight to Bangkok is on Friday", distinct=True)

    assert not refused.ok and "distinct" in refused.error
    assert stored.ok, stored.error
    assert "Bangkok" in (tmp_home_no_env / "memories" / "MEMORY.md").read_text()


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
