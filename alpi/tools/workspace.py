"""Local RAG over the user's workspace (BA in ROADMAP)."""

from __future__ import annotations

import json
import sqlite3
import struct
import threading
from pathlib import Path
from typing import Any, Iterable

from alpi.core import embed as embed_mod
from alpi.core.store import open_store
from alpi.home import get_home
from alpi.tools._paths import resolve_path
from alpi.tools.base import Tool, ToolResult


_MAX_TEXT_FILE_BYTES = 1_000_000
_MAX_BINARY_DOC_BYTES = 10_000_000
_MAX_IMAGE_BYTES = 20_000_000
_PDF_TEXT_FLOOR = 50
_LINES_PER_CHUNK = 30
_LINE_STRIDE = 25
_DEFAULT_GLOB = "**/*"

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

_ocr_reader_cache = None
_ocr_reader_lock = threading.Lock()

_SKIP_DIRS: frozenset[str] = frozenset({
    ".git", ".hg", ".svn",
    "node_modules", "__pycache__", ".venv", "venv", ".tox",
    "dist", "build", "target", ".next", ".cache",
    ".alpi",
})

def _vec_blob(vec: list[float]) -> bytes:
    return struct.pack(f"{len(vec)}f", *vec)


def _ensure_schema(
    conn: sqlite3.Connection,
    dim: int,
    embedder_name: str,
    force: bool = False,
) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS workspace_meta (
          key TEXT PRIMARY KEY,
          value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS workspace_files (
          source_path TEXT PRIMARY KEY,
          mtime REAL NOT NULL,
          size INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS workspace_chunks (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          source_path TEXT NOT NULL,
          chunk_index INTEGER NOT NULL,
          content TEXT NOT NULL,
          line_start INTEGER NOT NULL,
          line_end INTEGER NOT NULL
        );
        CREATE INDEX IF NOT EXISTS workspace_chunks_by_path
          ON workspace_chunks(source_path);
        """
    )
    conn.execute(
        f"CREATE VIRTUAL TABLE IF NOT EXISTS workspace_vec USING vec0("
        f"chunk_id INTEGER PRIMARY KEY, embedding float[{dim}])"
    )
    stored_dim = _get_meta(conn, "dim")
    stored_embedder = _get_meta(conn, "embedder")
    if stored_dim is None:
        _set_meta(conn, "dim", str(dim))
        _set_meta(conn, "embedder", embedder_name)
        conn.commit()
        return
    mismatch = int(stored_dim) != dim or stored_embedder != embedder_name
    if not mismatch:
        return
    if not force:
        raise EmbedderMismatch(
            f"Index was built with {stored_embedder} (dim={stored_dim}) "
            f"but current embedder is {embedder_name} (dim={dim}). "
            f"Re-index: index_workspace with force=true."
        )
    conn.executescript(
        """
        DROP TABLE IF EXISTS workspace_vec;
        DROP TABLE IF EXISTS workspace_chunks;
        DROP TABLE IF EXISTS workspace_files;
        DELETE FROM workspace_meta;
        CREATE TABLE workspace_files (
          source_path TEXT PRIMARY KEY,
          mtime REAL NOT NULL,
          size INTEGER NOT NULL
        );
        CREATE TABLE workspace_chunks (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          source_path TEXT NOT NULL,
          chunk_index INTEGER NOT NULL,
          content TEXT NOT NULL,
          line_start INTEGER NOT NULL,
          line_end INTEGER NOT NULL
        );
        CREATE INDEX workspace_chunks_by_path
          ON workspace_chunks(source_path);
        """
    )
    conn.execute(
        f"CREATE VIRTUAL TABLE workspace_vec USING vec0("
        f"chunk_id INTEGER PRIMARY KEY, embedding float[{dim}])"
    )
    _set_meta(conn, "dim", str(dim))
    _set_meta(conn, "embedder", embedder_name)
    conn.commit()


class EmbedderMismatch(RuntimeError):
    """Existing index was built with a different embedder."""


def _get_meta(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute(
        "SELECT value FROM workspace_meta WHERE key = ?", (key,)
    ).fetchone()
    return row["value"] if row else None


def _set_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO workspace_meta(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )


def _size_limit_for(suffix: str) -> int:
    if suffix in _IMAGE_SUFFIXES:
        return _MAX_IMAGE_BYTES
    if suffix in (_PDF_SUFFIXES | _DOCX_SUFFIXES | _EPUB_SUFFIXES):
        return _MAX_BINARY_DOC_BYTES
    return _MAX_TEXT_FILE_BYTES


def _iter_files(root: Path, glob: str) -> Iterable[Path]:
    for p in root.glob(glob):
        if not p.is_file():
            continue
        suffix = p.suffix.lower()
        if suffix not in _SUPPORTED_SUFFIXES:
            continue
        if any(part in _SKIP_DIRS for part in p.relative_to(root).parts[:-1]):
            continue
        try:
            if p.stat().st_size > _size_limit_for(suffix):
                continue
        except OSError:
            continue
        yield p


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _read_html(path: Path) -> str:
    import html2text

    h = html2text.HTML2Text()
    h.ignore_links = True
    h.ignore_images = True
    return h.handle(path.read_text(encoding="utf-8", errors="replace"))


class OcrRequired(RuntimeError):
    """The file needs OCR but the caller did not opt in."""


def _read_pdf(path: Path, ocr: bool = False) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    text = "\n\n".join(page.extract_text() or "" for page in reader.pages)
    if len(text.strip()) >= _PDF_TEXT_FLOOR:
        return text
    if not ocr:
        raise OcrRequired("scanned PDF — re-run index_workspace with ocr=true")
    return _ocr_pdf(path)


def _ocr_pdf(path: Path) -> str:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(path))
    try:
        parts: list[str] = []
        for page in pdf:
            pil = page.render(scale=2).to_pil()
            parts.append(_ocr_pil(pil))
        return "\n\n".join(parts)
    finally:
        pdf.close()


def _read_image(path: Path, ocr: bool = False) -> str:
    if not ocr:
        raise OcrRequired("image file — re-run index_workspace with ocr=true")
    from PIL import Image, ImageOps

    img = Image.open(path)
    img = ImageOps.exif_transpose(img)
    return _ocr_pil(img)


def _ocr_pil(pil_image) -> str:
    import numpy as np

    reader = _ocr_reader()
    arr = np.array(pil_image.convert("RGB"))
    result, _elapsed = reader(arr)
    if not result:
        return ""
    return "\n".join(text for _box, text, _score in result)


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


def _delete_file(conn: sqlite3.Connection, source_path: str) -> None:
    ids = [
        row["id"]
        for row in conn.execute(
            "SELECT id FROM workspace_chunks WHERE source_path = ?",
            (source_path,),
        )
    ]
    if ids:
        placeholders = ",".join("?" * len(ids))
        conn.execute(
            f"DELETE FROM workspace_vec WHERE chunk_id IN ({placeholders})",
            ids,
        )
        conn.execute(
            "DELETE FROM workspace_chunks WHERE source_path = ?",
            (source_path,),
        )
    conn.execute(
        "DELETE FROM workspace_files WHERE source_path = ?",
        (source_path,),
    )


def _index(
    root: Path,
    glob: str,
    force: bool,
    home: Path,
    ocr: bool = False,
    embedder: embed_mod.Embedder | None = None,
) -> dict[str, Any]:
    embedder = embedder or embed_mod.default()
    conn = open_store(home)
    try:
        _ensure_schema(conn, embedder.dim, embedder.name, force=force)
        indexed_files = 0
        skipped_files = 0
        added_chunks = 0
        failed_files: list[dict[str, str]] = []
        seen_paths: set[str] = set()
        for path in _iter_files(root, glob):
            rel = str(path.resolve())
            seen_paths.add(rel)
            stat = path.stat()
            mtime = stat.st_mtime
            size = stat.st_size
            existing = conn.execute(
                "SELECT mtime FROM workspace_files WHERE source_path = ?",
                (rel,),
            ).fetchone()
            if existing and not force and abs(existing["mtime"] - mtime) < 1e-6:
                skipped_files += 1
                continue
            reader = _reader_for(path.suffix.lower(), ocr=ocr)
            try:
                text = reader(path)
            except OcrRequired as e:
                failed_files.append({"path": rel, "reason": str(e)})
                continue
            except Exception as e:
                failed_files.append({"path": rel, "reason": str(e)[:200]})
                continue
            chunks = _chunk_lines(text)
            if not chunks:
                if path.suffix.lower() in (_PDF_SUFFIXES | _IMAGE_SUFFIXES):
                    failed_files.append({
                        "path": rel,
                        "reason": "OCR produced no text — image may be blank, illegible, or in an unsupported language",
                    })
                continue
            _delete_file(conn, rel)
            conn.execute(
                "INSERT INTO workspace_files(source_path, mtime, size) "
                "VALUES(?, ?, ?)",
                (rel, mtime, size),
            )
            bodies = [c[2] for c in chunks]
            vectors = embedder.embed(bodies)
            for chunk_idx, ((line_start, line_end, body), vec) in enumerate(
                zip(chunks, vectors, strict=True)
            ):
                cur = conn.execute(
                    "INSERT INTO workspace_chunks(source_path, chunk_index, "
                    "content, line_start, line_end) VALUES(?, ?, ?, ?, ?)",
                    (rel, chunk_idx, body, line_start, line_end),
                )
                chunk_id = cur.lastrowid
                conn.execute(
                    "INSERT INTO workspace_vec(chunk_id, embedding) VALUES(?, ?)",
                    (chunk_id, _vec_blob(vec)),
                )
                added_chunks += 1
            indexed_files += 1
        removed_files = 0
        root_prefix = str(root.resolve())
        scoped = conn.execute(
            "SELECT source_path FROM workspace_files WHERE source_path = ? "
            "OR source_path LIKE ?",
            (root_prefix, root_prefix + "/%"),
        ).fetchall()
        for row in scoped:
            sp = row["source_path"]
            if sp not in seen_paths:
                _delete_file(conn, sp)
                removed_files += 1
        conn.commit()
        if force:
            # _ensure_schema dropped the old tables, leaving every page in
            # the SQLite freelist — the file never shrinks back. VACUUM
            # after the rebuild commits compacts to the new index's real
            # size. Must run outside any transaction.
            prior_isolation = conn.isolation_level
            conn.isolation_level = None
            try:
                conn.execute("VACUUM")
            finally:
                conn.isolation_level = prior_isolation
        total_files = conn.execute(
            "SELECT COUNT(*) AS n FROM workspace_files"
        ).fetchone()["n"]
        total_chunks = conn.execute(
            "SELECT COUNT(*) AS n FROM workspace_chunks"
        ).fetchone()["n"]
        return {
            "root": str(root),
            "indexed_files": indexed_files,
            "skipped_files": skipped_files,
            "removed_files": removed_files,
            "added_chunks": added_chunks,
            "total_files": total_files,
            "total_chunks": total_chunks,
            "failed_files": failed_files,
            "embedder": embedder.name,
            "dim": embedder.dim,
        }
    finally:
        conn.close()


def _search(
    query: str,
    k: int,
    home: Path,
    embedder: embed_mod.Embedder | None = None,
) -> list[dict[str, Any]]:
    embedder = embedder or embed_mod.default()
    conn = open_store(home)
    try:
        _ensure_schema(conn, embedder.dim, embedder.name)
        if conn.execute(
            "SELECT COUNT(*) AS n FROM workspace_chunks"
        ).fetchone()["n"] == 0:
            return []
        qvec = embedder.embed([query])[0]
        rows = conn.execute(
            "SELECT c.source_path, c.content, c.line_start, c.line_end, "
            "v.distance FROM workspace_vec v JOIN workspace_chunks c "
            "ON c.id = v.chunk_id WHERE v.embedding MATCH ? AND k = ? "
            "ORDER BY v.distance",
            (_vec_blob(qvec), k),
        ).fetchall()
        return [
            {
                "path": r["source_path"],
                "snippet": r["content"],
                "line_start": r["line_start"],
                "line_end": r["line_end"],
                "score": float(r["distance"]),
            }
            for r in rows
        ]
    finally:
        conn.close()


class IndexWorkspace(Tool):
    name = "index_workspace"
    description = (
        "Build (or refresh) the semantic index over the user's local "
        "files so `search_workspace` can answer free-form questions about "
        "their content. Embeddings + index live in the profile's local "
        "store; nothing leaves the machine.\n"
        "\n"
        "Run this when:\n"
        "  • The user asks you to recall something from their files and "
        "`search_workspace` returns no results.\n"
        "  • The user explicitly asks to 'index my notes' or similar.\n"
        "  • After a known bulk change to their workspace.\n"
        "\n"
        "**Two modes:**\n"
        "  • Default (`ocr=false`, ~10s): markdown, plain text, source "
        "code, configs, HTML, DOCX, EPUB, and PDFs with a text layer. "
        "Scanned PDFs and image files (jpg/png/tiff/webp) land in "
        "`failed_files` with reason \"scanned PDF — re-run with "
        "ocr=true\".\n"
        "  • `ocr=true` (~30-90s+ depending on number of scans): "
        "everything above PLUS OCR over scanned PDFs and image files. "
        "Use when the user asks about content in photos, receipts, or "
        "image-only PDFs.\n"
        "\n"
        "Strategy: ALWAYS run the default (fast) pass first. Inspect "
        "the `failed_files` list. If the user's question likely needs "
        "those files (e.g., \"qué dice el recibo de…\"), call this "
        "tool again with `ocr=true`. Otherwise mention the deferred "
        "files in your answer so the user knows they exist.\n"
        "\n"
        "Incremental — files whose mtime hasn't moved are skipped. "
        "Skips .git, node_modules, build dirs. Limits: text 1 MB, "
        "binary docs 10 MB, images 20 MB."
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Root directory to walk. Defaults to the active workspace.",
            },
            "glob": {
                "type": "string",
                "description": "Glob filter relative to `path`. Default `**/*`.",
                "default": _DEFAULT_GLOB,
            },
            "force": {
                "type": "boolean",
                "description": "Re-embed every file even if mtime is unchanged.",
                "default": False,
            },
            "ocr": {
                "type": "boolean",
                "description": "Enable OCR for scanned PDFs and image files. Slow (~5-15s per scan) — only use when the user's question actually needs the image content.",
                "default": False,
            },
        },
    }

    def run(
        self,
        path: str | None = None,
        glob: str = _DEFAULT_GLOB,
        force: bool = False,
        ocr: bool = False,
    ) -> ToolResult:
        try:
            root = resolve_path(path) if path else _workspace_root()
        except ValueError as e:
            return ToolResult(ok=False, output="", error=str(e))
        if not root.exists() or not root.is_dir():
            return ToolResult(ok=False, output="", error=f"Not a directory: {root}")
        try:
            summary = _index(root, glob, force, home=get_home(), ocr=ocr)
        except EmbedderMismatch as e:
            return ToolResult(ok=False, output="", error=str(e))
        return ToolResult(ok=True, output=json.dumps(summary))


class SearchWorkspace(Tool):
    name = "search_workspace"
    description = (
        "**First tool to reach for when the user asks about their own "
        "files.** Semantic search across the user's workspace — notes, "
        "documents, labs, history, contracts, protocols, receipts, "
        "code they've authored. Returns top-K snippets ranked by "
        "meaning, not by literal match. Works across PDFs, DOCX, "
        "EPUB, images (OCR), and plain text.\n"
        "\n"
        "Examples that map to THIS tool (not `search`/`grep`):\n"
        "  • 'compara mis dos últimos blood panels'\n"
        "  • 'what did I write about the React migration?'\n"
        "  • 'qué suplementos tomo según mi protocolo más reciente'\n"
        "  • 'find the contract clause about renewal'\n"
        "  • 'show me receipts from last month'\n"
        "\n"
        "Use `search` (regex) only for literal-string code matches. "
        "Use `read_file` AFTER this tool surfaces a candidate path "
        "and you need the full passage.\n"
        "\n"
        "Returns `[{path, snippet, line_start, line_end, score}]` — "
        "score is cosine distance, lower is more similar. If the "
        "result hints `Run index_workspace first`, call "
        "`index_workspace` (no args needed when workspace is "
        "configured) and then retry this tool."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Free-form natural-language query."},
            "k": {
                "type": "integer",
                "description": "How many results to return.",
                "default": 5,
            },
        },
        "required": ["query"],
    }

    def run(self, query: str, k: int = 5) -> ToolResult:
        if not query or not query.strip():
            return ToolResult(ok=False, output="", error="Empty query.")
        if k < 1 or k > 50:
            return ToolResult(ok=False, output="", error="k must be in [1, 50].")
        try:
            results = _search(query.strip(), k, home=get_home())
        except EmbedderMismatch as e:
            return ToolResult(ok=False, output="", error=str(e))
        if not results:
            return ToolResult(
                ok=True,
                output=json.dumps({"results": [], "hint": "Index is empty. Run index_workspace first."}),
            )
        return ToolResult(ok=True, output=json.dumps({"results": results}))


def _workspace_root() -> Path:
    from alpi.tools._paths import _workspace_root as _wr

    return _wr()


TOOL_INDEX = IndexWorkspace
TOOL_SEARCH = SearchWorkspace
