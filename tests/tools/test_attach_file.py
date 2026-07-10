from __future__ import annotations

import json
from pathlib import Path

from alpi.tools import get
from alpi.tools.attach_file import AttachFile


def test_attach_file_is_registered() -> None:
    assert get("attach_file") is AttachFile


def test_attach_file_returns_out_json(tmp_path: Path) -> None:
    p = tmp_path / "report.md"
    p.write_text("# Report\n\nbody\n")
    res = AttachFile().run(str(p))
    assert res.ok
    assert json.loads(res.output) == {"out": str(p.resolve())}


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
