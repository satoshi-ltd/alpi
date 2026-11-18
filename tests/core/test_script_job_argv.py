from __future__ import annotations

import json
from pathlib import Path

import pytest

from alpi.scheduler import run as scheduler
from alpi.scheduler.run import validate_no_agent_command


@pytest.fixture
def home(tmp_home_no_env: Path) -> Path:
    script = tmp_home_no_env / "skills" / "a" / "b" / "scripts" / "run.py"
    script.parent.mkdir(parents=True)
    script.write_text("print('ok')\n")
    return tmp_home_no_env


SCRIPT = "$ALPI_HOME/skills/a/b/scripts/run.py"
MISSING = "$ALPI_HOME/skills/a/b/scripts/none.py"

INLINE_CODE = [
    f"python3 '-Bcopen(\"/x\",\"w\").write(\"ran\")' {MISSING}",
    f"python3 '-Bcopen(\"/x\",\"w\").write(\"ran\")' {SCRIPT}",
    f"python3 -Ic'print(1)' {SCRIPT}",
    f"python3 -uc'print(1)' {SCRIPT}",
    f"python3 -OOc'print(1)' {SCRIPT}",
    f"python3 -Bm http.server {SCRIPT}",
    f"python3 -Im http.server {SCRIPT}",
    f"python3 -c 'print(1)' {SCRIPT}",
    f"python3 -m os {SCRIPT}",
    f"python3 --command evil {SCRIPT}",
    f"python3 -X dev {SCRIPT}",
    f"python3 -W error {SCRIPT}",
    f"python3 -i {SCRIPT}",
    f"python3 -- {SCRIPT}",
    f"python3 - {SCRIPT}",
]


@pytest.mark.parametrize("command", INLINE_CODE)
def test_a_script_job_cannot_carry_inline_code_or_an_unknown_interpreter_flag(home: Path, command: str) -> None:
    assert validate_no_agent_command(command, home) is not None, command


def test_the_refusal_names_the_flag_and_what_is_allowed(home: Path) -> None:
    reason = validate_no_agent_command(f"python3 -Bcprint(1) {SCRIPT}", home)
    assert "-Bcprint(1)" in reason
    assert "-u" in reason and "-B" in reason


@pytest.mark.parametrize("command", [
    f"python3 {SCRIPT}",
    f"python3 -u {SCRIPT}",
    f"python3 -u -B {SCRIPT} --days 3",
    f"python3 -uB {SCRIPT}",
    f"python3 -OO {SCRIPT} arg",
    f"python3 -I -E -s {SCRIPT}",
    f"python3.12 -u {SCRIPT}",
    SCRIPT,
    f"{SCRIPT} sync",
])
def test_a_script_job_with_known_flags_and_an_existing_script_passes(home: Path, command: str) -> None:
    assert validate_no_agent_command(command, home) is None, command


@pytest.mark.parametrize("command", [
    f"python3 {MISSING}",
    f"python3 -u {MISSING}",
    MISSING,
])
def test_a_script_job_names_a_script_that_exists(home: Path, command: str) -> None:
    assert "exist" in validate_no_agent_command(command, home)


def test_a_symlink_or_a_directory_is_not_a_script(home: Path, tmp_path: Path) -> None:
    scripts = home / "skills" / "a" / "b" / "scripts"
    outside = tmp_path / "outside.py"
    outside.write_text("print('x')\n")
    (scripts / "link.py").symlink_to(outside)
    (scripts / "inside.py").symlink_to(scripts / "run.py")
    (scripts / "sub").mkdir()
    assert validate_no_agent_command("python3 $ALPI_HOME/skills/a/b/scripts/link.py", home) is not None
    assert validate_no_agent_command("python3 $ALPI_HOME/skills/a/b/scripts/inside.py", home) is not None
    assert validate_no_agent_command("python3 $ALPI_HOME/skills/a/b/scripts/sub", home) is not None
    assert validate_no_agent_command("python3 $ALPI_HOME/skills/a/b/scripts/../../../../../outside.py", home) is not None


def test_a_stored_job_with_inline_code_is_refused_when_it_fires(home: Path, monkeypatch) -> None:
    spawned: list = []
    monkeypatch.setattr(scheduler.subprocess, "run", lambda *a, **kw: spawned.append(a))
    job = {"id": "j", "kind": "cron", "no_agent": True, "prompt": f"python3 -Bcprint(1) {SCRIPT}"}
    ok, message, _ = scheduler.run_job(job, home)
    assert ok is False and "no_agent rejected" in message
    assert spawned == []


def test_the_schedule_tool_refuses_inline_code_it_would_have_inferred_as_a_script_job(home: Path) -> None:
    from alpi import tools
    result = tools.execute("schedule", {"action": "add", "prompt": f"python3 -Bcprint(1) {SCRIPT}", "schedule": "every 1h"})
    assert result.ok is False
    jobs_file = home / "schedule" / "jobs.json"
    assert not jobs_file.exists() or json.loads(jobs_file.read_text()) == []


@pytest.mark.parametrize("exe", ["python3.evil", "python3x", "pythonw", "./python3", "bin/python3", "python3.12t"])
def test_the_interpreter_must_be_a_real_python_name(home: Path, exe: str) -> None:
    assert validate_no_agent_command(f"{exe} {SCRIPT}", home) is not None, exe


def test_an_interpreter_inside_a_writable_root_is_refused(home: Path, tmp_path: Path) -> None:
    fake = tmp_path / "python3.12"
    fake.write_text("#!/bin/sh\necho pwned\n")
    fake.chmod(0o755)
    inside_home = home / "python3"
    inside_home.write_text("#!/bin/sh\n")
    inside_home.chmod(0o755)
    assert validate_no_agent_command(f"{fake} {SCRIPT}", home) is not None
    assert validate_no_agent_command(f"/tmp/python3.12 {SCRIPT}", home) is not None
    assert validate_no_agent_command(f"{inside_home} {SCRIPT}", home) is not None


@pytest.mark.parametrize("exe", ["python", "python3", "python3.12", "/usr/bin/python3", "/usr/local/bin/python3.11"])
def test_a_real_interpreter_name_or_a_system_path_passes(home: Path, exe: str) -> None:
    assert validate_no_agent_command(f"{exe} -u {SCRIPT}", home) is None, exe
