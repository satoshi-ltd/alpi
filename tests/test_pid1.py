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


@pytest.fixture
def blocked_update_check(monkeypatch: pytest.MonkeyPatch):
    from alpi import updater

    started = threading.Event()
    release = threading.Event()

    def check() -> None:
        started.set()
        release.wait(10)

    monkeypatch.delenv("ALPI_SKIP_UPDATE_CHECK", raising=False)
    monkeypatch.setattr(updater, "refresh_cache_if_stale", check)
    yield started
    release.set()
    for thread in threading.enumerate():
        if thread.name == "alpi-update-check":
            thread.join(5)


def _update_check_threads() -> list[str]:
    return [t.name for t in threading.enumerate() if t.name == "alpi-update-check"]


def test_pid1_forks_the_daemon_before_the_update_check_thread_exists(
    monkeypatch: pytest.MonkeyPatch, blocked_update_check: threading.Event,
) -> None:
    at_fork: list[list[str]] = []
    children: list[Callable[[], None]] = []

    def run(child: Callable[[], None]) -> None:
        at_fork.append(_update_check_threads())
        children.append(child)

    monkeypatch.setattr(pid1, "is_pid1", lambda: True)
    monkeypatch.setattr(pid1, "run", run)
    monkeypatch.setattr(cli, "_serve_daemon", lambda root: None)

    result = CliRunner().invoke(cli.main, ["daemon", "start"])

    assert result.exit_code == 0, result.output
    assert at_fork == [[]]
    assert not blocked_update_check.is_set()
    children[0]()
    assert blocked_update_check.wait(5)


def test_a_daemon_that_is_not_pid1_still_checks_for_updates(
    monkeypatch: pytest.MonkeyPatch, blocked_update_check: threading.Event,
) -> None:
    monkeypatch.setattr(pid1, "is_pid1", lambda: False)
    monkeypatch.setattr(cli, "_serve_daemon", lambda root: None)

    result = CliRunner().invoke(cli.main, ["daemon", "start"])

    assert result.exit_code == 0, result.output
    assert blocked_update_check.wait(5)


def test_pid1_running_another_command_still_checks_for_updates(
    monkeypatch: pytest.MonkeyPatch, blocked_update_check: threading.Event,
) -> None:
    monkeypatch.setattr(pid1, "is_pid1", lambda: True)

    result = CliRunner().invoke(cli.main, ["profile", "list"])

    assert result.exit_code == 0, result.output
    assert blocked_update_check.wait(5)


def test_run_names_the_threads_it_forks_with(
    restore_signals, quiet_parent, capfd: pytest.CaptureFixture[str],
) -> None:
    release = threading.Event()
    straggler = threading.Thread(target=release.wait, args=(10,), name="straggler-import", daemon=True)
    straggler.start()
    try:
        with pytest.raises(SystemExit):
            pid1.run(lambda: None)
    finally:
        release.set()
        straggler.join(5)
    assert "straggler-import" in capfd.readouterr().err


def test_run_is_silent_when_it_forks_alone(tmp_path) -> None:
    import subprocess
    import sys

    script = (
        "from alpi import pid1\n"
        "pid1._configure_logging = lambda: None\n"
        "pid1._set_proctitle = lambda: None\n"
        "pid1.run(lambda: None)\n"
    )
    env = {**os.environ, "HOME": str(tmp_path), "ALPI_HOME": str(tmp_path / ".alpi")}
    done = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=60, env=env)
    assert done.returncode == 0, done.stderr
    assert "live threads" not in done.stderr


_ENTRY_PROBE = """
import os, sys, threading
from alpi import __main__ as entry, pid1
os.getpid = lambda: 1
def run(child):
    heavy = sorted(m for m in ("alpi.cli", "litellm", "alpi.updater") if m in sys.modules)
    print("AT_FORK", sorted(t.name for t in threading.enumerate()), heavy)
    raise SystemExit(0)
pid1.run = run
sys.argv = ["alpi", *sys.argv[1:]]
entry.main()
"""


def _entry_probe(tmp_path, *argv: str) -> str:
    import subprocess
    import sys

    env = {
        **os.environ,
        "HOME": str(tmp_path),
        "ALPI_SKIP_UPDATE_CHECK": "1",
        "LITELLM_MODEL_COST_MAP_URL": "http://127.0.0.1:9/unreachable",
    }
    env.pop("ALPI_HOME", None)
    env.pop("LITELLM_LOCAL_MODEL_COST_MAP", None)
    done = subprocess.run(
        [sys.executable, "-c", _ENTRY_PROBE, *argv], capture_output=True, text=True, timeout=120, env=env,
    )
    assert done.returncode == 0, done.stderr
    return done.stdout


@pytest.mark.parametrize("argv", [
    ["daemon", "start"],
    ["--", "daemon", "start"],
    ["daemon", "--", "start"],
    ["-cp", "work", "daemon", "start"],
])
def test_the_container_entry_forks_before_the_cli_and_its_dependencies_load(tmp_path, argv: list[str]) -> None:
    assert "AT_FORK ['MainThread'] []" in _entry_probe(tmp_path, *argv)


def test_the_entry_forks_early_only_for_daemon_start(tmp_path) -> None:
    assert "AT_FORK" not in _entry_probe(tmp_path, "--version")
    assert "AT_FORK" not in _entry_probe(tmp_path, "daemon", "stop")


@pytest.mark.parametrize("argv,early", [
    (["daemon", "start"], True),
    (["-p", "work", "daemon", "start"], True),
    (["-pwork", "daemon", "start"], True),
    (["--profile", "work", "daemon", "start"], True),
    (["--profile=work", "daemon", "start"], True),
    (["-c", "daemon", "start"], True),
    (["--continue", "-p", "work", "daemon", "start"], True),
    (["daemon", "start", "--help"], True),
    (["--", "daemon", "start"], True),
    (["daemon", "--", "start"], True),
    (["-cp", "work", "daemon", "start"], True),
    (["-cpwork", "daemon", "start"], True),
    (["-pc", "daemon", "start"], True),
    (["-c", "--", "daemon", "--", "start"], True),
    (["-cx", "daemon", "start"], False),
    (["--", "--", "daemon", "start"], False),
    (["daemon", "--", "stop"], False),
    (["daemon"], False),
    (["daemon", "stop"], False),
    (["daemon", "status"], False),
    (["daemon", "restart"], False),
    (["-p", "daemon", "start"], False),
    (["-p"], False),
    (["--unknown", "daemon", "start"], False),
    (["chat", "daemon", "start"], False),
    (["update"], False),
    ([], False),
])
def test_only_a_daemon_start_is_recognised_whatever_global_options_precede_it(argv: list[str], early: bool) -> None:
    from alpi import __main__ as entry

    assert entry._starts_daemon(argv) is early


def test_the_real_entry_forks_and_mirrors_what_the_cli_does_in_the_child(tmp_path) -> None:
    import subprocess
    import sys

    script = (
        "import os, sys\n"
        "me, real = os.getpid(), os.getpid\n"
        "os.getpid = lambda: 1 if real() == me else real()\n"
        "from alpi import __main__ as entry, pid1\n"
        "pid1._set_proctitle = lambda: None\n"
        "sys.argv = ['alpi', '-p', 'work', 'daemon', 'start', '--help']\n"
        "entry.main()\n"
    )
    env = {
        **os.environ,
        "HOME": str(tmp_path),
        "ALPI_SKIP_UPDATE_CHECK": "1",
        "LITELLM_MODEL_COST_MAP_URL": "http://127.0.0.1:9/unreachable",
    }
    env.pop("ALPI_HOME", None)
    env.pop("LITELLM_LOCAL_MODEL_COST_MAP", None)
    done = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=120, env=env)
    assert done.returncode == 0, done.stderr
    assert "Run the daemon in the foreground." in done.stdout
    assert "init: daemon pid=" in done.stderr
    assert "live threads" not in done.stderr


def test_the_entry_hands_the_cli_to_the_forked_child(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys

    from alpi import __main__ as entry

    seen: list[object] = []

    def run(child: Callable[[], None]) -> None:
        seen.append(child)
        raise SystemExit(0)

    monkeypatch.setattr(os, "getpid", lambda: 1)
    monkeypatch.setattr(pid1, "run", run)
    monkeypatch.setattr(sys, "argv", ["alpi", "daemon", "start"])
    with pytest.raises(SystemExit):
        entry.main()
    assert seen == [entry._cli]
