from pathlib import Path

WEB_FACTORY = Path(__file__).resolve().parents[1] / "web-factory"
AGENTS = WEB_FACTORY / "agents"
RECIPE = WEB_FACTORY / "recipes" / "hotel.yaml"
MIRA_LIFECYCLE = AGENTS / "mira" / "skills" / "meta" / "project-lifecycle" / "SKILL.md"


def test_quill_pins_the_composition_contract():
    quill = (AGENTS / "quill" / "agent.md").read_text()
    assert "content-system.js" in quill
    assert "NEVER inflate" in quill
    assert "composition targets" in quill
    assert "`featured: true` — only on entries whose substantive `body` exists" in quill
    assert "the thin truth" in quill


def test_scout_feeds_composition_and_legal_identity():
    scout = (AGENTS / "scout" / "agent.md").read_text()
    assert "ONLY if the skill is present" in scout
    assert "Never promote a merely-named facility to flagship" in scout
    assert "site.legal.company" in scout
    assert "`work/intake.md`" in scout


def test_muse_pins_the_slot_bridge():
    muse = (AGENTS / "muse" / "agent.md").read_text()
    assert "`<prefix>-<slug>`" in muse
    assert "NEVER invent your own" in muse


def test_slug_table_is_the_single_naming_authority():
    for agent in ("scout", "quill", "muse"):
        body = " ".join((AGENTS / agent / "agent.md").read_text().split())
        assert "canonical slug table" in body, f"{agent} lost the slug-table rule"


def test_slug_contract_prevents_route_collisions():
    scout = " ".join((AGENTS / "scout" / "agent.md").read_text().split())
    quill = " ".join((AGENTS / "quill" / "agent.md").read_text().split())
    muse = " ".join((AGENTS / "muse" / "agent.md").read_text().split())
    assert "UNIQUE within its collection" in scout
    assert "prefix the property" in scout
    assert "VERBATIM — never a shortened variant" in quill
    assert "NEVER adding an `image` field" in quill
    assert "flat `slots:` mapping at the root" in muse


def test_lens_never_penalizes_brevity():
    lens = (AGENTS / "lens" / "agent.md").read_text()
    assert "brevity alone is NEVER a defect" in lens
    assert "substantive body" in lens


def test_recipe_tasks_are_thin_triggers():
    import yaml

    recipe = yaml.safe_load(RECIPE.read_text())
    for phase, step in recipe["pipeline_steps"].items():
        assert len(step["task"]) <= 120, (
            f"{phase} task is prose again ({len(step['task'])} chars); the how "
            "belongs in the owner's agent.md, the task is only a trigger"
        )
    assert "work/intake.md" in RECIPE.read_text()
    assert "Test workgroup" not in RECIPE.read_text()


def test_runtime_boundary_is_pinned_for_every_writer():
    recipe = RECIPE.read_text()
    lingua = (AGENTS / "lingua" / "agent.md").read_text()
    pixel = (AGENTS / "pixel" / "agent.md").read_text()
    lifecycle = MIRA_LIFECYCLE.read_text()
    lens = (AGENTS / "lens" / "agent.md").read_text()
    assert '"check:final"' in recipe.split("qa:")[1]
    assert "src/i18n/*.json` dictionaries INCLUDED" in lingua
    assert "src/i18n/*.json` dictionaries" in pixel
    assert "EXACTLY as Lens reported them" in lifecycle
    assert "NEVER run `npm run verify`" in lens


def test_mira_lifecycle_keeps_lens_verdict_authority():
    lifecycle = MIRA_LIFECYCLE.read_text()
    assert "a green `npm run verify` alone is NOT approval" in lifecycle


def test_lens_flags_count_contradictions_as_template_gaps():
    lens = " ".join((AGENTS / "lens" / "agent.md").read_text().split())
    assert "must match the count the page itself renders" in lens
    assert "template gap, not a content defect" in lens


def test_testimonial_language_contract():
    quill = " ".join((AGENTS / "quill" / "agent.md").read_text().split())
    lingua = " ".join((AGENTS / "lingua" / "agent.md").read_text().split())
    assert "never a `rating` field" in quill
    assert "written in the source language, testimonials included" in quill
    assert "The locale matching the original language gets the VERBATIM original" in lingua
    assert "Identical quote text across two locales fails the gate" in lingua


def test_mira_never_advances_a_red_gate():
    lifecycle = " ".join(MIRA_LIFECYCLE.read_text().split())
    assert "A FAILED phase gate is never advanced past" in lifecycle
    assert "NEVER substitutes a green gate" in lifecycle


def test_enrichment_testimonials_cover_multi_property_and_language():
    skill = " ".join((AGENTS / "scout" / "skills" / "meta" / "hotel-enrichment" / "SKILL.md").read_text().split())
    lingua = " ".join((AGENTS / "lingua" / "agent.md").read_text().split())
    assert "Record each quote's ORIGINAL LANGUAGE" in skill
    assert "Multi-property briefs are NOT exempt" in skill
    assert "rewording a quote in the SAME language" in lingua


def test_scout_never_links_legal_in_nav_groups():
    scout = " ".join((AGENTS / "scout" / "agent.md").read_text().split())
    assert "`legal` as a LINK inside any nav/footer group" in scout
    assert "Footer groups link enabled, linkable pages only" in scout


def test_scout_booking_schema_is_closed():
    scout = " ".join((AGENTS / "scout" / "agent.md").read_text().split())
    assert "`site.booking` is a CLOSED shape" in scout
    assert "Never invent provider values" in scout
    assert "omit `booking` entirely and record the gap" in scout


def test_mira_review_orders_protocol():
    skill = " ".join((AGENTS / "mira" / "skills" / "meta" / "review-orders" / "SKILL.md").read_text().split())
    assert "write it VERBATIM to `work/review/<review-id>.md`" in skill
    assert "never edit, renumber, or reword it" in skill
    assert "NOBODY — out of boundary" in skill
    assert "the brief always wins over the work order" in skill
    assert "A note silently dropped is a failure" in skill
    assert "never re-paste the document into a task" in skill
