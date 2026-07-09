from __future__ import annotations

import struct
from pathlib import Path

from alpi import extract as _extract
from alpi.extract import OcrRequired

_LINES_PER_CHUNK = 30
_LINE_STRIDE = 25

_TEXT_SUFFIXES: frozenset[str] = frozenset({
    ".md", ".markdown", ".txt", ".rst", ".org", ".text",
    ".py", ".pyi",
    ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs",
    ".go", ".rs", ".java", ".kt", ".swift",
    ".c", ".cc", ".cpp", ".h", ".hpp",
    ".rb", ".php", ".lua", ".sh", ".bash", ".zsh", ".fish",
    ".yaml", ".yml", ".json", ".toml", ".ini", ".cfg",
    ".css", ".scss",
    ".sql",
    ".tex",
})

_HTML_SUFFIXES: frozenset[str] = frozenset({".html", ".htm"})
_PDF_SUFFIXES: frozenset[str] = frozenset({".pdf"})
_DOCX_SUFFIXES: frozenset[str] = frozenset({".docx"})
_EPUB_SUFFIXES: frozenset[str] = frozenset({".epub"})
_IMAGE_SUFFIXES: frozenset[str] = frozenset({
    ".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp", ".bmp",
})

_SUPPORTED_SUFFIXES: frozenset[str] = (
    _TEXT_SUFFIXES
    | _HTML_SUFFIXES
    | _PDF_SUFFIXES
    | _DOCX_SUFFIXES
    | _EPUB_SUFFIXES
    | _IMAGE_SUFFIXES
)

_EMBED_BATCH = 64

def _vec_blob(vec: list[float]) -> bytes:
    return struct.pack(f"{len(vec)}f", *vec)


class EmbedderMismatch(RuntimeError):
    pass


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _read_html(path: Path) -> str:
    import html2text

    h = html2text.HTML2Text()
    h.ignore_links = True
    h.ignore_images = True
    return h.handle(path.read_text(encoding="utf-8", errors="replace"))


def _read_pdf(path: Path, ocr: bool = False) -> str:
    text, _ = _extract.extract_pdf_text(path)
    if len(text.strip()) >= _extract.SCANNED_PDF_TEXT_FLOOR:
        return text
    if not ocr:
        raise OcrRequired('scanned PDF - re-run knowledge(action="ingest", ocr=true)')
    return _extract.ocr_pdf(path)[0]


def _read_image(path: Path, ocr: bool = False) -> str:
    if not ocr:
        raise OcrRequired('image file - re-run knowledge(action="ingest", ocr=true)')
    return _extract.ocr_image(path)


def _read_docx(path: Path) -> str:
    from docx import Document

    doc = Document(str(path))
    return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())


def _read_epub(path: Path) -> str:
    import html2text
    from ebooklib import ITEM_DOCUMENT, epub

    book = epub.read_epub(str(path))
    h = html2text.HTML2Text()
    h.ignore_links = True
    h.ignore_images = True
    parts: list[str] = []
    for item in book.get_items_of_type(ITEM_DOCUMENT):
        parts.append(
            h.handle(item.get_content().decode("utf-8", errors="replace"))
        )
    return "\n\n".join(parts)


def _reader_for(suffix: str, ocr: bool = False):
    if suffix in _PDF_SUFFIXES:
        return lambda p: _read_pdf(p, ocr=ocr)
    if suffix in _DOCX_SUFFIXES:
        return _read_docx
    if suffix in _EPUB_SUFFIXES:
        return _read_epub
    if suffix in _HTML_SUFFIXES:
        return _read_html
    if suffix in _IMAGE_SUFFIXES:
        return lambda p: _read_image(p, ocr=ocr)
    return _read_text


def _chunk_lines(text: str) -> list[tuple[int, int, str]]:
    lines = text.splitlines()
    if not lines:
        return []
    out: list[tuple[int, int, str]] = []
    i = 0
    n = len(lines)
    while i < n:
        end = min(i + _LINES_PER_CHUNK, n)
        body = "\n".join(lines[i:end]).strip()
        if body:
            out.append((i + 1, end, body))
        if end == n:
            break
        i += _LINE_STRIDE
    return out
