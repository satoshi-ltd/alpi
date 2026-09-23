from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from alpi import ledger

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="POSIX flock")

_CHILD = r"""
import json, os, sys, time
from pathlib import Path

from alpi import ledger
from alpi.host import connection_context as cc

spec = json.loads(sys.argv[1])
sync = Path(spec["sync"])
home = Path(spec["home"])
name = spec["name"]


def wait_go():
    deadline = time.monotonic() + 30
    while not (sync / "go").exists():
        if time.monotonic() > deadline:
            sys.exit(3)
        time.sleep(0.01)


if spec.get("day"):
    ledger._today_utc = lambda: spec["day"]

pause = spec.get("pause")
if pause == "after_load":
    real_load = ledger.load

    def load(h):
        data = real_load(h)
        (sync / f"{name}.loaded").touch()
        wait_go()
        return data

    ledger.load = load
elif pause == "before_replace":
    real_replace = os.replace

    def replace(src, dst, *a, **k):
        if str(dst).endswith("ledger.json"):
            (sync / f"{name}.writing").touch()
            time.sleep(600)
        return real_replace(src, dst, *a, **k)

    os.replace = replace
elif pause == "before_append":
    real_open = Path.open

    def open_(self, mode="r", *a, **k):
        if self.name == "spend_archive.jsonl" and "a" in mode:
            (sync / f"{name}.loaded").touch()
            wait_go()
        return real_open(self, mode, *a, **k)

    Path.open = open_

(sync / f"{name}.ready").touch()
if spec.get("archive"):
    ledger.archive_entity(home, "session", "s-1", cost_usd=0.5, tokens_in=10, source_at="t0")
else:
    ctx = cc.ConnectionContext(connection_id=spec.get("connection", "host"))
    with cc.use(ctx), ledger.peer_context(spec.get("peer")):
        ledger.record(
            home, usd=spec["usd"], tokens=spec["tokens"],
            tokens_in=spec["tokens"], tokens_out=0,
        )
"""


@pytest.fixture
def home(tmp_path: Path) -> Path:
    d = tmp_path / "home"
    d.mkdir()
    return d


@pytest.fixture
def sync(tmp_path: Path) -> Path:
    d = tmp_path / "sync"
    d.mkdir()
    return d


def _spawn(spec: dict) -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, "-c", _CHILD, json.dumps(spec)],
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
    )


def _wait_for(paths: list[Path], timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if all(p.exists() for p in paths):
            return True
        time.sleep(0.01)
    return False


def _finish(*procs: subprocess.Popen) -> None:
    for proc in procs:
        _, err = proc.communicate(timeout=30)
        assert proc.returncode == 0, err.decode()


def _release_after_racing(sync: Path, names: list[str]) -> None:
    assert _wait_for([sync / f"{n}.ready" for n in names], 30)
    # Long enough for an unlocked racer to read the old state; a locked one stays blocked.
    _wait_for([sync / f"{n}.loaded" for n in names], 1.5)
    (sync / "go").touch()


def test_concurrent_writers_keep_every_total(home: Path, sync: Path) -> None:
    a = _spawn({"home": str(home), "sync": str(sync), "name": "a", "pause": "after_load",
                "usd": 1.0, "tokens": 10, "peer": "alice", "connection": "conn-a"})
    b = _spawn({"home": str(home), "sync": str(sync), "name": "b", "pause": "after_load",
                "usd": 1.0, "tokens": 10, "connection": "conn-b"})
    _release_after_racing(sync, ["a", "b"])
    _finish(a, b)

    snap = ledger.snapshot(home)
    assert snap["profile"]["usd"] == pytest.approx(2.0)
    assert snap["profile"]["tokens"] == 20
    assert snap["by_peer"]["alice"]["usd"] == pytest.approx(1.0)
    assert snap["by_peer"][ledger.INTERACTIVE_BUCKET]["usd"] == pytest.approx(1.0)
    assert snap["by_connection"]["conn-a"]["tokens_in"] == 10
    assert snap["by_connection"]["conn-b"]["tokens_in"] == 10
    day = snap["history"][snap["day"]]
    assert day["usd"] == pytest.approx(2.0)
    assert day["tokens_in"] == 20
    assert set(day["by_connection"]) == {"conn-a", "conn-b"}


def test_a_writer_crossing_midnight_keeps_the_earlier_days_charge(
    home: Path, sync: Path,
) -> None:
    before, after = "2026-03-10", "2026-03-11"
    with patch.object(ledger, "_today_utc", return_value=before):
        ledger.record(home, usd=0.5, tokens=5)
    a = _spawn({"home": str(home), "sync": str(sync), "name": "a", "pause": "after_load",
                "day": before, "usd": 1.0, "tokens": 10})
    assert _wait_for([sync / "a.loaded"], 30)
    b = _spawn({"home": str(home), "sync": str(sync), "name": "b", "pause": "after_load",
                "day": after, "usd": 2.0, "tokens": 20})
    _release_after_racing(sync, ["b"])
    _finish(a, b)

    with patch.object(ledger, "_today_utc", return_value=after):
        snap = ledger.snapshot(home)
    assert snap["profile"]["usd"] == pytest.approx(2.0)
    assert snap["history"][before]["usd"] == pytest.approx(1.5)
    assert snap["history"][after]["usd"] == pytest.approx(2.0)


def test_a_writer_killed_mid_save_neither_blocks_nor_corrupts(
    home: Path, sync: Path,
) -> None:
    ledger.record(home, usd=1.0, tokens=10)
    victim = _spawn({"home": str(home), "sync": str(sync), "name": "v",
                     "pause": "before_replace", "usd": 5.0, "tokens": 50})
    try:
        assert _wait_for([sync / "v.writing"], 30)
    finally:
        victim.send_signal(signal.SIGKILL)
        victim.wait(timeout=30)

    done = threading.Event()

    def survivor() -> None:
        ledger.record(home, usd=2.0, tokens=20)
        done.set()

    threading.Thread(target=survivor, daemon=True).start()
    assert done.wait(10), "a dead writer must not keep the ledger locked"

    snap = ledger.snapshot(home)
    assert snap["profile"]["usd"] == pytest.approx(3.0)
    assert snap["profile"]["tokens"] == 30
    assert list(ledger._path(home).parent.glob("*.tmp")) == []


def test_concurrent_archivers_file_one_row_per_entity(home: Path, sync: Path) -> None:
    a = _spawn({"home": str(home), "sync": str(sync), "name": "a",
                "pause": "before_append", "archive": True})
    b = _spawn({"home": str(home), "sync": str(sync), "name": "b",
                "pause": "before_append", "archive": True})
    _release_after_racing(sync, ["a", "b"])
    _finish(a, b)

    rows = [r for r in ledger.read_archive(home) if r["id"] == "s-1"]
    assert len(rows) == 1


def test_a_lock_that_cannot_open_drops_the_charge_loudly_without_raising(
    home: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
) -> None:
    ledger.record(home, usd=1.0, tokens=10)
    real_open = os.open

    def no_fds(path, *a, **k):
        if str(path).endswith("ledger.lock"):
            raise OSError(24, "Too many open files")
        return real_open(path, *a, **k)

    monkeypatch.setattr(os, "open", no_fds)
    with caplog.at_level("WARNING", logger="alpi.ledger"):
        ledger.record(home, usd=2.0, tokens=20)
    monkeypatch.setattr(os, "open", real_open)

    assert "ledger record dropped" in caplog.text
    assert ledger.snapshot(home)["profile"]["usd"] == pytest.approx(1.0)


def test_a_failed_replace_leaves_no_temp_and_keeps_the_last_good_ledger(
    home: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
) -> None:
    ledger.record(home, usd=1.0, tokens=10)

    def fail(*_a, **_k):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(ledger.os, "replace", fail)
    with caplog.at_level("WARNING", logger="alpi.ledger"):
        ledger.record(home, usd=2.0, tokens=20)
    monkeypatch.undo()

    assert "ledger record dropped" in caplog.text
    assert ledger.snapshot(home)["profile"]["usd"] == pytest.approx(1.0)
    assert list(ledger._path(home).parent.glob("*.tmp")) == []


def test_an_archive_lock_that_cannot_open_is_an_archive_failure(
    home: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_open = os.open

    def no_fds(path, *a, **k):
        if str(path).endswith("ledger.lock"):
            raise OSError(24, "Too many open files")
        return real_open(path, *a, **k)

    monkeypatch.setattr(os, "open", no_fds)
    with pytest.raises(OSError, match="cannot persist spend archive"):
        ledger.archive_entity(home, "session", "s-1", cost_usd=0.5)
