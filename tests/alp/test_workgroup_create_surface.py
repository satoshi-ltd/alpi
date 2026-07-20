import pytest

from alpi.alp import workgroup as wg_mod
from alpi.alp.keys import load_or_generate


PIPELINE = ("intake", "assets", "content", "qa")
STEPS = {
    "intake": {
        "owner": "scout", "next": "content",
        "task": "pick theme + write site.json",
        "gate": {"argv": ["python3", "check.py"], "cwd": "projects/x"},
    },
    "content": {"owner": "quill", "next": "qa", "task": "write copy"},
    "qa": {"owner": "lens"},
}


def test_validate_pipeline_steps_happy_path_normalizes():
    out = wg_mod.validate_pipeline_steps(PIPELINE, STEPS)
    assert set(out) == {"intake", "content", "qa"}
    assert out["intake"]["owner"] == "scout"
    assert out["intake"]["next"] == "content"
    assert out["intake"]["gate"] == {"argv": ["python3", "check.py"], "cwd": "projects/x"}
    assert "gate" not in out["qa"]


def test_validate_pipeline_steps_empty_is_empty():
    assert wg_mod.validate_pipeline_steps(PIPELINE, None) == {}
    assert wg_mod.validate_pipeline_steps(PIPELINE, {}) == {}


@pytest.mark.parametrize("steps, needle", [
    ("not-a-dict", "must be a mapping"),
    ({"nope": {"owner": "scout"}}, "not in the pipeline"),
    ({"intake": {"next": "content"}}, "missing 'owner'"),
    ({"intake": {"owner": "scout", "next": "ghost"}}, "next"),
    ({"intake": {"owner": "scout", "gate": {"argv": []}}}, "non-empty list"),
    ({"intake": {"owner": "scout", "gate": {"argv": ["ok"], "cwd": 5}}}, "cwd must be a string"),
    ({"intake": {"owner": "scout", "gate": "notdict"}}, "gate must be a mapping"),
    ({"intake": {"owner": "scout", "gate": {"argv": ["a", 2]}}}, "non-empty list"),
])
def test_validate_pipeline_steps_rejects(steps, needle):
    with pytest.raises(ValueError, match=needle):
        wg_mod.validate_pipeline_steps(PIPELINE, steps)


def test_validate_pipeline_steps_no_pipeline_skips_membership():
    out = wg_mod.validate_pipeline_steps((), {"any": {"owner": "bob", "next": "wherever"}})
    assert out["any"]["owner"] == "bob"
    assert out["any"]["next"] == "wherever"


def test_create_persists_steps_and_quorum(tmp_path):
    home = tmp_path / "hub"
    home.mkdir()
    kp = load_or_generate(home)
    wg = wg_mod.create(
        home, name="proj-x", hub_kp=kp, member_pubkeys=[],
        pipeline=list(PIPELINE), pipeline_steps=STEPS, quorum_timeout_seconds=180,
    )
    reloaded = wg_mod.load(home, wg.meta.id)
    assert reloaded.meta.pipeline == PIPELINE
    assert reloaded.meta.quorum_timeout_seconds == 180
    assert reloaded.meta.pipeline_steps["intake"]["next"] == "content"
    assert reloaded.meta.pipeline_steps["intake"]["gate"]["argv"] == ["python3", "check.py"]


def test_create_rejects_malformed_steps(tmp_path):
    home = tmp_path / "hub"
    home.mkdir()
    kp = load_or_generate(home)
    with pytest.raises(ValueError, match="not in the pipeline"):
        wg_mod.create(
            home, name="proj-y", hub_kp=kp, member_pubkeys=[],
            pipeline=["intake"], pipeline_steps={"ghost": {"owner": "x"}},
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
    assert reloaded.meta.pipeline_steps == {}
    assert reloaded.meta.quorum_timeout_seconds == 0
