"""UX.1 — ``ask_user`` tool routing + validation."""

from __future__ import annotations

import pytest

from alpi.tools import _clarification
from alpi.tools.ask_user import AskUser


@pytest.fixture(autouse=True)
def _reset_handler():
    _clarification.set_handler(None)
    yield
    _clarification.set_handler(None)


def _choices(n: int = 2) -> list[dict[str, str]]:
    base = [
        {"label": "WHOOP", "description": "recovery, sleep"},
        {"label": "COROS"},
        {"label": "Garmin", "description": "training load"},
        {"label": "Apple"},
    ]
    return base[:n]


def test_rejects_empty_question(monkeypatch) -> None:
    monkeypatch.delenv("ALPI_PLATFORM", raising=False)
    r = AskUser().run(question="  ", choices=_choices())
    assert not r.ok
    assert "question is required" in (r.error or "")


def test_rejects_fewer_than_two_choices(monkeypatch) -> None:
    monkeypatch.delenv("ALPI_PLATFORM", raising=False)
    r = AskUser().run(question="?", choices=[{"label": "Only"}])
    assert not r.ok
    assert "2-4" in (r.error or "")


def test_rejects_more_than_four_choices(monkeypatch) -> None:
    monkeypatch.delenv("ALPI_PLATFORM", raising=False)
    five = [{"label": f"L{i}"} for i in range(5)]
    r = AskUser().run(question="?", choices=five)
    assert not r.ok
    assert "2-4" in (r.error or "")


def test_multi_accepts_up_to_eight_choices(monkeypatch) -> None:
    monkeypatch.delenv("ALPI_PLATFORM", raising=False)
    monkeypatch.setattr("alpi.tools.ask_user._is_gateway", lambda: True)
    eight = [{"label": f"L{i}"} for i in range(8)]
    r = AskUser().run(question="?", choices=eight, multi=True)
    assert r.ok, r.error


def test_multi_rejects_more_than_eight_choices(monkeypatch) -> None:
    monkeypatch.delenv("ALPI_PLATFORM", raising=False)
    nine = [{"label": f"L{i}"} for i in range(9)]
    r = AskUser().run(question="?", choices=nine, multi=True)
    assert not r.ok
    assert "2-8" in (r.error or "")


def test_rejects_empty_label(monkeypatch) -> None:
    monkeypatch.delenv("ALPI_PLATFORM", raising=False)
    r = AskUser().run(question="?", choices=[{"label": "A"}, {"label": "  "}])
    assert not r.ok
    assert "non-empty" in (r.error or "")


def test_rejects_duplicate_labels(monkeypatch) -> None:
    monkeypatch.delenv("ALPI_PLATFORM", raising=False)
    r = AskUser().run(
        question="?", choices=[{"label": "Same"}, {"label": "Same"}],
    )
    assert not r.ok
    assert "duplicate" in (r.error or "")


def test_gateway_short_circuits_with_numbered_text(monkeypatch) -> None:
    monkeypatch.setenv("ALPI_PLATFORM", "telegram")
    r = AskUser().run(
        question="Which source?",
        choices=_choices(3),
        allow_other=True,
    )
    assert r.ok
    assert "1. WHOOP — recovery, sleep" in r.output
    assert "2. COROS" in r.output
    assert "3. Garmin — training load" in r.output
    assert "4. Other" in r.output
    assert "Relay this list" in r.output


def test_gateway_without_other_still_renders_options(monkeypatch) -> None:
    monkeypatch.setenv("ALPI_PLATFORM", "email")
    r = AskUser().run(
        question="?", choices=_choices(2), allow_other=False,
    )
    assert r.ok
    assert "Other" not in r.output


def test_handler_path_returns_chosen_label(monkeypatch) -> None:
    monkeypatch.delenv("ALPI_PLATFORM", raising=False)
    received: dict = {}

    def _handler(q, c, allow_other, multi):
        received["q"] = q
        received["c"] = c
        received["allow_other"] = allow_other
        received["multi"] = multi
        return "WHOOP"

    _clarification.set_handler(_handler)
    r = AskUser().run(
        question="Which?",
        choices=_choices(2),
        allow_other=False,
    )
    assert r.ok
    assert r.output == "WHOOP"
    assert received["q"] == "Which?"
    assert received["c"][0]["label"] == "WHOOP"
    assert received["allow_other"] is False
    assert received["multi"] is False


def test_handler_empty_string_means_no_response(monkeypatch) -> None:
    monkeypatch.delenv("ALPI_PLATFORM", raising=False)
    _clarification.set_handler(lambda *_a, **_k: "")
    r = AskUser().run(question="?", choices=_choices())
    assert r.ok
    assert "No response received" in r.output


def test_handler_exception_does_not_crash_turn(monkeypatch) -> None:
    monkeypatch.delenv("ALPI_PLATFORM", raising=False)
    def _boom(*_a, **_k):
        raise RuntimeError("ui crashed")
    _clarification.set_handler(_boom)
    r = AskUser().run(question="?", choices=_choices())
    assert r.ok
    assert "Clarification handler failed" in r.output


def test_multi_true_forces_allow_other_false(monkeypatch) -> None:
    monkeypatch.delenv("ALPI_PLATFORM", raising=False)
    received: dict = {}
    def _handler(q, c, allow_other, multi):
        received["allow_other"] = allow_other
        received["multi"] = multi
        return "WHOOP, COROS"
    _clarification.set_handler(_handler)
    r = AskUser().run(
        question="Which?",
        choices=_choices(3),
        allow_other=True,  # ignored
        multi=True,
    )
    assert r.ok
    assert r.output == "WHOOP, COROS"
    assert received["multi"] is True
    assert received["allow_other"] is False


def test_gateway_multi_render_mentions_multiple(monkeypatch) -> None:
    monkeypatch.setenv("ALPI_PLATFORM", "telegram")
    r = AskUser().run(
        question="What sources?",
        choices=_choices(3),
        multi=True,
    )
    assert r.ok
    assert "1. WHOOP" in r.output
    assert "separated by commas" in r.output
    assert "Other" not in r.output  # multi suppresses allow_other


def test_no_handler_returns_plain_fallback(monkeypatch) -> None:
    monkeypatch.delenv("ALPI_PLATFORM", raising=False)
    r = AskUser().run(question="?", choices=_choices())
    assert r.ok
    assert "ask the user plainly" in r.output


def test_gateway_path_does_not_call_handler(monkeypatch) -> None:
    monkeypatch.setenv("ALPI_PLATFORM", "matrix")
    sentinel = {"called": False}
    def _handler(*_a, **_k):
        sentinel["called"] = True
        return "should-not-happen"
    _clarification.set_handler(_handler)
    r = AskUser().run(question="?", choices=_choices())
    assert r.ok
    assert sentinel["called"] is False


def test_cron_headless_returns_fallback_without_calling_handler(monkeypatch) -> None:
    """Scheduled jobs have no live user — handler must not be touched and we must not emit a numbered text block (no inbound channel)."""
    monkeypatch.setenv("ALPI_PLATFORM", "cron")
    sentinel = {"called": False}
    def _handler(*_a, **_k):
        sentinel["called"] = True
        return "should-not-happen"
    _clarification.set_handler(_handler)
    r = AskUser().run(question="Which?", choices=_choices())
    assert r.ok
    assert sentinel["called"] is False
    assert "no live user" in r.output
    assert "cron" in r.output
    # Headless output must NOT be a numbered list — the model should treat it as a directive, not relay it.
    assert "1." not in r.output
    assert "2." not in r.output
