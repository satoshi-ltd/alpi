import importlib.util
from pathlib import Path

import pytest

_SETUP_PATH = Path(__file__).resolve().parents[2] / "organizations" / "setup.py"
_spec = importlib.util.spec_from_file_location("org_setup", _SETUP_PATH)
setup = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(setup)


@pytest.fixture(autouse=True)
def org_models(monkeypatch, tmp_path_factory):
    monkeypatch.setattr(setup, "TIER_MAIN", {"model": "prov/main-model", "effort": "medium"})
    monkeypatch.setattr(setup, "TIER_FAST", {"model": "prov/fast-model", "effort": "low"})
    monkeypatch.setattr(setup, "TIER_DEEP", {"model": "prov/deep-model", "effort": "high"})
    monkeypatch.setattr(setup, "BUDGET_DAILY_DEFAULT", 2.0)
    monkeypatch.setattr(setup, "COMMON_SKILLS_DIR", tmp_path_factory.mktemp("empty-common"))


def write_agent(tmp_path: Path, frontmatter: str) -> Path:
    agent_dir = tmp_path / "alpha"
    agent_dir.mkdir()
    path = agent_dir / "agent.md"
    path.write_text(f"---\n{frontmatter}\n---\n\n# Alpha\nSoul body.\n")
    return path


def test_org_models_resolve_main_and_tiers(tmp_path):
    agent = setup._parse_agent_file(write_agent(tmp_path, "bio: alpha"))
    assert agent["model"] == "prov/main-model"
    assert agent["reasoning_effort"] == "medium"
    assert agent["tiers"]["fast"] == {"model": "prov/fast-model", "effort": "low"}
    assert agent["tiers"]["deep"] == {"model": "prov/deep-model", "effort": "high"}


def test_reasoning_effort_overrides_org_default(tmp_path):
    agent = setup._parse_agent_file(write_agent(tmp_path, "reasoning_effort: high"))
    assert agent["reasoning_effort"] == "high"


def test_frontmatter_overrides_main_and_tier_models(tmp_path):
    agent = setup._parse_agent_file(
        write_agent(
            tmp_path,
            "model: prov/explicit\nmodel_fast: prov/explicit-fast\nmodel_deep: prov/explicit-deep\nreasoning_effort: medium",
        )
    )
    assert agent["model"] == "prov/explicit"
    assert agent["tiers"]["fast"]["model"] == "prov/explicit-fast"
    assert agent["tiers"]["deep"]["model"] == "prov/explicit-deep"
    assert agent["tiers"]["fast"]["effort"] == "low"
    assert agent["tiers"]["deep"]["effort"] == "high"


@pytest.mark.parametrize(
    ("frontmatter", "expected_usd"),
    [
        ("reasoning_effort: low", 2.0),
        ("daily_usd: 9.5\nreasoning_effort: low", 9.5),
    ],
)
def test_daily_usd_default_and_override(tmp_path, frontmatter, expected_usd):
    agent = setup._parse_agent_file(write_agent(tmp_path, frontmatter))
    assert agent["daily_usd"] == expected_usd


@pytest.mark.parametrize(
    ("tier", "raw", "expected"),
    [
        ("fast", "prov/bare-string", {"model": "prov/bare-string", "effort": ""}),
        ("deep", {"model": "prov/map", "effort": "high"}, {"model": "prov/map", "effort": "high"}),
    ],
)
def test_org_tier_parses_string_and_map(tier, raw, expected):
    assert setup._org_tier("testorg", tier, raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        {"effort": "low"},
        {"model": "prov/x", "effort": "extreme"},
        42,
    ],
)
def test_org_tier_rejects_invalid_shapes(raw):
    with pytest.raises(SystemExit):
        setup._org_tier("testorg", "fast", raw)


def test_org_tier_requires_effort_on_main():
    with pytest.raises(SystemExit):
        setup._org_tier("testorg", "main", {"model": "prov/x"}, require_effort=True)


def _validation_agent(legacy_tier=None) -> dict:
    return {
        "name": "alpha",
        "model": "prov/main-model",
        "tiers": {
            "fast": {"model": "prov/fast-model", "effort": ""},
            "deep": {"model": "prov/deep-model", "effort": ""},
        },
        "legacy_tier": legacy_tier,
        "reasoning_effort": "medium",
        "tools_deny": [],
    }


def test_validate_org_flags_legacy_tier(monkeypatch):
    monkeypatch.setattr(setup, "AGENTS_DIR", setup.REPO_ROOT / "organizations" / "testorg" / "agents")
    errors, _ = setup.validate_org([_validation_agent(legacy_tier="strong")])
    assert any("'tier:' was removed" in e for e in errors)


def test_validate_org_accepts_agent_without_legacy_tier(monkeypatch):
    monkeypatch.setattr(setup, "AGENTS_DIR", setup.REPO_ROOT / "organizations" / "testorg" / "agents")
    errors, _ = setup.validate_org([_validation_agent()])
    assert not errors


def test_workgroup_budget_ceiling_rejected(monkeypatch, tmp_path):
    wg_dir = tmp_path / "big"
    wg_dir.mkdir()
    (wg_dir / "workgroup.md").write_text("---\nhub: alpha\nmembers: [beta]\nbudget_usd: 80.0\n---\n\nToo rich.\n")
    monkeypatch.setattr(setup, "WORKGROUPS_DIR", tmp_path)
    monkeypatch.setattr(setup, "BUDGET_WG", 50.0)
    with pytest.raises(SystemExit):
        setup.load_workgroups()


def test_workgroup_budget_at_ceiling_accepted(monkeypatch, tmp_path):
    wg_dir = tmp_path / "ok"
    wg_dir.mkdir()
    (wg_dir / "workgroup.md").write_text("---\nhub: alpha\nmembers: [beta]\nbudget_usd: 50.0\n---\n\nFine.\n")
    monkeypatch.setattr(setup, "WORKGROUPS_DIR", tmp_path)
    monkeypatch.setattr(setup, "BUDGET_WG", 50.0)
    assert setup.load_workgroups()[0]["budget_usd"] == 50.0


def _write_skill(tmp_path: Path, category: str) -> Path:
    skill_dir = tmp_path / "alpha" / "skills" / category / "noop"
    skill_dir.mkdir(parents=True)
    skill = skill_dir / "SKILL.md"
    skill.write_text(
        f"---\nname: noop\ndescription: noop\ncategory: {category}\nallowed-tools: []\n---\n\nbody\n"
    )
    return skill


def test_validate_org_flags_skill_category_outside_alpi_enum(monkeypatch, tmp_path):
    monkeypatch.setattr(setup, "AGENTS_DIR", tmp_path)
    monkeypatch.setattr(setup, "REPO_ROOT", tmp_path)
    _write_skill(tmp_path, "factory")
    errors, _ = setup.validate_org([_validation_agent()])
    assert any("outside alpi's closed enum" in e and "factory" in e for e in errors)


def test_validate_org_accepts_skill_category_in_alpi_enum(monkeypatch, tmp_path):
    monkeypatch.setattr(setup, "AGENTS_DIR", tmp_path)
    monkeypatch.setattr(setup, "REPO_ROOT", tmp_path)
    _write_skill(tmp_path, "meta")
    errors, _ = setup.validate_org([_validation_agent()])
    assert not any("outside alpi's closed enum" in e for e in errors)


@pytest.mark.parametrize("org_name", setup.discover_orgs())
def test_real_org_validation_check_is_clean(org_name):
    setup.init_org(org_name)
    agents = setup.load_agents()
    workgroups = setup.load_workgroups()
    names = {a["name"] for a in agents}

    errors, warnings = setup.validate_org(agents)
    assert not errors
    assert not warnings

    missing_roles = [
        f"{wg['name']}:{role}"
        for wg in workgroups
        for role in [wg["hub"], *wg["members"]]
        if role not in names
    ]
    assert not missing_roles

    unknown_voices = sorted(set(setup.AGENT_VOICES) - names)
    assert not unknown_voices

    missing_common_skills = [
        path for path in setup.COMMON_SKILLS
        if not (setup.COMMON_SKILLS_DIR / path).exists()
    ]
    assert not missing_common_skills

    unknown_common_skill_targets = [
        f"{path}:{target}"
        for path, targets in setup.COMMON_SKILLS.items()
        for target in targets
        if target not in names
    ]
    assert not unknown_common_skill_targets
