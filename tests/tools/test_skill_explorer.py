"""Pure domain helpers behind the Skills Explorer surface."""

from __future__ import annotations

from pathlib import Path

import pytest

from alpi.tools import skill


def test_skill_ftype_maps_extensions() -> None:
    assert skill._skill_ftype("SKILL.md") == "skill"
    assert skill._skill_ftype("oauth.py") == "py"
    assert skill._skill_ftype("api.md") == "md"
    assert skill._skill_ftype("seen.sqlite") == "binary"
    assert skill._skill_ftype("notes.txt") == "text"


def test_skill_status_invalid_when_schema_errors() -> None:
    status, reason = skill.skill_status({"name": "Bad Name", "description": "x"})
    assert status == "invalid"
    assert reason


def test_skill_status_active_when_no_requirements() -> None:
    status, reason = skill.skill_status(
        {"name": "ok", "description": "fine", "category": "personal"},
        env={}, cfg_raw={},
    )
    assert status == "active"
    assert reason == ""


def test_skill_status_inactive_drops_var_noise() -> None:
    status, reason = skill.skill_status(
        {"name": "ok", "description": "fine", "category": "personal",
         "requires_env": "['NOPE']"},
        env={}, cfg_raw={},
    )
    assert status == "inactive"
    assert reason == "missing env NOPE"


def test_eligibility_and_requires_use_profile_path_for_binaries(tmp_path: Path) -> None:
    bindir = tmp_path / "bin"
    bindir.mkdir()
    exe = bindir / "only-profile-bin"
    exe.write_text("#!/bin/sh\n")
    exe.chmod(0o755)
    env = {"PATH": str(bindir)}  # binary lives only on the profile PATH, not the process PATH
    meta = {"name": "coros", "description": "d", "category": "personal", "requires_bins": "['only-profile-bin']"}
    status, reason = skill.skill_status(meta, env=env, cfg_raw={})
    assert status == "active", reason

    md = tmp_path / "skills" / "personal" / "coros" / "SKILL.md"
    md.parent.mkdir(parents=True)
    md.write_text("---\nname: coros\ncategory: personal\nrequires_bins: ['only-profile-bin']\n---\n\nbody")
    detail = skill.skill_detail_payload(md, category="personal", name="coros", env=env, cfg_raw={})
    resolved = {r["name"]: r["resolved"] for r in detail["requires"]}
    assert resolved["only-profile-bin"] is True


def test_skill_file_read_rejects_traversal_and_secrets(tmp_path: Path) -> None:
    d = tmp_path / "skills" / "personal" / "x"
    (d / "scripts").mkdir(parents=True)
    (d / "SKILL.md").write_text("---\nname: x\n---\n")
    with pytest.raises(ValueError):
        skill.skill_file_read(d, "../../../etc/passwd")
    with pytest.raises(PermissionError):
        skill.skill_file_read(d, "secrets/token")


def test_skill_file_read_rejects_symlink_into_secrets(tmp_path: Path) -> None:
    d = tmp_path / "skills" / "personal" / "x"
    (d / "scripts").mkdir(parents=True)
    (d / "secrets").mkdir()
    (d / "secrets" / "token.txt").write_text("TOP-SECRET")
    (d / "SKILL.md").write_text("---\nname: x\n---\n")
    link = d / "scripts" / "public.txt"
    try:
        link.symlink_to(d / "secrets" / "token.txt")
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable on this platform")
    with pytest.raises(PermissionError):
        skill.skill_file_read(d, "scripts/public.txt")
    tree = {n["name"]: n for n in skill.skill_tree(d)}
    assert tree["scripts"]["children"] == []


def test_skill_detail_payload_rejects_symlinked_skill_md(tmp_path: Path) -> None:
    d = tmp_path / "skills" / "personal" / "x"
    d.mkdir(parents=True)
    secret = tmp_path / "secret.txt"
    secret.write_text("TOP-SECRET")
    md = d / "SKILL.md"
    try:
        md.symlink_to(secret)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable on this platform")
    with pytest.raises(PermissionError):
        skill.skill_detail_payload(md, category="personal", name="x", env={}, cfg_raw={})


def test_skill_detail_payload_rejects_symlinked_skill_dir(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    (real / "SKILL.md").write_text("---\nname: x\n---\n\nBODY")
    linkdir = tmp_path / "skills" / "personal" / "x"
    linkdir.parent.mkdir(parents=True)
    try:
        linkdir.symlink_to(real)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable on this platform")
    with pytest.raises(PermissionError):
        skill.skill_detail_payload(linkdir / "SKILL.md", category="personal", name="x", env={}, cfg_raw={})


def test_skill_tree_skips_symlinked_subdir(tmp_path: Path) -> None:
    d = tmp_path / "skills" / "personal" / "y"
    (d / "references").mkdir(parents=True)
    (d / "references" / "real.md").write_text("# real")
    (d / "SKILL.md").write_text("---\nname: y\n---\n")
    try:
        (d / "scripts").symlink_to(d / "references")
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable on this platform")
    names = {n["name"] for n in skill.skill_tree(d)}
    assert "scripts" not in names
    assert "references" in names
