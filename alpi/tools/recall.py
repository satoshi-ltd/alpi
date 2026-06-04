from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from alpi.core import embed as embed_mod
from alpi.core.store import open_store, store_path
from alpi.home import get_home
from alpi.tools.base import Tool, ToolResult
from alpi.tools.workspace import EmbedderMismatch, _chunk_lines, _vec_blob

_EMBED_BATCH = 64
_MAX_SNIPPET = 600


def _get_meta(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute("SELECT value FROM session_meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def _set_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO session_meta(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )


def _ensure_schema(conn, dim, embedder_name, *, index_mode, force=False) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS session_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS session_files (
          session_id TEXT PRIMARY KEY,
          source_path TEXT NOT NULL,
          mtime REAL NOT NULL,
          size INTEGER NOT NULL,
          started_at REAL
        );
        CREATE TABLE IF NOT EXISTS session_chunks (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          session_id TEXT NOT NULL,
          chunk_index INTEGER NOT NULL,
          content TEXT NOT NULL,
          started_at REAL
        );
        CREATE INDEX IF NOT EXISTS session_chunks_by_session ON session_chunks(session_id);
        """
    )
    conn.execute(
        f"CREATE VIRTUAL TABLE IF NOT EXISTS session_vec USING vec0("
        f"chunk_id INTEGER PRIMARY KEY, embedding float[{dim}])"
    )
    stored_dim = _get_meta(conn, "dim")
    stored_embedder = _get_meta(conn, "embedder")
    if stored_dim is None:
        _set_meta(conn, "dim", str(dim))
        _set_meta(conn, "embedder", embedder_name)
        conn.commit()
        return
    drift = int(stored_dim) != dim or stored_embedder != embedder_name
    if not index_mode:
        if drift:
            raise EmbedderMismatch(
                f"Session index was built with {stored_embedder} (dim={stored_dim}) "
                f"but current embedder is {embedder_name} (dim={dim}). "
                f"Re-index: run index_sessions to rebuild."
            )
        return
    if not (force or drift):
        return
    conn.executescript(
        """
        DROP TABLE IF EXISTS session_vec;
        DROP TABLE IF EXISTS session_chunks;
        DROP TABLE IF EXISTS session_files;
        DELETE FROM session_meta;
        CREATE TABLE session_files (
          session_id TEXT PRIMARY KEY,
          source_path TEXT NOT NULL,
          mtime REAL NOT NULL,
          size INTEGER NOT NULL,
          started_at REAL
        );
        CREATE TABLE session_chunks (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          session_id TEXT NOT NULL,
          chunk_index INTEGER NOT NULL,
          content TEXT NOT NULL,
          started_at REAL
        );
        CREATE INDEX session_chunks_by_session ON session_chunks(session_id);
        """
    )
    conn.execute(
        f"CREATE VIRTUAL TABLE session_vec USING vec0("
        f"chunk_id INTEGER PRIMARY KEY, embedding float[{dim}])"
    )
    _set_meta(conn, "dim", str(dim))
    _set_meta(conn, "embedder", embedder_name)
    conn.commit()


def _delete_session(conn: sqlite3.Connection, session_id: str) -> None:
    ids = [
        row["id"]
        for row in conn.execute(
            "SELECT id FROM session_chunks WHERE session_id = ?", (session_id,)
        )
    ]
    if ids:
        placeholders = ",".join("?" * len(ids))
        conn.execute(f"DELETE FROM session_vec WHERE chunk_id IN ({placeholders})", ids)
        conn.execute("DELETE FROM session_chunks WHERE session_id = ?", (session_id,))
    conn.execute("DELETE FROM session_files WHERE session_id = ?", (session_id,))


def _transcript(data: dict) -> str:
    parts: list[str] = []
    for t in data.get("turns", []):
        user = (t.get("user") or "").strip()
        assistant = (t.get("assistant") or "").strip()
        if user:
            parts.append(f"user: {user}")
        if assistant:
            parts.append(f"alpi: {assistant}")
    return "\n".join(parts)


def index_sessions(
    home: Path,
    *,
    force: bool = False,
    embedder: embed_mod.Embedder | None = None,
    exclude_id: str | None = None,
) -> dict[str, Any]:
    embedder = embedder or embed_mod.default()
    sessions_dir = home / "sessions"
    conn = open_store(home)
    try:
        _ensure_schema(conn, embedder.dim, embedder.name, index_mode=True, force=force)
        indexed = skipped = removed = added = 0
        seen: set[str] = set()
        if sessions_dir.exists():
            for path in sessions_dir.glob("*.json"):
                try:
                    data = json.loads(path.read_text())
                except Exception:  # noqa: BLE001
                    continue
                sid = str(data.get("id") or path.stem)
                if exclude_id and sid == exclude_id:
                    continue
                seen.add(sid)
                stat = path.stat()
                mtime, size = stat.st_mtime, stat.st_size
                existing = conn.execute(
                    "SELECT mtime, size FROM session_files WHERE session_id = ?", (sid,),
                ).fetchone()
                if existing and abs(existing["mtime"] - mtime) < 1e-6 and existing["size"] == size:
                    skipped += 1
                    continue
                chunks = _chunk_lines(_transcript(data))
                started = data.get("started_at")
                _delete_session(conn, sid)
                conn.execute(
                    "INSERT INTO session_files(session_id, source_path, mtime, size, started_at) "
                    "VALUES(?, ?, ?, ?, ?)",
                    (sid, str(path), mtime, size, started),
                )
                if not chunks:
                    continue
                bodies = [c[2] for c in chunks]
                vectors: list[list[float]] = []
                for i in range(0, len(bodies), _EMBED_BATCH):
                    vectors.extend(embedder.embed(bodies[i:i + _EMBED_BATCH]))
                for chunk_idx, ((_ls, _le, body), vec) in enumerate(zip(chunks, vectors, strict=True)):
                    cur = conn.execute(
                        "INSERT INTO session_chunks(session_id, chunk_index, content, started_at) "
                        "VALUES(?, ?, ?, ?)",
                        (sid, chunk_idx, body, started),
                    )
                    conn.execute(
                        "INSERT INTO session_vec(chunk_id, embedding) VALUES(?, ?)",
                        (cur.lastrowid, _vec_blob(vec)),
                    )
                    added += 1
                indexed += 1
        # Orphan purge: a tracked session that's gone from disk and not seen this run is forgotten.
        for row in conn.execute("SELECT session_id, source_path FROM session_files").fetchall():
            sid = row["session_id"]
            if sid not in seen and not Path(row["source_path"]).exists():
                _delete_session(conn, sid)
                removed += 1
        conn.commit()
        total_sessions = conn.execute("SELECT COUNT(*) AS n FROM session_files").fetchone()["n"]
        total_chunks = conn.execute("SELECT COUNT(*) AS n FROM session_chunks").fetchone()["n"]
        return {
            "indexed_sessions": indexed,
            "skipped_sessions": skipped,
            "removed_sessions": removed,
            "added_chunks": added,
            "total_sessions": total_sessions,
            "total_chunks": total_chunks,
            "embedder": embedder.name,
            "dim": embedder.dim,
        }
    finally:
        conn.close()


def recall(
    home: Path,
    query: str,
    k: int,
    *,
    embedder: embed_mod.Embedder | None = None,
    exclude_id: str | None = None,
) -> list[dict[str, Any]]:
    embedder = embedder or embed_mod.default()
    conn = open_store(home)
    try:
        _ensure_schema(conn, embedder.dim, embedder.name, index_mode=False)
        if conn.execute("SELECT COUNT(*) AS n FROM session_chunks").fetchone()["n"] == 0:
            return []
        qvec = embedder.embed([query])[0]
        fetch = k + (8 if exclude_id else 0)
        rows = conn.execute(
            "SELECT c.session_id, c.content, c.started_at, v.distance "
            "FROM session_vec v JOIN session_chunks c ON c.id = v.chunk_id "
            "WHERE v.embedding MATCH ? AND k = ? ORDER BY v.distance",
            (_vec_blob(qvec), fetch),
        ).fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            if exclude_id and r["session_id"] == exclude_id:
                continue
            out.append({
                "session_id": r["session_id"],
                "when": _fmt_when(r["started_at"]),
                "snippet": r["content"][:_MAX_SNIPPET],
                "score": float(r["distance"]),
            })
            if len(out) >= k:
                break
        return out
    finally:
        conn.close()


def forget_session(home: Path, session_id: str) -> None:
    if not store_path(home).exists():
        return
    conn = open_store(home)
    try:
        _delete_session(conn, session_id)
        conn.commit()
    except sqlite3.OperationalError:
        pass
    finally:
        conn.close()


def _fmt_when(ts) -> str:
    if not ts:
        return "?"
    try:
        return datetime.fromtimestamp(float(ts)).strftime("%Y-%m-%d %H:%M")
    except Exception:  # noqa: BLE001
        return "?"


def _active_session_id() -> str | None:
    from alpi.tools import session_search
    return session_search._CURRENT_SESSION_ID


class IndexSessions(Tool):
    name = "index_sessions"
    description = (
        "Build (or refresh) the semantic index over past conversations so "
        "`recall_sessions` can answer free-form questions about them. Opt-in: "
        "sessions are NOT auto-indexed. Embeddings live in the profile's local "
        "store; nothing leaves the machine.\n"
        "\n"
        "Run this when `recall_sessions` reports an empty index, or after a bulk "
        "change to past sessions. Incremental — unchanged sessions are skipped, "
        "deleted ones are purged. `force=true` rebuilds from scratch. The active "
        "session is excluded."
    )
    parameters = {
        "type": "object",
        "properties": {
            "force": {
                "type": "boolean",
                "description": "Drop the session index and rebuild from scratch. Default false (incremental).",
                "default": False,
            },
        },
    }

    def run(self, force: bool = False) -> ToolResult:
        try:
            summary = index_sessions(get_home(), force=force, exclude_id=_active_session_id())
        except EmbedderMismatch as e:
            return ToolResult(ok=False, output="", error=str(e))
        return ToolResult(ok=True, output=json.dumps(summary))


class RecallSessions(Tool):
    name = "recall_sessions"
    description = (
        "Semantic search over past conversations — finds sessions by MEANING, "
        "not literal keywords. Use for \"when did we discuss X\", \"what did we "
        "decide about Y\", \"the conversation about Z\" when the wording is "
        "fuzzy.\n"
        "\n"
        "`session_search` (lexical) is the cheaper first layer for exact phrases; "
        "reach for `recall_sessions` when it misses or the match is by topic. "
        "Returns `[{session_id, when, snippet, score}]` (score = distance, lower "
        "is closer). If it reports an empty index, call `index_sessions` once, "
        "then retry. The active session is excluded."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Free-form natural-language query about a past conversation."},
            "k": {"type": "integer", "description": "How many results to return.", "default": 5},
        },
        "required": ["query"],
    }

    def run(self, query: str, k: int = 5) -> ToolResult:
        if not query or not query.strip():
            return ToolResult(ok=False, output="", error="Empty query.")
        if k < 1 or k > 50:
            return ToolResult(ok=False, output="", error="k must be in [1, 50].")
        try:
            results = recall(get_home(), query.strip(), k, exclude_id=_active_session_id())
        except EmbedderMismatch as e:
            return ToolResult(ok=False, output="", error=str(e))
        if not results:
            return ToolResult(ok=True, output=json.dumps(
                {"results": [], "hint": "Session index is empty. Run index_sessions first."}
            ))
        return ToolResult(ok=True, output=json.dumps({"results": results}))


TOOL_INDEX = IndexSessions
TOOL_RECALL = RecallSessions
