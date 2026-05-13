from __future__ import annotations

import ast
import json
from pathlib import Path


def lint_content(path: Path | str, content: str) -> str | None:
    # Returns None if the content parses for the file's suffix, or no
    # linter applies. Returns a one-line error otherwise. Used by
    # write_file / edit_file to refuse syntactically broken writes
    # before they hit disk and break downstream consumers.
    suffix = Path(path).suffix.lower()

    if suffix == ".py":
        try:
            ast.parse(content)
        except SyntaxError as e:
            return f"Python syntax error at line {e.lineno}: {e.msg}"
        return None

    if suffix == ".json":
        try:
            json.loads(content)
        except json.JSONDecodeError as e:
            return f"JSON parse error at line {e.lineno} col {e.colno}: {e.msg}"
        return None

    if suffix in (".yaml", ".yml"):
        try:
            import yaml
        except ImportError:
            return None
        try:
            yaml.safe_load(content)
        except yaml.YAMLError as e:
            mark = getattr(e, "problem_mark", None)
            loc = f" at line {mark.line + 1}" if mark else ""
            return f"YAML parse error{loc}: {getattr(e, 'problem', e)}"
        return None

    if suffix == ".toml":
        # tomllib is stdlib in 3.11+; fall back to tomli if installed.
        try:
            import tomllib
        except ImportError:
            try:
                import tomli as tomllib  # type: ignore
            except ImportError:
                return None
        try:
            tomllib.loads(content)
        except tomllib.TOMLDecodeError as e:
            return f"TOML parse error: {e}"
        return None

    return None
