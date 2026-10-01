#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

ALPI = (
    "alpi/*",
    "tests/*",
    "scripts/*",
    "docs/*",
    "README.md",
    "pyproject.toml",
    "uv.lock",
    "docker/*",
    "docker-compose*.yml",
    "desktop/src-tauri/tauri.conf.json",
    "common/*",
    ".github/*",
    ".githooks/*",
    "desktop/CHANGELOG.md",
    "desktop/RELEASING.md",
    "mobile/CHANGELOG.md",
)
KNOWLEDGE = ("alpi/knowledge/*", "docs/*")
CLIENTS = ("desktop/*", "mobile/*", "common/*")
MOBILE_DEPS = ("mobile/package.json", "mobile/package-lock.json")
DESIGN = (
    "design/*",
    "common/*",
    "desktop/src/*",
    "desktop/package.json",
    "mobile/src/*",
    "mobile/app/*",
    "mobile/package.json",
    "tests/test_design_kit.py",
)


@dataclass(frozen=True)
class Step:
    suite: str
    cmd: tuple[str, ...]
    cwd: str = "."

    def render(self) -> str:
        prefix = "" if self.cwd == "." else f"(cd {self.cwd}) "
        return prefix + shlex.join(self.cmd)


def _hits(paths: list[str], patterns: tuple[str, ...], exclude_tests: bool = False) -> bool:
    for p in paths:
        if exclude_tests and ".test." in Path(p).name:
            continue
        if any(fnmatch(p, pat) for pat in patterns):
            return True
    return False


def plan(paths: list[str], run_all: bool = False) -> list[Step]:
    def on(patterns: tuple[str, ...], exclude_tests: bool = False) -> bool:
        return run_all or _hits(paths, patterns, exclude_tests)

    steps = [Step("release", ("python3", "scripts/check_release.py"))]
    if on(ALPI):
        steps.append(Step("alpi", ("uv", "run", "pytest", "-q", "--integration")))
    if on(KNOWLEDGE):
        steps.append(Step("knowledge", ("uv", "run", "python", "scripts/sync_knowledge.py")))
    if on(CLIENTS):
        steps.append(Step("desktop", ("pnpm", "test"), "desktop"))
        steps.append(Step("desktop-build", ("npx", "vite", "build"), "desktop"))
        steps.append(Step("tauri", ("cargo", "test", "-q"), "desktop/src-tauri"))
        steps.append(Step("mobile", ("npm", "test"), "mobile"))
    if on(MOBILE_DEPS):
        steps.append(Step("mobile-lock", ("npm", "ci", "--dry-run"), "mobile"))
    if on(DESIGN, exclude_tests=True):
        steps.append(Step("design", ("python3", "design/drift.py")))
        steps.append(Step("design-kit", ("uv", "run", "pytest", "-q", "tests/test_design_kit.py")))
    return steps


def _git_lines(*args: str) -> list[str]:
    out = subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True)
    if out.returncode:
        raise SystemExit(f"validate: git {' '.join(args)} failed: {out.stderr.strip()}")
    return [line for line in out.stdout.splitlines() if line]


def changed_paths(base: str) -> list[str]:
    tracked = _git_lines("diff", "--name-only", base)
    untracked = _git_lines("ls-files", "--others", "--exclude-standard")
    return sorted(set(tracked) | set(untracked))


def _summary(results: list[tuple[Step, str, float]], pending: list[Step]) -> None:
    rows = [(s.suite, status, f"{secs:.1f}s", s.render()) for s, status, secs in results]
    rows += [(s.suite, "not run", "-", s.render()) for s in pending]
    widths = [
        max(len(r[i]) for r in rows + [("suite", "status", "time", "command")]) for i in range(3)
    ]
    print("\nsummary")
    for r in [("suite", "status", "time", "command"), *rows]:
        print(f"  {r[0]:<{widths[0]}}  {r[1]:<{widths[1]}}  {r[2]:>{widths[2]}}  {r[3]}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the suites touched by the current change.")
    parser.add_argument("--all", action="store_true", help="run every suite regardless of changes")
    parser.add_argument(
        "--base", default="HEAD", help="compare the working tree against this ref (default HEAD)"
    )
    parser.add_argument("--paths", help="comma-separated paths to use instead of git (testing)")
    parser.add_argument("--dry-run", action="store_true", help="print the plan without running it")
    args = parser.parse_args(argv)

    if args.paths is not None:
        paths = [p.strip() for p in args.paths.split(",") if p.strip()]
    elif args.all:
        paths = []
    else:
        paths = changed_paths(args.base)
    steps = plan(paths, run_all=args.all)
    if args.all:
        scope = "all suites"
    elif args.paths is not None:
        scope = f"{len(paths)} given path(s)"
    else:
        scope = f"{len(paths)} changed path(s) vs {args.base}"
    print(f"validate: {scope} -> {', '.join(s.suite for s in steps)}")

    if args.dry_run:
        for s in steps:
            print(f"  [{s.suite}] {s.render()}")
        return 0

    results: list[tuple[Step, str, float]] = []
    for i, step in enumerate(steps):
        print(f"\n==> [{step.suite}] {step.render()}", flush=True)
        start = time.monotonic()
        try:
            rc = subprocess.run(step.cmd, cwd=REPO_ROOT / step.cwd).returncode
        except FileNotFoundError:
            rc = 127
        elapsed = time.monotonic() - start
        if rc:
            results.append((step, f"FAIL ({rc})", elapsed))
            _summary(results, steps[i + 1 :])
            return rc
        results.append((step, "ok", elapsed))
    _summary(results, [])
    return 0


if __name__ == "__main__":
    sys.exit(main())
