from __future__ import annotations

import json
from pathlib import Path

import pytest

from alpi.host.connection_context import ConnectionContext, use
from alpi.tools import session_read, session_search

MEMBER_C1 = ConnectionContext(connection_id="c1", device_id="d1", source="remote", role="member")


def _session(
    home: Path, sid: str, connection_id: str | None, text: str, device_id: str = "",
) -> None:
    sdir = home / "sessions"
    sdir.mkdir(parents=True, exist_ok=True)
    payload = {
        "id": sid, "started_at": 1000.0,
        "turns": [{"user": text, "assistant": f"reply about {text}"}],
    }
    if connection_id is not None:
        payload["connection_id"] = connection_id
    if device_id:
        payload["device_id"] = device_id
    (sdir / f"{sid}.json").write_text(json.dumps(payload))


@pytest.fixture(autouse=True)
def _clear_active():
    session_search.set_current_session_id(None)
    yield
    session_search.set_current_session_id(None)


@pytest.fixture
def seeded(tmp_home) -> Path:
    _session(tmp_home, "s_c1", "c1", "apollo rockets")
    _session(tmp_home, "s_c2", "c2", "apollo rockets")
    _session(tmp_home, "s_host", "host", "apollo rockets")
    _session(tmp_home, "s_legacy", None, "apollo rockets")
    return tmp_home


def test_search_member_sees_only_own_connection(seeded):
    with use(MEMBER_C1):
        out = session_search.SessionSearch().run(query="apollo rockets", max_results=10)
    assert "s_c1" in out.output
    for other in ("s_c2", "s_host", "s_legacy"):
        assert other not in out.output


def test_search_admin_sees_all(seeded):
    out = session_search.SessionSearch().run(query="apollo rockets", max_results=10)
    for sid in ("s_c1", "s_c2", "s_host", "s_legacy"):
        assert sid in out.output


def test_list_member_sees_only_own(seeded):
    with use(MEMBER_C1):
        out = session_read.SessionRead().run()
    assert "s_c1" in out.output
    for other in ("s_c2", "s_host", "s_legacy"):
        assert other not in out.output


def test_list_admin_sees_all(seeded):
    out = session_read.SessionRead().run()
    for sid in ("s_c1", "s_c2", "s_host", "s_legacy"):
        assert sid in out.output


def test_open_by_id_member_own_ok(seeded):
    with use(MEMBER_C1):
        out = session_read.SessionRead().run(session="s_c1")
    assert out.ok and "apollo" in out.output.lower()


@pytest.mark.parametrize("sid", ["s_c2", "s_host", "s_legacy"])
def test_open_by_id_member_others_refused(seeded, sid):
    with use(MEMBER_C1):
        out = session_read.SessionRead().run(session=sid)
    assert out.ok is False and "no session" in (out.error or "").lower()


def test_open_by_id_admin_any(seeded):
    for sid in ("s_c1", "s_c2", "s_host", "s_legacy"):
        out = session_read.SessionRead().run(session=sid)
        assert out.ok


DEVICE_D1 = ConnectionContext("c1", "d1", "remote", "member", session_scope="device")
ADMIN_D1 = ConnectionContext("c1", "d1", "remote", "admin", session_scope="device")


@pytest.fixture
def devices(tmp_home) -> Path:
    _session(tmp_home, "s_d1", "c1", "apollo rockets", device_id="d1")
    _session(tmp_home, "s_d2", "c1", "apollo rockets", device_id="d2")
    _session(tmp_home, "s_shared", "c1", "apollo rockets")
    _session(tmp_home, "s_c2", "c2", "apollo rockets", device_id="d1")
    return tmp_home


def test_search_under_device_scope_sees_own_device_and_shared_sessions(devices):
    with use(DEVICE_D1):
        out = session_search.SessionSearch().run(query="apollo rockets", max_results=10)
    assert "s_d1" in out.output and "s_shared" in out.output
    assert "s_d2" not in out.output and "s_c2" not in out.output


def test_list_under_device_scope_hides_the_sibling_device(devices):
    with use(DEVICE_D1):
        out = session_read.SessionRead().run()
    assert "s_d1" in out.output and "s_shared" in out.output
    assert "s_d2" not in out.output


@pytest.mark.parametrize("sid,ok", [("s_d1", True), ("s_shared", True), ("s_d2", False)])
def test_open_by_id_under_device_scope(devices, sid, ok):
    with use(DEVICE_D1):
        out = session_read.SessionRead().run(session=sid)
    assert out.ok is ok


def test_connection_scope_still_shares_devices(devices):
    with use(MEMBER_C1):
        out = session_read.SessionRead().run(session="s_d2")
    assert out.ok


def test_admin_bypasses_device_scope(devices):
    with use(ADMIN_D1):
        out = session_search.SessionSearch().run(query="apollo rockets", max_results=10)
    for sid in ("s_d1", "s_d2", "s_shared", "s_c2"):
        assert sid in out.output
