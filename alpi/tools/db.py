"""``db`` — per-skill SQLite at ``<skill>/state/db.sqlite``; quotas enforced; no migration runner."""

from __future__ import annotations

import contextlib
import json
import sqlite3
from pathlib import Path

from alpi.home import get_home
from alpi.tools.base import Tool, ToolResult


MAX_DB_BYTES = 50 * 1024 * 1024
MAX_ROWS_PER_QUERY = 10_000
SQLITE_BUSY_TIMEOUT_S = 5.0


def _resolve_db(skill_name: str) -> tuple[Path, str | None]:
    if not skill_name:
        return Path(), "'skill' is required"
    from alpi.tools.skill import _find_skill
    home = get_home()
    skill_dir = _find_skill(home, skill_name)
    if skill_dir is None:
        return Path(), f"skill not found: {skill_name}"
    state_dir = skill_dir / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir / "db.sqlite", None


def _check_quota(path: Path) -> str | None:
    if not path.exists():
        return None
    size = path.stat().st_size
    if size >= MAX_DB_BYTES:
        return (
            f"db.sqlite at {size:,} bytes exceeds the {MAX_DB_BYTES:,}-byte "
            "quota — prune rows or reset the skill state"
        )
    return None


class Db(Tool):
    name = "db"
    description = (
        "Per-skill SQLite database under the skill's ``state/`` "
        "directory. Two actions:\n"
        "\n"
        "  query — SELECT. Returns rows as JSON list of dicts.\n"
        "  exec  — INSERT / UPDATE / DELETE / CREATE / DROP / etc. "
        "Returns rows affected.\n"
        "\n"
        "Always pass ``skill=<name>`` so the runner resolves the right "
        "DB. Use parameterised SQL via ``params=[…]`` — never string-"
        "interpolate user data into the SQL.\n"
        "\n"
        "Tables: create them yourself with ``CREATE TABLE IF NOT EXISTS …`` "
        "the first time a skill writes. Idempotent — safe to run on every "
        "invocation.\n"
        "\n"
        "Quotas: 50 MB file, 10 000 rows max per query result, 5 s "
        "busy timeout. Scope is per-skill: one skill cannot touch "
        "another skill's DB.\n"
        "\n"
        "Wipe state via ``skill(action='reset_state', name=…)`` — "
        "removes ``state/`` including the SQLite file. Use when a "
        "schema change leaves the DB inconsistent."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["query", "exec"]},
            "skill": {
                "type": "string",
                "description": "Owning skill (kebab-case name).",
            },
            "sql": {
                "type": "string",
                "description": "SQL statement. Placeholders are ``?``.",
            },
            "params": {
                "type": "array",
                "items": {"type": ["string", "number", "boolean", "null"]},
                "description": "Positional parameters for the ``?`` placeholders. Default: [].",
                "default": [],
            },
        },
        "required": ["action", "skill", "sql"],
    }

    def run(
        self,
        action: str,
        skill: str = "",
        sql: str = "",
        params: list | None = None,
    ) -> ToolResult:
        if action not in {"query", "exec"}:
            return ToolResult(ok=False, output="", error=f"unknown action: {action}")
        if not sql or not sql.strip():
            return ToolResult(ok=False, output="", error="'sql' is required")

        path, err = _resolve_db(skill)
        if err:
            return ToolResult(ok=False, output="", error=err)
        quota_err = _check_quota(path)
        if quota_err:
            return ToolResult(ok=False, output="", error=quota_err)

        param_tuple = tuple(params or [])
        try:
            with contextlib.closing(
                sqlite3.connect(str(path), timeout=SQLITE_BUSY_TIMEOUT_S),
            ) as conn:
                conn.row_factory = sqlite3.Row
                if action == "query":
                    cur = conn.execute(sql, param_tuple)
                    rows = cur.fetchmany(MAX_ROWS_PER_QUERY + 1)
                    if len(rows) > MAX_ROWS_PER_QUERY:
                        return ToolResult(
                            ok=False, output="",
                            error=(
                                f"query returned more than {MAX_ROWS_PER_QUERY} "
                                "rows — tighten with WHERE / LIMIT"
                            ),
                        )
                    out = [dict(r) for r in rows]
                    return ToolResult(ok=True, output=json.dumps(out, default=str))
                # exec
                cur = conn.execute(sql, param_tuple)
                conn.commit()
                return ToolResult(ok=True, output=f"rows affected: {cur.rowcount}")
        except sqlite3.OperationalError as e:
            return ToolResult(ok=False, output="", error=f"sqlite operational error: {e}")
        except sqlite3.IntegrityError as e:
            return ToolResult(ok=False, output="", error=f"sqlite integrity error: {e}")
        except sqlite3.Error as e:
            return ToolResult(ok=False, output="", error=f"sqlite error: {e}")


TOOL = Db
