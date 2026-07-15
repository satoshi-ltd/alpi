from __future__ import annotations

import base64
import mimetypes
from dataclasses import dataclass
from pathlib import Path

from alpi import extract

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
CHARS_PER_TOKEN = 4
AUTO_TEXT_WINDOW_FRACTION = 0.5
FALLBACK_TEXT_TOKENS = 100_000
MAX_TEXT_CHARS = 400_000
MAX_TURN_BYTES = 40 * 1024 * 1024
MAX_ATTACHMENTS = 10
SCAN_MAX_PAGES = 15
MAX_IMAGE_PAYLOAD_BYTES = 24 * 1024 * 1024


class AttachmentError(ValueError):
    pass


@dataclass(frozen=True)
class Attachment:
    path: Path
    mime: str
    name: str
    size: int


_PRODUCED_EXT_MIME = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp",
    ".pdf": "application/pdf",
    ".txt": "text/plain", ".md": "text/markdown", ".markdown": "text/markdown",
    ".csv": "text/csv", ".json": "application/json",
    ".yaml": "application/yaml", ".yml": "application/yaml",
    ".html": "text/html", ".htm": "text/html",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}
_PRODUCED_KIND = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "sheet",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "doc",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "deck",
}
_OFFICE_MIMES = frozenset(m for m in _PRODUCED_KIND if m != "application/pdf")


def produced_attachment(producer: str, output: str, *, roots: list) -> dict | None:
    import json
    if not isinstance(output, str):
        return None
    try:  # output is `{json}` + a trailing line; decode the leading object only
        data, _ = json.JSONDecoder().raw_decode(output.lstrip())
    except json.JSONDecodeError:
        return None
    out = data.get("out") if isinstance(data, dict) else None
    if not isinstance(out, str) or not out:
        return None
    p = Path(out)
    if not p.is_absolute():
        return None
    mime = _PRODUCED_EXT_MIME.get(p.suffix.lower())
    if not mime:
        return None
    try:
        rp = p.resolve()
    except OSError:
        return None
    allowed = []
    for r in roots or []:
        try:
            allowed.append(Path(r).resolve())
        except (OSError, TypeError):
            pass
    if not any(rp == a or rp.is_relative_to(a) for a in allowed):
        return None
    is_text = mime in TEXT_MIMES
    cap = MAX_TEXT_FILE_BYTES if is_text else MAX_FILE_BYTES
    try:
        st = rp.stat()
        if not rp.is_file() or st.st_size > cap:
            return None
        if mime in IMAGE_MIMES or mime == PDF_MIME or is_text or mime in _OFFICE_MIMES:
            with rp.open("rb") as f:
                head = f.read(1024)
            if is_text:
                if _looks_binary(head):
                    return None
            elif mime in _OFFICE_MIMES:
                if not head.startswith(b"PK\x03\x04"):
                    return None
            elif _detect_magic(head) != mime:
                return None
    except OSError:
        return None
    kind = "image" if mime in IMAGE_MIMES else "text" if is_text else _PRODUCED_KIND.get(mime, "file")
    return {
        "name": rp.name, "mime": mime, "size": int(st.st_size),
        "path": str(rp), "kind": kind, "source": "tool", "producer": producer,
    }


OUTPUT_ATTACHMENT_FIELDS = ("name", "mime", "size", "path", "kind", "source", "producer")
OUTPUT_ATTACHMENT_KINDS = frozenset({"image", "pdf", "text", "sheet", "doc", "deck", "file"})


def render_output_attachments(attachments: list | None) -> str:
    """One textual rendering of output attachments for every non-rich surface
    (CLI/TUI/ALP) so no surface loses or reinvents the list."""
    if not attachments:
        return ""
    lines = ["Attachments:"]
    for a in attachments:
        lines.append(f"- {a.get('mime', '')} {a.get('name', '')} {a.get('path', '')}".rstrip())
    return "\n".join(lines)


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
        if mime in ALLOWED_MIMES:
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
        out.append(Attachment(path=path, mime=mime or "application/octet-stream", name=name, size=size))
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


def model_context_tokens(model: str) -> int | None:
    try:
        import litellm
        n = litellm.get_model_info(model=model).get("max_input_tokens")
        return int(n) if n else None
    except Exception:  # noqa: BLE001 — unmapped model / litellm error → caller falls back
        return None


def resolve_max_text_chars(model: str, configured_tokens: int) -> int:
    if configured_tokens and configured_tokens > 0:
        tokens = configured_tokens
    else:
        window = model_context_tokens(model)
        tokens = int(window * AUTO_TEXT_WINDOW_FRACTION) if window else FALLBACK_TEXT_TOKENS
    return tokens * CHARS_PER_TOKEN


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


def build_content_parts(
    text: str,
    attachments: list[Attachment],
    *,
    vision: bool,
    scan_max_pages: int = SCAN_MAX_PAGES,
    max_image_bytes: int = MAX_IMAGE_PAYLOAD_BYTES,
    max_text_chars: int = MAX_TEXT_CHARS,
    on_progress=None,
) -> list[dict]:
    parts: list[dict] = []
    if text:
        parts.append(_text_part(text))
    if attachments:
        listing = "\n".join(f"  - {a.name} → {a.path}" for a in attachments)
        parts.append(_text_part(
            f"[{len(attachments)} file(s) are attached to this message; the available "
            "attachment content is included below. Use it directly — do NOT call "
            "filesystem or knowledge tools to look for them. If a tool or skill "
            "needs a file path on disk (e.g. image restore/enhance via --input), use "
            f"these absolute paths:\n{listing}]"
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
                parts.append(_text_part(
                    f"[{a.name}: not shown inline — this model has no image input. The file is "
                    f"at {a.path}; view it with a vision-capable tool or skill before acting on it.]"
                ))
                continue
            try:
                data = a.path.read_bytes()
            except OSError as e:
                raise AttachmentError(f"{a.name}: could not read file") from e
            if not add_image(a.mime, data):
                parts.append(_text_part(f"[{a.name}: omitted — turn image payload limit reached]"))
        elif is_pdf(a.mime):
            try:
                extracted, truncated = extract.extract_pdf_text(a.path, char_budget=max_text_chars)
            except Exception as e:  # noqa: BLE001 — corrupt/unsupported PDF
                raise AttachmentError(f"{a.name}: could not read PDF") from e
            if len(extracted.strip()) >= extract.SCANNED_PDF_TEXT_FLOOR:
                trunc = " (truncated)" if truncated else ""
                parts.append(_text_part(
                    f"--- attached PDF: {a.name}{trunc} ---\n{extracted}\n--- end of {a.name} ---"
                ))
            elif vision:
                try:
                    images, truncated = extract.render_pdf_images(a.path, max_pages=scan_max_pages)
                except Exception as e:  # noqa: BLE001
                    raise AttachmentError(f"{a.name}: could not render PDF") from e
                rendered = 0
                for img in images:
                    if not add_image("image/png", img):
                        break
                    rendered += 1
                caveats = []
                if truncated:
                    caveats.append(f"first {scan_max_pages} pages")
                if rendered < len(images):
                    caveats.append("image payload limit reached")
                if caveats:
                    parts.append(_text_part(
                        f"[{a.name}: {rendered} scanned page image(s) included — {', '.join(caveats)}]"
                    ))
            else:
                if on_progress:
                    on_progress(f"{a.name}: OCR (scanned PDF)…")
                try:
                    ocr_text, truncated = extract.ocr_pdf(
                        a.path, max_pages=scan_max_pages,
                        on_page=(lambda i, n: on_progress(f"{a.name}: OCR page {i}/{n}…")) if on_progress else None,
                    )
                except Exception as e:  # noqa: BLE001
                    raise AttachmentError(f"{a.name}: could not OCR scanned PDF") from e
                if ocr_text.strip():
                    over_budget = len(ocr_text) > max_text_chars
                    ocr_text = ocr_text[:max_text_chars]
                    marks = ["OCR"]
                    if truncated:
                        marks.append(f"first {scan_max_pages} pages")
                    if over_budget:
                        marks.append(f"truncated to {max_text_chars} chars")
                    parts.append(_text_part(
                        f"--- attached PDF: {a.name} ({', '.join(marks)}) ---\n{ocr_text}\n--- end of {a.name} ---"
                    ))
                else:
                    parts.append(_text_part(
                        f"[{a.name}: scanned PDF, OCR found no readable text — try a vision-capable model.]"
                    ))
        elif is_text(a.mime):
            try:
                body, truncated = _read_text(a.path, max_text_chars)
            except OSError as e:
                raise AttachmentError(f"{a.name}: could not read file") from e
            trunc = f" (truncated to {max_text_chars} chars)" if truncated else ""
            parts.append(_text_part(
                f"--- attached file: {a.name}{trunc} ---\n{body}\n--- end of {a.name} ---"
            ))
        else:
            parts.append(_text_part(
                f"[attached file {a.name} ({a.mime}, {a.size} bytes) is at {a.path} — "
                "not shown inline (binary/unknown type). Open it with a tool or skill "
                "if you need its contents.]"
            ))

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


def describe_produced(meta: list[dict] | None) -> str:
    if not meta:
        return ""
    items = ", ".join(
        f"{m.get('name')} → {m.get('path')}" for m in meta if m.get("path")
    )
    if not items:
        return ""
    return f"[produced this turn — reuse the absolute path for follow-up edits: {items}]"


def describe(attachments: list[Attachment]) -> str:
    return describe_meta(session_metadata(attachments))
