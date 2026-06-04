from __future__ import annotations

import base64
from pathlib import Path

import pytest

from alpi import attachments as att

PNG_BYTES = b"\x89PNG\r\n\x1a\nfake-image-data"


def _png(tmp_path: Path, name: str = "shot.png") -> Path:
    p = tmp_path / name
    p.write_bytes(PNG_BYTES)
    return p


def _pdf(tmp_path: Path, name: str = "doc.pdf", size: int = 64) -> Path:
    p = tmp_path / name
    p.write_bytes(b"%PDF-1.4\n" + b"x" * size)
    return p


# --- validate ------------------------------------------------------------

def test_validate_empty_is_ok():
    assert att.validate(None) == []
    assert att.validate([]) == []


def test_validate_accepts_image_and_sniffs_mime(tmp_path):
    p = _png(tmp_path)
    out = att.validate([{"path": str(p)}])  # no mime → sniff from extension
    assert len(out) == 1
    assert out[0].mime == "image/png"
    assert out[0].name == "shot.png"
    assert out[0].size == len(PNG_BYTES)


def test_validate_rejects_missing_file(tmp_path):
    with pytest.raises(att.AttachmentError, match="not found"):
        att.validate([{"path": str(tmp_path / "nope.png"), "mime": "image/png"}])


def test_validate_rejects_relative_path():
    with pytest.raises(att.AttachmentError, match="absolute"):
        att.validate([{"path": "rel/shot.png", "mime": "image/png"}])


def test_validate_accepts_text_files_by_extension(tmp_path):
    p = tmp_path / "notes.md"
    p.write_text("# Title\nbody")
    out = att.validate([{"path": str(p)}])  # no mime → sniff .md
    assert out[0].mime == "text/markdown"


def test_validate_accepts_code_files_as_text(tmp_path):
    p = tmp_path / "main.py"
    p.write_text("def f():\n    return 1\n")
    out = att.validate([{"path": str(p)}])  # no mime → sniff .py → text/plain
    assert out[0].mime == "text/plain"
    parts = att.build_content_parts("explain", out, vision=False)
    joined = " ".join(x.get("text", "") for x in parts)
    assert "--- attached file: main.py ---" in joined
    assert "def f()" in joined


def test_validate_rejects_unsupported_code_ext(tmp_path):
    p = tmp_path / "a.rb"
    p.write_text("puts 1\n")
    with pytest.raises(att.AttachmentError, match="unsupported type"):
        att.validate([{"path": str(p)}])


def test_validate_rejects_docx_and_xlsx(tmp_path):
    for name in ("doc.docx", "sheet.xlsx"):
        p = tmp_path / name
        p.write_bytes(b"PK\x03\x04 office binary")
        with pytest.raises(att.AttachmentError, match="unsupported type"):
            att.validate([{"path": str(p)}])


def test_validate_rejects_binary_disguised_as_text(tmp_path):
    p = tmp_path / "fake.txt"
    p.write_bytes(b"PK\x03\x04\x00\x00binary\x00zip-ish payload")  # NUL bytes
    with pytest.raises(att.AttachmentError, match="binary data, not text"):
        att.validate([{"path": str(p), "mime": "text/plain"}])


def test_validate_text_cap_is_lower(tmp_path):
    p = tmp_path / "big.csv"
    p.write_text("x" * 100)
    with pytest.raises(att.AttachmentError, match="per-file cap"):
        att.validate([{"path": str(p)}], max_text_bytes=10)


def test_text_file_becomes_text_part_no_vision_needed(tmp_path):
    p = tmp_path / "data.csv"
    p.write_text("a,b\n1,2\n")
    a = att.validate([{"path": str(p)}])
    parts = att.build_content_parts("summarize", a, vision=False)
    joined = " ".join(p.get("text", "") for p in parts)
    assert parts[0]["text"] == "summarize"
    assert "--- attached file: data.csv ---" in joined
    assert "a,b" in joined


def test_text_file_truncation_folded(tmp_path, monkeypatch):
    monkeypatch.setattr(att, "MAX_TEXT_CHARS", 10)
    p = tmp_path / "big.txt"
    p.write_text("y" * 50)
    a = att.validate([{"path": str(p)}])
    parts = att.build_content_parts("", a, vision=False)
    assert any("truncated to 10 chars" in p.get("text", "") for p in parts)


def test_text_file_decodes_non_utf8(tmp_path):
    p = tmp_path / "latin.txt"
    p.write_bytes(b"caf\xe9 was hot")  # 0xe9 = é in latin-1, invalid utf-8
    a = att.validate([{"path": str(p)}])
    parts = att.build_content_parts("", a, vision=False)
    assert any("caf" in p.get("text", "") for p in parts)  # decoded via fallback


def test_validate_rejects_unsupported_mime(tmp_path):
    p = tmp_path / "evil.exe"
    p.write_bytes(b"MZ")
    with pytest.raises(att.AttachmentError, match="unsupported type"):
        att.validate([{"path": str(p), "mime": "application/x-msdownload"}])


def test_validate_rejects_content_type_mismatch(tmp_path):
    p = tmp_path / "fake.png"
    p.write_bytes(b"this is not actually a png file")  # declared png, wrong magic
    with pytest.raises(att.AttachmentError, match="not a valid image/png"):
        att.validate([{"path": str(p), "mime": "image/png"}])


def test_corrupt_pdf_surfaces_as_attachment_error(tmp_path, monkeypatch):
    def boom(_p, _n):
        raise ValueError("broken pdf internals")
    monkeypatch.setattr(att, "_pdf_extract_text", boom)
    a = att.validate([{"path": str(_pdf(tmp_path)), "mime": "application/pdf"}])
    with pytest.raises(att.AttachmentError, match="could not read PDF"):
        att.build_content_parts("read it", a, vision=True)


def test_validate_enforces_per_file_cap(tmp_path):
    p = _png(tmp_path)
    with pytest.raises(att.AttachmentError, match="per-file cap"):
        att.validate([{"path": str(p), "mime": "image/png"}], max_file_bytes=4)


def test_validate_enforces_per_turn_cap(tmp_path):
    a, b = _png(tmp_path, "a.png"), _png(tmp_path, "b.png")
    with pytest.raises(att.AttachmentError, match="per-turn cap"):
        att.validate(
            [{"path": str(a), "mime": "image/png"}, {"path": str(b), "mime": "image/png"}],
            max_turn_bytes=len(PNG_BYTES) + 1,
        )


def test_validate_enforces_count_cap(tmp_path):
    p = _png(tmp_path)
    items = [{"path": str(p), "mime": "image/png"}] * 3
    with pytest.raises(att.AttachmentError, match="too many"):
        att.validate(items, max_count=2)


# --- content parts -------------------------------------------------------

def test_image_becomes_data_url_part(tmp_path):
    a = att.validate([{"path": str(_png(tmp_path)), "mime": "image/png"}])
    parts = att.build_content_parts("what is this?", a, vision=True)
    assert parts[0] == {"type": "text", "text": "what is this?"}
    img = next(p for p in parts if p["type"] == "image_url")
    assert img["type"] == "image_url"
    url = img["image_url"]["url"]
    assert url.startswith("data:image/png;base64,")
    assert base64.b64decode(url.split(",", 1)[1]) == PNG_BYTES


def test_image_without_vision_errors(tmp_path):
    a = att.validate([{"path": str(_png(tmp_path)), "mime": "image/png"}])
    with pytest.raises(att.AttachmentError, match="does not support image"):
        att.build_content_parts("hi", a, vision=False)


def test_text_pdf_becomes_text_part(tmp_path, monkeypatch):
    body = "Quarterly revenue grew 12 percent across every region this year."
    monkeypatch.setattr(att, "_pdf_extract_text", lambda p, n: (body, False))
    a = att.validate([{"path": str(_pdf(tmp_path)), "mime": "application/pdf"}])
    parts = att.build_content_parts("summarize", a, vision=False)
    joined = " ".join(p.get("text", "") for p in parts)
    assert parts[0]["text"] == "summarize"
    assert body in joined
    assert "attached PDF: doc.pdf" in joined


def test_text_pdf_truncation_folded_into_text(tmp_path, monkeypatch):
    monkeypatch.setattr(att, "_pdf_extract_text", lambda p, n: ("lots of real extractable text here, well over the floor", True))
    a = att.validate([{"path": str(_pdf(tmp_path)), "mime": "application/pdf"}])
    parts = att.build_content_parts("", a, vision=False, max_pdf_pages=15)
    assert any("first 15 pages only" in p.get("text", "") for p in parts)


def test_scanned_pdf_renders_images_with_vision(tmp_path, monkeypatch):
    monkeypatch.setattr(att, "_pdf_extract_text", lambda p, n: ("", False))
    monkeypatch.setattr(att, "_pdf_render_images", lambda p, n: ([b"PNG-page-1", b"PNG-page-2"], False))
    a = att.validate([{"path": str(_pdf(tmp_path)), "mime": "application/pdf"}])
    parts = att.build_content_parts("read it", a, vision=True)
    imgs = [p for p in parts if p["type"] == "image_url"]
    assert len(imgs) == 2
    assert imgs[0]["image_url"]["url"].startswith("data:image/png;base64,")


def test_image_payload_budget_stops_and_notes(tmp_path, monkeypatch):
    monkeypatch.setattr(att, "_pdf_extract_text", lambda p, n: ("", False))
    monkeypatch.setattr(att, "_pdf_render_images", lambda p, n: ([b"x" * 10, b"y" * 10, b"z" * 10], False))
    a = att.validate([{"path": str(_pdf(tmp_path)), "mime": "application/pdf"}])
    parts = att.build_content_parts("", a, vision=True, max_image_bytes=15)  # fits one page
    imgs = [p for p in parts if p["type"] == "image_url"]
    assert len(imgs) == 1
    assert any("payload limit" in p.get("text", "") for p in parts)


def test_validate_accepts_pdf_with_preamble(tmp_path):
    p = tmp_path / "p.pdf"
    p.write_bytes(b"\n\n   %PDF-1.7\n" + b"body" * 8)
    out = att.validate([{"path": str(p), "mime": "application/pdf"}])
    assert out[0].mime == "application/pdf"


def test_scanned_pdf_without_vision_errors(tmp_path, monkeypatch):
    monkeypatch.setattr(att, "_pdf_extract_text", lambda p, n: ("", False))
    a = att.validate([{"path": str(_pdf(tmp_path)), "mime": "application/pdf"}])
    with pytest.raises(att.AttachmentError, match="scanned PDF needs a vision"):
        att.build_content_parts("read it", a, vision=False)


# --- persistence helpers -------------------------------------------------

def test_session_metadata_is_bytes_free(tmp_path):
    a = att.validate([{"path": str(_png(tmp_path)), "mime": "image/png"}])
    meta = att.session_metadata(a)
    assert meta == [{"name": "shot.png", "mime": "image/png", "size": len(PNG_BYTES)}]


def test_describe_marker(tmp_path):
    a = att.validate([{"path": str(_png(tmp_path)), "mime": "image/png"}])
    assert att.describe(a) == "[attached: shot.png (image/png)]"
    assert att.describe([]) == ""


def test_session_persists_attachments_round_trip(tmp_path):
    from alpi import session as sess
    s = sess.Session(home=tmp_path, model="m")
    s.log_turn(
        user="resume this", assistant="ok", tools=[],
        attachments=[{"name": "f.pdf", "mime": "application/pdf", "size": 42}],
    )
    import json
    data = json.loads(s.save().read_text())
    assert data["turns"][0]["attachments"] == [
        {"name": "f.pdf", "mime": "application/pdf", "size": 42}
    ]
    turns = sess.load_turns(data)
    assert turns[0].attachments[0]["mime"] == "application/pdf"
    assert att.describe_meta(turns[0].attachments) == "[attached: f.pdf (application/pdf)]"


def test_supports_vision_blocks_only_when_litellm_is_sure(monkeypatch):
    import litellm
    monkeypatch.setattr(litellm, "supports_vision", lambda model: False)
    assert att.supports_vision("some/text-only-model") is False
    monkeypatch.setattr(litellm, "supports_vision", lambda model: (_ for _ in ()).throw(Exception("unknown")))
    assert att.supports_vision("mystery/model") is True
