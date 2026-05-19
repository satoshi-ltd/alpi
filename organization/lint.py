"""Lint SKILL.md files under organization/agents/.

Validates each skill's frontmatter against the live alpi tool registry and
checks structural conventions (state declarations, version drift). Findings
are printed as warnings; exit code is 0 unless --strict.

Run:
    python organization/lint.py            # warn-only
    python organization/lint.py --strict   # exit 1 on any finding
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
AGENTS_DIR = ROOT / "agents"
ALPI_TOOLS_DIR = ROOT.parent / "alpi" / "tools"


def canonical_tools() -> set[str]:
    names: set[str] = set()
    for py in ALPI_TOOLS_DIR.glob("*.py"):
        if py.name.startswith("_"):
            continue
        for m in re.finditer(r'^\s+name\s*=\s*"([a-z_]+)"', py.read_text(), re.M):
            names.add(m.group(1))
    return names


def parse_frontmatter(path: Path) -> tuple[dict, str]:
    text = path.read_text()
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 4)
    if end < 0:
        return {}, text
    fm = yaml.safe_load(text[4:end]) or {}
    body = text[end + 4:]
    return fm, body


def lint_skill(path: Path, tools: set[str]) -> list[str]:
    findings: list[str] = []
    fm, body = parse_frontmatter(path)

    declared = list(fm.get("tools") or [])
    unknown = [t for t in declared if t not in tools]
    if unknown:
        findings.append(f"unknown tool(s) in frontmatter: {unknown}")

    # Tools used in body (as backticked identifiers) but not declared.
    body_lower = body.lower()
    backticked = set(re.findall(r"`([a-z_]+)`", body_lower))
    referenced = backticked & tools
    missing = sorted(referenced - set(declared))
    # Filter common false positives (skill identifiers, generic shell verbs).
    missing = [m for m in missing if m not in {"skill"}]
    if missing:
        findings.append(f"tool(s) referenced in body but not declared: {missing}")

    # SQL schema without explicit storage hint.
    has_sql = "CREATE TABLE" in body
    if has_sql:
        sql_block = body[body.find("CREATE TABLE"):]
        if "state/db.sqlite" not in body and "state/" not in sql_block[:300]:
            findings.append("CREATE TABLE present but no `state/db.sqlite` storage hint nearby")
        # Only flag destructive SQL inside ```sql fences, not in prose mentions.
        for fence in re.findall(r"```sql\n(.*?)```", body, re.S):
            if re.search(r"\bALTER\b|\bDROP\b", fence):
                findings.append("SQL fence contains ALTER/DROP — schema must be additive-only")
                break

    # Version drift: still 0.1.0 but file mtime > 30 days old.
    version = str(fm.get("version") or "")
    if version == "0.1.0":
        import time
        age_days = (time.time() - path.stat().st_mtime) / 86400
        if age_days > 30:
            findings.append(f"version still 0.1.0 after {int(age_days)} days — bump or remove field")

    # Empty/missing keywords on a non-trivial skill.
    if not fm.get("keywords") and len(body) > 500:
        findings.append("keywords are empty — discovery will not find this skill")

    return findings


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true", help="exit 1 if any finding")
    args = ap.parse_args()

    tools = canonical_tools()
    if not tools:
        print("error: no tools found in alpi/tools/", file=sys.stderr)
        return 2

    total = 0
    flagged = 0
    for skill in sorted(AGENTS_DIR.rglob("SKILL.md")):
        total += 1
        findings = lint_skill(skill, tools)
        if not findings:
            continue
        flagged += 1
        rel = skill.relative_to(ROOT)
        print(f"\n{rel}")
        for f in findings:
            print(f"  - {f}")

    print(f"\n{total} skills scanned · {flagged} flagged")
    return 1 if (args.strict and flagged) else 0


if __name__ == "__main__":
    sys.exit(main())
