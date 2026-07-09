from __future__ import annotations

import io
import threading
from pathlib import Path

SCANNED_PDF_TEXT_FLOOR = 50


class OcrRequired(RuntimeError):
    pass


def extract_pdf_text(path: Path, *, char_budget: int | None = None) -> tuple[str, bool]:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    pages = reader.pages
    chunks: list[str] = []
    used = 0
    truncated = False
    for i, page in enumerate(pages):
        try:
            t = page.extract_text() or ""
        except Exception:  # noqa: BLE001 — one bad page shouldn't sink the whole read
            t = ""
        if t.strip():
            chunks.append(t)
            used += len(t)
        if char_budget is not None and used >= char_budget:
            truncated = i < len(pages) - 1
            break
    text = "\n\n".join(chunks)
    if char_budget is not None and len(text) > char_budget:
        text = text[:char_budget]
        truncated = True
    return text, truncated


def render_pdf_images(path: Path, *, max_pages: int) -> tuple[list[bytes], bool]:
    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(str(path))
    try:
        n = len(doc)
        images: list[bytes] = []
        for i in range(min(n, max_pages)):
            pil = doc[i].render(scale=2.0).to_pil()
            buf = io.BytesIO()
            pil.save(buf, format="PNG")
            images.append(buf.getvalue())
        return images, n > max_pages
    finally:
        doc.close()


def ocr_pdf(path: Path, *, max_pages: int | None = None, on_page=None) -> tuple[str, bool]:
    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(str(path))
    try:
        n = len(doc)
        limit = n if max_pages is None else min(n, max_pages)
        parts: list[str] = []
        for i in range(limit):
            if on_page is not None:
                on_page(i + 1, limit)
            pil = doc[i].render(scale=2.0).to_pil()
            parts.append(ocr_pil(pil))
        return "\n\n".join(p for p in parts if p.strip()), limit < n
    finally:
        doc.close()


def ocr_image(path: Path) -> str:
    from PIL import Image, ImageOps

    with Image.open(path) as img:
        return ocr_pil(ImageOps.exif_transpose(img))


def ocr_pil(pil_image) -> str:
    import numpy as np

    reader = _ocr_reader()
    arr = np.array(pil_image.convert("RGB"))
    result, _elapsed = reader(arr)
    if not result:
        return ""
    return "\n".join(text for _box, text, _score in result)


_ocr_reader_cache = None
_ocr_reader_lock = threading.Lock()


def _ocr_reader():
    global _ocr_reader_cache
    if _ocr_reader_cache is not None:
        return _ocr_reader_cache
    with _ocr_reader_lock:
        if _ocr_reader_cache is not None:
            return _ocr_reader_cache
        from rapidocr_onnxruntime import RapidOCR

        _ocr_reader_cache = RapidOCR()
        return _ocr_reader_cache
