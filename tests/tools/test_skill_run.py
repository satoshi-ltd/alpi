"""Tests for ``skill(action="run", name=...)``.

Why this exists: before this action, the only way for the agent to
"execute" a skill was to view SKILL.md and improvise terminal calls.
That broke reproducibility — chat output drifted from scheduled
output. ``run`` collapses both paths into one well-defined call.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from alpi.tools.skill import Skill


@pytest.fixture
def isolated_home(tmp_home_no_env: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("ALPI_HOME", str(tmp_home_no_env))
    return tmp_home_no_env


def _create(**kw) -> object:
    kw.setdefault("category", "personal")
    kw.setdefault("description", "test skill")
    return Skill().run(action="create", **kw)


def test_run_unknown_skill_fails(isolated_home: Path) -> None:
    r = Skill().run(action="run", name="does-not-exist")
    assert not r.ok
    assert "not found" in r.error.lower()


def test_run_requires_name(isolated_home: Path) -> None:
    r = Skill().run(action="run")
    assert not r.ok
    assert "name" in r.error.lower()


def test_run_without_script_returns_skill_md(isolated_home: Path) -> None:
    """No scripts/run.py → return SKILL.md prefixed with a directive."""
    body = "Step 1: do thing.\nStep 2: do other thing."
    _create(name="prose-only", body=body)
    r = Skill().run(action="run", name="prose-only")
    assert r.ok
    assert "no scripts/run.py" in r.output.lower()
    assert "Step 1: do thing" in r.output


def test_run_executes_script_and_returns_stdout(isolated_home: Path) -> None:
    """scripts/run.py exists → spawn it, return its stdout."""
    _create(name="echoer", body="prints a marker")
    Skill().run(
        action="add_file", name="echoer", subdir="scripts", filename="run.py",
        content="print('marker-out')\n",
    )
    r = Skill().run(action="run", name="echoer")
    assert r.ok, r.error
    assert "marker-out" in r.output


def test_run_propagates_nonzero_exit_as_failure(isolated_home: Path) -> None:
    _create(name="failer", body="exits 1")
    Skill().run(
        action="add_file", name="failer", subdir="scripts", filename="run.py",
        content="import sys; print('partial'); sys.exit(2)\n",
    )
    r = Skill().run(action="run", name="failer")
    assert not r.ok
    assert "rc=2" in r.error
    assert "partial" in r.output


def test_run_forwards_args(isolated_home: Path) -> None:
    _create(name="argprinter", body="echoes argv")
    Skill().run(
        action="add_file", name="argprinter", subdir="scripts", filename="run.py",
        content="import sys; print('|'.join(sys.argv[1:]))\n",
    )
    r = Skill().run(action="run", name="argprinter", args=["--foo", "bar"])
    assert r.ok
    assert "--foo|bar" in r.output


def test_run_blocks_when_required_env_missing(
    isolated_home: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Skills declaring ``requires_env`` should not spawn if the env is
    absent — same gate as the one used at system-prompt build time, so
    behaviour is consistent between "available to agent" and "actually
    runnable now"."""
    monkeypatch.delenv("ZZZ_TEST_KEY", raising=False)
    _create(name="needsenv", body="needs ZZZ_TEST_KEY",
            requires_env=["ZZZ_TEST_KEY"])
    Skill().run(
        action="add_file", name="needsenv", subdir="scripts", filename="run.py",
        content="print('should not run')\n",
    )
    r = Skill().run(action="run", name="needsenv")
    assert not r.ok
    assert "ZZZ_TEST_KEY" in r.error
    assert "should not run" not in r.output


def test_run_exposes_skill_dir_via_env(isolated_home: Path) -> None:
    """Scripts get ``ALPI_SKILL_DIR`` so they can resolve secrets/state
    without hardcoding the user's profile path."""
    _create(name="introspect", body="prints ALPI_SKILL_DIR")
    Skill().run(
        action="add_file", name="introspect", subdir="scripts", filename="run.py",
        content="import os; print(os.environ.get('ALPI_SKILL_DIR', 'MISSING'))\n",
    )
    r = Skill().run(action="run", name="introspect")
    assert r.ok
    assert "introspect" in r.output
    assert "MISSING" not in r.output


def test_run_blocks_scripts_that_import_tools_from_alpi(
    isolated_home: Path,
) -> None:
    _create(name="bad-mcp-script", body="tries to import a tool")
    Skill().run(
        action="add_file", name="bad-mcp-script", subdir="scripts",
        filename="run.py",
        content="from alpi import bitbucket_get_pull_requests\nprint('bad')\n",
    )

    r = Skill().run(action="run", name="bad-mcp-script")

    assert not r.ok
    assert "failed validation" in r.error
    assert "tools and MCP methods are not Python APIs" in r.output
    assert "bad" not in r.output


def test_run_validates_stdout_against_output_schema(isolated_home: Path) -> None:
    _create(
        name="json-ok",
        body="returns structured JSON",
        output_schema='{"type":"object","properties":{"ok":{"type":"boolean"}},"required":["ok"]}',
    )
    Skill().run(
        action="add_file", name="json-ok", subdir="scripts", filename="run.py",
        content="print('{\"ok\": true}')\n",
    )

    r = Skill().run(action="run", name="json-ok")

    assert r.ok, r.error
    assert '"ok": true' in r.output


def test_run_fails_when_output_schema_stdout_is_not_json(isolated_home: Path) -> None:
    _create(
        name="json-bad",
        body="returns invalid JSON",
        output_schema='{"type":"object","properties":{"ok":{"type":"boolean"}},"required":["ok"]}',
    )
    Skill().run(
        action="add_file", name="json-bad", subdir="scripts", filename="run.py",
        content="print('not-json')\n",
    )

    r = Skill().run(action="run", name="json-bad")

    assert not r.ok
    assert "declared output_schema" in r.error


def test_run_fails_when_output_schema_does_not_match(isolated_home: Path) -> None:
    _create(
        name="json-mismatch",
        body="returns the wrong shape",
        output_schema='{"type":"object","properties":{"ok":{"type":"boolean"}},"required":["ok"]}',
    )
    Skill().run(
        action="add_file", name="json-mismatch", subdir="scripts", filename="run.py",
        content="print('{\"ok\": \"yes\"}')\n",
    )

    r = Skill().run(action="run", name="json-mismatch")

    assert not r.ok
    assert "output_schema mismatch" in r.error
    assert "$.ok: expected boolean" in r.error


def test_test_runs_script_and_validates_output_schema(isolated_home: Path) -> None:
    _create(
        name="json-test",
        body="returns JSON",
        output_schema='{"type":"object","properties":{"count":{"type":"integer"}},"required":["count"]}',
    )
    Skill().run(
        action="add_file", name="json-test", subdir="scripts", filename="run.py",
        content="print('{\"count\": 3}')\n",
    )

    r = Skill().run(action="test", name="json-test")

    assert r.ok, r.error
    assert "[test ok]" in r.output
    assert "matches output_schema" in r.output


def test_test_rejects_prose_only_skills(isolated_home: Path) -> None:
    _create(name="prose-test", body="just prose")

    r = Skill().run(action="test", name="prose-test")

    assert not r.ok
    assert "only scripted skills support test" in r.error


def test_invoke_requires_scripted_skill(isolated_home: Path) -> None:
    _create(name="invoke-prose", body="just prose")

    r = Skill().run(action="invoke", name="invoke-prose")

    assert not r.ok
    assert "only scripted skills support invoke" in r.error


def test_invoke_requires_output_schema(isolated_home: Path) -> None:
    _create(name="invoke-no-schema", body="script but no schema")
    Skill().run(
        action="add_file", name="invoke-no-schema", subdir="scripts", filename="run.py",
        content="print('{\"ok\": true}')\n",
    )

    r = Skill().run(action="invoke", name="invoke-no-schema")

    assert not r.ok
    assert "invoke requires a structured contract" in r.error


def test_run_records_cost_usd_to_ledger(isolated_home: Path) -> None:
    # cost_usd in a skill's JSON stdout must reach the daily ledger.
    from alpi import ledger

    _create(
        name="paid-api",
        body="hits a paid API and reports cost",
        output_schema='{"type":"object","properties":{"out":{"type":"string"},"cost_usd":{"type":"number"}},"required":["out"]}',
    )
    Skill().run(
        action="add_file", name="paid-api", subdir="scripts", filename="run.py",
        content="print('{\"out\": \"/tmp/x.png\", \"cost_usd\": 0.04}')\n",
    )
    before = float(ledger.load(isolated_home).get("profile", {}).get("usd", 0.0))
    r = Skill().run(action="run", name="paid-api")
    assert r.ok, r.error
    after = float(ledger.load(isolated_home).get("profile", {}).get("usd", 0.0))
    assert round(after - before, 4) == 0.04
    assert "ledger" in r.output.lower()


def test_run_ignores_absent_cost(isolated_home: Path) -> None:
    from alpi import ledger

    _create(name="free-skill", body="reports no cost")
    Skill().run(
        action="add_file", name="free-skill", subdir="scripts", filename="run.py",
        content="print('{\"out\": \"/tmp/x.png\"}')\n",
    )
    before = float(ledger.load(isolated_home).get("profile", {}).get("usd", 0.0))
    r = Skill().run(action="run", name="free-skill")
    assert r.ok, r.error
    after = float(ledger.load(isolated_home).get("profile", {}).get("usd", 0.0))
    assert after == before
    assert "ledger" not in r.output.lower()


def test_invoke_returns_structured_json_for_scripted_skill(isolated_home: Path) -> None:
    _create(
        name="invoke-json",
        body="returns JSON",
        output_schema='{"type":"object","properties":{"items":{"type":"array","items":{"type":"integer"}}},"required":["items"]}',
    )
    Skill().run(
        action="add_file", name="invoke-json", subdir="scripts", filename="run.py",
        content="print('{\"items\": [1, 2, 3]}')\n",
    )

    r = Skill().run(action="invoke", name="invoke-json")

    assert r.ok, r.error
    assert r.output == '{"items": [1, 2, 3]}'
