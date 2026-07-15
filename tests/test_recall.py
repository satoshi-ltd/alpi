from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from alpi.core import embed as embed_mod
from alpi.tools import recall as rc
from alpi.tools import session_search


class StubEmbedder:
    name = "stub-test"
    dim = 16

    def embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for text in texts:
            vec = [0.0] * self.dim
            for token in (text.lower() or " ").split():
                h = hashlib.md5(token.encode("utf-8")).digest()
                for i in range(self.dim):
                    vec[i] += (h[i] - 128) / 128.0
            norm = sum(v * v for v in vec) ** 0.5 or 1.0
            out.append([v / norm for v in vec])
        return out


class OtherEmbedder(StubEmbedder):
    name = "other-embedder"
    dim = 8

    def embed(self, texts):
        return [[0.0] * self.dim for _ in texts]


@pytest.fixture
def stub_embedder(monkeypatch):
    embedder = StubEmbedder()
    monkeypatch.setattr(embed_mod, "_DEFAULT", embedder)
    yield embedder
    monkeypatch.setattr(embed_mod, "_DEFAULT", None)


@pytest.fixture(autouse=True)
def _clear_active_session():
    session_search.set_current_session_id(None)
    yield
    session_search.set_current_session_id(None)


def _session(home: Path, sid: str, turns: list[dict], started_at: float = 1000.0) -> Path:
    sdir = home / "sessions"
    sdir.mkdir(parents=True, exist_ok=True)
    path = sdir / f"{sid}.json"
    path.write_text(json.dumps({"id": sid, "started_at": started_at, "turns": turns}))
    return path


def _seed(home: Path) -> None:
    _session(home, "react", [
        {"user": "how did the React migration go", "assistant": "we replaced jQuery with React Router components"},
    ])
    _session(home, "infra", [
        {"user": "remind me about the database", "assistant": "Postgres on RDS with daily S3 snapshots"},
    ])


def test_index_then_recall_by_meaning(tmp_home, stub_embedder):
    _seed(tmp_home)
    summary = rc.index_sessions(tmp_home)
    assert summary["indexed_sessions"] == 2
    assert summary["added_chunks"] >= 2

    results = rc.recall(tmp_home, "the React migration to components", k=3)
    assert results
    assert results[0]["session_id"] == "react"
    assert "React" in results[0]["snippet"] or "jQuery" in results[0]["snippet"]
    assert set(results[0]).issuperset({"session_id", "when", "snippet", "score"})


def test_recall_empty_index_returns_empty(tmp_home, stub_embedder):
    assert rc.recall(tmp_home, "anything", k=3) == []


def test_recall_tool_hints_when_empty(tmp_home, stub_embedder):
    out = rc.RecallSessions().run(query="nothing indexed yet")
    assert out.ok
    body = json.loads(out.output)
    assert body["results"] == []
    assert "index_sessions" in body["hint"]


def test_incremental_skip_unchanged(tmp_home, stub_embedder):
    _seed(tmp_home)
    rc.index_sessions(tmp_home)
    second = rc.index_sessions(tmp_home)
    assert second["indexed_sessions"] == 0
    assert second["skipped_sessions"] == 2


def test_active_session_excluded_from_index_and_recall(tmp_home, stub_embedder):
    _seed(tmp_home)
    _session(tmp_home, "live", [
        {"user": "what about the React migration right now", "assistant": "in progress"},
    ])
    summary = rc.index_sessions(tmp_home, exclude_id="live")
    assert summary["indexed_sessions"] == 2
    results = rc.recall(tmp_home, "React migration", k=5, exclude_id="live")
    assert all(r["session_id"] != "live" for r in results)


def test_orphan_purge_on_reindex(tmp_home, stub_embedder):
    _seed(tmp_home)
    rc.index_sessions(tmp_home)
    (tmp_home / "sessions" / "react.json").unlink()
    summary = rc.index_sessions(tmp_home)
    assert summary["removed_sessions"] == 1
    results = rc.recall(tmp_home, "React migration", k=5)
    assert all(r["session_id"] != "react" for r in results)


def test_forget_session_purges_from_index(tmp_home, stub_embedder):
    _seed(tmp_home)
    rc.index_sessions(tmp_home)
    rc.forget_session(tmp_home, "react")
    results = rc.recall(tmp_home, "React migration", k=5)
    assert all(r["session_id"] != "react" for r in results)


def test_forget_session_no_index_is_safe(tmp_home):
    rc.forget_session(tmp_home, "never-indexed")  # no store yet — must not raise


def test_delete_session_hook_forgets_from_recall(tmp_home, stub_embedder):
    _seed(tmp_home)
    rc.index_sessions(tmp_home)
    from alpi.host import sessions as host_sessions
    assert host_sessions.delete_session(tmp_home, "react") is True
    results = rc.recall(tmp_home, "React migration", k=5)
    assert all(r["session_id"] != "react" for r in results)


def test_embedder_drift_raises_on_recall(tmp_home, stub_embedder):
    _seed(tmp_home)
    rc.index_sessions(tmp_home)
    with pytest.raises(rc.EmbedderMismatch):
        rc.recall(tmp_home, "React", k=3, embedder=OtherEmbedder())


def test_force_rebuild(tmp_home, stub_embedder):
    _seed(tmp_home)
    rc.index_sessions(tmp_home)
    summary = rc.index_sessions(tmp_home, force=True)
    assert summary["indexed_sessions"] == 2
    assert summary["total_sessions"] == 2


def _session_cid(home: Path, sid: str, cid: str, text: str) -> None:
    sdir = home / "sessions"
    sdir.mkdir(parents=True, exist_ok=True)
    (sdir / f"{sid}.json").write_text(json.dumps({
        "id": sid, "started_at": 1000.0, "connection_id": cid,
        "turns": [{"user": text, "assistant": f"jQuery to React Router — {text}"}],
    }))


def test_recall_scoped_by_connection(tmp_home, stub_embedder):
    _session_cid(tmp_home, "c1sess", "c1", "the React migration")
    _session_cid(tmp_home, "c2sess", "c2", "the React migration")
    _session_cid(tmp_home, "hostsess", "host", "the React migration")
    rc.index_sessions(tmp_home)

    allr = rc.recall(tmp_home, "React migration to components", k=10)
    assert {r["session_id"] for r in allr} == {"c1sess", "c2sess", "hostsess"}

    c1 = rc.recall(tmp_home, "React migration to components", k=10, connection_id="c1")
    assert {r["session_id"] for r in c1} == {"c1sess"}


def test_recall_tool_scopes_by_member_role(tmp_home, stub_embedder):
    _session_cid(tmp_home, "c1sess", "c1", "the React migration")
    _session_cid(tmp_home, "hostsess", "host", "the React migration")
    rc.index_sessions(tmp_home)
    from alpi.host.connection_context import ConnectionContext, use
    with use(ConnectionContext(connection_id="c1", source="remote", role="member")):
        out = rc.RecallSessions().run(query="React migration to components", k=10)
    ids = {r["session_id"] for r in json.loads(out.output)["results"]}
    assert ids == {"c1sess"}


def test_recall_relabels_owner_on_incremental_skip(tmp_home, stub_embedder):
    _session_cid(tmp_home, "c1sess", "c1", "the React migration")
    rc.index_sessions(tmp_home)

    from alpi.core.store import open_store
    conn = open_store(tmp_home)
    conn.execute("UPDATE session_files SET connection_id = 'host'")
    conn.execute("UPDATE session_chunks SET connection_id = 'host'")
    conn.commit()
    conn.close()
    assert rc.recall(tmp_home, "React migration", k=5, connection_id="c1") == []

    summary = rc.index_sessions(tmp_home)
    assert summary["skipped_sessions"] == 1
    assert {r["session_id"] for r in rc.recall(tmp_home, "React migration", k=5, connection_id="c1")} == {"c1sess"}


def _plain_session(home: Path, sid: str, cid: str, text: str) -> None:
    sdir = home / "sessions"
    sdir.mkdir(parents=True, exist_ok=True)
    (sdir / f"{sid}.json").write_text(json.dumps({
        "id": sid, "started_at": 1000.0, "connection_id": cid,
        "turns": [{"user": text, "assistant": text}],
    }))


def test_recall_finds_own_behind_many_closer_foreign(tmp_home, stub_embedder):
    for i in range(40):
        _plain_session(tmp_home, f"c2_{i}", "c2", "the React migration to components")
    _plain_session(tmp_home, "mine", "c1", "postgres database backups nightly")
    rc.index_sessions(tmp_home)

    res = rc.recall(tmp_home, "the React migration to components", k=3, connection_id="c1")
    assert {r["session_id"] for r in res} == {"mine"}


def test_recall_legacy_index_migrates_connection_column(tmp_home, stub_embedder):
    from alpi.core.store import open_store
    conn = open_store(tmp_home)
    conn.executescript(
        "CREATE TABLE session_files (session_id TEXT PRIMARY KEY, source_path TEXT NOT NULL, "
        "mtime REAL NOT NULL, size INTEGER NOT NULL, started_at REAL);"
        "CREATE TABLE session_chunks (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL, "
        "chunk_index INTEGER NOT NULL, content TEXT NOT NULL, started_at REAL);"
    )
    conn.commit()
    conn.close()

    _session_cid(tmp_home, "s1", "c1", "the React migration")
    rc.index_sessions(tmp_home)

    conn = open_store(tmp_home)
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(session_chunks)").fetchall()}
    conn.close()
    assert "connection_id" in cols
    assert {r["session_id"] for r in rc.recall(tmp_home, "React migration", k=5, connection_id="c1")} == {"s1"}
