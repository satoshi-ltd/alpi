from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "publish-docker.yml"

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="runs the workflow's bash steps")


@pytest.fixture(scope="module")
def jobs() -> dict:
    return yaml.safe_load(WORKFLOW.read_text())["jobs"]


def _step(job: dict, name: str) -> dict:
    matches = [s for s in job["steps"] if s.get("name") == name or s.get("id") == name]
    assert len(matches) == 1, name
    return matches[0]


def _evaluate(expression: str, context: dict) -> str:
    """GitHub's ``a || b`` over dotted context paths: a missing path is falsy."""
    inner = re.fullmatch(r"\$\{\{\s*(.*?)\s*\}\}", expression).group(1)
    for path in (part.strip() for part in inner.split("||")):
        value: object = context
        for key in path.split("."):
            value = value.get(key) if isinstance(value, dict) else None
        if value:
            return str(value)
    return ""


def _source_expression(jobs: dict) -> str:
    return _step(jobs["check-version"], "source")["env"]["SHA"]


def test_an_automatic_run_publishes_the_parent_revision_not_the_newest_main(jobs):
    event = {"github": {"sha": "b" * 40, "event": {"workflow_run": {"head_sha": "a" * 40}}}}

    assert _evaluate(_source_expression(jobs), event) == "a" * 40


def test_a_manual_run_publishes_the_dispatched_revision(jobs):
    event = {"github": {"sha": "c" * 40, "event": {"inputs": {"force": "false"}}}}

    assert _evaluate(_source_expression(jobs), event) == "c" * 40


def test_every_job_checks_out_the_resolved_revision(jobs):
    refs = {
        name: [s["with"].get("ref") for s in job["steps"] if str(s.get("uses", "")).startswith("actions/checkout@")]
        for name, job in jobs.items()
    }

    assert refs["check-version"] == ["${{ steps.source.outputs.sha }}"]
    assert refs["docker"] == ["${{ needs.check-version.outputs.sha }}"]
    assert refs["latest"] == ["${{ needs.check-version.outputs.sha }}"]
    assert jobs["check-version"]["outputs"]["sha"] == "${{ steps.source.outputs.sha }}"


def _bash(script: str, cwd: Path, env: dict) -> subprocess.CompletedProcess:
    # A `run` step without `shell:` is `bash -e {0}` on GitHub: no pipefail, so the steps must not rely on it.
    return subprocess.run(
        ["bash", "--noprofile", "--norc", "-e", "-c", script],
        cwd=cwd, env={**os.environ, **env}, capture_output=True, text=True, timeout=60,
    )


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=cwd, check=True, capture_output=True, text=True,
    ).stdout.strip()


@pytest.fixture
def checkout(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    (repo / "pyproject.toml").write_text('[project]\nname = "alpi-agent"\nversion = "0.15.12"\n')
    _git(repo, "add", "pyproject.toml")
    _git(repo, "commit", "-q", "-m", "release")
    return repo, _git(repo, "rev-parse", "HEAD")


@pytest.mark.parametrize(("sha", "version", "ok"), [
    (None, "0.15.12", True),
    ("f" * 40, "0.15.12", False),
    (None, "0.15.13", False),
])
def test_a_revision_or_version_mismatch_fails_before_anything_is_built(jobs, checkout, sha, version, ok):
    repo, head = checkout
    script = _step(jobs["docker"], "source is the released revision")["run"]

    result = _bash(script, repo, {"SHA": sha or head, "VERSION": version})

    assert (result.returncode == 0) is ok, result.stdout + result.stderr


def test_the_image_version_is_checked_before_the_image_is_pushed(jobs):
    steps = jobs["docker"]["steps"]
    check = next(i for i, s in enumerate(steps) if s.get("name") == "smoke — the image carries the version being published")
    push = next(i for i, s in enumerate(steps) if s.get("with", {}).get("push") is True)

    assert check < push
    assert 'm.version("alpi-agent")' in steps[check]["run"]
    assert 'test "$found" = "$VERSION"' in steps[check]["run"]


def test_a_release_pushes_only_its_version_and_latest_moves_elsewhere(jobs):
    push = next(s for s in jobs["docker"]["steps"] if s.get("with", {}).get("push") is True)

    assert ":latest" not in push["with"]["tags"]
    assert "${{ env.VERSION }}" in push["with"]["tags"]
    assert ":latest" not in yaml.safe_dump(jobs["docker"])
    assert ":latest" in _step(jobs["latest"], "move latest")["run"]


def test_moving_latest_is_serialized_and_follows_the_release(jobs):
    latest = jobs["latest"]

    assert latest["needs"] == ["check-version", "docker"]
    assert latest["concurrency"] == {"group": "publish-docker-latest", "cancel-in-progress": False}
    assert "$NEWEST" in _step(latest, "move latest")["run"]
    assert latest["steps"][-1]["name"] == "move latest"


@pytest.fixture
def origin(tmp_path: Path) -> tuple[Path, Path]:
    bare = tmp_path / "origin.git"
    _git(tmp_path, "init", "-q", "--bare", str(bare))
    clone = tmp_path / "clone"
    _git(tmp_path, "init", "-q", str(clone))
    (clone / "f").write_text("x")
    _git(clone, "add", "f")
    _git(clone, "commit", "-q", "-m", "c")
    _git(clone, "remote", "add", "origin", str(bare))
    return bare, clone


def _pick_newest(jobs: dict, clone: Path, tmp_path: Path) -> tuple[subprocess.CompletedProcess, str]:
    out = tmp_path / "github_output"
    out.write_text("")
    result = _bash(_step(jobs["latest"], "newest")["run"], clone, {"GITHUB_OUTPUT": str(out)})
    return result, out.read_text()


def test_latest_goes_to_the_highest_version_not_the_last_sorted_string(jobs, origin, tmp_path):
    _bare, clone = origin
    for tag in ("docker-v0.15.2", "docker-v0.15.10", "docker-v0.15.9", "v0.16.0", "desktop-v9.0.0"):
        _git(clone, "tag", "-a", tag, "-m", tag)
    _git(clone, "push", "-q", "origin", "--tags")

    result, output = _pick_newest(jobs, clone, tmp_path)

    assert result.returncode == 0, result.stderr
    assert output.strip() == "version=0.15.10"


def test_an_older_run_finishing_last_still_points_latest_at_the_newest(jobs, origin, tmp_path):
    _bare, clone = origin
    _git(clone, "tag", "docker-v0.15.12")
    _git(clone, "push", "-q", "origin", "--tags")
    _git(clone, "tag", "docker-v0.15.11")
    _git(clone, "push", "-q", "origin", "--tags")

    result, output = _pick_newest(jobs, clone, tmp_path)

    assert result.returncode == 0, result.stderr
    assert output.strip() == "version=0.15.12"


def test_no_published_version_fails_instead_of_moving_latest_nowhere(jobs, origin, tmp_path):
    _bare, clone = origin

    result, output = _pick_newest(jobs, clone, tmp_path)

    assert result.returncode != 0
    assert output == ""


@pytest.fixture
def released(tmp_path: Path) -> dict:
    bare = tmp_path / "released.git"
    _git(tmp_path, "init", "-q", "--bare", str(bare))
    repo = tmp_path / "released"
    _git(tmp_path, "init", "-q", str(repo))
    (repo / "pyproject.toml").write_text('[project]\nname = "alpi-agent"\nversion = "0.15.12"\n')
    _git(repo, "add", "pyproject.toml")
    _git(repo, "commit", "-q", "-m", "A: release 0.15.12")
    a = _git(repo, "rev-parse", "HEAD")
    (repo / "later.txt").write_text("B")
    _git(repo, "add", "later.txt")
    _git(repo, "commit", "-q", "-m", "B: same version")
    b = _git(repo, "rev-parse", "HEAD")
    _git(repo, "remote", "add", "origin", str(bare))
    _git(repo, "push", "-q", "origin", "HEAD:refs/heads/main")
    return {"repo": repo, "a": a, "b": b, "tmp": tmp_path}


def _tag(released: dict, name: str, commit: str, *, annotated: bool = True) -> None:
    args = ["tag", "-a", name, "-m", name, commit] if annotated else ["tag", name, commit]
    _git(released["repo"], *args)
    _git(released["repo"], "push", "-q", "origin", f"refs/tags/{name}")


def _gate(jobs: dict, released: dict, *, event: str, sha: str, force: str = "") -> dict:
    _git(released["repo"], "checkout", "-q", sha)
    out = released["tmp"] / "gate_output"
    out.write_text("")
    result = _bash(_step(jobs["check-version"], "gate")["run"], released["repo"],
                   {"EVENT": event, "FORCE": force, "SHA": sha, "GITHUB_OUTPUT": str(out)})
    assert result.returncode == 0, result.stdout + result.stderr
    return dict(line.split("=", 1) for line in out.read_text().splitlines()) | {"log": result.stdout}


def test_an_automatic_run_publishes_the_commit_its_release_tag_names(jobs, released):
    _tag(released, "v0.15.12", released["b"])

    gate = _gate(jobs, released, event="workflow_run", sha=released["b"])

    assert gate["should_publish"] == "true"
    assert gate["version"] == "0.15.12"


def test_a_later_commit_with_the_released_version_is_never_published_under_it(jobs, released):
    _tag(released, "v0.15.12", released["a"])

    gate = _gate(jobs, released, event="workflow_run", sha=released["b"])

    assert gate["should_publish"] == "false"
    assert f"released from {released['a']}, not {released['b']}" in gate["log"]


def test_an_automatic_run_without_a_release_tag_publishes_nothing(jobs, released):
    gate = _gate(jobs, released, event="workflow_run", sha=released["b"])

    assert gate["should_publish"] == "false"
    assert "released from no commit" in gate["log"]


def test_a_lightweight_release_tag_is_resolved_to_its_commit_too(jobs, released):
    _tag(released, "v0.15.12", released["b"], annotated=False)

    assert _gate(jobs, released, event="workflow_run", sha=released["b"])["should_publish"] == "true"


def test_a_released_revision_whose_image_is_already_out_is_skipped(jobs, released):
    _tag(released, "v0.15.12", released["b"])
    _tag(released, "docker-v0.15.12", released["b"])

    assert _gate(jobs, released, event="workflow_run", sha=released["b"])["should_publish"] == "false"


@pytest.mark.parametrize(("docker_tag", "force", "expected"), [
    (False, "", "true"),
    (True, "", "false"),
    (True, "true", "true"),
])
def test_a_manual_run_keeps_its_own_policy(jobs, released, docker_tag, force, expected):
    if docker_tag:
        _tag(released, "docker-v0.15.12", released["a"])

    gate = _gate(jobs, released, event="workflow_dispatch", sha=released["b"], force=force)

    assert gate["should_publish"] == expected


def test_force_never_bypasses_the_release_check_of_an_automatic_run(jobs, released):
    _tag(released, "v0.15.12", released["a"])

    gate = _gate(jobs, released, event="workflow_run", sha=released["b"], force="true")

    assert gate["should_publish"] == "false"
