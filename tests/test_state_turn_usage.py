"""Per-turn usage tally in ``alpi.tools._state``.

The engine seeds the tally at the top of every turn; tools that
need to know "what has this turn cost so far?" — most importantly
``workgroup_post`` declaring spend honestly to the workgroup
ledger — read it via ``get_turn_usage``.
"""

from __future__ import annotations

from alpi.tools import _state


def test_reset_initialises_zero() -> None:
    _state.reset_turn_usage()
    assert _state.get_turn_usage() == {"tokens_in": 0, "tokens_out": 0, "usd": 0.0}


def test_bump_accumulates() -> None:
    _state.reset_turn_usage()
    _state.bump_turn_usage(100, 200, 0.05)
    snap = _state.get_turn_usage()
    assert snap == {"tokens_in": 100, "tokens_out": 200, "usd": 0.05}

    _state.bump_turn_usage(50, 25, 0.02)
    snap = _state.get_turn_usage()
    assert snap["tokens_in"] == 150
    assert snap["tokens_out"] == 225
    assert abs(snap["usd"] - 0.07) < 1e-9


def test_record_usage_also_updates_tally() -> None:
    """``record_usage`` (canonical write path used by sub-agents like
    research / delegate) also bumps the tally — this is what makes
    ``workgroup_post`` see sub-agent spend truthfully."""
    _state.reset_turn_usage()
    _state.set_usage_sink(None)
    _state.record_usage(40, 60, 0.01)
    snap = _state.get_turn_usage()
    assert snap == {"tokens_in": 40, "tokens_out": 60, "usd": 0.01}


def test_get_turn_usage_returns_none_outside_a_turn() -> None:
    """Outside a turn the tally is unset — tools should treat None as
    'nothing to declare'."""
    _state._turn_usage.set(None)
    assert _state.get_turn_usage() is None
