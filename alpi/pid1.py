from __future__ import annotations

import logging
import os
import signal
import sys
from collections.abc import Callable

log = logging.getLogger("alpi.pid1")

_FORWARDED = tuple(
    sig for sig in (
        getattr(signal, name, None)
        for name in ("SIGTERM", "SIGINT", "SIGHUP", "SIGQUIT", "SIGUSR1", "SIGUSR2")
    )
    if sig is not None
)


def is_pid1() -> bool:
    return os.getpid() == 1


def run(child: Callable[[], None]) -> None:
    sys.stdout.flush()
    sys.stderr.flush()
    pid = os.fork()
    if pid == 0:
        os._exit(_run_child(child))
    _configure_logging()
    _set_proctitle()
    log.info("init: daemon pid=%d", pid)
    code = supervise(pid)
    log.info("init: daemon exited code=%d", code)
    sys.exit(code)


def supervise(
    child_pid: int,
    *,
    waitpid: Callable[[int, int], tuple[int, int]] = os.waitpid,
    kill: Callable[[int, int], None] = os.kill,
) -> int:
    def forward(signum: int, _frame: object) -> None:
        try:
            kill(child_pid, signum)
        except ProcessLookupError:
            pass

    for sig in _FORWARDED:
        signal.signal(sig, forward)
    while True:
        try:
            pid, status = waitpid(-1, 0)
        except ChildProcessError:
            return 1
        if pid == child_pid:
            return exit_code(status)
        log.info("init: reaped orphan pid=%d code=%d", pid, exit_code(status))


def exit_code(status: int) -> int:
    code = os.waitstatus_to_exitcode(status)
    return code if code >= 0 else 128 - code


def _run_child(child: Callable[[], None]) -> int:
    code = 0
    try:
        child()
    except SystemExit as e:
        if isinstance(e.code, int):
            code = e.code
        elif e.code is not None:
            print(e.code, file=sys.stderr)
            code = 1
    except BaseException:  # noqa: BLE001
        import traceback

        traceback.print_exc()
        code = 1
    sys.stdout.flush()
    sys.stderr.flush()
    logging.shutdown()
    return code


def _configure_logging() -> None:
    from alpi._log import FORMAT

    logging.basicConfig(
        level=logging.INFO, format=FORMAT, handlers=[logging.StreamHandler()], force=True,
    )


def _set_proctitle() -> None:
    try:
        import setproctitle

        setproctitle.setproctitle("alpi (init)")
    except Exception:  # noqa: BLE001
        pass
