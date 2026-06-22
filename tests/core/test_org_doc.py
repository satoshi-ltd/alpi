import ast
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SETUP_PY = REPO / "organizations" / "setup.py"
ORG_MD = REPO / "docs" / "ORGANIZATION.md"
REF_MD = REPO / "alpi" / "knowledge" / "references" / "organization.md"


def _setup_tree() -> ast.AST:
    return ast.parse(SETUP_PY.read_text())


def _find_func(tree: ast.AST, name: str) -> ast.FunctionDef | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def _string_get_args(node: ast.AST, receivers: set[str]) -> set[str]:
    keys: set[str] = set()
    for sub in ast.walk(node):
        if not isinstance(sub, ast.Call):
            continue
        func = sub.func
        if not (isinstance(func, ast.Attribute) and func.attr == "get"):
            continue
        recv = func.value
        if isinstance(recv, ast.Name) and recv.id in receivers:
            pass
        else:
            continue
        if sub.args and isinstance(sub.args[0], ast.Constant) and isinstance(sub.args[0].value, str):
            keys.add(sub.args[0].value)
    return keys


_NESTED_CONTAINERS = {"models", "budgets"}


def _extract_org_yaml_keys() -> set[str]:
    tree = _setup_tree()
    init_org = _find_func(tree, "init_org")
    assert init_org is not None, "setup.py must expose init_org()"
    keys: set[str] = set()
    for sub in ast.walk(init_org):
        if not isinstance(sub, ast.Call):
            continue
        func = sub.func
        if not (isinstance(func, ast.Attribute) and func.attr == "get"):
            continue
        recv = func.value
        if not isinstance(recv, ast.Name):
            continue
        if not (sub.args and isinstance(sub.args[0], ast.Constant) and isinstance(sub.args[0].value, str)):
            continue
        leaf = sub.args[0].value
        if recv.id == "cfg":
            keys.add(leaf)
        elif recv.id in _NESTED_CONTAINERS:
            keys.add(f"{recv.id}.{leaf}")
    for container in _NESTED_CONTAINERS:
        keys.discard(container)
    return keys


_AGENT_MD_SUBSCRIPT_FIELDS = {"model", "reasoning_effort"}


def _extract_agent_md_fields() -> set[str]:
    tree = _setup_tree()
    fn = _find_func(tree, "_parse_agent_file")
    assert fn is not None, "setup.py must expose _parse_agent_file()"
    return _string_get_args(fn, {"front"}) | set(_AGENT_MD_SUBSCRIPT_FIELDS)


_WORKGROUP_SUBSCRIPT_FIELDS = {"hub"}


def _extract_workgroup_md_fields() -> set[str]:
    tree = _setup_tree()
    fn = _find_func(tree, "load_workgroups")
    assert fn is not None, "setup.py must expose load_workgroups()"
    return _string_get_args(fn, {"front"}) | set(_WORKGROUP_SUBSCRIPT_FIELDS)


def _doc_backticked(text: str) -> set[str]:
    backticked: set[str] = set()
    in_code_block = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        for m in re.finditer(r"`([a-z_][a-z_0-9.<>]*)`", line):
            backticked.add(m.group(1))
    return backticked


def _doc_table_first_column(text: str, after_header: str) -> set[str]:
    keys: set[str] = set()
    lines = text.splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if after_header in line)
    except StopIteration:
        return keys
    in_table = False
    saw_separator = False
    for line in lines[start + 1:]:
        stripped = line.strip()
        if stripped.startswith("##"):
            break
        if stripped.startswith("|"):
            in_table = True
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if not cells:
                continue
            first = cells[0]
            if re.fullmatch(r"-+:?", first.replace(":", "-")):
                saw_separator = True
                continue
            if not saw_separator:
                continue
            m = re.match(r"`([a-z_][a-z_0-9.<>]*)`", first)
            if m:
                keys.add(m.group(1))
        elif in_table:
            in_table = False
            saw_separator = False
    return keys


def test_org_yaml_table_matches_setup_extraction_exactly():
    code_keys = _extract_org_yaml_keys()
    table_keys = _doc_table_first_column(ORG_MD.read_text(), "### `org.yaml` — full schema")
    code_only = code_keys - table_keys
    doc_only = table_keys - code_keys
    assert not code_only and not doc_only, (
        "docs/ORGANIZATION.md `org.yaml` table drifted from setup.py extraction.\n"
        f"  code-only (missing in doc):  {sorted(code_only)}\n"
        f"  doc-only  (phantom in doc): {sorted(doc_only)}"
    )


def test_reference_documents_every_org_yaml_key_read_by_setup():
    code_keys = _extract_org_yaml_keys()
    doc = _doc_backticked(REF_MD.read_text())
    missing = [k for k in sorted(code_keys) if k not in doc]
    assert not missing, (
        f"alpi/knowledge/references/organization.md missing keys: {missing}"
    )


def test_agent_md_table_matches_setup_extraction_exactly():
    code_fields = _extract_agent_md_fields()
    table_fields = _doc_table_first_column(ORG_MD.read_text(), "### `agent.md` — frontmatter fields")
    code_only = code_fields - table_fields
    doc_only = table_fields - code_fields
    assert not code_only and not doc_only, (
        "docs/ORGANIZATION.md `agent.md` table drifted from setup.py extraction.\n"
        f"  code-only (missing in doc):  {sorted(code_only)}\n"
        f"  doc-only  (phantom in doc): {sorted(doc_only)}"
    )


def test_org_md_documents_every_workgroup_md_field_read_by_setup():
    code_fields = _extract_workgroup_md_fields()
    doc = _doc_backticked(ORG_MD.read_text())
    missing = [f for f in sorted(code_fields) if f not in doc]
    assert not missing, (
        f"docs/ORGANIZATION.md missing workgroup.md field rows: {missing}\n"
        f"setup.py extracted: {sorted(code_fields)}"
    )


def test_legacy_peers_field_is_marked_legacy_in_doc():
    text = ORG_MD.read_text()
    low = text.lower()
    assert "legacy" in low and "peers" in low, (
        "docs/ORGANIZATION.md must call agent.md `peers:` legacy back-compat "
        "(superseded by org.yaml peer_edges)"
    )


def test_workgroups_described_as_persistent_not_ephemeral():
    text = ORG_MD.read_text()
    low = text.lower()
    assert "persistent" in low, (
        "docs/ORGANIZATION.md must describe workgroups as persistent"
    )
    if "ephemeral" in low:
        for line in text.splitlines():
            line_low = line.lower()
            if "ephemeral" in line_low and "workgroup" in line_low:
                assert "not" in line_low or "no longer" in line_low, (
                    f"Line implies workgroups are ephemeral: {line!r}"
                )


def test_organization_topic_wired_in_knowledge_tool():
    from alpi.knowledge import TOPICS
    from alpi.tools.knowledge import _TOPIC_SUMMARIES, AlpiKnowledge, PROMPT_RULE

    assert "organization" in TOPICS, "TOPICS must contain the 'organization' topic"
    assert "organization" in _TOPIC_SUMMARIES, "_TOPIC_SUMMARIES missing 'organization'"
    assert _TOPIC_SUMMARIES["organization"].strip(), "organization summary must be non-empty"
    desc = AlpiKnowledge.description
    assert "organization" in desc.lower(), (
        "AlpiKnowledge.description must mention organizations so the agent knows to ask"
    )
    assert "organization" in PROMPT_RULE.lower(), (
        "PROMPT_RULE must mention organizations so the system prompt triggers the tool"
    )


def test_topics_and_topic_summaries_are_symmetric():
    from alpi.knowledge import TOPICS
    from alpi.tools.knowledge import _TOPIC_SUMMARIES

    only_in_topics = set(TOPICS) - set(_TOPIC_SUMMARIES)
    only_in_summaries = set(_TOPIC_SUMMARIES) - set(TOPICS)
    assert not only_in_topics and not only_in_summaries, (
        "alpi.knowledge.TOPICS and alpi.tools.knowledge._TOPIC_SUMMARIES "
        "must enumerate exactly the same keys.\n"
        f"  TOPICS-only:   {sorted(only_in_topics)}\n"
        f"  summary-only:  {sorted(only_in_summaries)}"
    )
