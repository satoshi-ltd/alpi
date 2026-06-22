import ast
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ALPI_DIR = REPO / "alpi"

PROFILES_MD = REPO / "docs" / "PROFILES.md"
PROFILES_REF = REPO / "alpi" / "knowledge" / "references" / "profiles.md"
OPS_MD = REPO / "docs" / "OPERATIONS.md"
OPS_REF = REPO / "alpi" / "knowledge" / "references" / "operations.md"


def _python_files() -> list[Path]:
    return [p for p in ALPI_DIR.rglob("*.py") if "__pycache__" not in p.parts]


def _extract_subsystem_logger_names() -> set[str]:
    names: set[str] = set()
    for py in _python_files():
        try:
            tree = ast.parse(py.read_text())
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            is_call = (
                (isinstance(func, ast.Attribute) and func.attr == "get_subsystem_logger")
                or (isinstance(func, ast.Name) and func.id == "get_subsystem_logger")
            )
            if not is_call or len(node.args) < 2:
                continue
            second = node.args[1]
            if isinstance(second, ast.Constant) and isinstance(second.value, str):
                names.add(second.value)
    return names


def _per_profile_logs_from_code() -> set[str]:
    return {f"{name}.log" for name in _extract_subsystem_logger_names()}


def _doc_per_profile_logs(text: str) -> set[str]:
    section = re.search(r"^\|\s*`logs/`\s*\|.+?\n", text, re.M | re.S)
    if not section:
        return set()
    row = section.group(0)
    return set(re.findall(r"`([a-z][a-z_-]*\.log)`", row))


def _doc_log_files_in_table(text: str) -> set[str]:
    return set(re.findall(r"`([a-z][a-z_-]*\.log)`", text))


_LEGACY_PER_PROFILE_LOG_CLAIMS = {"gateway.log", "schedule.log", "alp.log", "workgroup.log"}

_ROOT_ONLY_LOGS = {"service.log"}


def test_profiles_md_logs_row_matches_real_writers():
    code = _per_profile_logs_from_code()
    doc = _doc_per_profile_logs(PROFILES_MD.read_text())
    legacy_drift = doc & _LEGACY_PER_PROFILE_LOG_CLAIMS
    code_only = code - doc
    doc_only = (doc - code) - _ROOT_ONLY_LOGS
    assert not legacy_drift and not code_only and not doc_only, (
        "docs/PROFILES.md `logs/` row drifted from real subsystem loggers:\n"
        f"  legacy claims with no writer: {sorted(legacy_drift)}\n"
        f"  code-only (writer exists, not documented): {sorted(code_only)}\n"
        f"  doc-only (documented, no writer):          {sorted(doc_only)}"
    )


def test_profiles_reference_logs_row_matches_real_writers():
    code = _per_profile_logs_from_code()
    doc = _doc_per_profile_logs(PROFILES_REF.read_text())
    legacy_drift = doc & _LEGACY_PER_PROFILE_LOG_CLAIMS
    code_only = code - doc
    doc_only = (doc - code) - _ROOT_ONLY_LOGS
    assert not legacy_drift and not code_only and not doc_only, (
        "alpi/knowledge/references/profiles.md `logs/` row drifted from real loggers:\n"
        f"  legacy claims with no writer: {sorted(legacy_drift)}\n"
        f"  code-only: {sorted(code_only)}\n"
        f"  doc-only:  {sorted(doc_only)}"
    )


def test_operations_docs_do_not_promise_phantom_log_files():
    expected = _per_profile_logs_from_code() | _ROOT_ONLY_LOGS
    for doc_path, label in ((OPS_MD, "docs/OPERATIONS.md"),
                            (OPS_REF, "alpi/knowledge/references/operations.md")):
        text = doc_path.read_text()
        mentioned = _doc_log_files_in_table(text)
        phantom = mentioned - expected - {f"{n}.1" for n in expected}
        legacy = mentioned & _LEGACY_PER_PROFILE_LOG_CLAIMS
        assert not phantom and not legacy, (
            f"{label} mentions phantom or legacy log files:\n"
            f"  phantom (no writer in alpi/): {sorted(phantom)}\n"
            f"  legacy (gateway/schedule/alp/workgroup.log claimed as real): {sorted(legacy)}\n"
            f"  expected = code writers ∪ root-only: {sorted(expected)}"
        )
