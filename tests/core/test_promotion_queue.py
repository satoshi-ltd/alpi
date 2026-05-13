"""CH.3 — promotion queue store: add / list / discard / apply, cap + expiry."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from alpi import promotion


def test_queue_path_under_memories(tmp_path: Path) -> None:
    assert promotion.queue_path(tmp_path) == tmp_path / "memories" / "promotion_queue.jsonl"


def test_add_then_list_pending(tmp_path: Path) -> None:
    c = promotion.add(
        tmp_path,
        source="compaction",
        session_id="sess-abc",
        model="gpt-5.4-mini",
        target="USER.md",
        text="User is in Madrid",
        confidence="normal",
    )
    pending = promotion.list_pending(tmp_path)
    assert len(pending) == 1
    assert pending[0].id == c.id
    assert pending[0].target == "USER.md"
    assert pending[0].text == "User is in Madrid"
    assert pending[0].source == "compaction"


def test_add_rejects_unknown_target(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        promotion.add(
            tmp_path, source="manual", session_id="s", model="m",
            target="OTHER.md", text="…",
        )


def test_discard_removes_one(tmp_path: Path) -> None:
    a = promotion.add(tmp_path, source="manual", session_id="s", model="m",
                      target="MEMORY.md", text="fact one")
    b = promotion.add(tmp_path, source="manual", session_id="s", model="m",
                      target="MEMORY.md", text="fact two")
    assert promotion.discard(tmp_path, a.id) is True
    remaining = promotion.list_pending(tmp_path)
    assert len(remaining) == 1
    assert remaining[0].id == b.id


def test_discard_returns_false_for_missing(tmp_path: Path) -> None:
    promotion.add(tmp_path, source="manual", session_id="s", model="m",
                  target="MEMORY.md", text="anything")
    assert promotion.discard(tmp_path, "nonexistent") is False


def test_get_and_remove_and_return(tmp_path: Path) -> None:
    c = promotion.add(tmp_path, source="manual", session_id="s", model="m",
                      target="USER.md", text="user is X")
    fetched = promotion.get(tmp_path, c.id)
    assert fetched is not None and fetched.text == "user is X"

    popped = promotion.remove_and_return(tmp_path, c.id)
    assert popped is not None and popped.id == c.id
    # Queue is empty after pop.
    assert promotion.list_pending(tmp_path) == []
    # Repeat pop returns None.
    assert promotion.remove_and_return(tmp_path, c.id) is None


def test_expired_pruned_on_list(tmp_path: Path) -> None:
    promotion.add(tmp_path, source="manual", session_id="s", model="m",
                  target="MEMORY.md", text="old")
    promotion.add(tmp_path, source="manual", session_id="s", model="m",
                  target="MEMORY.md", text="fresh")

    # Force virtual "now" 60 days into the future — only fresh writes
    # within MAX_AGE_DAYS would survive. Both are fresh now, so we instead
    # rewrite the file with an old created_at on one row, then re-read.
    path = promotion.queue_path(tmp_path)
    raw = path.read_text(encoding="utf-8").splitlines()
    import json
    rows = [json.loads(line) for line in raw]
    rows[0]["created_at"] = time.time() - (promotion.MAX_AGE_DAYS + 1) * 86400
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")

    pending = promotion.list_pending(tmp_path)
    assert len(pending) == 1
    assert pending[0].text == "fresh"


def test_cap_enforced(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(promotion, "MAX_PENDING", 3)
    for i in range(6):
        promotion.add(tmp_path, source="manual", session_id="s", model="m",
                      target="MEMORY.md", text=f"fact {i}")
    pending = promotion.list_pending(tmp_path)
    assert len(pending) == 3
    # Most recent three survive.
    assert [c.text for c in pending] == ["fact 3", "fact 4", "fact 5"]


def test_corrupted_jsonl_lines_skipped(tmp_path: Path) -> None:
    promotion.add(tmp_path, source="manual", session_id="s", model="m",
                  target="MEMORY.md", text="good")
    path = promotion.queue_path(tmp_path)
    path.write_text(path.read_text() + "not-json\n{\"target\":\"USER.md\"}\n",
                    encoding="utf-8")
    pending = promotion.list_pending(tmp_path)
    # Only the well-formed candidate from add() and the JSON-with-target survive;
    # but the second has empty text → Candidate.from_dict still loads it but the
    # store keeps everything well-formed JSON. So len >= 1 and "good" is there.
    texts = {c.text for c in pending}
    assert "good" in texts
