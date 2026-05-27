"""UX.1 — inline (stdin/stdout) clarification handler used by ``alpi chat --once``."""

from __future__ import annotations

import io
import sys

import pytest

from alpi.tui.clarification_inline import inline_handler


def _drive(monkeypatch, *lines: str) -> tuple[str, str]:
    """Feed ``lines`` to stdin in order; return ``(result, stderr_dump)``."""
    monkeypatch.setattr(sys, "stdin", io.StringIO("\n".join(lines) + "\n"))
    err = io.StringIO()
    monkeypatch.setattr(sys, "stderr", err)
    return None, err  # caller will call inline_handler explicitly


def _run(monkeypatch, lines, question, choices, allow_other=True):
    monkeypatch.setattr(sys, "stdin", io.StringIO("\n".join(lines) + "\n"))
    err = io.StringIO()
    monkeypatch.setattr(sys, "stderr", err)
    out = inline_handler(question, choices, allow_other)
    return out, err.getvalue()


def test_picks_by_number(monkeypatch) -> None:
    out, err = _run(
        monkeypatch, ["1"], "Which?",
        [{"label": "WHOOP"}, {"label": "COROS"}],
    )
    assert out == "WHOOP"
    assert "Which?" in err
    assert "1. WHOOP" in err
    assert "2. COROS" in err


def test_picks_by_label_case_insensitive(monkeypatch) -> None:
    out, _ = _run(
        monkeypatch, ["coros"], "?",
        [{"label": "WHOOP"}, {"label": "COROS"}],
    )
    assert out == "COROS"


def test_other_via_number_prompts_for_text(monkeypatch) -> None:
    out, err = _run(
        monkeypatch, ["3", "use the staging account"], "?",
        [{"label": "Personal"}, {"label": "Work"}],
        allow_other=True,
    )
    assert out == "use the staging account"
    assert "3. Other" in err


def test_free_text_when_allow_other_true(monkeypatch) -> None:
    out, _ = _run(
        monkeypatch, ["just merge it"], "?",
        [{"label": "Overwrite"}, {"label": "Skip"}],
        allow_other=True,
    )
    assert out == "just merge it"


def test_free_text_rejected_when_allow_other_false(monkeypatch) -> None:
    out, err = _run(
        monkeypatch, ["something else", "1"], "?",
        [{"label": "Overwrite"}, {"label": "Skip"}],
        allow_other=False,
    )
    assert out == "Overwrite"
    assert "Unknown choice" in err


def test_out_of_range_number_reprompts(monkeypatch) -> None:
    out, err = _run(
        monkeypatch, ["99", "1"], "?",
        [{"label": "A"}, {"label": "B"}],
        allow_other=False,
    )
    assert out == "A"
    assert "Out of range" in err


def test_empty_input_returns_empty(monkeypatch) -> None:
    out, _ = _run(
        monkeypatch, [""], "?",
        [{"label": "A"}, {"label": "B"}],
    )
    assert out == ""


def test_eof_returns_empty(monkeypatch) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))
    monkeypatch.setattr(sys, "stderr", io.StringIO())
    out = inline_handler("?", [{"label": "A"}, {"label": "B"}], False)
    assert out == ""


def test_multi_csv_numbers(monkeypatch) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO("1,3\n"))
    monkeypatch.setattr(sys, "stderr", io.StringIO())
    out = inline_handler(
        "Pick many",
        [{"label": "A"}, {"label": "B"}, {"label": "C"}, {"label": "D"}],
        allow_other=False,
        multi=True,
    )
    assert out == "A, C"


def test_multi_csv_labels_case_insensitive(monkeypatch) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO("sleep summary, training load\n"))
    monkeypatch.setattr(sys, "stderr", io.StringIO())
    out = inline_handler(
        "?",
        [
            {"label": "Sleep summary"},
            {"label": "Training load"},
            {"label": "Recovery breakdown"},
        ],
        allow_other=False,
        multi=True,
    )
    assert out == "Sleep summary, Training load"


def test_multi_dedupes_and_preserves_order(monkeypatch) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO("2, A, 1, B\n"))
    monkeypatch.setattr(sys, "stderr", io.StringIO())
    out = inline_handler(
        "?",
        [{"label": "A"}, {"label": "B"}, {"label": "C"}],
        allow_other=False,
        multi=True,
    )
    assert out == "B, A"


def test_multi_reprompts_when_no_valid_picks(monkeypatch) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO("nope\n1\n"))
    monkeypatch.setattr(sys, "stderr", io.StringIO())
    out = inline_handler(
        "?",
        [{"label": "A"}, {"label": "B"}],
        allow_other=False,
        multi=True,
    )
    assert out == "A"


def test_multi_empty_returns_empty(monkeypatch) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO("\n"))
    monkeypatch.setattr(sys, "stderr", io.StringIO())
    out = inline_handler("?", [{"label": "A"}, {"label": "B"}], False, multi=True)
    assert out == ""
