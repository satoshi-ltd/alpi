import importlib.util
from pathlib import Path

import pytest

_SETUP_PATH = Path(__file__).resolve().parents[2] / "organizations" / "setup.py"
_spec = importlib.util.spec_from_file_location("org_setup", _SETUP_PATH)
setup = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(setup)


@pytest.fixture(autouse=True)
def org_models(monkeypatch, tmp_path_factory):
    monkeypatch.setattr(setup, "MODEL_DEFAULT", "prov/default-model")
    monkeypatch.setattr(setup, "MODEL_STRONG", "prov/strong-model")
    monkeypatch.setattr(setup, "BUDGET_DAILY_DEFAULT", 2.0)
    monkeypatch.setattr(setup, "BUDGET_DAILY_STRONG", 5.0)
    monkeypatch.setattr(setup, "COMMON_SKILLS_DIR", tmp_path_factory.mktemp("empty-common"))


def write_agent(tmp_path: Path, frontmatter: str) -> Path:
    agent_dir = tmp_path / "alpha"
    agent_dir.mkdir()
    path = agent_dir / "agent.md"
    path.write_text(f"---\n{frontmatter}\n---\n\n# Alpha\nSoul body.\n")
    return path


@pytest.mark.parametrize(
    ("tier", "expected_model"),
    [
        ("default", "prov/default-model"),
        ("strong", "prov/strong-model"),
    ],
)
def test_tier_resolves_model(tmp_path, tier, expected_model):
    agent = setup._parse_agent_file(write_agent(tmp_path, f"tier: {tier}\nreasoning_effort: medium"))
    assert agent["model"] == expected_model


def test_frontmatter_model_overrides_tier(tmp_path):
    agent = setup._parse_agent_file(
        write_agent(tmp_path, "tier: strong\nmodel: prov/explicit\nreasoning_effort: medium")
    )
    assert agent["model"] == "prov/explicit"


@pytest.mark.parametrize(
    ("frontmatter", "expected_usd"),
    [
        ("tier: default\nreasoning_effort: low", 2.0),
        ("tier: strong\nreasoning_effort: low", 5.0),
        ("tier: strong\ndaily_usd: 9.5\nreasoning_effort: low", 9.5),
    ],
)
def test_daily_usd_defaults_follow_tier(tmp_path, frontmatter, expected_usd):
    agent = setup._parse_agent_file(write_agent(tmp_path, frontmatter))
    assert agent["daily_usd"] == expected_usd


def _validation_agent(tier: str) -> dict:
    return {
        "name": "alpha",
        "tier": tier,
        "model": "prov/default-model",
        "reasoning_effort": "medium",
        "tools_deny": [],
    }


def test_validate_org_flags_unknown_tier(monkeypatch):
    monkeypatch.setattr(setup, "AGENTS_DIR", setup.REPO_ROOT / "organizations" / "testorg" / "agents")
    errors, _ = setup.validate_org([_validation_agent("visoin")])
    assert any("unknown tier 'visoin'" in e for e in errors)


def test_validate_org_accepts_known_tiers(monkeypatch):
    monkeypatch.setattr(setup, "AGENTS_DIR", setup.REPO_ROOT / "organizations" / "testorg" / "agents")
    for tier in ("default", "strong"):
        errors, _ = setup.validate_org([_validation_agent(tier)])
        assert not errors


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
    errors, _ = setup.validate_org([_validation_agent("default")])
    assert any("outside alpi's closed enum" in e and "factory" in e for e in errors)


def test_validate_org_accepts_skill_category_in_alpi_enum(monkeypatch, tmp_path):
    monkeypatch.setattr(setup, "AGENTS_DIR", tmp_path)
    monkeypatch.setattr(setup, "REPO_ROOT", tmp_path)
    _write_skill(tmp_path, "meta")
    errors, _ = setup.validate_org([_validation_agent("default")])
    assert not any("outside alpi's closed enum" in e for e in errors)
