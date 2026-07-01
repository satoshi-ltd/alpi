"""Correctness checks for skills — syntax, imports, OAuth races, doc drift."""

from __future__ import annotations

import ast
import importlib.util
import re
import sys
from pathlib import Path
from typing import Iterable

_STDLIB = set(sys.stdlib_module_names) | {"alpi"}
_PORT_IN_DOC = re.compile(r"localhost[:\s]+(\d{2,5})\b|127\.0\.0\.1[:\s]+(\d{2,5})\b")
_BIND_IN_CODE = re.compile(
    r"""(?:bind|listen|TCPServer|HTTPServer|run)\s*\(\s*\(?\s*["']?(?:localhost|127\.0\.0\.1|0\.0\.0\.0|)["']?\s*,\s*(\d{2,5})""",
)


def validate_skill(skill_dir: Path) -> list[str]:
    """Return a list of ``['✗ …', '⚠ …']`` findings. Empty list = clean."""
    findings: list[str] = []
    py_files = sorted(p for p in skill_dir.rglob("scripts/*.py") if _is_real_skill_file(p))
    findings.extend(_check_syntax(py_files, skill_dir))
    findings.extend(_check_imports(py_files, skill_dir))
    findings.extend(_check_alpi_tool_imports(py_files, skill_dir))
    findings.extend(_check_oauth_race(py_files, skill_dir))
    findings.extend(_check_port_coherence(py_files, skill_dir))
    return findings


def _rel(p: Path, root: Path) -> str:
    try:
        return str(p.relative_to(root))
    except ValueError:
        return p.name


def _is_real_skill_file(p: Path) -> bool:
    return not any(part == "__pycache__" or part.startswith("._") for part in p.parts)


def _check_syntax(files: Iterable[Path], root: Path) -> list[str]:
    out: list[str] = []
    for p in files:
        try:
            source = p.read_text(encoding="utf-8", errors="replace")
            compile(source, str(p), "exec", dont_inherit=True)
        except SyntaxError as e:
            detail = f"line {e.lineno}: {e.msg}" if e.lineno else e.msg
            out.append(f"✗ {_rel(p, root)}: SyntaxError: {detail}")
        except Exception as e:  # noqa: BLE001
            out.append(f"✗ {_rel(p, root)}: {type(e).__name__}: {e}")
    return out


def _check_imports(files: Iterable[Path], root: Path) -> list[str]:
    out: list[str] = []
    local_modules = {p.stem for p in root.rglob("*.py") if _is_real_skill_file(p)}
    for p in files:
        try:
            tree = ast.parse(p.read_text(encoding="utf-8", errors="replace"))
        except Exception:  # noqa: BLE001
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    continue
                names = [(node.module or "").split(".")[0]] if node.module else []
            else:
                continue
            for mod in names:
                if not mod or mod in _STDLIB or mod in local_modules:
                    continue
                if importlib.util.find_spec(mod) is None:
                    out.append(
                        f"✗ {_rel(p, root)} imports `{mod}` — not installed"
                    )
    return out


def _check_alpi_tool_imports(files: Iterable[Path], root: Path) -> list[str]:
    out: list[str] = []
    for p in files:
        try:
            tree = ast.parse(p.read_text(encoding="utf-8", errors="replace"))
        except Exception:  # noqa: BLE001
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or node.module != "alpi":
                continue
            bad = [
                alias.name for alias in node.names
                if alias.name not in {"__version__"}
            ]
            if bad:
                out.append(
                    f"✗ {_rel(p, root)} imports `{', '.join(bad)}` from alpi "
                    "— tools and MCP methods are not Python APIs"
                )
    return out


def _check_oauth_race(files: Iterable[Path], root: Path) -> list[str]:
    out: list[str] = []
    for p in files:
        try:
            source = p.read_text(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            continue
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        open_line: int | None = None
        serve_line: int | None = None
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                attr = _dotted(node.func)
                if attr == "webbrowser.open" and open_line is None:
                    open_line = node.lineno
                if attr in {
                    "serve_forever", "handle_request",
                    "httpd.serve_forever", "httpd.handle_request",
                    "server.serve_forever", "server.handle_request",
                } and serve_line is None:
                    serve_line = node.lineno
        if open_line and serve_line and open_line < serve_line:
            out.append(
                f"⚠ {_rel(p, root)}: webbrowser.open() at line {open_line} "
                f"runs before server at line {serve_line} (race)"
            )
    return out


def _dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Attribute):
        return f"{_dotted(node.value)}.{node.attr}".lstrip(".")
    if isinstance(node, ast.Name):
        return node.id
    return ""


def _check_port_coherence(files: Iterable[Path], root: Path) -> list[str]:
    out: list[str] = []
    skill_md = root / "SKILL.md"
    if not skill_md.exists():
        return out
    doc = skill_md.read_text(encoding="utf-8", errors="replace")
    doc_ports: set[str] = set()
    for m in _PORT_IN_DOC.finditer(doc):
        port = m.group(1) or m.group(2)
        if port:
            doc_ports.add(port)
    if not doc_ports:
        return out
    code_ports: dict[str, Path] = {}
    for p in files:
        try:
            src = p.read_text(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            continue
        for m in _BIND_IN_CODE.finditer(src):
            code_ports.setdefault(m.group(1), p)
    if code_ports and doc_ports and not (doc_ports & set(code_ports)):
        doc_list = ", ".join(sorted(doc_ports))
        code_list = ", ".join(
            f"{port} ({_rel(path, root)})"
            for port, path in sorted(code_ports.items())
        )
        out.append(
            f"⚠ SKILL.md mentions localhost port {doc_list} "
            f"but scripts bind {code_list}"
        )
    return out
