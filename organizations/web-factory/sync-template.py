from __future__ import annotations

import argparse
import filecmp
import shutil
import sys
from pathlib import Path

WORKSPACE = Path.home() / "git" / "web-factory"
TEMPLATE = WORKSPACE / "templates" / "hotel-web"
PROJECTS = WORKSPACE / "projects"

# Fixed design layer only — per-project data (site.json, src/content/**, assets/, public/img/, intake.md, status.yaml, changes/, decisions/) must never be synced.
FIXED_DIRS = [
    "src/components",
    "src/styles",
    "src/layouts",
    "src/lib",
    "src/i18n",
    "src/pages",
    "scripts",
]
FIXED_FILES = [
    "src/config/site-schema.ts",
    "src/config/site.ts",
    "src/content/config.ts",
    "src/env.d.ts",
    "astro.config.mjs",
    "tsconfig.json",
    "package.json",
    "package-lock.json",
]

GREEN, YELLOW, RED, RESET = "\033[32m", "\033[33m", "\033[31m", "\033[0m"


def ok(msg: str) -> None:
    print(f"  {GREEN}✓{RESET} {msg}")


def warn(msg: str) -> None:
    print(f"  {YELLOW}⚠{RESET} {msg}")


def fail(msg: str) -> None:
    print(f"  {RED}✗{RESET} {msg}")
    sys.exit(1)


def _dir_diff(src: Path, dst: Path) -> list[str]:
    if not dst.exists():
        return ["(dir missing)"]
    diffs: list[str] = []
    cmp = filecmp.dircmp(src, dst)

    def _walk(c: filecmp.dircmp, prefix: str) -> None:
        for name in c.diff_files + c.left_only:
            diffs.append(f"{prefix}{name}")
        for name in c.right_only:
            diffs.append(f"{prefix}{name} (stale, will be removed)")
        for name, sub in c.subdirs.items():
            _walk(sub, f"{prefix}{name}/")

    _walk(cmp, "")
    return diffs


def sync_project(slug: str, dry_run: bool) -> bool:
    project = PROJECTS / slug
    if not project.is_dir():
        fail(f"no project at projects/{slug}")

    changed = False
    for rel in FIXED_DIRS:
        src, dst = TEMPLATE / rel, project / rel
        if not src.exists():
            warn(f"template layer missing: templates/hotel-web/{rel} — skipped")
            continue
        diffs = _dir_diff(src, dst)
        if not diffs:
            continue
        changed = True
        if dry_run:
            for d in diffs[:20]:
                print(f"    {rel}/{d}")
            if len(diffs) > 20:
                print(f"    … {len(diffs) - 20} more")
            continue
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        ok(f"{slug}: synced {rel}/ ({len(diffs)} difference(s))")

    for rel in FIXED_FILES:
        src, dst = TEMPLATE / rel, project / rel
        if not src.exists():
            warn(f"template file missing: templates/hotel-web/{rel} — skipped")
            continue
        if dst.exists() and filecmp.cmp(src, dst, shallow=False):
            continue
        changed = True
        if dry_run:
            print(f"    {rel}{'' if dst.exists() else ' (missing)'}")
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        ok(f"{slug}: synced {rel}")

    if not changed:
        ok(f"{slug}: fixed layer already up to date")
    elif dry_run:
        warn(f"{slug}: differences above — run without --dry-run to apply")
    else:
        warn(f"{slug}: fixed layer updated — rebuild required (@pixel: npm install && npm run ship), then lens spot-checks")
    return changed


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Re-copy the template's fixed design layer into project clone(s). Data (site.json, content, assets) is never touched.",
    )
    ap.add_argument("slug", nargs="?", help="project to sync; omit with --all")
    ap.add_argument("--all", action="store_true", help="sync every project under projects/")
    ap.add_argument("--dry-run", action="store_true", help="list differences without writing")
    args = ap.parse_args()

    if bool(args.slug) == args.all:
        fail("pass exactly one of <slug> or --all")
    if not TEMPLATE.exists():
        fail(f"template not found at {TEMPLATE} — bootstrap the org first")

    slugs = (
        sorted(p.name for p in PROJECTS.iterdir() if p.is_dir())
        if args.all
        else [args.slug]
    )
    any_changed = False
    for slug in slugs:
        any_changed = sync_project(slug, args.dry_run) or any_changed
    return 0 if not (args.dry_run and any_changed) else 1


if __name__ == "__main__":
    sys.exit(main())
