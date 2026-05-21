"""CF.2 — file mutation recorder + write_file/edit_file integration + engine batch boundary."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from alpi.tools import _mutations
from alpi.tools.edit_file import EditFile
from alpi.tools.write_file import WriteFile


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_write_file_records_create_when_file_did_not_exist(tmp_home_no_env: Path) -> None:
    target = tmp_home_no_env / "fresh.txt"
    token = _mutations.begin_batch()
    try:
        result = WriteFile().run(path=str(target), content="hola alpi")
        assert result.ok
    finally:
        records = _mutations.end_batch(token)

    assert len(records) == 1
    r = records[0]
    assert r.path == str(target)
    assert r.op == "create"
    assert r.sha_before is None
    assert r.sha_after == _sha("hola alpi")
    assert r.bytes_before == 0
    assert r.bytes_after == len("hola alpi".encode("utf-8"))
    assert r.lines_before == 0
    assert r.lines_after == 1


def test_write_file_records_overwrite_when_file_exists(tmp_home_no_env: Path) -> None:
    target = tmp_home_no_env / "exists.txt"
    target.write_text("old content\nsecond line\n")

    token = _mutations.begin_batch()
    try:
        result = WriteFile().run(path=str(target), content="brand new\n")
        assert result.ok
    finally:
        records = _mutations.end_batch(token)

    assert len(records) == 1
    r = records[0]
    assert r.op == "write"
    assert r.sha_before == _sha("old content\nsecond line\n")
    assert r.sha_after == _sha("brand new\n")
    assert r.bytes_before == len("old content\nsecond line\n".encode("utf-8"))
    assert r.bytes_after == len("brand new\n".encode("utf-8"))
    assert r.lines_before == 2
    assert r.lines_after == 1


def test_edit_file_records_with_op_edit(tmp_home_no_env: Path) -> None:
    target = tmp_home_no_env / "to-edit.txt"
    target.write_text("foo bar baz")

    token = _mutations.begin_batch()
    try:
        result = EditFile().run(path=str(target), old_string="bar", new_string="qux")
        assert result.ok
    finally:
        records = _mutations.end_batch(token)

    assert len(records) == 1
    r = records[0]
    assert r.op == "edit"
    assert r.sha_before == _sha("foo bar baz")
    assert r.sha_after == _sha("foo qux baz")
    assert "bar" in r.diff_preview or "qux" in r.diff_preview


def test_failed_write_records_nothing(tmp_home_no_env: Path) -> None:
    target = tmp_home_no_env / "broken.py"
    token = _mutations.begin_batch()
    try:
        # Unparseable Python — lint refuses
        result = WriteFile().run(path=str(target), content="def foo(:\n  pass\n")
        assert not result.ok
    finally:
        records = _mutations.end_batch(token)

    assert records == []
    assert not target.exists()


def test_failed_edit_records_nothing(tmp_home_no_env: Path) -> None:
    target = tmp_home_no_env / "f.txt"
    target.write_text("only one")
    token = _mutations.begin_batch()
    try:
        # old_string not found
        result = EditFile().run(path=str(target), old_string="MISSING", new_string="X")
        assert not result.ok
    finally:
        records = _mutations.end_batch(token)

    assert records == []


def test_record_outside_a_batch_is_a_noop(tmp_home_no_env: Path) -> None:
    target = tmp_home_no_env / "free.txt"
    result = WriteFile().run(path=str(target), content="just write me")
    assert result.ok  # the tool still works
    assert target.read_text() == "just write me"


def test_end_batch_clears_the_buffer(tmp_home_no_env: Path) -> None:
    target = tmp_home_no_env / "x.txt"

    token1 = _mutations.begin_batch()
    WriteFile().run(path=str(target), content="first")
    first = _mutations.end_batch(token1)
    assert len(first) == 1

    token2 = _mutations.begin_batch()
    second = _mutations.end_batch(token2)
    assert second == []


def test_format_footer_is_compact_one_line_per_record(tmp_home_no_env: Path) -> None:
    target_a = tmp_home_no_env / "a.txt"
    target_b = tmp_home_no_env / "b.txt"
    token = _mutations.begin_batch()
    WriteFile().run(path=str(target_a), content="aaa")
    target_b.write_text("old")
    WriteFile().run(path=str(target_b), content="new")
    records = _mutations.end_batch(token)

    footer = _mutations.format_footer(records)
    assert "[file_mutations]" in footer
    assert str(target_a) in footer
    assert str(target_b) in footer
    assert footer.count("\n") == len(records)


def test_engine_emits_file_mutations_event_and_appends_footer(
    tmp_home_no_env: Path, monkeypatch
) -> None:
    captured: list[tuple[str, dict]] = []
    from alpi.host import events as host_events

    def fake_emit(kind: str, data: dict | None = None) -> None:
        captured.append((kind, data or {}))

    monkeypatch.setattr(host_events, "emit", fake_emit)

    messages: list[dict] = []

    token = _mutations.begin_batch()
    target = tmp_home_no_env / "n.txt"
    WriteFile().run(path=str(target), content="alpha")
    EditFile().run(path=str(target), old_string="alpha", new_string="beta")
    records = _mutations.end_batch(token)
    if records:
        host_events.emit(
            "file_mutations",
            {
                "profile": "doc",
                "session_id": "abc123",
                "mutations": [m.to_dict() for m in records],
            },
        )
        footer = _mutations.format_footer(records)
        if footer:
            messages.append({"role": "system", "content": footer})

    assert len(records) == 2
    assert any(k == "file_mutations" for k, _ in captured)
    event = next(d for k, d in captured if k == "file_mutations")
    assert event["profile"] == "doc"
    assert event["session_id"] == "abc123"
    assert len(event["mutations"]) == 2
    assert event["mutations"][0]["op"] == "create"
    assert event["mutations"][1]["op"] == "edit"

    assert len(messages) == 1
    assert messages[0]["role"] == "system"
    assert "[file_mutations]" in messages[0]["content"]


def test_diff_preview_is_bounded(tmp_home_no_env: Path) -> None:
    target = tmp_home_no_env / "big.txt"
    target.write_text("\n".join(f"line-{i}" for i in range(2000)))
    token = _mutations.begin_batch()
    WriteFile().run(path=str(target), content="\n".join(f"row-{i}" for i in range(2000)))
    records = _mutations.end_batch(token)
    assert len(records[0].diff_preview) <= _mutations.DIFF_PREVIEW_MAX_CHARS + 20
