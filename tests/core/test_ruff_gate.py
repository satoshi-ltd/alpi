from pathlib import Path
import tomllib

from packaging.specifiers import SpecifierSet


ROOT = Path(__file__).resolve().parents[2]

CONFIG = tomllib.loads((ROOT / "pyproject.toml").read_text())
RUFF = CONFIG["tool"]["ruff"]


def _upper_bounded(spec: str) -> bool:
    return any(s.operator in ("<", "<=", "==", "~=") for s in SpecifierSet(spec))


def test_rule_selection_is_explicit():
    select = RUFF["lint"]["select"]
    assert select, "an empty select falls back to ruff's default, which moves between releases"
    assert {"E9", "F"} <= set(select)


def test_running_ruff_version_is_bounded():
    assert _upper_bounded(RUFF["required-version"])


def test_dev_extra_cannot_install_a_ruff_the_config_refuses():
    dev = CONFIG["project"]["optional-dependencies"]["dev"]
    ruff = next(d for d in dev if d.startswith("ruff"))
    spec = ruff.removeprefix("ruff")
    assert _upper_bounded(spec)
    required = SpecifierSet(RUFF["required-version"])
    assert all(v in required for v in SpecifierSet(spec).filter(["0.15.0", "0.15.11"]))


def test_no_rule_is_waived_for_production_code():
    for pattern in RUFF["lint"].get("per-file-ignores", {}):
        assert pattern.startswith("tests/"), f"{pattern} would waive a rule outside tests/"
