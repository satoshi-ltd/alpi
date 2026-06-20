import os
from pathlib import Path

import pytest

from alpi import home as home_mod


def _mode(p: Path) -> int:
    return os.stat(p).st_mode & 0o777


pytestmark = pytest.mark.skipif(os.name != "posix", reason="POSIX modes only")


def test_ensure_home_chmods_home_and_private_subdirs_to_0700(tmp_path: Path):
    home = tmp_path / "h"
    home_mod.ensure_home(home)
    assert _mode(home) == 0o700, f"profile home is {oct(_mode(home))}, not 0700"
    for sub in home_mod._PRIVATE_SUBDIRS:
        assert _mode(home / sub) == 0o700, f"{sub} is {oct(_mode(home / sub))}, not 0700"


def test_ensure_home_tightens_existing_loose_dirs(tmp_path: Path):
    home = tmp_path / "h"
    home.mkdir()
    home.chmod(0o755)
    (home / "sessions").mkdir(parents=True)
    (home / "sessions").chmod(0o755)
    assert _mode(home) == 0o755
    assert _mode(home / "sessions") == 0o755

    home_mod.ensure_home(home)

    assert _mode(home) == 0o700
    assert _mode(home / "sessions") == 0o700


def test_ensure_home_chmod_failure_does_not_crash(tmp_path: Path, monkeypatch):
    home = tmp_path / "h"

    def _raise(self, mode):
        raise OSError("simulated SMB/FAT chmod refusal")

    monkeypatch.setattr(Path, "chmod", _raise)
    home_mod.ensure_home(home)
    assert home.exists()
    assert (home / "sessions").exists()


def test_audit_flags_world_readable_private_dirs(tmp_path: Path):
    from alpi.audit import _audit_permissions

    home = tmp_path
    home_mod.ensure_home(home)
    (home / "memories").chmod(0o755)
    (home / "logs").chmod(0o750)

    checks = _audit_permissions(home)
    flagged = {c.name for c in checks if c.status in {"warn", "fail"}}
    assert "memories/" in flagged
    assert "logs/" in flagged


def test_audit_clean_when_all_private_dirs_are_0700(tmp_path: Path):
    from alpi.audit import _audit_permissions

    home = tmp_path
    home_mod.ensure_home(home)
    checks = _audit_permissions(home)
    bad = [c for c in checks if c.status in {"warn", "fail"}]
    assert not bad, f"expected no warnings after ensure_home, got: {[(c.name, c.status, c.detail) for c in bad]}"
