"""Tests for the local RAG workspace tools."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import pytest

from alpi.core import embed as embed_mod
from alpi.core.store import open_store, store_path
from alpi.tools import workspace as ws


class StubEmbedder:
    """Deterministic, dependency-free embedder for tests.

    Hashes each token of the input and folds it into a fixed-dim float
    vector. Same input → same vector across runs.
    """

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


def _make_workspace(root: Path) -> None:
    (root / "notes").mkdir()
    (root / "notes" / "react.md").write_text(
        "# React migration\n\n"
        "We replaced the legacy jQuery layer with React components.\n"
        "Routing now uses React Router v6.\n"
    )
    (root / "notes" / "infra.md").write_text(
        "# Infrastructure notes\n\n"
        "Kubernetes cluster runs on EKS.\n"
        "Postgres is hosted on RDS, daily snapshots to S3.\n"
    )
    (root / "node_modules").mkdir()
    (root / "node_modules" / "should_be_skipped.md").write_text("ignored")


def test_index_then_search_returns_results(tmp_home, tmp_path, stub_embedder):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    _make_workspace(workspace)

    out = ws.IndexWorkspace().run(path=str(workspace))
    assert out.ok, out.error
    summary = json.loads(out.output)
    assert summary["indexed_files"] == 2
    assert summary["added_chunks"] >= 2
    assert summary["embedder"] == "stub-test"

    res = ws.SearchWorkspace().run(query="React migration", k=3)
    assert res.ok, res.error
    payload = json.loads(res.output)
    paths = [r["path"] for r in payload["results"]]
    assert any("react.md" in p for p in paths)


def test_reindex_skips_unchanged_files(tmp_home, tmp_path, stub_embedder):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    _make_workspace(workspace)

    first = json.loads(ws.IndexWorkspace().run(path=str(workspace)).output)
    second = json.loads(ws.IndexWorkspace().run(path=str(workspace)).output)
    assert first["indexed_files"] == 2
    assert second["indexed_files"] == 0
    assert second["skipped_files"] == 2
    assert second["total_chunks"] == first["total_chunks"]


def test_reindex_force_rebuilds(tmp_home, tmp_path, stub_embedder):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    _make_workspace(workspace)

    ws.IndexWorkspace().run(path=str(workspace))
    forced = json.loads(
        ws.IndexWorkspace().run(path=str(workspace), force=True).output
    )
    assert forced["indexed_files"] == 2
    assert forced["skipped_files"] == 0


def test_modified_file_is_reindexed(tmp_home, tmp_path, stub_embedder):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    _make_workspace(workspace)
    ws.IndexWorkspace().run(path=str(workspace))

    react = workspace / "notes" / "react.md"
    new_mtime = react.stat().st_mtime + 5
    react.write_text(react.read_text() + "\nNew section about Suspense.")
    import os
    os.utime(react, (new_mtime, new_mtime))

    out = json.loads(ws.IndexWorkspace().run(path=str(workspace)).output)
    assert out["indexed_files"] == 1
    assert out["skipped_files"] == 1


def test_search_empty_index_returns_hint(tmp_home, stub_embedder):
    out = ws.SearchWorkspace().run(query="anything")
    assert out.ok
    payload = json.loads(out.output)
    assert payload["results"] == []
    assert "Run index_workspace" in payload["hint"]


def test_search_rejects_empty_query(tmp_home, stub_embedder):
    out = ws.SearchWorkspace().run(query="   ")
    assert not out.ok
    assert "Empty query" in out.error


def test_search_rejects_bad_k(tmp_home, stub_embedder):
    assert ws.SearchWorkspace().run(query="x", k=0).ok is False
    assert ws.SearchWorkspace().run(query="x", k=99).ok is False


def test_embedder_mismatch_blocks_search(tmp_home, tmp_path, stub_embedder, monkeypatch):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    _make_workspace(workspace)
    ws.IndexWorkspace().run(path=str(workspace))

    class OtherEmbedder(StubEmbedder):
        name = "different"
        dim = 16

    monkeypatch.setattr(embed_mod, "_DEFAULT", OtherEmbedder())
    out = ws.SearchWorkspace().run(query="anything")
    assert not out.ok
    assert "Re-index" in out.error


def test_embedder_mismatch_resolved_by_force_reindex(tmp_home, tmp_path, stub_embedder, monkeypatch):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    _make_workspace(workspace)
    ws.IndexWorkspace().run(path=str(workspace))

    class OtherEmbedder(StubEmbedder):
        name = "different"
        dim = 8

    monkeypatch.setattr(embed_mod, "_DEFAULT", OtherEmbedder())
    out = ws.IndexWorkspace().run(path=str(workspace), force=True)
    assert out.ok, out.error
    summary = json.loads(out.output)
    assert summary["embedder"] == "different"
    assert summary["dim"] == 8
    assert summary["indexed_files"] == 2

    res = json.loads(ws.SearchWorkspace().run(query="React migration").output)
    assert res["results"]


def test_index_purges_deleted_files(tmp_home, tmp_path, stub_embedder):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    _make_workspace(workspace)

    first = json.loads(ws.IndexWorkspace().run(path=str(workspace)).output)
    assert first["indexed_files"] == 2
    assert first["removed_files"] == 0

    (workspace / "notes" / "react.md").unlink()

    second = json.loads(ws.IndexWorkspace().run(path=str(workspace)).output)
    assert second["removed_files"] == 1
    assert second["total_files"] == 1

    res = json.loads(ws.SearchWorkspace().run(query="React migration").output)
    assert all("react.md" not in r["path"] for r in res["results"])


def test_index_skips_unsupported_and_oversized(tmp_home, tmp_path, stub_embedder):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "data.bin").write_bytes(b"\x00" * 100)
    (workspace / "big.md").write_text("x" * 1_100_000)
    (workspace / "ok.md").write_text("A short markdown note.\n")

    summary = json.loads(ws.IndexWorkspace().run(path=str(workspace)).output)
    assert summary["indexed_files"] == 1
    assert summary["total_chunks"] >= 1


def test_store_file_lives_under_profile_home(tmp_home, tmp_path, stub_embedder):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    _make_workspace(workspace)
    ws.IndexWorkspace().run(path=str(workspace))
    assert store_path(tmp_home).exists()


def test_open_store_loads_vec_extension(tmp_home):
    conn = open_store(tmp_home)
    try:
        row = conn.execute("SELECT vec_version() AS v").fetchone()
        assert row["v"]
    finally:
        conn.close()


def test_chunk_index_is_zero_based_ordinal(tmp_home, tmp_path, stub_embedder):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    body = "\n".join(f"line {i}" for i in range(120))
    (workspace / "long.md").write_text(body)
    ws.IndexWorkspace().run(path=str(workspace))

    conn = open_store(tmp_home)
    try:
        rows = conn.execute(
            "SELECT chunk_index, line_start FROM workspace_chunks "
            "ORDER BY chunk_index"
        ).fetchall()
    finally:
        conn.close()
    assert len(rows) >= 4
    assert [r["chunk_index"] for r in rows] == list(range(len(rows)))
    assert rows[0]["chunk_index"] == 0
    assert rows[0]["line_start"] == 1


def test_reader_dispatcher_routes_by_suffix():
    assert ws._reader_for(".md") is ws._read_text
    assert ws._reader_for(".py") is ws._read_text
    assert ws._reader_for(".html") is ws._read_html
    assert ws._reader_for(".htm") is ws._read_html
    assert ws._reader_for(".docx") is ws._read_docx
    assert ws._reader_for(".epub") is ws._read_epub
    pdf_reader = ws._reader_for(".pdf")
    assert callable(pdf_reader) and pdf_reader is not ws._read_pdf
    img_reader = ws._reader_for(".jpg")
    assert callable(img_reader) and img_reader is not ws._read_image


def test_index_indexes_docx(tmp_home, tmp_path, stub_embedder):
    from docx import Document

    workspace = tmp_path / "ws"
    workspace.mkdir()
    doc = Document()
    doc.add_paragraph("This document describes our quarterly revenue.")
    doc.add_paragraph("Q3 closed at 1.2M EUR, ahead of forecast.")
    doc.save(workspace / "report.docx")

    out = ws.IndexWorkspace().run(path=str(workspace))
    assert out.ok, out.error
    summary = json.loads(out.output)
    assert summary["indexed_files"] == 1
    assert summary["added_chunks"] >= 1
    assert summary["failed_files"] == []

    res = json.loads(ws.SearchWorkspace().run(query="revenue forecast").output)
    paths = [r["path"] for r in res["results"]]
    assert any("report.docx" in p for p in paths)


def test_corrupted_binary_file_lands_in_failed_files(tmp_home, tmp_path, stub_embedder):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "broken.pdf").write_bytes(b"not really a pdf, just garbage bytes")

    summary = json.loads(ws.IndexWorkspace().run(path=str(workspace)).output)
    assert summary["indexed_files"] == 0
    assert len(summary["failed_files"]) == 1
    assert summary["failed_files"][0]["path"].endswith("broken.pdf")


def test_oversized_binary_doc_is_skipped(tmp_home, tmp_path, stub_embedder):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "huge.pdf").write_bytes(b"x" * 11_000_000)
    (workspace / "ok.md").write_text("Tiny note.\n")

    summary = json.loads(ws.IndexWorkspace().run(path=str(workspace)).output)
    assert summary["indexed_files"] == 1
    assert summary["failed_files"] == []


def test_image_skipped_without_ocr_flag(tmp_home, tmp_path, stub_embedder):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "receipt.jpg").write_bytes(b"fake-jpg")
    (workspace / "note.md").write_text("Tiny note.\n")

    summary = json.loads(ws.IndexWorkspace().run(path=str(workspace)).output)
    assert summary["indexed_files"] == 1
    assert len(summary["failed_files"]) == 1
    assert "ocr=true" in summary["failed_files"][0]["reason"]


def test_image_path_uses_ocr_when_flag_on(tmp_home, tmp_path, stub_embedder, monkeypatch):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "receipt.jpg").write_bytes(b"fake-jpg-bytes")

    def fake_image_reader(path, ocr=False):
        assert ocr is True
        assert path.name == "receipt.jpg"
        return "Receipt: coffee 4.50 EUR, total 4.50 EUR"

    monkeypatch.setattr(ws, "_read_image", fake_image_reader)

    summary = json.loads(
        ws.IndexWorkspace().run(path=str(workspace), ocr=True).output
    )
    assert summary["indexed_files"] == 1
    res = json.loads(ws.SearchWorkspace().run(query="coffee receipt total").output)
    assert any("receipt.jpg" in r["path"] for r in res["results"])


def test_pdf_with_text_layer_skips_ocr(monkeypatch, tmp_path):
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"placeholder")

    monkeypatch.setattr(
        ws,
        "_ocr_pdf",
        lambda p: pytest.fail("OCR fallback should not run for text-layer PDFs"),
    )

    class FakePage:
        def extract_text(self):
            return "lots of real text " * 10

    class FakeReader:
        pages = [FakePage(), FakePage()]

    monkeypatch.setattr("pypdf.PdfReader", lambda _: FakeReader())
    out = ws._read_pdf(pdf, ocr=False)
    assert "real text" in out


def test_pdf_without_text_layer_requires_ocr_flag(monkeypatch, tmp_path):
    pdf = tmp_path / "scanned.pdf"
    pdf.write_bytes(b"placeholder")

    class EmptyPage:
        def extract_text(self):
            return ""

    class EmptyReader:
        pages = [EmptyPage()]

    monkeypatch.setattr("pypdf.PdfReader", lambda _: EmptyReader())

    with pytest.raises(ws.OcrRequired):
        ws._read_pdf(pdf, ocr=False)


def test_pdf_without_text_layer_falls_back_to_ocr_when_flag_on(monkeypatch, tmp_path):
    pdf = tmp_path / "scanned.pdf"
    pdf.write_bytes(b"placeholder")
    called = {"ocr": False}

    def fake_ocr(p):
        called["ocr"] = True
        return "OCR-extracted text from the scan"

    monkeypatch.setattr(ws, "_ocr_pdf", fake_ocr)

    class EmptyPage:
        def extract_text(self):
            return ""

    class EmptyReader:
        pages = [EmptyPage()]

    monkeypatch.setattr("pypdf.PdfReader", lambda _: EmptyReader())
    out = ws._read_pdf(pdf, ocr=True)
    assert "OCR-extracted" in out
    assert called["ocr"] is True
