import pytest

from alpi.alp import workgroup as wg_mod
from alpi.alp.keys import load_or_generate


PIPELINE = ("intake", "content", "qa")
LAUNCH = "intake"
PIPELINES = {LAUNCH: PIPELINE}
STEPS = {
    "intake": {
        "owner": "scout",
        "task": "pick theme + write site.json",
        "gate": {"argv": ["python3", "check.py"], "cwd": "projects/x"},
    },
    "content": {"owner": "quill", "task": "write copy"},
    "qa": {"owner": "lens"},
}


def test_validate_pipeline_steps_happy_path_normalizes():
    out = wg_mod.validate_pipeline_steps(PIPELINES, STEPS)
    assert set(out) == {"intake", "content", "qa"}
    assert out["intake"]["owner"] == "scout"
    assert "next" not in out["intake"]
    assert out["intake"]["gate"] == {"argv": ["python3", "check.py"], "cwd": "projects/x"}
    assert "gate" not in out["qa"]


def test_validate_pipeline_steps_empty_is_empty():
    assert wg_mod.validate_pipeline_steps(PIPELINES, None) == {}
    assert wg_mod.validate_pipeline_steps(PIPELINES, {}) == {}


@pytest.mark.parametrize("steps, needle", [
    ("not-a-dict", "must be a mapping"),
    ({"nope": {"owner": "scout"}}, "belongs to no declared pipeline"),
    ({"intake": {"next": "content"}}, "missing 'owner'"),
    ({"intake": {"owner": "scout", "next": "ghost"}}, "remove next"),
    ({"intake": {"owner": "scout", "next": "content"}}, "remove next"),
    ({"intake": {"owner": "scout", "gate": {"argv": []}}}, "non-empty list"),
    ({"intake": {"owner": "scout", "gate": {"argv": ["ok"], "cwd": 5}}}, "cwd must be a string"),
    ({"intake": {"owner": "scout", "gate": "notdict"}}, "gate must be a mapping"),
    ({"intake": {"owner": "scout", "gate": {"argv": ["a", 2]}}}, "non-empty list"),
])
def test_validate_pipeline_steps_rejects(steps, needle):
    with pytest.raises(ValueError, match=needle):
        wg_mod.validate_pipeline_steps(PIPELINES, steps)


def test_validate_pipeline_steps_unknown_key_names_the_declared_pipelines():
    with pytest.raises(ValueError, match=r"key 'ghost' belongs to no declared pipeline \['intake'\]"):
        wg_mod.validate_pipeline_steps(PIPELINES, {"ghost": {"owner": "scout"}})


def test_validate_pipeline_steps_next_error_points_at_the_owning_chain():
    with pytest.raises(ValueError, match=r"\.next is derived from pipelines\['intake'\]; remove next"):
        wg_mod.validate_pipeline_steps(PIPELINES, {"content": {"owner": "quill", "next": "qa"}})


def test_validate_pipeline_steps_no_pipeline_skips_membership():
    out = wg_mod.validate_pipeline_steps(None, {"any": {"owner": "bob"}})
    assert out["any"]["owner"] == "bob"


def test_validate_pipeline_steps_no_pipeline_still_rejects_next():
    with pytest.raises(ValueError, match="derived from the pipeline order; remove next"):
        wg_mod.validate_pipeline_steps(None, {"any": {"owner": "bob", "next": "wherever"}})


def test_create_persists_canonical_pipelines_and_quorum(tmp_path):
    home = tmp_path / "hub"
    home.mkdir()
    kp = load_or_generate(home)
    wg = wg_mod.create(
        home, name="proj-x", hub_kp=kp, member_pubkeys=[],
        pipelines={LAUNCH: list(PIPELINE)}, launch_pipeline=LAUNCH,
        pipeline_steps=STEPS, quorum_timeout_seconds=180,
    )
    reloaded = wg_mod.load(home, wg.meta.id)
    assert reloaded.meta.pipelines == PIPELINES
    assert reloaded.meta.launch_pipeline == LAUNCH
    assert reloaded.meta.launch_chain == PIPELINE
    assert reloaded.meta.quorum_timeout_seconds == 180
    assert "next" not in reloaded.meta.pipeline_steps["intake"]
    assert wg_mod.pipeline_successor(reloaded.meta, "intake") == "content"
    assert reloaded.meta.pipeline_steps["intake"]["gate"]["argv"] == ["python3", "check.py"]


def test_create_persists_dormant_chains_beside_the_launch_chain(tmp_path):
    home = tmp_path / "hub"
    home.mkdir()
    kp = load_or_generate(home)
    wg = wg_mod.create(
        home, name="proj-dormant", hub_kp=kp, member_pubkeys=[],
        pipelines={LAUNCH: list(PIPELINE), "patch": ["patch", "patch-qa"]},
        launch_pipeline=LAUNCH,
        pipeline_steps={
            **STEPS,
            "patch": {"owner": "pixel", "task": "patch it"},
            "patch-qa": {"owner": "lens"},
        },
    )
    reloaded = wg_mod.load(home, wg.meta.id)
    assert reloaded.meta.pipelines == {
        LAUNCH: PIPELINE, "patch": ("patch", "patch-qa"),
    }
    assert reloaded.meta.launch_pipeline == LAUNCH
    assert reloaded.meta.launch_chain == PIPELINE
    assert wg_mod.dormant_pipelines(reloaded.meta) == {"patch": ("patch", "patch-qa")}


@pytest.mark.parametrize("retired", [
    {"pipeline": list(PIPELINE)},
    {"operations": {"patch": ["patch", "patch-qa"]}},
])
def test_create_rejects_the_retired_kwargs(tmp_path, retired):
    home = tmp_path / "hub"
    home.mkdir()
    kp = load_or_generate(home)
    with pytest.raises(TypeError, match="unexpected keyword argument"):
        wg_mod.create(
            home, name="proj-retired", hub_kp=kp, member_pubkeys=[],
            pipelines={LAUNCH: list(PIPELINE)}, launch_pipeline=LAUNCH,
            **retired,
        )


def test_create_rejects_malformed_steps(tmp_path):
    home = tmp_path / "hub"
    home.mkdir()
    kp = load_or_generate(home)
    with pytest.raises(ValueError, match="belongs to no declared pipeline"):
        wg_mod.create(
            home, name="proj-y", hub_kp=kp, member_pubkeys=[],
            pipelines={"intake": ["intake"]}, launch_pipeline="intake",
            pipeline_steps={"ghost": {"owner": "x"}},
        )


@pytest.mark.parametrize("evil_id", [
    "../../../other/alp/workgroups/wg_abc",
    "wg/../../escape",
    "wg_ok/../..",
    "..",
    "with space",
    "wg.dot",
])
def test_wg_dir_rejects_path_traversal(tmp_path, evil_id):
    with pytest.raises(ValueError, match="invalid workgroup id"):
        wg_mod._wg_dir(tmp_path, evil_id)


def test_wg_dir_accepts_legit_ids(tmp_path):
    for ok in ("wg_abc123", "wg-test", "wg_x", "wg_nonexistent"):
        assert wg_mod._wg_dir(tmp_path, ok).name == ok


def test_create_defaults_unchanged_when_omitted(tmp_path):
    home = tmp_path / "hub"
    home.mkdir()
    kp = load_or_generate(home)
    wg = wg_mod.create(home, name="plain", hub_kp=kp, member_pubkeys=[])
    reloaded = wg_mod.load(home, wg.meta.id)
    assert reloaded.meta.pipelines == {}
    assert reloaded.meta.launch_pipeline is None
    assert reloaded.meta.launch_chain == ()
    assert reloaded.meta.pipeline_steps == {}
    assert reloaded.meta.quorum_timeout_seconds == 0


def test_gate_step_successor_comes_from_the_chain():
    import types

    from alpi.alp import pipeline_gates as gates

    meta = types.SimpleNamespace(
        pipelines=dict(PIPELINES), launch_pipeline=LAUNCH, pipeline_steps=STEPS,
    )
    step = gates.step_for(meta, "intake")
    assert step is not None, "a valid launch gate must not be silently disabled"
    assert step.next_phase == "content"
    assert step.next_owner == "quill"
    assert step.next_task == "write copy"


def test_gate_step_terminal_phase_has_no_successor():
    import types

    from alpi.alp import pipeline_gates as gates

    steps = {**STEPS, "qa": {"owner": "lens", "gate": {"argv": ["true"]}}}
    meta = types.SimpleNamespace(
        pipelines=dict(PIPELINES), launch_pipeline=LAUNCH, pipeline_steps=steps,
    )
    step = gates.step_for(meta, "qa")
    assert step is not None
    assert step.next_phase == ""
    assert step.next_owner == ""


def test_author_supplied_next_never_reaches_the_gate():
    steps = {**STEPS, "intake": {**STEPS["intake"], "next": "qa"}}
    with pytest.raises(ValueError, match="remove next"):
        wg_mod.validate_pipeline_steps(PIPELINES, steps)


def test_pipeline_steps_accept_a_bounded_turn_budget():
    steps = wg_mod.validate_pipeline_steps(
        {"intake": ("intake", "qa")},
        {"intake": {"owner": "scout", "turn_budget_s": 1800}, "qa": {"owner": "lens"}},
    )
    assert steps["intake"]["turn_budget_s"] == 1800
    assert "turn_budget_s" not in steps["qa"]


@pytest.mark.parametrize("bad", ["soon", 30, 7200, -1])
def test_pipeline_steps_reject_an_out_of_range_turn_budget(bad):
    with pytest.raises(ValueError, match="turn_budget_s"):
        wg_mod.validate_pipeline_steps(
            {"intake": ("intake",)},
            {"intake": {"owner": "scout", "turn_budget_s": bad}},
        )


def test_safe_phase_map_carries_the_turn_budget():
    import types

    meta = types.SimpleNamespace(pipeline_steps={
        "intake": {"owner": "scout", "task": "go", "turn_budget_s": 1800,
                   "gate": {"argv": ["npm", "run", "x"], "cwd": "app"}},
    })
    out = wg_mod.safe_phase_map(meta)
    assert out["intake"] == {"owner": "scout", "task": "go", "turn_budget_s": 1800}
