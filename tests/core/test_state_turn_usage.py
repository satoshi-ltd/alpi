"""Per-turn usage tally tests."""

from __future__ import annotations

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
