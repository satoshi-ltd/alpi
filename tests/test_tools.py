"""Unit tests for every registered tool (no LLM)."""

from __future__ import annotations

from pathlib import Path

import pytest

from alf import tools
from alf.tools.terminal import Terminal
from alf.tools.edit_file import EditFile
from alf.tools.read_file import ReadFile
from alf.tools.search import Search
from alf.tools.todo import Todo, _TODOS
from alf.tools.write_file import WriteFile


EXPECTED_TOOLS = {
    "read_file", "write_file", "edit_file", "terminal", "search",
    "todo", "web_search", "web_fetch", "web_extract", "schedule",
    "memory", "skill", "delegate",
    "session_search", "send_message", "email", "config",
}


def test_registry_has_all_expected_tools() -> None:
    names = {cls.name for cls in tools.all_tools()}
    missing = EXPECTED_TOOLS - names
    assert not missing, f"missing tools: {missing}"


def test_read_write_roundtrip(tmp_home_no_env: Path) -> None:
    target = tmp_home_no_env / "hello.txt"
    assert WriteFile().run(path=str(target), content="hola alf").ok
    r = ReadFile().run(path=str(target))
    assert r.ok and "hola alf" in r.output


def test_edit_file_single_match(tmp_home_no_env: Path) -> None:
    target = tmp_home_no_env / "f.txt"
    WriteFile().run(path=str(target), content="foo bar baz")
    r = EditFile().run(path=str(target), old_string="bar", new_string="qux")
    assert r.ok and target.read_text() == "foo qux baz"


def test_edit_file_rejects_missing(tmp_home_no_env: Path) -> None:
    target = tmp_home_no_env / "f.txt"
    WriteFile().run(path=str(target), content="abc")
    assert not EditFile().run(path=str(target), old_string="X", new_string="Y").ok


def test_edit_file_rejects_multi_match(tmp_home_no_env: Path) -> None:
    target = tmp_home_no_env / "f.txt"
    WriteFile().run(path=str(target), content="a a a")
    assert not EditFile().run(path=str(target), old_string="a", new_string="b").ok


def test_terminal_success() -> None:
    r = Terminal().run(command="echo hola")
    assert r.ok
    assert "hola" in r.output
    assert "[exit 0]" in r.output


def test_terminal_failure_surfaces_exit_code() -> None:
    r = Terminal().run(command="false")
    assert not r.ok
    assert "[exit 1]" in r.output


def test_terminal_background_and_kill(
    tmp_home_no_env: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALF_HOME", str(tmp_home_no_env))
    r = Terminal().run(action="background", command="sleep 30")
    assert r.ok
    pid = int(r.output.split("pid=")[1].split()[0])
    try:
        status = Terminal().run(action="status", pid=pid)
        assert status.ok and "running=True" in status.output
    finally:
        Terminal().run(action="kill", pid=pid)


def test_search_content_finds_pattern() -> None:
    repo_root = Path(__file__).resolve().parent.parent / "alf"
    r = Search().run(pattern="def run", path=str(repo_root), target="content")
    assert r.ok and "def run" in r.output


def test_search_filename_finds_py_files() -> None:
    repo_root = Path(__file__).resolve().parent.parent / "alf"
    r = Search().run(pattern="*.py", path=str(repo_root), target="files")
    assert r.ok and "cli.py" in r.output


def test_search_filename_smart_case_lowercase_is_insensitive(
    tmp_home_no_env: Path,
) -> None:
    (tmp_home_no_env / "Documents").mkdir()
    (tmp_home_no_env / "Documents" / "note.md").write_text("x")
    r = Search().run(pattern="documents/*.md",
                     path=str(tmp_home_no_env), target="files")
    assert r.ok
    assert "note.md" in r.output


def test_search_filename_smart_case_mixed_case_is_sensitive(
    tmp_home_no_env: Path,
) -> None:
    (tmp_home_no_env / "Documents").mkdir()
    (tmp_home_no_env / "Documents" / "note.md").write_text("x")
    r = Search().run(pattern="Documents/*.MD",
                     path=str(tmp_home_no_env), target="files")
    assert r.ok
    assert "note.md" not in r.output


def test_search_filename_case_sensitive_when_forced(
    tmp_home_no_env: Path,
) -> None:
    (tmp_home_no_env / "Documents").mkdir()
    (tmp_home_no_env / "Documents" / "note.md").write_text("x")
    r = Search().run(
        pattern="documents/*.md",
        path=str(tmp_home_no_env), target="files",
        case_sensitive=True,
    )
    assert r.ok
    assert "note.md" not in r.output


def test_search_target_aliases(tmp_home_no_env: Path) -> None:
    (tmp_home_no_env / "foo.py").write_text("x = 1\n")
    r = Search().run(pattern="*.py", path=str(tmp_home_no_env), target="find")
    assert r.ok and "foo.py" in r.output
    r = Search().run(pattern="x = 1", path=str(tmp_home_no_env), target="grep")
    assert r.ok and "foo.py" in r.output


def test_todo_lifecycle() -> None:
    _TODOS.clear()
    t = Todo()
    assert t.run(action="add", content="paso 1").ok
    assert "paso 1" in t.run(action="list").output
    assert t.run(action="complete", index=0).ok
    assert "[x]" in t.run(action="list").output
    t.run(action="clear")
    assert "no todos" in t.run(action="list").output


def test_write_file_atomic_overwrite(tmp_home_no_env: Path) -> None:
    target = tmp_home_no_env / "data.txt"
    WriteFile().run(path=str(target), content="v1")
    WriteFile().run(path=str(target), content="v2")
    assert target.read_text() == "v2"
    # No lingering .tmp or .bak siblings — write_file is intentionally
    # clean, git (or user backups) handles version recovery.
    assert not (tmp_home_no_env / "data.txt.tmp").exists()
    assert not (tmp_home_no_env / "data.txt.bak").exists()


def test_terminal_strips_ansi() -> None:
    r = Terminal().run(
        command="printf '\\033[31mRED\\033[0m normal\\n'",
    )
    assert r.ok
    assert "RED" in r.output
    assert "\x1b" not in r.output


def test_search_excludes_noise(tmp_home_no_env: Path) -> None:
    (tmp_home_no_env / "src").mkdir()
    (tmp_home_no_env / "src" / "real.py").write_text("x")
    (tmp_home_no_env / "node_modules").mkdir()
    (tmp_home_no_env / "node_modules" / "junk.py").write_text("x")
    r = Search().run(pattern="*.py", path=str(tmp_home_no_env), target="files")
    assert "real.py" in r.output
    assert "node_modules" not in r.output
    r2 = Search().run(pattern="*.py", path=str(tmp_home_no_env),
                      target="files", include_noise=True)
    assert "node_modules" in r2.output


def test_schemas_shape() -> None:
    schemas = tools.schemas()
    assert all("type" in s and s["type"] == "function" for s in schemas)
    assert all("function" in s and "name" in s["function"] for s in schemas)
