import json
import subprocess
import sys
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[1] / "web-factory" / "factory" / "check-intake.py"


def _project(tmp_path: Path, signal: str, images: int = 0) -> Path:
    p = tmp_path / "proj"
    (p / "src" / "config").mkdir(parents=True)
    (p / "assets").mkdir()
    (p / "src" / "config" / "site.json").write_text(json.dumps({
        "theme": "boutique", "brand": {"name": "Casa"},
        "locales": ["es", "en"], "defaultLocale": "es",
    }))
    (p / "intake.md").write_text(f"# Intake\n\nvisual_assets: {signal}\n")
    for i in range(images):
        (p / "assets" / f"photo-{i}.jpg").write_bytes(b"x")
    return p


def _run(project: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(_SCRIPT)], cwd=project,
        capture_output=True, text=True, timeout=30,
    )


def test_trivial_path_passes(tmp_path):
    res = _run(_project(tmp_path, "not_required"))
    assert res.returncode == 0
    assert "→ content" in res.stdout


def test_required_signal_fails_to_hub(tmp_path):
    res = _run(_project(tmp_path, "required before content"))
    assert res.returncode == 1
    assert "assets phase needed" in res.stdout


def test_not_required_with_photos_on_disk_fails(tmp_path):
    res = _run(_project(tmp_path, "not_required", images=2))
    assert res.returncode == 1
    assert "2 image(s)" in res.stdout


def test_missing_site_json_fields_fail(tmp_path):
    p = _project(tmp_path, "not_required")
    (p / "src" / "config" / "site.json").write_text(json.dumps({"theme": "boutique"}))
    res = _run(p)
    assert res.returncode == 1
    assert "missing" in res.stdout
