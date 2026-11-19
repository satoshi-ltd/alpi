from __future__ import annotations

import os
import signal
import stat
import subprocess
import sys
import textwrap

import pytest

from alpi import pid1

PROBE = textwrap.dedent("""
    import os, signal, sys, threading, time
    from pathlib import Path
    from alpi import service
    root = Path(sys.argv[1])
    path = service.register_stack_dump(root)
    hold = threading.Event()
    def parked_worker_for_the_dump():
        hold.wait(10)
    threading.Thread(target=parked_worker_for_the_dump, name="parked", daemon=True).start()
    time.sleep(0.2)
    os.kill(os.getpid(), signal.SIGUSR1)
    time.sleep(0.2)
    hold.set()
    print(path)
""")


@pytest.mark.skipif(not hasattr(signal, "SIGUSR1"), reason="needs SIGUSR1")
def test_sigusr1_writes_every_thread_stack_to_a_private_file_and_the_process_keeps_running(tmp_path):
    root = tmp_path / ".alpi"
    env = {**os.environ, "HOME": str(tmp_path), "ALPI_SKIP_UPDATE_CHECK": "1"}
    env.pop("ALPI_HOME", None)
    done = subprocess.run([sys.executable, "-c", PROBE, str(root)], capture_output=True, text=True, timeout=120, env=env)
    assert done.returncode == 0, done.stderr
    path = root / "logs" / "stacks.log"
    assert done.stdout.strip() == str(path)
    text = path.read_text()
    assert "parked_worker_for_the_dump" in text
    assert "Current thread 0x" in text and text.count("hread 0x") >= 2
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_the_container_init_forwards_sigusr1_to_the_daemon():
    assert signal.SIGUSR1 in pid1._FORWARDED


def test_the_daemon_registers_the_dump_once_it_owns_the_singleton_lock(tmp_path, monkeypatch):
    from alpi import service

    order = []

    class Lock:
        def close(self):
            pass

    monkeypatch.setattr(service, "_configure_logging_daemon", lambda root: None)
    monkeypatch.setattr(service, "_acquire_singleton_lock", lambda root: order.append("lock") or Lock())
    monkeypatch.setattr(service, "register_stack_dump", lambda root: order.append("dump"))
    monkeypatch.setattr(service, "_set_proctitle_daemon", lambda n: None)
    monkeypatch.setattr(service, "_write_daemon_pid", lambda root: None)
    monkeypatch.setattr(service, "_clear_daemon_pid", lambda root: None)
    monkeypatch.setattr(service.asyncio, "run", lambda coro: coro.close())
    monkeypatch.setattr("alpi.provider_pause.activate", lambda: None)
    service.serve_all(tmp_path)
    assert order == ["lock", "dump"]
