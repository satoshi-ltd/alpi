from pathlib import Path
import tomllib

from packaging.specifiers import SpecifierSet
import yaml


ROOT = Path(__file__).resolve().parents[2]


def test_release_smoke_covers_supported_python_versions():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    supported = SpecifierSet(project["requires-python"])
    assert "3.10" not in supported
    workflow = yaml.safe_load((ROOT / ".github/workflows/publish.yml").read_text())
    smoke = workflow["jobs"]["smoke"]
    images = smoke["strategy"]["matrix"]["image"]
    for version in ("3.11", "3.12", "3.13"):
        assert version in supported
        assert f"python:{version}-slim" in images
    system_python = {"ubuntu:24.04": "3.12", "debian:12": "3.11"}
    for image in images:
        version = image.split(":")[1].removesuffix("-slim") if image.startswith("python:") else system_python[image]
        assert version in supported
    assert "check-version" in smoke["needs"]
    assert "build" in smoke["needs"]
