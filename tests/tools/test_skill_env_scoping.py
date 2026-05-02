"""Per-skill env scoping."""

from __future__ import annotations

from pathlib import Path

import pytest

from alpi.tools import _state
from alpi.tools.skill import (
    Skill,
    _frontmatter_from_text,
    _parse_env_list,
)
from alpi.tools.terminal import Terminal, _build_subprocess_env, _SAFE_ENV_KEYS


def _line_for(output: str, key: str) -> str | None:
    for line in output.splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1]
    return None


def test_safelist_keys_pass_through(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    monkeypatch.setenv("HOME", "/tmp/h")
    _state.reset_skill_env()
    env = _build_subprocess_env()
    assert env.get("PATH") == "/usr/bin:/bin"
    assert env.get("HOME") == "/tmp/h"


def test_secrets_blocked_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-secret")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "1234:abcd")
    _state.reset_skill_env()
    env = _build_subprocess_env()
    assert "OPENAI_API_KEY" not in env
    assert "TELEGRAM_BOT_TOKEN" not in env


def test_skill_declared_env_passes_through(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-secret")
    monkeypatch.setenv("HTTP_PROXY", "http://proxy:3128")
    _state.reset_skill_env()
    _state.add_skill_env(["HTTP_PROXY"])
    env = _build_subprocess_env()
    assert env.get("HTTP_PROXY") == "http://proxy:3128"
    assert "OPENAI_API_KEY" not in env


def test_terminal_subprocess_cannot_see_secret(
    tmp_home: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-secret")
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    _state.reset_skill_env()
    r = Terminal().run(action="run", command="env")
    assert r.ok, r.error
    assert "sk-secret" not in r.output
    assert _line_for(r.output, "OPENAI_API_KEY") is None


def test_terminal_subprocess_sees_skill_declared_var(
    tmp_home: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HTTP_PROXY", "http://proxy:3128")
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    _state.reset_skill_env()
    _state.add_skill_env(["HTTP_PROXY"])
    r = Terminal().run(action="run", command="env")
    assert r.ok, r.error
    assert _line_for(r.output, "HTTP_PROXY") == "http://proxy:3128"


def test_view_registers_env_from_frontmatter(
    tmp_home: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    skill_dir = tmp_home / "skills" / "miscellaneous" / "demo"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: demo\n"
        "description: demo skill for env scoping\n"
        "category: miscellaneous\n"
        "version: 0.1.0\n"
        "origin: user\n"
        "env: [HTTP_PROXY, FOO_TOKEN]\n"
        "---\n"
        "\nHello.\n"
    )
    _state.reset_skill_env()
    r = Skill().run(action="view", name="demo")
    assert r.ok, r.error
    active = _state.get_active_skills_env()
    assert active == {"HTTP_PROXY", "FOO_TOKEN"}


def test_view_subfile_does_not_register_env(
    tmp_home: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    skill_dir = tmp_home / "skills" / "miscellaneous" / "demo"
    (skill_dir / "references").mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: demo\ndescription: x\ncategory: miscellaneous\n"
        "version: 0.1.0\norigin: user\nenv: [FOO_TOKEN]\n---\nbody\n"
    )
    (skill_dir / "references" / "page.md").write_text("# page")
    _state.reset_skill_env()
    r = Skill().run(action="view", name="demo", file="references/page.md")
    assert r.ok
    assert _state.get_active_skills_env() == set()


def test_parse_env_list_shapes() -> None:
    assert _parse_env_list("[FOO, BAR]") == ["FOO", "BAR"]
    assert _parse_env_list("['A', \"B\"]") == ["A", "B"]
    assert _parse_env_list("") == []
    assert _parse_env_list("[]") == []
    # Reject anything that isn't a plain identifier — no shell metas.
    assert _parse_env_list("[FOO=bar]") == []
    assert _parse_env_list("[$(whoami)]") == []


def test_safelist_excludes_secrets() -> None:
    assert "OPENAI_API_KEY" not in _SAFE_ENV_KEYS
    assert "TELEGRAM_BOT_TOKEN" not in _SAFE_ENV_KEYS
    assert "ANTHROPIC_API_KEY" not in _SAFE_ENV_KEYS
