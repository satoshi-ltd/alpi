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


def _install_uv_step() -> dict:
    workflow = yaml.safe_load((ROOT / ".github/workflows/publish.yml").read_text())
    return next(s for s in workflow["jobs"]["smoke"]["steps"] if s.get("name") == "install uv")


def test_the_uv_installer_download_retries_and_never_pipes_into_sh():
    run = _install_uv_step()["run"]

    assert "| sh" not in run
    assert "--retry" in run and "--retry-all-errors" in run
    assert "-o /tmp/uv-install.sh" in run
    assert "sh /tmp/uv-install.sh" in run


def _fake_curl(tmp_path: Path, script: str) -> dict:
    import os

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    curl = bin_dir / "curl"
    curl.write_text("#!/bin/sh\n" + script)
    curl.chmod(0o755)
    return {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", "HOME": str(tmp_path), "GITHUB_PATH": str(tmp_path / "github_path")}


def test_a_reset_download_fails_the_install_step_itself(tmp_path: Path):
    import subprocess

    env = _fake_curl(tmp_path, "echo 'curl: (35) Recv failure: Connection reset by peer' >&2\nexit 35\n")
    result = subprocess.run(["sh", "-e", "-c", _install_uv_step()["run"]], env=env, capture_output=True, text=True)

    assert result.returncode != 0
    assert "Connection reset" in result.stderr
    assert not (tmp_path / "github_path").exists()


def test_a_good_download_runs_the_installer_and_exports_its_bin(tmp_path: Path):
    import subprocess

    env = _fake_curl(tmp_path, (
        'out=""\nwhile [ $# -gt 0 ]; do case "$1" in -o) out="$2"; shift;; esac; shift; done\n'
        'printf \'#!/bin/sh\\nmkdir -p "$HOME/.local/bin" && echo installed > "$HOME/.local/bin/uv"\\n\' > "$out"\n'
    ))
    result = subprocess.run(["sh", "-e", "-c", _install_uv_step()["run"]], env=env, capture_output=True, text=True)

    assert result.returncode == 0, result.stderr
    assert (tmp_path / ".local" / "bin" / "uv").read_text().strip() == "installed"
    assert (tmp_path / "github_path").read_text().strip() == str(tmp_path / ".local" / "bin")
