import multiprocessing as mp
import os
import threading
from pathlib import Path

import yaml

from alpi.alp import peers as peers_mod
from alpi.alp.peers import Peer


def _make_peer(i: int) -> Peer:
    return Peer(
        id=f"peer{i:03d}",
        pubkey=f"PUBKEY{i:020d}",
        alias=f"alias{i}",
        address=None,
        allow=["link.ping"],
    )


def test_save_writes_yaml_atomically(tmp_path: Path):
    peers_mod.save(tmp_path, [_make_peer(1), _make_peer(2)])
    target = peers_mod.path(tmp_path)
    assert target.exists()
    loaded = yaml.safe_load(target.read_text())
    assert [e["id"] for e in loaded] == ["peer001", "peer002"]


def test_save_leaves_no_tmp_sibling_on_success(tmp_path: Path):
    peers_mod.save(tmp_path, [_make_peer(1)])
    target = peers_mod.path(tmp_path)
    leftover = [p for p in target.parent.glob(f".{target.name}.*") if p.is_file()]
    assert not leftover, f"unexpected .tmp sibling left behind: {leftover}"


def test_save_preserves_original_on_crash_mid_replace(tmp_path: Path, monkeypatch):
    peers_mod.save(tmp_path, [_make_peer(1)])
    target = peers_mod.path(tmp_path)
    original_bytes = target.read_bytes()

    def boom(*args, **kwargs):
        raise OSError("simulated rename failure (disk full)")

    monkeypatch.setattr(os, "replace", boom)
    try:
        peers_mod.save(tmp_path, [_make_peer(99)])
    except OSError:
        pass
    assert target.read_bytes() == original_bytes


def test_save_fsyncs_directory_for_power_loss_durability(tmp_path: Path, monkeypatch):
    if not hasattr(os, "O_DIRECTORY"):
        return
    dir_fsyncs: list[int] = []
    real_fsync = os.fsync
    real_fstat = os.fstat

    def tracking_fsync(fd: int) -> None:
        try:
            st = real_fstat(fd)
            from stat import S_ISDIR
            if S_ISDIR(st.st_mode):
                dir_fsyncs.append(fd)
        except OSError:
            pass
        real_fsync(fd)

    monkeypatch.setattr(os, "fsync", tracking_fsync)
    peers_mod.save(tmp_path, [_make_peer(1)])
    assert dir_fsyncs, (
        "atomic_write_yaml must fsync the parent directory after os.replace "
        "so the rename survives a power loss; got zero directory fsyncs"
    )


def test_save_cleans_up_tmp_when_replace_fails(tmp_path: Path, monkeypatch):
    peers_mod.save(tmp_path, [_make_peer(1)])
    target = peers_mod.path(tmp_path)

    def boom(*args, **kwargs):
        raise OSError("simulated rename failure")

    monkeypatch.setattr(os, "replace", boom)
    try:
        peers_mod.save(tmp_path, [_make_peer(99)])
    except OSError:
        pass
    leftover = [p for p in target.parent.glob(f".{target.name}.*") if p.is_file()]
    assert not leftover, (
        f"on a failed os.replace the helper must unlink its mkstemp temp; "
        f"orphans found: {leftover}"
    )


def test_save_sequence_never_leaves_truncated_yaml(tmp_path: Path):
    target = peers_mod.path(tmp_path)
    for i in range(50):
        peers_mod.save(tmp_path, [_make_peer(j) for j in range(i + 1)])
        loaded = yaml.safe_load(target.read_text())
        assert isinstance(loaded, list)
        assert len(loaded) == i + 1
        assert loaded[-1]["id"] == f"peer{i:03d}"


def test_concurrent_threaded_saves_each_produce_valid_yaml(tmp_path: Path):
    target = peers_mod.path(tmp_path)
    errors: list[BaseException] = []

    def writer(start: int) -> None:
        try:
            for i in range(start, start + 20):
                peers_mod.save(tmp_path, [_make_peer(i)])
        except BaseException as e:
            errors.append(e)

    threads = [threading.Thread(target=writer, args=(s,)) for s in (0, 100, 200)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors, f"unexpected save() failure under contention: {errors!r}"

    loaded = yaml.safe_load(target.read_text())
    assert isinstance(loaded, list) and len(loaded) == 1
    leftover = [p for p in target.parent.glob(f".{target.name}.*") if p.is_file()]
    assert not leftover, (
        f"no mkstemp temps must survive a contended write session; orphans: {leftover}"
    )


def _mp_add_worker(home_str: str, i: int) -> None:
    from alpi.alp import peers as ps
    from alpi.alp.peers import Peer
    ps.add(Path(home_str), Peer(
        id=f"peer{i:03d}",
        pubkey=f"PUBKEY{i:020d}",
        alias="",
        address=None,
        allow=["link.ping"],
    ))


def test_concurrent_multiprocess_adds_do_not_lose_updates(tmp_path: Path):
    target = peers_mod.path(tmp_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("[]\n")

    N = 20
    ctx = mp.get_context("spawn")
    procs = [ctx.Process(target=_mp_add_worker, args=(str(tmp_path), i)) for i in range(N)]
    for p in procs:
        p.start()
    for p in procs:
        p.join(timeout=60)
    for p in procs:
        assert p.exitcode == 0, f"worker pid={p.pid} exitcode={p.exitcode}"

    final = peers_mod.load(tmp_path)
    ids = sorted(p.id for p in final)
    expected = sorted(f"peer{i:03d}" for i in range(N))
    assert ids == expected, (
        f"every peers.add must survive contention; lost updates: "
        f"missing={set(expected) - set(ids)}"
    )
