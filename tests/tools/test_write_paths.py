from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from alpi import config
from alpi import tools as tools_mod
from alpi.tools import _policy


def _configure(home: Path, write_paths) -> Path:
    workspace = home / "ws"
    (workspace / "knowledge").mkdir(parents=True)
    (workspace / "knowledge" / "page.md").write_text("original\n")
    (home / "out").mkdir()
    (home / "config.yaml").write_text(yaml.safe_dump({
        "workspace": str(workspace), "tools": {"write_paths": write_paths},
    }))
    return workspace


def _write(path, content="new\n"):
    return tools_mod._execute_registered("write_file", {"path": str(path), "content": content})


def test_a_write_inside_a_listed_folder_lands(tmp_home_no_env: Path) -> None:
    _configure(tmp_home_no_env, ["out"])
    result = _write(tmp_home_no_env / "out" / "guide.md")
    assert result.ok, result.error
    assert (tmp_home_no_env / "out" / "guide.md").read_text() == "new\n"


def test_a_write_outside_the_listed_folders_is_refused_and_names_them(tmp_home_no_env: Path) -> None:
    workspace = _configure(tmp_home_no_env, ["out"])
    for target in (workspace / ".tmp-grep.sh", workspace / "knowledge" / "page.md", "relative.md"):
        result = _write(target)
        assert result.ok is False, target
        assert "tools.write_paths" in result.error and "out" in result.error, result.error
    assert (workspace / "knowledge" / "page.md").read_text() == "original\n"
    assert not (workspace / ".tmp-grep.sh").exists()
    assert not (workspace / "relative.md").exists()


def test_edit_and_delete_outside_the_listed_folders_are_refused(tmp_home_no_env: Path) -> None:
    workspace = _configure(tmp_home_no_env, ["out"])
    page = workspace / "knowledge" / "page.md"
    edited = tools_mod._execute_registered(
        "edit_file", {"path": str(page), "old_string": "original", "new_string": "changed"},
    )
    deleted = tools_mod._execute_registered("delete_file", {"path": str(page)})
    assert edited.ok is False and "tools.write_paths" in edited.error
    assert deleted.ok is False and "tools.write_paths" in deleted.error
    assert page.read_text() == "original\n"


def test_a_symlink_out_of_a_listed_folder_does_not_escape(tmp_home_no_env: Path) -> None:
    workspace = _configure(tmp_home_no_env, ["out"])
    (tmp_home_no_env / "out" / "kb").symlink_to(workspace / "knowledge")
    result = _write(tmp_home_no_env / "out" / "kb" / "page.md")
    assert result.ok is False and "tools.write_paths" in result.error
    assert (workspace / "knowledge" / "page.md").read_text() == "original\n"


def test_a_sibling_folder_sharing_the_prefix_is_outside(tmp_home_no_env: Path) -> None:
    _configure(tmp_home_no_env, ["out"])
    (tmp_home_no_env / "outside").mkdir()
    result = _write(tmp_home_no_env / "outside" / "x.md")
    assert result.ok is False and "tools.write_paths" in result.error


def test_absolute_entries_are_taken_as_they_are(tmp_home_no_env: Path) -> None:
    workspace = _configure(tmp_home_no_env, [str(tmp_home_no_env / "ws" / "drafts")])
    (workspace / "drafts").mkdir()
    assert _write(workspace / "drafts" / "d.md").ok
    assert _write(tmp_home_no_env / "out" / "d.md").ok is False


def test_without_write_paths_nothing_changes(tmp_home_no_env: Path) -> None:
    workspace = _configure(tmp_home_no_env, [])
    assert _write(workspace / "knowledge" / "page.md").ok
    assert (workspace / "knowledge" / "page.md").read_text() == "new\n"


def test_write_paths_roundtrips_and_is_omitted_when_empty(tmp_home_no_env: Path) -> None:
    (tmp_home_no_env / "config.yaml").write_text(yaml.safe_dump({"tools": {"write_paths": [" out ", "out"]}}))
    cfg = config.load(tmp_home_no_env)
    assert cfg.tools.write_paths == ["out"]
    cfg.model = "openai/gpt-4o"
    config.save(cfg)
    assert yaml.safe_load((tmp_home_no_env / "config.yaml").read_text())["tools"]["write_paths"] == ["out"]
    cfg.tools.write_paths = []
    config.save(cfg)
    assert "write_paths" not in (yaml.safe_load((tmp_home_no_env / "config.yaml").read_text()).get("tools") or {})


def test_a_bare_string_is_one_folder(tmp_home_no_env: Path) -> None:
    workspace = _configure(tmp_home_no_env, "out")
    assert config.load(tmp_home_no_env).tools.write_paths == ["out"]
    assert _write(tmp_home_no_env / "out" / "a.md").ok
    assert _write(workspace / "x.md").ok is False


def test_an_invalid_setting_refuses_every_write_and_survives_a_save(tmp_home_no_env: Path) -> None:
    workspace = tmp_home_no_env / "ws"
    workspace.mkdir()
    (tmp_home_no_env / "out").mkdir()
    for bad in (None, "", "  ", {"out": True}, [None], [True], [123], ["out", ""], 5):
        (tmp_home_no_env / "config.yaml").write_text(yaml.safe_dump({
            "workspace": str(workspace), "tools": {"write_paths": bad},
        }))
        cfg = config.load(tmp_home_no_env)
        assert cfg.tools.write_paths is None, bad
        for target in (tmp_home_no_env / "out" / "a.md", workspace / "a.md", tmp_home_no_env / "None" / "a.md"):
            result = _write(target)
            assert result.ok is False and "is invalid" in result.error, (bad, target)
        assert "skill:create" in _policy.profile_denies(cfg)
        cfg.model = "openai/gpt-4o"
        config.save(cfg)
        assert config.load(tmp_home_no_env).tools.write_paths is None, bad


def test_an_entry_that_cannot_be_resolved_refuses_writes_and_keeps_indexing(tmp_home_no_env: Path, monkeypatch) -> None:
    from alpi.core import embed as embed_mod

    monkeypatch.setattr(embed_mod, "_DEFAULT", _Stub())
    workspace = _configure(tmp_home_no_env, ["~nosuchuser-alpi/out"])
    result = _write(tmp_home_no_env / "out" / "a.md")
    assert result.ok is False and "cannot be resolved" in result.error
    indexed = tools_mod._execute_registered("knowledge", {"action": "index"})
    assert indexed.ok, indexed.error
    assert sorted(p.name for p in (workspace / "knowledge").iterdir()) == ["page.md"]


def test_the_refusal_names_the_folders_by_absolute_path(tmp_home_no_env: Path) -> None:
    workspace = _configure(tmp_home_no_env, ["out"])
    result = _write(workspace / "x.md")
    assert str((tmp_home_no_env / "out").resolve()) in result.error


class _Stub:
    name = "stub"
    dim = 4

    def embed(self, texts):
        return [[1.0, 0.0, 0.0, 0.0] for _ in texts]


def _maintain_proposal(monkeypatch):
    import json

    from alpi.llm import Completion
    from alpi.tools import knowledge_base as kb

    proposal = {"pages": [{"path": "concepts/injected.md", "type": "concept", "title": "X", "tags": [],
                           "sources": [], "body": "# X\n\nwritten"}], "log": "x"}
    monkeypatch.setattr(kb.llm, "complete", lambda **kw: Completion(
        content=json.dumps(proposal), tool_calls=[], input_tokens=0, output_tokens=0, cost_usd=0.0, raw=None,
    ))
    monkeypatch.setattr(kb, "index_knowledge", lambda *a, **k: {})


def test_knowledge_maintain_cannot_write_the_shared_base_or_any_path(tmp_home_no_env: Path, monkeypatch) -> None:
    from alpi.tools import knowledge_base as kb

    workspace = _configure(tmp_home_no_env, ["out"])
    _maintain_proposal(monkeypatch)
    completions = []
    original = kb.llm.complete
    monkeypatch.setattr(kb.llm, "complete", lambda **kw: completions.append(kw) or original(**kw))
    result = tools_mod._execute_registered("knowledge", {"action": "maintain", "topic": "anything"})
    assert result.ok is False and "tools.write_paths" in result.error
    other = tmp_home_no_env / "anywhere"
    other.mkdir()
    elsewhere = tools_mod._execute_registered("knowledge", {"action": "maintain", "topic": "a", "path": str(other)})
    assert elsewhere.ok is False and "tools.write_paths" in elsewhere.error
    assert sorted(p.name for p in (workspace / "knowledge").iterdir()) == ["page.md"]
    assert list(other.iterdir()) == []
    assert completions == []


def test_a_symlinked_log_out_of_an_allowed_base_is_refused(tmp_home_no_env: Path, monkeypatch) -> None:
    workspace = _configure(tmp_home_no_env, ["ws"])
    outside = tmp_home_no_env / "elsewhere"
    outside.mkdir()
    (workspace / "knowledge" / "log.md").symlink_to(outside / "log.md")
    _maintain_proposal(monkeypatch)
    result = tools_mod._execute_registered("knowledge", {"action": "maintain", "topic": "anything"})
    assert result.ok is False and "tools.write_paths" in result.error
    assert not (outside / "log.md").exists()
    assert not (workspace / "knowledge" / "concepts").exists()


def test_knowledge_maintain_still_writes_a_base_inside_the_folders(tmp_home_no_env: Path, monkeypatch) -> None:
    workspace = _configure(tmp_home_no_env, ["ws"])
    _maintain_proposal(monkeypatch)
    result = tools_mod._execute_registered("knowledge", {"action": "maintain", "topic": "anything"})
    assert result.ok, result.error
    assert (workspace / "knowledge" / "concepts" / "injected.md").is_file()


def test_knowledge_index_builds_the_store_without_repairing_the_shared_base(tmp_home_no_env: Path, monkeypatch) -> None:
    from alpi.core import embed as embed_mod

    monkeypatch.setattr(embed_mod, "_DEFAULT", _Stub())
    workspace = _configure(tmp_home_no_env, ["out"])
    kb = workspace / "knowledge"
    (kb / "page.md").unlink()
    (kb / "concepts").mkdir()
    (kb / "concepts" / "a.md").write_text(
        "---\ntype: concept\ntitle: A\ntags: []\nupdated_at: 2026-01-01T00:00:00Z\nsources: []\n---\n# A\n\nbody\n"
    )
    result = tools_mod._execute_registered("knowledge", {"action": "index"})
    assert result.ok, result.error
    assert sorted(p.name for p in kb.iterdir()) == ["concepts"]
    assert "1" in result.output or "indexed" in result.output


def test_delegate_sub_agents_inherit_the_skill_authoring_deny(tmp_home_no_env: Path) -> None:
    from alpi.tools import delegate

    _configure(tmp_home_no_env, ["out"])
    assert "skill:create" in delegate._turn_denies(config.load(tmp_home_no_env))
    (tmp_home_no_env / "config.yaml").write_text(yaml.safe_dump({"tools": {"write_paths": []}}))
    assert "skill:create" not in delegate._turn_denies(config.load(tmp_home_no_env))


def test_write_paths_denies_skill_authoring_but_not_running(tmp_home_no_env: Path, monkeypatch) -> None:
    denies = _policy.effective_denies([], write_limited=True)
    schema = next(s for s in tools_mod.schemas(deny=denies) if s["function"]["name"] == "skill")
    enum = schema["function"]["parameters"]["properties"]["action"]["enum"]
    assert not set(enum) & _policy.SKILL_AUTHORING_ACTIONS
    assert {"run", "view", "list"} <= set(enum)
    result = tools_mod._execute_registered(
        "skill",
        {"action": "create", "name": "grep-helper", "category": "miscellaneous", "description": "d", "body": "b"},
        deny=denies,
    )
    assert result.ok is False
    assert "tools.write_paths" in result.error and "operator" in result.error
    assert not (tmp_home_no_env / "skills" / "miscellaneous" / "grep-helper").exists()
    monkeypatch.setenv("ALPI_WORKGROUP_WRITE_SCOPE", '{"phase": "build", "paths": []}')
    in_phase = tools_mod._execute_registered(
        "skill",
        {"action": "create", "name": "grep-helper", "category": "miscellaneous", "description": "d", "body": "b"},
        deny=denies,
    )
    assert in_phase.ok is False and "tools.write_paths" in in_phase.error
    monkeypatch.delenv("ALPI_WORKGROUP_WRITE_SCOPE")
    assert _policy.SKILL_AUTHORING_ACTIONS.isdisjoint(
        {d.split(":", 1)[1] for d in _policy.effective_denies([]) if d.startswith("skill:")}
    )


@pytest.mark.parametrize("name", ["index.md", "log.md"])
def test_knowledge_index_skips_repair_when_a_bundle_file_is_outside(tmp_home_no_env, monkeypatch, name):
    from alpi.core import embed as embed_mod

    monkeypatch.setattr(embed_mod, "_DEFAULT", _Stub())
    workspace = _configure(tmp_home_no_env, ["ws"])
    bundle = workspace / "knowledge"
    outside = tmp_home_no_env / name
    (bundle / name).symlink_to(outside)
    indexed = tools_mod._execute_registered("knowledge", {"action": "index"})
    assert indexed.ok, indexed.error
    assert not outside.exists()
    assert not (bundle / "concepts").exists()


def test_workgroup_download_checks_the_final_destination(tmp_home_no_env, monkeypatch):
    from alpi.tools import workgroup_file

    _configure(tmp_home_no_env, ["out"])

    async def get_file(home, wg_id, digest):
        return {"name": "report.txt"}, b"new"

    monkeypatch.setattr(workgroup_file.wc, "get_file", get_file)
    out = tmp_home_no_env / "out"
    tool = workgroup_file.WorkgroupFileTool()
    args = {"action": "get", "wg_id": "group", "sha256": "digest"}
    denied = tool.run(**args, dest=str(out))
    assert not denied.ok and "tools.write_paths" in denied.error
    assert not (tmp_home_no_env / "out-1").exists()

    (out / "report.txt").write_bytes(b"original")
    allowed = tool.run(**args, dest=str(out / "report.txt"))
    assert allowed.ok, allowed.error
    assert (out / "report.txt").read_bytes() == b"original"
    assert (out / "report-1.txt").read_bytes() == b"new"
