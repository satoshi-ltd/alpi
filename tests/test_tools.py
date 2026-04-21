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
    "memory", "skill", "research", "delegate",
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


def test_research_depth_resolves_from_config(tmp_home_no_env) -> None:
    from alf.tools.research import _resolve_depth, DEPTH_STEPS_DEFAULTS
    from alf import config as cfg_mod
    cfg = cfg_mod.load(tmp_home_no_env)
    for d in ("quick", "normal", "deep"):
        assert _resolve_depth(cfg, d) == DEPTH_STEPS_DEFAULTS[d]


def test_research_depth_honors_user_overrides(tmp_home_no_env) -> None:
    (tmp_home_no_env / "config.yaml").write_text(
        "tools:\n  research:\n    deep_steps: 60\n    quick_steps: 3\n"
    )
    from alf.tools.research import _resolve_depth
    from alf import config as cfg_mod
    cfg = cfg_mod.load(tmp_home_no_env)
    assert _resolve_depth(cfg, "quick") == 3
    assert _resolve_depth(cfg, "normal") == 15
    assert _resolve_depth(cfg, "deep") == 60


def test_research_rejects_unknown_depth() -> None:
    from alf.tools.research import Research
    r = Research().run(brief="x", depth="superdeep")
    assert not r.ok
    assert "depth" in (r.error or "")


def test_delegate_rejects_unknown_toolset() -> None:
    from alf.tools.delegate import Delegate
    r = Delegate().run(goal="x", toolsets=["pollo"])
    assert not r.ok
    assert "pollo" in (r.error or "")


def test_delegate_resolves_toolsets_and_filters_blocked() -> None:
    from alf.tools.delegate import _resolve_tools, BLOCKED_FOR_DELEGATE
    names, unknown = _resolve_tools(["file", "web"])
    assert not unknown
    assert {"read_file", "write_file", "edit_file", "search"} <= names
    assert {"web_search", "web_fetch", "web_extract"} <= names
    assert names.isdisjoint(BLOCKED_FOR_DELEGATE)


def test_delegate_defaults_to_file_plus_web() -> None:
    from alf.tools.delegate import _resolve_tools
    names, _ = _resolve_tools(None)
    assert "write_file" in names
    assert "web_search" in names
    assert "terminal" not in names


def test_delegate_prefixes_inner_emit_with_step_counter(
    tmp_home_no_env: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from alf import llm
    from alf.llm import Completion
    from alf.tools import _state as tool_state_mod
    from alf.tools import delegate as delegate_mod
    from alf.tools.delegate import Delegate

    captured: list[str] = []
    tool_state_mod.set_emit(lambda label, error: captured.append(label))

    calls = iter([
        Completion(
            content="", input_tokens=1, output_tokens=1, cost_usd=0.0, raw=None,
            tool_calls=[{"id": "c1", "name": "write_file",
                         "arguments": '{"path": "x", "content": "y"}'}],
        ),
        Completion(
            content="done", input_tokens=1, output_tokens=1,
            cost_usd=0.0, raw=None, tool_calls=[],
        ),
    ])
    monkeypatch.setattr(llm, "complete", lambda **_: next(calls))

    def _fake_execute(name: str, args: dict):
        tool_state_mod.emit_state("writing file…")
        from alf.tools.base import ToolResult
        return ToolResult(ok=True, output="written")

    monkeypatch.setattr(delegate_mod, "execute", _fake_execute, raising=False)
    import alf.tools as tools_pkg
    monkeypatch.setattr(tools_pkg, "execute", _fake_execute, raising=False)

    result = Delegate().run(goal="write y to x", toolsets=["file"])
    assert result.ok
    assert any("step 1/" in s and "writing file…" in s for s in captured), (
        f"expected prefixed inner label, got: {captured}"
    )


def test_research_prefixes_inner_emit_with_step_counter(
    tmp_home_no_env: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from alf import llm
    from alf.llm import Completion
    from alf.tools import _state as tool_state_mod
    from alf.tools import research as research_mod
    from alf.tools.research import Research

    captured: list[str] = []
    tool_state_mod.set_emit(lambda label, error: captured.append(label))

    calls = iter([
        Completion(
            content="", input_tokens=1, output_tokens=1, cost_usd=0.0, raw=None,
            tool_calls=[{"id": "c1", "name": "web_search",
                         "arguments": '{"query": "x"}'}],
        ),
        Completion(
            content="final report", input_tokens=1, output_tokens=1,
            cost_usd=0.0, raw=None, tool_calls=[],
        ),
    ])
    monkeypatch.setattr(llm, "complete", lambda **_: next(calls))

    def _fake_execute(name: str, args: dict):
        tool_state_mod.emit_state("searching the web…")
        from alf.tools.base import ToolResult
        return ToolResult(ok=True, output="hit")

    monkeypatch.setattr(research_mod, "execute", _fake_execute, raising=False)
    import alf.tools as tools_pkg
    monkeypatch.setattr(tools_pkg, "execute", _fake_execute, raising=False)

    result = Research().run(brief="test", depth="quick")
    assert result.ok
    assert any("step 1/" in s and "searching the web…" in s for s in captured), (
        f"expected prefixed inner label, got: {captured}"
    )
    assert any(s.startswith("quick · step 1/") for s in captured)
