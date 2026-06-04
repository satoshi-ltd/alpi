from __future__ import annotations

import base64
import mimetypes
from dataclasses import dataclass
from pathlib import Path

IMAGE_MIMES = frozenset({"image/png", "image/jpeg", "image/webp"})
PDF_MIME = "application/pdf"
TEXT_MIMES = frozenset({
    "text/plain", "text/markdown", "text/csv",
    "application/json", "text/html",
    "application/yaml", "text/yaml", "application/x-yaml", "text/x-yaml",
})
ALLOWED_MIMES = IMAGE_MIMES | {PDF_MIME} | TEXT_MIMES

_EXT_MIME = {
    ".txt": "text/plain", ".text": "text/plain", ".log": "text/plain",
    ".md": "text/markdown", ".markdown": "text/markdown",
    ".csv": "text/csv",
    ".json": "application/json",
    ".yaml": "application/yaml", ".yml": "application/yaml",
    ".html": "text/html", ".htm": "text/html",
    ".js": "text/plain", ".jsx": "text/plain", ".ts": "text/plain", ".tsx": "text/plain",
    ".py": "text/plain", ".go": "text/plain", ".rs": "text/plain",
    ".sh": "text/plain", ".sql": "text/plain",
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".webp": "image/webp", ".pdf": "application/pdf",
}

MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_TEXT_FILE_BYTES = 2 * 1024 * 1024
MAX_TEXT_CHARS = 160_000
MAX_TURN_BYTES = 40 * 1024 * 1024
MAX_ATTACHMENTS = 10
MAX_PDF_PAGES = 15
MAX_IMAGE_PAYLOAD_BYTES = 24 * 1024 * 1024
_SCANNED_TEXT_MIN = 32


class AttachmentError(ValueError):
    pass


@dataclass(frozen=True)
class Attachment:
    path: Path
    mime: str
    name: str
    size: int


def is_image(mime: str) -> bool:
    return mime in IMAGE_MIMES


def is_pdf(mime: str) -> bool:
    return mime == PDF_MIME


def is_text(mime: str) -> bool:
    return mime in TEXT_MIMES


def _sniff_mime(path: Path, declared: str | None) -> str:
    declared = (declared or "").strip().lower()
    if declared in ALLOWED_MIMES:
        return declared
    ext = path.suffix.lower()
    if ext in _EXT_MIME:
        return _EXT_MIME[ext]
    if declared:
        return declared
    guessed, _ = mimetypes.guess_type(str(path))
    return (guessed or "").lower()


def _detect_magic(head: bytes) -> str | None:
    # Images must match at offset 0; PDFs allow a leading preamble before %PDF.
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    if b"%PDF" in head[:1024]:
        return "application/pdf"
    return None


def _looks_binary(head: bytes) -> bool:
    if b"\x00" in head:
        return True
    if not head:
        return False
    ctrl = sum(1 for b in head if b < 0x09 or 0x0e <= b < 0x20)
    return ctrl / len(head) > 0.3


def validate(
    raw: list[dict] | None,
    *,
    max_file_bytes: int = MAX_FILE_BYTES,
    max_text_bytes: int = MAX_TEXT_FILE_BYTES,
    max_turn_bytes: int = MAX_TURN_BYTES,
    max_count: int = MAX_ATTACHMENTS,
) -> list[Attachment]:
    if not raw:
        return []
    if len(raw) > max_count:
        raise AttachmentError(f"too many attachments: {len(raw)} (max {max_count})")

    out: list[Attachment] = []
    total = 0
    for item in raw:
        path_str = str((item or {}).get("path") or "").strip()
        if not path_str:
            raise AttachmentError("attachment missing 'path'")
        path = Path(path_str).expanduser()
        if not path.is_absolute():
            raise AttachmentError(f"attachment path must be absolute: {path_str!r}")
        if not path.is_file():
            raise AttachmentError(f"attachment not found: {path_str}")

        name = str((item or {}).get("name") or path.name).strip() or path.name
        mime = _sniff_mime(path, (item or {}).get("mime"))
        if mime not in ALLOWED_MIMES:
            raise AttachmentError(
                f"{name}: unsupported type {mime or 'unknown'!r} "
                f"(allowed: {', '.join(sorted(ALLOWED_MIMES))})"
            )

        # Binary types: trust the bytes over the declared mime (remote uploads).
        if is_image(mime) or is_pdf(mime):
            try:
                with open(path, "rb") as fh:
                    head = fh.read(1024)
            except OSError as e:
                raise AttachmentError(f"{name}: could not read file") from e
            detected = _detect_magic(head)
            if detected != mime:
                raise AttachmentError(
                    f"{name}: content is not a valid {mime} (looks like {detected or 'unknown'})"
                )
        elif is_text(mime):
            try:
                with open(path, "rb") as fh:
                    head = fh.read(4096)
            except OSError as e:
                raise AttachmentError(f"{name}: could not read file") from e
            if _looks_binary(head):
                raise AttachmentError(f"{name}: looks like binary data, not text")

        cap = max_text_bytes if is_text(mime) else max_file_bytes
        size = path.stat().st_size
        if size > cap:
            raise AttachmentError(
                f"{name}: {size} bytes exceeds the {cap}-byte per-file cap"
            )
        total += size
        if total > max_turn_bytes:
            raise AttachmentError(
                f"attachments exceed the {max_turn_bytes}-byte per-turn cap"
            )
        out.append(Attachment(path=path, mime=mime, name=name, size=size))
    return out


def vision_status(model: str) -> str:
    try:
        import litellm
        return "yes" if litellm.supports_vision(model=model) else "no"
    except Exception:  # noqa: BLE001
        return "unknown"


def supports_vision(model: str) -> bool:
    # Unknown → True: only block when litellm is sure the model can't.
    return vision_status(model) != "no"


def _data_url(mime: str, data: bytes) -> str:
    return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"


def _image_part(mime: str, data: bytes) -> dict:
    return {"type": "image_url", "image_url": {"url": _data_url(mime, data)}}


def _text_part(text: str) -> dict:
    return {"type": "text", "text": text}


def _read_text(path: Path, max_chars: int) -> tuple[str, bool]:
    data = path.read_bytes()
    text = None
    for enc in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            text = data.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        text = data.decode("utf-8", errors="replace")
    truncated = len(text) > max_chars
    return text[:max_chars], truncated


def _pdf_extract_text(path: Path, max_pages: int) -> tuple[str, bool]:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    pages = reader.pages
    truncated = len(pages) > max_pages
    chunks: list[str] = []
    for page in pages[:max_pages]:
        try:
            chunks.append(page.extract_text() or "")
        except Exception:  # noqa: BLE001
            chunks.append("")
    return "\n\n".join(c for c in chunks if c.strip()), truncated


def _pdf_render_images(path: Path, max_pages: int) -> tuple[list[bytes], bool]:
    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(str(path))
    try:
        n = len(doc)
        truncated = n > max_pages
        images: list[bytes] = []
        for i in range(min(n, max_pages)):
            page = doc[i]
            pil = page.render(scale=2.0).to_pil()
            import io
            buf = io.BytesIO()
            pil.save(buf, format="PNG")
            images.append(buf.getvalue())
        return images, truncated
    finally:
        doc.close()


def build_content_parts(
    text: str,
    attachments: list[Attachment],
    *,
    vision: bool,
    max_pdf_pages: int = MAX_PDF_PAGES,
    max_image_bytes: int = MAX_IMAGE_PAYLOAD_BYTES,
) -> list[dict]:
    parts: list[dict] = []
    if text:
        parts.append(_text_part(text))
    if attachments:
        parts.append(_text_part(
            f"[{len(attachments)} file(s) are attached to this message; the available "
            "attachment content is included below. Use it directly — do NOT call "
            "search_workspace or index_workspace to look for them.]"
        ))
    budget = [max_image_bytes]  # boxed so add_image can mutate it

    def add_image(mime: str, data: bytes) -> bool:
        if len(data) > budget[0]:
            return False
        budget[0] -= len(data)
        parts.append(_image_part(mime, data))
        return True

    for a in attachments:
        if is_image(a.mime):
            if not vision:
                raise AttachmentError(f"{a.name}: this model does not support image input")
            try:
                data = a.path.read_bytes()
            except OSError as e:
                raise AttachmentError(f"{a.name}: could not read file") from e
            if not add_image(a.mime, data):
                parts.append(_text_part(f"[{a.name}: omitted — turn image payload limit reached]"))
        elif is_pdf(a.mime):
            try:
                extracted, truncated = _pdf_extract_text(a.path, max_pdf_pages)
            except Exception as e:  # noqa: BLE001 — corrupt/unsupported PDF
                raise AttachmentError(f"{a.name}: could not read PDF") from e
            if len(extracted.strip()) >= _SCANNED_TEXT_MIN:
                pages = f" (first {max_pdf_pages} pages only)" if truncated else ""
                parts.append(_text_part(
                    f"--- attached PDF: {a.name}{pages} ---\n{extracted}\n--- end of {a.name} ---"
                ))
            else:
                if not vision:
                    raise AttachmentError(f"{a.name}: scanned PDF needs a vision-capable model")
                try:
                    images, truncated = _pdf_render_images(a.path, max_pdf_pages)
                except Exception as e:  # noqa: BLE001
                    raise AttachmentError(f"{a.name}: could not render PDF") from e
                rendered = 0
                for img in images:
                    if not add_image("image/png", img):
                        break
                    rendered += 1
                caveats = []
                if truncated:
                    caveats.append(f"first {max_pdf_pages} pages")
                if rendered < len(images):
                    caveats.append("image payload limit reached")
                if caveats:
                    parts.append(_text_part(
                        f"[{a.name}: {rendered} scanned page image(s) included — {', '.join(caveats)}]"
                    ))
        elif is_text(a.mime):
            try:
                body, truncated = _read_text(a.path, MAX_TEXT_CHARS)
            except OSError as e:
                raise AttachmentError(f"{a.name}: could not read file") from e
            trunc = f" (truncated to {MAX_TEXT_CHARS} chars)" if truncated else ""
            parts.append(_text_part(
                f"--- attached file: {a.name}{trunc} ---\n{body}\n--- end of {a.name} ---"
            ))
        else:  # validate() should have caught this
            raise AttachmentError(f"{a.name}: unsupported type {a.mime!r}")

    return parts


def session_metadata(attachments: list[Attachment]) -> list[dict]:
    return [
        {"name": a.name, "mime": a.mime, "size": a.size}
        for a in attachments
    ]


def describe_meta(meta: list[dict]) -> str:
    if not meta:
        return ""
    items = ", ".join(f"{m.get('name')} ({m.get('mime')})" for m in meta)
    return f"[attached: {items}]"


def describe(attachments: list[Attachment]) -> str:
    return describe_meta(session_metadata(attachments))
