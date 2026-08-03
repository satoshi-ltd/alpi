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
pipelines:
  intake: [intake, content, qa]
launch: intake
pipeline_steps:
  intake: { owner: scout, task: "do {slug}", gate: { argv: [npm, run, intake-check], cwd: "projects/{slug}" } }
  content: { owner: quill }
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
    assert r.launch_chain == ("intake", "content", "qa")
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


LAUNCHLESS = """
hub: mira
name: post-launch
pipelines:
  media-update: [media-update, media-build, media-qa]
  content-update: [content-update, content-qa]
pipeline_steps:
  media-update: { owner: muse, task: "refresh the photos" }
  media-build: { owner: pixel }
  media-qa: { owner: lens }
  content-update: { owner: quill, task: "rewrite the copy" }
  content-qa: { owner: lens }
"""


MULTI = VALID.replace(
    "pipelines:\n  intake: [intake, content, qa]",
    "pipelines:\n  intake: [intake, content, qa]\n"
    "  media-update: [media-update, media-build, media-qa]",
).replace(
    "  qa: { owner: lens }",
    """  qa: { owner: lens }
  media-update: { owner: muse, task: "refresh {slug}", gate: { argv: [npm, run, "assets:optimize"], cwd: "projects/{slug}" } }
  media-build: { owner: pixel }
  media-qa: { owner: lens }""",
)


RETIRED_PIPELINE = """
hub: mira
name: retired
pipeline: [intake, content]
pipeline_steps:
  intake: { owner: scout, task: t }
  content: { owner: quill }
"""


RETIRED_OPERATIONS = """
hub: mira
name: retired
pipelines:
  intake: [intake, content]
launch: intake
operations:
  media-update:
    steps: [media-update, media-qa]
pipeline_steps:
  intake: { owner: scout, task: t }
  content: { owner: quill }
task: "@scout #task #intake · go"
"""


@pytest.mark.parametrize("text", [RETIRED_PIPELINE, RETIRED_OPERATIONS])
def test_parse_rejects_the_retired_pipeline_and_operations_keys(text) -> None:
    with pytest.raises(recipes.RecipeError, match="declares retired"):
        recipes.parse_recipe(text, "hotel")


def test_dormant_chains_are_declared_next_to_the_launch_chain() -> None:
    r = recipes.parse_recipe(MULTI, "hotel")
    assert r.pipelines == {
        "intake": ("intake", "content", "qa"),
        "media-update": ("media-update", "media-build", "media-qa"),
    }
    assert r.launch_pipeline == "intake"
    assert r.launch_chain == ("intake", "content", "qa"), "launch chain unchanged"
    assert {"media-update", "media-build", "media-qa"} <= set(r.pipeline_steps)


def test_canonical_pipelines_with_launch() -> None:
    r = recipes.parse_recipe(VALID, "hotel")
    assert r.pipelines == {"intake": ("intake", "content", "qa")}
    assert r.launch_pipeline == "intake"
    assert r.launch_chain == ("intake", "content", "qa")


def test_launchless_pipelines_are_valid() -> None:
    r = recipes.parse_recipe(LAUNCHLESS, "post")
    assert r.pipelines == {
        "media-update": ("media-update", "media-build", "media-qa"),
        "content-update": ("content-update", "content-qa"),
    }
    assert r.launch_pipeline is None
    assert r.launch_chain == ()
    assert r.task == ""


def test_deliberation_recipe_keeps_its_task_without_pipelines() -> None:
    r = recipes.parse_recipe("hub: mira\nname: debate\ntask: '@quill #task · discuss'", "debate")
    assert r.pipelines == {}
    assert r.launch_pipeline is None
    assert r.launch_chain == ()
    assert r.task == "@quill #task · discuss"


def test_retired_accessors_are_gone_and_launch_chain_is_read_only() -> None:
    r = recipes.parse_recipe(MULTI, "hotel")
    assert not hasattr(r, "operations")
    assert not hasattr(r, "pipeline")
    with pytest.raises(AttributeError):
        r.launch_chain = ("x",)


def test_pipeline_steps_are_validated_and_normalized_at_parse_time() -> None:
    r = recipes.parse_recipe(VALID, "hotel")
    assert r.pipeline_steps["intake"] == {
        "owner": "scout",
        "task": "do {slug}",
        "gate": {"argv": ["npm", "run", "intake-check"], "cwd": "projects/{slug}"},
    }
    assert r.pipeline_steps["content"] == {"owner": "quill"}
    assert all("next" not in step for step in r.pipeline_steps.values())


def test_resolve_returns_pipelines_and_launch_pipeline() -> None:
    spec = recipes.resolve(recipes.parse_recipe(VALID, "hotel"), {"slug": "abc", "tier": "pro"})
    assert spec["pipelines"] == {"intake": ["intake", "content", "qa"]}
    assert spec["launch_pipeline"] == "intake"
    assert "pipeline" not in spec
    assert "operations" not in spec
    assert spec["pipeline_steps"]["intake"]["task"] == "do abc"
    assert spec["pipeline_steps"]["intake"]["gate"]["cwd"] == "projects/abc"


def test_dormant_chains_reach_resolve_for_the_launcher() -> None:
    spec = recipes.resolve(recipes.parse_recipe(MULTI, "hotel"), {"slug": "abc", "tier": "pro"})
    assert spec["pipelines"] == {
        "intake": ["intake", "content", "qa"],
        "media-update": ["media-update", "media-build", "media-qa"],
    }
    assert spec["launch_pipeline"] == "intake"
    assert spec["pipeline_steps"]["media-update"]["gate"]["cwd"] == "projects/abc"


def test_launchless_pipelines_resolve_with_a_null_selector() -> None:
    spec = recipes.resolve(recipes.parse_recipe(LAUNCHLESS, "post"), {})
    assert spec["launch_pipeline"] is None
    assert spec["pipelines"]["content-update"] == ["content-update", "content-qa"]
    assert spec["task"] == ""


@pytest.mark.parametrize("body, needle", [
    (
        "pipelines:\n  intake: [intake, content]\npipeline: [intake, content]\n"
        "pipeline_steps: { intake: { owner: scout, task: t } }",
        "declares retired pipeline",
    ),
    ("pipelines: [intake]", "pipelines must be a mapping"),
    ("launch: intake", "declared without any pipelines"),
    (
        "pipelines:\n  intake: [intake]\nlaunch: ghost\n"
        "pipeline_steps: { intake: { owner: scout, task: t } }",
        r"launch pipeline 'ghost' is not one of \['intake'\]",
    ),
    (
        "pipelines:\n  build: [intake, content]\n"
        "pipeline_steps: { intake: { owner: scout, task: t } }",
        "must be keyed by its first phase",
    ),
    (
        "pipelines:\n  intake: [intake, content, content]\n"
        "pipeline_steps: { intake: { owner: scout, task: t } }",
        "duplicate pipeline phase slug 'content'",
    ),
    (
        "pipelines:\n  intake: [intake, content]\n  media: [media, content]\n"
        "pipeline_steps: { intake: { owner: scout, task: t }, media: { owner: muse, task: t } }",
        "chains must be disjoint",
    ),
    (
        "pipelines:\n  intake: [intake, content]\n"
        "pipeline_steps: { intake: { owner: scout }, content: { owner: quill } }",
        "cannot be triggered",
    ),
    (
        "pipelines:\n  intake: [intake, content]\n"
        "pipeline_steps: { content: { owner: quill, task: t } }",
        r"has phases with no owner in pipeline_steps: \['intake'\]",
    ),
    (
        "pipelines:\n  intake: [intake, content]\n"
        "pipeline_steps: { intake: { owner: scout, task: t } }",
        r"has phases with no owner in pipeline_steps: \['content'\]",
    ),
    (
        "task: talk it over\n"
        "pipeline_steps: { ghost: { owner: scout, gate: { argv: [rm, -rf, x] } } }",
        "declares pipeline_steps without any pipeline",
    ),
    (
        "pipelines:\n  intake: [intake, content]\n"
        "pipeline_steps: { intake: { owner: '', task: t } }",
        "missing 'owner'",
    ),
    (
        "pipelines:\n  intake: [intake]\nlaunch: intake\n"
        "pipeline_steps: { intake: { owner: scout, task: t } }\n"
        "task: '@scout #task #content · go'",
        "must open the launch pipeline's first phase",
    ),
    (
        "pipelines:\n  intake: [intake]\n"
        "pipeline_steps: { intake: { owner: scout, task: t } }\n"
        "task: '@scout #task #intake · go'",
        "an idle pipeline workgroup posts no kickoff",
    ),
    (
        "pipelines:\n  intake: [intake, content]\nlaunch: intake\n"
        "pipeline_steps: { intake: { owner: scout, task: t }, ghost: { owner: quill } }",
        r"pipeline_steps key 'ghost' belongs to no declared pipeline \['intake'\]",
    ),
    (
        "pipelines:\n  intake: [intake, content]\nlaunch: intake\n"
        "pipeline_steps: { intake: { owner: scout, task: t, next: content } }",
        r"pipeline_steps\['intake'\]\.next is derived from pipelines\['intake'\]; remove next",
    ),
    ("pipeline_steps: notamap", "pipeline_steps must be a mapping"),
])
def test_parse_rejects_bad_pipeline_declarations(body, needle) -> None:
    with pytest.raises(recipes.RecipeError, match=needle):
        recipes.parse_recipe("hub: mira\nname: n\n" + body, "r")


def test_single_chain_recipe_declares_one_chain() -> None:
    r = recipes.parse_recipe(VALID, "hotel")
    assert list(r.pipelines) == ["intake"]


def test_dormant_chain_must_be_disjoint_from_the_launch_chain() -> None:
    bad = MULTI.replace(
        "  media-update: [media-update, media-build, media-qa]",
        "  media-update: [media-update, qa]",
    )
    with pytest.raises(recipes.RecipeError, match="phase 'qa' belongs to pipelines 'intake' and 'media-update'"):
        recipes.parse_recipe(bad, "hotel")


def test_dormant_chains_must_be_disjoint_from_each_other() -> None:
    bad = MULTI.replace(
        "  media-update: [media-update, media-build, media-qa]",
        "  media-update: [media-update, media-build]\n  media-qa: [media-qa, media-build]",
    )
    with pytest.raises(recipes.RecipeError, match="chains must be disjoint"):
        recipes.parse_recipe(bad, "hotel")


def test_chain_phase_slug_must_be_valid() -> None:
    bad = MULTI.replace(
        "  media-update: [media-update, media-build, media-qa]",
        '  media-update: [media-update, "Media Build"]',
    )
    with pytest.raises(recipes.RecipeError, match="invalid pipeline phase slug"):
        recipes.parse_recipe(bad, "hotel")
