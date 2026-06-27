"""Tests for the host-plane approval bridge (CF.3).

Cover the request/response cycle, the four choices, the timeout
auto-deny, idempotency on late responses, and the per-profile audit
log.
"""

from __future__ import annotations

import asyncio
import json
import shutil
import tempfile
import threading
import time
from pathlib import Path

import pytest

from alpi.alp.keys import load_or_generate
from alpi.host import approval as host_approval
from alpi.host import events as host_events
from alpi.host import server as host_server
from alpi.tools import _approval


@pytest.fixture
def short_tmp() -> Path:
    d = Path(tempfile.mkdtemp(prefix="alp-approval-", dir="/tmp"))
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


@pytest.fixture(autouse=True)
def _reset_state():
    yield
    host_approval._reset_for_tests()
    _approval.set_prompt_callback(None)
    _approval.clear_session_allowlist()


async def _make_server(home: Path) -> host_server.Server:
    srv = host_server.Server(home=home)
    host_events.register(srv)
    host_approval.register(srv)
    await srv.start()
    return srv


async def _subscribe(srv: host_server.Server, kinds: list[str] | None = None):
    reader, writer = await asyncio.open_unix_connection(str(srv.socket_path()))
    params: dict = {}
    if kinds:
        params["kinds"] = kinds
    writer.write(
        (json.dumps({"id": "sub", "method": "host.events.subscribe", "params": params}) + "\n").encode()
    )
    await writer.drain()
    first = json.loads(await reader.readline())
    assert first["event"] == "subscribed"
    return reader, writer


async def _rpc(srv: host_server.Server, method: str, params: dict) -> dict:
    reader, writer = await asyncio.open_unix_connection(str(srv.socket_path()))
    try:
        writer.write(
            (json.dumps({"id": "r", "method": method, "params": params}) + "\n").encode()
        )
        await writer.drain()
        line = await asyncio.wait_for(reader.readline(), timeout=2.0)
        return json.loads(line)
    finally:
        writer.close()
        await writer.wait_closed()


def _run_check_in_thread(cmd: str, out: dict) -> threading.Thread:
    """Call _approval.check() on a worker thread (mimics the tool exec thread)."""

    def _run() -> None:
        out["decision"] = _approval.check(cmd)

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return t


async def _await_event(reader, kind: str, timeout: float = 2.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        remaining = max(0.05, deadline - time.time())
        line = await asyncio.wait_for(reader.readline(), timeout=remaining)
        frame = json.loads(line)
        if frame.get("event") == kind:
            return frame
    raise AssertionError(f"event {kind!r} did not arrive within {timeout}s")


@pytest.mark.asyncio
async def test_once_choice_unblocks_terminal_with_approval(short_tmp: Path) -> None:
    home = short_tmp / "h"
    home.mkdir()
    load_or_generate(home)
    srv = await _make_server(home)

    try:
        reader, writer = await _subscribe(srv, kinds=["approval.request", "approval.resolved"])
        out: dict = {}
        t = _run_check_in_thread("rm -rf build", out)

        req = await _await_event(reader, "approval.request")
        assert req["data"]["severity"] == "caution"
        assert req["data"]["pattern"] == "recursive rm"
        request_id = req["data"]["request_id"]
        assert isinstance(request_id, str) and request_id

        resp = await _rpc(srv, "host.approval.respond", {"request_id": request_id, "choice": "once"})
        assert resp.get("result") == {"ok": True}

        t.join(timeout=3.0)
        assert not t.is_alive()
        d: _approval.Decision = out["decision"]
        assert d.allowed is True
        assert d.severity == _approval.Severity.CAUTION
        assert d.pattern == "recursive rm"
        assert "user approved" in d.reason

        resolved = await _await_event(reader, "approval.resolved")
        assert resolved["data"]["choice"] == "once"
        assert resolved["data"]["request_id"] == request_id

        writer.close()
        await writer.wait_closed()
    finally:
        await srv.stop()


@pytest.mark.asyncio
async def test_deny_choice_blocks_command_and_carries_user_rejected_reason(short_tmp: Path) -> None:
    home = short_tmp / "h"
    home.mkdir()
    load_or_generate(home)
    srv = await _make_server(home)

    try:
        reader, writer = await _subscribe(srv, kinds=["approval.request"])
        out: dict = {}
        t = _run_check_in_thread("rm -rf build", out)

        req = await _await_event(reader, "approval.request")
        request_id = req["data"]["request_id"]

        resp = await _rpc(srv, "host.approval.respond", {"request_id": request_id, "choice": "deny"})
        assert resp.get("result") == {"ok": True}

        t.join(timeout=3.0)
        d = out["decision"]
        assert d.allowed is False
        assert "user rejected" in d.reason.lower()

        writer.close()
        await writer.wait_closed()
    finally:
        await srv.stop()


@pytest.mark.asyncio
async def test_session_choice_persists_for_repeat_caution_pattern(short_tmp: Path) -> None:
    home = short_tmp / "h"
    home.mkdir()
    load_or_generate(home)
    srv = await _make_server(home)

    try:
        reader, writer = await _subscribe(srv, kinds=["approval.request"])

        out1: dict = {}
        t1 = _run_check_in_thread("rm -rf build", out1)
        req1 = await _await_event(reader, "approval.request")
        await _rpc(srv, "host.approval.respond", {
            "request_id": req1["data"]["request_id"], "choice": "session",
        })
        t1.join(timeout=3.0)
        assert out1["decision"].allowed is True

        # second call hits the session allowlist without prompting again
        out2: dict = {}
        t2 = _run_check_in_thread("rm -rf dist", out2)
        t2.join(timeout=3.0)
        assert out2["decision"].allowed is True
        assert "session" in out2["decision"].reason.lower()

        writer.close()
        await writer.wait_closed()
    finally:
        await srv.stop()


@pytest.mark.asyncio
async def test_always_choice_writes_pattern_to_config_allowlist(short_tmp: Path, monkeypatch) -> None:
    home = short_tmp / "h"
    home.mkdir()
    load_or_generate(home)
    srv = await _make_server(home)

    # _persist_always reads from alpi.home.get_home() — point it at the test home (restored after the test, or it leaks _ROOT into later modules).
    from alpi import home as home_mod
    monkeypatch.setattr(home_mod, "_ROOT", home)

    try:
        reader, writer = await _subscribe(srv, kinds=["approval.request"])

        out: dict = {}
        t = _run_check_in_thread("rm -rf build", out)
        req = await _await_event(reader, "approval.request")
        await _rpc(srv, "host.approval.respond", {
            "request_id": req["data"]["request_id"], "choice": "always",
        })
        t.join(timeout=3.0)

        import yaml
        data = yaml.safe_load((home / "config.yaml").read_text())
        allow = data["tools"]["terminal"]["approval"]["allowlist"]
        assert "recursive rm" in allow

        writer.close()
        await writer.wait_closed()
    finally:
        await srv.stop()


@pytest.mark.asyncio
async def test_timeout_auto_denies_without_a_responder(short_tmp: Path, monkeypatch) -> None:
    home = short_tmp / "h"
    home.mkdir()
    load_or_generate(home)
    srv = await _make_server(home)

    monkeypatch.setattr(host_approval, "PROMPT_TIMEOUT_S", 0.3)

    try:
        out: dict = {}
        t = _run_check_in_thread("rm -rf build", out)
        # Yield to the loop until the worker finishes — t.join() would block the loop's
        # only thread and starve _arm_coro/_await_choice from ever running.
        deadline = time.time() + 3.0
        while t.is_alive() and time.time() < deadline:
            await asyncio.sleep(0.05)
        assert not t.is_alive()
        d = out["decision"]
        assert d.allowed is False
        assert d.severity == _approval.Severity.CAUTION
    finally:
        await srv.stop()


@pytest.mark.asyncio
async def test_late_response_for_unknown_request_is_idempotent_noop(short_tmp: Path) -> None:
    home = short_tmp / "h"
    home.mkdir()
    load_or_generate(home)
    srv = await _make_server(home)

    try:
        resp = await _rpc(srv, "host.approval.respond", {
            "request_id": "does-not-exist", "choice": "once",
        })
        assert resp.get("result") == {"ok": False, "reason": "unknown or already resolved"}
    finally:
        await srv.stop()


@pytest.mark.asyncio
async def test_invalid_choice_is_rejected_without_resolving_the_future(short_tmp: Path) -> None:
    home = short_tmp / "h"
    home.mkdir()
    load_or_generate(home)
    srv = await _make_server(home)

    try:
        reader, writer = await _subscribe(srv, kinds=["approval.request"])
        out: dict = {}
        t = _run_check_in_thread("rm -rf build", out)
        req = await _await_event(reader, "approval.request")
        request_id = req["data"]["request_id"]

        resp = await _rpc(srv, "host.approval.respond", {
            "request_id": request_id, "choice": "lgtm",
        })
        assert resp.get("result", {}).get("ok") is False

        # the real choice now lands cleanly
        resp2 = await _rpc(srv, "host.approval.respond", {
            "request_id": request_id, "choice": "once",
        })
        assert resp2.get("result") == {"ok": True}

        t.join(timeout=3.0)
        assert out["decision"].allowed is True

        writer.close()
        await writer.wait_closed()
    finally:
        await srv.stop()


@pytest.mark.asyncio
async def test_pending_rpc_lets_a_cold_start_client_see_in_flight_approvals(short_tmp: Path) -> None:
    """A request emitted before the client subscribed won't reach it via the
    live stream — `host.approval.pending` is the recovery path that closes the
    cold-start window."""
    home = short_tmp / "h"
    home.mkdir()
    load_or_generate(home)
    srv = await _make_server(home)

    try:
        out: dict = {}
        # First subscriber (the daemon's "active" view) sees the request and lets us capture the id.
        reader1, writer1 = await _subscribe(srv, kinds=["approval.request"])
        t = _run_check_in_thread("rm -rf build", out)
        req = await _await_event(reader1, "approval.request")
        request_id = req["data"]["request_id"]

        # Now a brand-new client comes up cold and asks for pending approvals — no live subscription needed.
        pending = await _rpc(srv, "host.approval.pending", {})
        items = pending["result"]["requests"]
        assert any(it["request_id"] == request_id for it in items)
        entry = next(it for it in items if it["request_id"] == request_id)
        assert entry["pattern"] == "recursive rm"
        assert entry["command"] == "rm -rf build"

        # The cold client can now respond exactly like the warm one would have.
        resp = await _rpc(srv, "host.approval.respond", {"request_id": request_id, "choice": "once"})
        assert resp.get("result") == {"ok": True}
        t.join(timeout=3.0)
        assert out["decision"].allowed is True

        # And after the respond completes, pending is empty.
        pending2 = await _rpc(srv, "host.approval.pending", {})
        assert pending2["result"]["requests"] == []

        writer1.close()
        await writer1.wait_closed()
    finally:
        await srv.stop()


@pytest.mark.asyncio
async def test_profile_field_resolves_via_get_home_not_env(short_tmp: Path, monkeypatch) -> None:
    """The approval.request payload's `profile` must come from the daemon's
    per-turn ContextVar (get_home()), not the legacy ALPI_PROFILE env. The
    daemon supervises many profiles in one process; ALPI_PROFILE is the
    last-loaded leftover and would mis-tag every approval after the first
    profile boots.

    To actually exercise the ContextVar — not just `_ROOT` fallback path
    parsing — the worker thread is the one to bind it, since each call to
    ``_approval.check`` runs on whatever thread the tool execution picked,
    and ``Engine.run_turn`` is where the per-turn home gets bound in
    production. We bind a DIFFERENT home into the worker than the global
    ``_ROOT`` so a regression that drops the ContextVar lookup would
    surface as the wrong profile name in the emitted event.
    """
    from alpi import home as home_mod

    daemon_root = short_tmp / "h"
    daemon_root.mkdir(parents=True)
    load_or_generate(daemon_root)
    monkeypatch.setattr(home_mod, "_ROOT", daemon_root)
    monkeypatch.setenv("ALPI_PROFILE", "WRONG-leftover-from-env")

    per_turn_home = short_tmp / "profiles" / "mirai"
    per_turn_home.mkdir(parents=True)

    srv = await _make_server(daemon_root)

    def _run_with_ctxvar(out: dict) -> threading.Thread:
        def _run() -> None:
            token = home_mod.set_active_home(per_turn_home)
            try:
                out["decision"] = _approval.check("rm -rf build")
            finally:
                home_mod.reset_active_home(token)
        th = threading.Thread(target=_run, daemon=True)
        th.start()
        return th

    try:
        reader, writer = await _subscribe(srv, kinds=["approval.request"])
        out: dict = {}
        t = _run_with_ctxvar(out)
        req = await _await_event(reader, "approval.request")
        # ContextVar wins over _ROOT and over ALPI_PROFILE.
        assert req["data"]["profile"] == "mirai"

        await _rpc(srv, "host.approval.respond", {"request_id": req["data"]["request_id"], "choice": "deny"})
        t.join(timeout=3.0)

        writer.close()
        await writer.wait_closed()
    finally:
        await srv.stop()


@pytest.mark.asyncio
async def test_safe_command_skips_the_prompt_entirely(short_tmp: Path) -> None:
    home = short_tmp / "h"
    home.mkdir()
    load_or_generate(home)
    srv = await _make_server(home)

    try:
        reader, writer = await _subscribe(srv, kinds=["approval.request"])

        out: dict = {}
        t = _run_check_in_thread("ls -la", out)
        t.join(timeout=1.0)
        d = out["decision"]
        assert d.allowed is True
        assert d.severity == _approval.Severity.SAFE

        # no event should have been emitted
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(reader.readline(), timeout=0.2)

        writer.close()
        await writer.wait_closed()
    finally:
        await srv.stop()
