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
BRIEFINGS = ORG_DIR / "briefings"
MEMBERS = ["scout", "quill", "lingua", "muse", "pixel", "lens"]

DEFAULT_SET = ["golden", "visual", "restore", "boutique", "budget", "business", "resort"]
SLUGS = {
    "golden": "casa-bahia-golden", "visual": "marlene-suites-visual",
    "restore": "casa-patio-restore", "boutique": "casa-bahia",
    "budget": "easystay-atocha", "business": "heritage-towers", "resort": "bahia-mallorca",
}


def run(cmd, timeout=120.0):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL)


def teardown(slug):
    wg = pipeline_state.find_wg(HUB_HOME, HUB, slug)
    if wg:
        wid = wg.name
        for m in MEMBERS:
            run(["alpi", "-p", m, "workgroup", "leave", wid])
        if run(["alpi", "-p", HUB, "workgroup", "remove", wid, "--yes"], timeout=30).returncode != 0:
            run(["alpi", "-p", HUB, "workgroup", "remove", wid, "--force"], timeout=30)
    project = WORKSPACE / "projects" / slug
    if project.exists():
        shutil.rmtree(project)


def one(name, timeout_min):
    slug = SLUGS[name]
    project = WORKSPACE / "projects" / slug
    brief = BRIEFINGS / name / "brief.md"
    assets = BRIEFINGS / name / "assets"
    teardown(slug)
    cmd = ["alpi", "-p", HUB, "workgroup", "launch", "--recipe", str(RECIPE),
           "--param", f"slug={slug}", "--input", f"brief={brief}"]
    if assets.is_dir() and any(p.suffix in {".jpg", ".png", ".jpeg"} for p in assets.iterdir()):
        cmd += ["--assets", str(assets)]
    t0 = time.time()
    res = run(cmd, timeout=300)
    if res.returncode != 0:
        return {"name": name, "slug": slug, "outcome": "LAUNCH-FAIL", "detail": res.stderr.strip()[:80]}
    deadline = time.time() + timeout_min * 60
    outcome = "TIMEOUT"
    while time.time() < deadline:
        _, st = pipeline_state.read_state(HUB_HOME, HUB, slug)
        if st == "launched":
            outcome = "launched"
            break
        wg = pipeline_state.find_wg(HUB_HOME, HUB, slug)
        if wg and "#done BLOCKED" in run(["alpi", "-p", HUB, "workgroup", "show", wg.name]).stdout:
            outcome = "BLOCKED"
            break
        time.sleep(20)
    mins = (time.time() - t0) / 60

    site = json.loads((project / "src" / "config" / "site.json").read_text()) if (project / "src" / "config" / "site.json").exists() else {}
    dist = project / "dist"
    html = len(list(dist.rglob("*.html"))) if dist.exists() else 0
    manifest = project / "assets" / "assets.yaml"
    slots = manifest.read_text().count("slot:") if manifest.exists() else 0
    wg = pipeline_state.find_wg(HUB_HOME, HUB, slug)
    ledger = (wg / "ledger.json") if wg else None
    usd = json.loads(ledger.read_text()).get("usd", 0) if ledger and ledger.exists() else 0
    return {
        "name": name, "slug": slug, "outcome": outcome,
        "theme": site.get("theme", "?"), "locales": ",".join(site.get("locales", [])),
        "pid": site.get("booking", {}).get("propertyId", "") or "(empty→demo)",
        "pages": html, "slots": slots,
        "usd": round(usd, 2), "min": round(mins, 1),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--set", nargs="*", default=DEFAULT_SET, choices=DEFAULT_SET)
    ap.add_argument("--timeout-min", type=float, default=55.0)
    args = ap.parse_args()

    print(f"batch · {len(args.set)} briefings · SEQUENTIAL (one roster) · up to {args.timeout_min:.0f} min each\n")
    rows = []
    for name in args.set:
        print(f"→ {name} ...", flush=True)
        r = one(name, args.timeout_min)
        rows.append(r)
        print(f"  {r['outcome']} · theme={r.get('theme','?')} · {r.get('pages','?')} pages · "
              f"{r.get('locales','?')} · pid={r.get('pid','?')} · slots={r.get('slots','?')} · "
              f"${r.get('usd','?')} · {r.get('min','?')}min\n", flush=True)

    print("\n=== ANALYSIS ===")
    hdr = f"{'brief':<10} {'outcome':<9} {'theme':<9} {'pages':>5} {'locales':<14} {'pid':<14} {'slots':>5} {'usd':>6} {'min':>5}"
    print(hdr); print("-" * len(hdr))
    for r in rows:
        if r["outcome"] in {"LAUNCH-FAIL"}:
            print(f"{r['name']:<10} {r['outcome']:<9} {r.get('detail','')}")
            continue
        print(f"{r['name']:<10} {r['outcome']:<9} {r.get('theme','?'):<9} {r.get('pages',0):>5} "
              f"{r.get('locales',''):<14} {str(r.get('pid','')):<14} {r.get('slots',0):>5} "
              f"{r.get('usd',0):>6} {r.get('min',0):>5}")
    launched = sum(1 for r in rows if r["outcome"] == "launched")
    total_usd = round(sum(r.get("usd", 0) for r in rows), 2)
    print(f"\n{launched}/{len(rows)} launched · total ${total_usd}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
