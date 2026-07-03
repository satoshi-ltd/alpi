"""UX.1 — ``host.clarification.*`` RPC + Future bridge."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from alpi.host import clarification as host_clar
from alpi.host import server as host_server


@pytest.fixture(autouse=True)
def _reset_host_clarification():
    host_clar._reset_for_tests()
    yield
    host_clar._reset_for_tests()


@pytest.mark.asyncio
async def test_pending_handler_returns_empty_initially(tmp_path: Path) -> None:
    srv = host_server.Server(home=tmp_path)
    host_clar.register(srv)
    resp = await srv._dispatch({
        "id": "r", "method": "host.clarification.pending", "params": {},
    })
    assert resp["result"] == {"requests": []}


@pytest.mark.asyncio
async def test_respond_unknown_id_returns_clean_error(tmp_path: Path) -> None:
    srv = host_server.Server(home=tmp_path)
    host_clar.register(srv)
    resp = await srv._dispatch({
        "id": "r", "method": "host.clarification.respond",
        "params": {"request_id": "deadbeef", "choice": "WHOOP"},
    })
    assert resp["result"] == {"ok": False, "reason": "unknown or already resolved"}


@pytest.mark.asyncio
async def test_respond_requires_non_empty_choice(tmp_path: Path) -> None:
    srv = host_server.Server(home=tmp_path)
    host_clar.register(srv)
    resp = await srv._dispatch({
        "id": "r", "method": "host.clarification.respond",
        "params": {"request_id": "abc", "choice": "   "},
    })
    assert resp["result"]["ok"] is False
    assert "non-empty" in resp["result"]["reason"]


@pytest.mark.asyncio
async def test_full_cycle_handler_resolves_via_respond(tmp_path: Path) -> None:
    """Handler-thread blocks; an out-of-band ``host.clarification.respond`` call wakes it. Mirrors how a real client would answer mid-turn."""
    srv = host_server.Server(home=tmp_path)
    host_clar.register(srv)

    captured: dict = {}
    from alpi.host import events as host_events

    def _spy(kind, data=None):
        captured.setdefault(kind, []).append(dict(data or {}))
    monkeypatched_emit = pytest.MonkeyPatch()
    monkeypatched_emit.setattr(host_events, "emit", _spy)

    try:
        loop = asyncio.get_running_loop()
        choices = [{"label": "WHOOP"}, {"label": "COROS"}]

        def _run_handler() -> str:
            return host_clar.host_clarification_handler(
                "Which source?", choices, allow_other=True,
            )

        handler_future = loop.run_in_executor(None, _run_handler)

        async def _respond_when_request_seen() -> None:
            for _ in range(50):
                if captured.get("clarification.request"):
                    break
                await asyncio.sleep(0.02)
            rid = captured["clarification.request"][0]["request_id"]
            resp = await srv._dispatch({
                "id": "r", "method": "host.clarification.respond",
                "params": {"request_id": rid, "choice": "WHOOP"},
            })
            assert resp["result"] == {"ok": True}

        await asyncio.wait_for(
            asyncio.gather(handler_future, _respond_when_request_seen()),
            timeout=10.0,
        )
        assert handler_future.result() == "WHOOP"
        assert "clarification.resolved" in captured
        resolved = captured["clarification.resolved"][0]
        assert resolved["choice"] == "WHOOP"
        assert resolved["timed_out"] is False
    finally:
        monkeypatched_emit.undo()


@pytest.mark.asyncio
async def test_double_respond_idempotent(tmp_path: Path) -> None:
    srv = host_server.Server(home=tmp_path)
    host_clar.register(srv)
    from alpi.host import events as host_events
    captured: dict = {}
    def _spy(kind, data=None):
        captured.setdefault(kind, []).append(dict(data or {}))
    monkeypatched = pytest.MonkeyPatch()
    monkeypatched.setattr(host_events, "emit", _spy)
    try:
        loop = asyncio.get_running_loop()

        def _run_handler() -> str:
            return host_clar.host_clarification_handler(
                "?", [{"label": "A"}, {"label": "B"}], allow_other=False,
            )

        handler_future = loop.run_in_executor(None, _run_handler)

        rid = None
        for _ in range(50):
            if captured.get("clarification.request"):
                rid = captured["clarification.request"][0]["request_id"]
                break
            await asyncio.sleep(0.02)
        assert rid is not None

        first = await srv._dispatch({
            "id": "1", "method": "host.clarification.respond",
            "params": {"request_id": rid, "choice": "A"},
        })
        second = await srv._dispatch({
            "id": "2", "method": "host.clarification.respond",
            "params": {"request_id": rid, "choice": "B"},
        })
        assert first["result"] == {"ok": True}
        assert second["result"]["ok"] is False
        assert second["result"]["reason"] == "unknown or already resolved"

        result = await asyncio.wait_for(handler_future, timeout=5.0)
        assert result == "A"
    finally:
        monkeypatched.undo()


@pytest.mark.asyncio
async def test_pending_handler_lists_in_flight_requests(tmp_path: Path) -> None:
    srv = host_server.Server(home=tmp_path)
    host_clar.register(srv)
    from alpi.host import events as host_events
    monkeypatched = pytest.MonkeyPatch()
    monkeypatched.setattr(host_events, "emit", lambda *a, **k: None)
    try:
        loop = asyncio.get_running_loop()

        def _run_handler() -> str:
            return host_clar.host_clarification_handler(
                "Choose one", [{"label": "X"}, {"label": "Y"}], allow_other=True,
            )

        handler_future = loop.run_in_executor(None, _run_handler)
        await asyncio.sleep(0.05)

        resp = await srv._dispatch({
            "id": "r", "method": "host.clarification.pending", "params": {},
        })
        items = resp["result"]["requests"]
        assert len(items) == 1
        assert items[0]["question"] == "Choose one"
        assert items[0]["allow_other"] is True
        rid = items[0]["request_id"]

        await srv._dispatch({
            "id": "r2", "method": "host.clarification.respond",
            "params": {"request_id": rid, "choice": "X"},
        })
        result = await asyncio.wait_for(handler_future, timeout=5.0)
        assert result == "X"

        resp_after = await srv._dispatch({
            "id": "r3", "method": "host.clarification.pending", "params": {},
        })
        assert resp_after["result"]["requests"] == []
    finally:
        monkeypatched.undo()


@pytest.mark.asyncio
async def test_respond_rejects_freeform_when_allow_other_false(tmp_path: Path) -> None:
    """With ``allow_other=False`` the server must refuse a choice that doesn't match any offered label — protects against a stale / hostile client fabricating an answer the tool never offered."""
    srv = host_server.Server(home=tmp_path)
    host_clar.register(srv)
    from alpi.host import events as host_events
    monkeypatched = pytest.MonkeyPatch()
    monkeypatched.setattr(host_events, "emit", lambda *a, **k: None)
    try:
        loop = asyncio.get_running_loop()

        def _run_handler() -> str:
            return host_clar.host_clarification_handler(
                "Pick one", [{"label": "A"}, {"label": "B"}], allow_other=False,
            )

        handler_future = loop.run_in_executor(None, _run_handler)
        await asyncio.sleep(0.05)
        pending_resp = await srv._dispatch({
            "id": "p", "method": "host.clarification.pending", "params": {},
        })
        rid = pending_resp["result"]["requests"][0]["request_id"]

        bad = await srv._dispatch({
            "id": "bad", "method": "host.clarification.respond",
            "params": {"request_id": rid, "choice": "made-up answer"},
        })
        assert bad["result"]["ok"] is False
        assert "does not match" in bad["result"]["reason"]

        good = await srv._dispatch({
            "id": "good", "method": "host.clarification.respond",
            "params": {"request_id": rid, "choice": "A"},
        })
        assert good["result"] == {"ok": True}
        result = await asyncio.wait_for(handler_future, timeout=5.0)
        assert result == "A"
    finally:
        monkeypatched.undo()


@pytest.mark.asyncio
async def test_respond_accepts_freeform_when_allow_other_true(tmp_path: Path) -> None:
    srv = host_server.Server(home=tmp_path)
    host_clar.register(srv)
    from alpi.host import events as host_events
    monkeypatched = pytest.MonkeyPatch()
    monkeypatched.setattr(host_events, "emit", lambda *a, **k: None)
    try:
        loop = asyncio.get_running_loop()

        def _run_handler() -> str:
            return host_clar.host_clarification_handler(
                "Pick one", [{"label": "A"}, {"label": "B"}], allow_other=True,
            )

        handler_future = loop.run_in_executor(None, _run_handler)
        await asyncio.sleep(0.05)
        pending_resp = await srv._dispatch({
            "id": "p", "method": "host.clarification.pending", "params": {},
        })
        rid = pending_resp["result"]["requests"][0]["request_id"]

        resp = await srv._dispatch({
            "id": "r", "method": "host.clarification.respond",
            "params": {"request_id": rid, "choice": "something custom"},
        })
        assert resp["result"] == {"ok": True}
        result = await asyncio.wait_for(handler_future, timeout=5.0)
        assert result == "something custom"
    finally:
        monkeypatched.undo()


@pytest.mark.asyncio
async def test_respond_always_accepts_cancel_sentinel(tmp_path: Path) -> None:
    """Cancel marker is the protocol value the UI sends when the user closes the sheet — it must resolve even with ``allow_other=False``, otherwise closing the sheet leaves the model hanging."""
    srv = host_server.Server(home=tmp_path)
    host_clar.register(srv)
    from alpi.host import events as host_events
    monkeypatched = pytest.MonkeyPatch()
    monkeypatched.setattr(host_events, "emit", lambda *a, **k: None)
    try:
        loop = asyncio.get_running_loop()

        def _run_handler() -> str:
            return host_clar.host_clarification_handler(
                "Pick", [{"label": "A"}, {"label": "B"}], allow_other=False,
            )

        handler_future = loop.run_in_executor(None, _run_handler)
        await asyncio.sleep(0.05)
        pending_resp = await srv._dispatch({
            "id": "p", "method": "host.clarification.pending", "params": {},
        })
        rid = pending_resp["result"]["requests"][0]["request_id"]

        resp = await srv._dispatch({
            "id": "r", "method": "host.clarification.respond",
            "params": {"request_id": rid, "choice": host_clar.CANCEL_SENTINEL},
        })
        assert resp["result"] == {"ok": True}
        result = await asyncio.wait_for(handler_future, timeout=5.0)
        assert result == host_clar.CANCEL_SENTINEL
    finally:
        monkeypatched.undo()


@pytest.mark.asyncio
async def test_multi_respond_accepts_json_array_of_labels(tmp_path: Path) -> None:
    """``multi=True`` accepts a JSON-array string of labels and joins them ``", "`` for the model."""
    srv = host_server.Server(home=tmp_path)
    host_clar.register(srv)
    from alpi.host import events as host_events
    monkeypatched = pytest.MonkeyPatch()
    monkeypatched.setattr(host_events, "emit", lambda *a, **k: None)
    try:
        loop = asyncio.get_running_loop()

        def _run_handler() -> str:
            return host_clar.host_clarification_handler(
                "Pick many", [{"label": "A"}, {"label": "B"}, {"label": "C"}],
                allow_other=False, multi=True,
            )

        handler_future = loop.run_in_executor(None, _run_handler)
        await asyncio.sleep(0.05)
        pending = await srv._dispatch({
            "id": "p", "method": "host.clarification.pending", "params": {},
        })
        rid = pending["result"]["requests"][0]["request_id"]
        assert pending["result"]["requests"][0]["multi"] is True

        resp = await srv._dispatch({
            "id": "r", "method": "host.clarification.respond",
            "params": {"request_id": rid, "choice": '["A","C"]'},
        })
        assert resp["result"] == {"ok": True}
        result = await asyncio.wait_for(handler_future, timeout=5.0)
        assert result == "A, C"
    finally:
        monkeypatched.undo()


@pytest.mark.asyncio
async def test_multi_respond_preserves_labels_containing_commas(tmp_path: Path) -> None:
    """A label like ``"Research, quick"`` round-trips intact because the wire is JSON, not CSV."""
    srv = host_server.Server(home=tmp_path)
    host_clar.register(srv)
    from alpi.host import events as host_events
    monkeypatched = pytest.MonkeyPatch()
    monkeypatched.setattr(host_events, "emit", lambda *a, **k: None)
    try:
        loop = asyncio.get_running_loop()

        def _run_handler() -> str:
            return host_clar.host_clarification_handler(
                "?",
                [{"label": "Research, quick"}, {"label": "Other"}],
                allow_other=False, multi=True,
            )

        handler_future = loop.run_in_executor(None, _run_handler)
        await asyncio.sleep(0.05)
        pending = await srv._dispatch({
            "id": "p", "method": "host.clarification.pending", "params": {},
        })
        rid = pending["result"]["requests"][0]["request_id"]

        resp = await srv._dispatch({
            "id": "r", "method": "host.clarification.respond",
            "params": {"request_id": rid, "choice": '["Research, quick","Other"]'},
        })
        assert resp["result"] == {"ok": True}
        result = await asyncio.wait_for(handler_future, timeout=5.0)
        assert result == "Research, quick, Other"
    finally:
        monkeypatched.undo()


@pytest.mark.asyncio
async def test_multi_respond_rejects_unknown_label(tmp_path: Path) -> None:
    srv = host_server.Server(home=tmp_path)
    host_clar.register(srv)
    from alpi.host import events as host_events
    monkeypatched = pytest.MonkeyPatch()
    monkeypatched.setattr(host_events, "emit", lambda *a, **k: None)
    try:
        loop = asyncio.get_running_loop()

        def _run_handler() -> str:
            return host_clar.host_clarification_handler(
                "?", [{"label": "A"}, {"label": "B"}],
                allow_other=False, multi=True,
            )

        handler_future = loop.run_in_executor(None, _run_handler)
        await asyncio.sleep(0.05)
        pending = await srv._dispatch({
            "id": "p", "method": "host.clarification.pending", "params": {},
        })
        rid = pending["result"]["requests"][0]["request_id"]

        bad = await srv._dispatch({
            "id": "bad", "method": "host.clarification.respond",
            "params": {"request_id": rid, "choice": '["A","Z"]'},
        })
        assert bad["result"]["ok"] is False
        assert "Z" in bad["result"]["reason"]

        good = await srv._dispatch({
            "id": "good", "method": "host.clarification.respond",
            "params": {"request_id": rid, "choice": '["B"]'},
        })
        assert good["result"] == {"ok": True}
        result = await asyncio.wait_for(handler_future, timeout=5.0)
        assert result == "B"
    finally:
        monkeypatched.undo()


@pytest.mark.asyncio
async def test_multi_respond_rejects_empty_array(tmp_path: Path) -> None:
    srv = host_server.Server(home=tmp_path)
    host_clar.register(srv)
    from alpi.host import events as host_events
    monkeypatched = pytest.MonkeyPatch()
    monkeypatched.setattr(host_events, "emit", lambda *a, **k: None)
    try:
        loop = asyncio.get_running_loop()

        def _run_handler() -> str:
            return host_clar.host_clarification_handler(
                "?", [{"label": "A"}, {"label": "B"}],
                allow_other=False, multi=True,
            )

        handler_future = loop.run_in_executor(None, _run_handler)
        await asyncio.sleep(0.05)
        pending = await srv._dispatch({
            "id": "p", "method": "host.clarification.pending", "params": {},
        })
        rid = pending["result"]["requests"][0]["request_id"]

        bad = await srv._dispatch({
            "id": "bad", "method": "host.clarification.respond",
            "params": {"request_id": rid, "choice": "[]"},
        })
        assert bad["result"]["ok"] is False
        assert "at least one" in bad["result"]["reason"]

        await srv._dispatch({
            "id": "good", "method": "host.clarification.respond",
            "params": {"request_id": rid, "choice": '["A"]'},
        })
        await asyncio.wait_for(handler_future, timeout=5.0)
    finally:
        monkeypatched.undo()


@pytest.mark.asyncio
async def test_multi_respond_rejects_non_json_choice(tmp_path: Path) -> None:
    """Legacy CSV strings now fail validation — the protocol is JSON-array only."""
    srv = host_server.Server(home=tmp_path)
    host_clar.register(srv)
    from alpi.host import events as host_events
    monkeypatched = pytest.MonkeyPatch()
    monkeypatched.setattr(host_events, "emit", lambda *a, **k: None)
    try:
        loop = asyncio.get_running_loop()

        def _run_handler() -> str:
            return host_clar.host_clarification_handler(
                "?", [{"label": "A"}, {"label": "B"}],
                allow_other=False, multi=True,
            )

        handler_future = loop.run_in_executor(None, _run_handler)
        await asyncio.sleep(0.05)
        pending = await srv._dispatch({
            "id": "p", "method": "host.clarification.pending", "params": {},
        })
        rid = pending["result"]["requests"][0]["request_id"]

        bad = await srv._dispatch({
            "id": "bad", "method": "host.clarification.respond",
            "params": {"request_id": rid, "choice": "A, B"},
        })
        assert bad["result"]["ok"] is False
        assert "JSON" in bad["result"]["reason"]

        await srv._dispatch({
            "id": "good", "method": "host.clarification.respond",
            "params": {"request_id": rid, "choice": '["A"]'},
        })
        await asyncio.wait_for(handler_future, timeout=5.0)
    finally:
        monkeypatched.undo()


def test_pending_profile_resolves_and_fails_closed(monkeypatch):
    from alpi.host import clarification as clar
    clar._reset_for_tests()
    with clar._pending_lock:
        clar._pending_meta["req-1"] = {"request_id": "req-1", "profile": "finance"}
    try:
        assert clar.pending_profile("req-1") == "finance"
        assert clar.pending_profile("unknown") is None
        assert clar.pending_profile("") is None
        assert clar.pending_profile(None) is None
    finally:
        clar._reset_for_tests()
