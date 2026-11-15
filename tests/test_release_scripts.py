from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"
sys.path.insert(0, str(SCRIPTS))

import bump  # noqa: E402
import check_release  # noqa: E402
import validate  # noqa: E402
import versions  # noqa: E402

FILES = {
    "alpi": ["pyproject.toml", "alpi/__init__.py", "uv.lock"],
    "desktop": [
        "desktop/package.json",
        "desktop/src-tauri/tauri.conf.json",
        "desktop/src-tauri/Cargo.toml",
        "desktop/src-tauri/Cargo.lock",
    ],
    "mobile": ["mobile/package.json", "mobile/package-lock.json", "mobile/app.json"],
}
EXPECTED_CHANGED_LINES = {
    "pyproject.toml": 1,
    "alpi/__init__.py": 1,
    "uv.lock": 1,
    "desktop/package.json": 1,
    "desktop/src-tauri/tauri.conf.json": 1,
    "desktop/src-tauri/Cargo.toml": 1,
    "desktop/src-tauri/Cargo.lock": 1,
    "mobile/package.json": 1,
    "mobile/package-lock.json": 2,
    "mobile/app.json": 3,
}


@pytest.fixture
def repo_copy(tmp_path: Path) -> Path:
    for rel in [*sum(FILES.values(), []), *versions.CHANGELOGS.values()]:
        dest = tmp_path / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO / rel, dest)
    return tmp_path


def _current(product: str, root: Path) -> str:
    return {v for _, v in versions.read_versions(product, root)}.pop()


def _changed_lines(before: str, after: str) -> list[tuple[str, str]]:
    old, new = before.split("\n"), after.split("\n")
    assert len(old) == len(new)
    return [(a, b) for a, b in zip(old, new) if a != b]


@pytest.mark.parametrize("product", versions.PRODUCTS)
@pytest.mark.parametrize("part", ["patch", "minor", "major"])
def test_bump_touches_only_version_lines(repo_copy: Path, product: str, part: str) -> None:
    before = {rel: (repo_copy / rel).read_bytes().decode() for rel in FILES[product]}
    old = _current(product, repo_copy)
    new = versions.next_version(old, part)
    assert bump.main([product, part, "--root", str(repo_copy), "--no-lock"]) == 0
    assert {v for _, v in versions.read_versions(product, repo_copy)} == {new}
    for rel in FILES[product]:
        changed = _changed_lines(before[rel], (repo_copy / rel).read_bytes().decode())
        assert len(changed) == EXPECTED_CHANGED_LINES[rel], rel
        version_lines = [(a, b) for a, b in changed if old in a]
        assert version_lines and all(b == a.replace(old, new) for a, b in version_lines), rel
    assert not list(repo_copy.rglob("*.bump-tmp"))


def test_bump_prints_new_version(repo_copy: Path, capsys: pytest.CaptureFixture[str]) -> None:
    old = _current("desktop", repo_copy)
    assert bump.main(["desktop", "--root", str(repo_copy)]) == 0
    assert capsys.readouterr().out.strip() == versions.next_version(old, "patch")


def test_bump_mobile_increments_build_counters(repo_copy: Path) -> None:
    before = json.loads((repo_copy / "mobile/app.json").read_text())["expo"]
    assert bump.main(["mobile", "--root", str(repo_copy)]) == 0
    after = json.loads((repo_copy / "mobile/app.json").read_text())["expo"]
    assert after["ios"]["buildNumber"] == str(int(before["ios"]["buildNumber"]) + 1)
    assert after["android"]["versionCode"] == before["android"]["versionCode"] + 1
    lock = json.loads((repo_copy / "mobile/package-lock.json").read_text())
    assert lock["version"] == lock["packages"][""]["version"] == after["version"]


def test_bump_refuses_when_locations_disagree(repo_copy: Path) -> None:
    conf = repo_copy / "desktop/src-tauri/tauri.conf.json"
    conf.write_text(
        conf.read_text().replace(
            f'"version": "{_current("desktop", repo_copy)}"', '"version": "9.9.9"'
        )
    )
    untouched = (repo_copy / "desktop/package.json").read_bytes()
    assert bump.main(["desktop", "--root", str(repo_copy)]) == 1
    assert (repo_copy / "desktop/package.json").read_bytes() == untouched


def test_check_release_passes_on_real_repo() -> None:
    out = subprocess.run(
        [sys.executable, str(SCRIPTS / "check_release.py")], capture_output=True, text=True
    )
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "ok"


def _replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text()
    assert text.count(old) >= 1
    path.write_text(text.replace(old, new, 1))


@pytest.mark.parametrize(
    "rel, product",
    [
        ("alpi/__init__.py", "alpi"),
        ("uv.lock", "alpi"),
        ("desktop/src-tauri/Cargo.lock", "desktop"),
        ("desktop/src-tauri/Cargo.toml", "desktop"),
        ("mobile/app.json", "mobile"),
    ],
)
def test_check_release_catches_version_mismatch(repo_copy: Path, rel: str, product: str) -> None:
    assert check_release.check(repo_copy) == ([], [])
    version = _current(product, repo_copy)
    _replace_once(repo_copy / rel, f'"{version}"', '"9.9.9"')
    errors, _ = check_release.check(repo_copy)
    assert len(errors) == 1 and errors[0].startswith(f"{product}: versions disagree")


def test_check_release_catches_package_lock_inner_line(repo_copy: Path) -> None:
    lock = repo_copy / "mobile/package-lock.json"
    text = lock.read_text()
    version = _current("mobile", repo_copy)
    head, sep, tail = text.partition('    "": {\n')
    lock.write_text(head + sep + tail.replace(f'"version": "{version}"', '"version": "9.9.9"', 1))
    errors, _ = check_release.check(repo_copy)
    assert len(errors) == 1 and 'packages[""]' in errors[0]


@pytest.mark.parametrize("product", versions.PRODUCTS)
def test_check_release_catches_stale_changelog(repo_copy: Path, product: str) -> None:
    assert bump.main([product, "--root", str(repo_copy), "--no-lock"]) == 0
    errors, _ = check_release.check(repo_copy)
    assert len(errors) == 1 and errors[0].startswith(
        f"{product}: {versions.CHANGELOGS[product]} top heading"
    )


def test_check_release_unreleased_heading_warns(repo_copy: Path) -> None:
    assert bump.main(["desktop", "--root", str(repo_copy)]) == 0
    _replace_once(
        repo_copy / "desktop/CHANGELOG.md", "\n## v", "\n## Unreleased\n\n- pending\n\n## v"
    )
    errors, warnings = check_release.check(repo_copy)
    assert errors == []
    assert len(warnings) == 1 and warnings[0].startswith("desktop:")
    assert check_release.main(["--root", str(repo_copy)]) == 0


def _suites(paths: list[str]) -> list[str]:
    return [s.suite for s in validate.plan(paths)]


@pytest.mark.parametrize(
    "paths, expected",
    [
        ([], ["release"]),
        (["README.md"], ["release", "alpi", "site"]),
        (["alpi/tools/terminal.py"], ["release", "alpi"]),
        (["alpi/host/server.py"], ["release", "alpi"]),
        (["docs/guide.md"], ["release", "alpi", "knowledge", "site"]),
        (["alpi/knowledge/references/x.md"], ["release", "alpi", "knowledge"]),
        (["desktop/src/App.helpers.test.jsx"], ["release", "desktop", "desktop-build", "tauri", "mobile"]),
        (["desktop/src/App.jsx"], ["release", "desktop", "desktop-build", "tauri", "mobile", "design", "design-kit"]),
        (["desktop/src-tauri/src/lib.rs"], ["release", "desktop", "desktop-build", "tauri", "mobile"]),
        (["desktop/package.json"], ["release", "desktop", "desktop-build", "tauri", "mobile", "design", "design-kit"]),
        (["mobile/package.json"], ["release", "desktop", "desktop-build", "tauri", "mobile", "mobile-lock", "design", "design-kit"]),
        (["mobile/src/screens/Chat.jsx"], ["release", "desktop", "desktop-build", "tauri", "mobile", "design", "design-kit"]),
        (["common/tokens.mjs"], ["release", "alpi", "desktop", "desktop-build", "tauri", "mobile", "design", "design-kit", "site"]),
        (["site/templates/landing.html"], ["release", "site"]),
        ([".github/workflows/publish-site.yml"], ["release", "alpi", "site"]),
        (["design/src/gen.py"], ["release", "design", "design-kit"]),
        ([".github/workflows/publish-desktop.yml"], ["release", "alpi"]),
        ([".githooks/pre-commit"], ["release", "alpi"]),
        (["docker/Dockerfile", "docker-compose.yml"], ["release", "alpi"]),
        (["desktop/RELEASING.md"], ["release", "alpi", "desktop", "desktop-build", "tauri", "mobile"]),
    ],
)
def test_validate_plan_picks_suites(paths: list[str], expected: list[str]) -> None:
    assert _suites(paths) == expected


def test_validate_all_runs_every_suite() -> None:
    suites = [s.suite for s in validate.plan([], run_all=True)]
    assert suites == [
        "release",
        "alpi",
        "knowledge",
        "desktop",
        "desktop-build",
        "tauri",
        "mobile",
        "mobile-lock",
        "design",
        "design-kit",
        "site",
    ]


def test_validate_dry_run_prints_commands_without_running() -> None:
    out = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "validate.py"),
            "--dry-run",
            "--paths",
            "desktop/src-tauri/Cargo.toml",
        ],
        capture_output=True,
        text=True,
    )
    assert out.returncode == 0, out.stderr
    assert "(cd desktop/src-tauri) cargo test -q" in out.stdout
    assert "python3 scripts/check_release.py" in out.stdout
    assert "summary" not in out.stdout


def test_alpi_changes_run_the_integration_suite() -> None:
    step = next(s for s in validate.plan(["alpi/tools/terminal.py"]) if s.suite == "alpi")
    assert "--integration" in step.cmd


def test_design_drift_passes_when_the_build_changes_nothing_and_names_what_it_regenerated(tmp_path: Path) -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location("design_drift", REPO / "design" / "drift.py")
    drift = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(drift)
    (tmp_path / "design").mkdir()
    (tmp_path / "design" / "a.html").write_text("same")
    (tmp_path / "design" / "build.py").write_text("")
    assert drift.main(tmp_path) == 0
    (tmp_path / "design" / "build.py").write_text("from pathlib import Path\nPath(__file__).with_name('a.html').write_text('new')\n")
    assert drift.main(tmp_path) == 1


def test_the_real_design_build_is_deterministic(tmp_path: Path) -> None:
    import hashlib

    out = tmp_path / "kit"

    def build_and_hash() -> dict[str, str]:
        subprocess.run([sys.executable, str(REPO / "design" / "build.py"), "--out", str(out)], cwd=REPO, check=True, capture_output=True)
        return {str(p.relative_to(out)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.rglob("*")) if p.is_file()}

    assert build_and_hash() == build_and_hash()


@pytest.mark.parametrize("previous", ["[]", "<<<<<<< HEAD\n{}\n=======\n", '{"createdOnFiles": "x"}'])
def test_the_design_build_survives_a_malformed_previous_index(tmp_path: Path, previous: str) -> None:
    out = tmp_path / "kit"
    (out / "canvas" / "project").mkdir(parents=True)
    (out / "canvas" / "project" / "canvas.json").write_text(previous)
    subprocess.run([sys.executable, str(REPO / "design" / "build.py"), "--out", str(out)], cwd=REPO, check=True, capture_output=True)
    assert json.loads((out / "canvas" / "project" / "canvas.json").read_text())["createdOnFiles"]["at"]


def _run_hook(tmp_path: Path, staged: list[str]) -> list[str]:
    repo = tmp_path / "repo"
    bin_dir = tmp_path / "bin"
    log = tmp_path / "calls.log"
    for folder in (".githooks", "desktop/src-tauri", "mobile"):
        (repo / folder).mkdir(parents=True)
    shutil.copy(REPO / ".githooks" / "pre-commit", repo / ".githooks" / "pre-commit")
    bin_dir.mkdir()
    for tool in ("uv", "pnpm", "npm", "cargo"):
        stub = bin_dir / tool
        stub.write_text(f'#!/bin/sh\necho "{tool} $*" >> "{log}"\n')
        stub.chmod(0o755)
    isolated = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")} | {"HOME": str(tmp_path), "GIT_CEILING_DIRECTORIES": str(tmp_path)}
    git = ["git", "-C", str(repo)]
    subprocess.run([*git, "init", "-q"], check=True, env=isolated)
    assert subprocess.run([*git, "rev-parse", "--show-toplevel"], check=True, env=isolated, capture_output=True, text=True).stdout.strip() == str(repo.resolve())
    for path in staged:
        (repo / path).parent.mkdir(parents=True, exist_ok=True)
        (repo / path).write_text("x\n")
        subprocess.run([*git, "add", path], check=True, env=isolated)
    env = {"PATH": f"{bin_dir}:/usr/bin:/bin", "HOME": str(tmp_path), "GIT_CEILING_DIRECTORIES": str(tmp_path)}
    subprocess.run(["bash", str(repo / ".githooks" / "pre-commit")], cwd=repo, env=env, check=True, capture_output=True)
    return log.read_text().splitlines() if log.exists() else []


@pytest.mark.parametrize("source", ["common/agentMarks.mjs", "common/workgroupMark.mjs", "common/markEyes.mjs", "common/shapes.mjs"])
def test_pre_commit_runs_the_console_mark_tests_when_only_shared_marks_change(tmp_path: Path, source: str) -> None:
    calls = _run_hook(tmp_path, [source])
    assert "uv run pytest -q tests/core/test_fold_art.py tests/core/test_appearance.py tests/test_icons.py" in calls
    assert any(c.startswith("pnpm") for c in calls) and any(c.startswith("npm") for c in calls)


def test_pre_commit_skips_the_console_mark_tests_for_other_common_files_and_when_the_alpi_suite_runs(tmp_path: Path) -> None:
    assert not any(c.startswith("uv") for c in _run_hook(tmp_path / "a", ["common/tokens.mjs"]))
    calls = _run_hook(tmp_path / "b", ["common/agentMarks.mjs", "alpi/fold_art.py"])
    assert [c for c in calls if c.startswith("uv")] == ["uv run pytest -q --ignore=tests/llm --ignore=tests/integration"]
