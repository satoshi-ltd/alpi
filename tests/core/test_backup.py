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


def _seed(home: Path) -> None:
    home.mkdir(parents=True, exist_ok=True)
    # Top-level (default-profile) content
    (home / "memories").mkdir()
    (home / "memories" / "AGENT.md").write_text("# agent\nhello\n")
    (home / "memories" / "USER.md").write_text("user notes\n")
    (home / "skills").mkdir()
    (home / "skills" / "demo").mkdir()
    (home / "skills" / "demo" / "SKILL.md").write_text("---\nname: demo\n---\n")
    (home / "config.yaml").write_text("model: gpt-4\n")
    (home / ".env").write_text("OPENAI_API_KEY=sk-test\n")
    # Ephemeral state that must NOT appear in the restored home.
    (home / "logs").mkdir()
    (home / "logs" / "daemon.log").write_text("noisy\n")
    (home / "cache").mkdir()
    (home / "cache" / "tmp.bin").write_bytes(b"\x00" * 64)
    (home / "service.pid").write_text("4242\n")
    (home / "alp").mkdir()
    (home / "alp" / "alp.sock").write_text("")
    (home / "alp" / "alp_key.pem").write_text("PRIVATE KEY MATERIAL\n")
    # Named profiles under profiles/ — must be included
    (home / "profiles").mkdir()
    (home / "profiles" / "doc").mkdir()
    (home / "profiles" / "doc" / ".env").write_text("FOLDER=/tmp\n")
    (home / "profiles" / "doc" / "memories").mkdir()
    (home / "profiles" / "doc" / "memories" / "AGENT.md").write_text("doc agent\n")
    (home / "profiles" / "doc" / "skills").mkdir()
    (home / "profiles" / "doc" / "skills" / "whoop").mkdir()
    (home / "profiles" / "doc" / "skills" / "whoop" / "SKILL.md").write_text(
        "---\nname: whoop\n---\n",
    )
    # Each profile also has its own ephemeral state that must be excluded.
    (home / "profiles" / "doc" / "logs").mkdir()
    (home / "profiles" / "doc" / "logs" / "agent.log").write_text("noisy\n")
    (home / "profiles" / "doc" / "cache").mkdir()
    (home / "profiles" / "doc" / "cache" / "blob.bin").write_bytes(b"\x00" * 32)
    # Second profile to confirm multi-profile coverage.
    (home / "profiles" / "mirai").mkdir()
    (home / "profiles" / "mirai" / ".env").write_text("OTHER=value\n")


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
        "scope": "machine",
    }
    header_bytes = json.dumps(header, separators=(",", ":")).encode() + b"\n"
    ct = ChaCha20Poly1305(key).encrypt(nonce, buf.getvalue(), header_bytes)
    archive.write_bytes(backup.MAGIC + header_bytes + ct)


def test_round_trip(tmp_path: Path) -> None:
    src = tmp_path / "src"
    _seed(src)
    archive = tmp_path / "out.alpi-backup"
    info = backup.create_backup(src, archive, "correct horse battery staple")
    assert info.file_count >= 8
    assert archive.exists()
    assert archive.stat().st_mode & 0o777 == 0o600

    target = tmp_path / "restored"
    target.mkdir()
    restored = backup.restore_backup(archive, target, "correct horse battery staple")
    assert restored.target == target
    assert restored.file_count == info.file_count
    # Top-level survives
    assert (target / "config.yaml").read_text() == "model: gpt-4\n"
    assert (target / ".env").read_text() == "OPENAI_API_KEY=sk-test\n"
    assert (target / "memories" / "USER.md").read_text() == "user notes\n"
    assert (target / "alp" / "alp_key.pem").read_text() == "PRIVATE KEY MATERIAL\n"
    # All profiles survive
    assert (target / "profiles" / "doc" / ".env").read_text() == "FOLDER=/tmp\n"
    assert (target / "profiles" / "doc" / "memories" / "AGENT.md").read_text() == "doc agent\n"
    assert (target / "profiles" / "doc" / "skills" / "whoop" / "SKILL.md").exists()
    assert (target / "profiles" / "mirai" / ".env").read_text() == "OTHER=value\n"


def test_excludes_ephemeral_everywhere(tmp_path: Path) -> None:
    src = tmp_path / "src"
    _seed(src)
    archive = tmp_path / "out.alpi-backup"
    backup.create_backup(src, archive, "pw")
    target = tmp_path / "restored"
    target.mkdir()
    backup.restore_backup(archive, target, "pw")
    # Top-level ephemeral pruned
    assert not (target / "logs").exists()
    assert not (target / "cache").exists()
    assert not (target / "service.pid").exists()
    assert not (target / "alp" / "alp.sock").exists()
    # Per-profile ephemeral pruned too (deep prune at every level)
    assert not (target / "profiles" / "doc" / "logs").exists()
    assert not (target / "profiles" / "doc" / "cache").exists()


def test_wrong_passphrase(tmp_path: Path) -> None:
    src = tmp_path / "src"
    _seed(src)
    archive = tmp_path / "out.alpi-backup"
    backup.create_backup(src, archive, "right")
    target = tmp_path / "restored"
    with pytest.raises(backup.BackupError):
        backup.restore_backup(archive, target, "wrong")
    assert not (target / "config.yaml").exists()


def test_tampered_header_rejected(tmp_path: Path) -> None:
    src = tmp_path / "src"
    _seed(src)
    archive = tmp_path / "out.alpi-backup"
    backup.create_backup(src, archive, "pw")
    raw = archive.read_bytes()
    # Flip a byte in the header section so the AAD-bound tag fails.
    raw = raw[: len(backup.MAGIC) + 5] + bytes([raw[len(backup.MAGIC) + 5] ^ 0xFF]) + raw[len(backup.MAGIC) + 6 :]
    archive.write_bytes(raw)
    target = tmp_path / "restored"
    with pytest.raises(backup.BackupError):
        backup.restore_backup(archive, target, "pw")


def test_refuses_to_overwrite_archive(tmp_path: Path) -> None:
    src = tmp_path / "src"
    _seed(src)
    archive = tmp_path / "out.alpi-backup"
    backup.create_backup(src, archive, "pw")
    with pytest.raises(backup.BackupError):
        backup.create_backup(src, archive, "pw")


def test_refuses_to_restore_into_non_empty(tmp_path: Path) -> None:
    src = tmp_path / "src"
    _seed(src)
    archive = tmp_path / "out.alpi-backup"
    backup.create_backup(src, archive, "pw")
    target = tmp_path / "restored"
    target.mkdir()
    (target / "existing.txt").write_text("dont overwrite\n")
    with pytest.raises(backup.BackupError):
        backup.restore_backup(archive, target, "pw", force=False)
    # Pre-existing file untouched
    assert (target / "existing.txt").read_text() == "dont overwrite\n"


def test_force_overwrites_non_empty_target(tmp_path: Path) -> None:
    src = tmp_path / "src"
    _seed(src)
    archive = tmp_path / "out.alpi-backup"
    backup.create_backup(src, archive, "pw")
    target = tmp_path / "restored"
    target.mkdir()
    (target / "existing.txt").write_text("clobber me\n")
    backup.restore_backup(archive, target, "pw", force=True)
    assert (target / "config.yaml").exists()


def test_force_is_clean_replace_not_overlay(tmp_path: Path) -> None:
    src = tmp_path / "src"
    _seed(src)
    archive = tmp_path / "out.alpi-backup"
    backup.create_backup(src, archive, "pw")
    target = tmp_path / "restored"
    target.mkdir()
    # Pre-existing junk that is NOT in the archive — must be gone after restore.
    (target / "stale.txt").write_text("leftover\n")
    (target / "profiles").mkdir()
    (target / "profiles" / "ghost").mkdir()
    (target / "profiles" / "ghost" / "config.yaml").write_text("orphan\n")
    backup.restore_backup(archive, target, "pw", force=True)
    assert not (target / "stale.txt").exists()
    assert not (target / "profiles" / "ghost").exists()
    # And the archive contents did land.
    assert (target / "config.yaml").exists()
    assert (target / "profiles" / "doc" / ".env").exists()


def test_force_preserves_archive_inside_target(tmp_path: Path) -> None:
    src = tmp_path / "src"
    _seed(src)
    target = tmp_path / "restored"
    target.mkdir()
    (target / "stale.txt").write_text("leftover\n")
    # Archive lives INSIDE the target — must survive the wipe.
    archive = target / "self.alpi-backup"
    backup.create_backup(src, archive, "pw")
    backup.restore_backup(archive, target, "pw", force=True)
    assert archive.exists()
    assert not (target / "stale.txt").exists()
    assert (target / "config.yaml").exists()


def test_force_preserves_archive_in_subdir_of_target(tmp_path: Path) -> None:
    src = tmp_path / "src"
    _seed(src)
    target = tmp_path / "restored"
    (target / "backups").mkdir(parents=True)
    archive = target / "backups" / "self.alpi-backup"
    backup.create_backup(src, archive, "pw")
    # Stale data alongside the backups/ subtree must still be wiped.
    (target / "stale.txt").write_text("leftover\n")
    (target / "other").mkdir()
    (target / "other" / "junk.txt").write_text("junk\n")
    backup.restore_backup(archive, target, "pw", force=True)
    assert archive.exists()
    assert (target / "backups").exists()
    assert not (target / "stale.txt").exists()
    assert not (target / "other").exists()
    assert (target / "config.yaml").exists()


def test_wrong_passphrase_does_not_wipe_target(tmp_path: Path) -> None:
    src = tmp_path / "src"
    _seed(src)
    archive = tmp_path / "out.alpi-backup"
    backup.create_backup(src, archive, "right")
    target = tmp_path / "restored"
    target.mkdir()
    (target / "precious.txt").write_text("user data\n")
    with pytest.raises(backup.BackupError):
        backup.restore_backup(archive, target, "wrong", force=True)
    assert (target / "precious.txt").read_text() == "user data\n"


def test_rejects_wrong_tar_root(tmp_path: Path) -> None:
    archive = tmp_path / "wrong-root.alpi-backup"
    _write_encrypted_tar(archive, [
        ("not-alpi-home/config.yaml", b"model: x\n"),
    ])
    target = tmp_path / "restored"
    with pytest.raises(backup.BackupError, match="unexpected tar root"):
        backup.restore_backup(archive, target, "pw")


def test_rejects_unsupported_scope(tmp_path: Path) -> None:
    # Build an envelope whose JSON header carries a non-"machine" scope.
    archive = tmp_path / "scoped.alpi-backup"
    _write_encrypted_tar(archive, [("alpi-home/config.yaml", b"x\n")])
    raw = archive.read_bytes()
    magic_len = len(backup.MAGIC)
    header_end = raw.index(b"\n", magic_len)
    header = json.loads(raw[magic_len:header_end].decode())
    header["scope"] = "profile"
    new_header = json.dumps(header, separators=(",", ":")).encode() + b"\n"
    archive.write_bytes(raw[:magic_len] + new_header + raw[header_end + 1:])
    with pytest.raises(backup.BackupError, match="scope"):
        backup.inspect(archive)
    with pytest.raises(backup.BackupError, match="scope"):
        backup.restore_backup(archive, tmp_path / "restored", "pw")


def test_inspect_does_not_decrypt(tmp_path: Path) -> None:
    src = tmp_path / "src"
    _seed(src)
    archive = tmp_path / "out.alpi-backup"
    backup.create_backup(src, archive, "pw")
    header = backup.inspect(archive)
    assert header["scope"] == "machine"
    assert header["v"] == 1
    assert "file_count" in header
    assert "created_at" in header


def test_rejects_non_backup_file(tmp_path: Path) -> None:
    archive = tmp_path / "not-a-backup"
    archive.write_bytes(b"hello world\n")
    with pytest.raises(backup.BackupError):
        backup.inspect(archive)


def test_path_traversal_rejected(tmp_path: Path) -> None:
    archive = tmp_path / "evil.alpi-backup"
    _write_encrypted_tar(archive, [
        ("alpi-home/../etc/passwd", b"root::0:0:root:/:/bin/sh\n"),
    ])
    target = tmp_path / "restored"
    with pytest.raises(backup.BackupError):
        backup.restore_backup(archive, target, "pw")


def test_path_traversal_rejected_without_partial_extract(tmp_path: Path) -> None:
    archive = tmp_path / "evil.alpi-backup"
    _write_encrypted_tar(archive, [
        ("alpi-home/ok.txt", b"safe\n"),
        ("alpi-home/../etc/escape", b"nope\n"),
    ])
    target = tmp_path / "restored"
    target.mkdir()
    with pytest.raises(backup.BackupError):
        backup.restore_backup(archive, target, "pw")
    # The safe file must NOT be partially extracted.
    assert not (target / "ok.txt").exists()


def test_unsupported_kdf_params_rejected_before_deriving(
    tmp_path: Path, monkeypatch,
) -> None:
    src = tmp_path / "src"
    _seed(src)
    archive = tmp_path / "out.alpi-backup"
    backup.create_backup(src, archive, "pw")
    # Mutate the header to claim a cheaper KDF; AAD makes this fail with
    # InvalidTag, but the early validator catches it first.
    raw = archive.read_bytes()
    head, sep, rest = raw.partition(b"\n")
    header_line, _, ct = rest.partition(b"\n")
    header = json.loads(header_line)
    header["kdf_params"] = {"n": 2, "r": 1, "p": 1, "length": 32}
    new_header_bytes = json.dumps(header, separators=(",", ":")).encode()
    archive.write_bytes(head + b"\n" + new_header_bytes + b"\n" + ct)
    target = tmp_path / "restored"
    with pytest.raises(backup.BackupError):
        backup.restore_backup(archive, target, "pw")


def test_empty_passphrase_rejected(tmp_path: Path) -> None:
    src = tmp_path / "src"
    _seed(src)
    archive = tmp_path / "out.alpi-backup"
    with pytest.raises(backup.BackupError):
        backup.create_backup(src, archive, "")


def test_empty_home_rejected(tmp_path: Path) -> None:
    src = tmp_path / "empty"
    src.mkdir()
    archive = tmp_path / "out.alpi-backup"
    with pytest.raises(backup.BackupError):
        backup.create_backup(src, archive, "pw")


def test_cli_round_trip(tmp_home: Path) -> None:
    # tmp_home points at the alpi root for this test.
    _seed(tmp_home)
    runner = CliRunner()
    out = tmp_home / "backup.alpi-backup"
    res = runner.invoke(
        cli,
        ["backup", "--out", str(out), "--passphrase-stdin"],
        input="hunter2\nhunter2\n",
        env={"ALPI_HOME": str(tmp_home)},
    )
    assert res.exit_code == 0, res.output
    assert out.exists()
    # Wipe the home (except the backup file itself), restore it, verify.
    for p in tmp_home.iterdir():
        if p == out:
            continue
        if p.is_dir():
            import shutil
            shutil.rmtree(p)
        else:
            p.unlink()
    res = runner.invoke(
        cli,
        ["restore", str(out), "--passphrase-stdin", "--force"],
        input="hunter2\n",
        env={"ALPI_HOME": str(tmp_home)},
    )
    assert res.exit_code == 0, res.output
    assert (tmp_home / "config.yaml").exists()
    assert (tmp_home / "profiles" / "doc" / "skills" / "whoop" / "SKILL.md").exists()


def test_preview_groups_by_default_and_profiles(tmp_path: Path) -> None:
    src = tmp_path / "src"
    _seed(src)
    pv = backup.preview(src)
    default_names = {e.name for e in pv.default_entries}
    profile_names = {e.name for e in pv.profile_entries}
    # Named profiles land in the profiles section, by bare name.
    assert "doc" in profile_names
    assert "mirai" in profile_names
    # Non-profile top-level dirs / files land in the default section.
    assert "memories" in default_names
    assert "skills" in default_names
    assert "alp" in default_names
    assert ".env" in default_names
    # Excluded state never enters either section.
    assert "logs" not in default_names | profile_names
    assert "cache" not in default_names | profile_names
    assert "service.pid" not in default_names | profile_names
    # Excludes apply recursively too — the doc profile has its own logs/cache.
    doc = next(e for e in pv.profile_entries if e.name == "doc")
    assert doc.file_count >= 3  # .env + memories/AGENT.md + skills/whoop/SKILL.md
    # Totals match what create_backup will archive.
    info = backup.create_backup(src, tmp_path / "out.alpi-backup", "pw")
    assert pv.total_files == info.file_count


def test_preview_and_backup_skip_ds_store(tmp_path: Path) -> None:
    src = tmp_path / "src"
    _seed(src)
    (src / ".DS_Store").write_bytes(b"\x00" * 256)
    (src / "profiles" / "doc" / ".DS_Store").write_bytes(b"\x00" * 256)
    pv = backup.preview(src)
    default_names = {e.name for e in pv.default_entries}
    assert ".DS_Store" not in default_names
    info = backup.create_backup(src, tmp_path / "out.alpi-backup", "pw")
    target = tmp_path / "restored"
    target.mkdir()
    backup.restore_backup(tmp_path / "out.alpi-backup", target, "pw")
    assert not (target / ".DS_Store").exists()
    assert not (target / "profiles" / "doc" / ".DS_Store").exists()
    assert info.file_count == pv.total_files


def test_preview_largest_files_surfaces_big_blobs(tmp_path: Path) -> None:
    src = tmp_path / "src"
    _seed(src)
    # A 2MB blob inside the default profile, plus a small file that must
    # not appear in the largest-files list.
    (src / "profiles" / "doc" / "knowledge.sqlite").write_bytes(b"\x00" * 2 * 1024 * 1024)
    (src / "profiles" / "doc" / "tiny.txt").write_text("tiny\n")
    pv = backup.preview(src)
    paths = [f.path for f in pv.largest_files]
    assert "profiles/doc/knowledge.sqlite" in paths
    assert "profiles/doc/tiny.txt" not in paths
    assert all(f.size >= 1024 * 1024 for f in pv.largest_files)
    assert len(pv.largest_files) <= 5


def test_preview_shown_before_passphrase(tmp_home: Path) -> None:
    _seed(tmp_home)
    runner = CliRunner()
    out = tmp_home / "backup.alpi-backup"
    res = runner.invoke(
        cli,
        ["backup", "--out", str(out), "--passphrase-stdin"],
        input="hunter2\nhunter2\n",
        env={"ALPI_HOME": str(tmp_home)},
    )
    assert res.exit_code == 0, res.output
    assert "preview:" in res.output
    assert "default:" in res.output
    assert "profiles (" in res.output
    assert "doc" in res.output
    assert "mirai" in res.output
    # Excludes must not leak into the preview either.
    assert "logs" not in res.output.split("preview:")[1].split("backup:")[0]


def test_cli_backup_refuses_overwrite_without_force(tmp_home: Path) -> None:
    _seed(tmp_home)
    runner = CliRunner()
    out = tmp_home / "backup.alpi-backup"
    out.write_bytes(b"existing")
    res = runner.invoke(
        cli,
        ["backup", "--out", str(out), "--passphrase-stdin"],
        input="hunter2\nhunter2\n",
        env={"ALPI_HOME": str(tmp_home)},
    )
    assert res.exit_code != 0
    assert "already exists" in res.output


def test_excludes_out_only_at_home_and_profile_roots(tmp_path: Path) -> None:
    src = tmp_path / "src"
    _seed(src)
    (src / "out").mkdir()
    (src / "out" / "chart.png").write_text("png")
    (src / "profiles" / "doc" / "out").mkdir()
    (src / "profiles" / "doc" / "out" / "report.pdf").write_text("pdf")
    (src / "profiles" / "doc" / "skills" / "whoop" / "out").mkdir()
    (src / "profiles" / "doc" / "skills" / "whoop" / "out" / "state.json").write_text("{}")
    archive = tmp_path / "out.alpi-backup"
    backup.create_backup(src, archive, "pw")
    target = tmp_path / "restored"
    target.mkdir()
    backup.restore_backup(archive, target, "pw")
    assert not (target / "out").exists()
    assert not (target / "profiles" / "doc" / "out").exists()
    assert (target / "profiles" / "doc" / "skills" / "whoop" / "out" / "state.json").exists()
