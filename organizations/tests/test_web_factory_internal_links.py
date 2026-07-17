import re
from pathlib import Path

import pytest

ORGS_ROOT = Path(__file__).resolve().parents[1]
WEB_FACTORY = ORGS_ROOT / "web-factory"

pytestmark = pytest.mark.skipif(
    not WEB_FACTORY.exists(),
    reason="organizations/web-factory/ is not in this checkout (subtree imported once acceptance fixtures pass)",
)

_PREFIXED_LINK_RE = re.compile(
    r"`((?:factory|templates|library|briefings|projects|archive|src|public|agents|workgroups)/[A-Za-z0-9_./-]+)`"
)

_BARE_MD_RE = re.compile(r"`([A-Za-z][A-Za-z0-9_.-]*\.md)`")

_RUNTIME_PATH_PREFIXES = ("projects/", "archive/", "src/", "public/")

_RUNTIME_BARE_NAMES = {
    "intake.md", "brief.md", "AGENT.md", "USER.md",
    "CHANGELOG.md",
    "NNN-short-title.md",
}


_SKIP_DIRS = {"templates"}


def _walk_lines_outside_code(text: str):
    in_code_block = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        yield line


def test_internal_factory_links_resolve_on_disk():
    broken: list[tuple[str, str]] = []
    for md in WEB_FACTORY.rglob("*.md"):
        rel_md = md.relative_to(WEB_FACTORY)
        text = md.read_text()
        for line in _walk_lines_outside_code(text):
            for m in _PREFIXED_LINK_RE.finditer(line):
                ref = m.group(1)
                if ref.startswith(_RUNTIME_PATH_PREFIXES):
                    continue
                if "*" in ref:
                    continue
                if not ref.endswith((".md", ".json", ".html", ".yaml", ".yml", ".css", ".js", ".jsx", ".astro", ".py")):
                    continue
                if not (WEB_FACTORY / ref).exists():
                    broken.append((str(rel_md), ref))
    assert not broken, (
        "web-factory backticked prefixed links pointing at non-existent files:\n  "
        + "\n  ".join(f"{src} → `{ref}`" for src, ref in broken)
    )


def test_bare_markdown_refs_resolve_relative_to_their_doc():
    broken: list[tuple[str, str]] = []
    for md in WEB_FACTORY.rglob("*.md"):
        rel_md = md.relative_to(WEB_FACTORY)
        if rel_md.parts and rel_md.parts[0] in _SKIP_DIRS:
            continue
        text = md.read_text()
        for line in _walk_lines_outside_code(text):
            for m in _BARE_MD_RE.finditer(line):
                name = m.group(1)
                if name in _RUNTIME_BARE_NAMES:
                    continue
                if (md.parent / name).exists():
                    continue
                if (WEB_FACTORY / name).exists():
                    continue
                broken.append((str(rel_md), name))
    assert not broken, (
        "web-factory backticked bare `.md` refs that resolve neither next "
        "to their own file nor at the org root:\n  "
        + "\n  ".join(f"{src} → `{ref}`" for src, ref in broken)
    )
