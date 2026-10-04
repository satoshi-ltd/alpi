from __future__ import annotations

import os
import shutil
import signal
import socket
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import pytest

from alpi.core.execution_world import DockerExecutionWorld
from alpi.core.run_context import RunContext
from alpi.host.connection_context import ConnectionContext, use
from alpi.tools import _sandbox, _state, terminal

MEMBER = ConnectionContext(connection_id="c1", device_id="d1", source="remote", role="member")
OTHER_MEMBER = ConnectionContext(connection_id="c2", device_id="d2", source="remote", role="member")
ADMIN = ConnectionContext(connection_id="c1", device_id="d1", source="remote", role="admin")

SANDBOX = sys.platform.startswith("linux") and shutil.which("bwrap") is not None
needs_sandbox = pytest.mark.skipif(not SANDBOX, reason="needs bwrap (Linux)")
SECRETS = ("TOPSECRET", "OTHERSECRET", "ENVSECRET", "CHUNKSECRET")


@pytest.fixture
def home(tmp_path: Path, monkeypatch) -> Path:
    root = tmp_path / "alpi"
    ws = tmp_path / "ws"
    root.mkdir()
    ws.mkdir()
    monkeypatch.setenv("ALPI_HOME", str(root))
    monkeypatch.chdir(ws)
    (root / "config.yaml").write_text(f"workspace: {ws}\n")
    (root / "sessions").mkdir()
    (root / "sessions" / "s1.json").write_text('{"text": "TOPSECRET"}')
    other = root / "profiles" / "doc" / "runs"
    other.mkdir(parents=True)
    (other / "r1.jsonl").write_text("OTHERSECRET\n")
    (root / ".env").write_text("GMAIL_TOKEN=ENVSECRET\n")
    db = sqlite3.connect(root / "knowledge.sqlite")
    db.execute("create table session_chunks(content text)")
    db.execute("insert into session_chunks values ('CHUNKSECRET')")
    db.commit()
    db.close()
    return root


def _platform(monkeypatch, name: str, binary: str | None) -> None:
    monkeypatch.setattr(_sandbox.shutil, "which", lambda _name: binary)
    monkeypatch.setattr(_sandbox, "sys", type("S", (), {"platform": name})())


def test_linux_member_sandbox_never_mounts_the_alpi_home(home: Path, monkeypatch) -> None:
    _platform(monkeypatch, "linux", "/usr/bin/bwrap")
    ws = home.parent / "ws"
    args = _sandbox.wrap_command("ls", workspace=ws, alpi_home=home, allow_network=False, member_root=home)
    assert not any(a.startswith(str(home)) or a.startswith(str(home.resolve())) for a in args)
    assert not any(a.startswith(str(Path.home())) for a in args)
    assert "--unshare-pid" in args
    assert str(home) in _sandbox.wrap_command("ls", workspace=ws, alpi_home=home, allow_network=False)


def test_macos_never_sandboxes_a_member_because_it_cannot_hide_other_processes(home: Path, monkeypatch) -> None:
    _platform(monkeypatch, "darwin", "/usr/bin/sandbox-exec")
    with pytest.raises(_sandbox.SandboxUnavailable, match="other processes"):
        _sandbox.wrap_command("ls", workspace=home.parent / "ws", alpi_home=home, allow_network=True, member_root=home)
    assert _sandbox.wrap_command("ls", workspace=home.parent / "ws", alpi_home=home, allow_network=True)[0] == "sandbox-exec"


@pytest.mark.integration
@pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")
def test_on_macos_a_member_command_is_refused_before_it_runs(home: Path) -> None:
    marker = home.parent / "ws" / "ran"
    with use(MEMBER):
        result = terminal.Terminal().run(command=f"touch {marker}; cat {home.resolve()}/sessions/s1.json")
    assert result.ok is False and "other processes" in result.error
    assert not marker.exists() and "TOPSECRET" not in (result.output or "")


def test_docker_world_does_not_mount_the_profile_home_for_a_member(home: Path, monkeypatch) -> None:
    monkeypatch.setattr("alpi.core.execution_world.shutil.which", lambda name: "/usr/bin/docker")
    ws = home.parent / "ws"
    world = DockerExecutionWorld(context=RunContext("r1", home, ws, "default", "user", "s1", "c1"))
    mount = f"{home.resolve()}:{home.resolve()}"
    assert mount not in world.command("ls", ws, (), member=True)
    assert mount in world.command("ls", ws, ())


@pytest.mark.parametrize("action", ["run", "background"])
def test_a_member_is_refused_before_anything_runs_when_no_sandbox_exists(home: Path, monkeypatch, action) -> None:
    monkeypatch.setattr(terminal, "_sandbox_config", lambda: (False, True))
    spawned: list[object] = []
    monkeypatch.setattr(terminal.subprocess, "Popen", lambda *a, **kw: spawned.append(a))
    _platform(monkeypatch, "linux", None)
    marker = home.parent / "ws" / "ran"
    with use(MEMBER):
        result = terminal.Terminal().run(action=action, command=f"touch {marker}")
    assert result.ok is False
    assert "member devices and to peers without a tool policy" in result.error and "sandbox=false" not in result.error
    assert spawned == [] and not marker.exists()


@pytest.mark.parametrize("where", ["workspace", "cwd"])
def test_a_member_is_refused_when_its_workspace_or_cwd_touches_the_alpi_home(home: Path, monkeypatch, where) -> None:
    monkeypatch.setattr(terminal.subprocess, "Popen", lambda *a, **kw: pytest.fail("spawned"))
    cwd = None
    if where == "workspace":
        (home / "config.yaml").write_text(f"workspace: {home.parent}\n")
    else:
        cwd = str(home / "profiles" / "doc" / "runs")
    with use(MEMBER):
        result = terminal.Terminal().run(command="ls", cwd=cwd)
    assert result.ok is False and "inside the alpi home" in result.error


def test_an_admin_keeps_the_profile_sandbox_setting(home: Path, monkeypatch) -> None:
    monkeypatch.setattr(terminal, "_sandbox_config", lambda: (False, True))
    with use(ADMIN):
        assert terminal._resolve_popen_args("cat sessions/s1.json") == "cat sessions/s1.json"


def test_a_member_shell_never_inherits_a_viewed_skills_secrets(home: Path, monkeypatch) -> None:
    monkeypatch.setenv("GMAIL_TOKEN", "ENVSECRET")
    monkeypatch.setattr(_state, "get_active_skills_env", lambda: ("GMAIL_TOKEN",))
    monkeypatch.setattr("alpi.home.effective_profile_env", lambda _home: dict(os.environ))
    with use(MEMBER):
        assert "GMAIL_TOKEN" not in terminal._build_subprocess_env()
    with use(ADMIN):
        assert terminal._build_subprocess_env()["GMAIL_TOKEN"] == "ENVSECRET"


def test_a_member_only_sees_its_own_background_jobs(home: Path) -> None:
    bg = terminal._bg_dir()
    log = bg / "theirs.log"
    log.write_text("ADMINJOB")
    (bg / "4242.meta").write_text(f"log={log}\nstarted=1\nowner=c9:d9\n")
    tool = terminal.Terminal()
    with use(MEMBER):
        for action in ("status", "output", "kill"):
            result = tool.run(action=action, pid=4242)
            assert result.ok is False and "ADMINJOB" not in result.output
    (bg / "4243.meta").write_text(f"log={log}\nstarted=1\nowner=c1:d1\n")
    with use(MEMBER):
        assert tool.run(action="output", pid=4243).output == "ADMINJOB"
    with use(OTHER_MEMBER):
        assert tool.run(action="output", pid=4243).ok is False
    with use(ADMIN):
        assert tool.run(action="output", pid=4242).output == "ADMINJOB"


@pytest.mark.integration
@needs_sandbox
@pytest.mark.parametrize("command", [
    "cat {home}/sessions/s1.json",
    "cat {home}/profiles/doc/runs/r1.jsonl",
    "cat {home}/.env",
    "sqlite3 {home}/knowledge.sqlite 'select content from session_chunks'; strings {home}/knowledge.sqlite",
    "python3 -c \"print(open('{home}/sessions/s1.json').read())\"",
    "ln -s {home}/sessions/s1.json {ws}/link; cat {ws}/link",
    "ln {home}/sessions/s1.json {ws}/hard; cat {ws}/hard",
    "cd {home} && grep -r SECRET .",
    "mv {home}/profiles/doc {home}/profiles/dx; cat {home}/profiles/dx/runs/r1.jsonl",
    "mv {home} {ws}/stolen; cat {ws}/stolen/sessions/s1.json",
    "mv {parent} {parent}-moved; cat {parent}-moved/alpi/sessions/s1.json",
])
def test_a_member_command_never_reads_or_moves_the_alpi_home(home: Path, command: str) -> None:
    root = home.resolve()
    with use(MEMBER):
        result = terminal.Terminal().run(
            command=command.format(home=root, ws=root.parent / "ws", parent=root.parent), timeout=30,
        )
    text = (result.output or "") + (result.error or "")
    for secret in SECRETS:
        assert secret not in text, command
    assert (root / "sessions" / "s1.json").exists() and (root / "profiles" / "doc").exists()


@pytest.mark.integration
@needs_sandbox
def test_a_member_background_job_never_reads_an_area_created_after_it_started(home: Path) -> None:
    root = home.resolve()
    with use(MEMBER):
        started = terminal.Terminal().run(action="background", command=f"sleep 2; cat {root}/profiles/late/sessions/x.json")
    pid = int(started.output.split("pid=")[1].split()[0])
    (root / "profiles" / "late" / "sessions").mkdir(parents=True)
    (root / "profiles" / "late" / "sessions" / "x.json").write_text("LATESECRET")
    deadline = time.time() + 15
    while terminal._pid_alive(pid) and time.time() < deadline:
        time.sleep(0.2)
    with use(MEMBER):
        assert "LATESECRET" not in terminal.Terminal().run(action="output", pid=pid).output


@pytest.mark.integration
@needs_sandbox
def test_a_member_command_cannot_reach_the_daemon_socket(home: Path, monkeypatch) -> None:
    import tempfile

    root = Path(tempfile.mkdtemp(prefix="ah", dir="/tmp")).resolve()
    (root / "config.yaml").write_text(f"workspace: {home.parent / 'ws'}\n")
    monkeypatch.setenv("ALPI_HOME", str(root))
    (root / "host").mkdir()
    path = root / "host" / "h.sock"
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(str(path))
    server.listen(1)
    probe = f"import socket; s=socket.socket(socket.AF_UNIX); s.connect('{path}'); print('CONNECTED')"
    try:
        with use(ADMIN):
            assert "CONNECTED" in terminal.Terminal().run(command=f"python3 -c \"{probe}\"", timeout=30).output
        with use(MEMBER):
            result = terminal.Terminal().run(command=f"python3 -c \"{probe}\"", timeout=30)
        assert "CONNECTED" not in (result.output or "")
    finally:
        server.close()
        shutil.rmtree(root, ignore_errors=True)


@pytest.mark.integration
@needs_sandbox
def test_a_member_command_cannot_signal_a_process_outside_its_sandbox(home: Path) -> None:
    outside = subprocess.Popen(["sleep", "30"])
    try:
        with use(MEMBER):
            terminal.Terminal().run(command=f"kill -TERM {outside.pid}", timeout=30)
        time.sleep(0.3)
        assert outside.poll() is None
    finally:
        outside.send_signal(signal.SIGKILL)
        outside.wait()


@pytest.mark.integration
@needs_sandbox
def test_a_member_command_in_the_workspace_still_works_and_admin_reads_its_home(home: Path) -> None:
    ws = (home.parent / "ws").resolve()
    with use(MEMBER):
        result = terminal.Terminal().run(command=f"echo hello > {ws}/a.txt && cat {ws}/a.txt", timeout=30)
    assert result.ok, result.error
    assert "hello" in result.output
    with use(ADMIN):
        assert "TOPSECRET" in terminal.Terminal().run(command=f"cat {home.resolve()}/sessions/s1.json", timeout=30).output


@pytest.mark.parametrize("target", ["linked", "ssh"])
def test_a_member_is_refused_a_workspace_inside_a_linked_profile_or_a_credentials_folder(home: Path, monkeypatch, target) -> None:
    monkeypatch.setattr(terminal.subprocess, "Popen", lambda *a, **kw: pytest.fail("spawned"))
    if target == "linked":
        real = home.parent / "disk" / "linked"
        (real / "work").mkdir(parents=True)
        (home / "profiles" / "linked").symlink_to(real)
        workspace = real / "work"
    else:
        fake_home = home.parent / "user"
        (fake_home / ".ssh").mkdir(parents=True)
        monkeypatch.setenv("HOME", str(fake_home))
        workspace = fake_home
    (home / "config.yaml").write_text(f"workspace: {workspace}\n")
    with use(MEMBER):
        result = terminal.Terminal().run(command="ls")
    assert result.ok is False and "credentials folder" in result.error


def test_a_fenced_command_is_refused_before_anyone_is_asked_to_approve_it(home: Path, monkeypatch) -> None:
    _platform(monkeypatch, "darwin", "/usr/bin/sandbox-exec")
    monkeypatch.setattr(terminal, "approval_check", lambda *a, **kw: pytest.fail("approval asked"))
    with use(MEMBER):
        assert terminal.Terminal().run(command="rm -rf build").ok is False
        assert terminal.Terminal().run(action="background", command="rm -rf build").ok is False


def test_a_recycled_pid_is_never_killed_on_an_old_jobs_authority(home: Path) -> None:
    stranger = subprocess.Popen(["sleep", "30"])
    try:
        bg = terminal._bg_dir()
        (bg / f"{stranger.pid}.meta").write_text(
            f"log={bg / 'old.log'}\nstarted=1\nowner=c1:d1\nident=Mon Jan  1 00:00:00 2001\n"
        )
        with use(MEMBER):
            result = terminal.Terminal().run(action="kill", pid=stranger.pid)
            status = terminal.Terminal().run(action="status", pid=stranger.pid)
        time.sleep(0.2)
        assert stranger.poll() is None
        assert "not running" in result.output and "running=False" in status.output
        (bg / f"{stranger.pid}.meta").write_text(
            f"log={bg / 'old.log'}\nstarted=1\nowner=c1:d1\nident={terminal._process_identity(stranger.pid)}\n"
        )
        with use(MEMBER):
            terminal.Terminal().run(action="kill", pid=stranger.pid)
        stranger.wait(timeout=5)
    finally:
        if stranger.poll() is None:
            stranger.kill()
            stranger.wait()


def test_a_linux_process_identity_is_its_boot_relative_start_tick() -> None:
    from alpi.tools import terminal

    stat = "4242 (python3 (x) y) S 1 4242 4242 0 -1 4194560 100 0 0 0 1 2 0 0 20 0 1 0 987654 1000 10"
    assert terminal._proc_start(stat) == "proc:987654"
    assert terminal._proc_start("4242 (sh) S 1") is None
