import dataclasses
import re
from pathlib import Path

from alpi.config import DEFAULT_CONFIG, Config

REPO = Path(__file__).resolve().parents[2]
CONFIG_MD = REPO / "docs" / "CONFIG.md"


_DOC_KEY_RE = re.compile(r"`([a-z][a-z0-9_]*(?:\.[a-z_<>0-9]+)*)`")

_DOC_TOP_LEVEL_PREFIXES = {
    "model", "model_reasoning", "fallback_models", "workspace", "providers",
    "tools", "tui", "mcp", "gateway", "runtime", "memory", "alp", "host",
    "network", "budget", "service", "public_bio", "paused",
}


DOCUMENTED_BUT_PARSED_ELSEWHERE = {
    "tools.budget.per_result_chars",
    "tools.<name>.max_result_chars",
    "model_reasoning.effort",
    "memory.review_interval",
    "host.tcp_port",
    "host.device_name",
    "host.allow_public_bind",
    "alp.tcp_port",
    "network.host",
    "budget.daily_usd",
    "service.gateway",
    "service.schedule",
    "service.alp",
    "service.workgroups",
    "service.host",
    "mcp.servers",
    "gateway.imap.poll_interval",
    "gateway.imap.mark_as_read",
    "gateway.gmail.poll_interval",
    "gateway.gmail.mark_as_read",
    "providers.openrouter.models",
}


CODE_LEAVES_INTENTIONALLY_UNDOCUMENTED: set[str] = set()


_CONFIG_CONTAINER_FIELDS = {
    "providers", "tools", "memory", "model_reasoning", "runtime",
    "tui", "gateway", "alp", "host", "network", "budget", "service",
}

_CONFIG_INTERNAL_FIELDS = {"home", "raw"}

CONFIG_SCALAR_FIELDS_INTENTIONALLY_UNDOCUMENTED: set[str] = set()


def _flatten_default_config() -> set[str]:
    out: set[str] = set()
    def walk(prefix: str, value):
        if isinstance(value, dict) and value:
            for k, v in value.items():
                full = f"{prefix}.{k}" if prefix else k
                walk(full, v)
        else:
            if prefix:
                out.add(prefix)
    walk("", DEFAULT_CONFIG)
    return out


def _extract_keys_from_doc(text: str) -> set[str]:
    keys: set[str] = set()
    in_code_block = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        if not stripped.startswith("|"):
            continue
        for m in _DOC_KEY_RE.finditer(line):
            key = m.group(1)
            head = key.split(".", 1)[0]
            if head in _DOC_TOP_LEVEL_PREFIXES:
                keys.add(key)
    return keys


def test_config_doc_extractor_sees_known_keys():
    text = CONFIG_MD.read_text()
    keys = _extract_keys_from_doc(text)
    for required in ("model", "tools.browser.allow_local", "model_reasoning.effort",
                     "public_bio", "paused", "tools.terminal.sandbox",
                     "gateway.telegram", "gateway.matrix"):
        assert required in keys, (
            f"the doc-key extractor failed to pick up {required!r} — the regex is broken"
        )


def test_every_documented_config_key_resolves_in_code():
    text = CONFIG_MD.read_text()
    documented = _extract_keys_from_doc(text)

    default_keys = _flatten_default_config()
    default_inner_dicts = _flatten_default_config_with_dicts()
    top_level_fields = {f.name for f in dataclasses.fields(Config)}

    missing: list[str] = []
    for key in sorted(documented):
        if key in default_keys:
            continue
        if key in default_inner_dicts:
            continue
        if key in DOCUMENTED_BUT_PARSED_ELSEWHERE:
            continue
        if "." not in key and key in top_level_fields:
            continue
        missing.append(key)

    assert not missing, (
        "CONFIG.md documents keys not reachable in alpi/config.py:\n  "
        + "\n  ".join(missing)
        + "\nEither add the key to DEFAULT_CONFIG / a Config dataclass field, "
        "or list it in DOCUMENTED_BUT_PARSED_ELSEWHERE with the parsing site."
    )


def _flatten_default_config_with_dicts() -> set[str]:
    out: set[str] = set()
    def walk(prefix: str, value):
        if isinstance(value, dict):
            if not value and prefix:
                out.add(prefix)
            for k, v in value.items():
                full = f"{prefix}.{k}" if prefix else k
                if isinstance(v, dict) and not v:
                    out.add(full)
                walk(full, v)
        else:
            if prefix:
                out.add(prefix)
    walk("", DEFAULT_CONFIG)
    return out


def test_every_config_dataclass_scalar_field_is_documented():
    text = CONFIG_MD.read_text()
    documented = _extract_keys_from_doc(text)

    undocumented: list[str] = []
    for f in dataclasses.fields(Config):
        if f.name in _CONFIG_CONTAINER_FIELDS:
            continue
        if f.name in _CONFIG_INTERNAL_FIELDS:
            continue
        if f.name in CONFIG_SCALAR_FIELDS_INTENTIONALLY_UNDOCUMENTED:
            continue
        if f.name in documented:
            continue
        undocumented.append(f.name)

    assert not undocumented, (
        "alpi/config.py Config dataclass has top-level scalar fields not "
        "documented in CONFIG.md:\n  "
        + "\n  ".join(undocumented)
        + "\nAdd a backticked row in docs/CONFIG.md, or — if the field is a "
        "new container — add its name to _CONFIG_CONTAINER_FIELDS in this "
        "test and document its nested keys."
    )


def test_every_default_config_leaf_is_documented():
    text = CONFIG_MD.read_text()
    documented = _extract_keys_from_doc(text)
    code_leaves = _flatten_default_config() | _flatten_default_config_with_dicts()

    undocumented: list[str] = []
    for leaf in sorted(code_leaves):
        if leaf in documented:
            continue
        if leaf in CODE_LEAVES_INTENTIONALLY_UNDOCUMENTED:
            continue
        undocumented.append(leaf)

    assert not undocumented, (
        "alpi/config.py DEFAULT_CONFIG has leaves not documented in CONFIG.md:\n  "
        + "\n  ".join(undocumented)
        + "\nAdd a backticked mention in docs/CONFIG.md or list the leaf in "
        "CODE_LEAVES_INTENTIONALLY_UNDOCUMENTED with the reason."
    )
