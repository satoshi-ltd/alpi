"""Frontmatter schema validator — field-by-field diagnostics.

The schema is the single source of truth for what a SKILL.md
manifest looks like. Every test here picks one field and shows
both a valid example and at least one invalid one with the exact
diagnostic the validator is expected to emit.
"""

from __future__ import annotations

import pytest

from alpi.tools import _skill_schema as schema
from alpi.tools.skill import CATEGORIES


_BASE: dict[str, str] = {
    "name": "ok-skill",
    "description": "A working skill",
    "category": "software",
}


def _validate(extra: dict[str, str] | None = None, **overrides) -> list[schema.Issue]:
    meta = dict(_BASE)
    if extra:
        meta.update(extra)
    meta.update(overrides)
    return schema.validate_frontmatter(meta, categories=CATEGORIES)


# Happy path

def test_minimal_valid_frontmatter_passes() -> None:
    assert _validate() == []


def test_full_valid_frontmatter_passes() -> None:
    issues = _validate({
        "version": "1.2.3",
        "origin": "user",
        "requires_env": "['TOKEN']",
        "tools": "['terminal', 'web_fetch']",
        "output_schema": '{"type":"object","properties":{"ok":{"type":"boolean"}},"required":["ok"]}',
        "created_at": "2026-05-02",
    })
    assert issues == []


# name

def test_name_required() -> None:
    issues = _validate(name="")
    assert any(i.field == "name" and i.severity == "error" for i in issues)


def test_name_must_be_kebab_case() -> None:
    for bad in ("CamelCase", "snake_case", "Has Spaces", "x", "9starts-with-digit"):
        issues = _validate(name=bad)
        assert any(
            i.field == "name" and i.severity == "error" for i in issues
        ), f"expected error for name={bad!r}"


def test_name_accepts_kebab_case() -> None:
    for good in ("a1", "ok-skill", "deep-research-2", "abc"):
        assert _validate(name=good) == []


# description

def test_description_required() -> None:
    issues = _validate(description="")
    assert any(i.field == "description" and i.severity == "error" for i in issues)


def test_description_too_long_is_warning_not_error() -> None:
    # Instructional skill descriptions can legitimately exceed the headline length. The schema warns to encourage brevity but never blocks creation on length alone.
    issues = _validate(description="x" * 200)
    msg = next((i for i in issues if i.field == "description"), None)
    assert msg is not None and msg.severity == "warning"
    assert "200" in msg.message


def test_description_trailing_period_warns() -> None:
    issues = _validate(description="A skill.")
    assert any(
        i.field == "description" and i.severity == "warning" for i in issues
    )


# category

def test_category_required() -> None:
    issues = _validate(category="")
    assert any(i.field == "category" and i.severity == "error" for i in issues)


def test_category_unknown_is_error() -> None:
    issues = _validate(category="not-a-category")
    err = next((i for i in issues if i.field == "category"), None)
    assert err is not None and err.severity == "error"
    assert "not-a-category" in err.message


# version

def test_version_optional_blank_is_clean() -> None:
    assert _validate(version="") == []


def test_version_non_semver_warns() -> None:
    issues = _validate(version="latest")
    assert any(
        i.field == "version" and i.severity == "warning" for i in issues
    )


def test_version_semver_passes() -> None:
    for v in ("0.1.0", "1.0.0", "12.34.56", "1.0.0-rc1", "2.3.4+build5"):
        assert _validate(version=v) == [], f"expected clean for version={v}"


# origin

def test_origin_invalid_is_error() -> None:
    issues = _validate(origin="not-an-origin")
    assert any(i.field == "origin" and i.severity == "error" for i in issues)


def test_origin_valid_passes() -> None:
    for o in ("agent", "user"):
        assert _validate(origin=o) == []


# requires_env

def test_requires_env_invalid_var_name_is_error() -> None:
    issues = _validate(requires_env="['9_BAD']")
    err = next((i for i in issues if i.field == "requires_env"), None)
    assert err is not None and err.severity == "error"


def test_requires_env_with_space_is_error() -> None:
    issues = _validate(requires_env="['my var']")
    assert any(i.field == "requires_env" and i.severity == "error" for i in issues)


def test_requires_env_valid_var_names_pass() -> None:
    assert _validate(requires_env="['FOO', 'BAR_BAZ', '_LEADING_UNDER']") == []


def test_requires_env_empty_string_is_clean() -> None:
    assert _validate(requires_env="") == []


def test_requires_env_empty_list_is_clean() -> None:
    assert _validate(requires_env="[]") == []


# tools

def test_tools_non_snake_case_warns() -> None:
    issues = _validate(tools="['WebFetch']")
    assert any(i.field == "tools" and i.severity == "warning" for i in issues)


def test_tools_snake_case_passes() -> None:
    assert _validate(tools="['web_fetch', 'terminal', 'memory']") == []


def test_keywords_accept_hyphenated_tokens() -> None:
    assert _validate(keywords="['deep-research', 'oauth2']") == []


# created_at

def test_created_at_non_iso_warns() -> None:
    issues = _validate(created_at="May 2nd 2026")
    assert any(i.field == "created_at" and i.severity == "warning" for i in issues)


def test_created_at_iso_passes() -> None:
    assert _validate(created_at="2026-05-02") == []


# output_schema

def test_output_schema_invalid_json_is_error() -> None:
    issues = _validate(output_schema="{bad json")
    assert any(i.field == "output_schema" and i.severity == "error" for i in issues)


def test_output_schema_must_be_object() -> None:
    issues = _validate(output_schema='["not", "an", "object"]')
    assert any(i.field == "output_schema" and i.severity == "error" for i in issues)


def test_output_schema_valid_subset_passes() -> None:
    issues = _validate(
        output_schema='{"type":"array","items":{"type":"object","properties":{"id":{"type":"integer"}}}}'
    )
    assert issues == []


# helpers

def test_errors_filters_out_warnings() -> None:
    issues = [
        schema.Issue("a", "error", "x"),
        schema.Issue("b", "warning", "y"),
        schema.Issue("c", "error", "z"),
    ]
    assert [i.field for i in schema.errors(issues)] == ["a", "c"]
    assert [i.field for i in schema.warnings(issues)] == ["b"]


def test_render_format_uses_severity_glyphs() -> None:
    out = schema.render_issues([
        schema.Issue("name", "error", "required"),
        schema.Issue("version", "warning", "not semver"),
    ])
    lines = out.split("\n")
    assert lines[0].startswith("✗ name")
    assert lines[1].startswith("⚠ version")


# Smoke: happy create still works (regression guard for schema integration)

def test_create_still_works_with_valid_inputs(
    tmp_home_no_env, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from alpi.tools.skill import Skill
    monkeypatch.setenv("ALPI_HOME", str(tmp_home_no_env))
    r = Skill().run(
        action="create",
        name="schema-smoke",
        category="miscellaneous",
        description="Smoke test for schema integration",
        body="## When to use\nNever in tests.\n",
    )
    assert r.ok, r.error


def test_create_surfaces_schema_warnings_in_output(
    tmp_home_no_env, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Warnings are non-blocking but must reach the LLM, otherwise the
    skill ships with a malformed field (e.g. ``'25 min'`` keyword) and
    the runtime silently fails to fire."""
    from alpi.tools.skill import Skill
    monkeypatch.setenv("ALPI_HOME", str(tmp_home_no_env))
    r = Skill().run(
        action="create",
        name="warning-surfaced",
        category="miscellaneous",
        description="Short",
        body="## When to use\nN/A.\n",
        keywords=["pomodoro", "25 min"],  # second one warns
    )
    assert r.ok, r.error
    assert "schema warnings" in r.output
    assert "keywords" in r.output
    assert "25 min" in r.output


def test_create_rejects_with_field_level_error(
    tmp_home_no_env, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from alpi.tools.skill import Skill
    monkeypatch.setenv("ALPI_HOME", str(tmp_home_no_env))
    r = Skill().run(
        action="create",
        name="Bad-Name",
        category="miscellaneous",
        description="ok",
        body="## When to use\nNever.\n",
    )
    assert not r.ok
    assert "name" in r.error
    assert "kebab-case" in r.error
