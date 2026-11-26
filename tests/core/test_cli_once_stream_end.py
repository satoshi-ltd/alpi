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

ONCE = ["chat", "--once", "ping", "--connection-id", "conn_t"]


@pytest.fixture
def daemon_stream(monkeypatch):
    root = Path(tempfile.mkdtemp(prefix="alp-cli-end-", dir="/tmp"))
    (root / "host").mkdir()
    monkeypatch.setenv("ALPI_HOME", str(root))
    monkeypatch.setenv("HOME", str(root))
    frames: list[dict] = []

    class Handler(socketserver.StreamRequestHandler):
        def handle(self) -> None:
            self.rfile.readline()
            for frame in frames:
                self.wfile.write((json.dumps(frame) + "\n").encode())

    server = socketserver.ThreadingUnixStreamServer(str(root / "host" / "host.sock"), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield frames
    finally:
        server.shutdown()
        server.server_close()
        shutil.rmtree(root, ignore_errors=True)


@pytest.mark.parametrize("frames", [
    [],
    [{"event": "assistant_delta", "text": "half an ans"}],
    [{"event": "tool_start", "name": "terminal"}, {"event": "tool_end", "name": "terminal", "ok": True}],
    [{"event": "reply", "text": "all of it"}],
])
@pytest.mark.parametrize("extra", [[], ["--emit-events"]])
def test_a_stream_that_ends_before_done_is_a_failure(daemon_stream, frames: list[dict], extra: list[str]) -> None:
    daemon_stream.extend(frames)
    result = CliRunner().invoke(cli.main, ONCE + extra)
    assert result.exit_code == 1, result.output
    assert "the daemon closed the connection before the turn finished" in result.output
    assert '"kind": "reply"' not in result.output


@pytest.mark.parametrize("extra, said", [([], "the answer"), (["--emit-events"], '{"kind": "reply", "text": "the answer"}')])
def test_a_stream_that_ends_with_done_prints_the_reply(daemon_stream, extra: list[str], said: str) -> None:
    daemon_stream.extend([{"event": "reply", "text": "the answer"}, {"event": "done"}])
    result = CliRunner().invoke(cli.main, ONCE + extra)
    assert result.exit_code == 0, result.output
    assert result.output.strip().splitlines()[-1] == said


@pytest.mark.parametrize("extra", [[], ["--emit-events"]])
@pytest.mark.parametrize("before", [[], [{"event": "preparing"}, {"event": "heartbeat"}]])
def test_a_request_the_daemon_refused_fails_with_the_daemon_reason(daemon_stream, extra: list[str], before: list[dict]) -> None:
    daemon_stream.extend([*before, {"event": "error", "text": "session already has a running turn"}])
    result = CliRunner().invoke(cli.main, ONCE + extra)
    assert result.exit_code == 1, result.output
    assert "delegated chat failed: session already has a running turn" in result.output
    assert "outcome is unknown" not in result.output
    assert '"kind": "reply"' not in result.output


def test_a_turn_that_ended_in_an_error_and_finished_still_prints_it(daemon_stream) -> None:
    daemon_stream.extend([{"event": "error", "text": "provider exploded"}, {"event": "reply", "text": ""}, {"event": "done"}])
    result = CliRunner().invoke(cli.main, ONCE)
    assert result.exit_code == 0, result.output
    assert result.output.strip() == "[error] provider exploded"


def test_an_error_after_the_turn_started_is_not_reported_as_a_refusal(daemon_stream) -> None:
    daemon_stream.extend([
        {"event": "tool_start", "name": "terminal"}, {"event": "tool_end", "name": "terminal", "ok": True},
        {"event": "error", "text": "The provider is overloaded. Try again."},
    ])
    result = CliRunner().invoke(cli.main, ONCE)
    assert result.exit_code == 1, result.output
    assert "The provider is overloaded. Try again.; the daemon closed the connection before the turn finished" in result.output
