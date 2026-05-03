"""LLM-in-loop tests for the skill surface."""

from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.llm


def _frontmatter(md: str) -> dict[str, str]:
    if not md.startswith("---"):
        return {}
    _, raw, _ = md.split("---", 2)
    out: dict[str, str] = {}
    for line in raw.strip().splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip()
    return out


def test_skill_create_lands_with_english_body_and_db_tool(llm_engine) -> None:
    _engine, home, trace, run = llm_engine()
    run(
        "Crea un skill para trackear mis workouts. Cada entry: tipo, "
        "minutos, fecha. Quiero ver los últimos 7 días."
    )

    creates = [
        e for e in trace.tool_calls("skill")
        if e.args.get("action") == "create"
    ]
    assert creates, "agent did not call skill(action='create')"
    name = creates[0].args.get("name") or ""
    assert name, "skill create call missing 'name' arg"

    md_files = list((home / "skills").rglob("SKILL.md"))
    md_files = [m for m in md_files if name in m.parts]
    assert md_files, f"SKILL.md not on disk for {name!r}"
    text = md_files[0].read_text()
    meta = _frontmatter(text)

    body = text.split("---", 2)[2].lower()
    assert "minutos" not in body and "fecha" not in body, (
        "body has Spanish field names - English persistence rule failed"
    )

    declared_tools = meta.get("tools", "").lower()
    body_mentions_db = (
        "sqlite" in body or "db(action" in body or "db tool" in body
    )
    assert "db" in declared_tools or body_mentions_db, (
        f"skill never references db tool; tools={declared_tools!r}, "
        f"body excerpt:\n{text[:500]}"
    )


def test_skill_set_meta_used_to_fix_frontmatter(llm_engine) -> None:
    _engine, home, trace, run = llm_engine()

    skill_dir = home / "skills" / "software" / "fix-target"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: fix-target\n"
        "description: Calls a service that needs SERVICE_TOKEN\n"
        "category: software\n"
        "version: 0.1.0\n"
        "origin: agent\n"
        "requires_env: []\n"
        "tools: ['terminal']\n"
        "keywords: []\n"
        "created_at: 2026-05-03\n"
        "---\n"
        "## When to use\nFor service integrations.\n"
    )

    run(
        "El skill `fix-target` necesita SERVICE_TOKEN como env var. "
        "Arregla el frontmatter para declararlo correctamente."
    )

    set_meta_calls = [
        e for e in trace.tool_calls("skill")
        if e.args.get("action") == "set_meta"
    ]
    edit_calls = [
        e for e in trace.tool_calls("skill")
        if e.args.get("action") == "edit"
    ]
    assert set_meta_calls, "agent did not use set_meta to fix frontmatter"
    assert not edit_calls, (
        "agent used edit (would corrupt the body) instead of set_meta"
    )

    md = (skill_dir / "SKILL.md").read_text()
    assert "requires_env: ['SERVICE_TOKEN']" in md or \
           '"SERVICE_TOKEN"' in md, (
               f"requires_env not updated correctly; SKILL.md has:\n{md}"
           )
    assert "## When to use\nFor service integrations.\n" in md
    assert md.count("\n---\n") == 1


def test_inactive_skill_hidden_from_index(llm_engine) -> None:
    _engine, home, _trace, _run = llm_engine()
    skill_dir = home / "skills" / "software" / "needs-secret"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: needs-secret\n"
        "description: Hits an API requiring SECRET_TOKEN\n"
        "category: software\n"
        "requires_env: ['SECRET_TOKEN']\n"
        "tools: ['terminal']\n"
        "keywords: ['api', 'secret-fetch']\n"
        "---\n"
        "## When to use\nWhenever the user asks for the secret API.\n"
    )

    from alpi.tools.skill import skills_index_block
    assert "needs-secret" not in skills_index_block(home)


def test_db_tool_used_for_stateful_recipe(llm_engine) -> None:
    _engine, home, trace, run = llm_engine()
    skill_dir = home / "skills" / "personal" / "workout-tracker"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: workout-tracker\n"
        "description: Track workouts in SQLite\n"
        "category: personal\n"
        "tools: ['db']\n"
        "keywords: ['workout', 'cardio', 'training']\n"
        "---\n"
        "# Workout Tracker\n\n"
        "Use the `db` tool against `state/db.sqlite` with this schema:\n\n"
        "```sql\n"
        "CREATE TABLE IF NOT EXISTS workouts (\n"
        "  id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
        "  kind TEXT, mins INTEGER, day TEXT\n"
        ");\n"
        "```\n\n"
        "On `add`: INSERT a row. On `last7`: SELECT WHERE day in last 7 days.\n"
    )

    run("Apunta este workout: cardio 35 min hoy")

    db_calls = trace.tool_calls("db")
    assert db_calls, "agent did not use the db tool to persist the workout"
    db_file = skill_dir / "state" / "db.sqlite"
    assert db_file.exists(), "db.sqlite was not created"
    import sqlite3
    rows = sqlite3.connect(str(db_file)).execute(
        "SELECT kind, mins FROM workouts"
    ).fetchall()
    assert rows, "no rows in workouts table"
    kinds = {r[0].lower() for r in rows}
    assert any("cardio" in k for k in kinds), f"unexpected rows: {rows}"


def test_dont_over_skill_for_trivial_question(llm_engine) -> None:
    _engine, _home, trace, run = llm_engine()
    run("¿Cuál es la capital de Francia?")

    creates = [
        e for e in trace.tool_calls("skill")
        if e.args.get("action") == "create"
    ]
    assert not creates, (
        "agent created a skill for a trivial fact lookup - "
        "skills are for procedures asked twice, not single answers"
    )
