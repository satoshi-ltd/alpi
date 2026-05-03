"""Round-trip + safety tests for ``alpi backup`` / ``alpi restore``."""

from __future__ import annotations

import base64
import gzip
import io
import json
import os
import tarfile
from pathlib import Path

import pytest
from click.testing import CliRunner
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305

from alpi import backup
from alpi.cli import main as cli


def _seed(profile: Path) -> None:
    profile.mkdir(parents=True, exist_ok=True)
    (profile / "memories").mkdir()
    (profile / "memories" / "AGENT.md").write_text("# agent\nhello\n")
    (profile / "memories" / "USER.md").write_text("user notes\n")
    (profile / "skills").mkdir()
    (profile / "skills" / "demo").mkdir()
    (profile / "skills" / "demo" / "SKILL.md").write_text("---\nname: demo\n---\n")
    (profile / "config.yaml").write_text("model: gpt-4\n")
    (profile / ".env").write_text("OPENAI_API_KEY=sk-test\n")
    # Ephemeral state that must NOT appear in the restored profile.
    (profile / "logs").mkdir()
    (profile / "logs" / "daemon.log").write_text("noisy\n")
    (profile / "cache").mkdir()
    (profile / "cache" / "tmp.bin").write_bytes(b"\x00" * 64)
    (profile / "service.pid").write_text("4242\n")
    (profile / "alp").mkdir()
    (profile / "alp" / "alp.sock").write_text("")
    # Nested profiles dir must not recurse into other profiles.
    (profile / "profiles").mkdir()
    (profile / "profiles" / "other").mkdir()
    (profile / "profiles" / "other" / "leak.txt").write_text("nope\n")


def _write_encrypted_tar(archive: Path, files: list[tuple[str, bytes]]) -> None:
    salt = os.urandom(backup.SALT_BYTES)
    nonce = os.urandom(backup.NONCE_BYTES)
    key = backup._derive_key("pw", salt, n=backup.SCRYPT_N, r=backup.SCRYPT_R, p=backup.SCRYPT_P)
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", mtime=0) as gz:
        with tarfile.open(fileobj=gz, mode="w") as tar:
            for name, data in files:
                info = tarfile.TarInfo(name=name)
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
    header = {
        "v": 1,
        "kdf": "scrypt",
        "kdf_params": {"n": backup.SCRYPT_N, "r": backup.SCRYPT_R, "p": backup.SCRYPT_P, "length": backup.KEY_BYTES},
        "cipher": "chacha20poly1305",
        "compression": "gzip",
        "salt": base64.b64encode(salt).decode(),
        "nonce": base64.b64encode(nonce).decode(),
        "profile": "default",
    }
    header_bytes = json.dumps(header, separators=(",", ":")).encode() + b"\n"
    ct = ChaCha20Poly1305(key).encrypt(nonce, buf.getvalue(), header_bytes)
    archive.write_bytes(backup.MAGIC + header_bytes + ct)


def test_round_trip(tmp_path: Path) -> None:
    src = tmp_path / "src"
    _seed(src)
    archive = tmp_path / "out.alpi-backup"
    info = backup.create_backup(src, archive, "correct horse battery staple", profile_name="default")
    assert info.file_count >= 5
    assert archive.exists()
    assert archive.stat().st_mode & 0o777 == 0o600

    target = tmp_path / "restored"
    r = backup.restore_backup(archive, target, "correct horse battery staple")
    assert r.profile == "default"
    assert (target / "memories" / "AGENT.md").read_text() == "# agent\nhello\n"
    assert (target / "config.yaml").read_text() == "model: gpt-4\n"
    assert (target / ".env").read_text() == "OPENAI_API_KEY=sk-test\n"
    assert (target / "skills" / "demo" / "SKILL.md").exists()


def test_excludes_ephemeral(tmp_path: Path) -> None:
    src = tmp_path / "src"
    _seed(src)
    archive = tmp_path / "out.alpi-backup"
    backup.create_backup(src, archive, "pw", profile_name="default")

    target = tmp_path / "restored"
    backup.restore_backup(archive, target, "pw")
    assert not (target / "logs").exists()
    assert not (target / "cache").exists()
    assert not (target / "service.pid").exists()
    assert not (target / "alp" / "alp.sock").exists()
    assert not (target / "profiles").exists()


def test_wrong_passphrase(tmp_path: Path) -> None:
    src = tmp_path / "src"
    _seed(src)
    archive = tmp_path / "out.alpi-backup"
    backup.create_backup(src, archive, "right", profile_name="default")
    target = tmp_path / "restored"
    with pytest.raises(backup.BackupError, match="decryption failed"):
        backup.restore_backup(archive, target, "wrong")
    # Failed decrypt must not have created any files in the target.
    if target.exists():
        assert not any(target.rglob("*"))


def test_tampered_header_rejected(tmp_path: Path) -> None:
    src = tmp_path / "src"
    _seed(src)
    archive = tmp_path / "out.alpi-backup"
    backup.create_backup(src, archive, "pw", profile_name="default")
    raw = archive.read_bytes()
    magic_end = raw.index(b"\n") + 1
    nl = raw.index(b"\n", magic_end)
    header = json.loads(raw[magic_end:nl])
    header["profile"] = "evil"
    new_header = (json.dumps(header, separators=(",", ":")).encode("utf-8") + b"\n")
    tampered = raw[:magic_end] + new_header + raw[nl + 1:]
    archive.write_bytes(tampered)
    with pytest.raises(backup.BackupError, match="decryption failed"):
        backup.restore_backup(archive, tmp_path / "restored", "pw")


def test_refuses_to_overwrite_archive(tmp_path: Path) -> None:
    src = tmp_path / "src"
    _seed(src)
    archive = tmp_path / "out.alpi-backup"
    backup.create_backup(src, archive, "pw", profile_name="default")
    with pytest.raises(backup.BackupError, match="already exists"):
        backup.create_backup(src, archive, "pw", profile_name="default")


def test_refuses_to_restore_into_non_empty(tmp_path: Path) -> None:
    src = tmp_path / "src"
    _seed(src)
    archive = tmp_path / "out.alpi-backup"
    backup.create_backup(src, archive, "pw", profile_name="default")
    target = tmp_path / "restored"
    target.mkdir()
    (target / "existing.txt").write_text("keep")
    with pytest.raises(backup.BackupError, match="not empty"):
        backup.restore_backup(archive, target, "pw")
    # File must still be there — refusal is non-destructive.
    assert (target / "existing.txt").read_text() == "keep"


def test_force_overwrites_non_empty_target(tmp_path: Path) -> None:
    src = tmp_path / "src"
    _seed(src)
    archive = tmp_path / "out.alpi-backup"
    backup.create_backup(src, archive, "pw", profile_name="default")
    target = tmp_path / "restored"
    target.mkdir()
    (target / "leftover.txt").write_text("old")
    backup.restore_backup(archive, target, "pw", force=True)
    assert (target / "memories" / "AGENT.md").exists()
    # The leftover file is *not* deleted; restore overlays the backup.
    assert (target / "leftover.txt").read_text() == "old"


def test_inspect_does_not_decrypt(tmp_path: Path) -> None:
    src = tmp_path / "src"
    _seed(src)
    archive = tmp_path / "out.alpi-backup"
    backup.create_backup(src, archive, "pw", profile_name="myprofile")
    header = backup.inspect(archive)
    assert header["profile"] == "myprofile"
    assert header["v"] == 1
    assert header["cipher"] == "chacha20poly1305"
    assert "salt" in header and "nonce" in header


def test_rejects_non_backup_file(tmp_path: Path) -> None:
    bogus = tmp_path / "bogus.bin"
    bogus.write_bytes(b"this is not a backup\n")
    with pytest.raises(backup.BackupError, match="bad magic"):
        backup.inspect(bogus)


def test_path_traversal_rejected(tmp_path: Path) -> None:
    """A hostile archive must not write outside the target dir."""
    archive = tmp_path / "evil.alpi-backup"
    _write_encrypted_tar(archive, [("default/../../escape.txt", b"pwn\n")])
    with pytest.raises(backup.BackupError, match="unsafe path"):
        backup.restore_backup(archive, tmp_path / "target", "pw")
    assert not (tmp_path / "escape.txt").exists()


def test_path_traversal_rejected_without_partial_extract(tmp_path: Path) -> None:
    archive = tmp_path / "evil.alpi-backup"
    _write_encrypted_tar(
        archive,
        [
            ("default/safe.txt", b"safe\n"),
            ("default/../../escape.txt", b"pwn\n"),
        ],
    )
    target = tmp_path / "target"
    with pytest.raises(backup.BackupError, match="unsafe path"):
        backup.restore_backup(archive, target, "pw")
    assert not target.exists() or not any(target.rglob("*"))
    assert not (tmp_path / "escape.txt").exists()


def test_unsupported_kdf_params_rejected_before_deriving(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    archive = tmp_path / "hostile.alpi-backup"
    header = {
        "v": 1,
        "kdf": "scrypt",
        "kdf_params": {"n": 2 ** 30, "r": 8, "p": 1, "length": backup.KEY_BYTES},
        "cipher": "chacha20poly1305",
        "compression": "gzip",
        "salt": base64.b64encode(os.urandom(backup.SALT_BYTES)).decode(),
        "nonce": base64.b64encode(os.urandom(backup.NONCE_BYTES)).decode(),
        "profile": "default",
    }
    header_bytes = json.dumps(header, separators=(",", ":")).encode() + b"\n"
    archive.write_bytes(backup.MAGIC + header_bytes + b"not decrypted")

    def fail_if_called(*args, **kwargs):
        pytest.fail("_derive_key should not be called for unsupported params")

    monkeypatch.setattr(backup, "_derive_key", fail_if_called)
    with pytest.raises(backup.BackupError, match="unsupported backup crypto parameters"):
        backup.restore_backup(archive, tmp_path / "target", "pw")


def test_empty_passphrase_rejected(tmp_path: Path) -> None:
    src = tmp_path / "src"
    _seed(src)
    with pytest.raises(backup.BackupError, match="passphrase"):
        backup.create_backup(src, tmp_path / "out.alpi-backup", "", profile_name="default")


def test_empty_profile_rejected(tmp_path: Path) -> None:
    src = tmp_path / "empty"
    src.mkdir()
    with pytest.raises(backup.BackupError, match="empty"):
        backup.create_backup(src, tmp_path / "out.alpi-backup", "pw", profile_name="empty")


# ------------------------------------------------------------------ CLI


def test_cli_round_trip(tmp_home: Path) -> None:
    from alpi import home as home_mod
    home_mod.ensure_home(tmp_home)
    (tmp_home / "memories" / "AGENT.md").write_text("# from cli\n")

    runner = CliRunner()
    archive = tmp_home / "out.alpi-backup"
    res = runner.invoke(
        cli, ["backup", "--out", str(archive), "--passphrase-stdin"],
        input="cli-pass\n",
    )
    assert res.exit_code == 0, res.output
    assert archive.exists()

    # Drop the original to prove restore reconstructs it.
    (tmp_home / "memories" / "AGENT.md").unlink()
    res = runner.invoke(
        cli, ["restore", str(archive), "--passphrase-stdin", "--force"],
        input="cli-pass\n",
    )
    assert res.exit_code == 0, res.output
    assert (tmp_home / "memories" / "AGENT.md").read_text() == "# from cli\n"


def test_cli_backup_refuses_overwrite_without_force(tmp_home: Path) -> None:
    from alpi import home as home_mod
    home_mod.ensure_home(tmp_home)
    (tmp_home / "memories" / "AGENT.md").write_text("hi\n")
    runner = CliRunner()
    archive = tmp_home / "out.alpi-backup"
    archive.write_bytes(b"already here\n")
    res = runner.invoke(
        cli, ["backup", "--out", str(archive), "--passphrase-stdin"],
        input="pw\n",
    )
    assert res.exit_code != 0
    assert "already exists" in res.output
    # Sentinel file is untouched.
    assert archive.read_bytes() == b"already here\n"
