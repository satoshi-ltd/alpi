"""Persistent outputs store — JSONL inbox under <home>/outputs/."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from alpi import outputs as outputs_mod


@pytest.fixture
def home(tmp_path: Path) -> Path:
    h = tmp_path / "h"
    h.mkdir()
    return h


def _append(home: Path, **overrides) -> dict:
    base = dict(
        profile="default",
        source="send_message",
        body="hello",
    )
    base.update(overrides)
    return outputs_mod.append(home, **base)


def test_append_persists_and_returns_record(home: Path) -> None:
    out = _append(home, body="ping")
    assert out["id"] and len(out["id"]) == 12
    assert out["status"] == "unread"
    assert out["body"] == "ping"
    assert "title" not in out
    path = outputs_mod._store_path(home)
    assert path.exists()
    lines = path.read_text().splitlines()
    assert json.loads(lines[0])["id"] == out["id"]


def test_list_returns_newest_first(home: Path) -> None:
    a = _append(home, body="first")
    b = _append(home, body="second")
    c = _append(home, body="third")
    items = outputs_mod.list_outputs(home)
    assert [it["id"] for it in items] == [c["id"], b["id"], a["id"]]


def test_list_filters_by_status(home: Path) -> None:
    a = _append(home, body="a")
    _append(home, body="b")
    outputs_mod.mark_read(home, a["id"])
    _append(home, body="c")
    unread = outputs_mod.list_outputs(home, status="unread")
    assert [it["body"] for it in unread] == ["c", "b"]
    read_only = outputs_mod.list_outputs(home, status="read")
    assert [it["body"] for it in read_only] == ["a"]


def test_list_rejects_archived_status(home: Path) -> None:
    """status="archived" returns [] not raises — archive was removed."""
    _append(home, body="a")
    assert outputs_mod.list_outputs(home, status="archived") == []


def test_read_returns_record(home: Path) -> None:
    out = _append(home, body="ping")
    got = outputs_mod.read(home, out["id"])
    assert got is not None and got["id"] == out["id"]
    assert outputs_mod.read(home, "deadbeef") is None


def test_mark_read_idempotent(home: Path) -> None:
    out = _append(home, body="ping")
    assert outputs_mod.mark_read(home, out["id"])["status"] == "read"
    assert outputs_mod.mark_read(home, out["id"])["status"] == "read"
    assert outputs_mod.read(home, out["id"])["status"] == "read"


def test_mark_all_read_flips_only_unread(home: Path) -> None:
    a = _append(home, body="a")
    _append(home, body="b")
    _append(home, body="c")
    outputs_mod.mark_read(home, a["id"])
    touched = outputs_mod.mark_all_read(home)
    assert touched == 2
    assert outputs_mod.list_outputs(home, status="unread") == []
    assert len(outputs_mod.list_outputs(home, status="read")) == 3


def test_mark_all_read_empty_inbox_is_zero(home: Path) -> None:
    assert outputs_mod.mark_all_read(home) == 0


def test_mark_all_read_idempotent(home: Path) -> None:
    _append(home, body="a")
    outputs_mod.mark_all_read(home)
    assert outputs_mod.mark_all_read(home) == 0


def test_retention_caps_at_max_outputs(home: Path) -> None:
    cap = outputs_mod.MAX_OUTPUTS
    overflow = 7
    kept = []
    for i in range(cap + overflow):
        kept.append(_append(home, body=f"row-{i}"))
    items = outputs_mod.list_outputs(home, limit=cap + overflow + 10)
    assert len(items) == cap
    assert items[0]["id"] == kept[-1]["id"]
    assert items[-1]["id"] == kept[overflow]["id"]


def test_corrupt_lines_are_skipped(home: Path) -> None:
    out = _append(home, body="ping")
    path = outputs_mod._store_path(home)
    with path.open("a", encoding="utf-8") as f:
        f.write("not-json\n")
        f.write('{"id": ""}\n')
    items = outputs_mod.list_outputs(home)
    assert [it["id"] for it in items] == [out["id"]]


def test_append_rejects_unknown_source(home: Path) -> None:
    with pytest.raises(ValueError, match="invalid source"):
        outputs_mod.append(
            home, profile="default", source="garbage", body="x",
        )


def test_append_normalises_invalid_severity_and_kind(home: Path) -> None:
    out = _append(home, severity="ULTRA", kind="wibble")
    assert out["severity"] == "normal"
    assert out["kind"] == "result"


def test_delivered_to_round_trips(home: Path) -> None:
    out = _append(home, delivered_to=["alpi", "telegram"])
    got = outputs_mod.read(home, out["id"])
    assert got["delivered_to"] == ["alpi", "telegram"]
