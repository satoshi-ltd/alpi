"""``db`` — per-skill SQLite at ``<skill>/state/db.sqlite``; quotas enforced; no migration runner."""

from __future__ import annotations

import contextlib
import json
import re
import sqlite3
from pathlib import Path

from alpi.home import get_home
from alpi.tools.base import Tool, ToolResult


MAX_DB_BYTES = 50 * 1024 * 1024
MAX_ROWS_PER_QUERY = 10_000
SQLITE_BUSY_TIMEOUT_S = 5.0
_FETCH_BATCH = 500
_COMMENTS = re.compile(r"--[^\n]*|/\*.*?\*/", re.S)
_TRANSACTION_CONTROL = {sqlite3.SQLITE_TRANSACTION, sqlite3.SQLITE_SAVEPOINT}


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


def _statements(sql: str) -> list[str]:
    out: list[str] = []
    start = 0
    for i, ch in enumerate(sql):
        # complete_statement knows string literals and trigger bodies, so only a real terminator splits.
        if ch == ";" and sqlite3.complete_statement(sql[start:i + 1]):
            out.append(sql[start:i + 1])
            start = i + 1
    out.append(sql[start:])
    return [stmt.strip() for stmt in out if _COMMENTS.sub("", stmt).strip(" \t\r\n;")]


class _Guard:
    """SQLite authorizer: judges what the engine parsed, so no spelling of the SQL gets around it."""

    def __init__(self) -> None:
        self.in_script = False
        self.denied: int | None = None

    def __call__(self, action: int, target: str | None, *_rest) -> int:
        # Only VACUUM's anonymous scratch database ("") passes; None means a parameter or expression whose file is unknown here.
        if (action == sqlite3.SQLITE_ATTACH and target != "") or (self.in_script and action in _TRANSACTION_CONTROL):
            self.denied = action
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK


def _drain(cur: sqlite3.Cursor, rows: list) -> int:
    extra = 0
    while batch := cur.fetchmany(_FETCH_BATCH):
        room = max(MAX_ROWS_PER_QUERY - len(rows), 0)
        rows.extend(batch[:room])
        extra += len(batch) - min(room, len(batch))
    return extra


def _returned(rows: list, extra: int) -> str:
    if not rows:
        return ""
    note = f" ({extra} more not shown)" if extra else ""
    return f"\nreturned: {json.dumps([dict(r) for r in rows], default=str)}{note}"


def _exec_script(conn: sqlite3.Connection, statements: list[str], guard: _Guard) -> ToolResult:
    conn.isolation_level = None
    conn.execute("BEGIN")
    guard.in_script = True
    affected, rows, extra = 0, [], 0
    # A failure leaves the transaction open; the caller closes the connection, which discards it.
    for n, stmt in enumerate(statements, start=1):
        try:
            cur = conn.execute(stmt)
            if cur.description:
                extra += _drain(cur, rows)
        except sqlite3.Error as e:
            if guard.denied in _TRANSACTION_CONTROL:
                raise sqlite3.Error(
                    f"statement {n} of {len(statements)} is transaction control, so none of them "
                    "was applied: exec already runs the script in one transaction — drop the "
                    "BEGIN / COMMIT / ROLLBACK / SAVEPOINT / RELEASE statements and send the rest",
                ) from e
            raise sqlite3.Error(
                f"statement {n} of {len(statements)} failed, so none of them was applied: {e}",
            ) from e
        affected += max(cur.rowcount, 0)
    guard.in_script = False
    conn.execute("COMMIT")
    out = f"statements: {len(statements)}, rows affected: {affected}"
    return ToolResult(ok=True, output=out + _returned(rows, extra))


class Db(Tool):
    name = "db"
    description = (
        "Per-skill SQLite database under the skill's ``state/`` "
        "directory. Two actions:\n"
        "\n"
        "  query — SELECT. Returns rows as JSON list of dicts.\n"
        "  exec  — INSERT / UPDATE / DELETE / CREATE / DROP / etc. "
        "Returns rows affected, plus any rows a RETURNING clause produced. "
        "Without params it also takes several statements separated by "
        "``;`` and runs them in one transaction (all or none); with params "
        "it takes exactly one statement.\n"
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
                "items": {"anyOf": [{"type": "string"}, {"type": "number"}, {"type": "boolean"}, {"type": "null"}]},
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
        statements = _statements(sql) if action == "exec" else []
        if len(statements) > 1 and param_tuple:
            return ToolResult(
                ok=False, output="",
                error=(
                    f"exec with params runs exactly one statement, and this sql has "
                    f"{len(statements)}. Send each statement in its own exec call with "
                    "the params it uses, or drop params to run them all as one script."
                ),
            )
        guard = _Guard()
        try:
            with contextlib.closing(
                sqlite3.connect(str(path), timeout=SQLITE_BUSY_TIMEOUT_S),
            ) as conn:
                conn.row_factory = sqlite3.Row
                conn.set_authorizer(guard)
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
                if len(statements) > 1:
                    return _exec_script(conn, statements, guard)
                cur = conn.execute(statements[0] if statements else sql, param_tuple)
                rows: list = []
                # A RETURNING or SELECT cursor left unread holds the statement open, and commit then fails.
                extra = _drain(cur, rows) if cur.description else 0
                conn.commit()
                out = f"rows affected: {cur.rowcount}"
                return ToolResult(ok=True, output=out + _returned(rows, extra))
        except sqlite3.Error as e:
            if guard.denied == sqlite3.SQLITE_ATTACH:
                return ToolResult(
                    ok=False, output="",
                    error=(
                        "db works on this skill's own database only; attaching or writing another "
                        "database file (ATTACH '<file>', VACUUM INTO '<file>') is not allowed"
                    ),
                )
            if isinstance(e, sqlite3.OperationalError):
                return ToolResult(ok=False, output="", error=f"sqlite operational error: {e}")
            if isinstance(e, sqlite3.IntegrityError):
                return ToolResult(ok=False, output="", error=f"sqlite integrity error: {e}")
            return ToolResult(ok=False, output="", error=f"sqlite error: {e}")


TOOL = Db
