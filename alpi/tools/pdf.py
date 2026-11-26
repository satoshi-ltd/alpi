from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path

from alpi.tools._paths import resolve_path
from alpi.tools.base import Tool, ToolResult

MAX_SOURCE_BYTES = 2_000_000
MAX_PDF_BYTES = 20 * 1024 * 1024


def _slug(text: str) -> str:
    stem = re.sub(r"\.pdf$", "", text.strip(), flags=re.I)
    stem = re.sub(r"[^\w-]+", "-", stem, flags=re.UNICODE).strip("-_").lower()
    while len(stem.encode("utf-8")) > 150:
        stem = stem[:-1]
    return stem.strip("-_")


def _destination(out_dir: Path, stem: str) -> Path:
    candidate = out_dir / f"{stem}.pdf"
    n = 2
    while candidate.exists():
        candidate = out_dir / f"{stem}-{n}.pdf"
        n += 1
    return candidate


class Pdf(Tool):
    name = "pdf"
    description = (
        "Make a PDF from Markdown and attach it to your reply. Supports headings, bold/italic, inline code, "
        "lists, quotes, tables, code blocks, links, `---` rules, ```chart blocks (drawn as tables) and "
        "`<!-- pagebreak -->` on its own line to start a new page. Pass the Markdown in `markdown`, or the "
        "`path` of a .md file you already wrote. The PDF is written as a new file in the profile's `out/` "
        "folder (never overwrites); `name` sets its file name, `title` the footer and document title "
        "(default: the first `#` heading). Say in one line what you attached; do not paste the document into "
        "your reply as well."
    )
    parameters = {
        "type": "object",
        "properties": {
            "markdown": {"type": "string", "description": "The document in Markdown."},
            "path": {"type": "string", "description": "A .md file to convert instead of `markdown`."},
            "name": {"type": "string", "description": "File name for the PDF, without folder."},
            "title": {"type": "string", "description": "Document title for the footer and metadata."},
        },
    }

    def run(self, markdown: str = "", path: str = "", name: str = "", title: str = "") -> ToolResult:
        from alpi.home import get_home
        from alpi.pdf import layout
        from alpi.tools import _state

        if bool(markdown) == bool(path):
            return ToolResult(ok=False, output="", error="pass either `markdown` or `path`, not both or neither")
        if path:
            try:
                source = resolve_path(path)
            except ValueError as exc:
                return ToolResult(ok=False, output="", error=str(exc))
            if not source.is_file():
                return ToolResult(ok=False, output="", error=f"no such file: {source}")
            if source.stat().st_size > MAX_SOURCE_BYTES:
                return ToolResult(ok=False, output="", error=f"{source} is over {MAX_SOURCE_BYTES:,} bytes")
            markdown = source.read_text(encoding="utf-8", errors="replace")
        try:
            rendered = layout.render(markdown, title=title)
        except layout.DocumentTooLarge as exc:
            return ToolResult(ok=False, output="", error=f"{exc}; split it into several PDFs")
        if len(rendered.data) > MAX_PDF_BYTES:
            return ToolResult(ok=False, output="", error="the PDF would be over 20 MiB; split it into several PDFs")
        stem = _slug(name) or f"{_slug(rendered.title) or 'document'}-{datetime.now().strftime('%Y%m%d-%H%M')}"
        candidate = _destination(get_home() / "out", stem)
        known = _state.is_turn_output(candidate.resolve())
        try:
            target = resolve_path(str(candidate), for_write=True)
        except ValueError as exc:
            return ToolResult(ok=False, output="", error=str(exc))
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        except OSError as exc:
            if not known:
                _state.forget_turn_output(target)
            if isinstance(exc, FileExistsError):
                return ToolResult(ok=False, output="", error=f"{target.name} appeared while writing; call pdf again")
            return ToolResult(ok=False, output="", error=f"cannot write {target}: {exc}")
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(rendered.data)
        except BaseException:
            target.unlink(missing_ok=True)
            if not known:
                _state.forget_turn_output(target)
            raise
        return ToolResult(
            ok=True,
            output=json.dumps({"out": str(target), "pages": rendered.pages})
            + f"\nPDF ready: {target.name}, {rendered.pages} page(s).",
        )


TOOL = Pdf
