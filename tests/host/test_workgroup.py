"""Tests for ``host.workgroup.transcript``."""

from __future__ import annotations

import asyncio
import json
import shutil
import tempfile
from pathlib import Path

import pytest

from alpi.host import server as host_server
from alpi.alp import workgroup as wg_mod
from alpi.alp.keys import load_or_generate
from alpi.host import handlers as data_handlers
from alpi.host import workgroup as data_workgroup


@pytest.fixture
def short_tmp() -> Path:
    d = Path(tempfile.mkdtemp(prefix="alp-data-", dir="/tmp"))
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


def _seed_workgroup_with_one_post(home: Path, body: bytes) -> str:
    """Create a local workgroup transcript with one post."""
    home.mkdir(exist_ok=True)
    kp = load_or_generate(home)
    wg = wg_mod.create(
        home,
        name="test-wg",
        hub_kp=kp,
        member_pubkeys=[],
        briefing="",
    )
    me = wg.member(kp.pubkey_b64())
    assert me is not None, "hub must be member of its own workgroup"
    group_key = wg_mod.open_sealed_group_key(me.sealed_key, kp)
    nonce_b64, ct_b64 = wg_mod.encrypt_post(group_key, body)
    d = home / "alp" / "workgroups" / wg.meta.id
    entry = {
        "seq": 1,
        "ts": "2026-05-01T00:00:00Z",
        "from": kp.pubkey_b64(),
        "key_version": me.key_version,
        "nonce": nonce_b64,
        "ciphertext": ct_b64,
    }
    (d / "transcript.jsonl").write_text(
        json.dumps(entry, separators=(",", ":")) + "\n", encoding="utf-8",
    )
    return wg.meta.id


def test_decrypt_transcript_hub_roundtrip(short_tmp: Path) -> None:
    home = short_tmp / "hub"
    wg_id = _seed_workgroup_with_one_post(home, b"hello workgroup")

    posts = data_workgroup.decrypt_transcript(home, wg_id)
    assert len(posts) == 1
    assert posts[0]["body"] == "hello workgroup"
    assert posts[0]["seq"] == 1
    assert posts[0]["from"] == "@default"


def _append_post(home: Path, wg_id: str, body: bytes, *, seq: int) -> None:
    kp = load_or_generate(home)
    wg = wg_mod.load(home, wg_id)
    assert wg is not None
    me = wg.member(kp.pubkey_b64())
    assert me is not None
    group_key = wg_mod.open_sealed_group_key(me.sealed_key, kp)
    nonce_b64, ct_b64 = wg_mod.encrypt_post(group_key, body)
    entry = {
        "seq": seq,
        "ts": f"2026-05-01T00:00:{seq:02d}Z",
        "from": kp.pubkey_b64(),
        "key_version": me.key_version,
        "nonce": nonce_b64,
        "ciphertext": ct_b64,
    }
    p = home / "alp" / "workgroups" / wg_id / "transcript.jsonl"
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, separators=(",", ":")) + "\n")


def test_decrypt_transcript_after_seq_returns_only_newer(short_tmp: Path) -> None:
    home = short_tmp / "hub"
    wg_id = _seed_workgroup_with_one_post(home, b"post-1")
    _append_post(home, wg_id, b"post-2", seq=2)
    _append_post(home, wg_id, b"post-3", seq=3)

    posts = data_workgroup.decrypt_transcript(home, wg_id, after_seq=1)
    assert [p["seq"] for p in posts] == [2, 3]
    assert posts[0]["body"] == "post-2"


def test_decrypt_transcript_tail_with_limit(short_tmp: Path) -> None:
    home = short_tmp / "hub"
    wg_id = _seed_workgroup_with_one_post(home, b"post-1")
    _append_post(home, wg_id, b"post-2", seq=2)
    _append_post(home, wg_id, b"post-3", seq=3)

    posts = data_workgroup.decrypt_transcript(home, wg_id, limit=2, tail=True)
    assert [p["seq"] for p in posts] == [2, 3]


def test_decrypt_transcript_opens_group_key_once(
    short_tmp: Path, monkeypatch,
) -> None:
    """Reopening the sealed key per-post is ~10ms each on Curve25519; we cache it for the call so an N-post transcript stays O(N) AEAD only."""
    home = short_tmp / "hub"
    wg_id = _seed_workgroup_with_one_post(home, b"post-1")
    _append_post(home, wg_id, b"post-2", seq=2)
    _append_post(home, wg_id, b"post-3", seq=3)

    real_open = wg_mod.open_sealed_group_key
    calls = {"n": 0}

    def counting_open(sealed, kp):
        calls["n"] += 1
        return real_open(sealed, kp)

    monkeypatch.setattr(data_workgroup.wg_mod, "open_sealed_group_key", counting_open)

    posts = data_workgroup.decrypt_transcript(home, wg_id)
    assert len(posts) == 3
    assert calls["n"] == 1


def test_decrypt_transcript_unknown_workgroup_returns_empty(short_tmp: Path) -> None:
    home = short_tmp / "hub"
    home.mkdir()
    load_or_generate(home)
    out = data_workgroup.decrypt_transcript(home, "wg_does_not_exist")
    assert out == []


@pytest.mark.integration
@pytest.mark.asyncio
async def test_data_workgroup_transcript_over_unix_socket(
    short_tmp: Path, monkeypatch,
) -> None:
    """The control socket returns decrypted transcript rows."""
    home = short_tmp / "hub"
    wg_id = _seed_workgroup_with_one_post(home, b"first plaintext")

    monkeypatch.setattr(
        Path, "home", classmethod(lambda cls: short_tmp.parent),  # type: ignore[arg-type]
    )

    srv = host_server.Server(home=home)
    data_handlers.register(srv)
    await srv.start()
    try:
        monkeypatch.setattr(
            data_handlers, "_resolve_home",
            lambda profile: home,
        )

        reader, writer = await asyncio.open_unix_connection(
            str(srv.socket_path()),
        )
        request = {
            "id": "req-1",
            "method": "host.workgroup.transcript",
            "params": {"profile": "default", "wg_id": wg_id},
        }
        writer.write((json.dumps(request) + "\n").encode("utf-8"))
        await writer.drain()
        line = await reader.readline()
        writer.close()
        await writer.wait_closed()
    finally:
        await srv.stop()

    response = json.loads(line)
    assert response["id"] == "req-1"
    assert "error" not in response
    posts = response["result"]["posts"]
    assert len(posts) == 1
    assert posts[0]["body"] == "first plaintext"


@pytest.mark.asyncio
async def test_control_method_not_found(short_tmp: Path) -> None:
    home = short_tmp / "hub"
    home.mkdir()
    load_or_generate(home)
    srv = host_server.Server(home=home)
    data_handlers.register(srv)
    await srv.start()
    try:
        reader, writer = await asyncio.open_unix_connection(str(srv.socket_path()))
        writer.write(
            (json.dumps({"id": "x", "method": "host.does.not.exist"}) + "\n").encode(),
        )
        await writer.drain()
        line = await reader.readline()
        writer.close()
        await writer.wait_closed()
    finally:
        await srv.stop()
    response = json.loads(line)
    assert response["error"]["code"] == -32601


@pytest.mark.asyncio
async def test_workgroup_transcript_handler_defaults_to_tail(
    short_tmp: Path, monkeypatch,
) -> None:
    """First-paint default — without an after_seq cursor the daemon must return the most recent window, not the oldest. Otherwise a long-lived workgroup paints page 1 of its history every time the UI opens."""
    home = short_tmp / "hub"
    wg_id = _seed_workgroup_with_one_post(home, b"post-1")
    for i in range(2, 6):
        _append_post(home, wg_id, f"post-{i}".encode(), seq=i)

    monkeypatch.setattr(data_handlers, "_resolve_home", lambda profile: home)
    srv = host_server.Server(home=home)
    data_handlers.register(srv)

    resp = await srv._dispatch({
        "id": "r", "method": "host.workgroup.transcript",
        "params": {"profile": "default", "wg_id": wg_id, "limit": 3},
    })
    seqs = [p["seq"] for p in resp["result"]["posts"]]
    # 3 most recent, in oldest-first order.
    assert seqs == [3, 4, 5]


@pytest.mark.asyncio
async def test_workgroup_transcript_handler_paginates(
    short_tmp: Path, monkeypatch,
) -> None:
    """Handler-level surface: after_seq + limit + tail return the right slice and next_seq for incremental fetch."""
    home = short_tmp / "hub"
    wg_id = _seed_workgroup_with_one_post(home, b"post-1")
    _append_post(home, wg_id, b"post-2", seq=2)
    _append_post(home, wg_id, b"post-3", seq=3)

    monkeypatch.setattr(data_handlers, "_resolve_home", lambda profile: home)
    srv = host_server.Server(home=home)
    data_handlers.register(srv)

    resp = await srv._dispatch({
        "id": "r", "method": "host.workgroup.transcript",
        "params": {"profile": "default", "wg_id": wg_id, "after_seq": 1},
    })
    result = resp["result"]
    assert [p["seq"] for p in result["posts"]] == [2, 3]
    assert result["next_seq"] == 3

    resp = await srv._dispatch({
        "id": "r", "method": "host.workgroup.transcript",
        "params": {"profile": "default", "wg_id": wg_id, "limit": 1, "tail": True},
    })
    assert [p["seq"] for p in resp["result"]["posts"]] == [3]


def test_register_rejects_non_data_namespace(short_tmp: Path) -> None:
    home = short_tmp / "hub"
    home.mkdir()
    load_or_generate(home)
    srv = host_server.Server(home=home)
    with pytest.raises(ValueError):
        srv.register("link.something", lambda *_: {})


def _seed_workgroup_with_posts(home: Path, bodies: list[bytes]) -> str:
    home.mkdir(exist_ok=True)
    kp = load_or_generate(home)
    wg = wg_mod.create(
        home, name="test-wg", hub_kp=kp, member_pubkeys=[], briefing="",
    )
    me = wg.member(kp.pubkey_b64())
    assert me is not None
    group_key = wg_mod.open_sealed_group_key(me.sealed_key, kp)
    d = home / "alp" / "workgroups" / wg.meta.id
    lines = []
    for i, body in enumerate(bodies, start=1):
        nonce_b64, ct_b64 = wg_mod.encrypt_post(group_key, body)
        lines.append(json.dumps({
            "seq": i, "ts": "2026-05-01T00:00:00Z", "from": kp.pubkey_b64(),
            "key_version": me.key_version, "nonce": nonce_b64, "ciphertext": ct_b64,
        }, separators=(",", ":")))
    (d / "transcript.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return wg.meta.id


def test_fold_task_state_active(short_tmp: Path) -> None:
    home = short_tmp / "hub"
    wg_id = _seed_workgroup_with_posts(home, [b"@quill #task #content write the copy"])
    state = data_workgroup.fold_task_state(home, wg_id)
    assert state["active"] == {"slug": "content", "title": "write the copy", "opened_seq": 1}
    assert state["closed"] == []
    assert state["blocked"] is None


def test_fold_task_state_blocked(short_tmp: Path) -> None:
    home = short_tmp / "hub"
    wg_id = _seed_workgroup_with_posts(home, [
        b"@pixel #task #build wire it",
        b"#done BLOCKED build \xc2\xb7 deps missing",
    ])
    state = data_workgroup.fold_task_state(home, wg_id)
    assert state["active"] is None
    assert len(state["closed"]) == 1
    assert state["closed"][0]["slug"] == "build"
    assert state["closed"][0]["blocked"] is True
    assert state["blocked"]["slug"] == "build"
    assert state["blocked"]["reason"].startswith("BLOCKED build")


def test_fold_task_state_retask_clears_blocked(short_tmp: Path) -> None:
    home = short_tmp / "hub"
    wg_id = _seed_workgroup_with_posts(home, [
        b"@pixel #task #build wire it",
        b"#done BLOCKED build",
        b"@pixel #task #build-recheck retry",
    ])
    state = data_workgroup.fold_task_state(home, wg_id)
    assert state["active"]["slug"] == "build-recheck"
    assert state["blocked"] is None
