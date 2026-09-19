from __future__ import annotations

from pathlib import Path
import re
import tomllib

import alpi.tools  # noqa: F401  — the import is what populates the registry
from alpi.tools import all_tools


ROOT = Path(__file__).resolve().parents[2]
ARCHITECTURE = (ROOT / "docs" / "ARCHITECTURE.md").read_text()
CONFIG = (ROOT / "docs" / "CONFIG.md").read_text()


def _runtime_dependencies() -> set[str]:
    raw = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["dependencies"]
    return {re.split(r"[<>=!~\[ ]", spec, 1)[0].strip() for spec in raw}


def _dependencies_section() -> str:
    start = ARCHITECTURE.index("## Dependencies")
    end = ARCHITECTURE.index("\n## ", start + 1)
    return ARCHITECTURE[start:ARCHITECTURE.index("Optional `dev` extra", start, end)]


def test_every_runtime_dependency_is_justified_in_the_docs():
    section = _dependencies_section()
    undocumented = sorted(d for d in _runtime_dependencies() if d not in section)
    assert undocumented == [], (
        "SECURITY.md requires a line per runtime dep in ARCHITECTURE.md → Dependencies; "
        f"missing: {undocumented}"
    )


def test_the_dependency_section_names_nothing_that_is_not_a_dependency():
    section = _dependencies_section()
    named = set(re.findall(r"^- `([a-z0-9][a-z0-9._-]*)`", section, re.M))
    named |= set(re.findall(r"\+ `([a-z0-9][a-z0-9._-]*)`", section))
    stale = sorted(named - _runtime_dependencies())
    assert stale == [], f"documented but no longer a runtime dependency: {stale}"


def test_every_tool_name_offered_for_tools_deny_is_registered():
    start = CONFIG.index("Canonical names are the strings used at registration time")
    sentence = CONFIG[start:CONFIG.index(".", CONFIG.index("etc", start))]
    offered = set(re.findall(r"`([a-z][a-z0-9_]*)`", sentence))
    unenforceable = sorted(offered - {t.name for t in all_tools()})
    assert unenforceable == [], (
        f"CONFIG.md offers these for tools.deny but nothing registers them, and the same "
        f"page says an unknown deny name is a silent no-op: {unenforceable}"
    )
