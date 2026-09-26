from __future__ import annotations

import json
from pathlib import Path

from alpi.tools import get
from alpi.tools.attach_file import AttachFile


def test_attach_file_is_registered() -> None:
    assert get("attach_file") is AttachFile


def test_write_file_points_to_attach_for_deliverables() -> None:
    from alpi.tools.write_file import WriteFile
    assert "attach_file" in WriteFile.description


def test_attach_file_scopes_to_deliverables_not_project_files() -> None:
    desc = AttachFile.description.lower()
    assert "deliverable" in desc
    assert "project file" in desc


def test_attach_file_returns_out_json(tmp_home_no_env: Path) -> None:
    p = tmp_home_no_env / "out" / "report.md"
    p.parent.mkdir(exist_ok=True)
    p.write_text("# Report\n\nbody\n")
    res = AttachFile().run(str(p))
    assert res.ok
    assert json.loads(res.output) == {"out": str(p.resolve())}


def test_attach_file_refuses_a_document_the_app_cannot_serve(tmp_home_no_env: Path, tmp_path_factory) -> None:
    elsewhere = tmp_path_factory.mktemp("tmp-docs")
    for doc in (elsewhere / "report.md", tmp_home_no_env / "cache" / "report.pdf"):
        doc.parent.mkdir(parents=True, exist_ok=True)
        doc.write_text("x")
        res = AttachFile().run(str(doc))
        assert not res.ok
        assert str(tmp_home_no_env / "out") in res.error


def test_attach_file_keeps_images_in_tmp_and_documents_in_the_workspace(tmp_home_no_env: Path, tmp_path_factory) -> None:
    elsewhere = tmp_path_factory.mktemp("tmp-images")
    img = elsewhere / "chart.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n")
    assert AttachFile().run(str(img)).ok
    workspace = tmp_path_factory.mktemp("workspace")
    (tmp_home_no_env / "config.yaml").write_text(f"workspace: {workspace}\n")
    doc = workspace / "notes.md"
    doc.write_text("x")
    assert AttachFile().run(str(doc)).ok


def test_attach_file_names_the_out_folder() -> None:
    assert "`out/`" in AttachFile.description and "/tmp" in AttachFile.description


def test_attach_file_missing_file(tmp_path: Path) -> None:
    res = AttachFile().run(str(tmp_path / "nope.md"))
    assert not res.ok
    assert "no such file" in res.error


def test_attach_file_unsupported_type(tmp_path: Path) -> None:
    p = tmp_path / "bin.bin"
    p.write_bytes(b"\x00\x01\x02")
    res = AttachFile().run(str(p))
    assert not res.ok
    assert "unsupported file type" in res.error
