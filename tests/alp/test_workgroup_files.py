from __future__ import annotations

import asyncio
import base64
import hashlib
import os
import shutil
import socket
import tempfile
import time
from pathlib import Path

import pytest

from alpi.alp import server as alp_server
from alpi.alp import peers as peers_mod
from alpi.alp import subscription as sub_mod
from alpi.alp import workgroup as wg_mod
from alpi.alp import workgroup_client as wc
from alpi.alp import workgroup_files as wf
from alpi.alp.keys import load_or_generate
from alpi.alp.peers import Peer


@pytest.fixture
def short_tmp() -> Path:
    path = Path(tempfile.mkdtemp(prefix="alpi-wgf-", dir="/tmp"))
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def _setup(short_tmp: Path, members: int = 1):
    hub_home = short_tmp / "hub"
    hub_home.mkdir()
    hub_kp = load_or_generate(hub_home)
    member_keys = []
    for index in range(members):
        member_home = short_tmp / f"member-{index}"
        member_home.mkdir()
        member_keys.append(load_or_generate(member_home))
    wg = wg_mod.create(
        hub_home,
        name="files",
        hub_kp=hub_kp,
        member_pubkeys=[kp.pubkey_b64() for kp in member_keys],
    )
    for kp in member_keys:
        member = wg.member(kp.pubkey_b64())
        member.joined = True
    wg_mod._save_members(wg_mod._wg_dir(hub_home, wg.meta.id), wg.members)
    server = alp_server.Server(hub_home)
    wg_mod.register(server, hub_home)
    peers = [
        Peer(id=f"member-{index}", pubkey=kp.pubkey_b64())
        for index, kp in enumerate(member_keys)
    ]
    return hub_home, hub_kp, member_keys, peers, wg, server


def _free_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])
    finally:
        sock.close()


def _encrypted_params(wg, hub_home: Path, hub_kp, peer, data: bytes, **overrides):
    key = wg_mod.hub_group_keys(hub_home, wg, hub_kp)[wg.meta.current_key_version]
    nonce, encoded = wg_mod.encrypt_post(key, data)
    digest = hashlib.sha256(data).hexdigest()
    params = {
        "workgroup_id": wg.meta.id,
        "sha256": digest,
        "name": "report.bin",
        "size": len(data),
        "key_version": wg.meta.current_key_version,
        "nonce": nonce,
        "offset": 0,
        "data_base64": encoded,
        "done": True,
        "note": "final result",
    }
    params.update(overrides)
    return params, digest, key


async def _put(server, peer, params):
    return await server.handlers["workgroup.file_put"](params, peer, server)


async def _get(server, peer, wg_id, digest, offset=0):
    return await server.handlers["workgroup.file_get"](
        {"workgroup_id": wg_id, "sha256": digest, "offset": offset},
        peer,
        server,
    )


async def _list(server, peer, wg_id, offset=0, limit=50):
    return await server.handlers["workgroup.file_list"](
        {"workgroup_id": wg_id, "offset": offset, "limit": limit},
        peer,
        server,
    )


@pytest.mark.parametrize("size", [1, wf.CHUNK_BYTES - 16, wf.CHUNK_BYTES + 1])
@pytest.mark.asyncio
async def test_put_get_roundtrip_and_marker(short_tmp: Path, size: int) -> None:
    hub_home, hub_kp, _, peers, wg, server = _setup(short_tmp)
    data = b"x" * size
    params, digest, key = _encrypted_params(wg, hub_home, hub_kp, peers[0], data)
    ciphertext = base64.b64decode(params.pop("data_base64"))
    result = None
    for offset in range(0, len(ciphertext), wf.CHUNK_BYTES):
        chunk = ciphertext[offset: offset + wf.CHUNK_BYTES]
        result = await _put(server, peers[0], {
            **params,
            "offset": offset,
            "data_base64": base64.b64encode(chunk).decode("ascii"),
            "done": offset + len(chunk) == len(ciphertext),
        })

    assert result["complete"] is True
    root = hub_home / "alp" / "workgroups" / wg.meta.id / "files"
    assert (root / f"{digest}.bin").read_bytes() == ciphertext
    assert digest not in (hub_home / "alp" / "workgroups" / wg.meta.id / "transcript.jsonl").read_text()

    downloaded = bytearray()
    offset = 0
    while True:
        response = await _get(server, peers[0], wg.meta.id, digest, offset)
        chunk = base64.b64decode(response["data_base64"])
        downloaded.extend(chunk)
        offset += len(chunk)
        if response["eof"]:
            break
    plaintext = wg_mod.decrypt_post(
        key,
        response["nonce"],
        base64.b64encode(bytes(downloaded)).decode("ascii"),
    )
    assert plaintext == data

    marker_entry = wg_mod._read_transcript(wg_mod._wg_dir(hub_home, wg.meta.id))[-1]
    marker = wg_mod.decrypt_post(
        key,
        marker_entry["nonce"],
        marker_entry["ciphertext"],
    ).decode()
    assert marker.startswith("#file report.bin · ")
    assert f"sha256:{digest}" in marker
    assert marker.endswith("\nfinal result")
    assert marker_entry["from"] == peers[0].pubkey


@pytest.mark.asyncio
async def test_empty_file_is_rejected(short_tmp: Path) -> None:
    hub_home, hub_kp, _, peers, wg, server = _setup(short_tmp)
    params, _, _ = _encrypted_params(wg, hub_home, hub_kp, peers[0], b"x")
    params.update(size=0, data_base64="", done=True)

    with pytest.raises(alp_server.HandlerError) as exc:
        await _put(server, peers[0], params)

    assert exc.value.code == -32602


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("name", "bad\n#task #injected"),
        ("note", "context\n#skip done"),
    ],
)
@pytest.mark.asyncio
async def test_file_marker_fields_cannot_inject_protocol_markers(
    short_tmp: Path,
    field: str,
    value: str,
) -> None:
    hub_home, hub_kp, _, peers, wg, server = _setup(short_tmp)
    params, _, _ = _encrypted_params(wg, hub_home, hub_kp, peers[0], b"x")
    params[field] = value

    with pytest.raises(alp_server.HandlerError) as exc:
        await _put(server, peers[0], params)

    assert exc.value.code == -32602
    assert wg_mod._read_transcript(wg_mod._wg_dir(hub_home, wg.meta.id)) == []


def test_file_note_rejects_nested_file_marker() -> None:
    with pytest.raises(wf.WorkgroupFileError, match="protocol markers"):
        wf._validate_note(
            "use the hotel brief\n"
            f"#file evil.exe · 1KB · sha256:{'a' * 64}",
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("name", "x" * (wf._MAX_NAME_CHARS + 1)),
        ("note", "x" * (wf._MAX_NOTE_CHARS + 1)),
    ],
)
@pytest.mark.asyncio
async def test_file_marker_fields_reject_oversized_values(
    short_tmp: Path,
    field: str,
    value: str,
) -> None:
    hub_home, hub_kp, _, peers, wg, server = _setup(short_tmp)
    params, _, _ = _encrypted_params(wg, hub_home, hub_kp, peers[0], b"x")
    params[field] = value

    with pytest.raises(alp_server.HandlerError) as exc:
        await _put(server, peers[0], params)

    assert exc.value.code == -32602


@pytest.mark.asyncio
async def test_interrupted_upload_restarts_at_zero(short_tmp: Path) -> None:
    hub_home, hub_kp, _, peers, wg, server = _setup(short_tmp)
    data = b"x" * (wf.CHUNK_BYTES + 20)
    params, digest, _ = _encrypted_params(wg, hub_home, hub_kp, peers[0], data)
    ciphertext = base64.b64decode(params.pop("data_base64"))
    first = ciphertext[:wf.CHUNK_BYTES]

    response = await _put(server, peers[0], {
        **params,
        "offset": 0,
        "data_base64": base64.b64encode(first).decode("ascii"),
        "done": False,
    })

    root = hub_home / "alp" / "workgroups" / wg.meta.id / "files"
    assert response["complete"] is False
    assert (root / f".{digest}.part").exists()
    assert not (root / f"{digest}.bin").exists()

    result = None
    for offset in range(0, len(ciphertext), wf.CHUNK_BYTES):
        chunk = ciphertext[offset: offset + wf.CHUNK_BYTES]
        result = await _put(server, peers[0], {
            **params,
            "offset": offset,
            "data_base64": base64.b64encode(chunk).decode("ascii"),
            "done": offset + len(chunk) == len(ciphertext),
        })
    assert result["complete"] is True
    assert not (root / f".{digest}.part").exists()


@pytest.mark.asyncio
async def test_next_upload_removes_stale_partial(short_tmp: Path) -> None:
    hub_home, hub_kp, _, peers, wg, server = _setup(short_tmp)
    root = hub_home / "alp" / "workgroups" / wg.meta.id / "files"
    root.mkdir()
    stale = root / f".{'a' * 64}.part"
    stale_meta = root / f".{'a' * 64}.part.json"
    orphan_meta = root / f".{'b' * 64}.part.json"
    stale.write_bytes(b"partial")
    stale_meta.write_text("{}")
    orphan_meta.write_text("{}")
    old = time.time() - wf._PART_TTL_SECONDS - 1
    os.utime(stale, (old, old))
    os.utime(orphan_meta, (old, old))
    params, _, _ = _encrypted_params(wg, hub_home, hub_kp, peers[0], b"new")

    await _put(server, peers[0], params)

    assert not stale.exists()
    assert not stale_meta.exists()
    assert not orphan_meta.exists()


@pytest.mark.asyncio
async def test_sha_mismatch_removes_partial(short_tmp: Path) -> None:
    hub_home, hub_kp, _, peers, wg, server = _setup(short_tmp)
    data = b"actual"
    params, _, _ = _encrypted_params(wg, hub_home, hub_kp, peers[0], data)
    wrong = hashlib.sha256(b"different").hexdigest()
    params["sha256"] = wrong

    with pytest.raises(alp_server.HandlerError) as exc:
        await _put(server, peers[0], params)

    root = hub_home / "alp" / "workgroups" / wg.meta.id / "files"
    assert exc.value.code == -32602
    assert not (root / f".{wrong}.part").exists()
    assert not (root / f".{wrong}.part.json").exists()
    assert not (root / f"{wrong}.bin").exists()


@pytest.mark.asyncio
async def test_marker_failure_rolls_back_completed_blob(
    short_tmp: Path,
    monkeypatch,
) -> None:
    hub_home, hub_kp, _, peers, wg, server = _setup(short_tmp)
    params, digest, _ = _encrypted_params(wg, hub_home, hub_kp, peers[0], b"file")

    def fail_marker(*args, **kwargs):
        raise OSError("transcript unavailable")

    monkeypatch.setattr(wf, "_append_marker", fail_marker)

    with pytest.raises(alp_server.HandlerError) as exc:
        await _put(server, peers[0], params)

    root = hub_home / "alp" / "workgroups" / wg.meta.id / "files"
    assert exc.value.code == -32602
    assert not (root / f"{digest}.bin").exists()
    assert not (root / f"{digest}.json").exists()


@pytest.mark.asyncio
async def test_quota_rejected_before_writing(short_tmp: Path, monkeypatch) -> None:
    hub_home, hub_kp, _, peers, wg, server = _setup(short_tmp)
    params, digest, _ = _encrypted_params(wg, hub_home, hub_kp, peers[0], b"12345")
    monkeypatch.setattr(wf, "MAX_WORKGROUP_BYTES", 4)

    with pytest.raises(alp_server.HandlerError) as exc:
        await _put(server, peers[0], params)

    root = hub_home / "alp" / "workgroups" / wg.meta.id / "files"
    assert exc.value.code == -32012
    assert not (root / f".{digest}.part").exists()


@pytest.mark.asyncio
async def test_put_get_require_membership_and_existing_workgroup(short_tmp: Path) -> None:
    hub_home, hub_kp, _, peers, wg, server = _setup(short_tmp)
    outsider_home = short_tmp / "outsider"
    outsider_home.mkdir()
    outsider = Peer(id="outsider", pubkey=load_or_generate(outsider_home).pubkey_b64())
    params, digest, _ = _encrypted_params(wg, hub_home, hub_kp, peers[0], b"x")

    for method, request in (
        ("workgroup.file_put", params),
        ("workgroup.file_get", {"workgroup_id": wg.meta.id, "sha256": digest, "offset": 0}),
    ):
        with pytest.raises(alp_server.HandlerError) as exc:
            await server.handlers[method](request, outsider, server)
        assert exc.value.code == -32008

    with pytest.raises(alp_server.HandlerError) as exc:
        await server.handlers["workgroup.file_get"](
            {"workgroup_id": "wg_missing", "sha256": digest, "offset": 0},
            peers[0],
            server,
        )
    assert exc.value.code == -32009


@pytest.mark.asyncio
async def test_put_get_require_joined_membership(short_tmp: Path) -> None:
    hub_home, hub_kp, _, peers, wg, server = _setup(short_tmp)
    member = wg.member(peers[0].pubkey)
    member.joined = False
    wg_mod._save_members(wg_mod._wg_dir(hub_home, wg.meta.id), wg.members)
    params, digest, _ = _encrypted_params(wg, hub_home, hub_kp, peers[0], b"x")

    for method, request in (
        ("workgroup.file_put", params),
        ("workgroup.file_get", {"workgroup_id": wg.meta.id, "sha256": digest}),
    ):
        with pytest.raises(alp_server.HandlerError) as exc:
            await server.handlers[method](request, peers[0], server)
        assert exc.value.code == -32008
        assert exc.value.message == "workgroup-not-joined"


@pytest.mark.asyncio
async def test_missing_blob_returns_file_not_found(short_tmp: Path) -> None:
    _, _, _, peers, wg, server = _setup(short_tmp)
    digest = hashlib.sha256(b"missing").hexdigest()

    with pytest.raises(alp_server.HandlerError) as exc:
        await _get(server, peers[0], wg.meta.id, digest)

    assert exc.value.code == -32011


@pytest.mark.asyncio
async def test_file_list_is_bounded_and_newest_first(short_tmp: Path) -> None:
    hub_home, hub_kp, _, peers, wg, server = _setup(short_tmp)
    digests = []
    for index in range(3):
        params, digest, _ = _encrypted_params(
            wg,
            hub_home,
            hub_kp,
            peers[0],
            f"file-{index}".encode(),
            name=f"file-{index}.md",
            note=f"brief {index}",
        )
        await _put(server, peers[0], params)
        digests.append(digest)
        meta_path = (
            hub_home / "alp" / "workgroups" / wg.meta.id
            / "files" / f"{digest}.json"
        )
        meta = wf._read_json(meta_path)
        meta["uploaded_at"] = f"2026-07-2{index}T00:00:00Z"
        wf._atomic_json(meta_path, meta)

    first = await _list(server, peers[0], wg.meta.id, limit=2)
    second = await _list(
        server,
        peers[0],
        wg.meta.id,
        offset=first["next_offset"],
        limit=2,
    )

    assert first["total"] == 3
    assert [item["name"] for item in first["files"]] == [
        "file-2.md",
        "file-1.md",
    ]
    assert first["files"][0]["sha256"] == digests[2]
    assert first["files"][0]["note"] == "brief 2"
    assert first["next_offset"] == 2
    assert [item["name"] for item in second["files"]] == ["file-0.md"]
    assert second["next_offset"] is None


@pytest.mark.asyncio
async def test_file_list_requires_joined_membership(short_tmp: Path) -> None:
    hub_home, _, _, peers, wg, server = _setup(short_tmp)
    member = wg.member(peers[0].pubkey)
    member.joined = False
    wg_mod._save_members(wg_mod._wg_dir(hub_home, wg.meta.id), wg.members)

    with pytest.raises(alp_server.HandlerError) as exc:
        await _list(server, peers[0], wg.meta.id)

    assert exc.value.code == -32008
    assert exc.value.message == "workgroup-not-joined"


@pytest.mark.asyncio
async def test_old_key_version_file_survives_rotation(short_tmp: Path) -> None:
    hub_home, hub_kp, member_keys, peers, wg, server = _setup(short_tmp, members=2)
    params, digest, old_key = _encrypted_params(wg, hub_home, hub_kp, peers[0], b"before")
    await _put(server, peers[0], params)

    rotated = wg_mod._rekey(hub_home, wg.meta.id, member_keys[0].pubkey_b64())
    assert rotated.meta.current_key_version == 2
    response = await _get(server, peers[1], wg.meta.id, digest)

    plaintext = wg_mod.decrypt_post(old_key, response["nonce"], response["data_base64"])
    assert plaintext == b"before"
    assert response["key_version"] == 1


@pytest.mark.asyncio
async def test_local_hub_send_rejects_paused_workgroup(short_tmp: Path) -> None:
    hub_home, _, _, _, wg, _ = _setup(short_tmp)
    wg.meta.paused = True
    wg_mod._save_meta(wg_mod._wg_dir(hub_home, wg.meta.id), wg.meta)
    source = short_tmp / "paused.bin"
    source.write_bytes(b"file")

    with pytest.raises(ValueError, match="workgroup is paused"):
        await wc.send_file(hub_home, wg.meta.id, source)

    root = hub_home / "alp" / "workgroups" / wg.meta.id / "files"
    assert not root.exists()


@pytest.mark.asyncio
async def test_member_client_decrypts_file_from_old_key_version(
    short_tmp: Path,
    monkeypatch,
) -> None:
    hub_home, hub_kp, member_keys, peers, wg, server = _setup(short_tmp, members=2)
    member_home = short_tmp / "member-1"
    remaining = wg.member(member_keys[1].pubkey_b64())
    old_sealed = remaining.sealed_key
    params, digest, _ = _encrypted_params(wg, hub_home, hub_kp, peers[0], b"before")
    await _put(server, peers[0], params)
    rotated = wg_mod._rekey(hub_home, wg.meta.id, member_keys[0].pubkey_b64())
    new_sealed = rotated.member(member_keys[1].pubkey_b64()).sealed_key
    sub = sub_mod.Subscription(
        wg_id=wg.meta.id,
        name=wg.meta.name,
        hub_id="hub",
        hub_pubkey=hub_kp.pubkey_b64(),
    )
    sub.upsert_key(1, old_sealed)
    sub.upsert_key(2, new_sealed)
    sub_mod.upsert(member_home, sub)

    async def local_call(home, kp, peer_id, method, params, timeout=30.0):
        return await server.handlers[method](params, peers[1], server)

    monkeypatch.setattr(wc, "_call", local_call)
    metadata, plaintext = await wc.get_file(member_home, wg.meta.id, digest)

    assert metadata["key_version"] == 1
    assert plaintext == b"before"


@pytest.mark.asyncio
async def test_concurrent_duplicate_uploads_deduplicate_blob(short_tmp: Path) -> None:
    hub_home, hub_kp, _, peers, wg, server = _setup(short_tmp, members=2)
    data = b"same file"
    first, digest, _ = _encrypted_params(wg, hub_home, hub_kp, peers[0], data)
    second, _, _ = _encrypted_params(wg, hub_home, hub_kp, peers[1], data)

    a, b = await asyncio.gather(
        _put(server, peers[0], first),
        _put(server, peers[1], second),
    )

    root = hub_home / "alp" / "workgroups" / wg.meta.id / "files"
    assert a["complete"] is True
    assert b["complete"] is True
    assert sorted((a["existed"], b["existed"])) == [False, True]
    assert len(list(root.glob("*.bin"))) == 1
    assert len(wg_mod._read_transcript(wg_mod._wg_dir(hub_home, wg.meta.id))) == 2


def test_destroy_removes_workgroup_files(short_tmp: Path) -> None:
    hub_home, _, _, _, wg, _ = _setup(short_tmp)
    root = hub_home / "alp" / "workgroups" / wg.meta.id / "files"
    root.mkdir()
    (root / "file.bin").write_bytes(b"ciphertext")

    wg_mod.destroy(hub_home, wg.meta.id)

    assert not root.exists()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tcp_noise_join_send_and_get_file(short_tmp: Path) -> None:
    hub_home = short_tmp / "hub"
    member_home = short_tmp / "member"
    hub_home.mkdir()
    member_home.mkdir()
    hub_kp = load_or_generate(hub_home)
    member_kp = load_or_generate(member_home)
    wg = wg_mod.create(
        hub_home,
        name="remote-files",
        hub_kp=hub_kp,
        member_pubkeys=[member_kp.pubkey_b64()],
    )
    port = _free_port()
    peers_mod.add(hub_home, Peer(id="member", pubkey=member_kp.pubkey_b64()))
    peers_mod.add(member_home, Peer(
        id="hub",
        pubkey=hub_kp.pubkey_b64(),
        address=f"127.0.0.1:{port}",
    ))
    server = alp_server.Server(
        hub_home,
        tcp_host="127.0.0.1",
        tcp_port=port,
    )
    wg_mod.register(server, hub_home)
    source = member_home / "workspace" / "remote.bin"
    source.parent.mkdir()
    source.write_bytes(b"noise transport file")

    await server.start()
    try:
        await wc.join(member_home, "hub", wg.meta.id)
        sent = await wc.send_file(member_home, wg.meta.id, source)
        listed = await wc.list_files(member_home, wg.meta.id)
        metadata, downloaded = await wc.get_file(
            member_home,
            wg.meta.id,
            sent["sha256"],
        )
    finally:
        await server.stop()

    assert metadata["name"] == source.name
    assert listed["files"][0]["sha256"] == sent["sha256"]
    assert downloaded == source.read_bytes()
