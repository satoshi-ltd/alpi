from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from alpi.core import embed as embed_mod
from alpi.tools import workgroup_search as wgs


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


def _post(seq, body, who="@mira", ts="2026-06-04T12:00:00Z"):
    return {"seq": seq, "at": ts, "from": who, "from_pubkey": "pk", "body": body, "key_version": 1}


@pytest.fixture
def wg_env(monkeypatch):
    posts: dict[str, list] = {}

    def fake_decrypt(home, wg_id, **kw):
        return posts.get(wg_id, [])

    monkeypatch.setattr("alpi.host.workgroup.decrypt_transcript", fake_decrypt)
    monkeypatch.setattr(
        wgs, "_hub_targets",
        lambda home, workgroup_id="": ([workgroup_id] if workgroup_id else list(posts.keys())),
    )
    return posts


def _seed(home: Path, posts: dict, wg_id: str, plist: list, lines: int = 3) -> None:
    d = home / "alp" / "workgroups" / wg_id
    d.mkdir(parents=True, exist_ok=True)
    (d / "transcript.jsonl").write_text("x\n" * lines)
    posts[wg_id] = plist


def test_index_and_search_by_meaning(tmp_home, stub_embedder, wg_env):
    _seed(tmp_home, wg_env, "wg_a", [
        _post(1, "We decided the launch gate is no placeholders", who="@mira"),
        _post(2, "QA should block if hotel phone or address is missing", who="@lens"),
    ])
    summary = wgs.index_workgroups(tmp_home)
    assert summary["indexed_workgroups"] == 1
    assert summary["added_chunks"] >= 1

    results = wgs.workgroup_search(tmp_home, "wg_a", "what blocks launch quality", k=5)
    assert results
    assert "placeholders" in results[0]["snippet"] or "phone" in results[0]["snippet"]
    assert results[0]["workgroup_id"] == "wg_a"
    assert "@mira" in results[0]["authors"] or "@lens" in results[0]["authors"]
    assert set(results[0]).issuperset({"workgroup_id", "seq_start", "seq_end", "when", "authors", "snippet", "score"})


def test_search_scoped_to_one_workgroup(tmp_home, stub_embedder, wg_env):
    _seed(tmp_home, wg_env, "wg_a", [_post(1, "launch gate no placeholders")])
    _seed(tmp_home, wg_env, "wg_b", [_post(1, "postgres backups to s3 nightly")])
    wgs.index_workgroups(tmp_home)
    results = wgs.workgroup_search(tmp_home, "wg_b", "launch gate placeholders", k=5)
    assert all(r["workgroup_id"] == "wg_b" for r in results)
    assert all("placeholders" not in r["snippet"] for r in results)


def test_empty_index_hint(tmp_home, stub_embedder, wg_env):
    out = wgs.workgroup_search(tmp_home, "wg_a", "anything", k=3)
    assert out == []


def test_incremental_skip_unchanged(tmp_home, stub_embedder, wg_env):
    _seed(tmp_home, wg_env, "wg_a", [_post(1, "decision about pricing")])
    wgs.index_workgroups(tmp_home)
    second = wgs.index_workgroups(tmp_home)
    assert second["indexed_workgroups"] == 0
    assert second["skipped_workgroups"] == 1


def test_reindex_on_change(tmp_home, stub_embedder, wg_env):
    _seed(tmp_home, wg_env, "wg_a", [_post(1, "first decision")])
    wgs.index_workgroups(tmp_home)
    _seed(tmp_home, wg_env, "wg_a", [_post(1, "first decision"), _post(2, "second decision about rollout")], lines=6)
    summary = wgs.index_workgroups(tmp_home)
    assert summary["indexed_workgroups"] == 1
    results = wgs.workgroup_search(tmp_home, "wg_a", "rollout decision", k=5)
    assert any("rollout" in r["snippet"] for r in results)


def test_force_rebuild(tmp_home, stub_embedder, wg_env):
    _seed(tmp_home, wg_env, "wg_a", [_post(1, "a decision")])
    wgs.index_workgroups(tmp_home)
    summary = wgs.index_workgroups(tmp_home, force=True)
    assert summary["indexed_workgroups"] == 1


def test_scoped_force_leaves_other_workgroups(tmp_home, stub_embedder, wg_env):
    _seed(tmp_home, wg_env, "wg_a", [_post(1, "alpha launch gate placeholders")])
    _seed(tmp_home, wg_env, "wg_b", [_post(1, "bravo postgres backups nightly")])
    wgs.index_workgroups(tmp_home)
    summary = wgs.index_workgroups(tmp_home, workgroup_id="wg_a", force=True)
    assert summary["indexed_workgroups"] == 1
    # wg_b must survive a scoped force rebuild of wg_a.
    res_b = wgs.workgroup_search(tmp_home, "wg_b", "postgres backups", k=5)
    assert res_b and res_b[0]["workgroup_id"] == "wg_b"
    res_a = wgs.workgroup_search(tmp_home, "wg_a", "launch gate", k=5)
    assert res_a and res_a[0]["workgroup_id"] == "wg_a"


def test_global_force_rebuilds_all(tmp_home, stub_embedder, wg_env):
    _seed(tmp_home, wg_env, "wg_a", [_post(1, "alpha decision")])
    _seed(tmp_home, wg_env, "wg_b", [_post(1, "bravo decision")])
    wgs.index_workgroups(tmp_home)
    summary = wgs.index_workgroups(tmp_home, force=True)
    assert summary["indexed_workgroups"] == 2
    assert wgs.workgroup_search(tmp_home, "wg_a", "decision", k=5)
    assert wgs.workgroup_search(tmp_home, "wg_b", "decision", k=5)


def test_orphan_sweep(tmp_home, stub_embedder, wg_env):
    _seed(tmp_home, wg_env, "wg_a", [_post(1, "a decision")])
    wgs.index_workgroups(tmp_home)
    import shutil
    shutil.rmtree(tmp_home / "alp" / "workgroups" / "wg_a")
    del wg_env["wg_a"]
    summary = wgs.index_workgroups(tmp_home)
    assert summary["removed_workgroups"] == 1
    assert wgs.workgroup_search(tmp_home, "wg_a", "decision", k=5) == []


def test_forget_workgroup_purges(tmp_home, stub_embedder, wg_env):
    _seed(tmp_home, wg_env, "wg_a", [_post(1, "a decision")])
    wgs.index_workgroups(tmp_home)
    wgs.forget_workgroup(tmp_home, "wg_a")
    assert wgs.workgroup_search(tmp_home, "wg_a", "decision", k=5) == []


def test_forget_no_index_is_safe(tmp_home):
    wgs.forget_workgroup(tmp_home, "wg_missing")


def test_rekey_placeholders_skipped(tmp_home, stub_embedder, wg_env):
    _seed(tmp_home, wg_env, "wg_a", [
        _post(1, "[v1 key rotated out of hub state]"),
        _post(2, "the renewal decision was 42 seats"),
        _post(3, "[decrypt failed: bad tag]"),
    ])
    summary = wgs.index_workgroups(tmp_home)
    assert summary["added_chunks"] >= 1
    results = wgs.workgroup_search(tmp_home, "wg_a", "renewal seats", k=5)
    assert any("42 seats" in r["snippet"] for r in results)
    assert all("rotated" not in r["snippet"] and "decrypt failed" not in r["snippet"] for r in results)


def test_embedder_drift_raises(tmp_home, stub_embedder, wg_env):
    _seed(tmp_home, wg_env, "wg_a", [_post(1, "a decision")])
    wgs.index_workgroups(tmp_home)
    with pytest.raises(wgs.EmbedderMismatch):
        wgs.workgroup_search(tmp_home, "wg_a", "decision", k=3, embedder=OtherEmbedder())


def test_tool_requires_workgroup_id(tmp_home, stub_embedder):
    out = wgs.WorkgroupSearch().run(workgroup_id="", query="x")
    assert not out.ok
    assert "workgroup_id is required" in out.error


def test_tool_validates_k(tmp_home, stub_embedder):
    out = wgs.WorkgroupSearch().run(workgroup_id="wg_a", query="x", k=99)
    assert not out.ok
    assert "k must be in" in out.error


def test_tool_nonexistent_workgroup_errors(tmp_home, stub_embedder, monkeypatch):
    monkeypatch.setattr("alpi.alp.workgroup.load", lambda home, wg_id: None)
    out = wgs.WorkgroupSearch().run(workgroup_id="wg_nope", query="x")
    assert not out.ok
    assert "not found" in out.error


class _FailsMidRebuild(StubEmbedder):
    def __init__(self, *, fail_on_call: int = 1, name: str | None = None, dim: int | None = None):
        self.calls = 0
        self.fail_on_call = fail_on_call
        if name:
            self.name = name
        if dim:
            self.dim = dim

    def embed(self, texts):
        self.calls += 1
        if self.calls >= self.fail_on_call:
            raise RuntimeError("embedder went away mid-rebuild")
        return super().embed(texts) if self.dim == StubEmbedder.dim else [[0.1] * self.dim for _ in texts]


def _wg_counts(home: Path) -> dict:
    from alpi.core.store import open_store
    conn = open_store(home)
    try:
        return {
            "chunks": {r["workgroup_id"]: r["n"] for r in conn.execute(
                "SELECT workgroup_id, COUNT(*) AS n FROM workgroup_chunks GROUP BY workgroup_id")},
            "files": conn.execute("SELECT COUNT(*) AS n FROM workgroup_files").fetchone()["n"],
            "meta": {r["key"]: r["value"] for r in conn.execute("SELECT key, value FROM workgroup_meta")},
        }
    finally:
        conn.close()


def _two_workgroups(home: Path, posts: dict) -> None:
    _seed(home, posts, "wg_a", [_post(1, "alpha launch gate placeholders")])
    _seed(home, posts, "wg_b", [_post(1, "bravo postgres backups nightly")])
    wgs.index_workgroups(home)


def test_a_failed_global_force_keeps_every_workgroup_searchable(tmp_home, stub_embedder, wg_env):
    _two_workgroups(tmp_home, wg_env)
    before = _wg_counts(tmp_home)
    assert before["chunks"] == {"wg_a": 1, "wg_b": 1}

    with pytest.raises(RuntimeError, match="mid-rebuild"):
        wgs.index_workgroups(tmp_home, force=True, embedder=_FailsMidRebuild(fail_on_call=2))

    assert _wg_counts(tmp_home) == before
    assert wgs.workgroup_search(tmp_home, "wg_a", "launch gate", k=1)[0]["workgroup_id"] == "wg_a"
    assert wgs.workgroup_search(tmp_home, "wg_b", "postgres backups", k=1)[0]["workgroup_id"] == "wg_b"


def test_a_failed_scoped_force_keeps_that_workgroup_and_the_others(tmp_home, stub_embedder, wg_env):
    _two_workgroups(tmp_home, wg_env)
    before = _wg_counts(tmp_home)

    with pytest.raises(RuntimeError, match="mid-rebuild"):
        wgs.index_workgroups(tmp_home, workgroup_id="wg_a", force=True, embedder=_FailsMidRebuild())

    assert _wg_counts(tmp_home) == before
    assert wgs.workgroup_search(tmp_home, "wg_a", "launch gate", k=1)


def test_a_failed_rebuild_after_embedder_drift_keeps_the_old_index_and_meta(tmp_home, stub_embedder, wg_env):
    _two_workgroups(tmp_home, wg_env)
    before = _wg_counts(tmp_home)

    with pytest.raises(RuntimeError, match="mid-rebuild"):
        wgs.index_workgroups(tmp_home, embedder=_FailsMidRebuild(name="drifted", dim=8))

    assert _wg_counts(tmp_home) == before
    assert before["meta"] == {"dim": "16", "embedder": "stub-test"}
    assert wgs.workgroup_search(tmp_home, "wg_b", "postgres backups", k=1)


def test_a_workgroup_rebuild_leaves_the_session_index_alone(tmp_home, stub_embedder, wg_env):
    from alpi.core.store import open_store

    _two_workgroups(tmp_home, wg_env)
    conn = open_store(tmp_home)
    conn.execute("CREATE TABLE unrelated_owner (v TEXT)")
    conn.execute("INSERT INTO unrelated_owner VALUES ('keep me')")
    conn.commit()
    conn.close()

    with pytest.raises(RuntimeError):
        wgs.index_workgroups(tmp_home, force=True, embedder=_FailsMidRebuild())
    wgs.index_workgroups(tmp_home, force=True)

    conn = open_store(tmp_home)
    try:
        assert [r["v"] for r in conn.execute("SELECT v FROM unrelated_owner")] == ["keep me"]
    finally:
        conn.close()


def test_readers_keep_searching_while_a_global_force_runs(tmp_home, stub_embedder, wg_env):
    import threading

    _two_workgroups(tmp_home, wg_env)
    inside, release = threading.Event(), threading.Event()

    class _Slow(StubEmbedder):
        def embed(self, texts):
            inside.set()
            assert release.wait(10)
            return super().embed(texts)

    errors: list[BaseException] = []

    def rebuild():
        try:
            wgs.index_workgroups(tmp_home, force=True, embedder=_Slow())
        except BaseException as e:  # noqa: BLE001
            errors.append(e)

    worker = threading.Thread(target=rebuild)
    worker.start()
    try:
        assert inside.wait(10)
        hits = wgs.workgroup_search(tmp_home, "wg_b", "postgres backups", k=1)
        assert hits and hits[0]["workgroup_id"] == "wg_b"
    finally:
        release.set()
        worker.join(10)
    assert not errors
    assert _wg_counts(tmp_home)["chunks"] == {"wg_a": 1, "wg_b": 1}


def test_a_first_workgroup_index_that_fails_leaves_nothing_half_built(tmp_home, stub_embedder, wg_env):
    from alpi.core.store import open_store

    _seed(tmp_home, wg_env, "wg_a", [_post(1, "alpha launch gate placeholders")])
    _seed(tmp_home, wg_env, "wg_b", [_post(1, "bravo postgres backups nightly")])

    with pytest.raises(RuntimeError):
        wgs.index_workgroups(tmp_home, embedder=_FailsMidRebuild(fail_on_call=2))

    conn = open_store(tmp_home)
    try:
        exists = conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'workgroup_chunks'").fetchone()
        left = conn.execute("SELECT COUNT(*) AS n FROM workgroup_chunks").fetchone()["n"] if exists else 0
    finally:
        conn.close()
    assert left == 0


def _undecryptable(monkeypatch, posts: dict, broken: str) -> None:
    def decrypt(home, wg_id, **kw):
        if wg_id == broken:
            raise RuntimeError("no key for this epoch")
        return posts.get(wg_id, [])

    monkeypatch.setattr("alpi.host.workgroup.decrypt_transcript", decrypt)


def test_an_undecryptable_workgroup_is_skipped_by_an_incremental_pass(tmp_home, stub_embedder, wg_env, monkeypatch):
    _two_workgroups(tmp_home, wg_env)
    _seed(tmp_home, wg_env, "wg_b", [_post(1, "bravo postgres backups nightly"), _post(2, "more")], lines=6)
    _undecryptable(monkeypatch, wg_env, "wg_b")

    summary = wgs.index_workgroups(tmp_home)

    assert summary["failed_workgroups"][0]["workgroup_id"] == "wg_b"
    assert _wg_counts(tmp_home)["chunks"] == {"wg_a": 1, "wg_b": 1}


@pytest.mark.parametrize("trigger", ["force", "drift"])
def test_an_undecryptable_workgroup_stops_a_destructive_rebuild(tmp_home, stub_embedder, wg_env, monkeypatch, trigger):
    _two_workgroups(tmp_home, wg_env)
    before = _wg_counts(tmp_home)
    _undecryptable(monkeypatch, wg_env, "wg_b")
    kwargs = {"force": True} if trigger == "force" else {"embedder": _FailsMidRebuild(name="drifted", dim=8, fail_on_call=99)}

    with pytest.raises(wgs.RebuildAborted, match=r"workgroup wg_b cannot be decrypted .*previous index was kept"):
        wgs.index_workgroups(tmp_home, **kwargs)

    assert _wg_counts(tmp_home) == before


def test_a_scoped_force_is_not_stopped_by_another_broken_workgroup(tmp_home, stub_embedder, wg_env, monkeypatch):
    _two_workgroups(tmp_home, wg_env)
    _undecryptable(monkeypatch, wg_env, "wg_b")

    summary = wgs.index_workgroups(tmp_home, workgroup_id="wg_a", force=True)

    assert summary["indexed_workgroups"] == 1
    assert _wg_counts(tmp_home)["chunks"] == {"wg_a": 1, "wg_b": 1}


def test_the_index_tool_reports_an_aborted_rebuild(tmp_home, stub_embedder, wg_env, monkeypatch):
    _two_workgroups(tmp_home, wg_env)
    _undecryptable(monkeypatch, wg_env, "wg_b")

    result = wgs.IndexWorkgroups().run(force=True)

    assert not result.ok
    assert "wg_b cannot be decrypted" in result.error
    assert _wg_counts(tmp_home)["chunks"] == {"wg_a": 1, "wg_b": 1}
