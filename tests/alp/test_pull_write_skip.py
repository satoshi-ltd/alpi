from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any

import pytest

from alpi.alp import subscription as sub_mod
from alpi.alp import workgroup_client as wc

HUB_PK = "H" * 44


@pytest.fixture(autouse=True)
def _clear_raw_cache():
    sub_mod._raw_cache.clear()
    yield
    sub_mod._raw_cache.clear()


@pytest.fixture
def member(tmp_path: Path) -> Path:
    home = tmp_path / "member"
    sub = sub_mod.Subscription(
        wg_id="wg_a", name="site", hub_id="hub", hub_pubkey=HUB_PK, last_seq=7,
        joined_at="2026-08-20T09:00:00Z",
    )
    sub.upsert_key(1, "SEALED_V1")
    sub.roster = {"PK_A": "2026-08-22T10:00:00Z", HUB_PK: "2026-08-22T10:00:00Z"}
    sub.roster_bios = {"PK_A": "engineer"}
    sub.recent_posts = [
        {"seq": i, "text": f"post {i}", "from": HUB_PK, "ts": "2026-08-22T09:00:00Z"}
        for i in range(1, 8)
    ]
    sub_mod.upsert(home, sub)
    return home


def _reply(**extra: Any) -> dict[str, Any]:
    reply: dict[str, Any] = {
        "posts": [],
        "head": 7,
        "current_key_version": 1,
        "sealed_key": "SEALED_V1",
        "paused": False,
        "members": [
            {"pubkey": "PK_A", "last_seen_at": "2026-08-22T10:00:30Z",
             "bio": "engineer", "voice": ""},
            {"pubkey": HUB_PK, "last_seen_at": "2026-08-22T10:00:30Z",
             "bio": "", "voice": ""},
        ],
    }
    reply.update(extra)
    return reply


def _wire(home: Path, monkeypatch: pytest.MonkeyPatch, reply: dict[str, Any]) -> None:
    async def fake_call(*args: Any, **kwargs: Any) -> dict[str, Any]:
        return reply

    monkeypatch.setattr(wc, "_call", fake_call)
    monkeypatch.setattr(
        sub_mod, "decrypt_post",
        lambda sub, kp, post: str(post.get("plain", "")).encode(),
    )


async def _pull_and_stamp(
    home: Path, monkeypatch: pytest.MonkeyPatch, reply: dict[str, Any],
) -> tuple[int, tuple[list[dict[str, Any]], int]]:
    _wire(home, monkeypatch, reply)
    p = sub_mod.path(home)
    before = p.stat().st_mtime_ns
    out = await wc.pull(home, "wg_a")
    return before, out


def _rewrote(home: Path, before: int) -> bool:
    return sub_mod.path(home).stat().st_mtime_ns != before


@pytest.mark.asyncio
async def test_empty_pull_does_not_rewrite_the_file(
    member: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    before, (posts, head) = await _pull_and_stamp(member, monkeypatch, _reply())
    assert (posts, head) == ([], 7)
    assert not _rewrote(member, before)


@pytest.mark.asyncio
async def test_repeated_empty_pulls_never_rewrite_the_file(
    member: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _wire(member, monkeypatch, _reply())
    before = sub_mod.path(member).stat().st_mtime_ns
    for _ in range(5):
        await wc.pull(member, "wg_a")
    assert not _rewrote(member, before)
    stored = sub_mod.get(member, "wg_a")
    assert stored is not None
    assert stored.last_seq == 7


@pytest.mark.asyncio
async def test_presence_restamps_inside_one_bucket_do_not_rewrite_the_file(
    member: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    stamps = ["2026-08-22T10:00:11Z", "2026-08-22T10:01:04Z", "2026-08-22T10:01:59Z"]
    buckets = {sub_mod._presence_bucket(s) for s in stamps}
    assert len(buckets) == 1
    reply = _reply()
    for row in reply["members"]:
        row["last_seen_at"] = stamps[0]
    before, _ = await _pull_and_stamp(member, monkeypatch, reply)
    assert not _rewrote(member, before)
    for stamp in stamps[1:]:
        for row in reply["members"]:
            row["last_seen_at"] = stamp
        _wire(member, monkeypatch, reply)
        await wc.pull(member, "wg_a")
        assert not _rewrote(member, before)


@pytest.mark.asyncio
async def test_a_presence_restamp_past_the_bucket_refreshes_the_mirror_once(
    member: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    reply = _reply()
    for row in reply["members"]:
        row["last_seen_at"] = "2026-08-22T18:00:00Z"
    before, _ = await _pull_and_stamp(member, monkeypatch, reply)
    assert _rewrote(member, before)
    settled = sub_mod.path(member).stat().st_mtime_ns
    for row in reply["members"]:
        row["last_seen_at"] = "2026-08-22T18:01:30Z"
    _wire(member, monkeypatch, reply)
    await wc.pull(member, "wg_a")
    assert not _rewrote(member, settled)


@pytest.mark.asyncio
async def test_a_new_post_rewrites_the_file(
    member: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    reply = _reply(head=8, posts=[{
        "seq": 8, "from": HUB_PK, "ts": "2026-08-22T10:00:00Z",
        "key_version": 1, "nonce": "n", "ciphertext": "c", "plain": "#task build",
    }])
    before, (posts, head) = await _pull_and_stamp(member, monkeypatch, reply)
    assert head == 8
    assert [p["text"] for p in posts] == ["#task build"]
    assert _rewrote(member, before)
    stored = sub_mod.get(member, "wg_a")
    assert stored is not None
    assert stored.last_seq == 8
    assert stored.recent_posts[-1]["text"] == "#task build"


@pytest.mark.asyncio
async def test_a_change_rewrite_also_refreshes_the_presence_mirror(
    member: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    reply = _reply(head=8, posts=[{
        "seq": 8, "from": HUB_PK, "ts": "2026-08-22T10:00:00Z",
        "key_version": 1, "nonce": "n", "ciphertext": "c", "plain": "hello",
    }])
    for row in reply["members"]:
        row["last_seen_at"] = "2026-08-22T10:30:00Z"
    await _pull_and_stamp(member, monkeypatch, reply)
    stored = sub_mod.get(member, "wg_a")
    assert stored is not None
    assert stored.roster["PK_A"] == "2026-08-22T10:30:00Z"


@pytest.mark.asyncio
async def test_a_roster_membership_change_rewrites_the_file(
    member: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    reply = _reply()
    reply["members"].append({
        "pubkey": "PK_NEW", "last_seen_at": "2026-08-22T10:00:30Z",
        "bio": "qa", "voice": "",
    })
    before, _ = await _pull_and_stamp(member, monkeypatch, reply)
    assert _rewrote(member, before)
    stored = sub_mod.get(member, "wg_a")
    assert stored is not None
    assert "PK_NEW" in stored.roster
    assert stored.roster_bios["PK_NEW"] == "qa"


@pytest.mark.asyncio
async def test_a_bio_change_rewrites_the_file(
    member: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    reply = _reply()
    reply["members"][0]["bio"] = "staff engineer"
    before, _ = await _pull_and_stamp(member, monkeypatch, reply)
    assert _rewrote(member, before)


@pytest.mark.asyncio
async def test_a_pause_flip_rewrites_the_file(
    member: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    before, _ = await _pull_and_stamp(member, monkeypatch, _reply(paused=True))
    assert _rewrote(member, before)
    stored = sub_mod.get(member, "wg_a")
    assert stored is not None
    assert stored.paused is True


@pytest.mark.asyncio
async def test_a_rotated_key_rewrites_the_file(
    member: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    before, _ = await _pull_and_stamp(
        member, monkeypatch,
        _reply(current_key_version=2, sealed_key="SEALED_V2"),
    )
    assert _rewrote(member, before)
    stored = sub_mod.get(member, "wg_a")
    assert stored is not None
    assert stored.sealed_for(2) == "SEALED_V2"


@pytest.mark.asyncio
async def test_a_pipeline_change_rewrites_the_file(
    member: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    before, _ = await _pull_and_stamp(
        member, monkeypatch,
        _reply(pipelines={"build": ["build", "qa"]}, launch_pipeline="build"),
    )
    assert _rewrote(member, before)
    stored = sub_mod.get(member, "wg_a")
    assert stored is not None
    assert stored.launch_chain == ("build", "qa")


@pytest.mark.asyncio
async def test_empty_pull_leaves_a_locally_advanced_cursor_alone(
    member: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    sub_mod.mutate(member, "wg_a", lambda s: _set_responded(s, 7))
    before, _ = await _pull_and_stamp(member, monkeypatch, _reply())
    assert not _rewrote(member, before)
    stored = sub_mod.get(member, "wg_a")
    assert stored is not None
    assert stored.last_responded_seq == 7


def _set_responded(sub: sub_mod.Subscription, seq: int) -> bool:
    sub.last_responded_seq = seq
    return True


def _populated() -> sub_mod.Subscription:
    sub = sub_mod.Subscription(
        wg_id="wg_a", name="site", hub_id="hub", hub_pubkey=HUB_PK, last_seq=7,
        joined_at="2026-08-20T09:00:00Z", briefing="ship it",
        pipelines={"launch": ("build", "qa")}, launch_pipeline="launch",
        pipeline_mode=True, phase_map={"build": {"owner": "quill"}},
        paused=False, last_responded_seq=3,
        last_dispatch_at="2026-08-21T09:00:00Z",
    )
    sub.upsert_key(1, "SEALED_V1")
    sub.roster = {"PK_A": "2026-08-22T10:00:00Z"}
    sub.roster_bios = {"PK_A": "engineer"}
    sub.roster_voices = {"PK_A": "en-US-AriaNeural"}
    sub.recent_posts = [{"seq": 7, "text": "post", "from": HUB_PK}]
    return sub


def _mutations() -> dict[str, Any]:
    return {
        "wg_id": "wg_other",
        "name": "other",
        "hub_id": "hub2",
        "hub_pubkey": "K" * 44,
        "sealed_keys": [sub_mod.SealedKey(version=2, sealed="SEALED_V2")],
        "last_seq": 8,
        "joined_at": "2026-08-20T09:00:01Z",
        "briefing": "ship it later",
        "pipelines": {"launch": ("build",)},
        "launch_pipeline": "other",
        "pipeline_mode": False,
        "phase_map": {"build": {"owner": "scout"}},
        "paused": True,
        "last_responded_seq": 4,
        "roster": {"PK_A": "2026-08-22T10:00:00Z", "PK_B": ""},
        "roster_bios": {"PK_A": "architect"},
        "roster_voices": {"PK_A": "en-GB-RyanNeural"},
        "last_dispatch_at": "2026-08-21T09:00:01Z",
        "recent_posts": [{"seq": 7, "text": "edited", "from": HUB_PK}],
    }


def test_every_persisted_field_moves_the_signature() -> None:
    names = {f.name for f in dataclasses.fields(sub_mod.Subscription)}
    mutations = _mutations()
    assert names == set(mutations), (
        "a Subscription field has no signature-change case — an empty pull would "
        "silently drop changes to it"
    )
    baseline = sub_mod.persisted_signature(_populated())
    for name, value in mutations.items():
        sub = _populated()
        setattr(sub, name, value)
        assert sub_mod.persisted_signature(sub) != baseline, name


def test_a_presence_restamp_inside_one_bucket_does_not_move_the_signature() -> None:
    sub = _populated()
    baseline = sub_mod.persisted_signature(sub)
    same_bucket = "2026-08-22T10:01:59Z"
    assert sub_mod._presence_bucket(same_bucket) == sub_mod._presence_bucket(
        sub.roster["PK_A"],
    )
    sub.roster = {"PK_A": same_bucket}
    assert sub_mod.persisted_signature(sub) == baseline
    sub.roster = {"PK_A": same_bucket, "PK_B": ""}
    assert sub_mod.persisted_signature(sub) != baseline


def test_a_presence_restamp_past_the_bucket_refreshes_the_mirror() -> None:
    sub = _populated()
    baseline = sub_mod.persisted_signature(sub)
    next_bucket = "2026-08-22T10:05:00Z"
    assert sub_mod._presence_bucket(next_bucket) != sub_mod._presence_bucket(
        sub.roster["PK_A"],
    )
    sub.roster = {"PK_A": next_bucket}
    assert sub_mod.persisted_signature(sub) != baseline


def test_the_mirror_cannot_go_stale_enough_to_read_as_offline() -> None:
    from alpi.alp.agent_context import _ONLINE_SECONDS

    assert sub_mod.PRESENCE_BUCKET_SECONDS < _ONLINE_SECONDS


def test_an_unparseable_presence_stamp_still_sorts() -> None:
    sub = _populated()
    sub.roster = {"PK_A": "not-a-timestamp", "PK_B": "2026-08-22T10:00:00Z"}
    assert sub_mod.persisted_signature(sub)


def test_signature_sees_a_post_mutated_in_place() -> None:
    sub = _populated()
    baseline = sub_mod.persisted_signature(sub)
    sub.recent_posts[0]["text"] = "rewritten"
    assert sub_mod.persisted_signature(sub) != baseline
    sub.recent_posts[0]["text"] = "post"
    assert sub_mod.persisted_signature(sub) == baseline
    sub.phase_map["build"]["owner"] = "muse"
    assert sub_mod.persisted_signature(sub) != baseline


def test_mutate_returns_the_subscription_when_nothing_changed(
    member: Path,
) -> None:
    before = sub_mod.path(member).stat().st_mtime_ns
    got = sub_mod.mutate(member, "wg_a", lambda s: False)
    assert got is not None
    assert got.wg_id == "wg_a"
    assert not _rewrote(member, before)


def test_mutate_still_saves_when_the_mutator_reports_a_change(
    member: Path,
) -> None:
    other = sub_mod.Subscription(
        wg_id="wg_b", name="other", hub_id="hub", hub_pubkey=HUB_PK,
    )
    sub_mod.upsert(member, other)
    got = sub_mod.mutate(member, "wg_a", lambda s: _set_responded(s, 11))
    assert got is not None
    stored = sub_mod.load(member)
    assert [s.wg_id for s in stored] == ["wg_a", "wg_b"]
    assert stored[0].last_responded_seq == 11
    assert stored[1].name == "other"


def test_mutate_returns_none_for_an_unknown_id(member: Path) -> None:
    calls: list[str] = []
    assert sub_mod.mutate(
        member, "wg_missing", lambda s: calls.append(s.wg_id) or True,
    ) is None
    assert calls == []
