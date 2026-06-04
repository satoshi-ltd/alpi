from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from alpi.core import embed as embed_mod
from alpi.tools import _state
from alpi.tools import workspace as ws_mod
from alpi.tools.learn_file import LearnFile


class StubEmbedder:
    name = "stub-test"
    dim = 16

    def embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for text in texts:
            vec = [0.0] * self.dim
            for token in (text.lower() or " ").split():
                h = hashlib.md5(token.encode("utf-8")).digest()
                for i in range(self.dim):
                    vec[i] += (h[i] - 128) / 128.0
            norm = sum(v * v for v in vec) ** 0.5 or 1.0
            out.append([v / norm for v in vec])
        return out


@pytest.fixture
def stub_embedder(monkeypatch):
    embedder = StubEmbedder()
    monkeypatch.setattr(embed_mod, "_DEFAULT", embedder)
    yield embedder
    monkeypatch.setattr(embed_mod, "_DEFAULT", None)


@pytest.fixture(autouse=True)
def _clear_turn_attachments():
    _state.set_turn_attachments([])
    yield
    _state.set_turn_attachments([])


def _workspace(tmp_home: Path, configured: bool = True) -> Path:
    ws = tmp_home / "ws"
    ws.mkdir(exist_ok=True)
    if configured:
        (tmp_home / "config.yaml").write_text(f"workspace: {ws}\n")
    return ws


def _attach(directory: Path, name: str, content: str | bytes = "hello world\nsecond line\n") -> dict:
    directory.mkdir(parents=True, exist_ok=True)
    p = directory / name
    if isinstance(content, bytes):
        p.write_bytes(content)
    else:
        p.write_text(content)
    return {"name": name, "path": str(p), "mime": ""}


def test_learn_single_current_turn_attachment(tmp_home, tmp_path, stub_embedder):
    ws = _workspace(tmp_home)
    _state.set_turn_attachments([_attach(tmp_path / "src", "plan.md", "# Plan\nrun 10k\n")])
    out = LearnFile().run()
    assert out.ok, out.error
    body = json.loads(out.output)
    assert body["ok"] is True
    assert body["indexed"] is True
    assert body["path"].startswith(".alpi/documents/")
    assert (ws / body["path"]).is_file()


def test_learn_attachment_by_name(tmp_home, tmp_path, stub_embedder):
    ws = _workspace(tmp_home)
    base = tmp_path / "src"
    base.mkdir()
    _state.set_turn_attachments([
        _attach(base, "plan.md", "# Plan\n"),
        _attach(base, "notes.md", "# Notes\n"),
    ])
    out = LearnFile().run(name="notes.md")
    assert out.ok, out.error
    body = json.loads(out.output)
    assert body["path"].endswith("notes.md")


def test_ambiguous_multiple_attachments_errors(tmp_home, tmp_path, stub_embedder):
    _workspace(tmp_home)
    base = tmp_path / "src"
    base.mkdir()
    _state.set_turn_attachments([
        _attach(base, "a.md", "a"),
        _attach(base, "b.md", "b"),
    ])
    out = LearnFile().run()
    assert not out.ok
    assert "multiple files attached" in out.error


def test_missing_workspace_errors(tmp_home, tmp_path, stub_embedder):
    _workspace(tmp_home, configured=False)
    _state.set_turn_attachments([_attach(tmp_path / "src", "plan.md", "x")])
    out = LearnFile().run()
    assert not out.ok
    assert "no workspace configured" in out.error


def test_configured_workspace_must_exist(tmp_home, tmp_path, stub_embedder):
    missing = tmp_home / "missing-workspace"
    (tmp_home / "config.yaml").write_text(f"workspace: {missing}\n")
    _state.set_turn_attachments([_attach(tmp_path / "src", "plan.md", "x")])
    out = LearnFile().run()
    assert not out.ok
    assert "configured workspace does not exist" in out.error


def test_source_path_for_workspace_file(tmp_home, tmp_path, stub_embedder):
    ws = _workspace(tmp_home)
    (ws / "doc.md").write_text("# Doc\nbody text\n")
    out = LearnFile().run(source_path="doc.md")
    assert out.ok, out.error
    body = json.loads(out.output)
    assert body["indexed"] is True
    assert (ws / body["path"]).is_file()


def test_folder_sanitization_rejects_traversal(tmp_home, tmp_path, stub_embedder):
    _workspace(tmp_home)
    _state.set_turn_attachments([_attach(tmp_path / "src", "plan.md", "x")])
    out = LearnFile().run(folder="../../etc")
    assert not out.ok
    assert ".." in out.error


def test_duplicate_filename_gets_suffix(tmp_home, tmp_path, stub_embedder):
    ws = _workspace(tmp_home)
    src = _attach(tmp_path / "src", "plan.md", "# Plan one\n")
    _state.set_turn_attachments([src])
    first = json.loads(LearnFile().run().output)
    _state.set_turn_attachments([src])
    second = json.loads(LearnFile().run().output)
    assert first["path"] != second["path"]
    assert Path(second["path"]).stem.endswith("-2")
    assert (ws / first["path"]).is_file()
    assert (ws / second["path"]).is_file()


def test_manifest_entry_written(tmp_home, tmp_path, stub_embedder):
    ws = _workspace(tmp_home)
    _state.set_turn_attachments([_attach(tmp_path / "src", "plan.md", "# Plan\n")])
    body = json.loads(LearnFile().run().output)
    manifest = ws / ".alpi" / "documents" / "manifest.jsonl"
    assert manifest.is_file()
    entry = json.loads(manifest.read_text().splitlines()[-1])
    assert entry["path"] == body["path"]
    assert entry["original_name"] == "plan.md"
    assert entry["mime"] == "text/markdown"
    assert entry["size"] > 0
    assert entry["learned_at"].endswith("Z")
    assert entry["source"] == "attachment"


def test_manifest_failure_is_visible_not_fatal(tmp_home, tmp_path, stub_embedder, monkeypatch):
    ws = _workspace(tmp_home)
    from alpi.tools import learn_file as lf
    def boom(docs_root, entry):
        raise OSError("permission denied")
    monkeypatch.setattr(lf, "_append_manifest", boom)
    _state.set_turn_attachments([_attach(tmp_path / "src", "plan.md", "# Plan\nbody\n")])
    out = LearnFile().run()
    assert out.ok, out.error
    body = json.loads(out.output)
    assert body["ok"] is True
    assert body["indexed"] is True
    assert body["manifest_written"] is False
    assert "manifest not written" in body["warning"]
    assert (ws / body["path"]).is_file()


def test_session_metadata_does_not_persist_paths(tmp_path):
    from alpi import attachments as att
    p = tmp_path / "plan.md"
    p.write_text("# Plan\n")
    validated = att.validate([{"path": str(p), "name": "plan.md"}])
    meta = att.session_metadata(validated)
    assert all("path" not in entry for entry in meta)
    assert meta[0]["name"] == "plan.md"


def test_learned_markdown_found_by_search(tmp_home, tmp_path, stub_embedder):
    _workspace(tmp_home)
    _state.set_turn_attachments([
        _attach(tmp_path / "src", "react.md", "# React migration\nWe moved jQuery to React.\n"),
    ])
    learned = json.loads(LearnFile().run().output)
    res = ws_mod.SearchWorkspace().run(query="React migration", k=5)
    assert res.ok, res.error
    results = json.loads(res.output)["results"]
    assert any(".alpi/documents/" in r["path"] for r in results)
    assert any(Path(r["path"]).name == Path(learned["path"]).name for r in results)


def test_learned_pdf_text_indexed(tmp_home, tmp_path, stub_embedder, monkeypatch):
    ws = _workspace(tmp_home)
    monkeypatch.setattr(ws_mod, "_read_pdf", lambda path, ocr=False: "Quarterly revenue grew across regions.\n")
    pdf = tmp_path / "report.pdf"
    pdf.write_bytes(b"%PDF-1.4\n" + b"x" * 64)
    _state.set_turn_attachments([{"name": "report.pdf", "path": str(pdf), "mime": "application/pdf"}])
    out = LearnFile().run()
    assert out.ok, out.error
    body = json.loads(out.output)
    assert body["indexed"] is True
    assert (ws / body["path"]).suffix == ".pdf"


def test_unsupported_type_rejected(tmp_home, tmp_path, stub_embedder):
    _workspace(tmp_home)
    _state.set_turn_attachments([
        {"name": "bundle.zip", "path": str(_attach(tmp_path / "src", "bundle.zip", b"PK\x03\x04zip")["path"]), "mime": ""},
    ])
    out = LearnFile().run()
    assert not out.ok
    assert "unsupported type" in out.error


def test_index_failure_keeps_file_and_reports(tmp_home, tmp_path, stub_embedder, monkeypatch):
    ws = _workspace(tmp_home)
    monkeypatch.setattr(ws_mod, "index_files", lambda home, files, ocr=False: {
        "indexed_files": 0, "added_chunks": 0,
        "failed_files": [{"path": str(files[0]), "reason": "boom"}],
    })
    _state.set_turn_attachments([_attach(tmp_path / "src", "plan.md", "# Plan\n")])
    out = LearnFile().run()
    body = json.loads(out.output)
    assert body["ok"] is False
    assert body["indexed"] is False
    assert body["error"] == "boom"
    assert (ws / body["path"]).is_file()


def test_remote_staged_attachment_path_works(tmp_home, tmp_path, stub_embedder):
    ws = _workspace(tmp_home)
    staged_dir = tmp_path / "host" / "attachments" / "tmp" / "abc123"
    staged_dir.mkdir(parents=True)
    staged = staged_dir / "contract.md"
    staged.write_text("# Contract\nrenewal clause here\n")
    _state.set_turn_attachments([{"name": "contract.md", "path": str(staged), "mime": "text/markdown"}])
    out = LearnFile().run()
    assert out.ok, out.error
    body = json.loads(out.output)
    assert body["indexed"] is True
    assert (ws / body["path"]).is_file()


def test_index_files_uses_the_home_passed_not_active_home(tmp_home, tmp_path, stub_embedder):
    from alpi.core.store import open_store

    _workspace(tmp_home)
    other_home = tmp_path / "other-home"
    other_home.mkdir()
    other_ws = other_home / "workspace"
    other_ws.mkdir()
    (other_home / "config.yaml").write_text(f"workspace: {other_ws}\n")
    doc = other_ws / "other.md"
    doc.write_text("# Other workspace\nunique other content\n")

    summary = ws_mod.index_files(other_home, [doc])
    assert summary["indexed_files"] == 1
    conn = open_store(other_home)
    try:
        root = conn.execute(
            "SELECT value FROM workspace_meta WHERE key = 'workspace_root'"
        ).fetchone()["value"]
    finally:
        conn.close()
    assert root == str(other_ws.resolve())
