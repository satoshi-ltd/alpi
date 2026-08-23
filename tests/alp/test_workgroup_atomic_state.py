"""Hub workgroup state files must land all-or-nothing."""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

import pytest

from alpi.alp import workgroup as wg_mod


@pytest.fixture
def home() -> Path:
    d = Path(tempfile.mkdtemp(prefix="alpi-wgatomic-", dir="/tmp"))
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def wg_dir(home: Path) -> Path:
    return home / "alp" / "workgroups" / "wg_x"


def _meta() -> wg_mod.Meta:
    return wg_mod.Meta(
        id="wg_x", name="site", hub_pubkey="HUB",
        created_at="2026-08-01T00:00:00Z", current_key_version=1,
    )


def _members() -> list[wg_mod.Member]:
    return [
        wg_mod.Member(pubkey="HUB", sealed_key="hub-sealed"),
        wg_mod.Member(pubkey="ALICE", sealed_key="alice-sealed", joined=True),
    ]


def test_roster_and_meta_land_by_rename_not_by_truncating_the_live_file(
    wg_dir: Path, monkeypatch,
) -> None:
    replaced: list[str] = []
    real = os.replace

    def spy(src, dst):
        replaced.append(str(dst))
        return real(src, dst)

    monkeypatch.setattr(os, "replace", spy)
    wg_mod._save_meta(wg_dir, _meta())
    wg_mod._save_members(wg_dir, _members())

    assert replaced == [
        str(wg_dir / "meta.yaml"), str(wg_dir / "members.yaml"),
    ]
    assert not [p.name for p in wg_dir.iterdir() if p.name.startswith(".")]


def test_a_failed_roster_write_leaves_the_previous_roster_intact(
    home: Path, wg_dir: Path, monkeypatch,
) -> None:
    wg_mod._save_meta(wg_dir, _meta())
    wg_mod._save_members(wg_dir, _members())
    before = (wg_dir / "members.yaml").read_text()

    def boom(*args, **kwargs):
        raise OSError("disk full")

    # Presence rewrites the roster every ~30s per member, so a hub killed inside one must not be able to leave a 0-byte file.
    monkeypatch.setattr(os, "chmod", boom)
    with pytest.raises(OSError):
        wg_mod._save_members(wg_dir, [wg_mod.Member(pubkey="HUB", sealed_key="x")])
    monkeypatch.undo()

    assert (wg_dir / "members.yaml").read_text() == before
    wg = wg_mod.load(home, "wg_x")
    assert wg is not None
    assert wg.member("ALICE") is not None
    assert not [p.name for p in wg_dir.iterdir() if p.name.startswith(".")]


def test_an_empty_roster_file_is_what_a_definitive_rejection_looks_like(
    home: Path, wg_dir: Path,
) -> None:
    wg_mod._save_meta(wg_dir, _meta())
    (wg_dir / "members.yaml").write_text("")

    wg = wg_mod.load(home, "wg_x")
    assert wg is not None
    # The pull handler answers -32008 for every member off exactly this state, which is why the member poller must corroborate before retiring.
    assert wg.members == []
