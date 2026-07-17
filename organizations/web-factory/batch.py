from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import yaml

ORG_DIR = Path(__file__).resolve().parent
WORKSPACE = Path.home() / "git" / "web-factory"
HUB = "mira"
BRIEFINGS = ORG_DIR / "briefings"

DEFAULT_SET = ["golden", "visual", "restore", "boutique", "budget", "business", "resort"]
SLUGS = {
    "golden": "casa-bahia-golden", "visual": "marlene-suites-visual",
    "restore": "casa-patio-restore", "boutique": "casa-bahia",
    "budget": "easystay-atocha", "business": "heritage-towers", "resort": "bahia-mallorca",
}


def run(cmd, timeout=120.0):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL)


def find_wg(slug):
    root = Path.home() / ".alpi" / "profiles" / HUB / "alp" / "workgroups"
    for d in (root.iterdir() if root.exists() else []):
        meta = d / "meta.yaml"
        if meta.exists() and (yaml.safe_load(meta.read_text()) or {}).get("name") == f"proj-{slug}":
            return d
    return None


def one(name, timeout_min):
    slug = SLUGS[name]
    project = WORKSPACE / "projects" / slug
    brief = BRIEFINGS / name / "brief.md"
    assets = BRIEFINGS / name / "assets"
    np = ORG_DIR / "new-project.py"
    run([sys.executable, str(np), slug, "--nuke"], timeout=120)
    cmd = [sys.executable, str(np), slug, "--brief", str(brief)]
    if assets.is_dir() and any(p.suffix in {".jpg", ".png", ".jpeg"} for p in assets.iterdir()):
        cmd += ["--assets", str(assets)]
    t0 = time.time()
    res = run(cmd, timeout=300)
    if res.returncode != 0:
        return {"name": name, "slug": slug, "outcome": "CREATE-FAIL", "detail": res.stderr.strip()[:80]}
    deadline = time.time() + timeout_min * 60
    outcome = "TIMEOUT"
    while time.time() < deadline:
        st = (yaml.safe_load((project / "status.yaml").read_text()) or {}) if (project / "status.yaml").exists() else {}
        if st.get("state") == "launched":
            outcome = "launched"
            break
        wg = find_wg(slug)
        if wg and "#done BLOCKED" in run(["alpi", "-p", HUB, "workgroup", "show", wg.name]).stdout:
            outcome = "BLOCKED"
            break
        time.sleep(20)
    mins = (time.time() - t0) / 60

    st = (yaml.safe_load((project / "status.yaml").read_text()) or {}) if (project / "status.yaml").exists() else {}
    site = json.loads((project / "src" / "config" / "site.json").read_text()) if (project / "src" / "config" / "site.json").exists() else {}
    dist = project / "dist"
    html = len(list(dist.rglob("*.html"))) if dist.exists() else 0
    manifest = project / "assets" / "assets.yaml"
    slots = manifest.read_text().count("slot:") if manifest.exists() else 0
    wg = find_wg(slug)
    ledger = (wg / "ledger.json") if wg else None
    usd = json.loads(ledger.read_text()).get("usd", 0) if ledger and ledger.exists() else 0
    return {
        "name": name, "slug": slug, "outcome": outcome,
        "theme": site.get("theme", "?"), "locales": ",".join(site.get("locales", [])),
        "pid": site.get("booking", {}).get("propertyId", "") or "(empty→demo)",
        "pages": html, "slots": slots, "iters": st.get("iterations", "?"),
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
              f"iters={r.get('iters','?')} · ${r.get('usd','?')} · {r.get('min','?')}min\n", flush=True)

    print("\n=== ANALYSIS ===")
    hdr = f"{'brief':<10} {'outcome':<9} {'theme':<9} {'pages':>5} {'locales':<14} {'pid':<14} {'slots':>5} {'iters':>5} {'usd':>6} {'min':>5}"
    print(hdr); print("-" * len(hdr))
    for r in rows:
        if r["outcome"] in {"CREATE-FAIL"}:
            print(f"{r['name']:<10} {r['outcome']:<9} {r.get('detail','')}")
            continue
        print(f"{r['name']:<10} {r['outcome']:<9} {r.get('theme','?'):<9} {r.get('pages',0):>5} "
              f"{r.get('locales',''):<14} {str(r.get('pid','')):<14} {r.get('slots',0):>5} "
              f"{str(r.get('iters','')):>5} {r.get('usd',0):>6} {r.get('min',0):>5}")
    launched = sum(1 for r in rows if r["outcome"] == "launched")
    total_usd = round(sum(r.get("usd", 0) for r in rows), 2)
    print(f"\n{launched}/{len(rows)} launched · total ${total_usd}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
