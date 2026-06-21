import ast
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ALP_MD = REPO / "docs" / "ALP.md"
ALP_REF = REPO / "alpi" / "knowledge" / "references" / "alp.md"
HANDLERS = REPO / "alpi" / "alp" / "handlers.py"
ALP_INIT = REPO / "alpi" / "alp" / "__init__.py"


SILENT_DROPPED_ENVELOPE_ERRORS = {"-32002", "-32003", "-32006"}
CLIENT_SIDE_ONLY_CODES = {"-32004", "-32011"}


def _handler_run_turn_return_keys() -> set[str]:
    tree = ast.parse(HANDLERS.read_text())
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or node.name != "_run_turn":
            continue
        for sub in ast.walk(node):
            if isinstance(sub, ast.Return) and isinstance(sub.value, ast.Dict):
                return {
                    ast.literal_eval(k)
                    for k in sub.value.keys
                    if isinstance(k, ast.Constant)
                }
    raise AssertionError("alpi/alp/handlers.py::_run_turn return dict not found")


def _doc_link_ask_nonstreaming_keys() -> set[str]:
    text = ALP_MD.read_text()
    section = re.search(
        r"### `link\.ask`(.+?)### `link\.cancel`", text, re.DOTALL,
    )
    assert section, "docs/ALP.md: link.ask section not found"
    block = re.search(
        r"```\s*\nparams:.+?\nresult:\s*(?:#[^\n]*)?\n(.+?)```",
        section.group(1), re.DOTALL,
    )
    assert block, "docs/ALP.md: link.ask non-streaming result block not found"
    keys: set[str] = set()
    for line in block.group(1).splitlines():
        m = re.match(r"\s+([a-z_][a-z0-9_]*)\s*[:?]", line)
        if m:
            keys.add(m.group(1))
    return keys


def test_link_ask_doc_matches_handler_return():
    handler = _handler_run_turn_return_keys()
    doc = _doc_link_ask_nonstreaming_keys()
    assert handler == doc, (
        "link.ask result drift between alpi/alp/handlers.py and docs/ALP.md:\n"
        f"  handler returns: {sorted(handler)}\n"
        f"  doc lists:       {sorted(doc)}\n"
        f"  doc-only:        {sorted(doc - handler)}\n"
        f"  handler-only:    {sorted(handler - doc)}"
    )


def test_alp_doc_error_table_omits_silent_dropped():
    text = ALP_MD.read_text()
    table_m = re.search(r"## Error codes(.+?)\n## ", text, re.DOTALL)
    assert table_m, "docs/ALP.md: '## Error codes' section not found"
    table = table_m.group(1)
    listed = {code for code in SILENT_DROPPED_ENVELOPE_ERRORS if f"`{code}`" in table}
    assert not listed, (
        "docs/ALP.md error code table lists envelope-level errors that the "
        "server silent-drops (no wire error reaches the caller):\n  "
        + "\n  ".join(sorted(listed))
        + "\nDescribe these in the Envelope / Versioning sections as "
        "'silent-drop', not in the wire error code table."
    )


def test_alp_reference_error_table_omits_silent_dropped():
    text = ALP_REF.read_text()
    listed = {code for code in SILENT_DROPPED_ENVELOPE_ERRORS if f"`{code}`" in text}
    assert not listed, (
        "alpi/knowledge/references/alp.md lists silent-dropped envelope errors "
        "as wire codes:\n  " + "\n  ".join(sorted(listed))
    )


def test_alp_doc_error_table_omits_client_side_codes():
    text = ALP_MD.read_text()
    table_m = re.search(r"## Error codes(.+?)(?=\n### |\n## )", text, re.DOTALL)
    assert table_m, "docs/ALP.md: '## Error codes' section not found"
    table_only = re.split(r"\n### Client-side diagnostics", table_m.group(1))[0]
    listed = {c for c in CLIENT_SIDE_ONLY_CODES if f"`{c}`" in table_only}
    assert not listed, (
        "docs/ALP.md wire error table lists client-side-only codes:\n  "
        + "\n  ".join(sorted(listed))
        + "\nThese are SDK exceptions without a JSON-RPC code; describe "
        "them under '### Client-side diagnostics' instead."
    )


def test_alp_reference_error_table_omits_client_side_codes():
    text = ALP_REF.read_text()
    table_m = re.search(r"## Error codes(.+?)(?=\nClient-side diagnostics|\n## )", text, re.DOTALL)
    assert table_m, "references/alp.md: '## Error codes' section not found"
    listed = {c for c in CLIENT_SIDE_ONLY_CODES if f"`{c}`" in table_m.group(1)}
    assert not listed, (
        "references/alp.md error table lists client-side-only codes:\n  "
        + "\n  ".join(sorted(listed))
    )


def test_alp_init_docstring_does_not_claim_wire_error_on_version_mismatch():
    text = ALP_INIT.read_text()
    for code in SILENT_DROPPED_ENVELOPE_ERRORS:
        assert code not in text, (
            f"alpi/alp/__init__.py still references {code} for envelope "
            f"errors that the server silent-drops. Align the docstring with "
            f"the runtime."
        )
