from pathlib import Path

import pytest

from alpi.tools._skill_schema import errors, validate_frontmatter
from alpi.tools.skill import CATEGORIES, _frontmatter_from_text

ORGS_ROOT = Path(__file__).resolve().parents[1]

SKILLS = sorted(ORGS_ROOT.rglob("SKILL.md"))


@pytest.mark.parametrize("skill_md", SKILLS, ids=lambda p: str(p.relative_to(ORGS_ROOT)))
def test_skill_frontmatter_valid(skill_md):
    meta = _frontmatter_from_text(skill_md.read_text())
    es = errors(validate_frontmatter(meta, categories=CATEGORIES))
    assert not es, f"{skill_md.relative_to(ORGS_ROOT)}: {es}"


def test_skill_categories_within_alpi_enum():
    leak = []
    for md in SKILLS:
        meta = _frontmatter_from_text(md.read_text())
        cat = meta.get("category")
        if cat and cat not in CATEGORIES:
            leak.append(f"{md.relative_to(ORGS_ROOT)}: {cat!r}")
    assert not leak, "Skills outside alpi CATEGORIES enum (would be dropped from system-prompt index):\n  " + "\n  ".join(leak)
