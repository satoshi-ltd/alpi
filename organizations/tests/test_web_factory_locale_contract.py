import json
from pathlib import Path

import pytest

WEB_FACTORY = Path(__file__).resolve().parents[1] / "web-factory"
SPEC = WEB_FACTORY / "factory" / "template-spec.json"
I18N_DIR = WEB_FACTORY / "templates" / "hotel-web" / "src" / "i18n"
SCOUT_SKILL = WEB_FACTORY / "agents" / "scout" / "skills" / "meta" / "intake-interview" / "SKILL.md"

pytestmark = pytest.mark.skipif(
    not WEB_FACTORY.exists(),
    reason="organizations/web-factory/ is not in this checkout (subtree imported once acceptance fixtures pass)",
)


def test_supported_locales_match_shipped_i18n_files():
    spec = json.loads(SPEC.read_text())
    declared = set(spec["i18n"]["supportedLocales"])
    shipped = {p.stem for p in I18N_DIR.glob("*.json")}
    assert declared == shipped, (
        f"template-spec.json supportedLocales drift from src/i18n/*.json: "
        f"declared-only={sorted(declared - shipped)}, shipped-only={sorted(shipped - declared)}"
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
