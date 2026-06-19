"""host.skills.list / host.skill.read / host.skill.file — the Skills Explorer surface."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from alpi.host import device_state as host_device_state
from alpi.host import handlers as host_handlers
from alpi.host import server as host_server


def _write_skill(home: Path, category: str, name: str, frontmatter: dict, body: str = "", files: dict | None = None) -> Path:
    d = home / "skills" / category / name
    d.mkdir(parents=True)
    fm = "\n".join(f"{k}: {v}" for k, v in frontmatter.items())
    (d / "SKILL.md").write_text(f"---\n{fm}\n---\n\n{body}\n")
    for rel, content in (files or {}).items():
        fp = d / rel
        fp.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            fp.write_bytes(content)
        else:
            fp.write_text(content)
    return d


@pytest.fixture
def skills_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "h"
    home.mkdir()
    (home / ".env").write_text("ALPI_EXPLORER_PRESENT=1\n")
    _write_skill(
        home, "personal", "weekly",
        {
            "name": "weekly",
            "description": "Generate the Sunday weekly health report",
            "category": "personal",
            "version": "0.2.0",
            "origin": "user",
            "created_at": "2026-02-18",
            "tools": ["read_file", "write_file"],
            "keywords": ["weekly", "report"],
        },
        body="# Weekly health report\n\nEvery Sunday at 19:00.",
        files={"references/report-template.md": "# template"},
    )
    (home / "skills" / "personal" / "weekly" / "state").mkdir()
    _write_skill(
        home, "personal", "whoop",
        {
            "name": "whoop",
            "description": "Sync nightly WHOOP recovery, strain, and sleep numbers",
            "category": "personal",
            "version": "0.1.0",
            "origin": "agent",
            "created_at": "2026-04-20",
            "requires_env": ["ALPI_EXPLORER_PRESENT", "ALPI_EXPLORER_ABSENT"],
            "tools": ["read_file", "write_file", "terminal"],
            "keywords": ["whoop", "recovery"],
        },
        body="# WHOOP sync\n\nOAuth-token based.",
        files={
            "scripts/oauth.py": "import os\n\ndef token():\n    return os.environ['X']\n",
            "references/api-endpoints.md": "# endpoints",
            "secrets/token.json": '{"secret": "do-not-leak"}',
            "state/seen.sqlite": b"SQLite format 3\x00\x01\x02binary",
        },
    )
    monkeypatch.setattr(host_handlers, "_resolve_home", lambda profile: home)
    monkeypatch.setattr(host_device_state.home_mod, "_ROOT", home)
    return home


async def _call(home: Path, method: str, params: dict) -> dict:
    srv = host_server.Server(home=home)
    host_device_state.register(srv)
    return await srv._dispatch({"id": "r", "method": method, "params": params})


@pytest.mark.asyncio
async def test_skills_list_enriches_status_reason_size(skills_home: Path) -> None:
    resp = await _call(skills_home, "host.skills.list", {"profile": "default"})
    rows = {r["name"]: r for r in resp["result"]["skills"]}
    assert rows["weekly"]["status"] == "active"
    assert rows["weekly"]["reason"] == ""
    assert rows["weekly"]["size"] > 0
    assert rows["weekly"]["category"] == "personal"
    assert rows["whoop"]["status"] == "inactive"
    assert "ALPI_EXPLORER_ABSENT" in rows["whoop"]["reason"]
    assert rows["whoop"]["size"] > 0
    assert rows["whoop"]["keywords"] == ["whoop", "recovery"]


@pytest.mark.asyncio
async def test_skill_read_returns_structured_frontmatter_and_tree(skills_home: Path) -> None:
    resp = await _call(
        skills_home, "host.skill.read",
        {"profile": "default", "name": "whoop", "category": "personal"},
    )
    skill = resp["result"]["skill"]
    assert skill["status"] == "inactive"
    assert "ALPI_EXPLORER_ABSENT" in skill["reason"]
    assert skill["version"] == "0.1.0"
    assert skill["origin"] == "agent"
    assert skill["created_at"] == "2026-04-20"
    assert skill["tools"] == ["read_file", "write_file", "terminal"]
    assert skill["keywords"] == ["whoop", "recovery"]
    assert "WHOOP sync" in skill["body"]

    reqs = {r["name"]: r["resolved"] for r in skill["requires"]}
    assert reqs["ALPI_EXPLORER_PRESENT"] is True
    assert reqs["ALPI_EXPLORER_ABSENT"] is False

    tree = {n["name"]: n for n in skill["tree"]}
    assert tree["SKILL.md"]["ftype"] == "skill"
    assert tree["scripts"]["children"][0]["name"] == "oauth.py"
    assert tree["scripts"]["children"][0]["ftype"] == "py"
    secrets = tree["secrets"]
    assert secrets["locked"] is True
    assert secrets["count"] == 1
    assert "children" not in secrets
    assert "token.json" not in json.dumps(skill["tree"])


@pytest.mark.asyncio
async def test_skill_file_reads_text_script(skills_home: Path) -> None:
    resp = await _call(
        skills_home, "host.skill.file",
        {"profile": "default", "name": "whoop", "category": "personal", "path": "scripts/oauth.py"},
    )
    f = resp["result"]["file"]
    assert f["binary"] is False
    assert "def token" in f["text"]
    assert f["ftype"] == "py"


@pytest.mark.asyncio
async def test_skill_read_rejects_path_chars_in_name(skills_home: Path) -> None:
    for bad in ["..", "foo/bar", "..\\evil", "a/../b", "x\\y", ".hidden"]:
        resp = await _call(skills_home, "host.skill.read",
                           {"profile": "default", "name": bad, "category": "personal"})
        assert "result" not in resp
        assert resp["error"]["code"] == -32602
    resp = await _call(skills_home, "host.skill.read",
                       {"profile": "default", "name": "whoop", "category": "..\\evil"})
    assert resp["error"]["code"] == -32602


@pytest.mark.asyncio
async def test_skill_file_refuses_secrets(skills_home: Path) -> None:
    resp = await _call(
        skills_home, "host.skill.file",
        {"profile": "default", "name": "whoop", "category": "personal", "path": "secrets/token.json"},
    )
    assert "result" not in resp
    assert resp["error"]["code"] == -32603


@pytest.mark.asyncio
async def test_symlinked_skill_md_is_refused_and_unlisted(skills_home: Path, tmp_path: Path) -> None:
    secret = tmp_path / "leak.txt"
    secret.write_text("TOP-SECRET")
    evil = skills_home / "skills" / "personal" / "evil"
    evil.mkdir()
    try:
        (evil / "SKILL.md").symlink_to(secret)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable on this platform")
    resp = await _call(skills_home, "host.skill.read",
                       {"profile": "default", "name": "evil", "category": "personal"})
    assert "result" not in resp
    listed = await _call(skills_home, "host.skills.list", {"profile": "default", "include_body": True})
    assert "evil" not in [r["name"] for r in listed["result"]["skills"]]
    assert "TOP-SECRET" not in json.dumps(listed["result"])


@pytest.mark.asyncio
async def test_symlinked_skill_dir_is_refused(skills_home: Path, tmp_path: Path) -> None:
    real = tmp_path / "elsewhere"
    real.mkdir()
    (real / "SKILL.md").write_text("---\nname: leak\n---\n\nLEAK-BODY")
    link = skills_home / "skills" / "personal" / "linkdir"
    try:
        link.symlink_to(real)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable on this platform")
    resp = await _call(skills_home, "host.skill.read",
                       {"profile": "default", "name": "linkdir", "category": "personal"})
    assert "result" not in resp
    listed = await _call(skills_home, "host.skills.list", {"profile": "default", "include_body": True})
    assert "linkdir" not in [r["name"] for r in listed["result"]["skills"]]
    assert "LEAK-BODY" not in json.dumps(listed["result"])


@pytest.mark.asyncio
async def test_symlinked_skills_root_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "h"
    home.mkdir()
    (home / ".env").write_text("")
    outside = tmp_path / "outside"
    (outside / "personal" / "leak").mkdir(parents=True)
    (outside / "personal" / "leak" / "SKILL.md").write_text(
        "---\nname: leak\ncategory: personal\n---\n\nSECRET-BODY",
    )
    try:
        (home / "skills").symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable on this platform")
    monkeypatch.setattr(host_handlers, "_resolve_home", lambda profile: home)
    monkeypatch.setattr(host_device_state.home_mod, "_ROOT", home)

    listed = await _call(home, "host.skills.list", {"profile": "default", "include_body": True})
    assert listed["result"]["skills"] == []
    assert "SECRET-BODY" not in json.dumps(listed["result"])
    resp = await _call(home, "host.skill.read", {"profile": "default", "name": "leak", "category": "personal"})
    assert "result" not in resp


@pytest.mark.asyncio
async def test_skill_file_flags_binary_state(skills_home: Path) -> None:
    resp = await _call(
        skills_home, "host.skill.file",
        {"profile": "default", "name": "whoop", "category": "personal", "path": "state/seen.sqlite"},
    )
    f = resp["result"]["file"]
    assert f["binary"] is True
    assert "text" not in f
