from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

from alpi import provider_pause as pp
from alpi import service


@pytest.fixture
def short_tmp() -> Path:
    d = Path(tempfile.mkdtemp(prefix="alpi-pause-", dir="/tmp"))
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


@pytest.fixture(autouse=True)
def _clean():
    pp.reset()
    pp.activate()
    service._LAST_TURN_END.clear()
    service._INFLIGHT.clear()
    yield
    pp.reset()
    service._LAST_TURN_END.clear()
    service._INFLIGHT.clear()


def _home(short_tmp: Path) -> Path:
    home = short_tmp / "alice"
    home.mkdir()
    (home / "alp").mkdir()
    return home


@pytest.mark.asyncio
async def test_dispatch_is_skipped_while_the_provider_is_paused(short_tmp: Path, monkeypatch) -> None:
    home = _home(short_tmp)
    pp.record_failure("alice", "insufficient_credit")
    pp.record_failure("alice", "insufficient_credit")
    spawned = []

    async def fake_create(*argv, **kw):
        spawned.append(argv)
        raise AssertionError("must not spawn")

    monkeypatch.setattr(service.asyncio, "create_subprocess_exec", fake_create)
    await service._dispatch_workgroup_turn(
        home, profile="alice", wg_id="wg_x", wg_name="design", reason="hub posted",
    )
    assert spawned == []
    events = [json.loads(l) for l in service.turn_log_path(home).read_text().splitlines()]
    assert events[-1]["event"] == "skipped-provider-paused"
    assert events[-1]["code"] == "insufficient_credit"


@pytest.mark.asyncio
async def test_a_turn_that_fails_with_a_credit_code_counts_toward_the_pause(short_tmp: Path, monkeypatch) -> None:
    home = _home(short_tmp)
    monkeypatch.setattr(pp, "notify_opened", lambda *a, **k: None)
    line = json.dumps({"kind": "error", "text": "x", "code": "insufficient_credit", "transient": False})
    real_create = service.asyncio.create_subprocess_exec

    async def fake_create(*argv, **kw):
        return await real_create(
            sys.executable, "-c", f"print({line!r})",
            stdout=service.asyncio.subprocess.PIPE, stderr=service.asyncio.subprocess.PIPE,
        )

    monkeypatch.setattr(service.asyncio, "create_subprocess_exec", fake_create)
    for _ in range(2):
        await service._dispatch_workgroup_turn(
            home, profile="alice", wg_id="wg_x", wg_name="design", reason="hub posted",
        )
    assert pp.paused("alice") is not None


@pytest.mark.asyncio
async def test_a_clean_turn_closes_the_pause(short_tmp: Path, monkeypatch) -> None:
    home = _home(short_tmp)
    monkeypatch.setattr(pp, "notify_closed", lambda *a, **k: None)
    pp.record_failure("alice", "auth", now=0.0)
    pp.record_failure("alice", "auth", now=1.0)
    real_create = service.asyncio.create_subprocess_exec

    async def fake_create(*argv, **kw):
        return await real_create(
            sys.executable, "-c", "pass",
            stdout=service.asyncio.subprocess.PIPE, stderr=service.asyncio.subprocess.PIPE,
        )

    monkeypatch.setattr(service.asyncio, "create_subprocess_exec", fake_create)
    monkeypatch.setattr(pp, "paused", lambda profile, now=None: None)
    await service._dispatch_workgroup_turn(
        home, profile="alice", wg_id="wg_x", wg_name="design", reason="hub posted",
    )
    monkeypatch.undo()
    assert pp._states.get("alice") is None


@pytest.mark.asyncio
async def test_a_turn_that_errored_without_a_code_does_not_close_the_pause(short_tmp: Path, monkeypatch) -> None:
    home = _home(short_tmp)
    monkeypatch.setattr(pp, "notify_closed", lambda *a, **k: None)
    pp.record_failure("alice", "auth", now=0.0)
    pp.record_failure("alice", "auth", now=1.0)
    line = json.dumps({"kind": "error", "text": "stale-round"})
    real_create = service.asyncio.create_subprocess_exec

    async def fake_create(*argv, **kw):
        return await real_create(
            sys.executable, "-c", f"print({line!r})",
            stdout=service.asyncio.subprocess.PIPE, stderr=service.asyncio.subprocess.PIPE,
        )

    monkeypatch.setattr(service.asyncio, "create_subprocess_exec", fake_create)
    monkeypatch.setattr(pp, "paused", lambda profile, now=None: None)
    await service._dispatch_workgroup_turn(
        home, profile="alice", wg_id="wg_x", wg_name="design", reason="hub posted",
    )
    monkeypatch.undo()
    assert pp._states.get("alice") is not None
