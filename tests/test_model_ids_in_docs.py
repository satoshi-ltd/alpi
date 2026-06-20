import re
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
CATALOG_PATH = REPO / "alpi" / "providers" / "openrouter_models.yaml"

DOCS = [
    REPO / "docs" / "MODELS.md",
    REPO / "alpi" / "knowledge" / "references" / "models.md",
    REPO / "alpi" / "knowledge" / "references" / "config.md",
]

NATIVE_ANTHROPIC = re.compile(r"^claude-(opus|sonnet|haiku)-\d+-\d+$")
NATIVE_OPENAI = re.compile(r"^(gpt-\d|o\d)")
BARE_OR_IDS = {"owl-alpha"}


def _load_catalog() -> set[str]:
    data = yaml.safe_load(CATALOG_PATH.read_text(encoding="utf-8"))
    return set(data.keys()) if isinstance(data, dict) else set()


def _or_vendors(catalog: set[str]) -> set[str]:
    vendors: set[str] = set()
    for key in catalog:
        if "/" in key:
            vendors.add(key.split("/", 1)[0])
    return vendors


def _candidate_ids(text: str) -> list[str]:
    backticked = re.findall(r"`([a-z][a-z0-9./\-]+)`", text)
    yaml_model = re.findall(r"(?m)^\s*model:\s*([a-z0-9][a-z0-9./\-]+)\s*$", text)
    return backticked + yaml_model


def _is_native(s: str) -> bool:
    if NATIVE_ANTHROPIC.match(s):
        return True
    if "/" not in s and NATIVE_OPENAI.match(s):
        return True
    return False


def _is_or_route(s: str, vendors: set[str]) -> bool:
    bare = s.removeprefix("openrouter/")
    if _is_native(bare):
        return False
    if "/" in bare:
        return bare.split("/", 1)[0] in vendors
    return bare in BARE_OR_IDS


def _in_catalog(catalog: set[str], doc_id: str) -> bool:
    bare = doc_id.removeprefix("openrouter/")
    return bare in catalog or f"openrouter/{bare}" in catalog


@pytest.mark.parametrize("doc", DOCS, ids=lambda p: str(p.relative_to(REPO)))
def test_openrouter_ids_resolve_in_catalog(doc):
    catalog = _load_catalog()
    vendors = _or_vendors(catalog)
    or_ids = [c for c in _candidate_ids(doc.read_text()) if _is_or_route(c, vendors)]
    missing = sorted({c for c in or_ids if not _in_catalog(catalog, c)})
    assert not missing, f"{doc.name}: IDs not in openrouter_models.yaml — {missing}"


def test_guard_actually_sees_or_ids():
    catalog = _load_catalog()
    vendors = _or_vendors(catalog)
    found = []
    for doc in DOCS:
        found.extend(c for c in _candidate_ids(doc.read_text()) if _is_or_route(c, vendors))
    assert len(found) >= 30, f"guard regex matched only {len(found)} OR IDs — likely broken"
