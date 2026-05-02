"""User-skill mutations run the validator."""

from __future__ import annotations

from pathlib import Path

import pytest

from alpi.tools.skill import Skill


@pytest.fixture
def isolated_home(tmp_home_no_env: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("ALPI_HOME", str(tmp_home_no_env))
    (tmp_home_no_env / "skills").mkdir(parents=True, exist_ok=True)
    return tmp_home_no_env


def _create_plain(isolated_home: Path) -> None:
    Skill().run(
        action="create", name="demo", category="personal",
        description="demo skill", body="# demo\nsteps",
    )


def test_create_without_scripts_has_no_validation_line(isolated_home: Path) -> None:
    r = Skill().run(
        action="create", name="plain", category="personal",
        description="no scripts here", body="# plain\nprose only",
    )
    assert r.ok, r.error
    assert "validation:" not in r.output


def test_add_file_with_broken_script_surfaces_findings(isolated_home: Path) -> None:
    _create_plain(isolated_home)
    r = Skill().run(
        action="add_file", name="demo", subdir="scripts",
        filename="run.py",
        content="import nonexistent_module_xyz\n\nprint('hi')\n",
        confirm_user_skill=True,
    )
    assert r.ok, r.error
    assert "validation:" in r.output


def test_add_file_with_clean_script_no_findings(isolated_home: Path) -> None:
    _create_plain(isolated_home)
    r = Skill().run(
        action="add_file", name="demo", subdir="scripts",
        filename="run.py",
        content="import sys\nprint('ok')\nsys.exit(0)\n",
        confirm_user_skill=True,
    )
    assert r.ok, r.error
    assert "validation:" not in r.output


def test_patch_re_runs_validation(isolated_home: Path) -> None:
    _create_plain(isolated_home)
    Skill().run(
        action="add_file", name="demo", subdir="scripts", filename="run.py",
        content="import sys\nprint('ok')\n", confirm_user_skill=True,
    )
    # Patch introduces a syntax error.
    r = Skill().run(
        action="patch", name="demo", subdir="scripts", filename="run.py",
        old_string="print('ok')", new_string="print('broken' ",
        confirm_user_skill=True,
    )
    assert r.ok, r.error
    assert "validation:" in r.output


def test_remove_file_revalidates(isolated_home: Path) -> None:
    _create_plain(isolated_home)
    Skill().run(
        action="add_file", name="demo", subdir="scripts", filename="a.py",
        content="import sys\n", confirm_user_skill=True,
    )
    Skill().run(
        action="add_file", name="demo", subdir="scripts", filename="b.py",
        content="import sys\n", confirm_user_skill=True,
    )
    r = Skill().run(
        action="remove_file", name="demo", subdir="scripts", filename="a.py",
        confirm_user_skill=True,
    )
    assert r.ok, r.error
    assert "validation:" not in r.output


def test_edit_body_revalidates(isolated_home: Path) -> None:
    _create_plain(isolated_home)
    Skill().run(
        action="add_file", name="demo", subdir="scripts", filename="run.py",
        content="# port: 8080\nimport http.server\nhttp.server.HTTPServer(('localhost', 8080), None)\n",
        confirm_user_skill=True,
    )
    # A wrong port should trigger the coherence check.
    r = Skill().run(
        action="edit", name="demo",
        body="# demo\nRuns on localhost:9999.",
        confirm_user_skill=True,
    )
    assert r.ok, r.error
    assert "validation:" in r.output
