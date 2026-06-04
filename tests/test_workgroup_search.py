from __future__ import annotations

import hashlib
import json
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
