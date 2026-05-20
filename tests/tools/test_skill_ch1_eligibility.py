"""CH.1 — requires_bins / requires_config / platforms eligibility coverage."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from alpi.tools import _state
from alpi.tools.skill import (
    Skill,
    _current_platform,
    keyword_match_hint,
    skill_eligibility,
    skill_requirements,
    skills_index_block,
)


@pytest.fixture
def isolated_home(tmp_home_no_env: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("ALPI_HOME", str(tmp_home_no_env))
    _state.reset_skill_env()
    return tmp_home_no_env


# requires_bins ---------------------------------------------------------------


def test_requirements_parses_bins() -> None:
    meta = {"requires_bins": "['gh', 'sqlite3']"}
    assert skill_requirements(meta)["bins"] == ["gh", "sqlite3"]


def test_requirements_filters_bad_bin_names() -> None:
    meta = {"requires_bins": "['gh', 'with space', '../etc/passwd', 'ffmpeg']"}
    assert skill_requirements(meta)["bins"] == ["gh", "ffmpeg"]


def test_missing_bin_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("shutil.which", lambda _: None)
    ok, missing = skill_eligibility({"requires_bins": "['definitely_not_a_real_binary_xyz']"})
    assert not ok
    assert any("binary definitely_not_a_real_binary_xyz" in m for m in missing)


def test_present_bin_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("shutil.which", lambda b: f"/usr/bin/{b}")
    ok, missing = skill_eligibility({"requires_bins": "['gh']"})
    assert ok and missing == []


# requires_config -------------------------------------------------------------


def test_requirements_parses_config_paths() -> None:
    meta = {"requires_config": "['home_assistant.url', 'gateway.imap.poll_interval']"}
    assert skill_requirements(meta)["config"] == [
        "home_assistant.url", "gateway.imap.poll_interval",
    ]


def test_requirements_filters_bad_config_paths() -> None:
    meta = {"requires_config": "['ok.path', '../sibling', '1.bad', 'foo.bar']"}
    assert skill_requirements(meta)["config"] == ["ok.path", "foo.bar"]


def test_missing_config_key_blocks() -> None:
    ok, missing = skill_eligibility(
        {"requires_config": "['home_assistant.url']"},
        cfg_raw={},
    )
    assert not ok
    assert "config key home_assistant.url" in missing


def test_present_config_key_passes() -> None:
    ok, _ = skill_eligibility(
        {"requires_config": "['home_assistant.url']"},
        cfg_raw={"home_assistant": {"url": "http://localhost:8123"}},
    )
    assert ok


def test_empty_config_value_counts_as_missing() -> None:
    ok, missing = skill_eligibility(
        {"requires_config": "['home_assistant.url']"},
        cfg_raw={"home_assistant": {"url": ""}},
    )
    assert not ok
    assert "config key home_assistant.url" in missing


def test_skipped_when_cfg_raw_not_provided() -> None:
    """Legacy callers that omit cfg_raw must not silently hide config-gated skills."""
    ok, _ = skill_eligibility({"requires_config": "['home_assistant.url']"})
    assert ok


# platforms -------------------------------------------------------------------


def test_requirements_parses_platforms() -> None:
    meta = {"platforms": "['linux', 'macos']"}
    assert sorted(skill_requirements(meta)["platforms"]) == ["linux", "macos"]


def test_requirements_filters_bad_platforms() -> None:
    meta = {"platforms": "['linux', 'BeOS', 'windows']"}
    assert sorted(skill_requirements(meta)["platforms"]) == ["linux", "windows"]


def test_platform_mismatch_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    ok, missing = skill_eligibility({"platforms": "['macos']"})
    assert not ok
    assert any("platform macos" in m for m in missing)
    assert any("this is linux" in m for m in missing)


def test_platform_match_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "darwin")
    ok, _ = skill_eligibility({"platforms": "['macos']"})
    assert ok


# compound reasons ------------------------------------------------------------


def test_compound_misses_listed_together(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("shutil.which", lambda _: None)
    monkeypatch.setattr(sys, "platform", "linux")
    ok, missing = skill_eligibility(
        {
            "requires_env": "['TOKEN']",
            "requires_bins": "['gh']",
            "platforms": "['windows']",
            "requires_config": "['acme.url']",
        },
        env={},
        cfg_raw={},
    )
    assert not ok
    joined = "; ".join(missing)
    assert "env var TOKEN" in joined
    assert "binary gh" in joined
    assert "platform windows" in joined
    assert "config key acme.url" in joined


# Integration: surfaces -------------------------------------------------------


def _make_skill(home: Path, *, name: str, **extra: list[str]) -> None:
    r = Skill().run(
        action="create",
        name=name,
        category="software",
        description=f"Skill {name}.",
        body="## When to use\nA test skill.\n",
        **extra,
    )
    assert r.ok, r.error


def test_create_persists_new_eligibility_fields(isolated_home: Path) -> None:
    _make_skill(
        isolated_home,
        name="full-fields",
        requires_bins=["gh"],
        requires_config=["acme.url"],
        platforms=["macos", "linux", "windows"],
    )
    md = (isolated_home / "skills" / "software" / "full-fields" / "SKILL.md").read_text()
    assert "requires_bins: ['gh']" in md
    assert "requires_config: ['acme.url']" in md
    assert "platforms:" in md
    assert "macos" in md and "linux" in md and "windows" in md


def test_index_block_hides_skill_with_unmet_bin(
    isolated_home: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("shutil.which", lambda _: None)
    _make_skill(isolated_home, name="needs-gh", requires_bins=["gh"])
    block = skills_index_block(isolated_home)
    assert "needs-gh" not in block


def test_index_block_hides_skill_with_wrong_platform(
    isolated_home: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    other_platform = "windows" if _current_platform() != "windows" else "macos"
    _make_skill(isolated_home, name="other-os", platforms=[other_platform])
    block = skills_index_block(isolated_home)
    assert "other-os" not in block


def test_index_block_hides_skill_with_missing_config(isolated_home: Path) -> None:
    _make_skill(
        isolated_home,
        name="needs-cfg",
        requires_config=["definitely_not_set_anywhere.url"],
    )
    block = skills_index_block(isolated_home)
    assert "needs-cfg" not in block


def test_keyword_match_hint_filters_inactive_skills(
    isolated_home: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("shutil.which", lambda _: None)
    r = Skill().run(
        action="create",
        name="needs-gh-kw",
        category="software",
        description="Skill that uses gh.",
        body="## When to use\nWhen the user mentions foozle.\n",
        requires_bins=["gh"],
        keywords=["foozle"],
    )
    assert r.ok, r.error
    hint = keyword_match_hint(isolated_home, "let's foozle now")
    assert "needs-gh-kw" not in hint


# Explicit invocation gate ----------------------------------------------------


def test_run_fails_fast_on_inactive_skill(
    isolated_home: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("shutil.which", lambda _: None)
    _make_skill(isolated_home, name="needs-gh-run", requires_bins=["gh"])
    r = Skill().run(action="run", name="needs-gh-run")
    assert not r.ok
    assert "inactive" in r.error
    assert "binary gh" in r.error


def test_test_fails_fast_on_inactive_skill(
    isolated_home: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("shutil.which", lambda _: None)
    _make_skill(isolated_home, name="needs-gh-test", requires_bins=["gh"])
    r = Skill().run(action="test", name="needs-gh-test")
    assert not r.ok
    assert "inactive" in r.error


# _list compound reasons ------------------------------------------------------


def test_list_shows_compound_inactive_reason(
    isolated_home: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("shutil.which", lambda _: None)
    monkeypatch.delenv("ZTOKEN", raising=False)
    r = Skill().run(
        action="create",
        name="multi-miss",
        category="software",
        description="Needs many things.",
        body="## When to use\nMultiple requirements.\n",
        requires_env=["ZTOKEN"],
        requires_bins=["gh"],
    )
    assert r.ok, r.error
    r2 = Skill().run(action="list")
    assert r2.ok
    line = next(ln for ln in r2.output.splitlines() if "multi-miss" in ln)
    assert "[inactive:" in line
    assert "env var ZTOKEN" in line
    assert "binary gh" in line


# Per-profile env contract — regressions caught after v0.4.52 ship.
# A skill whose requires_env is satisfied by the PROFILE's .env (and only
# the profile's) must be eligible / runnable from a chat in that profile.


def test_skill_run_uses_profile_env_not_os_environ(
    isolated_home: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``skill(action='run', name=...)`` checked eligibility against ``os.environ`` by default before v0.4.52, so a key only in ``<home>/.env`` would falsely flag the skill inactive."""
    monkeypatch.delenv("FOLDER_FROM_PROFILE", raising=False)
    (isolated_home / ".env").write_text("FOLDER_FROM_PROFILE=/x/y/z\n")
    r = Skill().run(
        action="create",
        name="env-from-profile",
        category="software",
        description="needs FOLDER_FROM_PROFILE.",
        body="## When to use\nFor the profile-env contract test.\n",
        requires_env=["FOLDER_FROM_PROFILE"],
    )
    assert r.ok, r.error
    # run with no script falls through to ToolResult error("no script") — but
    # the eligibility gate is what we're pinning here; if eligibility wrongly
    # fails, the error message would mention env var FOLDER_FROM_PROFILE.
    r2 = Skill().run(action="run", name="env-from-profile")
    assert "env var FOLDER_FROM_PROFILE" not in (r2.error or ""), r2.error


def test_skill_list_marks_eligible_when_key_in_profile_env(
    isolated_home: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``skill(action='list')`` rendered ``[inactive: env var …]`` even when the key was present in the profile's .env — fixed by piping ``effective_profile_env`` into ``_state_tag``."""
    monkeypatch.delenv("DOC_TOKEN", raising=False)
    (isolated_home / ".env").write_text("DOC_TOKEN=ok\n")
    r = Skill().run(
        action="create",
        name="doc-only",
        category="personal",
        description="Profile-scoped token.",
        body="## When to use\nProfile env test.\n",
        requires_env=["DOC_TOKEN"],
    )
    assert r.ok, r.error
    r2 = Skill().run(action="list")
    assert r2.ok
    line = next(ln for ln in r2.output.splitlines() if "doc-only" in ln)
    assert "[inactive:" not in line, line


def test_skills_index_block_keeps_profile_env_skills_visible(
    isolated_home: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """System-prompt skill index — pre-fix a requires_env tied to the profile would be silently filtered out, hiding the skill from the agent."""
    monkeypatch.delenv("DOC_TOKEN", raising=False)
    (isolated_home / ".env").write_text("DOC_TOKEN=ok\n")
    r = Skill().run(
        action="create",
        name="visible-via-profile",
        category="personal",
        description="Profile-scoped token.",
        body="## When to use\nIndex visibility test.\n",
        requires_env=["DOC_TOKEN"],
    )
    assert r.ok, r.error
    idx = skills_index_block(isolated_home)
    assert "visible-via-profile" in idx


def test_keyword_match_hint_respects_profile_env(
    isolated_home: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The per-turn keyword hint also filtered by eligibility against ``os.environ``; ensure it now uses the profile env."""
    monkeypatch.delenv("DOC_TOKEN", raising=False)
    (isolated_home / ".env").write_text("DOC_TOKEN=ok\n")
    r = Skill().run(
        action="create",
        name="hinted-skill",
        category="personal",
        description="Hinted by some keyword.",
        body="## When to use\nKeyword hint test.\n",
        requires_env=["DOC_TOKEN"],
        keywords=["bananarama"],
    )
    assert r.ok, r.error
    hint = keyword_match_hint(isolated_home, "do something with bananarama today")
    assert "hinted-skill" in hint
