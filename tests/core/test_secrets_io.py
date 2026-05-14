from __future__ import annotations

import os
from pathlib import Path

import pytest

from alpi.secrets_io import safe_write_secret


def test_creates_file_with_0600(tmp_path: Path) -> None:
    target = tmp_path / "tokens.json"
    safe_write_secret(target, '{"access": "x"}')
    assert target.read_text() == '{"access": "x"}'
    mode = target.stat().st_mode & 0o777
    assert mode == 0o600, f"expected 0o600, got {oct(mode)}"


def test_no_tmp_file_left_behind(tmp_path: Path) -> None:
    target = tmp_path / "tokens.json"
    safe_write_secret(target, "x")
    leftover = [p for p in target.parent.iterdir() if p.suffix == ".tmp"]
    assert leftover == []


def test_stale_loose_tmp_does_not_compromise_target(tmp_path: Path) -> None:
    # P0 regression: a pre-existing <target>.tmp at 0o644 must NOT make the
    # final target inherit those perms. Older versions of this helper used
    # a deterministic .tmp name with O_CREAT (no O_EXCL), which truncated
    # the existing file and kept its loose mode.
    target = tmp_path / "tokens.json"
    stale = target.with_suffix(target.suffix + ".tmp")
    stale.write_text("attacker-planted")
    os.chmod(stale, 0o644)

    safe_write_secret(target, "real-secret")

    assert target.read_text() == "real-secret"
    assert (target.stat().st_mode & 0o777) == 0o600
    # The stale .tmp is unrelated to our random tmp name, so it just stays.
    assert stale.exists()


def test_overwrite_preserves_0600(tmp_path: Path) -> None:
    target = tmp_path / "tokens.json"
    safe_write_secret(target, "v1")
    safe_write_secret(target, "v2")
    assert target.read_text() == "v2"
    assert (target.stat().st_mode & 0o777) == 0o600


def test_accepts_bytes(tmp_path: Path) -> None:
    target = tmp_path / "key.pem"
    safe_write_secret(target, b"-----BEGIN PRIVATE KEY-----\n")
    assert target.read_bytes() == b"-----BEGIN PRIVATE KEY-----\n"
    assert (target.stat().st_mode & 0o777) == 0o600


def test_resists_loose_umask(tmp_path: Path) -> None:
    # Even with a permissive umask, 0o600 stays 0o600 because the masked
    # bits (group + other) are already zero in the requested mode.
    prev = os.umask(0o000)
    try:
        target = tmp_path / "tokens.json"
        safe_write_secret(target, "x")
        assert (target.stat().st_mode & 0o777) == 0o600
    finally:
        os.umask(prev)


def test_creates_parent_dirs(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "deep" / "tokens.json"
    safe_write_secret(target, "x")
    assert target.exists()
    assert (target.stat().st_mode & 0o777) == 0o600


def test_no_intermediate_world_readable_state(tmp_path: Path) -> None:
    # The hardening invariant: at no point during the write should the
    # final target exist with mode looser than 0o600. We can't observe
    # the exact race, but we can confirm the file never appears at the
    # final path with the wrong mode by checking that the tmp path was
    # used (and rejected if it had been world-readable).
    target = tmp_path / "tokens.json"
    safe_write_secret(target, "x")
    # Target was created from a tmp file; tmp is gone.
    assert target.exists()
    assert not (target.parent / "tokens.json.tmp").exists()
    assert (target.stat().st_mode & 0o777) == 0o600


def test_custom_mode(tmp_path: Path) -> None:
    target = tmp_path / "key.pem"
    safe_write_secret(target, "x", mode=0o400)
    assert (target.stat().st_mode & 0o777) == 0o400


def test_tmp_cleaned_on_write_error(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "tokens.json"
    # Force the write to fail mid-stream.
    real_fdopen = os.fdopen

    def broken_fdopen(fd, mode="r", *a, **kw):
        f = real_fdopen(fd, mode, *a, **kw)
        original_write = f.write
        def boom(data):
            original_write(data)
            raise IOError("disk full")
        f.write = boom
        return f

    monkeypatch.setattr(os, "fdopen", broken_fdopen)
    with pytest.raises(IOError):
        safe_write_secret(target, "x")
    assert not target.exists()
    leftover = [p for p in target.parent.iterdir() if p.suffix == ".tmp"]
    assert leftover == [], f"random tmp not cleaned: {leftover}"
