"""PID-1 init shim: reaps orphans, forwards signals, mirrors the daemon's exit code."""

from __future__ import annotations

import os
import signal
import threading
import time
from collections.abc import Callable

import pytest
from click.testing import CliRunner

from alpi import cli, pid1


@pytest.fixture
def restore_signals():
    saved = {sig: signal.getsignal(sig) for sig in pid1._FORWARDED}
    yield
    for sig, handler in saved.items():
        signal.signal(sig, handler)


@pytest.fixture
def quiet_parent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pid1, "_configure_logging", lambda: None)
    monkeypatch.setattr(pid1, "_set_proctitle", lambda: None)


def _fork(child: Callable[[], None]) -> int:
    pid = os.fork()
    if pid == 0:
        try:
            child()
        finally:
            os._exit(99)
    return pid


def test_exit_code_mirrors_exit_and_maps_signals_to_128_plus() -> None:
    assert pid1.exit_code(0) == 0
    assert pid1.exit_code(5 << 8) == 5
    assert pid1.exit_code(signal.SIGKILL) == 128 + signal.SIGKILL


def test_supervise_mirrors_child_exit_code(restore_signals) -> None:
    pid = _fork(lambda: os._exit(7))
    assert pid1.supervise(pid) == 7


def test_supervise_reports_signal_death_as_128_plus_signum(restore_signals) -> None:
    pid = _fork(lambda: os.kill(os.getpid(), signal.SIGKILL))
    assert pid1.supervise(pid) == 128 + signal.SIGKILL


def test_supervise_forwards_signals_to_the_child(restore_signals) -> None:
    r, w = os.pipe()

    def child() -> None:
        signal.signal(signal.SIGTERM, lambda *_: os._exit(3))
        os.write(w, b"1")
        while True:
            signal.pause()

    pid = _fork(child)
    os.close(w)
    assert os.read(r, 1) == b"1"
    os.close(r)
    original = signal.getsignal(signal.SIGTERM)

    def send_when_armed() -> None:
        while signal.getsignal(signal.SIGTERM) is original:
            time.sleep(0.005)
        os.kill(os.getpid(), signal.SIGTERM)

    threading.Thread(target=send_when_armed).start()
    assert pid1.supervise(pid) == 3


def test_supervise_keeps_reaping_orphans_until_the_child_exits(restore_signals) -> None:
    events = iter([(4242, 0), (4243, signal.SIGKILL), (77, 5 << 8)])
    seen: list[int] = []

    def waitpid(pid: int, options: int) -> tuple[int, int]:
        assert (pid, options) == (-1, 0)
        event = next(events)
        seen.append(event[0])
        return event

    assert pid1.supervise(77, waitpid=waitpid, kill=lambda *_: None) == 5
    assert seen == [4242, 4243, 77]


def test_supervise_without_children_reports_failure(restore_signals) -> None:
    def waitpid(pid: int, options: int) -> tuple[int, int]:
        raise ChildProcessError

    assert pid1.supervise(1, waitpid=waitpid, kill=lambda *_: None) == 1


def test_run_exits_with_the_child_code(restore_signals, quiet_parent) -> None:
    with pytest.raises(SystemExit) as exc:
        pid1.run(lambda: os._exit(5))
    assert exc.value.code == 5


def test_run_child_system_exit_is_mirrored(restore_signals, quiet_parent) -> None:
    def leave() -> None:
        raise SystemExit(4)

    with pytest.raises(SystemExit) as exc:
        pid1.run(leave)
    assert exc.value.code == 4


def test_run_child_normal_return_exits_zero(restore_signals, quiet_parent) -> None:
    with pytest.raises(SystemExit) as exc:
        pid1.run(lambda: None)
    assert exc.value.code == 0


def test_run_child_exception_exits_one_with_traceback(
    restore_signals, quiet_parent, capfd: pytest.CaptureFixture[str],
) -> None:
    def boom() -> None:
        raise RuntimeError("boom")

    with pytest.raises(SystemExit) as exc:
        pid1.run(boom)
    assert exc.value.code == 1
    assert "RuntimeError: boom" in capfd.readouterr().err


def test_daemon_start_stands_in_as_init_only_when_pid1(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[object] = []
    monkeypatch.setattr(pid1, "run", lambda child: calls.append(child))
    monkeypatch.setattr(cli, "_serve_daemon", lambda root: calls.append(("serve", root)))

    monkeypatch.setattr(pid1, "is_pid1", lambda: True)
    result = CliRunner().invoke(cli.main, ["daemon", "start"])
    assert result.exit_code == 0, result.output
    assert len(calls) == 1 and callable(calls[0])
    calls[0]()
    assert calls[1] == ("serve", cli._root())

    calls.clear()
    monkeypatch.setattr(pid1, "is_pid1", lambda: False)
    result = CliRunner().invoke(cli.main, ["daemon", "start"])
    assert result.exit_code == 0, result.output
    assert calls == [("serve", cli._root())]
