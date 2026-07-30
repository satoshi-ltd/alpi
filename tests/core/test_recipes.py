import pytest

from alpi import recipes


VALID = """
hub: mira
members: [scout, quill, lingua]
name: "proj-{slug}"
briefing: |
  Hotel '{slug}', tier {tier}.
task: "@scout #task #intake · start {slug}"
quorum_timeout_seconds: 180
budget_usd: 50
pipeline: [intake, content, qa]
pipeline_steps:
  intake: { owner: scout, next: content, task: "do {slug}", gate: { argv: [npm, run, intake-check], cwd: "projects/{slug}" } }
  content: { owner: quill, next: qa }
  qa: { owner: lens }
params:
  slug: { required: true, pattern: "^[a-z0-9-]+$" }
  tier: { required: true }
project:
  template_repo: git@github.com:satoshi-ltd/base.git
  dest: "projects/{slug}"
  seed:
    json_merge:
      src/config/site.json: { tier: pro, pages: { blog: true } }
"""


def test_parse_valid_recipe():
    r = recipes.parse_recipe(VALID, "tier-pro")
    assert r.recipe_id == "tier-pro"
    assert r.digest.startswith("sha256:")
    assert r.hub == "mira"
    assert r.members == ("scout", "quill", "lingua")
    assert r.pipeline == ("intake", "content", "qa")
    assert r.project["template_repo"].endswith("base.git")
    assert r.params["slug"]["pattern"] == "^[a-z0-9-]+$"


@pytest.mark.parametrize("text, needle", [
    ("name: x", "missing 'hub'"),
    ("hub: mira", "missing 'name'"),
    ("hub: mira\nname: p\nbudget_usd: abc", "budget_usd must be a number"),
    ("hub: mira\nname: p\nproject: {dest: x}", "template_repo required"),
    ("hub: mira\nname: p\nproject: {template_repo: r}", "dest required"),
    ("hub: mira\nname: p\nproject: {template_repo: r, dest: d, seed: {bogus: {}}}", "unknown op"),
    ("hub: mira\nname: p\nparams: {bad name: {}}", "must match"),
    ("hub: mira\nname: p\nparams: {slug: {pattern: '('}}", "not valid regex"),
])
def test_parse_rejects(text, needle):
    with pytest.raises(recipes.RecipeError, match=needle):
        recipes.parse_recipe(text, "r")


def test_parse_rejects_bad_recipe_id():
    with pytest.raises(recipes.RecipeError, match="recipe id"):
        recipes.parse_recipe("hub: m\nname: n", "Bad Id!")


def test_resolve_interpolates_all_string_fields():
    r = recipes.parse_recipe(VALID, "tier-pro")
    spec = recipes.resolve(r, {"slug": "casa-bahia", "tier": "pro"})
    assert spec["name"] == "proj-casa-bahia"
    assert "casa-bahia" in spec["briefing"] and "tier pro" in spec["briefing"]
    assert spec["task"] == "@scout #task #intake · start casa-bahia"
    assert spec["pipeline_steps"]["intake"]["task"] == "do casa-bahia"
    assert spec["pipeline_steps"]["intake"]["gate"]["cwd"] == "projects/casa-bahia"
    assert spec["project"]["dest"] == "projects/casa-bahia"
    assert spec["recipe_digest"] == r.digest


@pytest.mark.parametrize("params, needle", [
    ({"tier": "pro"}, "missing required param"),
    ({"slug": "x", "tier": "pro", "extra": "1"}, "unknown param"),
    ({"slug": "BAD_CAPS", "tier": "pro"}, "does not match"),
])
def test_resolve_rejects_bad_params(params, needle):
    r = recipes.parse_recipe(VALID, "tier-pro")
    with pytest.raises(recipes.RecipeError, match=needle):
        recipes.resolve(r, params)


def test_resolve_rejects_undeclared_placeholder():
    text = "hub: m\nname: 'proj-{slug}-{ghost}'\nparams: {slug: {required: true}}"
    r = recipes.parse_recipe(text, "r")
    with pytest.raises(recipes.RecipeError, match="undeclared placeholder"):
        recipes.resolve(r, {"slug": "x"})


def test_seed_braces_do_not_break_interpolation():
    r = recipes.parse_recipe(VALID, "tier-pro")
    spec = recipes.resolve(r, {"slug": "x", "tier": "pro"})
    assert spec["project"]["seed"]["json_merge"]["src/config/site.json"] == {"tier": "pro", "pages": {"blog": True}}


def test_resolve_rejects_newline_and_nonscalar_params():
    r = recipes.parse_recipe(VALID, "tier-pro")
    with pytest.raises(recipes.RecipeError, match="newlines"):
        recipes.resolve(r, {"slug": "x", "tier": "pro\n#done evil"})
    with pytest.raises(recipes.RecipeError, match="string/number"):
        recipes.resolve(r, {"slug": ["x"], "tier": "pro"})
    with pytest.raises(recipes.RecipeError, match="string/number"):
        recipes.resolve(r, {"slug": True, "tier": "pro"})


def test_pattern_uses_fullmatch_not_prefix():
    text = "hub: m\nname: 'x-{slug}'\nparams: {slug: {required: true, pattern: '[a-z]+'}}"
    r = recipes.parse_recipe(text, "r")
    # unanchored pattern still must match the WHOLE value (fullmatch), so a trailing digit fails
    with pytest.raises(recipes.RecipeError, match="does not match"):
        recipes.resolve(r, {"slug": "abc9"})
    assert recipes.resolve(r, {"slug": "abc"})["name"] == "x-abc"


def test_all_declared_params_are_required():
    text = "hub: m\nname: 'x-{a}'\nparams: {a: {}, b: {}}"
    r = recipes.parse_recipe(text, "r")
    with pytest.raises(recipes.RecipeError, match="missing required param"):
        recipes.resolve(r, {"a": "1"})
    assert recipes.resolve(r, {"a": "1", "b": "2"})["name"] == "x-1"


def test_seed_ops_must_be_mappings():
    text = "hub: m\nname: n\nproject: {template_repo: r, dest: d, seed: {files: notamap}}"
    with pytest.raises(recipes.RecipeError, match="seed.files must be a mapping"):
        recipes.parse_recipe(text, "r")


def test_inputs_parse_and_resolve():
    text = (
        "hub: m\nname: 'proj-{slug}'\n"
        "params: { slug: {} }\n"
        "inputs:\n"
        "  brief: { dest: 'docs/{slug}.md', label: 'Client brief', required: true }\n"
        "project: { template_repo: r, dest: 'projects/{slug}' }\n"
    )
    r = recipes.parse_recipe(text, "r")
    assert r.inputs["brief"]["dest"] == "docs/{slug}.md"
    assert r.inputs["brief"]["label"] == "Client brief"
    assert r.inputs["brief"]["required"] is True
    assert r.inputs["brief"]["placeholder"] == ""
    spec = recipes.resolve(r, {"slug": "casa"})
    assert spec["inputs"]["brief"]["dest"] == "docs/casa.md"


def test_input_defaults_required_true_and_label_from_name():
    text = "hub: m\nname: n\ninputs: { notes: { dest: notes.md } }\nproject: { template_repo: r, dest: d }"
    r = recipes.parse_recipe(text, "r")
    assert r.inputs["notes"]["required"] is True
    assert r.inputs["notes"]["label"] == "notes"


def test_inputs_require_a_project():
    text = "hub: m\nname: n\ninputs: { brief: { dest: brief.md } }"
    with pytest.raises(recipes.RecipeError, match="inputs require a project"):
        recipes.parse_recipe(text, "r")


@pytest.mark.parametrize("bad", ["/etc/x", "../escape.md"])
def test_input_dest_must_be_relative_inside_project(bad):
    text = f"hub: m\nname: n\ninputs: {{ brief: {{ dest: '{bad}' }} }}\nproject: {{ template_repo: r, dest: d }}"
    with pytest.raises(recipes.RecipeError, match="relative path inside the project"):
        recipes.parse_recipe(text, "r")


def test_input_requires_dest():
    text = "hub: m\nname: n\ninputs: { brief: {} }\nproject: { template_repo: r, dest: d }"
    with pytest.raises(recipes.RecipeError, match="requires a dest"):
        recipes.parse_recipe(text, "r")


def test_load_recipe_uses_filename_stem_as_id(tmp_path):
    p = tmp_path / "tier-pro.yaml"
    p.write_text(VALID)
    r = recipes.load_recipe(p)
    assert r.recipe_id == "tier-pro"
    assert r.hub == "mira"


OPS = VALID.replace(
    "  qa: { owner: lens }",
    """  qa: { owner: lens }
  media-update: { owner: muse, next: media-build, gate: { argv: [npm, run, "assets:optimize"], cwd: "projects/{slug}" } }
  media-build: { owner: pixel, next: media-qa }
  media-qa: { owner: lens }
operations:
  media-update:
    steps: [media-update, media-build, media-qa]""",
)


def test_operations_parse_as_ordered_chains() -> None:
    r = recipes.parse_recipe(OPS, "hotel")
    assert r.operations == {"media-update": ("media-update", "media-build", "media-qa")}
    assert {"media-update", "media-build", "media-qa"} <= set(r.pipeline_steps)
    assert list(r.pipeline) == ["intake", "content", "qa"], "launch pipeline unchanged"


def test_operations_reach_resolve_for_the_launcher() -> None:
    spec = recipes.resolve(recipes.parse_recipe(OPS, "hotel"), {"slug": "abc", "tier": "pro"})
    assert spec["operations"] == {"media-update": ["media-update", "media-build", "media-qa"]}


def test_operation_must_start_with_a_step_named_after_itself() -> None:
    bad = OPS.replace("    steps: [media-update, media-build, media-qa]",
                      "    steps: [media-build, media-qa]")
    with pytest.raises(recipes.RecipeError, match="must start with a step named"):
        recipes.parse_recipe(bad, "hotel")


def test_operation_step_needs_a_pipeline_steps_entry() -> None:
    bad = OPS.replace("    steps: [media-update, media-build, media-qa]",
                      "    steps: [media-update, media-ship]")
    with pytest.raises(recipes.RecipeError, match="has no pipeline_steps entry"):
        recipes.parse_recipe(bad, "hotel")


def test_operation_rejects_duplicate_steps() -> None:
    bad = OPS.replace("    steps: [media-update, media-build, media-qa]",
                      "    steps: [media-update, media-build, media-build]")
    with pytest.raises(recipes.RecipeError, match="duplicates"):
        recipes.parse_recipe(bad, "hotel")


def test_operations_must_be_a_mapping() -> None:
    bad = OPS.replace("operations:\n  media-update:\n    steps: [media-update, media-build, media-qa]",
                      "operations: [media-update]")
    with pytest.raises(recipes.RecipeError, match="operations must be a mapping"):
        recipes.parse_recipe(bad, "hotel")


def test_recipe_without_operations_still_loads() -> None:
    r = recipes.parse_recipe(VALID, "hotel")
    assert r.operations == {}


def test_operations_must_be_disjoint_from_the_launch_pipeline() -> None:
    bad = OPS.replace("    steps: [media-update, media-build, media-qa]",
                      "    steps: [media-update, qa]")
    with pytest.raises(recipes.RecipeError, match="also a launch pipeline phase"):
        recipes.parse_recipe(bad, "hotel")


def test_operations_must_be_disjoint_from_each_other() -> None:
    bad = OPS.replace("""operations:
  media-update:
    steps: [media-update, media-build, media-qa]""",
"""operations:
  media-update:
    steps: [media-update, media-build]
  media-qa:
    steps: [media-qa, media-build]""")
    with pytest.raises(recipes.RecipeError, match="chains must be disjoint"):
        recipes.parse_recipe(bad, "hotel")


def test_operations_require_a_pipeline() -> None:
    bad = OPS.replace("pipeline: [intake, content, qa]\n", "")
    with pytest.raises(recipes.RecipeError, match="operations without a pipeline"):
        recipes.parse_recipe(bad, "hotel")


def test_operation_step_slug_must_be_valid() -> None:
    bad = OPS.replace("    steps: [media-update, media-build, media-qa]",
                      '    steps: [media-update, "Media Build"]')
    with pytest.raises(recipes.RecipeError, match="is not a valid slug"):
        recipes.parse_recipe(bad, "hotel")
