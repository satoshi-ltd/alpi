from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from alpi import attachments as att
from alpi import config as cfg_mod
from alpi import llm
from alpi.core import embed as embed_mod
from alpi.core.store import open_store
from alpi.home import get_home
from alpi.tools import _state
from alpi.tools._paths import resolve_path
from alpi.tools.base import Tool, ToolResult
from alpi.tools.workspace import (
    EmbedderMismatch,
    OcrRequired,
    _chunk_lines,
    _reader_for,
    _vec_blob,
)


_KNOWLEDGE_REL = ("knowledge",)
_REQUIRED_FILES = ("index.md", "log.md")
_ALLOWED_TYPES = frozenset({"concept", "project", "person", "source", "note"})
_EMBED_BATCH = 64
_MAX_SNIPPET = 700
_DEFAULT_K = 5
_LINK_RE = re.compile(r"(?<!!)\[[^\]]+\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
_TOKEN_RE = re.compile(r"[A-Za-z0-9_]{2,}")
_INVISIBLE_RE = re.compile("[\u200B-\u200F\u202A-\u202E\u2060-\u206F\uFEFF]")
_SECRET_FINDING_TERMS = (
    "hardcoded",
    "openai-style key",
    "github pat",
    "aws access key id",
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _workspace_root_for(home: Path) -> Path:
    try:
        wp = cfg_mod.load(home.resolve()).workspace_path
    except Exception:  # noqa: BLE001
        wp = None
    return wp if wp is not None else Path.cwd().resolve()


def _knowledge_root(home: Path, path: str = "") -> Path:
    if path:
        return resolve_path(path)
    return _workspace_root_for(home).joinpath(*_KNOWLEDGE_REL).resolve()


def _rel(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _iter_pages(root: Path) -> list[Path]:
    if not root.exists() or not root.is_dir():
        return []
    return sorted(p for p in root.rglob("*.md") if p.is_file())


def _frontmatter_parts(text: str) -> tuple[dict[str, Any], str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("missing YAML frontmatter block")
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        raise ValueError("unterminated YAML frontmatter block")
    raw = "\n".join(lines[1:end]).strip()
    try:
        meta = yaml.safe_load(raw) or {}
    except yaml.YAMLError as e:
        raise ValueError(f"invalid YAML frontmatter: {e}") from e
    if not isinstance(meta, dict):
        raise ValueError("frontmatter must be a mapping")
    return meta, "\n".join(lines[end + 1:]).strip()


def _meta_issues(meta: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    page_type = meta.get("type")
    if page_type not in _ALLOWED_TYPES:
        issues.append(
            "frontmatter.type must be one of "
            + ", ".join(sorted(_ALLOWED_TYPES))
        )
    title = meta.get("title")
    if not isinstance(title, str) or not title.strip():
        issues.append("frontmatter.title must be a non-empty string")
    tags = meta.get("tags")
    if not isinstance(tags, list) or any(not isinstance(t, str) for t in tags):
        issues.append("frontmatter.tags must be a list of strings")
    updated_at = meta.get("updated_at")
    if not isinstance(updated_at, str) or not updated_at.strip():
        issues.append("frontmatter.updated_at must be a non-empty string")
    sources = meta.get("sources")
    if not isinstance(sources, list) or any(not isinstance(s, str) for s in sources):
        issues.append("frontmatter.sources must be a list of strings")
    return issues


def _parse_page(root: Path, path: Path) -> dict[str, Any]:
    rel = _rel(root, path)
    text = path.read_text(encoding="utf-8")
    meta, body = _frontmatter_parts(text)
    issues = _meta_issues(meta)
    if issues:
        raise ValueError("; ".join(issues))
    return {
        "path": rel,
        "meta": meta,
        "body": body,
        "text": text,
        "links": _extract_links(root, path, body),
    }


def _skip_href(href: str) -> bool:
    lower = href.lower()
    return (
        not href
        or href.startswith("#")
        or "://" in href
        or lower.startswith(("mailto:", "tel:", "data:"))
    )


def _extract_links(root: Path, page_path: Path, body: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for match in _LINK_RE.finditer(body):
        raw = match.group(1).strip()
        if _skip_href(raw):
            continue
        target_raw = raw.split("#", 1)[0].split("?", 1)[0]
        if not target_raw:
            continue
        target = (page_path.parent / target_raw).resolve()
        try:
            target_rel = target.relative_to(root.resolve()).as_posix()
        except ValueError:
            out.append({"raw": raw, "target": target_raw, "external": True})
            continue
        out.append({"raw": raw, "target": target_rel, "external": False})
    return out


def _issue(path: str, message: str) -> dict[str, str]:
    return {"path": path, "severity": "error", "message": message}


def lint_knowledge(root: Path) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    if not root.exists() or not root.is_dir():
        return {
            "ok": False,
            "root": str(root),
            "pages": 0,
            "issues": [_issue(".", "knowledge root does not exist")],
        }

    pages = _iter_pages(root)
    page_set = {_rel(root, p) for p in pages}
    for required in _REQUIRED_FILES:
        if required not in page_set:
            issues.append(_issue(required, "required OKF file is missing"))

    parsed: dict[str, dict[str, Any]] = {}
    inbound: dict[str, set[str]] = {rel: set() for rel in page_set}
    for path in pages:
        rel = _rel(root, path)
        try:
            parsed[rel] = _parse_page(root, path)
        except ValueError as e:
            issues.append(_issue(rel, str(e)))
            continue

    for rel, page in parsed.items():
        for link in page["links"]:
            target = link["target"]
            if link["external"] or target not in page_set:
                issues.append(_issue(rel, f"broken link: {link['raw']}"))
                continue
            if target != rel:
                inbound.setdefault(target, set()).add(rel)

    for rel in sorted(page_set):
        if rel in _REQUIRED_FILES:
            continue
        if not inbound.get(rel):
            issues.append(_issue(rel, "orphan page: no inbound links"))

    return {
        "ok": not issues,
        "root": str(root),
        "pages": len(pages),
        "issues": issues,
    }


def _get_meta(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute("SELECT value FROM okf_meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def _set_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO okf_meta(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )


def _create_tables(conn: sqlite3.Connection, dim: int) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS okf_files (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          path TEXT NOT NULL UNIQUE,
          mtime REAL NOT NULL,
          size INTEGER NOT NULL,
          title TEXT NOT NULL,
          type TEXT NOT NULL,
          tags TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          sources TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS okf_chunks (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          file_id INTEGER NOT NULL,
          path TEXT NOT NULL,
          chunk_index INTEGER NOT NULL,
          content TEXT NOT NULL,
          FOREIGN KEY(file_id) REFERENCES okf_files(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS okf_chunks_by_path ON okf_chunks(path);
        CREATE TABLE IF NOT EXISTS okf_links (
          source_path TEXT NOT NULL,
          target_path TEXT NOT NULL,
          raw_href TEXT NOT NULL,
          broken INTEGER NOT NULL DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS okf_links_by_source ON okf_links(source_path);
        CREATE INDEX IF NOT EXISTS okf_links_by_target ON okf_links(target_path);
        """
    )
    conn.execute(
        f"CREATE VIRTUAL TABLE IF NOT EXISTS okf_vec USING vec0("
        f"chunk_id INTEGER PRIMARY KEY, embedding float[{dim}])"
    )
    conn.execute(
        "CREATE VIRTUAL TABLE IF NOT EXISTS okf_fts "
        "USING fts5(path UNINDEXED, title, tags, content)"
    )


def _drop_tables(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        DROP TABLE IF EXISTS okf_vec;
        DROP TABLE IF EXISTS okf_fts;
        DROP TABLE IF EXISTS okf_links;
        DROP TABLE IF EXISTS okf_chunks;
        DROP TABLE IF EXISTS okf_files;
        """
    )


def _ensure_schema(
    conn: sqlite3.Connection,
    dim: int,
    embedder_name: str,
    *,
    root: str | None = None,
    force: bool = False,
    index_mode: bool = False,
) -> bool:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS okf_meta "
        "(key TEXT PRIMARY KEY, value TEXT NOT NULL)"
    )
    stored_dim = _get_meta(conn, "dim")
    stored_embedder = _get_meta(conn, "embedder")
    stored_root = _get_meta(conn, "knowledge_root")
    if stored_dim is None:
        _create_tables(conn, dim)
        _set_meta(conn, "dim", str(dim))
        _set_meta(conn, "embedder", embedder_name)
        if root is not None:
            _set_meta(conn, "knowledge_root", root)
        conn.commit()
        return False
    drift = int(stored_dim) != dim or stored_embedder != embedder_name
    if not index_mode:
        _create_tables(conn, int(stored_dim))
        if drift:
            raise EmbedderMismatch(
                f"Knowledge index was built with {stored_embedder} (dim={stored_dim}) "
                f"but current embedder is {embedder_name} (dim={dim}). "
                'Re-index: run knowledge(action="index") to rebuild.'
            )
        return False
    root_changed = root is not None and stored_root not in (None, root)
    if not (force or drift or root_changed):
        _create_tables(conn, dim)
        if root is not None and stored_root is None:
            _set_meta(conn, "knowledge_root", root)
            conn.commit()
        return False
    _drop_tables(conn)
    conn.execute("DELETE FROM okf_meta")
    _create_tables(conn, dim)
    _set_meta(conn, "dim", str(dim))
    _set_meta(conn, "embedder", embedder_name)
    if root is not None:
        _set_meta(conn, "knowledge_root", root)
    conn.commit()
    return True


def _delete_page(conn: sqlite3.Connection, rel_path: str) -> None:
    ids = [
        row["id"]
        for row in conn.execute(
            "SELECT id FROM okf_chunks WHERE path = ?", (rel_path,)
        )
    ]
    if ids:
        placeholders = ",".join("?" * len(ids))
        conn.execute(f"DELETE FROM okf_vec WHERE chunk_id IN ({placeholders})", ids)
        conn.execute(f"DELETE FROM okf_fts WHERE rowid IN ({placeholders})", ids)
        conn.execute("DELETE FROM okf_chunks WHERE path = ?", (rel_path,))
    conn.execute("DELETE FROM okf_links WHERE source_path = ? OR target_path = ?", (rel_path, rel_path))
    conn.execute("DELETE FROM okf_files WHERE path = ?", (rel_path,))


def _page_chunks(title: str, body: str) -> list[str]:
    content = f"# {title}\n\n{body.strip()}".strip()
    chunks = _chunk_lines(content)
    return [c[2] for c in chunks] or [title]


def index_knowledge(
    home: Path,
    root: Path,
    *,
    force: bool = False,
    embedder: embed_mod.Embedder | None = None,
) -> dict[str, Any]:
    embedder = embedder or embed_mod.default()
    root = root.resolve()
    conn = open_store(home)
    try:
        _ensure_schema(
            conn,
            embedder.dim,
            embedder.name,
            root=str(root),
            force=force,
            index_mode=True,
        )
        indexed = skipped = removed = added = 0
        failed: list[dict[str, str]] = []
        seen: set[str] = set()
        parsed_pages: dict[str, dict[str, Any]] = {}

        for path in _iter_pages(root):
            rel = _rel(root, path)
            seen.add(rel)
            try:
                page = _parse_page(root, path)
            except ValueError as e:
                if conn.execute("SELECT 1 FROM okf_files WHERE path = ?", (rel,)).fetchone():
                    _delete_page(conn, rel)
                    removed += 1
                failed.append({"path": rel, "reason": str(e)})
                continue
            parsed_pages[rel] = page
            stat = path.stat()
            mtime, size = stat.st_mtime, stat.st_size
            existing = conn.execute(
                "SELECT mtime, size FROM okf_files WHERE path = ?", (rel,)
            ).fetchone()
            if (
                existing
                and abs(existing["mtime"] - mtime) < 1e-6
                and existing["size"] == size
            ):
                skipped += 1
                continue
            meta = page["meta"]
            _delete_page(conn, rel)
            cur = conn.execute(
                "INSERT INTO okf_files(path, mtime, size, title, type, tags, updated_at, sources) "
                "VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    rel,
                    mtime,
                    size,
                    meta["title"].strip(),
                    meta["type"],
                    json.dumps(meta["tags"]),
                    meta["updated_at"],
                    json.dumps(meta["sources"]),
                ),
            )
            file_id = cur.lastrowid
            chunks = _page_chunks(meta["title"], page["body"])
            vectors: list[list[float]] = []
            for i in range(0, len(chunks), _EMBED_BATCH):
                vectors.extend(embedder.embed(chunks[i:i + _EMBED_BATCH]))
            tags_text = " ".join(meta["tags"])
            for chunk_idx, (body, vec) in enumerate(zip(chunks, vectors, strict=True)):
                ccur = conn.execute(
                    "INSERT INTO okf_chunks(file_id, path, chunk_index, content) "
                    "VALUES(?, ?, ?, ?)",
                    (file_id, rel, chunk_idx, body),
                )
                chunk_id = ccur.lastrowid
                conn.execute(
                    "INSERT INTO okf_vec(chunk_id, embedding) VALUES(?, ?)",
                    (chunk_id, _vec_blob(vec)),
                )
                conn.execute(
                    "INSERT INTO okf_fts(rowid, path, title, tags, content) "
                    "VALUES(?, ?, ?, ?, ?)",
                    (chunk_id, rel, meta["title"], tags_text, body),
                )
                added += 1
            indexed += 1

        for row in conn.execute("SELECT path FROM okf_files").fetchall():
            rel = row["path"]
            if rel not in seen:
                _delete_page(conn, rel)
                removed += 1

        valid_page_set = set(parsed_pages)
        conn.execute("DELETE FROM okf_links")
        for rel, page in parsed_pages.items():
            for link in page["links"]:
                conn.execute(
                    "INSERT INTO okf_links(source_path, target_path, raw_href, broken) "
                    "VALUES(?, ?, ?, ?)",
                    (
                        rel,
                        link["target"],
                        link["raw"],
                        1 if link["external"] or link["target"] not in valid_page_set else 0,
                    ),
                )

        conn.commit()
        total_pages = conn.execute("SELECT COUNT(*) AS n FROM okf_files").fetchone()["n"]
        total_chunks = conn.execute("SELECT COUNT(*) AS n FROM okf_chunks").fetchone()["n"]
        return {
            "root": str(root),
            "indexed_pages": indexed,
            "skipped_pages": skipped,
            "removed_pages": removed,
            "added_chunks": added,
            "total_pages": total_pages,
            "total_chunks": total_chunks,
            "failed_pages": failed,
            "embedder": embedder.name,
            "dim": embedder.dim,
        }
    finally:
        conn.close()


def _fts_query(query: str) -> str:
    tokens = _TOKEN_RE.findall(query)
    return " OR ".join(f'"{token}"' for token in tokens[:12])


def _page_links(conn: sqlite3.Connection, path: str) -> list[str]:
    return [
        row["target_path"]
        for row in conn.execute(
            "SELECT target_path FROM okf_links WHERE source_path = ? AND broken = 0 "
            "ORDER BY target_path",
            (path,),
        )
    ]


def _row_result(
    conn: sqlite3.Connection,
    row: sqlite3.Row,
    score: float,
) -> dict[str, Any]:
    try:
        tags = json.loads(row["tags"])
    except Exception:  # noqa: BLE001
        tags = []
    return {
        "path": row["path"],
        "title": row["title"],
        "type": row["type"],
        "tags": tags,
        "snippet": str(row["content"])[:_MAX_SNIPPET],
        "score": float(score),
        "links": _page_links(conn, row["path"]),
    }


def _normalized_lower_better(values: dict[str, float]) -> dict[str, float]:
    if not values:
        return {}
    low = min(values.values())
    high = max(values.values())
    if abs(high - low) < 1e-12:
        return {key: 1.0 for key in values}
    return {
        key: (high - value) / (high - low)
        for key, value in values.items()
    }


def _add_ranked_result(
    candidates: dict[str, dict[str, Any]],
    conn: sqlite3.Connection,
    row: sqlite3.Row,
    score: float,
) -> None:
    path = row["path"]
    if path not in candidates:
        candidates[path] = _row_result(conn, row, 0.0)
    candidates[path]["score"] = float(candidates[path]["score"]) + score


def search_knowledge(
    home: Path,
    query: str,
    k: int = _DEFAULT_K,
    *,
    embedder: embed_mod.Embedder | None = None,
) -> list[dict[str, Any]]:
    embedder = embedder or embed_mod.default()
    conn = open_store(home)
    try:
        _ensure_schema(conn, embedder.dim, embedder.name, index_mode=False)
        if conn.execute("SELECT COUNT(*) AS n FROM okf_chunks").fetchone()["n"] == 0:
            return []
        candidates: dict[str, dict[str, Any]] = {}

        qvec = embedder.embed([query])[0]
        rows = conn.execute(
            "SELECT f.path, f.title, f.type, f.tags, c.content, v.distance "
            "FROM okf_vec v JOIN okf_chunks c ON c.id = v.chunk_id "
            "JOIN okf_files f ON f.id = c.file_id "
            "WHERE v.embedding MATCH ? AND k = ? ORDER BY v.distance",
            (_vec_blob(qvec), max(k * 3, k)),
        ).fetchall()
        vector_rows: dict[str, sqlite3.Row] = {}
        vector_distances: dict[str, float] = {}
        for row in rows:
            path = row["path"]
            distance = float(row["distance"])
            if path not in vector_distances or distance < vector_distances[path]:
                vector_rows[path] = row
                vector_distances[path] = distance
        for path, score in _normalized_lower_better(vector_distances).items():
            _add_ranked_result(candidates, conn, vector_rows[path], score)

        fts = _fts_query(query)
        if fts:
            try:
                fts_rows = conn.execute(
                    "SELECT f.path, f.title, f.type, f.tags, c.content, bm25(okf_fts) AS rank "
                    "FROM okf_fts JOIN okf_chunks c ON c.id = okf_fts.rowid "
                    "JOIN okf_files f ON f.id = c.file_id "
                    "WHERE okf_fts MATCH ? ORDER BY rank LIMIT ?",
                    (fts, max(k * 3, k)),
                ).fetchall()
            except sqlite3.OperationalError:
                fts_rows = []
            fts_best_rows: dict[str, sqlite3.Row] = {}
            fts_ranks: dict[str, float] = {}
            for row in fts_rows:
                path = row["path"]
                rank = float(row["rank"])
                if path not in fts_ranks or rank < fts_ranks[path]:
                    fts_best_rows[path] = row
                    fts_ranks[path] = rank
            for path, score in _normalized_lower_better(fts_ranks).items():
                _add_ranked_result(candidates, conn, fts_best_rows[path], score)

        return sorted(candidates.values(), key=lambda r: (-r["score"], r["path"]))[:k]
    finally:
        conn.close()


def _safe_rel_page(path: str) -> str:
    raw = str(path or "").strip()
    if not raw:
        raise ValueError("page path is required")
    p = Path(raw)
    if p.is_absolute() or ".." in p.parts:
        raise ValueError(f"page path must stay inside the knowledge bundle: {raw}")
    if p.name in _REQUIRED_FILES:
        raise ValueError(f"{p.name} is managed by knowledge(action='maintain')")
    if p.suffix.lower() != ".md":
        p = p.with_suffix(".md")
    clean_parts = []
    for part in p.parts:
        cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", part).strip(".-")
        if not cleaned or cleaned != part:
            raise ValueError(f"invalid path segment in {raw!r}")
        clean_parts.append(cleaned)
    return Path(*clean_parts).as_posix()


def _render_page(meta: dict[str, Any], body: str) -> str:
    frontmatter = yaml.safe_dump(meta, sort_keys=False, allow_unicode=True).strip()
    return f"---\n{frontmatter}\n---\n\n{body.strip()}\n"


def _default_page(page_type: str, title: str, body: str = "") -> str:
    return _render_page(
        {
            "type": page_type,
            "title": title,
            "tags": [],
            "updated_at": _now_iso(),
            "sources": [],
        },
        body or f"# {title}\n",
    )


def _ensure_bundle(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for folder in ("concepts", "projects", "people", "sources"):
        (root / folder).mkdir(exist_ok=True)
    index = root / "index.md"
    if not index.exists():
        index.write_text(
            _default_page("note", "Knowledge Index", "# Knowledge Index\n\n## Pages\n"),
            encoding="utf-8",
        )
    log = root / "log.md"
    if not log.exists():
        log.write_text(
            _default_page("note", "Knowledge Log", "# Knowledge Log\n"),
            encoding="utf-8",
        )


def _read_source(path: Path, *, ocr: bool = False) -> str:
    suffix = path.suffix.lower()
    try:
        return _reader_for(suffix, ocr=ocr)(path)
    except OcrRequired as e:
        raise ValueError(str(e)) from e


def _source_ref(root: Path, source: Path | None) -> str:
    if source is None:
        return ""
    try:
        return source.resolve().relative_to(root.parent.resolve()).as_posix()
    except ValueError:
        return f"input:{source.name}"


def _resolve_source(name: str, source_path: str) -> tuple[Path, str]:
    if source_path:
        src = resolve_path(source_path)
        if not src.is_file():
            raise ValueError(f"file not found: {source_path}")
        return src, src.name
    attachments = _state.get_turn_attachments()
    if name:
        matches = [a for a in attachments if a.get("name") == name]
        if not matches:
            raise ValueError(f"no attachment named {name!r} in this turn; attach it or pass source_path")
        if len(matches) > 1:
            raise ValueError(f"multiple attachments named {name!r}; pass source_path to disambiguate")
        chosen = matches[0]
        return Path(chosen["path"]), chosen.get("name") or Path(chosen["path"]).name
    if len(attachments) == 1:
        chosen = attachments[0]
        return Path(chosen["path"]), chosen.get("name") or Path(chosen["path"]).name
    if not attachments:
        raise ValueError("no file to ingest: attach a file or pass source_path")
    names = ", ".join(a.get("name", "?") for a in attachments)
    raise ValueError(f"multiple files attached ({names}); specify which with name= or source_path=")


def _validated_source(name: str, source_path: str, *, ocr: bool) -> tuple[Path, att.Attachment]:
    src, original_name = _resolve_source(name, source_path)
    try:
        validated = att.validate([{"path": str(src), "name": original_name}])
    except att.AttachmentError as e:
        raise ValueError(str(e)) from e
    meta = validated[0]
    if att.is_image(meta.mime) and not ocr:
        raise ValueError(f"{meta.name}: images are only ingestible with ocr=true")
    return src, meta


def _parse_llm_json(text: str) -> dict[str, Any]:
    body = (text or "").strip()
    if body.startswith("```"):
        body = re.sub(r"^```(?:json)?\s*", "", body)
        body = re.sub(r"\s*```$", "", body)
    try:
        obj = json.loads(body)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM returned invalid JSON: {e}") from e
    if not isinstance(obj, dict):
        raise ValueError("LLM response must be a JSON object")
    return obj


def _strip_invisible(text: str) -> str:
    return _INVISIBLE_RE.sub("", text)


def _knowledge_safety_findings(text: str) -> list[str]:
    from alpi.scan import scan_injection, scan_memory_content

    findings = scan_memory_content(text)
    out = [
        f for f in findings
        if any(term in f.lower() for term in _SECRET_FINDING_TERMS)
    ]
    if scan_injection(text):
        out.append("prompt injection")
    return out


def _apply_maintenance(root: Path, proposal: dict[str, Any], source_ref: str) -> dict[str, Any]:
    _ensure_bundle(root)
    pages = proposal.get("pages") or []
    if not isinstance(pages, list):
        raise ValueError("proposal.pages must be a list")
    written: list[str] = []
    for raw_page in pages:
        if not isinstance(raw_page, dict):
            raise ValueError("each proposed page must be an object")
        rel = _safe_rel_page(str(raw_page.get("path") or ""))
        page_type = str(raw_page.get("type") or "note")
        if page_type not in _ALLOWED_TYPES:
            raise ValueError(f"{rel}: invalid type {page_type!r}")
        title = _strip_invisible(str(raw_page.get("title") or Path(rel).stem.replace("-", " ").title())).strip()
        tags = raw_page.get("tags") or []
        sources = raw_page.get("sources") or []
        if source_ref and source_ref not in sources:
            sources = [*sources, source_ref]
        body = _strip_invisible(str(raw_page.get("body") or "")).strip()
        if not body:
            body = f"# {title}\n"
        meta = {
            "type": page_type,
            "title": title,
            "tags": [_strip_invisible(str(t)).strip() for t in tags if _strip_invisible(str(t)).strip()],
            "updated_at": _now_iso(),
            "sources": [_strip_invisible(str(s)).strip() for s in sources if _strip_invisible(str(s)).strip()],
        }
        rendered = _render_page(meta, body)
        findings = _knowledge_safety_findings(rendered)
        if findings:
            raise ValueError(f"{rel}: refused to write unsafe knowledge content: {', '.join(findings)}")
        target = (root / rel).resolve()
        if not str(target).startswith(str(root.resolve())):
            raise ValueError(f"{rel}: resolved path escapes knowledge bundle")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered, encoding="utf-8")
        written.append(rel)

    if written:
        _update_index(root, written)
    log_text = str(proposal.get("log") or "").strip()
    _append_log(root, log_text or f"Updated {', '.join(written) if written else 'knowledge bundle'}.")
    return {"written": written}


def _update_index(root: Path, pages: list[str]) -> None:
    index = root / "index.md"
    if not index.exists():
        index.write_text(
            _default_page("note", "Knowledge Index", "# Knowledge Index\n\n## Pages\n"),
            encoding="utf-8",
        )
    text = index.read_text(encoding="utf-8")
    additions: list[str] = []
    for rel in pages:
        if f"]({rel})" in text:
            continue
        try:
            page = _parse_page(root, root / rel)
            title = page["meta"]["title"]
        except Exception:  # noqa: BLE001
            title = Path(rel).stem.replace("-", " ").title()
        additions.append(f"- [{title}]({rel})")
    if additions:
        index.write_text(text.rstrip() + "\n" + "\n".join(additions) + "\n", encoding="utf-8")


def _append_log(root: Path, line: str) -> None:
    log = root / "log.md"
    if not log.exists():
        log.write_text(
            _default_page("note", "Knowledge Log", "# Knowledge Log\n"),
            encoding="utf-8",
        )
    text = log.read_text(encoding="utf-8")
    entry = f"\n- {_now_iso()} - {line.strip()}\n"
    log.write_text(text.rstrip() + entry, encoding="utf-8")


_MAINTAIN_PROMPT = """You maintain an OKF-style local Markdown knowledge bundle.

Return one JSON object only, no prose and no fences:
{
  "pages": [
    {
      "path": "concepts/example.md",
      "type": "concept|project|person|source|note",
      "title": "Human title",
      "tags": ["short", "lowercase"],
      "sources": ["optional source reference"],
      "body": "# Human title\\n\\nConcise Markdown synthesis with relative links when useful."
    }
  ],
  "log": "One short sentence describing the maintenance change."
}

Prefer updating a small number of durable concept/project/person/source pages.
Do not include secrets, credentials, API keys, tokens, or raw private data.
Do not create pages for ephemeral session state.
"""


def maintain_knowledge(
    home: Path,
    root: Path,
    *,
    source_path: str = "",
    topic: str = "",
    apply: bool = True,
    ocr: bool = False,
    source_text: str | None = None,
    source_ref: str = "",
) -> dict[str, Any]:
    source = resolve_path(source_path) if source_path else None
    if source is not None and not source.is_file():
        raise ValueError(f"source file not found: {source_path}")
    if source is not None:
        try:
            validated = att.validate([{"path": str(source), "name": source.name}])
        except att.AttachmentError as e:
            raise ValueError(str(e)) from e
        if att.is_image(validated[0].mime) and not ocr:
            raise ValueError(f"{validated[0].name}: images are only ingestible with ocr=true")
    if source is None and source_text is None and not topic.strip():
        raise ValueError("source_path or topic is required")
    if source_text is None:
        source_text = _read_source(source, ocr=ocr) if source is not None else ""
    source_ref = source_ref or _source_ref(root, source)
    related = []
    if topic.strip():
        try:
            related = search_knowledge(home, topic.strip(), k=3)
        except EmbedderMismatch:
            raise
        except Exception:  # noqa: BLE001
            related = []
    cfg = cfg_mod.load(home)
    messages = [
        {"role": "system", "content": _MAINTAIN_PROMPT},
        {
            "role": "user",
            "content": json.dumps({
                "topic": topic.strip(),
                "source_ref": source_ref,
                "source_excerpt": source_text[:12000],
                "related_pages": related,
            }),
        },
    ]
    completion = llm.complete(messages=messages, **cfg_mod.resolve_model(cfg))
    proposal = _parse_llm_json(completion.content)
    if not apply:
        return {"applied": False, "proposal": proposal}
    applied = _apply_maintenance(root, proposal, source_ref)
    lint = lint_knowledge(root)
    return {"applied": True, "proposal": proposal, "lint": lint, **applied}


def ingest_knowledge(
    home: Path,
    root: Path,
    *,
    name: str = "",
    source_path: str = "",
    topic: str = "",
    apply: bool = True,
    ocr: bool = False,
) -> dict[str, Any]:
    source, meta = _validated_source(name, source_path, ocr=ocr)
    text = _read_source(source, ocr=ocr)
    result = maintain_knowledge(
        home,
        root,
        topic=topic.strip() or f"Ingest {meta.name}",
        apply=apply,
        ocr=ocr,
        source_text=text,
        source_ref=_source_ref(root, source),
    )
    result["source"] = {
        "name": meta.name,
        "mime": meta.mime,
        "size": meta.size,
        "saved": False,
    }
    return result


def _maybe_index_after_apply(home: Path, root: Path, result: dict[str, Any]) -> dict[str, Any]:
    if result.get("applied") is True:
        result["index"] = index_knowledge(home, root)
    return result


class Knowledge(Tool):
    name = "knowledge"
    description = (
        "Work with the user's workspace knowledge wiki. Actions: search durable "
        "OKF Markdown pages, ingest a source file into synthesized Markdown "
        "without saving the raw source, maintain pages explicitly, lint the "
        "bundle, or rebuild the derived SQLite index. Use alpi_knowledge "
        "instead for questions about alpi itself."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["search", "ingest", "maintain", "lint", "index"],
                "description": "Operation to run.",
            },
            "query": {
                "type": "string",
                "description": "Natural-language query for action='search'.",
            },
            "k": {
                "type": "integer",
                "description": "How many pages to return for action='search'.",
                "default": _DEFAULT_K,
            },
            "name": {
                "type": "string",
                "description": "Attachment filename for action='ingest' when source_path is omitted.",
            },
            "source_path": {
                "type": "string",
                "description": "Source file to synthesize for action='ingest' or action='maintain'. The raw file is read, not copied.",
            },
            "topic": {
                "type": "string",
                "description": "Topic or maintenance instruction for action='ingest' or action='maintain'.",
            },
            "path": {
                "type": "string",
                "description": "Knowledge root. Defaults to <workspace>/knowledge.",
            },
            "force": {
                "type": "boolean",
                "description": "Drop and rebuild the OKF index for action='index'.",
                "default": False,
            },
            "apply": {
                "type": "boolean",
                "description": "For maintain/ingest, false returns the proposal without writing.",
                "default": True,
            },
            "ocr": {
                "type": "boolean",
                "description": "Enable OCR for scanned PDFs and image inputs during ingest/maintain.",
                "default": False,
            },
        },
        "required": ["action"],
    }

    def run(
        self,
        action: str,
        query: str = "",
        k: int = _DEFAULT_K,
        name: str = "",
        source_path: str = "",
        topic: str = "",
        path: str = "",
        force: bool = False,
        apply: bool = True,
        ocr: bool = False,
    ) -> ToolResult:
        action = (action or "").strip().lower()
        root = _knowledge_root(get_home(), path)
        try:
            if action == "search":
                if not query or not query.strip():
                    return ToolResult(ok=False, output="", error="Empty query.")
                if k < 1 or k > 50:
                    return ToolResult(ok=False, output="", error="k must be in [1, 50].")
                results = search_knowledge(get_home(), query.strip(), k)
                if not results:
                    return ToolResult(
                        ok=True,
                        output=json.dumps({
                            "results": [],
                            "hint": 'Knowledge index is empty. Run knowledge(action="index") first.',
                        }),
                    )
                return ToolResult(ok=True, output=json.dumps({"results": results}))
            if action == "index":
                if not root.exists() or not root.is_dir():
                    return ToolResult(ok=False, output="", error=f"Not a directory: {root}")
                return ToolResult(
                    ok=True,
                    output=json.dumps(index_knowledge(get_home(), root, force=force)),
                )
            if action == "lint":
                return ToolResult(ok=True, output=json.dumps(lint_knowledge(root)))
            if action == "maintain":
                result = maintain_knowledge(
                    get_home(),
                    root,
                    source_path=source_path,
                    topic=topic,
                    apply=apply,
                    ocr=ocr,
                )
                return ToolResult(
                    ok=True,
                    output=json.dumps(_maybe_index_after_apply(get_home(), root, result)),
                )
            if action == "ingest":
                result = ingest_knowledge(
                    get_home(),
                    root,
                    name=name,
                    source_path=source_path,
                    topic=topic,
                    apply=apply,
                    ocr=ocr,
                )
                return ToolResult(
                    ok=True,
                    output=json.dumps(_maybe_index_after_apply(get_home(), root, result)),
                )
            return ToolResult(ok=False, output="", error=f"unknown knowledge action: {action}")
        except EmbedderMismatch as e:
            return ToolResult(ok=False, output="", error=str(e))
        except ValueError as e:
            return ToolResult(ok=False, output="", error=str(e))


TOOL = Knowledge
