"""``skill(action='set_meta')`` and the matching ``edit`` guard.

Discovered during integration testing: when an agent tried to fix a
broken frontmatter via ``edit``, it pasted a full SKILL.md (with its
own ``---`` block) as the ``body`` argument. ``edit`` preserved the
real frontmatter and wrote the body verbatim, leaving a SKILL.md
with TWO ``---`` blocks — silently broken. ``set_meta`` is the
correct verb for frontmatter mutations; ``edit`` now rejects bodies
that contain a frontmatter block.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from alpi.tools.skill import Skill


@pytest.fixture
def isolated_home(tmp_home_no_env: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("ALPI_HOME", str(tmp_home_no_env))
    return tmp_home_no_env


@pytest.fixture
def base_skill(isolated_home: Path) -> str:
    r = Skill().run(
        action="create",
        name="meta-target",
        category="personal",
        description="A skill",
        body="## When to use\nFor testing.\n",
        requires_env=[],
        tools=["terminal"],
        keywords=["alpha"],
    )
    assert r.ok, r.error
    return "meta-target"


# edit-rejection

def test_edit_rejects_body_with_frontmatter_block(
    isolated_home: Path, base_skill: str,
) -> None:
    bad_body = (
        "---\n"
        "name: meta-target\n"
        "requires_env: ['NEW_VAR']\n"
        "---\n"
        "## When to use\nUpdated.\n"
    )
    r = Skill().run(action="edit", name=base_skill, body=bad_body, confirm_user_skill=True)
    assert not r.ok
    assert "frontmatter block" in r.error
    assert "set_meta" in r.error


def test_edit_accepts_pure_prose_body(
    isolated_home: Path, base_skill: str,
) -> None:
    good_body = (
        "## When to use\n\nNow updated with a longer explanation.\n\n"
        "## Workflow\n\n1. Read the input\n2. Validate it\n3. Persist\n"
    )
    r = Skill().run(action="edit", name=base_skill, body=good_body, confirm_user_skill=True)
    assert r.ok, r.error


def test_edit_rejects_placeholder_body(
    isolated_home: Path, base_skill: str,
) -> None:
    """``[PENDING_VIEW]`` was the actual placeholder we observed in
    integration when the LLM forgot to ``view`` first. Anything under
    ``MIN_EDIT_BODY_CHARS`` is rejected as a classic
    'forgot to read existing content first' bug."""
    for placeholder in ("[PENDING_VIEW]", "TODO", "<placeholder>", "..."):
        r = Skill().run(
            action="edit",
            name=base_skill,
            body=placeholder,
            confirm_user_skill=True,
        )
        assert not r.ok, f"expected reject for {placeholder!r}"
        assert "placeholder" in r.error
        assert "view" in r.error and "patch" in r.error


def test_edit_accepts_short_real_body(
    isolated_home: Path, base_skill: str,
) -> None:
    r = Skill().run(
        action="edit",
        name=base_skill,
        body="## Summary\nReal but short.\n",
        confirm_user_skill=True,
    )
    assert r.ok, r.error


def test_edit_allows_triple_dash_in_text_when_not_frontmatter(
    isolated_home: Path, base_skill: str,
) -> None:
    # A horizontal rule mid-prose isn't frontmatter — only top-of-file
    # ``---\n…\n---\n`` triggers the guard.
    body = (
        "## Section A\n\nSome longer prose for the first section.\n\n"
        "---\n\n## Section B\n\nMore prose here that crosses the rule.\n"
    )
    r = Skill().run(action="edit", name=base_skill, body=body, confirm_user_skill=True)
    assert r.ok, r.error


# set_meta — happy path

def test_set_meta_overwrites_single_field(
    isolated_home: Path, base_skill: str,
) -> None:
    r = Skill().run(
        action="set_meta",
        name=base_skill,
        fields={"requires_env": ["MY_TOKEN"]},
        confirm_user_skill=True,
    )
    assert r.ok, r.error
    md = (isolated_home / "skills" / "personal" / "meta-target" / "SKILL.md").read_text()
    assert "requires_env: ['MY_TOKEN']" in md
    # Other fields stay.
    assert "tools: ['terminal']" in md
    assert "keywords: ['alpha']" in md


def test_set_meta_preserves_prose_body(
    isolated_home: Path, base_skill: str,
) -> None:
    md_before = (isolated_home / "skills" / "personal" / "meta-target" / "SKILL.md").read_text()
    body_before = md_before.split("---", 2)[2]

    Skill().run(
        action="set_meta",
        name=base_skill,
        fields={"keywords": ["beta", "gamma"]},
        confirm_user_skill=True,
    )

    md_after = (isolated_home / "skills" / "personal" / "meta-target" / "SKILL.md").read_text()
    body_after = md_after.split("---", 2)[2]
    assert body_before == body_after


def test_set_meta_writes_bak(
    isolated_home: Path, base_skill: str,
) -> None:
    Skill().run(
        action="set_meta",
        name=base_skill,
        fields={"keywords": ["new"]},
        confirm_user_skill=True,
    )
    bak = isolated_home / "skills" / "personal" / "meta-target" / "SKILL.md.bak"
    assert bak.exists()


def test_set_meta_multiple_fields_in_one_call(
    isolated_home: Path, base_skill: str,
) -> None:
    r = Skill().run(
        action="set_meta",
        name=base_skill,
        fields={
            "requires_env": ["TOKEN_A", "TOKEN_B"],
            "tools": ["terminal", "db"],
            "keywords": ["delta"],
        },
        confirm_user_skill=True,
    )
    assert r.ok, r.error
    md = (isolated_home / "skills" / "personal" / "meta-target" / "SKILL.md").read_text()
    assert "requires_env: ['TOKEN_A', 'TOKEN_B']" in md
    assert "tools: ['terminal', 'db']" in md
    assert "keywords: ['delta']" in md


def test_set_meta_can_add_output_schema(
    isolated_home: Path, base_skill: str,
) -> None:
    r = Skill().run(
        action="set_meta",
        name=base_skill,
        fields={
            "output_schema": '{"type":"object","properties":{"ok":{"type":"boolean"}},"required":["ok"]}',
        },
        confirm_user_skill=True,
    )
    assert r.ok, r.error
    md = (isolated_home / "skills" / "personal" / "meta-target" / "SKILL.md").read_text()
    assert 'output_schema: {"type":"object","properties":{"ok":{"type":"boolean"}},"required":["ok"]}' in md


def test_set_meta_accepts_top_level_fields(
    isolated_home: Path, base_skill: str,
) -> None:
    r = Skill().run(
        action="set_meta",
        name=base_skill,
        description="Updated metadata",
        requires_env=["TOKEN_A"],
        tools=["terminal", "db"],
        keywords=["alpha", "beta"],
        confirm_user_skill=True,
    )
    assert r.ok, r.error
    md = (isolated_home / "skills" / "personal" / "meta-target" / "SKILL.md").read_text()
    assert "description: Updated metadata" in md
    assert "requires_env: ['TOKEN_A']" in md
    assert "tools: ['terminal', 'db']" in md
    assert "keywords: ['alpha', 'beta']" in md


# set_meta — guards

def test_set_meta_requires_fields(
    isolated_home: Path, base_skill: str,
) -> None:
    r = Skill().run(action="set_meta", name=base_skill, confirm_user_skill=True)
    assert not r.ok
    assert "fields" in r.error


def test_set_meta_unknown_skill(isolated_home: Path) -> None:
    r = Skill().run(
        action="set_meta", name="nope",
        fields={"keywords": ["x"]}, confirm_user_skill=True,
    )
    assert not r.ok
    assert "skill not found" in r.error


def test_set_meta_rejects_bundled(isolated_home: Path) -> None:
    r = Skill().run(
        action="set_meta",
        name="@alpi/knowledge",
        fields={"keywords": ["x"]},
    )
    assert not r.ok
    assert "bundled" in r.error


def test_set_meta_origin_user_requires_confirmation(
    isolated_home: Path,
) -> None:
    skill_dir = isolated_home / "skills" / "personal" / "user-owned"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: user-owned\n"
        "description: hand-written\n"
        "category: personal\n"
        "origin: user\n"
        "requires_env: []\n"
        "---\n"
        "## When to use\nN/A.\n"
    )
    r = Skill().run(
        action="set_meta", name="user-owned",
        fields={"keywords": ["x"]},
    )
    assert not r.ok
    assert "confirm_user_skill" in r.error


def test_set_meta_blocks_invalid_value(
    isolated_home: Path, base_skill: str,
) -> None:
    """Schema runs after the merge — invalid values block the write."""
    r = Skill().run(
        action="set_meta",
        name=base_skill,
        fields={"category": "not-a-real-category"},
        confirm_user_skill=True,
    )
    assert not r.ok
    assert "category" in r.error


def test_set_meta_rejects_unknown_field(
    isolated_home: Path, base_skill: str,
) -> None:
    r = Skill().run(
        action="set_meta",
        name=base_skill,
        fields={"not_a_field": "x"},
        confirm_user_skill=True,
    )
    assert not r.ok
    assert "unknown frontmatter field" in r.error


def test_set_meta_surfaces_warnings(
    isolated_home: Path, base_skill: str,
) -> None:
    r = Skill().run(
        action="set_meta",
        name=base_skill,
        fields={"keywords": ["valid", "Bad Token"]},
        confirm_user_skill=True,
    )
    assert r.ok, r.error
    assert "schema warnings" in r.output
    assert "keywords" in r.output


# integration: the bug we found

def test_set_meta_fixes_strava_style_skill(
    isolated_home: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The exact flow that failed in the integration test:
    skill created with empty requires_env / tools / keywords, then
    fixed via set_meta."""
    Skill().run(
        action="create",
        name="strava-oauth-api",
        category="software",
        description="Connect to the Strava API with OAuth2",
        body="## When to use\nFor Strava integrations.\n",
    )
    md0 = (isolated_home / "skills" / "software" / "strava-oauth-api" / "SKILL.md").read_text()
    assert "requires_env: []" in md0

    r = Skill().run(
        action="set_meta",
        name="strava-oauth-api",
        fields={
            "requires_env": ["STRAVA_CLIENT_ID", "STRAVA_CLIENT_SECRET"],
            "tools": ["terminal", "web_fetch"],
            "keywords": ["strava", "oauth", "fitness"],
        },
        confirm_user_skill=True,
    )
    assert r.ok, r.error
    md1 = (isolated_home / "skills" / "software" / "strava-oauth-api" / "SKILL.md").read_text()
    assert "requires_env: ['STRAVA_CLIENT_ID', 'STRAVA_CLIENT_SECRET']" in md1
    assert "tools: ['terminal', 'web_fetch']" in md1
    assert "keywords: ['strava', 'oauth', 'fitness']" in md1
    # Should land at the index now if env vars are set.
    monkeypatch.setenv("STRAVA_CLIENT_ID", "id")
    monkeypatch.setenv("STRAVA_CLIENT_SECRET", "secret")
    from alpi.tools.skill import skills_index_block
    block = skills_index_block(isolated_home)
    assert "strava-oauth-api" in block
