"""Persistent outputs store — JSONL inbox under <home>/outputs/."""

from __future__ import annotations

import json
import re
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


def test_append_persists_title_when_set(home: Path) -> None:
    out = _append(home, body="python3 run.py exited with code 1.", title="whoop sync failed")
    assert out["title"] == "whoop sync failed"
    assert outputs_mod.read(home, out["id"])["title"] == "whoop sync failed"


def test_sanitize_emoji_keeps_only_status_circles() -> None:
    s = outputs_mod.sanitize_emoji
    assert s("🔴 down, 🟡 warn, 🟢 ok") == "🔴 down, 🟡 warn, 🟢 ok"
    assert s("⚠️ alert ✅ done 🚀 ship 🎉") == "alert done ship"
    assert s("1.798 → 25 — 🟢 ok • bullet") == "1.798 → 25 — 🟢 ok • bullet"
    assert s("") == ""


def test_append_strips_disallowed_emoji(home: Path) -> None:
    out = _append(home, body="✅ Deploy ok 🚀\n🔴 checkout 2%", title="📊 Report")
    assert out["body"] == "Deploy ok\n🔴 checkout 2%"
    assert out["title"] == "Report"


def test_normalize_body_downgrades_disallowed_markdown() -> None:
    n = outputs_mod.normalize_notification_body
    assert n("# Resumen") == "## Resumen"
    assert n("## Anomalías:") == "## Anomalías"
    assert n("#### Deep") == "### Deep"
    assert n("see [docs](https://x) now") == "see docs now"
    assert n("![chart](https://x/c.png)") == "chart"
    assert n("a\n---\nb") == "a\nb"
    assert n("text <b>bold</b> tag") == "text bold tag"
    assert n("  - nested item") == "- nested item"
    assert n("**Veredicto:** ok") == "**Veredicto:** ok"


def test_normalize_strips_only_real_html_tags() -> None:
    n = outputs_mod.normalize_notification_body
    assert n("strip <b>tags</b> only") == "strip tags only"
    assert n("5 < x > 3, latency < p95 > target") == "5 < x > 3, latency < p95 > target"


def test_normalize_preserves_quotes_and_tables() -> None:
    n = outputs_mod.normalize_notification_body
    assert n("> quoted line") == "> quoted line"
    table = "| a | b |\n| --- | --- |\n| 1 | 2 |"
    assert n(table) == table


def test_normalize_title_strips_links_and_emoji() -> None:
    assert outputs_mod.normalize_notification_title("📊 [Report](https://x)") == "Report"


def test_append_normalizes_body_markdown(home: Path) -> None:
    out = _append(home, body="# Daily\n\nsee [here](https://x)\n---\n- item")
    assert out["body"] == "## Daily\n\nsee here\n- item"


def test_read_normalizes_legacy_rows(home: Path) -> None:
    path = outputs_mod._store_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = {
        "id": "a" * 12, "profile": "default", "created_at": 1.0,
        "body": "# Old 🚀\n![chart](http://y)", "title": "📊 T",
        "type": "info", "status": "unread", "delivered_to": [],
    }
    path.write_text(json.dumps(raw) + "\n", encoding="utf-8")
    out = outputs_mod.read(home, "a" * 12)
    assert out["body"] == "## Old\nchart"
    assert out["title"] == "T"


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


def test_delete_drops_one_row(home: Path) -> None:
    a = _append(home, body="a")
    b = _append(home, body="b")
    assert outputs_mod.delete(home, a["id"]) is True
    items = outputs_mod.list_outputs(home)
    assert [it["id"] for it in items] == [b["id"]]


def test_delete_unknown_id_returns_false(home: Path) -> None:
    _append(home, body="a")
    assert outputs_mod.delete(home, "deadbeefcafe") is False
    # Nothing was touched.
    assert len(outputs_mod.list_outputs(home)) == 1


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


def test_append_normalises_invalid_type(home: Path) -> None:
    out = _append(home, type="wibble")
    assert out["type"] == "info"


def test_delivered_to_round_trips(home: Path) -> None:
    out = _append(home, delivered_to=["alpi", "telegram"])
    got = outputs_mod.read(home, out["id"])
    assert got["delivered_to"] == ["alpi", "telegram"]


def test_cli_marks_one_output_unread_and_shows_its_source(tmp_path, monkeypatch) -> None:
    from click.testing import CliRunner

    from alpi import cli, home as home_mod
    from alpi import outputs as outputs_mod

    monkeypatch.setattr(home_mod, "_ROOT", tmp_path)
    monkeypatch.delenv("ALPI_HOME", raising=False)
    monkeypatch.delenv("ALPI_PROFILE", raising=False)
    out = outputs_mod.append(tmp_path, profile="default", body="digest", job_id="daily", run_id="r" * 32)
    shown = CliRunner().invoke(cli.main, ["outputs", "show", out["id"]])
    assert shown.exit_code == 0, shown.output
    assert "job_id daily" in shown.output and f"run_id {'r' * 32}" in shown.output
    assert outputs_mod.read(tmp_path, out["id"])["status"] == "read"
    unread = CliRunner().invoke(cli.main, ["outputs", "unread", out["id"]])
    assert unread.exit_code == 0, unread.output
    assert outputs_mod.read(tmp_path, out["id"])["status"] == "unread"
    assert CliRunner().invoke(cli.main, ["outputs", "unread", "0" * 12]).exit_code == 1


def test_cli_unread_goes_through_the_daemon_when_it_runs(tmp_path, monkeypatch) -> None:
    from click.testing import CliRunner

    from alpi import cli, home as home_mod
    from alpi import outputs as outputs_mod
    from alpi.tui import host_client

    monkeypatch.setattr(home_mod, "_ROOT", tmp_path)
    monkeypatch.delenv("ALPI_HOME", raising=False)
    monkeypatch.delenv("ALPI_PROFILE", raising=False)
    out = outputs_mod.append(tmp_path, profile="default", body="digest")
    outputs_mod.mark_read(tmp_path, out["id"])
    calls = []

    async def fake(method, params=None, **kw):
        calls.append((method, params))
        return {"ok": True}

    monkeypatch.setattr(host_client, "acall", fake)
    result = CliRunner().invoke(cli.main, ["outputs", "unread", out["id"]])
    assert result.exit_code == 0, result.output
    assert calls == [("host.outputs.mark_unread", {"profile": "default", "id": out["id"]})]
    assert outputs_mod.read(tmp_path, out["id"])["status"] == "read"


FIXTURES = Path(__file__).resolve().parents[1] / "common" / "notificationSummary.fixtures.mjs"
CASE_ROW = re.compile(r'^\s*\[("(?:[^"\\]|\\.)*"), ("(?:[^"\\]|\\.)*")\],$', re.M)
CASES = [(json.loads(body), json.loads(summary)) for body, summary in CASE_ROW.findall(FIXTURES.read_text(encoding="utf-8"))]


def test_the_shared_summary_corpus_is_readable() -> None:
    assert len(CASES) == FIXTURES.read_text(encoding="utf-8").count("\n  [")


@pytest.mark.parametrize(("body", "summary"), CASES, ids=lambda v: v[:32] or "empty")
def test_derive_summary_matches_the_shared_corpus(body: str, summary: str) -> None:
    assert outputs_mod.derive_summary(body) == summary


def test_derived_summary_never_exceeds_the_cap_or_ends_on_a_colon() -> None:
    for body, _expected in CASES:
        summary = outputs_mod.derive_summary(body)
        assert len(summary) <= outputs_mod.SUMMARY_MAX
        assert not summary.endswith(":")


def test_append_stores_no_derived_summary_but_the_message_derives_one(home: Path) -> None:
    out = _append(home, body="**Normal day, volume at the floor of the week, alert is a base effect.**\n\n## Volume\n- 1,743 chats")
    assert "summary" not in out
    assert "summary" not in outputs_mod.read(home, out["id"])
    assert outputs_mod.message_summary(out) == "Normal day, volume at the floor of the week, alert is a base effect."


def test_append_keeps_a_given_summary_as_plain_text(home: Path) -> None:
    out = _append(home, body="detail", summary="## **Three** findings fixed:\n- one")
    assert out["summary"] == "Three findings fixed: one"


def test_append_clips_a_long_given_summary(home: Path) -> None:
    out = _append(home, body="detail", summary="word " * 80)
    assert len(out["summary"]) <= outputs_mod.SUMMARY_MAX
    assert out["summary"].endswith("…")


def test_append_omits_the_summary_when_the_body_has_no_prose(home: Path) -> None:
    out = _append(home, body="```text\ntrace\n```")
    assert "summary" not in out


def test_rows_keep_a_given_summary_and_drop_a_malformed_one_without_deriving(home: Path) -> None:
    path = outputs_mod._store_path(home)
    path.parent.mkdir(parents=True)
    legacy = {"id": "aaaaaaaaaaaa", "profile": "default", "created_at": 1.0, "body": "Intro line:\n- the point", "type": "info", "status": "unread"}
    kept = {"id": "bbbbbbbbbbbb", "profile": "default", "created_at": 2.0, "body": "body", "summary": "stored", "type": "info", "status": "unread"}
    broken = {"id": "cccccccccccc", "profile": "default", "created_at": 3.0, "body": "body", "summary": ["x"], "type": "info", "status": "unread"}
    path.write_text("\n".join(json.dumps(row) for row in (legacy, kept, broken)) + "\n")
    assert "summary" not in outputs_mod.read(home, "aaaaaaaaaaaa")
    assert outputs_mod.read(home, "bbbbbbbbbbbb")["summary"] == "stored"
    assert "summary" not in outputs_mod.read(home, "cccccccccccc")
    outputs_mod.mark_read(home, "aaaaaaaaaaaa")
    assert "summary" not in json.loads(path.read_text().split("\n")[0])


def test_title_loses_markdown_but_keeps_hashes_inside() -> None:
    assert outputs_mod.normalize_notification_title("## **PR #482** is `ready`") == "PR #482 is ready"


def test_a_line_separator_inside_a_row_does_not_drop_it(home: Path) -> None:
    first = _append(home, body="before")
    odd = _append(home, body="one\u2028two\u2029three\x85four")
    last = _append(home, body="after")
    ids = {it["id"] for it in outputs_mod.list_outputs(home)}
    assert ids == {first["id"], odd["id"], last["id"]}
    outputs_mod.mark_read(home, first["id"])
    assert {it["id"] for it in outputs_mod.list_outputs(home)} == ids


def test_code_spans_and_urls_keep_their_underscores_and_stars() -> None:
    assert outputs_mod.normalize_notification_title("Fix `__init__` and `**kwargs**` handling") == "Fix __init__ and **kwargs** handling"
    assert outputs_mod.derive_summary("See https://x.example/_private_/path and `2**10 and 3**4`.") == "See https://x.example/_private_/path and 2**10 and 3**4."


def test_a_nul_in_the_text_cannot_reach_the_placeholders(home: Path) -> None:
    out = _append(home, body="x\x005\x00 y", title="a\x000\x00b `c`")
    assert out["title"] == "a0b c"
    assert outputs_mod.message_summary(out) == "x5 y"
    assert outputs_mod.list_outputs(home)[0]["id"] == out["id"]


@pytest.mark.parametrize("value", [5, True, {"text": "x"}, None])
def test_text_arg_turns_non_text_into_nothing(value) -> None:
    assert outputs_mod.text_arg(value) == ""


def test_text_arg_joins_a_list_of_strings() -> None:
    assert outputs_mod.text_arg(["Done.", "All good."]) == "Done. All good."


def test_given_summary_hides_one_the_body_already_opens_with(home: Path) -> None:
    out = _append(home, body="Three replies wait on you.\n\n## Inbox\n- a", summary="Three replies wait on you.")
    assert outputs_mod.given_summary(out) == ""
    other = _append(home, body="## Inbox\n- a", summary="Three replies wait on you.")
    assert outputs_mod.given_summary(other) == "Three replies wait on you."


def test_a_stored_title_survives_reads_and_rewrites_unchanged(home: Path) -> None:
    out = _append(home, body="b", title="Fix `**kwargs**` and `_private_`")
    assert out["title"] == "Fix **kwargs** and _private_"
    assert outputs_mod.read(home, out["id"])["title"] == "Fix **kwargs** and _private_"
    outputs_mod.mark_read(home, out["id"])
    outputs_mod.mark_unread(home, out["id"])
    assert outputs_mod.read(home, out["id"])["title"] == "Fix **kwargs** and _private_"
