import re
from pathlib import Path

import pytest

from alpi.core.execution_world import DockerExecutionWorld, ExecutionWorld, current, use
from alpi.core.run_context import RunContext
from alpi.tools.terminal import Terminal


def _context(tmp_path: Path) -> RunContext:
    workspace = tmp_path / "workspace"
    home = tmp_path / "home"
    workspace.mkdir()
    home.mkdir()
    return RunContext("run", home, workspace, "default", "user", "s", "host")


def test_local_world_is_identity_and_context_scoped(tmp_path: Path) -> None:
    context = _context(tmp_path)
    world = ExecutionWorld(context)
    assert current() is None
    with use(world):
        assert current() is world
        assert world.filesystem_path(context.workspace) == context.workspace
    assert current() is None


def test_docker_world_preserves_paths_and_disables_network(tmp_path: Path, monkeypatch) -> None:
    context = _context(tmp_path)
    monkeypatch.setattr(
        "alpi.core.execution_world.shutil.which", lambda name, **kwargs: "/usr/bin/docker",
    )
    world = DockerExecutionWorld(context=context, image="alpi-test:1")
    args = world.command("pwd", context.workspace, ("PATH", "ALPI_HOME"))
    assert args[:7] == ["docker", "run", "--rm", "-i", "--network", "none", "--volume"]
    assert ["--workdir", str(context.workspace)] == args[args.index("--workdir"):args.index("--workdir") + 2]
    assert args[-4:] == ["alpi-test:1", "/bin/sh", "-lc", "pwd"]


def test_docker_world_names_container_and_validates_inputs(tmp_path: Path, monkeypatch) -> None:
    context = _context(tmp_path)
    monkeypatch.setattr(
        "alpi.core.execution_world.shutil.which", lambda name, **kwargs: "/usr/bin/docker",
    )
    args = DockerExecutionWorld(context=context).command(
        "pwd", context.workspace, (), container_name="alpi-test",
    )
    assert args[args.index("--name"):args.index("--name") + 2] == ["--name", "alpi-test"]
    with pytest.raises(RuntimeError, match="image reference"):
        DockerExecutionWorld(context=context, image="--privileged").command(
            "pwd", context.workspace, (),
        )
    with pytest.raises(RuntimeError, match="cwd is not a directory"):
        DockerExecutionWorld(context=context).command("pwd", tmp_path / "missing", ())


def test_docker_world_fails_cleanly_without_cli(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("alpi.core.execution_world.shutil.which", lambda name, **kwargs: None)
    with pytest.raises(RuntimeError, match="docker CLI"):
        DockerExecutionWorld(context=_context(tmp_path)).command("true", tmp_path, ())


def test_terminal_refuses_background_in_ephemeral_docker_world(tmp_path: Path) -> None:
    with use(DockerExecutionWorld(context=_context(tmp_path))):
        result = Terminal().run(action="background", command="sleep 30")

    assert not result.ok
    assert "background commands are unavailable" in (result.error or "")


def test_terminal_timeout_force_removes_docker_container(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import subprocess
    from types import SimpleNamespace
    from alpi.tools import terminal as terminal_mod

    context = _context(tmp_path)
    monkeypatch.setenv("ALPI_HOME", str(context.home))
    monkeypatch.setattr(
        "alpi.core.execution_world.shutil.which", lambda name, **kwargs: "/usr/bin/docker",
    )
    monkeypatch.setattr(
        terminal_mod, "approval_check",
        lambda command, cwd=None: SimpleNamespace(allowed=True),
    )
    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)
        if args[:2] == ["docker", "run"]:
            raise subprocess.TimeoutExpired(args, 1)
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(terminal_mod.subprocess, "run", fake_run)
    with use(DockerExecutionWorld(context=context)):
        result = Terminal().run(
            command="sleep 30", timeout=1, cwd=str(context.workspace),
        )

    assert not result.ok and "Timed out" in (result.error or "")
    container_name = calls[0][calls[0].index("--name") + 1]
    assert re.fullmatch(r"alpi-[a-f0-9]{32}", container_name)
    assert calls[-1] == ["docker", "rm", "-f", container_name]


def test_docker_world_keeps_search_out_of_host_subprocesses(tmp_path: Path, monkeypatch) -> None:
    from alpi.tools.search import _can_use_local_rg

    monkeypatch.setattr("alpi.tools.search.shutil.which", lambda name: "/usr/bin/rg")
    with use(DockerExecutionWorld(context=_context(tmp_path))):
        assert _can_use_local_rg() is False
