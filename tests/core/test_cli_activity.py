from __future__ import annotations

import json
import shutil
import socketserver
import tempfile
import threading
import time
from pathlib import Path

import pytest
from click.testing import CliRunner

from alpi import cli


def _result() -> dict:
    return {
        "needs_you": [{
            "kind": "approval", "request_id": "r1", "profile": "builder", "title": "run a shell command",
            "severity": "caution", "ts": time.time() - 12, "timeout_s": 60.0, "session_id": "s1",
        }],
        "running": [
            {"kind": "turn", "profile": "alpi", "session_id": "s2", "title": "deploy summary",
             "started_at": time.time() - 42, "source": "chat"},
            {"kind": "workgroup", "profile": "alpi", "workgroup_id": "wg1", "name": "launch-crew",
             "pipeline": "launch", "phase": "analyze", "phases_done": 1, "phases_total": 4},
        ],
        "scheduled": [
            {"profile": "doc", "job_id": "brief", "title": "daily brief", "next_fire": "2099-01-01T08:00:00+00:00",
             "last_run_at": None, "last_run_status": None},
            {"profile": "doc", "job_id": "labs", "title": "weekly labs", "next_fire": None,
             "last_run_at": "2026-09-29T03:00:00+00:00", "last_run_status": "error"},
        ],
    }


@pytest.fixture
def fake_host(monkeypatch):
    root = Path(tempfile.mkdtemp(prefix="alp-cli-act-", dir="/tmp"))
    (root / "host").mkdir()
    monkeypatch.setenv("ALPI_HOME", str(root))
    requests: list[dict] = []
    result = _result()

    class Handler(socketserver.StreamRequestHandler):
        def handle(self) -> None:
            body = json.loads(self.rfile.readline())
            requests.append(body)
            self.wfile.write((json.dumps({"id": body["id"], "result": result}) + "\n").encode())

    server = socketserver.ThreadingUnixStreamServer(str(root / "host" / "host.sock"), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield requests, result
    finally:
        server.shutdown()
        server.server_close()
        shutil.rmtree(root, ignore_errors=True)


def test_activity_json_calls_the_host_verb(fake_host) -> None:
    result = CliRunner().invoke(cli.main, ["activity", "--json"])
    assert result.exit_code == 0, result.output
    requests, expected = fake_host
    assert json.loads(result.output) == expected
    assert requests == [{"id": "cli-activity", "method": "host.activity.list", "params": {}}]


def test_activity_table_lists_needs_you_first(fake_host) -> None:
    result = CliRunner().invoke(cli.main, ["activity"])
    assert result.exit_code == 0, result.output
    lines = result.output.splitlines()
    assert lines[0] == "Needs you · 1"
    assert "run a shell command" in lines[1] and "12s ago" in lines[1]
    assert lines[2] == "Running · 2"
    assert "deploy summary" in lines[3] and "chat" in lines[3]
    assert "launch-crew" in lines[4] and "analyze 1/4" in lines[4]
    assert lines[5] == "Scheduled · 2"
    assert "daily brief" in lines[6] and "in " in lines[6]
    assert "weekly labs" in lines[7] and "last run: error" in lines[7]


def test_activity_without_daemon_says_so(monkeypatch) -> None:
    root = Path(tempfile.mkdtemp(prefix="alp-cli-act-", dir="/tmp"))
    monkeypatch.setenv("ALPI_HOME", str(root))
    try:
        result = CliRunner().invoke(cli.main, ["activity"])
    finally:
        shutil.rmtree(root, ignore_errors=True)
    assert result.exit_code != 0
    assert "daemon not running" in result.output


def test_activity_reports_a_garbled_reply_as_such(monkeypatch) -> None:
    root = Path(tempfile.mkdtemp(prefix="alp-cli-act-", dir="/tmp"))
    (root / "host").mkdir()
    monkeypatch.setenv("ALPI_HOME", str(root))

    class Handler(socketserver.StreamRequestHandler):
        def handle(self) -> None:
            self.rfile.readline()
            self.wfile.write(b"not json\n")

    server = socketserver.ThreadingUnixStreamServer(str(root / "host" / "host.sock"), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        result = CliRunner().invoke(cli.main, ["activity"])
    finally:
        server.shutdown()
        server.server_close()
        shutil.rmtree(root, ignore_errors=True)
    assert result.exit_code != 0
    assert "invalid response from the daemon" in result.output
    assert "daemon not running" not in result.output


def test_activity_reads_replies_past_the_default_stream_limit(monkeypatch) -> None:
    root = Path(tempfile.mkdtemp(prefix="alp-cli-act-", dir="/tmp"))
    (root / "host").mkdir()
    monkeypatch.setenv("ALPI_HOME", str(root))
    big = {"needs_you": [], "scheduled": [], "running": [
        {"kind": "turn", "profile": "p", "session_id": f"s{i}", "title": "x" * 80,
         "started_at": time.time(), "source": "chat"}
        for i in range(1000)
    ]}

    class Handler(socketserver.StreamRequestHandler):
        def handle(self) -> None:
            body = json.loads(self.rfile.readline())
            self.wfile.write((json.dumps({"id": body["id"], "result": big}) + "\n").encode())

    server = socketserver.ThreadingUnixStreamServer(str(root / "host" / "host.sock"), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        result = CliRunner().invoke(cli.main, ["activity", "--json"])
    finally:
        server.shutdown()
        server.server_close()
        shutil.rmtree(root, ignore_errors=True)
    assert result.exit_code == 0, result.output
    assert len(json.loads(result.output)["running"]) == 1000
