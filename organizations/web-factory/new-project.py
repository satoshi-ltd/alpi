from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import yaml

HUB = "mira"
PROJECT_MEMBERS = ["scout", "quill", "lingua", "muse", "pixel", "lens"]
PIPELINE = "intake,assets,content,translation,build,qa"
ORG_DIR = Path(__file__).resolve().parent
WORKSPACE = Path.home() / "git" / "web-factory"
TEMPLATE = WORKSPACE / "templates" / "hotel-web"
PROJECTS = WORKSPACE / "projects"


def _project_budget_usd() -> float:
    # Single source of truth: org.yaml budgets.project_workgroup.
    try:
        cfg = yaml.safe_load((ORG_DIR / "org.yaml").read_text()) or {}
        return float((cfg.get("budgets") or {}).get("project_workgroup", 50.0))
    except Exception:  # noqa: BLE001
        return 50.0

GREEN, YELLOW, RED, RESET = "\033[32m", "\033[33m", "\033[31m", "\033[0m"


def ok(msg: str) -> None:
    print(f"  {GREEN}✓{RESET} {msg}")


def warn(msg: str) -> None:
    print(f"  {YELLOW}⚠{RESET} {msg}")


def fail(msg: str) -> None:
    print(f"  {RED}✗{RESET} {msg}")
    sys.exit(1)


def run(cmd: list[str], timeout: float = 30.0) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=timeout, stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired as e:
        return subprocess.CompletedProcess(
            cmd, 124, stdout=e.stdout or "", stderr=f"timeout after {timeout}s",
        )


def site_skeleton() -> dict:
    return {
        "theme": "boutique",
        "brand": {"name": ""},
        "locales": ["es"],
        "defaultLocale": "es",
        "contact": {},
        "booking": {"provider": "mirai", "propertyId": "", "fields": ["checkin", "checkout", "guests", "rooms"]},
        "nav": {"primary": ["rooms", "amenities", "dining", "gallery", "location", "about"], "cta": "book", "showLangSwitcher": True},
        "pages": {"landing": True, "rooms": True, "roomDetail": True, "amenities": True, "dining": True, "gallery": True, "location": True, "about": True, "offers": False, "blog": False},
    }


def scaffold(slug: str, brief: Path | None) -> Path:
    project = PROJECTS / slug
    if project.exists():
        fail(f"{project} already exists — `--nuke` first")
    # Clone the template; example content + node_modules/build artefacts excluded.
    shutil.copytree(
        TEMPLATE, project,
        ignore=shutil.ignore_patterns("node_modules", ".astro", "dist"),
    )
    # Strip the template's example content; keep config.ts (fixed schema).
    content = project / "src" / "content"
    if content.exists():
        for entry in content.rglob("*"):
            if entry.is_file() and entry.name not in {"config.ts"}:
                entry.unlink()
        for coll in content.iterdir():
            if coll.is_dir():
                (coll / ".gitkeep").write_text("")
    # Reset site.json to a neutral skeleton.
    (project / "src" / "config" / "site.json").write_text(
        json.dumps(site_skeleton(), indent=2) + "\n"
    )
    # Project artefacts.
    for d in ("changes", "decisions", "assets"):
        (project / d).mkdir(exist_ok=True)
        (project / d / ".gitkeep").write_text("")
    web = project / "public" / "img"
    web.mkdir(parents=True, exist_ok=True)
    (web / ".gitkeep").write_text("")
    (project / "intake.md").write_text(
        f"# Intake — {slug}\n\n(scout fills theme rationale, voice, and the "
        f"facts the content phase needs from brief.md)\n"
    )
    (project / "CHANGELOG.md").write_text(f"# {slug} — changelog\n")
    if brief is not None:
        if not brief.exists():
            fail(f"brief not found: {brief}")
        shutil.copy(brief, project / "brief.md")
        ok(f"brief copied → projects/{slug}/brief.md")
    else:
        warn("no --brief given; projects/<slug>/brief.md is empty")
        (project / "brief.md").write_text(f"# Brief — {slug}\n\n(no brief provided)\n")
    ok(f"scaffolded projects/{slug}/ from the template")
    return project


def write_status(slug: str, project: Path) -> None:
    today = run(["date", "+%Y-%m-%d"]).stdout.strip()
    status = {
        "slug": slug,
        "theme": "",
        "state": "created",
        "created": today,
        "launched_at": None,
        "launch_target": None,
        "archived_at": None,
        "iterations": 0,
        "history": [{"state": "created", "at": today, "by": "new-project.py"}],
    }
    (project / "status.yaml").write_text(yaml.safe_dump(status, sort_keys=False, allow_unicode=True))


def create_workgroup(slug: str) -> str:
    name = f"proj-{slug}"
    cmd = ["alpi", "-p", HUB, "workgroup", "create", name]
    for m in PROJECT_MEMBERS:
        cmd += ["--member", m]
    cmd += ["--budget-usd", str(_project_budget_usd())]
    cmd += ["--pipeline", PIPELINE]
    res = run(cmd)
    if res.returncode != 0:
        fail(f"workgroup create '{name}' failed: {res.stderr.strip()}")
    return name


def find_wg_dir(hub: str, name: str) -> Path | None:
    wg_root = Path.home() / ".alpi" / "profiles" / hub / "alp" / "workgroups"
    if not wg_root.exists():
        return None
    for d in wg_root.iterdir():
        if not d.is_dir():
            continue
        meta = d / "meta.yaml"
        if meta.exists():
            try:
                if (yaml.safe_load(meta.read_text()) or {}).get("name") == name:
                    return d
            except Exception:  # noqa: BLE001
                continue
    return None


def join_members(wg_id: str) -> None:
    for m in PROJECT_MEMBERS:
        # The daemon may still be respawning (alp.sock race) — back off and retry.
        for attempt in range(4):
            res = run(["alpi", "-p", m, "workgroup", "join", HUB, wg_id])
            if res.returncode == 0:
                break
            time.sleep(1.5 * (attempt + 1))
        else:
            warn(f"{m} join failed after retries: {res.stderr.strip()}")


def attach_briefing(slug: str, launch_date: str | None) -> str | None:
    # Resolve by known name, not most-recent dir — a concurrent create could win the mtime race.
    wg_dir = find_wg_dir(HUB, f"proj-{slug}")
    if not wg_dir:
        warn(f"workgroup 'proj-{slug}' not found — briefing not attached")
        return None
    meta_path = wg_dir / "meta.yaml"
    meta = yaml.safe_load(meta_path.read_text()) or {}
    # pipeline is set at `workgroup create --pipeline …`; preserved on re-read.
    # Pipeline phases produce a verifiable artifact, so the hub can close on disk
    # evidence fast — no need for the 10-min full-quorum wait when an owner's
    # handoff post is missed. Bounds recovery latency to ~the watchdog refire.
    meta["quorum_timeout_seconds"] = 180
    # `task` describes its OWN phase (next_task_text reads steps[next].task); intake's gate passes only on the trivial path (not_required + assets/ empty) and any other outcome routes to the hub's judgment; qa is gateless by design.
    meta["pipeline_steps"] = {
        "intake": {
            "owner": "scout",
            "next": "content",
            "task": "pick the theme + write src/config/site.json + intake.md; end the handoff with the visual_assets: signal line",
            "gate": {"cwd": f"projects/{slug}", "argv": ["python3", "../../factory/check-intake.py"]},
        },
        "content": {
            "owner": "quill",
            "next": "translation",
            "task": "write the source-locale content under src/content/** per the binding catalogue (factory/template-spec.json); every pages/*.json intro is an object, never a string; NEVER write image/gallery paths",
            "gate": {"cwd": f"projects/{slug}", "argv": ["npm", "run", "content-check"]},
        },
        "translation": {
            "owner": "lingua",
            "next": "build",
            "task": "translate every source entry into the locales declared in site.json (run your multi-locale-translation-pass skill)",
            "gate": {"cwd": f"projects/{slug}", "argv": ["npm", "run", "content-check"]},
        },
        "build": {
            "owner": "pixel",
            "next": "qa",
            "task": "green npm run ship ONLY (manifest → build → preflight), dist/ on disk",
            "gate": {"cwd": f"projects/{slug}", "argv": ["test", "-d", "dist"]},
        },
        "qa": {
            "owner": "lens",
            "task": f"audit projects/{slug}/dist/ against the launch checklist; one PASS/FAIL verdict",
        },
    }
    launch_line = f" Launch target: {launch_date}." if launch_date else ""
    # Project facts + pipeline map ONLY. How each agent operates lives in its
    # soul/skills; the hub's phase procedure lives in mira's project-lifecycle
    # skill. Prose duplicated here proved both noisy and unenforceable.
    meta["briefing"] = (
        f"Workgroup for hotel '{slug}' — produce its launch-ready website.{launch_line}\n"
        f"Brief (raw, immutable): projects/{slug}/brief.md\n"
        f"Contract: factory/template-spec.json · agents produce ONLY data "
        f"(src/config/site.json + src/content/**) · components, themes and *.ts are the fixed design layer.\n"
        f"Pipeline, one owner per phase: #intake @scout · #assets @muse · #content @quill · "
        f"#translation @lingua · #build @pixel · #qa @lens.\n"
        f"The hub (mira) runs the phase procedure from its meta/project-lifecycle skill."
    )
    meta_path.write_text(yaml.safe_dump(meta, sort_keys=False, allow_unicode=True))
    return wg_dir.name


def kickoff(slug: str) -> None:
    name = f"proj-{slug}"
    wg = find_wg_dir(HUB, name)
    if not wg:
        warn("kickoff skipped — workgroup not found")
        return
    text = (
        "@scout #task #intake · pick the theme + write src/config/site.json + intake.md\n\n"
        f"Kickoff for {name}. Raw brief at `projects/{slug}/brief.md`. Deliverables "
        "and rubric: your craft + factory/template-spec.json. End the handoff with "
        "the `visual_assets:` signal line."
    )
    res = run(["alpi", "-p", HUB, "workgroup", "post", wg.name, text])
    if res.returncode != 0:
        warn(f"kickoff post failed: {res.stderr.strip()}")


def advance_status_intake(project: Path) -> None:
    status = yaml.safe_load((project / "status.yaml").read_text()) or {}
    today = run(["date", "+%Y-%m-%d"]).stdout.strip()
    status["state"] = "intake"
    status.setdefault("history", []).append(
        {"state": "intake", "at": today, "by": "new-project.py", "note": "kickoff task posted to scout"}
    )
    (project / "status.yaml").write_text(yaml.safe_dump(status, sort_keys=False, allow_unicode=True))


PHASES = PIPELINE.split(",")


def _canonical_phase(slug: str) -> str | None:
    slug = (slug or "").lower()
    for phase in sorted(PHASES, key=len, reverse=True):
        if slug == phase or slug.startswith(phase + "-"):
            return phase
    return None


def derive_state(posts: list[dict], hub_pubkey: str) -> str | None:
    """Fold the transcript's task ledger into the pipeline state; None = no signal."""
    from alpi.alp import tasks as wg_tasks

    events = []
    for p in posts:
        events.extend(wg_tasks.parse_post(
            str(p.get("text") or ""), int(p.get("seq", 0)),
            str(p.get("from") or ""), hub_pubkey=hub_pubkey,
        ))
    folded = wg_tasks.fold_tasks(events)
    if not folded:
        return None
    last = folded[-1]
    phase = _canonical_phase(last.slug)
    if last.is_open:
        if last.slug.startswith("maint-"):
            return "maintenance"
        return phase or "iterating"
    result = (last.result or "").strip().upper()
    if result.startswith("BLOCKED"):
        return "blocked"
    if last.slug.startswith("maint-"):
        return "launched"
    if phase == PHASES[-1]:
        return "launched"
    if phase in PHASES:
        return PHASES[PHASES.index(phase) + 1]
    return None


def sync_status_payload(status: dict, derived: str, today: str) -> tuple[dict, bool]:
    current = str(status.get("state", ""))
    if current == derived:
        return status, False
    updated = dict(status)
    updated["state"] = derived
    if derived == "launched" and not updated.get("launched_at"):
        updated["launched_at"] = today
    history = list(updated.get("history") or [])
    history.append({
        "state": derived,
        "at": today,
        "by": "status-sync",
        "note": f"derived from transcript (was {current or '?'})",
    })
    updated["history"] = history
    return updated, True


def sync_status(slug: str) -> None:
    project = PROJECTS / slug
    if not project.exists():
        fail(f"no project at projects/{slug}")
    wg = find_wg_dir(HUB, f"proj-{slug}")
    if wg is None:
        fail(f"workgroup proj-{slug} not found on hub {HUB}")
    from alpi.alp import workgroup as wg_mod
    from alpi.service import _all_hub_posts_decrypted

    home = Path.home() / ".alpi" / "profiles" / HUB
    wg_obj = wg_mod.load(home, wg.name)
    posts = _all_hub_posts_decrypted(home, wg_obj)
    derived = derive_state(posts, wg_obj.meta.hub_pubkey)
    if derived is None:
        warn("transcript carries no task signal — status.yaml untouched")
        return
    status = yaml.safe_load((project / "status.yaml").read_text()) or {}
    current = str(status.get("state", ""))
    today = run(["date", "+%Y-%m-%d"]).stdout.strip()
    status, changed = sync_status_payload(status, derived, today)
    if not changed:
        ok(f"status.yaml already '{current}' — in sync with the transcript")
        return
    from alpi.config import atomic_write_yaml

    atomic_write_yaml(project / "status.yaml", status)
    ok(f"status.yaml: {current or '?'} → {derived} (transcript is truth)")


def audit(slug: str) -> None:
    """Read-only guard: flag a status.yaml.state that disagrees with what's on disk."""
    project = PROJECTS / slug
    if not project.exists():
        fail(f"no project at projects/{slug}")
    status = yaml.safe_load((project / "status.yaml").read_text()) or {}
    state = str(status.get("state", "?"))
    site = project / "src" / "config" / "site.json"
    locales = []
    if site.exists():
        try:
            locales = json.loads(site.read_text()).get("locales") or []
        except Exception:  # noqa: BLE001
            pass
    dist = project / "dist"
    html = sorted(dist.rglob("*.html")) if dist.exists() else []
    sitemap = dist.exists() and any(dist.glob("sitemap*.xml"))
    robots = (dist / "robots.txt").exists()
    # NOT a launch gate (preflight + lens own that) — just "are there build
    # artifacts on disk", enough to catch a state that disagrees with disk.
    has_artifacts = bool(html) and sitemap and robots

    print("  status sanity (not the launch gate — preflight + lens own readiness)")
    print(f"  state: {state}")
    print(f"  site.json: {'present' if site.exists() else 'MISSING'}  locales={locales or '—'}")
    print(f"  dist: {len(html)} html · sitemap={'yes' if sitemap else 'no'} · robots={'yes' if robots else 'no'}")

    issues = []
    if has_artifacts and state in {"created", "intake", "assets", "content", "translation", "build"}:
        issues.append(f"build artifacts on disk but state={state} → close build, open #qa (don't re-run content/intake)")
    if state == "launched" and not has_artifacts:
        issues.append("state=launched but dist has no build artifacts (html+sitemap+robots)")
    if state in {"build", "qa", "launched"} and not site.exists():
        issues.append(f"state={state} but site.json is missing")
    if issues:
        for i in issues:
            warn(i)
        sys.exit(2)
    ok("status.yaml is consistent with what's on disk")


def nuke(slug: str) -> None:
    name = f"proj-{slug}"
    wg = find_wg_dir(HUB, name)
    if wg:
        wg_id = wg.name
        for m in PROJECT_MEMBERS:
            run(["alpi", "-p", m, "workgroup", "leave", wg_id])
        res = run(["alpi", "-p", HUB, "workgroup", "remove", wg_id, "--yes"], timeout=15.0)
        if res.returncode != 0:
            run(["alpi", "-p", HUB, "workgroup", "remove", wg_id, "--force"], timeout=15.0)
    project = PROJECTS / slug
    if project.exists():
        shutil.rmtree(project)
    ok(f"{slug} nuked. Re-run with `--brief <file>` to start fresh.")


def main() -> None:
    ap = argparse.ArgumentParser(description="Per-project bootstrap for the web factory.")
    ap.add_argument("slug")
    ap.add_argument("--brief", type=Path, default=None, help="raw client brief (copied verbatim to projects/<slug>/brief.md)")
    ap.add_argument("--assets", type=Path, default=None, help="folder of hotel-supplied photos, copied into projects/<slug>/assets/")
    ap.add_argument("--launch-date", default=None)
    ap.add_argument("--nuke", action="store_true", help="remove the workgroup + project dir")
    ap.add_argument("--audit", action="store_true", help="read-only: check status.yaml against disk, no changes")
    ap.add_argument("--sync-status", action="store_true", help="derive status.yaml state from the workgroup transcript (transcript is truth)")
    args = ap.parse_args()

    if args.nuke:
        nuke(args.slug)
        return

    if args.audit:
        audit(args.slug)
        return

    if args.sync_status:
        sync_status(args.slug)
        return

    if not TEMPLATE.exists():
        fail(f"template not found at {TEMPLATE} — bootstrap the org first")

    project = scaffold(args.slug, args.brief)
    if args.assets is not None:
        if not args.assets.is_dir():
            fail(f"--assets folder not found: {args.assets}")
        n = 0
        for f in sorted(args.assets.iterdir()):
            if f.is_file() and not f.name.startswith("."):
                shutil.copy(f, project / "assets" / f.name)
                n += 1
        ok(f"{n} hotel asset(s) copied → projects/{args.slug}/assets/")
    write_status(args.slug, project)
    create_workgroup(args.slug)
    wg_id = attach_briefing(args.slug, args.launch_date)
    if wg_id:
        join_members(wg_id)
        ok(f"created proj-{args.slug}  ({wg_id[:11]}…)")
    kickoff(args.slug)
    advance_status_intake(project)
    print("\033[34m=== ready ===\033[0m")


if __name__ == "__main__":
    main()
