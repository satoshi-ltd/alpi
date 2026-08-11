from __future__ import annotations

import pytest

from alpi.tools import _state
from alpi.tools import workgroup as tool_mod
from alpi.tools.workgroup import WorkgroupPostTool


def test_posts_declare_only_new_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    async def post(*args, **kwargs):
        calls.append(kwargs)
        return {"seq": len(calls), "ts": "now"}

    monkeypatch.setattr(tool_mod.wc, "post", post)
    monkeypatch.setattr(tool_mod, "get_home", lambda: None)
    monkeypatch.setenv("ALPI_WORKGROUP_TURN_ID", "b" * 32)
    _state.reset_turn_usage()
    _state.bump_turn_usage(100, 10, 0.01, 80)

    assert WorkgroupPostTool().run(wg_id="wg_x", text="#working build").ok
    _state.bump_turn_usage(50, 5, 0.004, 40)
    assert WorkgroupPostTool().run(wg_id="wg_x", text="build complete").ok

    assert calls[0]["cost"] == {
        "tokens_in": 100,
        "tokens_out": 10,
        "usd": 0.01,
        "cached_in": 80,
        "measured_in": 100,
        "tokens": 110,
    }
    assert calls[1]["cost"] == {
        "tokens_in": 50,
        "tokens_out": 5,
        "usd": pytest.approx(0.004),
        "cached_in": 40,
        "measured_in": 50,
        "tokens": 55,
    }
    assert {call["turn_id"] for call in calls} == {"b" * 32}


def test_rejected_post_does_not_consume_pending_usage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    costs = []

    async def post(*args, **kwargs):
        costs.append(kwargs["cost"])
        if len(costs) == 1:
            raise ValueError("rejected")
        return {"seq": 1, "ts": "now"}

    monkeypatch.setattr(tool_mod.wc, "post", post)
    monkeypatch.setattr(tool_mod, "get_home", lambda: None)
    _state.reset_turn_usage()
    _state.bump_turn_usage(75, 4, 0.02, 60)

    assert not WorkgroupPostTool().run(wg_id="wg_x", text="first").ok
    assert WorkgroupPostTool().run(wg_id="wg_x", text="retry").ok
    assert costs[0] == costs[1]
