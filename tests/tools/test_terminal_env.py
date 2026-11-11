from __future__ import annotations

import time
from pathlib import Path

import pytest
import yaml

from alpi import config as cfg_mod
from alpi.home import reset_active_home, set_active_home
from alpi.tools import _state, terminal


def _home(tmp_home_no_env: Path, env: dict | None) -> Path:
    workspace = tmp_home_no_env / "workspace"
    workspace.mkdir(exist_ok=True)
    data = {"workspace": str(workspace)}
    if env is not None:
        data["tools"] = {"terminal": {"env": env}}
    (tmp_home_no_env / "config.yaml").write_text(yaml.safe_dump(data))
    _state.reset_skill_env()
    return tmp_home_no_env


@pytest.fixture
def toolchain(tmp_path: Path) -> Path:
    bin_dir = tmp_path / "toolchains" / "jdk" / "bin"
    bin_dir.mkdir(parents=True)
    java = bin_dir / "java"
    java.write_text("#!/bin/sh\necho \"volume java $JAVA_HOME\"\n")
    java.chmod(0o755)
    return bin_dir


def _env_for(home: Path) -> dict[str, str]:
    token = set_active_home(home)
    try:
        return terminal._build_subprocess_env()
    finally:
        reset_active_home(token)


def test_a_profile_without_the_map_gets_the_same_environment(tmp_home_no_env: Path, monkeypatch) -> None:
    home = _home(tmp_home_no_env, None)
    with_map_code = _env_for(home)
    monkeypatch.setattr(terminal, "_profile_env", lambda: ({}, ""))
    assert _env_for(home) == with_map_code
    assert _env_for(_home(tmp_home_no_env, {})) == with_map_code


def test_the_map_is_applied_with_path_prepended(tmp_home_no_env: Path, toolchain: Path) -> None:
    plain = _env_for(_home(tmp_home_no_env, None))
    env = _env_for(_home(tmp_home_no_env, {"JAVA_HOME": str(toolchain.parent), "PATH": str(toolchain)}))
    assert env["JAVA_HOME"] == str(toolchain.parent)
    assert env["PATH"] == f"{toolchain}:{plain['PATH']}"


def test_protected_and_invalid_entries_never_reach_the_command(tmp_home_no_env: Path) -> None:
    home = _home(tmp_home_no_env, {
        "ALPI_HOME": "/forged", "ALPI_AUTHORITY": "admin", "HOME": "/", "TMPDIR": "/x", "WORKSPACE": "/y",
        "bad key": "v", "NUMBER": 3, "MULTI": "a\nb", "OK": "yes",
    })
    env = _env_for(home)
    assert env["ALPI_HOME"] == str(home)
    assert env["OK"] == "yes"
    assert "ALPI_AUTHORITY" not in env or env["ALPI_AUTHORITY"] != "admin"
    assert not {"NUMBER", "MULTI", "bad key"} & set(env)
    assert env.get("HOME") != "/" and env.get("TMPDIR") != "/x" and env.get("WORKSPACE") != "/y"
    assert cfg_mod.load(home).tools.terminal.env == {"OK": "yes"}


def test_values_are_literal_and_never_expand_other_variables(tmp_home_no_env: Path, monkeypatch) -> None:
    monkeypatch.setenv("SECRET_KEY", "s3cret")
    env = _env_for(_home(tmp_home_no_env, {"PROBE": "$SECRET_KEY"}))
    assert env["PROBE"] == "$SECRET_KEY"


def test_foreground_and_background_commands_find_the_volume_toolchain(tmp_home_no_env: Path, toolchain: Path) -> None:
    home = _home(tmp_home_no_env, {"JAVA_HOME": str(toolchain.parent), "PATH": str(toolchain)})
    token = set_active_home(home)
    try:
        result = terminal.Terminal().run(command="java -version")
        assert result.ok, result.error
        assert f"volume java {toolchain.parent}" in result.output
        started = terminal.Terminal().run(action="background", command="java -version")
        assert started.ok, started.error
        pid = int(started.output.split("pid=", 1)[1].split()[0])
        for _ in range(200):
            out = terminal.Terminal().run(action="output", pid=pid)
            if "volume java" in (out.output or ""):
                break
            time.sleep(0.05)
        assert "volume java" in out.output
    finally:
        reset_active_home(token)


def test_the_docker_backend_forwards_the_map_and_prepends_path_inside_the_image(tmp_home_no_env: Path, monkeypatch) -> None:
    from alpi.core.execution_world import DockerExecutionWorld
    from alpi.core.run_context import RunContext

    home = _home(tmp_home_no_env, {"JAVA_HOME": "/data/toolchains/jdk", "PATH": "/data/toolchains/jdk/bin"})
    workspace = home / "workspace"
    context = RunContext(home=home, workspace=workspace, run_id="r1", profile="default", source="host", connection_id="host", session_id="s1")
    world = DockerExecutionWorld(context=context)
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/docker")
    monkeypatch.setattr("alpi.core.execution_world.current", lambda: world)
    token = set_active_home(home)
    try:
        args = terminal._resolve_popen_args("java -version", str(workspace))
    finally:
        reset_active_home(token)
    joined = " ".join(args)
    assert "--env JAVA_HOME" in joined
    assert args[-1] == "PATH=/data/toolchains/jdk/bin:\"$PATH\"; export PATH; java -version"


@pytest.mark.integration
@pytest.mark.skipif(__import__("sys").platform != "darwin" or __import__("shutil").which("sandbox-exec") is None,
                    reason="needs macOS sandbox-exec")
def test_the_native_sandbox_still_sees_the_profile_environment(tmp_home_no_env: Path, toolchain: Path) -> None:
    home = _home(tmp_home_no_env, {"PROBE_VALUE": "inside"})
    data = yaml.safe_load((home / "config.yaml").read_text())
    data["tools"]["terminal"]["sandbox"] = True
    (home / "config.yaml").write_text(yaml.safe_dump(data))
    token = set_active_home(home)
    try:
        result = terminal.Terminal().run(command="printf %s \"$PROBE_VALUE\"")
    finally:
        reset_active_home(token)
    assert result.ok, result.error
    assert "inside" in result.output



@pytest.mark.parametrize("path", ["bin", "/opt/jdk/bin:", ":/opt/jdk/bin", "/opt/jdk/bin::/usr/bin", "./node_modules/.bin"])
def test_a_relative_or_empty_path_entry_is_refused(tmp_home_no_env: Path, path: str) -> None:
    home = _home(tmp_home_no_env, {"PATH": path})
    assert "PATH" not in cfg_mod.load(home).tools.terminal.env


@pytest.mark.parametrize("key", ["LD_PRELOAD", "LD_LIBRARY_PATH", "DYLD_INSERT_LIBRARIES", "DOCKER_HOST", "DOCKER_CONFIG", "BASH_ENV", "ENV", "IFS"])
def test_variables_that_steer_the_launcher_or_the_shell_are_refused(tmp_home_no_env: Path, key: str) -> None:
    home = _home(tmp_home_no_env, {key: "/tmp/x"})
    assert key not in cfg_mod.load(home).tools.terminal.env


def test_the_sandbox_launcher_is_found_with_the_daemons_path_not_the_profiles(tmp_home_no_env: Path, tmp_path: Path, monkeypatch) -> None:
    fake_dir = tmp_path / "evil"
    fake_dir.mkdir()
    for name in ("sandbox-exec", "bwrap", "docker"):
        fake = fake_dir / name
        fake.write_text("#!/bin/sh\necho UNSANDBOXED\n")
        fake.chmod(0o755)
    real = tmp_path / "real"
    real.mkdir()
    for name in ("sandbox-exec", "bwrap", "docker"):
        launcher = real / name
        launcher.write_text("#!/bin/sh\necho REAL\n")
        launcher.chmod(0o755)
    monkeypatch.setenv("PATH", f"{real}:/usr/bin:/bin")
    assert terminal._pinned(["sandbox-exec", "-p", "x"])[0] == str(real / "sandbox-exec")
    assert terminal._pinned(["bwrap", "--ro-bind"])[0] == str(real / "bwrap")
    assert terminal._pinned("echo plain") == "echo plain"
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    with pytest.raises(terminal.SandboxUnavailable):
        terminal._pinned(["definitely-not-a-launcher-xyz"])


def test_a_member_turn_does_not_get_the_owner_environment(tmp_home_no_env: Path, monkeypatch) -> None:
    home = _home(tmp_home_no_env, {"OWNER_ONLY": "yes"})
    monkeypatch.setattr(terminal, "_is_member", lambda: True)
    assert "OWNER_ONLY" not in _env_for(home)


def test_a_skill_declared_value_wins_over_a_same_named_profile_entry(tmp_home_no_env: Path, monkeypatch) -> None:
    home = _home(tmp_home_no_env, {"GITHUB_TOKEN": "from-config"})
    monkeypatch.setenv("GITHUB_TOKEN", "from-skill-env")
    monkeypatch.setattr(_state, "get_active_skills_env", lambda: {"GITHUB_TOKEN"})
    assert _env_for(home)["GITHUB_TOKEN"] == "from-skill-env"


def test_saving_the_config_keeps_entries_it_refused(tmp_home_no_env: Path) -> None:
    home = _home(tmp_home_no_env, {"PORT": 8080, "OK": "yes"})
    cfg = cfg_mod.load(home)
    cfg.public_bio = "changed"
    cfg_mod.save(cfg)
    saved = yaml.safe_load((home / "config.yaml").read_text())
    assert saved["tools"]["terminal"]["env"] == {"PORT": 8080, "OK": "yes"}



def test_a_profile_path_never_picks_the_launcher_of_a_real_command(tmp_home_no_env: Path, tmp_path: Path, monkeypatch) -> None:
    evil = tmp_path / "evil"
    real = tmp_path / "real"
    for folder, word in ((evil, "UNSANDBOXED"), (real, "REAL")):
        folder.mkdir()
        launcher = folder / "fake-launcher"
        launcher.write_text(f"#!/bin/sh\necho {word}\n")
        launcher.chmod(0o755)
    monkeypatch.setenv("PATH", f"{real}:/usr/bin:/bin")
    home = _home(tmp_home_no_env, {"PATH": str(evil)})
    monkeypatch.setattr(terminal, "_resolve_popen_args", lambda *a, **kw: ["fake-launcher"])
    token = set_active_home(home)
    try:
        fg = terminal.Terminal().run(command="ignored")
        bg = terminal.Terminal().run(action="background", command="ignored")
        pid = int(bg.output.split("pid=", 1)[1].split()[0])
        for _ in range(200):
            out = terminal.Terminal().run(action="output", pid=pid)
            if "REAL" in (out.output or "") or "UNSANDBOXED" in (out.output or ""):
                break
            time.sleep(0.05)
    finally:
        reset_active_home(token)
    assert "REAL" in fg.output and "UNSANDBOXED" not in fg.output
    assert "REAL" in out.output and "UNSANDBOXED" not in out.output


def test_the_host_docker_cli_keeps_the_daemons_path_in_the_docker_world(tmp_home_no_env: Path, monkeypatch) -> None:
    from alpi.core.execution_world import DockerExecutionWorld
    from alpi.core.run_context import RunContext

    home = _home(tmp_home_no_env, {"PATH": "/workspace/bin", "JAVA_HOME": "/data/jdk"})
    context = RunContext(home=home, workspace=home / "workspace", run_id="r1", profile="default", source="host", connection_id="host", session_id="s1")
    monkeypatch.setattr("alpi.core.execution_world.current", lambda: DockerExecutionWorld(context=context))
    env = _env_for(home)
    assert "/workspace/bin" not in env.get("PATH", "")
    assert env["JAVA_HOME"] == "/data/jdk"
