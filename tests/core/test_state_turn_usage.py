"""Per-turn usage tally tests."""

from __future__ import annotations

import pytest

from alpi.tools import _state


def test_reset_initialises_zero() -> None:
    _state.reset_turn_usage()
    assert _state.get_turn_usage() == {
        "tokens_in": 0, "tokens_out": 0, "usd": 0.0,
        "cached_in": 0, "measured_in": 0,
    }


def test_an_unreported_bump_stays_out_of_the_denominator() -> None:
    _state.reset_turn_usage()
    _state.bump_turn_usage(100, 200, 0.05)
    snap = _state.get_turn_usage()
    assert snap["cached_in"] == 0 and snap["measured_in"] == 0

    _state.bump_turn_usage(100, 0, 0.01, 90)
    snap = _state.get_turn_usage()
    assert snap["cached_in"] == 90 and snap["measured_in"] == 100

    _state.bump_turn_usage(50, 0, 0.01, 0)
    snap = _state.get_turn_usage()
    assert snap["cached_in"] == 90 and snap["measured_in"] == 150, (
        "a reported zero is a measured miss and grows the denominator"
    )


def test_bump_accumulates() -> None:
    _state.reset_turn_usage()
    _state.bump_turn_usage(100, 200, 0.05)
    snap = _state.get_turn_usage()
    assert snap == {
        "tokens_in": 100, "tokens_out": 200, "usd": 0.05,
        "cached_in": 0, "measured_in": 0,
    }

    _state.bump_turn_usage(50, 25, 0.02)
    snap = _state.get_turn_usage()
    assert snap["tokens_in"] == 150
    assert snap["tokens_out"] == 225
    assert abs(snap["usd"] - 0.07) < 1e-9


def test_record_usage_also_updates_tally() -> None:
    """`record_usage` should also bump the tally."""
    _state.reset_turn_usage()
    _state.set_usage_sink(None)
    _state.record_usage(40, 60, 0.01)
    snap = _state.get_turn_usage()
    assert snap == {
        "tokens_in": 40, "tokens_out": 60, "usd": 0.01,
        "cached_in": 0, "measured_in": 0,
    }


def test_get_turn_usage_returns_none_outside_a_turn() -> None:
    """Outside a turn, the tally is unset."""
    _state._turn_usage.set(None)
    assert _state.get_turn_usage() is None


def test_undeclared_usage_advances_only_when_marked() -> None:
    _state.reset_turn_usage()
    _state.bump_turn_usage(100, 10, 0.01, 80)

    first, snapshot = _state.get_undeclared_turn_usage()
    assert first == {
        "tokens_in": 100, "tokens_out": 10, "usd": 0.01,
        "cached_in": 80, "measured_in": 100,
    }
    assert _state.get_undeclared_turn_usage()[0] == first

    _state.mark_turn_usage_declared(snapshot)
    _state.bump_turn_usage(25, 3, 0.002, 20)
    delta, _ = _state.get_undeclared_turn_usage()
    assert delta == {
        "tokens_in": 25, "tokens_out": 3, "usd": pytest.approx(0.002),
        "cached_in": 20, "measured_in": 25,
    }


def test_turn_id_uses_dispatch_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPI_WORKGROUP_TURN_ID", "a" * 32)
    _state.reset_turn_usage()
    assert _state.get_turn_id() == "a" * 32
