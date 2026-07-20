import json
from pathlib import Path

WEB_FACTORY = Path(__file__).resolve().parents[1] / "web-factory"
SPEC = WEB_FACTORY / "factory" / "template-spec.json"
QUILL_SKILL = (
    WEB_FACTORY / "agents" / "quill" / "skills" / "creative" / "hotel-voice-tone" / "SKILL.md"
)
MIRA_LIFECYCLE = (
    WEB_FACTORY / "agents" / "mira" / "skills" / "meta" / "project-lifecycle" / "SKILL.md"
)


def test_binding_catalogue_never_uses_ambiguous_page_intro():
    catalogue = json.loads(SPEC.read_text())["bindingCatalogue"]
    ambiguous = {
        page
        for page, bindings in catalogue.items()
        if "page.intro" in bindings
    }
    assert not ambiguous, (
        "Use page.intro.title/page.intro.body instead of the ambiguous "
        f"page.intro binding: {sorted(ambiguous)}"
    )


def test_quill_and_mira_pin_the_pre_translation_contract():
    quill = QUILL_SKILL.read_text()
    lifecycle = MIRA_LIFECYCLE.read_text()
    assert '"intro": { "title":' in quill
    assert "npm run content-check" in lifecycle
    assert "failure is a Quill `#content-fix`" in lifecycle
    assert "Run the same gate again" in lifecycle
    assert "Lingua" in lifecycle
    assert "`#translation-fix`" in lifecycle
