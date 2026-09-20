from __future__ import annotations

from pathlib import Path
import re
import tomllib

import alpi.tools  # noqa: F401  — the import is what populates the registry
from dataclasses import fields, is_dataclass
import typing

from alpi import config as config_mod
from alpi.cli import main as cli_main
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


def _cli_invocations():
    # ROADMAP.md names commands on purpose that do not exist: proposals and discarded ideas.
    pages = [p for p in (ROOT / "docs").glob("*.md") if p.name != "ROADMAP.md"]
    for page in pages:
        for span in re.findall(r"`([^`\n]+)`", page.read_text()):
            words = span.replace("\\", "").split()
            if not words or words[0] != "alpi":
                continue
            rest = words[1:]
            while rest and (rest[0].startswith("-") or (len(rest) > 1 and rest[0] in ("-p", "--profile"))):
                rest = rest[2:] if rest[0] in ("-p", "--profile") else rest[1:]
            # A command is a bare word; `alpi (<profile>)` is the process title ps shows.
            if rest and re.fullmatch(r"[a-z][a-z-]*", rest[0]):
                yield page.name, rest[0]


def test_every_alpi_command_the_docs_show_actually_exists():
    real = set(cli_main.commands)
    bogus = sorted({f"{page}: alpi {name}" for page, name in _cli_invocations() if name not in real})
    assert bogus == [], f"documented commands that do not exist: {bogus}"


def test_the_scan_finds_the_commands_at_all_so_an_empty_sweep_cannot_pass():
    names = {name for _, name in _cli_invocations()}
    assert len(names) >= 10
    assert {"chat", "doctor", "workgroup"} <= names


# Config models these as bare dicts, so reflection cannot reach their keys.
UNTYPED_SECTIONS = {"providers", "tui", "email", "alp", "host", "network", "budget", "relay"}
NOT_CONFIG = {"home", "raw"}
# Documented keys read straight off cfg.raw, past the dataclass. Each must stay documented.
RAW_READ_KEYS = {
    "mcp.servers",
    "tools.budget.per_result_chars",
    "tools.web_search.max_per_turn",
}


def _config_keys(cls=config_mod.Config, prefix=""):
    hints = typing.get_type_hints(cls)
    out = set()
    for f in fields(cls):
        if not prefix and f.name in NOT_CONFIG:
            continue
        name = f"{prefix}.{f.name}" if prefix else f.name
        nested = hints.get(f.name)
        out |= _config_keys(nested, name) if is_dataclass(nested) else {name}
    return out


def _documented_rows():
    return set(re.findall(r"^\| `([a-z][a-z0-9_.]*)`", (ROOT / "docs" / "CONFIG.md").read_text(), re.M))


def test_every_typed_config_field_has_a_row_in_the_reference():
    missing = sorted(
        key for key in _config_keys()
        if key not in _documented_rows() and key not in UNTYPED_SECTIONS
    )
    assert missing == [], f"config fields with no row in CONFIG.md: {missing}"


def test_every_documented_row_under_a_typed_section_is_a_real_field():
    keys = _config_keys()
    orphans = sorted(
        row for row in _documented_rows()
        if row.split(".")[0] not in UNTYPED_SECTIONS
        and row not in keys
        and row not in RAW_READ_KEYS
    )
    assert orphans == [], f"CONFIG.md rows with no config field behind them: {orphans}"


def test_no_raw_read_exception_outlives_the_row_it_excuses():
    stale = sorted(RAW_READ_KEYS - _documented_rows())
    assert stale == [], f"exceptions for rows that no longer exist: {stale}"


def test_the_reflection_reaches_the_whole_config_so_an_empty_sweep_cannot_pass():
    keys = _config_keys()
    assert len(keys) >= 40
    assert {"model", "workspace", "tiers.fast.model", "runtime.max_retries"} <= keys
    assert len(_documented_rows()) >= 50


def _alpi_sources():
    return [f for f in (ROOT / "alpi").rglob("*.py")]


def test_every_documented_key_in_an_untyped_section_is_named_somewhere_in_the_code():
    # Reflection cannot reach a dict[str, Any], so this asks a weaker question the code can
    # still answer: does anything read a key by this name? It catches a row that outlived
    # its knob, not a knob that was never written down.
    bodies = [f.read_text() for f in _alpi_sources()]
    unread = sorted(
        row for row in _documented_rows()
        if row.split(".")[0] in UNTYPED_SECTIONS
        and not any(f'"{row.split(".")[-1]}"' in b or f"'{row.split('.')[-1]}'" in b for b in bodies)
    )
    assert unread == [], f"CONFIG.md documents keys no code names: {unread}"


def test_the_source_sweep_reads_the_package_so_an_empty_scan_cannot_pass():
    sources = _alpi_sources()
    assert len(sources) > 80
    assert any("max_active_workgroups" in f.read_text() for f in sources)
