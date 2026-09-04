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


@pytest.mark.parametrize(
    "error",
    [
        tool_mod.alp_client.RemoteError(-32005, "rate-limited"),
        tool_mod.alp_client.RemoteError(-32007, "target-busy"),
        OSError("connection reset"),
    ],
)
def test_transient_post_failure_is_preserved(
    monkeypatch: pytest.MonkeyPatch, error: Exception,
) -> None:
    async def post(*args, **kwargs):
        raise error

    monkeypatch.setattr(tool_mod.wc, "post", post)
    monkeypatch.setattr(tool_mod, "get_home", lambda: None)

    result = WorkgroupPostTool().run(wg_id="wg_x", text="handoff")

    assert not result.ok
    assert result.transient is True


def test_semantic_post_rejection_is_not_transient(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def post(*args, **kwargs):
        raise tool_mod.alp_client.RemoteError(-32012, "gate-failed")

    monkeypatch.setattr(tool_mod.wc, "post", post)
    monkeypatch.setattr(tool_mod, "get_home", lambda: None)

    result = WorkgroupPostTool().run(wg_id="wg_x", text="handoff")

    assert not result.ok
    assert result.transient is False


def test_dispatch_turn_posts_to_its_own_workgroup_even_with_a_mistyped_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []

    async def post(home, wg_id, text, cost=None, turn_id=None):
        calls.append(wg_id)
        return {"seq": 7, "ts": "2026-09-04T00:00:00Z"}

    monkeypatch.setattr(tool_mod.wc, "post", post)
    monkeypatch.setattr(tool_mod, "get_home", lambda: None)
    monkeypatch.setenv("ALPI_WORKGROUP_TURN_ID", "c" * 32)
    monkeypatch.setenv("ALPI_WORKGROUP_DISPATCH", "wg_y3qtl5shxutlhyxq")
    _state.set_undeclared_turn_usage_for_tests(0.0, 0) if hasattr(_state, "set_undeclared_turn_usage_for_tests") else None

    result = WorkgroupPostTool().run(wg_id="wg_y3qt5lshxutlhyxq", text="setup done")
    assert result.ok, result.error
    assert calls == ["wg_y3qtl5shxutlhyxq"]
    assert "replaced by this turn's workgroup" in result.output

    result = WorkgroupPostTool().run(text="setup done again")
    assert result.ok, result.error
    assert calls[-1] == "wg_y3qtl5shxutlhyxq"


def test_member_turn_rejects_a_bare_working_post_but_keeps_finalizer_continuations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []

    async def post(home, wg_id, text, cost=None, turn_id=None):
        calls.append(text.decode())
        return {"seq": 3, "ts": "2026-09-04T00:00:00Z"}

    monkeypatch.setattr(tool_mod.wc, "post", post)
    monkeypatch.setattr(tool_mod, "get_home", lambda: None)
    monkeypatch.setenv("ALPI_WORKGROUP_TURN_ID", "d" * 32)
    monkeypatch.setenv("ALPI_WORKGROUP_DISPATCH", "wg_target")
    monkeypatch.setenv("ALPI_WORKGROUP_MEMBER_TURN", "1")
    from alpi.tools import _state
    _state.reset_turn_usage()
    _state.set_turn_tools_run(3)

    rejected = WorkgroupPostTool().run(text="#working starting the content batch")
    assert not rejected.ok
    assert "post only your handoff" in rejected.error
    assert calls == []

    assert WorkgroupPostTool().run(text="#working half written; next pages (continuation)").ok
    assert WorkgroupPostTool().run(text="#content delivered: 14 files").ok
    assert len(calls) == 2


def test_member_turn_rejects_a_handoff_before_any_tool_ran(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from alpi.tools import _state

    calls = []

    async def post(home, wg_id, text, cost=None, turn_id=None):
        calls.append(text.decode())
        return {"seq": 4, "ts": "2026-09-04T00:00:00Z"}

    monkeypatch.setattr(tool_mod.wc, "post", post)
    monkeypatch.setattr(tool_mod, "get_home", lambda: None)
    monkeypatch.setenv("ALPI_WORKGROUP_TURN_ID", "e" * 32)
    monkeypatch.setenv("ALPI_WORKGROUP_DISPATCH", "wg_target")
    monkeypatch.setenv("ALPI_WORKGROUP_MEMBER_TURN", "1")
    _state.reset_turn_usage()

    rejected = WorkgroupPostTool().run(text="@muse acknowledging #assets task; reading the briefing")
    assert not rejected.ok
    assert "nothing ran this turn" in rejected.error
    assert WorkgroupPostTool().run(text="#working resuming after the budget (continuation)").ok

    _state.set_turn_tools_run(1)
    assert WorkgroupPostTool().run(text="#assets delivered: manifest reconciled").ok
    assert len(calls) == 2
