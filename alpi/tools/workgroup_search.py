from __future__ import annotations

import json
import math
import sqlite3
import struct
from pathlib import Path
from typing import Any

from alpi.core import embed as embed_mod
from alpi.core.store import open_store, store_path
from alpi.home import get_home
from alpi.tools.base import Tool, ToolResult
from alpi.tools.workspace import EmbedderMismatch, _vec_blob

_CHUNK_CHARS = 2000
_MAX_SNIPPET = 700


def _wg_dir(home: Path, wg_id: str) -> Path:
    return home / "alp" / "workgroups" / wg_id


def _transcript_path(home: Path, wg_id: str) -> Path:
    return _wg_dir(home, wg_id) / "transcript.jsonl"


def _get_meta(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute("SELECT value FROM workgroup_meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def _set_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO workgroup_meta(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )


def _recreate_tables(conn, dim) -> None:
    conn.executescript(
        """
        DROP TABLE IF EXISTS workgroup_vec;
        DROP TABLE IF EXISTS workgroup_chunks;
        DROP TABLE IF EXISTS workgroup_files;
        CREATE TABLE workgroup_files (
          workgroup_id TEXT PRIMARY KEY,
          transcript_path TEXT NOT NULL,
          mtime REAL NOT NULL,
          size INTEGER NOT NULL,
          head_seq INTEGER NOT NULL
        );
        CREATE TABLE workgroup_chunks (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          workgroup_id TEXT NOT NULL,
          seq_start INTEGER NOT NULL,
          seq_end INTEGER NOT NULL,
          ts_start TEXT,
          ts_end TEXT,
          authors TEXT NOT NULL,
          content TEXT NOT NULL
        );
        CREATE INDEX workgroup_chunks_by_wg ON workgroup_chunks(workgroup_id);
        """
    )
    conn.execute(
        f"CREATE VIRTUAL TABLE workgroup_vec USING vec0("
        f"chunk_id INTEGER PRIMARY KEY, embedding float[{dim}])"
    )


def _ensure_schema(conn, dim, embedder_name, *, index_mode) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS workgroup_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS workgroup_files (
          workgroup_id TEXT PRIMARY KEY,
          transcript_path TEXT NOT NULL,
          mtime REAL NOT NULL,
          size INTEGER NOT NULL,
          head_seq INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS workgroup_chunks (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          workgroup_id TEXT NOT NULL,
          seq_start INTEGER NOT NULL,
          seq_end INTEGER NOT NULL,
          ts_start TEXT,
          ts_end TEXT,
          authors TEXT NOT NULL,
          content TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS workgroup_chunks_by_wg ON workgroup_chunks(workgroup_id);
        """
    )
    conn.execute(
        f"CREATE VIRTUAL TABLE IF NOT EXISTS workgroup_vec USING vec0("
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
                f"Workgroup index was built with {stored_embedder} (dim={stored_dim}) "
                f"but current embedder is {embedder_name} (dim={dim}). "
                f"Re-index: run index_workgroups to rebuild."
            )
        return
    if not drift:
        return
    # Embedder/dim drift → the whole vec table is the wrong shape; only this forces a global rebuild.
    _recreate_tables(conn, dim)
    conn.execute("DELETE FROM workgroup_meta")
    _set_meta(conn, "dim", str(dim))
    _set_meta(conn, "embedder", embedder_name)
    conn.commit()


def _delete_workgroup(conn: sqlite3.Connection, wg_id: str) -> None:
    ids = [
        row["id"]
        for row in conn.execute(
            "SELECT id FROM workgroup_chunks WHERE workgroup_id = ?", (wg_id,)
        )
    ]
    if ids:
        placeholders = ",".join("?" * len(ids))
        conn.execute(f"DELETE FROM workgroup_vec WHERE chunk_id IN ({placeholders})", ids)
        conn.execute("DELETE FROM workgroup_chunks WHERE workgroup_id = ?", (wg_id,))
    conn.execute("DELETE FROM workgroup_files WHERE workgroup_id = ?", (wg_id,))


def _is_indexable(body: str) -> bool:
    b = body.strip()
    if not b:
        return False
    # Posts that didn't decrypt (rotated-out key, AEAD failure) carry a placeholder, not content.
    return not (b.startswith("[decrypt failed") or (b.startswith("[v") and "key rotated" in b))


def _post_block(post: dict) -> str:
    seq = int(post.get("seq", 0))
    ts = str(post.get("at") or "")
    author = post.get("from") or post.get("from_pubkey") or "?"
    return f"[seq {seq} · {ts} · {author}]\n{post.get('body', '').strip()}"


def _chunk_posts(posts: list[dict], cap: int = _CHUNK_CHARS) -> list[dict]:
    chunks: list[dict] = []
    buf: list[str] = []
    authors: set[str] = set()
    seq_start = seq_end = None
    ts_start = ts_end = None

    def flush() -> None:
        nonlocal buf, authors, seq_start, seq_end, ts_start, ts_end
        if buf:
            chunks.append({
                "seq_start": seq_start, "seq_end": seq_end,
                "ts_start": ts_start, "ts_end": ts_end,
                "authors": sorted(authors), "content": "\n\n".join(buf),
            })
        buf, authors = [], set()
        seq_start = seq_end = ts_start = ts_end = None

    for post in posts:
        body = str(post.get("body") or "")
        if not _is_indexable(body):
            continue
        seq = int(post.get("seq", 0))
        ts = str(post.get("at") or "")
        author = str(post.get("from") or post.get("from_pubkey") or "?")
        block = _post_block(post)
        if len(block) > cap:
            flush()
            for piece in _split_block(block, cap):
                chunks.append({
                    "seq_start": seq, "seq_end": seq, "ts_start": ts, "ts_end": ts,
                    "authors": [author], "content": piece,
                })
            continue
        if buf and sum(len(b) + 2 for b in buf) + len(block) > cap:
            flush()
        buf.append(block)
        authors.add(author)
        if seq_start is None:
            seq_start, ts_start = seq, ts
        seq_end, ts_end = seq, ts
    flush()
    return chunks


def _split_block(block: str, cap: int) -> list[str]:
    out: list[str] = []
    cur: list[str] = []
    size = 0
    for line in block.splitlines():
        if size + len(line) + 1 > cap and cur:
            out.append("\n".join(cur))
            cur, size = [], 0
        cur.append(line)
        size += len(line) + 1
    if cur:
        out.append("\n".join(cur))
    return out


def _hub_targets(home: Path, workgroup_id: str) -> list[str]:
    from alpi.alp import workgroup as wg_mod
    from alpi.alp.keys import load_or_generate

    own = load_or_generate(home).pubkey_b64()
    if workgroup_id:
        wg = wg_mod.load(home, workgroup_id)
        if wg is None:
            raise ValueError(f"workgroup {workgroup_id!r} not found locally")
        if wg.meta.hub_pubkey != own:
            raise ValueError(
                f"only the hub can index {workgroup_id!r} — workgroup search is hub-owned"
            )
        return [workgroup_id]
    return [wg.meta.id for wg in wg_mod.list_workgroups(home) if wg.meta.hub_pubkey == own]


def index_workgroups(
    home: Path,
    workgroup_id: str = "",
    *,
    force: bool = False,
    embedder: embed_mod.Embedder | None = None,
) -> dict[str, Any]:
    from alpi.host import workgroup as host_wg

    embedder = embedder or embed_mod.default()
    targets = _hub_targets(home, workgroup_id)
    conn = open_store(home)
    try:
        _ensure_schema(conn, embedder.dim, embedder.name, index_mode=True)
        # force is scoped: a global rebuild only when no workgroup_id was given.
        if force and not workgroup_id:
            _recreate_tables(conn, embedder.dim)
            conn.commit()
        indexed = skipped = removed = added = 0
        failed: list[dict[str, str]] = []
        seen: set[str] = set()
        for wg_id in targets:
            seen.add(wg_id)
            tpath = _transcript_path(home, wg_id)
            if not tpath.exists():
                continue
            stat = tpath.stat()
            mtime, size = stat.st_mtime, stat.st_size
            existing = conn.execute(
                "SELECT mtime, size FROM workgroup_files WHERE workgroup_id = ?", (wg_id,),
            ).fetchone()
            if not force and existing and abs(existing["mtime"] - mtime) < 1e-6 and existing["size"] == size:
                skipped += 1
                continue
            try:
                posts = host_wg.decrypt_transcript(home, wg_id)
            except Exception as e:  # noqa: BLE001
                failed.append({"workgroup_id": wg_id, "reason": str(e)[:200]})
                continue
            chunks = _chunk_posts(posts)
            head_seq = max((int(p.get("seq", 0)) for p in posts), default=0)
            _delete_workgroup(conn, wg_id)
            conn.execute(
                "INSERT INTO workgroup_files(workgroup_id, transcript_path, mtime, size, head_seq) "
                "VALUES(?, ?, ?, ?, ?)",
                (wg_id, str(tpath), mtime, size, head_seq),
            )
            if not chunks:
                continue
            bodies = [c["content"] for c in chunks]
            vectors: list[list[float]] = []
            for i in range(0, len(bodies), 64):
                vectors.extend(embedder.embed(bodies[i:i + 64]))
            for c, vec in zip(chunks, vectors, strict=True):
                cur = conn.execute(
                    "INSERT INTO workgroup_chunks(workgroup_id, seq_start, seq_end, "
                    "ts_start, ts_end, authors, content) VALUES(?, ?, ?, ?, ?, ?, ?)",
                    (wg_id, c["seq_start"], c["seq_end"], c["ts_start"], c["ts_end"],
                     json.dumps(c["authors"]), c["content"]),
                )
                conn.execute(
                    "INSERT INTO workgroup_vec(chunk_id, embedding) VALUES(?, ?)",
                    (cur.lastrowid, _vec_blob(vec)),
                )
                added += 1
            indexed += 1
        for row in conn.execute("SELECT workgroup_id FROM workgroup_files").fetchall():
            wid = row["workgroup_id"]
            if not _wg_dir(home, wid).exists():
                _delete_workgroup(conn, wid)
                removed += 1
        conn.commit()
        return {
            "indexed_workgroups": indexed,
            "skipped_workgroups": skipped,
            "removed_workgroups": removed,
            "added_chunks": added,
            "failed_workgroups": failed,
            "embedder": embedder.name,
            "dim": embedder.dim,
        }
    finally:
        conn.close()


def workgroup_search(
    home: Path,
    workgroup_id: str,
    query: str,
    k: int,
    *,
    embedder: embed_mod.Embedder | None = None,
) -> list[dict[str, Any]]:
    embedder = embedder or embed_mod.default()
    conn = open_store(home)
    try:
        _ensure_schema(conn, embedder.dim, embedder.name, index_mode=False)
        rows = conn.execute(
            "SELECT c.seq_start, c.seq_end, c.ts_start, c.authors, c.content, v.embedding "
            "FROM workgroup_chunks c JOIN workgroup_vec v ON v.chunk_id = c.id "
            "WHERE c.workgroup_id = ?",
            (workgroup_id,),
        ).fetchall()
        if not rows:
            return []
        qvec = embedder.embed([query])[0]
        qnorm = math.sqrt(sum(a * a for a in qvec)) or 1.0
        scored: list[tuple[float, sqlite3.Row]] = []
        for r in rows:
            vec = struct.unpack(f"{embedder.dim}f", r["embedding"])
            dot = sum(a * b for a, b in zip(qvec, vec, strict=True))
            vnorm = math.sqrt(sum(b * b for b in vec)) or 1.0
            dist = 1.0 - dot / (qnorm * vnorm)
            scored.append((dist, r))
        scored.sort(key=lambda t: t[0])
        out: list[dict[str, Any]] = []
        for dist, r in scored[:k]:
            try:
                authors = json.loads(r["authors"])
            except Exception:  # noqa: BLE001
                authors = []
            out.append({
                "workgroup_id": workgroup_id,
                "seq_start": r["seq_start"],
                "seq_end": r["seq_end"],
                "when": r["ts_start"] or "?",
                "authors": authors,
                "snippet": r["content"][:_MAX_SNIPPET],
                "score": float(dist),
            })
        return out
    finally:
        conn.close()


def forget_workgroup(home: Path, workgroup_id: str) -> None:
    if not store_path(home).exists():
        return
    conn = open_store(home)
    try:
        _delete_workgroup(conn, workgroup_id)
        conn.commit()
    except sqlite3.OperationalError:
        pass
    finally:
        conn.close()


class IndexWorkgroups(Tool):
    name = "index_workgroups"
    description = (
        "Build (or refresh) the semantic index over hub-owned workgroup "
        "transcripts so `workgroup_search` can answer free-form questions about "
        "what was said or decided. Opt-in: transcripts are NOT auto-indexed. "
        "Decrypts the hub's local transcript (key history handled); embeddings "
        "live in the profile's local store; nothing leaves the machine.\n"
        "\n"
        "With no `workgroup_id`, indexes every hub-owned workgroup on this "
        "profile. Incremental — unchanged transcripts are skipped, removed "
        "workgroups are purged. `force=true` rebuilds. Hub-owned only; this "
        "machine does not index peers' workgroups."
    )
    parameters = {
        "type": "object",
        "properties": {
            "workgroup_id": {
                "type": "string",
                "description": "Index just this workgroup. Empty = all hub-owned workgroups on this profile.",
            },
            "force": {
                "type": "boolean",
                "description": "Drop the workgroup index and rebuild from scratch. Default false (incremental).",
                "default": False,
            },
        },
    }

    def run(self, workgroup_id: str = "", force: bool = False) -> ToolResult:
        try:
            summary = index_workgroups(get_home(), workgroup_id, force=force)
        except ValueError as e:
            return ToolResult(ok=False, output="", error=str(e))
        except EmbedderMismatch as e:
            return ToolResult(ok=False, output="", error=str(e))
        return ToolResult(ok=True, output=json.dumps(summary))


class WorkgroupSearch(Tool):
    name = "workgroup_search"
    description = (
        "Semantic search over a workgroup's past transcript — finds posts by "
        "MEANING. Use when the user asks to recall what happened or what was "
        "decided in a specific workgroup and the answer needs older history "
        "(for the live visible transcript, just read it).\n"
        "\n"
        "Requires `workgroup_id`. Returns `[{workgroup_id, seq_start, seq_end, "
        "when, authors, snippet, score}]` (score = distance, lower is closer). "
        "If it reports an empty index, call `index_workgroups(workgroup_id=…)` "
        "once, then retry. Hub-owned only."
    )
    parameters = {
        "type": "object",
        "properties": {
            "workgroup_id": {"type": "string", "description": "The workgroup to search (e.g. wg_...)."},
            "query": {"type": "string", "description": "Free-form natural-language query about the transcript."},
            "k": {"type": "integer", "description": "How many results to return.", "default": 5},
        },
        "required": ["workgroup_id", "query"],
    }

    def run(self, workgroup_id: str, query: str, k: int = 5) -> ToolResult:
        if not workgroup_id or not workgroup_id.strip():
            return ToolResult(ok=False, output="", error="workgroup_id is required.")
        if not query or not query.strip():
            return ToolResult(ok=False, output="", error="Empty query.")
        if k < 1 or k > 50:
            return ToolResult(ok=False, output="", error="k must be in [1, 50].")
        from alpi.alp import workgroup as wg_mod
        if wg_mod.load(get_home(), workgroup_id) is None:
            return ToolResult(ok=False, output="", error=f"workgroup {workgroup_id!r} not found locally")
        try:
            results = workgroup_search(get_home(), workgroup_id.strip(), query.strip(), k)
        except EmbedderMismatch as e:
            return ToolResult(ok=False, output="", error=str(e))
        if not results:
            return ToolResult(ok=True, output=json.dumps(
                {"results": [], "hint": "Workgroup index is empty. Run index_workgroups first."}
            ))
        return ToolResult(ok=True, output=json.dumps({"results": results}))


TOOL_INDEX = IndexWorkgroups
TOOL_SEARCH = WorkgroupSearch
