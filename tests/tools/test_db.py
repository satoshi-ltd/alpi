"""``db`` tool — per-skill SQLite without scripts.

Surface tested: query / exec, parameterised SQL, scope isolation
between skills, quota enforcement, error paths (unknown skill,
bundled skill, malformed SQL).
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from alpi.tools.db import (
    MAX_DB_BYTES,
    MAX_ROWS_PER_QUERY,
    Db,
)
from alpi.tools.skill import Skill


@pytest.fixture
def isolated_home(tmp_home_no_env: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("ALPI_HOME", str(tmp_home_no_env))
    return tmp_home_no_env


@pytest.fixture
def whoop_skill(isolated_home: Path) -> str:
    """Create a real skill so the db tool can resolve it."""
    r = Skill().run(
        action="create",
        name="whoop-tracker",
        category="personal",
        description="Track Whoop workouts",
        body="## When to use\nFor workout tracking.\n",
    )
    assert r.ok, r.error
    return "whoop-tracker"


def test_exec_creates_table_then_query_returns_rows(
    isolated_home: Path, whoop_skill: str,
) -> None:
    db = Db()
    r = db.run(
        action="exec",
        skill=whoop_skill,
        sql="CREATE TABLE workouts (id INTEGER PRIMARY KEY, kind TEXT, mins INTEGER)",
    )
    assert r.ok, r.error

    r = db.run(
        action="exec",
        skill=whoop_skill,
        sql="INSERT INTO workouts (kind, mins) VALUES (?, ?)",
        params=["cardio", 35],
    )
    assert r.ok, r.error
    assert "1" in r.output

    r = db.run(
        action="query",
        skill=whoop_skill,
        sql="SELECT kind, mins FROM workouts ORDER BY id",
    )
    assert r.ok, r.error
    rows = json.loads(r.output)
    assert rows == [{"kind": "cardio", "mins": 35}]


def test_create_table_if_not_exists_is_idempotent(
    isolated_home: Path, whoop_skill: str,
) -> None:
    db = Db()
    sql = "CREATE TABLE IF NOT EXISTS t (id INTEGER PRIMARY KEY, x TEXT)"
    for _ in range(3):
        r = db.run(action="exec", skill=whoop_skill, sql=sql)
        assert r.ok, r.error


def test_parameterised_sql_does_not_string_interpolate(
    isolated_home: Path, whoop_skill: str,
) -> None:
    db = Db()
    db.run(
        action="exec", skill=whoop_skill,
        sql="CREATE TABLE notes (id INTEGER PRIMARY KEY, body TEXT)",
    )
    # Single quotes + apostrophes in user data must not break the query.
    bad = "Robert'); DROP TABLE notes;--"
    r = db.run(
        action="exec", skill=whoop_skill,
        sql="INSERT INTO notes (body) VALUES (?)",
        params=[bad],
    )
    assert r.ok, r.error
    r = db.run(
        action="query", skill=whoop_skill,
        sql="SELECT body FROM notes",
    )
    rows = json.loads(r.output)
    assert rows == [{"body": bad}]


def test_scope_is_per_skill(isolated_home: Path, whoop_skill: str) -> None:
    Skill().run(
        action="create",
        name="other-skill",
        category="personal",
        description="Sibling that should not see whoop's data",
        body="## When to use\nNever.\n",
    )
    db = Db()
    db.run(
        action="exec", skill=whoop_skill,
        sql="CREATE TABLE x (n INTEGER)",
    )
    db.run(
        action="exec", skill=whoop_skill,
        sql="INSERT INTO x VALUES (?)", params=[42],
    )
    # Sibling has no table — should error, not see whoop's data.
    r = db.run(
        action="query", skill="other-skill",
        sql="SELECT * FROM x",
    )
    assert not r.ok
    assert "no such table" in r.error.lower()


def test_unknown_skill_rejected(isolated_home: Path) -> None:
    r = Db().run(
        action="query", skill="does-not-exist",
        sql="SELECT 1",
    )
    assert not r.ok
    assert "skill not found" in r.error


def test_bundled_skill_rejected(isolated_home: Path) -> None:
    r = Db().run(
        action="query", skill="@alpi/knowledge",
        sql="SELECT 1",
    )
    assert not r.ok
    assert "bundled" in r.error


def test_unknown_action_rejected(isolated_home: Path, whoop_skill: str) -> None:
    r = Db().run(action="vacuum", skill=whoop_skill, sql="SELECT 1")
    assert not r.ok
    assert "unknown action" in r.error


def test_empty_sql_rejected(isolated_home: Path, whoop_skill: str) -> None:
    r = Db().run(action="query", skill=whoop_skill, sql="")
    assert not r.ok
    assert "'sql' is required" in r.error


def test_malformed_sql_returns_error_not_crash(
    isolated_home: Path, whoop_skill: str,
) -> None:
    r = Db().run(
        action="exec", skill=whoop_skill,
        sql="THIS IS NOT VALID SQL",
    )
    assert not r.ok
    assert "sqlite" in r.error.lower()


def test_query_row_cap_blocks_runaway_results(
    isolated_home: Path, whoop_skill: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Lower the cap for the test so we don't insert 10k rows.
    monkeypatch.setattr("alpi.tools.db.MAX_ROWS_PER_QUERY", 5)
    db = Db()
    db.run(
        action="exec", skill=whoop_skill,
        sql="CREATE TABLE big (n INTEGER)",
    )
    for n in range(10):
        db.run(
            action="exec", skill=whoop_skill,
            sql="INSERT INTO big VALUES (?)", params=[n],
        )
    r = db.run(
        action="query", skill=whoop_skill,
        sql="SELECT * FROM big",
    )
    assert not r.ok
    assert "more than 5" in r.error


def test_quota_blocks_when_db_too_large(
    isolated_home: Path, whoop_skill: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Create a DB by writing once, then squeeze the quota below its size.
    db = Db()
    db.run(action="exec", skill=whoop_skill, sql="CREATE TABLE t (x TEXT)")
    db.run(
        action="exec", skill=whoop_skill,
        sql="INSERT INTO t VALUES (?)", params=["x" * 100],
    )
    # Squeeze the quota.
    monkeypatch.setattr("alpi.tools.db.MAX_DB_BYTES", 10)
    r = db.run(action="query", skill=whoop_skill, sql="SELECT * FROM t")
    assert not r.ok
    assert "quota" in r.error


def test_db_file_lands_under_skill_state(
    isolated_home: Path, whoop_skill: str,
) -> None:
    Db().run(
        action="exec", skill=whoop_skill,
        sql="CREATE TABLE foo (x INTEGER)",
    )
    expected = (
        isolated_home / "skills" / "personal" / "whoop-tracker"
        / "state" / "db.sqlite"
    )
    assert expected.exists()
    assert expected.stat().st_size > 0


def test_constants_are_documented_values() -> None:
    # Guard against accidental relax of quotas in a refactor.
    assert MAX_DB_BYTES == 50 * 1024 * 1024
    assert MAX_ROWS_PER_QUERY == 10_000
