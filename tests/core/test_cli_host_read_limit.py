from __future__ import annotations

import json
import shutil
import socketserver
import tempfile
import threading
from pathlib import Path

import pytest
from click.testing import CliRunner

from alpi import cli

BIG = 200 * 1024


@pytest.fixture
def fake_host(monkeypatch):
    root = Path(tempfile.mkdtemp(prefix="alp-cli-lim-", dir="/tmp"))
    (root / "host").mkdir()
    monkeypatch.setenv("ALPI_HOME", str(root))
    requests: list[dict] = []
    replies: list[list[dict]] = []

    class Handler(socketserver.StreamRequestHandler):
        def handle(self) -> None:
            body = json.loads(self.rfile.readline())
            requests.append(body)
            for frame in replies.pop(0):
                self.wfile.write((json.dumps(frame) + "\n").encode())

    server = socketserver.ThreadingUnixStreamServer(str(root / "host" / "host.sock"), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield requests, replies
    finally:
        server.shutdown()
        server.server_close()
        shutil.rmtree(root, ignore_errors=True)


def test_delegated_once_prints_a_reply_past_the_default_stream_limit(fake_host) -> None:
    requests, replies = fake_host
    answer = "a" * BIG
    replies.append([
        {"event": "tool_start", "name": "write_file", "args": {"path": "out/a.md", "content": "c" * BIG}},
        {"event": "reply", "text": answer},
        {"event": "done"},
    ])
    result = CliRunner().invoke(
        cli.main, ["chat", "--once", "ping", "--connection-id", "conn_t"],
    )
    assert result.exit_code == 0, result.output
    assert result.output.strip() == answer
    assert requests[0]["method"] == "host.chat.delegate"
    assert requests[0]["params"]["profile"] == "default"
    assert requests[0]["params"]["connection_id"] == "conn_t"


def test_runs_cancel_reads_a_reply_past_the_default_stream_limit(fake_host) -> None:
    _, replies = fake_host
    replies.append([{"id": "cli-runs-cancel", "result": {"cancelled": True, "pad": "p" * BIG}}])
    result = CliRunner().invoke(cli.main, ["runs", "cancel", "run_1"])
    assert result.exit_code == 0, result.output
    assert "cancellation requested for run_1" in result.output
