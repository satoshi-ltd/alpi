import importlib.util
import json
from pathlib import Path

_SCRIPT = (
    Path(__file__).resolve().parents[1] / "web-factory" / "tools" / "bootstrap_project.py"
)
_spec = importlib.util.spec_from_file_location("bootstrap_project", _SCRIPT)
bootstrap = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bootstrap)


def _project(tmp_path: Path, site: dict) -> Path:
    config = tmp_path / "src" / "config"
    config.mkdir(parents=True)
    (config / "site.json").write_text(json.dumps(site), encoding="utf-8")
    return tmp_path


def _legal(project: Path):
    return json.loads((project / "src" / "config" / "site.json").read_text())["legal"]


def test_an_empty_company_with_legal_pages_off_is_demo_data(tmp_path):
    """Every fresh clone failed check:setup on this — the gate reads presence, not completeness."""
    project = _project(tmp_path, {
        "legal": {"company": {"name": "", "taxId": "", "email": ""}},
        "pages": {"legal": False},
    })
    assert bootstrap.neutralize_legal(project) is True
    assert _legal(project) is False


def test_a_declared_company_with_legal_pages_on_is_left_alone(tmp_path):
    company = {"company": {"name": "Hotel Maestranza SL", "taxId": "B123"}}
    project = _project(tmp_path, {"legal": company, "pages": {"legal": True}})
    assert bootstrap.neutralize_legal(project) is False
    assert _legal(project) == company


def test_an_already_neutral_config_is_not_rewritten(tmp_path):
    project = _project(tmp_path, {"legal": False, "pages": {"legal": False}})
    before = (project / "src" / "config" / "site.json").read_text()
    assert bootstrap.neutralize_legal(project) is False
    assert (project / "src" / "config" / "site.json").read_text() == before


def test_a_missing_config_is_not_an_error(tmp_path):
    assert bootstrap.neutralize_legal(tmp_path) is False


def test_bootstrap_ends_on_the_setup_phase_gate():
    body = _SCRIPT.read_text()
    assert '"check:setup"' in body, "bootstrap must end on the gate the phase is judged by"
    assert body.index("neutralize_legal(project)") < body.index('"check:setup"')


def test_pixel_hands_off_on_the_bootstrap_exit_code():
    pixel = (
        Path(__file__).resolve().parents[1] / "web-factory" / "agents" / "pixel" / "agent.md"
    )
    body = " ".join(pixel.read_text().split())
    assert "npm run check:setup" in body
    assert "exits 0 IS your handoff condition" in body
    assert "never hand off on a claim that the check passed" in body
