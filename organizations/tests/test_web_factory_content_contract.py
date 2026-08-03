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
    scout = " ".join((AGENTS / "scout" / "agent.md").read_text().split())
    assert "only if it is present" in scout
    assert "commodity one-liners are NOT" in scout
    assert "`label: <reason>` note" in scout
    assert "must include `reviews` whenever the enrichment captured" in scout
    assert "site.legal.company" in scout
    assert "`work/intake.md`" in scout


def test_muse_pins_the_slot_bridge():
    muse = (AGENTS / "muse" / "agent.md").read_text()
    assert "`<prefix>-<slug>`" in muse
    assert "NEVER invent your own" in muse


def test_one_logo_slot_on_one_ground():
    """Header and footer are both ink, so a light-ground variant has nowhere to render."""
    muse = " ".join((AGENTS / "muse" / "agent.md").read_text().split())
    scout = " ".join((AGENTS / "scout" / "agent.md").read_text().split())
    assert "The logo slot is `logo` and it renders on a dark ground" in muse
    assert "A logo drawn in dark ink is a client-input gap" in muse
    assert "white on transparency" in muse
    assert "`brand.logo` is the bare slot name `logo`" in scout
    for stale in ("logo-on-dark", "logoOnDark"):
        assert stale not in muse and stale not in scout, f"{stale} survives one-slot"


def test_muse_never_authors_client_media():
    muse = " ".join((AGENTS / "muse" / "agent.md").read_text().split())
    assert "Write only `assets/manifest.yaml`" in muse
    assert "`assets/source/` is client input and you never write into it" in muse
    assert "decisions about files, never files" in muse


def test_muse_cannot_fabricate_a_brand():
    muse = " ".join((AGENTS / "muse" / "agent.md").read_text().split())
    assert "A hotel's logo is never yours to make" in muse
    assert "an SVG built out of `<text>` is exactly as forbidden" in muse
    assert "leave `logo` out of the manifest entirely" in muse
    assert "typographic brand lockup" in muse
    assert "false provenance claim" in muse


def test_lens_never_passes_a_red_gate():
    lens = " ".join((AGENTS / "lens" / "agent.md").read_text().split())
    assert "A red gate is never a PASS" in lens
    assert "Your verdict describes the ARTIFACT, not fault" in lens
    assert "QA BLOCKED · template gap" in lens
    assert "it earns `QA BLOCKED`, never `QA PASS`" in lens



def test_logo_skill_never_self_triggers_on_a_missing_logo():
    skill = AGENTS / "muse" / "skills" / "creative" / "make-logo-svg" / "SKILL.md"
    body = " ".join(skill.read_text().split())
    assert "NEVER for a client hotel's logo" in body
    assert "A client hotel having no logo is NOT a reason to run this skill" in body
    assert "explicit written authorization that names this skill" in body
    assert "never a reason to run this skill" in body
    assert "First choice when the hotel has no logo" not in body
    assert "assets/source/logo.svg" not in body


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
    assert "that same slug VERBATIM, never shortened" in quill
    assert "NEVER add an `image` field" in quill
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
    assert '"check:audit"' not in recipe
    assert "src/i18n/*.json` dictionaries INCLUDED" in lingua
    assert "src/i18n/*.json` dictionaries" in pixel
    assert "EXACTLY as Lens reported them" in lifecycle
    assert "NEVER run `npm run verify`" in lens


def test_mira_lifecycle_keeps_lens_verdict_authority():
    lifecycle = MIRA_LIFECYCLE.read_text()
    assert "The QA verdict is Lens's, not `check:audit`'s" in lifecycle
    assert "Never record `test_ready` over a Lens `QA FAIL`" in lifecycle


def test_lens_flags_count_contradictions_as_template_gaps():
    lens = " ".join((AGENTS / "lens" / "agent.md").read_text().split())
    assert "must match the count the page itself renders" in lens
    assert "template gap, not a content defect" in lens


def test_testimonial_language_contract():
    quill = " ".join((AGENTS / "quill" / "agent.md").read_text().split())
    lingua = " ".join((AGENTS / "lingua" / "agent.md").read_text().split())
    assert "never a `rating`, never the platform" in quill
    assert "source language, testimonials included" in quill
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


def test_dining_has_the_same_flagship_discipline_as_amenities():
    """regio opened /restaurante/ on a bare card (0 flagships); roma stacked 3 features."""
    scout = " ".join((AGENTS / "scout" / "agent.md").read_text().split())
    skill = " ".join((AGENTS / "scout" / "skills" / "meta" / "hotel-enrichment" / "SKILL.md").read_text().split())
    assert "Dining follows the same flagship discipline" in scout
    assert "zero flagships opens the dining page on a bare card" in scout
    assert "AND for every dining venue" in skill


def test_scope_is_the_briefs_never_a_members_pick():
    """beachmate: a chain brief shipped as one property after an unanswered scope question."""
    scout = " ".join((AGENTS / "scout" / "agent.md").read_text().split())
    mira = " ".join((AGENTS / "mira" / "agent.md").read_text().split())
    assert "is ONE site covering every property" in scout
    assert "Narrowing scope is deriving a fact" in scout
    assert "`#done BLOCKED · scope: <question>`" in scout
    assert "A member question addressed to you gets an answer in your next turn" in mira
    assert "never a member's pick of one" in mira


def test_scout_never_links_legal_in_nav_groups():
    scout = " ".join((AGENTS / "scout" / "agent.md").read_text().split())
    assert "never put `legal` inside any nav or footer group" in scout
    assert "linking only enabled pages" in scout
    assert "Never set `pages.legal: false` when `site.legal.company` exists" in scout


def test_scout_booking_schema_is_closed():
    scout = " ".join((AGENTS / "scout" / "agent.md").read_text().split())
    assert "closed shape the template requires" in scout
    assert "write the block WITHOUT `propertyId`" in scout
    assert "Never invent one" in scout


def test_mira_review_orders_protocol():
    skill = " ".join((AGENTS / "mira" / "skills" / "meta" / "review-orders" / "SKILL.md").read_text().split())
    assert "write it VERBATIM to `work/review/<review-id>.md`" in skill
    assert "VERBATIM is a COPY operation, not a retelling" in skill
    assert "a fabricated client request" in skill
    assert "never edit, renumber, or reword it" in skill
    assert "NOBODY — out of boundary" in skill
    assert "the brief always wins over the work order" in skill
    assert "A note silently dropped is a failure" in skill
    assert "never re-paste the document into a task" in skill


def test_muse_sees_but_never_creates_unauthorized():
    muse = " ".join((AGENTS / "muse" / "agent.md").read_text().split())
    assert "read_image" not in muse.split("---")[1]
    assert "inspecting is always allowed, generating never is by default" in muse


def test_gallery_slots_never_orphan_silently():
    muse = " ".join((AGENTS / "muse" / "agent.md").read_text().split())
    scout = " ".join((AGENTS / "scout" / "agent.md").read_text().split())
    assert "Silent orphan gallery slots ship dead bytes" in muse
    assert "`pages.gallery` and the gallery slots move together, always" in scout



def test_quill_about_requires_authored_body():
    quill = " ".join((AGENTS / "quill" / "agent.md").read_text().split())
    assert "REQUIRES the `about` block inside" in quill
    assert "that block IS the about page" in quill
    assert "renders it from authored content only" in quill


def test_about_is_always_on():
    scout = " ".join((AGENTS / "scout" / "agent.md").read_text().split())
    assert "`pages.about` is ALWAYS true" in scout
    assert "storytelling briefing" in scout


def test_lens_audits_meta_uniqueness_empty_pages_and_waste():
    lens = " ".join((AGENTS / "lens" / "agent.md").read_text().split())
    assert "UNIQUE `<title>` and meta description per page and per locale" in lens
    assert "little more than its h1 is a FAIL" in lens
    assert "dead bytes" in lens


def test_brief_can_pin_aesthetics():
    scout = " ".join((AGENTS / "scout" / "agent.md").read_text().split())
    readme = " ".join((WEB_FACTORY / "README.md").read_text().split())
    assert "An explicit client choice always wins" in scout
    assert "always wins over the AI's choice" in readme


def test_seo_coverage_and_structured_address():
    quill = " ".join((AGENTS / "quill" / "agent.md").read_text().split())
    scout = " ".join((AGENTS / "scout" / "agent.md").read_text().split())
    assert "fill it for EVERY page you write" in quill
    assert "structured `contact.address` fields" in scout


def test_updates_never_touch_the_web_and_category_is_literal():
    scout = " ".join((AGENTS / "scout" / "agent.md").read_text().split())
    assert "NEVER touch the web" in scout
    assert "copies the brief's rating type literally" in scout
    assert "must cover EVERY site locale" in scout


def test_id_provenance_and_hero_resolution():
    scout = " ".join((AGENTS / "scout" / "agent.md").read_text().split())
    muse = " ".join((AGENTS / "muse" / "agent.md").read_text().split())
    assert "never mistake a number found in an asset URL or CMS path" in scout
    assert "Choose every slot by CONTENT first, then resolution" in muse


def test_brief_register_and_supplied_alt():
    quill = " ".join((AGENTS / "quill" / "agent.md").read_text().split())
    lingua = " ".join((AGENTS / "lingua" / "agent.md").read_text().split())
    muse = " ".join((AGENTS / "muse" / "agent.md").read_text().split())
    assert "Honour the brief's tone in every string" in quill
    assert "Carry the source register across locales" in lingua
    assert "Supplied slots ALSO carry `alt`" in muse


def test_scout_never_disables_a_mandated_page_to_clear_a_gate():
    scout = " ".join((AGENTS / "scout" / "agent.md").read_text().split())
    assert "A red gate is never cleared by disabling a page the brief mandates" in scout
    assert "a \"temporary\" flip is never revisited" in scout


def test_quill_never_invents_numbers():
    quill = " ".join((AGENTS / "quill" / "agent.md").read_text().split())
    assert "NUMBERS are the sharpest edge" in quill
    assert "a fabricated monetary commitment reaches the guest as a promise" in quill
    assert "Five room TYPES is not eleven rooms" in quill


def test_quill_never_deletes_content_for_a_disabled_page():
    quill = " ".join((AGENTS / "quill" / "agent.md").read_text().split())
    assert "Do not delete authored content because a config flag disables its page" in quill
    assert "survive a red gate" in quill



def test_briefing_guide_exists_and_pins_the_essentials():
    guide = " ".join((WEB_FACTORY / "BRIEFING.md").read_text().split())
    for k in ("ID de hotel del motor Mirai", "Tarifas «desde»", "Datos societarios",
              "No mandes un volcado de la web actual", "Nada se inventa"):
        assert k in guide, f"BRIEFING.md lost: {k}"
    readme = " ".join((WEB_FACTORY / "README.md").read_text().split())
    assert "`BRIEFING.md`" in readme

def test_scout_names_the_logo_by_slot_not_by_client_filename():
    scout = " ".join((AGENTS / "scout" / "agent.md").read_text().split())
    assert "`brand.logo` is the bare slot name `logo`" in scout
    assert "never a path, never an extension, never the client's filename" in scout
    assert "The manifest owns the indirection" in scout


def test_scout_moves_gallery_page_and_slots_together():
    scout = " ".join((AGENTS / "scout" / "agent.md").read_text().split())
    assert "`pages.gallery` and the gallery slots move together, always" in scout
    assert "enabled with no `gallery-*` slot builds a page with nothing in it" in scout
    assert "enabled WITH `gallery-1..N` as placeholders" in scout


def test_scout_takes_the_accent_from_enrichment_when_the_brief_is_silent():
    scout = " ".join((AGENTS / "scout" / "agent.md").read_text().split())
    assert "A `Brand colour` line in `work/enrichment.md`" in scout
    assert "Map it to `tokens.accent`" in scout
    assert "Never derive a colour yourself" in scout
    for key in ("accent", "accent2", "ink", "paper", "surface", "fontHead", "fontBody"):
        assert key in scout, f"token key {key} missing from the allowed set"


def test_enrichment_captures_the_brand_colour_as_a_single_source_fact():
    skill = " ".join(
        (AGENTS / "scout" / "skills" / "meta" / "hotel-enrichment" / "SKILL.md").read_text().split()
    )
    assert "DO write the hotel's brand colour" in skill
    assert "with WHERE it came from" in skill
    assert "The brand colour is the one exception, and only it" in skill
    assert "no second source exists" in skill
    assert "Read it, never eyeball it from a screenshot" in skill


def test_muse_defers_the_logo_ground_to_the_measured_check():
    """v5 shipped an invisible header: muse read the file and applied the prose rule inverted."""
    muse = " ".join((AGENTS / "muse" / "agent.md").read_text().split())
    assert "alpha-weighted ink luminance" in muse
    assert "fails the slot when the mark cannot carry that ground at 3:1" in muse
    for prose in ("reads ONLY on a DARK ground", "leave `logo` OUT entirely"):
        assert prose not in muse, (
            "the branch table is now a measured gate; two copies means the next "
            "reader trusts the weaker one"
        )


def test_mira_defers_declared_transitions_to_the_daemon():
    body = " ".join(MIRA_LIFECYCLE.read_text().split())
    assert "daemon owns declared pipeline transitions" in body
    assert "Never duplicate that task" in body
    assert "workgroup trigger <wg_id> <pipeline>" in body
    assert "open the owner task explicitly" in body


def test_media_update_chain_lives_in_its_own_skill():
    skill = AGENTS / "mira" / "skills" / "meta" / "media-update" / "SKILL.md"
    body = " ".join(skill.read_text().split())
    assert "workgroup trigger <wg_id> media-update" in body
    assert "owns the order below" in body
    assert "never re-state the order in a post" in body
    assert "Phase 2 is conditional, not disposable" in body
    assert "NOT optional when `media-update` declared the `logo` slot" in body
    assert "must be the bare slot name" in body
    assert "is a false claim" in body


def test_post_launch_protocols_are_triggered_not_recalled():
    readme = " ".join((AGENTS.parent / "README.md").read_text().split())
    for key in ("media-update", "content-update", "review"):
        assert f"alpi -p mira workgroup trigger <wg_id> {key}" in readme
    assert "There is no free-text suffix on a trigger" in readme


def test_mira_uses_the_declared_gate_commands():
    body = " ".join((AGENTS / "mira" / "agent.md").read_text().split())
    assert "eight phases" in body
    assert "npm run check:setup" in body
    assert "npm run check:enrichment" in body
    assert "npm run check:audit" in body
    lifecycle = MIRA_LIFECYCLE.read_text()
    assert "## Post-launch operations" not in lifecycle, (
        "the chain belongs in media-update, not in the skill Mira reads every launch turn"
    )


def test_scout_runs_its_own_gate_before_handing_off():
    """v3 handed off 11 failures for rules the contract already stated — it never ran the check."""
    scout = " ".join((AGENTS / "scout" / "agent.md").read_text().split())
    assert "Before you hand off, run the check" in scout
    assert "only hand off green" in scout
    assert 'it is not "run or request"' in scout


def test_scout_has_a_worked_footer_example():
    scout = (AGENTS / "scout" / "agent.md").read_text()
    assert '"label": "nav.explore"' in scout
    assert '"brand": true' in scout
    assert "never objects" in scout


def test_enrichment_is_gap_driven_not_exploratory():
    skill = " ".join(
        (AGENTS / "scout" / "skills" / "meta" / "hotel-enrichment" / "SKILL.md").read_text().split()
    )
    assert "Step 0 — list the gaps" in skill
    assert "If the brief states it, do not look it up and do not write it" in skill
    assert "Never a sweep, never following links" in skill
    assert "closed allowlist of three" in skill.lower()
    for banned in ("Google Hotels", "a tourism portal"):
        assert banned in skill, f"the allowlist must name {banned} as excluded"


def test_testimonials_are_a_deliverable_not_a_bonus():
    """v5 shipped with no testimonials because the skill granted permission instead of asking."""
    skill = " ".join(
        (AGENTS / "scout" / "skills" / "meta" / "hotel-enrichment" / "SKILL.md").read_text().split()
    )
    assert "ALWAYS with guest reviews as one of its questions" in skill
    assert "Testimonials are a deliverable of this phase, not a bonus" in skill
    assert "required, not conditional" in skill
    assert "an absent section reads as \"not attempted\"" in skill
    assert "omits them silently rather than failing" in skill


def test_lens_must_back_every_claim_or_label_it():
    lens = " ".join((AGENTS / "lens" / "agent.md").read_text().split())
    assert "quote the gate line or the file path you read it from" in lens
    assert "write `opinion:` in front of the sentence" in lens
    assert "manufactures confidence" in lens

