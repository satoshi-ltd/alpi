"""CH.4 regression guard: skills_index_block + keyword_match_hint stay metadata-only (no body leak)."""

from __future__ import annotations

from pathlib import Path

import pytest

from alpi.tools.skill import keyword_match_hint, skills_index_block


BODY_SENTINEL = "ZBODYLEAK_DO_NOT_INJECT_5f3a91"
SCRIPT_SENTINEL = "ZSCRIPTLEAK_DO_NOT_INJECT_88c4b2"
REFERENCE_SENTINEL = "ZREFLEAK_DO_NOT_INJECT_124aa9"


def _write_skill(
    home: Path,
    *,
    name: str = "regression-guard",
    category: str = "miscellaneous",
    description: str = "Pinned guard skill — keyword foozle.",
    keywords: list[str] | None = None,
    body: str = "",
    extra_files: dict[str, str] | None = None,
) -> Path:
    skill_dir = home / "skills" / category / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    kw_line = ""
    if keywords:
        kw_line = "keywords: [" + ", ".join(keywords) + "]\n"
    skill_md = (
        "---\n"
        f"name: {name}\n"
        f"description: {description}\n"
        f"category: {category}\n"
        "version: 0.1.0\n"
        "origin: user\n"
        f"{kw_line}"
        "---\n\n"
        f"{body}\n"
    )
    (skill_dir / "SKILL.md").write_text(skill_md, encoding="utf-8")
    for rel, content in (extra_files or {}).items():
        target = skill_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return skill_dir


def test_skills_index_block_does_not_leak_skill_body(tmp_home: Path) -> None:
    body = (
        "## When to use\n"
        f"This body must NEVER appear in the prompt. Sentinel: {BODY_SENTINEL}.\n"
        "It contains step-by-step instructions that the LLM only sees after "
        "calling skill(action='view').\n"
    )
    _write_skill(tmp_home, body=body)

    index = skills_index_block(tmp_home)

    assert index, "fake skill should be eligible and indexed"
    assert "regression-guard" in index, "name should appear in the index"
    assert "Pinned guard skill" in index, "description should appear in the index"
    assert BODY_SENTINEL not in index, (
        "skills_index_block must stay metadata-only — body must not leak"
    )


def test_skills_index_block_does_not_leak_scripts_or_references(tmp_home: Path) -> None:
    _write_skill(
        tmp_home,
        body="## When to use\nNormal prose body.\n",
        extra_files={
            "scripts/run.py": f"# {SCRIPT_SENTINEL}\nprint('hello')\n",
            "references/notes.md": f"# Notes\n\n{REFERENCE_SENTINEL}\n",
        },
    )

    index = skills_index_block(tmp_home)

    assert "regression-guard" in index
    assert SCRIPT_SENTINEL not in index, (
        "scripts/run.py contents must NOT appear in the index"
    )
    assert REFERENCE_SENTINEL not in index, (
        "references/*.md contents must NOT appear in the index"
    )


def test_keyword_match_hint_does_not_leak_skill_body(tmp_home: Path) -> None:
    body = (
        "## Workflow\n"
        f"Hidden body content — sentinel {BODY_SENTINEL}.\n"
    )
    _write_skill(
        tmp_home,
        keywords=["foozle"],
        body=body,
    )

    hint = keyword_match_hint(tmp_home, "I need to do foozle right now")

    assert hint, "keyword should trigger the hint"
    assert "regression-guard" in hint, "skill name should appear in the hint"
    assert BODY_SENTINEL not in hint, (
        "keyword_match_hint must stay metadata-only — body must not leak"
    )


def test_keyword_match_hint_capped_and_metadata_only(tmp_home: Path) -> None:
    """Even with many keyword-matching skills, the hint only lists names."""
    for i in range(6):
        _write_skill(
            tmp_home,
            name=f"guard-{i}",
            description=f"Guard {i}.",
            keywords=["foozle"],
            body=f"Body for guard-{i} containing sentinel {BODY_SENTINEL}-{i}.\n",
        )

    hint = keyword_match_hint(tmp_home, "let's foozle the thing")

    assert hint
    for i in range(6):
        assert f"{BODY_SENTINEL}-{i}" not in hint
    listed = sum(1 for i in range(6) if f"guard-{i}" in hint)
    assert listed >= 1, "at least one matching skill should appear in the hint"


def test_inactive_skills_do_not_appear_in_index(
    tmp_home: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """requires_env gating must hide skills from the index even before body-leak rules apply."""
    skill_dir = tmp_home / "skills" / "miscellaneous" / "needs-secret"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: needs-secret\n"
        "description: Should be hidden without the env var.\n"
        "category: miscellaneous\n"
        "version: 0.1.0\n"
        "origin: user\n"
        "requires_env: [ZREGRESSION_GUARD_SECRET]\n"
        "---\n\nbody\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("ZREGRESSION_GUARD_SECRET", raising=False)

    index = skills_index_block(tmp_home)

    assert "needs-secret" not in index, (
        "skills failing requires_env must be hidden from the prompt"
    )
