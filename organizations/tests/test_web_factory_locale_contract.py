from pathlib import Path

import pytest

WEB_FACTORY = Path(__file__).resolve().parents[1] / "web-factory"
SCOUT_SKILL = WEB_FACTORY / "agents" / "scout" / "skills" / "meta" / "intake-interview" / "SKILL.md"

pytestmark = pytest.mark.skipif(
    not WEB_FACTORY.exists(),
    reason="organizations/web-factory/ is not in this checkout (subtree imported once acceptance fixtures pass)",
)


def test_scout_skill_references_clone_locale_sources():
    body = SCOUT_SKILL.read_text()
    assert "src/i18n/" in body, (
        "scout/intake-interview/SKILL.md must point at the clone's src/i18n/*.json "
        "dictionaries as the supported-locale source of truth."
    )
    assert "route-slugs" in body, (
        "scout/intake-interview/SKILL.md must reference src/config/route-slugs.js "
        "as the mirror of the supported-locale set."
    )
    assert "read what the clone actually ships" in body
