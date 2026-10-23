from pathlib import Path
import re
import shlex
import tomllib

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[2]
PIP_BOOTSTRAP = "pip==26.2.1"


def _cooldown_days() -> int:
    span = tomllib.loads((ROOT / "pyproject.toml").read_text())["tool"]["uv"]["exclude-newer"]
    match = re.fullmatch(r"(\d+) days", span)
    assert match, span
    return int(match.group(1))


def _commands(script):
    return [
        shlex.split(line)
        for line in re.split(r"&&|;|\n", script.replace("\\\n", " "))
        if re.match(r"^\s*(?:RUN (?:--\S+ )*)?(?:sudo )?(?:python3? -m pip|pip3?|uv|uvx)\s", line)
    ]


def _check_pip(command):
    command = command[1:] if command[0] == "sudo" else command
    args = command[command.index("install") + 1 :]
    if PIP_BOOTSTRAP in args:
        assert args == ["--upgrade", PIP_BOOTSTRAP], command
    else:
        assert ["--uploaded-prior-to", f"P{_cooldown_days()}D"] == args[:2], command


def test_uv_lock_records_the_pyproject_cooldown():
    lock = tomllib.loads((ROOT / "uv.lock").read_text())
    assert lock["options"]["exclude-newer-span"] == f"P{_cooldown_days()}D"


def test_docker_image_installs_with_the_same_cooldown():
    commands = _commands((ROOT / "docker/Dockerfile").read_text())
    installs = [command for command in commands if "pip" in command and "install" in command]
    assert len(installs) == 2
    for command in installs:
        _check_pip(command)


@pytest.mark.parametrize("name", ["pull-request.yml", "publish.yml"])
def test_ci_installs_with_the_same_cooldown(name):
    workflow = yaml.safe_load((ROOT / ".github/workflows" / name).read_text())
    installs = []
    for job in workflow["jobs"].values():
        for step in job.get("steps", []):
            installs.extend(
                command
                for command in _commands(step.get("run", ""))
                if "pip" in command and "install" in command
            )
    assert len(installs) == (4 if name == "pull-request.yml" else 2)
    for command in installs:
        _check_pip(command)


def test_release_build_tools_and_smoke_install_use_the_cooldown():
    workflow = yaml.safe_load((ROOT / ".github/workflows/publish.yml").read_text())
    commands = [
        command
        for job in workflow["jobs"].values()
        for step in job.get("steps", [])
        for command in _commands(step.get("run", ""))
        if command[0] in ("uv", "uvx")
    ]
    assert len(commands) == 3
    for command in commands:
        index = command.index("--exclude-newer") if "--exclude-newer" in command else -1
        assert index >= 0, command
        assert command[index + 1] == f"{_cooldown_days()} days", command


def test_every_workflow_pip_install_uses_the_cooldown():
    for path in sorted((ROOT / ".github/workflows").glob("*.yml")):
        workflow = yaml.safe_load(path.read_text())
        for job in workflow["jobs"].values():
            for step in job.get("steps", []):
                for command in _commands(step.get("run", "")):
                    if "install" in command and any(word.startswith("pip") for word in command[:4]):
                        _check_pip(command)
