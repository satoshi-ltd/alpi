from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import yaml

ORG_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import pipeline_state  # noqa: E402

WORKSPACE = Path.home() / "git" / "web-factory"
HUB = "mira"
HUB_HOME = Path.home() / ".alpi" / "profiles" / HUB
RECIPE = ORG_DIR / "recipes" / "hotel.yaml"
MEMBERS = ["scout", "quill", "lingua", "muse", "pixel", "lens"]

FIXTURES = {
    "golden": {
        "slug": "casa-bahia-golden",
        "brief": "briefings/golden/brief.md",
        "url": "https://casabahia.es",
        "muse": False,
    },
    "visual": {
        "slug": "marlene-suites-visual",
        "brief": "briefings/visual/brief.md",
        "url": "https://marlenesuites.com",
        "muse": True,
    },
    "restore": {
        "slug": "casa-patio-restore",
        "brief": "briefings/restore/brief.md",
        "url": "https://casadelpatio.es",
        "muse": True,
        "assets_dir": "briefings/restore/assets",
        "restored": True,
    },
}

GREEN, RED, RESET = "\033[32m", "\033[31m", "\033[0m"


def run(cmd: list[str], timeout: float = 120.0) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL)


def find_wg(slug: str) -> Path | None:
    return pipeline_state.find_wg(HUB_HOME, HUB, slug)


def transcript(wg_id: str) -> str:
    return run(["alpi", "-p", HUB, "workgroup", "show", wg_id]).stdout


def teardown(slug: str) -> None:
    wg = find_wg(slug)
    if wg:
        wid = wg.name
        for m in MEMBERS:
            run(["alpi", "-p", m, "workgroup", "leave", wid])
        if run(["alpi", "-p", HUB, "workgroup", "remove", wid, "--yes"], timeout=30).returncode != 0:
            run(["alpi", "-p", HUB, "workgroup", "remove", wid, "--force"], timeout=30)
    project = WORKSPACE / "projects" / slug
    if project.exists():
        shutil.rmtree(project)


def state(slug: str) -> str | None:
    _, st = pipeline_state.read_state(HUB_HOME, HUB, slug)
    return st


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("fixture", choices=sorted(FIXTURES))
    ap.add_argument("--timeout-min", type=float, default=45.0)
    ap.add_argument("--no-recreate", action="store_true", help="assert against the existing project instead of teardown+launch")
    args = ap.parse_args()

    fx = FIXTURES[args.fixture]
    slug, project = fx["slug"], WORKSPACE / "projects" / fx["slug"]

    if not args.no_recreate:
        teardown(slug)
        cmd = ["alpi", "-p", HUB, "workgroup", "launch", "--recipe", str(RECIPE),
               "--param", f"slug={slug}", "--input", f"brief={ORG_DIR / fx['brief']}"]
        if fx.get("assets_dir"):
            cmd += ["--assets", str(ORG_DIR / fx["assets_dir"])]
        res = run(cmd, timeout=300)
        if res.returncode != 0:
            print(f"{RED}✗ recipe launch failed:{RESET} {res.stderr.strip()[:300]}")
            return 2
        print(f"launched proj-{slug} — waiting (max {args.timeout_min:.0f} min)")
        deadline = time.time() + args.timeout_min * 60
        while time.time() < deadline:
            if state(slug) == "launched":
                break
            wg = find_wg(slug)
            if wg and "#done BLOCKED" in transcript(wg.name):
                print(f"{RED}✗ pipeline BLOCKED{RESET}")
                return 1
            time.sleep(20)

    st = state(slug)
    wg = find_wg(slug)
    text = transcript(wg.name) if wg else ""
    site = json.loads((project / "src" / "config" / "site.json").read_text())
    dist = project / "dist"

    checks: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append((name, ok, detail))

    check("state == launched", st == "launched", str(st))
    check("no qa-recheck loop (clean first pass)", "#qa-recheck" not in text)
    check("no #done BLOCKED", "#done BLOCKED" not in text)
    check(f"site.json url == {fx['url']}", site.get("url") == fx["url"], str(site.get("url")))

    default_home = dist / site.get("defaultLocale", "es") / "index.html"
    canonical_ok = default_home.exists() and fx["url"] in default_home.read_text()
    check("canonical carries the brief's domain", canonical_ok)

    html = list(dist.rglob("*.html")) if dist.exists() else []
    check("dist has html for every locale", len(html) >= len(site.get("locales", [])) and (dist / "sitemap.xml").exists())

    asset_files = [p for p in (project / "assets").iterdir() if p.name != ".gitkeep"] if (project / "assets").exists() else []
    if fx["muse"]:
        ordered = "#task #assets" in text and "#task #content" in text and text.index("#task #assets") < text.index("#task #content")
        check("muse wrote the manifest", any(p.name == "assets.yaml" for p in asset_files), f"{len(asset_files)} files")
        check("#assets opened BEFORE #content", ordered)
        if fx.get("restored"):
            manifest = (project / "assets" / "assets.yaml")
            check("manifest carries kind: restored", manifest.exists() and "restored" in manifest.read_text())
            rooms_dir = project / "src" / "content" / "rooms"
            wired = rooms_dir.exists() and any("/img/" in p.read_text() for p in rooms_dir.glob("*.json"))
            check("restored photo wired into a room", wired)
            check("home ships a real image", default_home.exists() and "/img/" in default_home.read_text())
        else:
            check("logo svg produced", any(p.suffix == ".svg" for p in asset_files))
            check("generated hero shipped on home", default_home.exists() and "/img/hero-main" in default_home.read_text())
    else:
        check("muse NOT tasked (signal not_required)", "@muse" not in text or "#task #assets" not in text.split("@muse", 1)[1][:200])
        check("assets dir untouched", not asset_files, f"{len(asset_files)} files")

    ledger = wg / "ledger.json" if wg else None
    usd = json.loads(ledger.read_text()).get("usd", 0) if ledger and ledger.exists() else 0
    check("cost under $2", usd < 2.0, f"${usd:.2f}")

    print()
    failed = [c for c in checks if not c[1]]
    for name, ok, detail in checks:
        mark = f"{GREEN}✓{RESET}" if ok else f"{RED}✗{RESET}"
        print(f"  {mark} {name}" + (f"  ({detail})" if detail and not ok else ""))
    print()
    verdict = f"{GREEN}ACCEPTANCE PASS{RESET}" if not failed else f"{RED}ACCEPTANCE FAIL · {len(failed)} criteria{RESET}"
    print(f"{verdict} · {args.fixture} · ${usd:.2f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
