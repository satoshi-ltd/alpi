"""``db`` tool — per-skill SQLite without scripts.

Surface tested: query / exec, parameterised SQL, scope isolation
between skills, quota enforcement, error paths (unknown skill,
malformed SQL).
"""

from __future__ import annotations

import json
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


def test_db_does_not_leak_file_descriptors_across_many_calls(
    isolated_home: Path, whoop_skill: str,
) -> None:
    """sqlite3.Connection's context manager only commits/rollbacks — it does
    NOT close. Pre-fix, this test leaked one FD per call and would blow past
    the soft RLIMIT_NOFILE in a tool-heavy turn (ledger.json.tmp EMFILE)."""
    import resource

    db = Db()
    db.run(action="exec", skill=whoop_skill, sql="CREATE TABLE leak (n INTEGER)")
    soft, _ = resource.getrlimit(resource.RLIMIT_NOFILE)

    # Drop the soft limit to something the test can actually exhaust without
    # touching the rest of the suite (raised back in finally).
    test_limit = 96
    try:
        resource.setrlimit(resource.RLIMIT_NOFILE, (test_limit, _))
        for i in range(test_limit * 2):
            r = db.run(
                action="exec", skill=whoop_skill,
                sql="INSERT INTO leak VALUES (?)", params=[i],
            )
            assert r.ok, f"call {i} failed: {r.error}"
    finally:
        resource.setrlimit(resource.RLIMIT_NOFILE, (soft, _))


def _exec(skill: str, sql: str, params: list | None = None):
    return Db().run(action="exec", skill=skill, sql=sql, params=params)


def _query(skill: str, sql: str) -> list[dict]:
    r = Db().run(action="query", skill=skill, sql=sql)
    assert r.ok, r.error
    return json.loads(r.output)


def _tables(skill: str) -> set[str]:
    return {row["name"] for row in _query(skill, "SELECT name FROM sqlite_master WHERE type = 'table'")}


def test_two_create_tables_in_one_exec_both_land(isolated_home: Path, whoop_skill: str) -> None:
    r = _exec(whoop_skill, "CREATE TABLE IF NOT EXISTS runs (id INTEGER PRIMARY KEY, day TEXT);\n"
                           "CREATE TABLE IF NOT EXISTS audit (id INTEGER PRIMARY KEY, what TEXT);")

    assert r.ok, r.error
    assert "statements: 2" in r.output
    assert {"runs", "audit"} <= _tables(whoop_skill)


def test_a_script_is_all_or_nothing(isolated_home: Path, whoop_skill: str) -> None:
    assert _exec(whoop_skill, "CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT NOT NULL)").ok

    r = _exec(whoop_skill, "INSERT INTO t (v) VALUES ('kept?'); INSERT INTO t (v) VALUES (NULL);")

    assert not r.ok
    assert "statement 2 of 2 failed, so none of them was applied" in r.error
    assert "NOT NULL" in r.error
    assert _query(whoop_skill, "SELECT * FROM t") == []


def test_a_script_counts_rows_across_statements(isolated_home: Path, whoop_skill: str) -> None:
    assert _exec(whoop_skill, "CREATE TABLE t (v TEXT)").ok

    r = _exec(whoop_skill, "INSERT INTO t VALUES ('a'); INSERT INTO t VALUES ('b'), ('c'); DELETE FROM t WHERE v = 'a';")

    assert r.ok, r.error
    assert r.output == "statements: 3, rows affected: 4"
    assert [row["v"] for row in _query(whoop_skill, "SELECT v FROM t ORDER BY v")] == ["b", "c"]


def test_semicolons_inside_literals_and_trigger_bodies_do_not_split(isolated_home: Path, whoop_skill: str) -> None:
    r = _exec(whoop_skill, """
        CREATE TABLE notes (id INTEGER PRIMARY KEY, body TEXT);
        CREATE TABLE log (msg TEXT);
        CREATE TRIGGER notes_log AFTER INSERT ON notes BEGIN
            INSERT INTO log VALUES ('added; ' || NEW.body);
        END;
        INSERT INTO notes (body) VALUES ('one; two -- not a comment');
    """)

    assert r.ok, r.error
    assert "statements: 4" in r.output
    assert _query(whoop_skill, "SELECT body FROM notes") == [{"body": "one; two -- not a comment"}]
    assert _query(whoop_skill, "SELECT msg FROM log") == [{"msg": "added; one; two -- not a comment"}]


def test_insert_returning_commits_and_returns_its_rows(isolated_home: Path, whoop_skill: str) -> None:
    assert _exec(whoop_skill, "CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)").ok

    r = _exec(whoop_skill, "INSERT INTO t (v) VALUES (?), (?) RETURNING id, v", ["a", "b"])

    assert r.ok, r.error
    assert r.output.splitlines()[0] == "rows affected: 2"
    assert json.loads(r.output.split("returned: ", 1)[1]) == [{"id": 1, "v": "a"}, {"id": 2, "v": "b"}]
    assert len(_query(whoop_skill, "SELECT * FROM t")) == 2


def test_a_script_returns_the_rows_its_returning_clauses_produced(isolated_home: Path, whoop_skill: str) -> None:
    r = _exec(whoop_skill, "CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT);"
                           "INSERT INTO t (v) VALUES ('a') RETURNING id;"
                           "INSERT INTO t (v) VALUES ('b') RETURNING id, v;")

    assert r.ok, r.error
    assert r.output.startswith("statements: 3, rows affected: 2")
    assert json.loads(r.output.split("returned: ", 1)[1]) == [{"id": 1}, {"id": 2, "v": "b"}]


def test_a_select_sent_as_exec_returns_its_rows(isolated_home: Path, whoop_skill: str) -> None:
    r = _exec(whoop_skill, "SELECT 1 AS one, 'x' AS two")

    assert r.ok, r.error
    assert json.loads(r.output.split("returned: ", 1)[1]) == [{"one": 1, "two": "x"}]


def test_returned_rows_are_capped_but_every_row_is_written(
    isolated_home: Path, whoop_skill: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("alpi.tools.db.MAX_ROWS_PER_QUERY", 2)
    assert _exec(whoop_skill, "CREATE TABLE t (id INTEGER PRIMARY KEY)").ok

    r = _exec(whoop_skill, "INSERT INTO t (id) VALUES (1), (2), (3), (4), (5) RETURNING id")

    assert r.ok, r.error
    assert "(3 more not shown)" in r.output
    assert _query(whoop_skill, "SELECT COUNT(*) AS n FROM t") == [{"n": 5}]


def test_params_with_several_statements_are_refused_with_the_fix(isolated_home: Path, whoop_skill: str) -> None:
    assert _exec(whoop_skill, "CREATE TABLE t (v TEXT)").ok

    r = _exec(whoop_skill, "INSERT INTO t VALUES (?); INSERT INTO t VALUES (?);", ["a", "b"])

    assert not r.ok
    assert "exactly one statement, and this sql has 2" in r.error
    assert "its own exec call" in r.error
    assert _query(whoop_skill, "SELECT * FROM t") == []


@pytest.mark.parametrize("sql", [
    "INSERT INTO t VALUES (?);",
    "INSERT INTO t VALUES (?); -- the audit row",
    "  INSERT INTO t VALUES (?) ;;  /* done */ ",
])
def test_one_statement_with_trailing_noise_still_takes_params(
    isolated_home: Path, whoop_skill: str, sql: str,
) -> None:
    assert _exec(whoop_skill, "CREATE TABLE t (v TEXT)").ok

    r = _exec(whoop_skill, sql, ["a"])

    assert r.ok, r.error
    assert _query(whoop_skill, "SELECT v FROM t") == [{"v": "a"}]


@pytest.mark.parametrize("control", [
    "BEGIN", "BEGIN TRANSACTION", "COMMIT", "END", "SAVEPOINT s", "RELEASE s", "ROLLBACK",
    "-- open it\nbegin", "\ufeffCOMMIT",
])
def test_a_script_with_its_own_transaction_control_is_refused(
    isolated_home: Path, whoop_skill: str, control: str,
) -> None:
    assert _exec(whoop_skill, "CREATE TABLE t (v TEXT)").ok

    r = _exec(whoop_skill, f"INSERT INTO t VALUES ('a'); {control}; INSERT INTO t VALUES ('b');")

    assert not r.ok
    assert "statement 2 of 3 is transaction control, so none of them was applied" in r.error
    assert _query(whoop_skill, "SELECT * FROM t") == []


def test_a_hidden_commit_cannot_split_the_script_and_leave_half_of_it(
    isolated_home: Path, whoop_skill: str,
) -> None:
    r = _exec(whoop_skill, "CREATE TABLE t (v TEXT); INSERT INTO t VALUES ('x'); \ufeffCOMMIT; THIS IS INVALID;")

    assert not r.ok
    assert "none of them was applied" in r.error
    assert "t" not in _tables(whoop_skill)


@pytest.fixture
def foreign_db(isolated_home: Path) -> Path:
    import sqlite3

    path = isolated_home / "foreign.sqlite"
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE secret (v TEXT)")
    conn.execute("INSERT INTO secret VALUES ('another database')")
    conn.commit()
    conn.close()
    return path


@pytest.mark.parametrize(("action", "sql"), [
    ("query", "ATTACH DATABASE '{db}' AS other"),
    ("exec", "ATTACH DATABASE '{db}' AS other"),
    ("exec", "ATTACH DATABASE '{db}' AS other; SELECT v FROM other.secret;"),
    ("exec", "ATTACH DATABASE ':memory:' AS other"),
])
def test_no_statement_reaches_another_database(
    isolated_home: Path, whoop_skill: str, foreign_db: Path, action: str, sql: str,
) -> None:
    r = Db().run(action=action, skill=whoop_skill, sql=sql.format(db=foreign_db))

    assert not r.ok
    assert "own database only" in r.error
    assert "another database" not in (r.output or "")


@pytest.mark.parametrize("computed", [
    "ATTACH DATABASE ('{dir}/' || 'foreign.sqlite') AS other; SELECT v FROM other.secret;",
    "ATTACH DATABASE replace('{db}', 'x', 'x') AS other",
    "ATTACH DATABASE '' || '{db}' AS other",
])
def test_an_attach_target_computed_at_run_time_is_refused(
    isolated_home: Path, whoop_skill: str, foreign_db: Path, computed: str,
) -> None:
    r = _exec(whoop_skill, computed.format(dir=foreign_db.parent, db=foreign_db))

    assert not r.ok
    assert "own database only" in r.error
    assert "another database" not in (r.output or "")


def test_an_attach_target_bound_as_a_parameter_is_refused(
    isolated_home: Path, whoop_skill: str, foreign_db: Path,
) -> None:
    r = _exec(whoop_skill, "ATTACH DATABASE ? AS other", [str(foreign_db)])

    assert not r.ok
    assert "own database only" in r.error


def test_vacuum_into_another_file_is_refused_and_writes_nothing(
    isolated_home: Path, whoop_skill: str,
) -> None:
    assert _exec(whoop_skill, "CREATE TABLE t (v TEXT)").ok
    copy = isolated_home / "copy.sqlite"

    r = _exec(whoop_skill, f"VACUUM INTO '{copy}'")

    assert not r.ok
    assert "own database only" in r.error
    assert not copy.exists()


@pytest.mark.parametrize("sql", ["VACUUM", "VACUUM main"])
def test_vacuum_still_compacts_the_skills_own_database(
    isolated_home: Path, whoop_skill: str, sql: str,
) -> None:
    db_file = isolated_home / "skills" / "personal" / "whoop-tracker" / "state" / "db.sqlite"
    assert _exec(whoop_skill, "CREATE TABLE t (v TEXT)").ok
    for _ in range(20):
        assert _exec(whoop_skill, "INSERT INTO t VALUES (?)", ["x" * 20_000]).ok
    assert _exec(whoop_skill, "DELETE FROM t").ok
    bloated = db_file.stat().st_size

    r = _exec(whoop_skill, sql)

    assert r.ok, r.error
    assert db_file.stat().st_size < bloated


def test_vacuum_in_a_script_reports_sqlites_reason_not_transaction_control(
    isolated_home: Path, whoop_skill: str,
) -> None:
    r = _exec(whoop_skill, "CREATE TABLE t (v TEXT); VACUUM;")

    assert not r.ok
    assert "cannot VACUUM from within a transaction" in r.error
    assert "is transaction control" not in r.error
    assert "t" not in _tables(whoop_skill)


def test_an_anonymous_scratch_database_is_not_another_file(isolated_home: Path, whoop_skill: str) -> None:
    r = _exec(whoop_skill, "ATTACH DATABASE '' AS scratch")

    assert r.ok, r.error


def test_a_huge_result_is_never_held_in_memory(
    isolated_home: Path, whoop_skill: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import tracemalloc

    monkeypatch.setattr("alpi.tools.db.MAX_ROWS_PER_QUERY", 10)
    sql = ("WITH RECURSIVE n(i) AS (SELECT 1 UNION ALL SELECT i + 1 FROM n WHERE i < 200000) "
           "SELECT i, hex(zeroblob(500)) AS pad FROM n")
    tracemalloc.start()
    try:
        r = _exec(whoop_skill, sql)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    assert r.ok, r.error
    assert "(199990 more not shown)" in r.output
    assert len(json.loads(r.output.split("returned: ", 1)[1].split(" (", 1)[0])) == 10
    assert peak < 20 * 1024 * 1024, f"peak {peak / 1e6:.1f} MB — the cursor was materialised"


def test_a_single_pragma_still_runs_outside_a_transaction(isolated_home: Path, whoop_skill: str) -> None:
    r = _exec(whoop_skill, "PRAGMA journal_mode = WAL")

    assert r.ok, r.error
    assert json.loads(r.output.split("returned: ", 1)[1]) == [{"journal_mode": "wal"}]


def test_a_script_keeps_the_per_skill_scope_and_quota(
    isolated_home: Path, whoop_skill: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    Skill().run(action="create", name="other-skill", category="personal",
                description="Sibling", body="## When to use\nNever.\n")
    assert _exec(whoop_skill, "CREATE TABLE a (x); CREATE TABLE b (y);").ok
    assert "a" not in _tables("other-skill")

    monkeypatch.setattr("alpi.tools.db.MAX_DB_BYTES", 10)
    r = _exec(whoop_skill, "CREATE TABLE c (x); CREATE TABLE d (y);")
    assert not r.ok
    assert "quota" in r.error
