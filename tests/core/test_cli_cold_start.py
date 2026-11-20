from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HEAVY = ("litellm", "alpi.engine", "alpi.llm", "textual")

_PROBE = """
import json, sys
from alpi import cli
code = None
try:
    cli.main(sys.argv[1:], standalone_mode=False)
except SystemExit as e:
    code = e.code
except BaseException as e:
    code = type(e).__name__
sys.stdout.flush()
print("\\n" + json.dumps({{"code": code, "heavy": [m for m in {heavy!r} if m in sys.modules]}}))
"""


def _run(tmp_path: Path, code: str, *argv: str, update_check: bool = False) -> str:
    env = {**os.environ, "HOME": str(tmp_path), "ALPI_HOME": str(tmp_path / ".alpi")}
    env.pop("ALPI_PROFILE", None)
    if update_check:
        env.pop("ALPI_SKIP_UPDATE_CHECK", None)
    return subprocess.run(
        [sys.executable, "-c", code, *argv],
        capture_output=True, text=True, env=env, timeout=60, check=True,
    ).stdout


@pytest.mark.parametrize("argv", [
    ("--version",), ("--help",), ("runs", "list"), ("schedule", "list"), ("daemon", "status"), ("profile", "list"),
])
def test_short_commands_load_neither_the_engine_nor_the_model_library(tmp_path: Path, argv) -> None:
    result = json.loads(_run(tmp_path, _PROBE.format(heavy=HEAVY), *argv).strip().splitlines()[-1])
    assert result["code"] in (None, 0)
    assert result["heavy"] == []


def test_the_chat_entry_points_still_reach_the_engine(tmp_path: Path) -> None:
    code = (
        "import sys\n"
        "import alpi.tui\n"
        "assert 'alpi.engine' not in sys.modules\n"
        "assert 'AlpiApp' in dir(alpi.tui)\n"
        "from alpi.tui import AlpiApp, host_client\n"
        "from textual.widgets._markdown import MarkdownBlock\n"
        "assert 'alpi.engine' in sys.modules\n"
        "assert getattr(MarkdownBlock._token_to_content, '_alpi_link_patched', False)\n"
    )
    _run(tmp_path, code)


def test_daemon_start_loads_the_engine_before_any_thread_starts(tmp_path: Path) -> None:
    code = (
        "import json, sys, threading\n"
        "from alpi import cli, service, updater\n"
        "starts = []\n"
        "_start = threading.Thread.start\n"
        "def start(self):\n"
        "    starts.append([self.name, 'alpi.engine' in sys.modules])\n"
        "    return _start(self)\n"
        "threading.Thread.start = start\n"
        "updater.refresh_cache_if_stale = lambda: None\n"
        "class Lock:\n"
        "    def close(self): pass\n"
        "async def main(root, profiles):\n"
        "    starts.append(['loop', 'alpi.engine' in sys.modules])\n"
        "service._acquire_singleton_lock = lambda root: Lock()\n"
        "service.register_stack_dump = lambda root: None\n"
        "service._set_proctitle_daemon = lambda n: None\n"
        "service._main_all = main\n"
        "try:\n"
        "    cli.main(['daemon', 'start'], standalone_mode=False)\n"
        "finally:\n"
        "    print('\\n' + json.dumps(starts))\n"
    )
    starts = json.loads(_run(tmp_path, code, update_check=True).strip().splitlines()[-1])
    assert ["alpi-update-check", True] in starts
    assert starts[-1] == ["loop", True]
    assert all(loaded for _, loaded in starts)


def test_daemon_commands_start_no_update_check_thread(tmp_path: Path) -> None:
    code = (
        "import json, threading\n"
        "from alpi import cli, updater\n"
        "names = []\n"
        "_start = threading.Thread.start\n"
        "def start(self):\n"
        "    names.append(self.name)\n"
        "    return _start(self)\n"
        "threading.Thread.start = start\n"
        "updater.refresh_cache_if_stale = lambda: None\n"
        "try:\n"
        "    cli.main(['daemon', 'status'], standalone_mode=False)\n"
        "except SystemExit:\n"
        "    pass\n"
        "print('\\n' + json.dumps(names))\n"
    )
    names = json.loads(_run(tmp_path, code, update_check=True).strip().splitlines()[-1])
    assert "alpi-update-check" not in names


def test_a_daemon_that_cannot_load_the_engine_releases_its_lock_and_writes_no_pid(monkeypatch, tmp_path: Path) -> None:
    from alpi import service

    events: list[str] = []

    class Lock:
        def close(self) -> None:
            events.append("lock released")

    monkeypatch.setitem(sys.modules, "alpi.engine", None)
    monkeypatch.setattr("alpi.provider_pause.activate", lambda: None)
    monkeypatch.setattr(service, "_configure_logging_daemon", lambda root: None)
    monkeypatch.setattr(service, "_acquire_singleton_lock", lambda root: Lock())
    monkeypatch.setattr(service, "register_stack_dump", lambda root: None)
    monkeypatch.setattr(service, "_set_proctitle_daemon", lambda n: None)
    monkeypatch.setattr(service, "_write_daemon_pid", lambda root: events.append("pid written"))
    with pytest.raises(ImportError):
        service.serve_all(tmp_path)
    assert events == ["lock released"]
