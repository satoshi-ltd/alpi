from pathlib import Path

import pytest

WEB_FACTORY = Path(__file__).resolve().parents[1] / "web-factory"
SCOUT_SKILL = WEB_FACTORY / "agents" / "scout" / "skills" / "meta" / "intake-interview" / "SKILL.md"

pytestmark = pytest.mark.skipif(
    not WEB_FACTORY.exists(),
    reason="organizations/web-factory/ is not in this checkout (subtree imported once acceptance fixtures pass)",
)


def test_scout_skill_references_template_spec_for_locales():
    body = SCOUT_SKILL.read_text()
    assert "factory/template-spec.json" in body, (
        "scout/intake-interview/SKILL.md must point at factory/template-spec.json "
        "as the single source of truth for locales (do not duplicate the list)."
    )
    assert "supportedLocales" in body, (
        "scout/intake-interview/SKILL.md must reference "
        "i18n.supportedLocales explicitly."
    )
