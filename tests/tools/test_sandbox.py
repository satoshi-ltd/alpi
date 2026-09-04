"""Phase-2 sandbox: macOS sandbox-exec / Linux bubblewrap wrappers."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from alpi.tools import _sandbox


@pytest.fixture
def ws(tmp_path: Path) -> Path:
    d = tmp_path / "workspace"
    d.mkdir()
    return d


@pytest.fixture
def ah(tmp_path: Path) -> Path:
    d = tmp_path / "alpi_home"
    d.mkdir()
    return d


def test_unsupported_platform_raises(ws: Path, ah: Path) -> None:
    with patch.object(_sandbox, "sys") as sysmod:
        sysmod.platform = "win32"
        with pytest.raises(_sandbox.SandboxUnavailable) as ei:
            _sandbox.wrap_command("ls", workspace=ws, alpi_home=ah, allow_network=False)
        assert "win32" in str(ei.value)


def test_macos_missing_binary_raises(ws: Path, ah: Path) -> None:
    with patch.object(_sandbox, "sys") as sysmod, \
         patch.object(_sandbox.shutil, "which", return_value=None):
        sysmod.platform = "darwin"
        with pytest.raises(_sandbox.SandboxUnavailable) as ei:
            _sandbox.wrap_command("ls", workspace=ws, alpi_home=ah, allow_network=False)
        assert "sandbox-exec" in str(ei.value)


def test_linux_missing_binary_raises(ws: Path, ah: Path) -> None:
    with patch.object(_sandbox, "sys") as sysmod, \
         patch.object(_sandbox.shutil, "which", return_value=None):
        sysmod.platform = "linux"
        with pytest.raises(_sandbox.SandboxUnavailable) as ei:
            _sandbox.wrap_command("ls", workspace=ws, alpi_home=ah, allow_network=False)
        assert "bwrap" in str(ei.value)


def test_phase_write_rules_translate_only_exact_sandbox_shapes(ws: Path) -> None:
    project = ws / "projects" / "hotel"
    assets = project / "assets"
    config = project / "src" / "config" / "site.json"
    assets.mkdir(parents=True)
    config.parent.mkdir(parents=True)
    config.write_text("{}\n")

    rules = _sandbox.phase_write_rules(ws, json.dumps({
        "root": "projects/hotel",
        "paths": ["assets/**", "src/config/site.json"],
    }))

    assert rules == (("subpath", assets), ("literal", config))


def test_phase_write_rules_fail_closed_on_ambiguous_glob(ws: Path) -> None:
    project = ws / "projects" / "hotel"
    project.mkdir(parents=True)

    with pytest.raises(_sandbox.SandboxUnavailable, match="cannot be sandboxed exactly"):
        _sandbox.phase_write_rules(ws, json.dumps({
            "root": "projects/hotel", "paths": ["assets/*.webp"],
        }))


def test_phase_write_rules_rejects_missing_file_and_bare_directory(ws: Path) -> None:
    project = ws / "projects" / "hotel"
    (project / "assets").mkdir(parents=True)

    for path in ("work/status.yaml", "assets", ""):
        with pytest.raises(_sandbox.SandboxUnavailable, match="terminal refused"):
            _sandbox.phase_write_rules(ws, json.dumps({
                "root": "projects/hotel", "paths": [path],
            }))


def test_phase_write_rules_create_a_declared_output_directory_that_does_not_exist_yet(ws: Path) -> None:
    project = ws / "projects" / "hotel"
    project.mkdir(parents=True)

    rules = _sandbox.phase_write_rules(ws, json.dumps({
        "root": "projects/hotel", "paths": ["dist/**", ".astro/**"],
    }))

    assert rules == (("subpath", project / "dist"), ("subpath", project / ".astro"))
    assert (project / "dist").is_dir() and (project / ".astro").is_dir()


def test_phase_write_rules_empty_scope_allows_no_persistent_writes(ws: Path) -> None:
    assert _sandbox.phase_write_rules(ws, '{"root":"","paths":[]}') == ()


def test_macos_scoped_profile_drops_alpi_home_write(ws: Path, ah: Path) -> None:
    allowed = ws / "assets"
    allowed.mkdir()
    with patch.object(_sandbox, "sys") as sysmod, \
         patch.object(_sandbox.shutil, "which", return_value="/usr/bin/sandbox-exec"):
        sysmod.platform = "darwin"
        args = _sandbox.wrap_command(
            "echo ok", workspace=ws, alpi_home=ah, allow_network=False,
            write_rules=(("subpath", allowed),),
        )

    profile = args[args.index("-p") + 1]
    assert '(subpath (param "WRITE_0"))' in profile
    assert "ALPI_HOME" not in profile
    assert f"WRITE_0={allowed}" in args


@pytest.mark.skipif(sys.platform != "darwin" or shutil.which("sandbox-exec") is None,
                    reason="macOS-only, requires sandbox-exec")
def test_macos_builds_sandbox_exec_command(ws: Path, ah: Path) -> None:
    args = _sandbox.wrap_command("echo ok", workspace=ws, alpi_home=ah, allow_network=False)
    assert args[0] == "sandbox-exec"
    assert "-p" in args
    assert args[-3:] == ["/bin/sh", "-c", "echo ok"]
    profile = args[args.index("-p") + 1]
    assert "(deny default)" in profile
    assert "(deny network*)" in profile
    # Secrets under ALPI_HOME are denied both read and write inside the sandbox.
    assert "(deny file-read-data" in profile
    assert "(deny file-write*" in profile
    assert r"/\.alpi/(profiles/[^/]+/)?\.env$" in profile


@pytest.mark.skipif(sys.platform != "darwin" or shutil.which("sandbox-exec") is None,
                    reason="macOS-only, requires sandbox-exec")
def test_macos_allow_network_flips_profile(ws: Path, ah: Path) -> None:
    args = _sandbox.wrap_command("echo ok", workspace=ws, alpi_home=ah, allow_network=True)
    profile = args[args.index("-p") + 1]
    assert "(allow network*)" in profile


@pytest.mark.integration
@pytest.mark.skipif(sys.platform != "darwin" or shutil.which("sandbox-exec") is None,
                    reason="macOS-only, requires sandbox-exec")
def test_macos_workspace_write_allowed_escape_blocked(ws: Path, ah: Path, tmp_path: Path) -> None:
    import subprocess

    args = _sandbox.wrap_command(
        f"echo inside > {ws}/ok.txt && cat {ws}/ok.txt",
        workspace=ws, alpi_home=ah, allow_network=False,
    )
    proc = subprocess.run(args, capture_output=True, text=True, timeout=10)
    assert proc.returncode == 0, proc.stderr
    assert "inside" in proc.stdout

    escape = Path("/etc/alpi_sandbox_escape_probe")
    args = _sandbox.wrap_command(
        f"echo pwn > {escape}",
        workspace=ws, alpi_home=ah, allow_network=False,
    )
    proc = subprocess.run(args, capture_output=True, text=True, timeout=10)
    assert proc.returncode != 0
    assert not escape.exists()


@pytest.mark.integration
@pytest.mark.skipif(sys.platform != "darwin" or shutil.which("sandbox-exec") is None,
                    reason="macOS-only, requires sandbox-exec")
def test_macos_phase_scope_keeps_workspace_readable_and_other_paths_read_only(
    ws: Path, ah: Path,
) -> None:
    import subprocess

    allowed = ws / "project" / "assets"
    denied = ws / "project" / "src"
    allowed.mkdir(parents=True)
    denied.mkdir()
    (denied / "source.txt").write_text("readable\n")
    args = _sandbox.wrap_command(
        f"cat {denied}/source.txt && echo ok > {allowed}/ok.txt && echo no > {denied}/no.txt",
        workspace=ws, alpi_home=ah, allow_network=False,
        write_rules=(("subpath", allowed),),
    )

    proc = subprocess.run(args, capture_output=True, text=True, timeout=10)

    assert proc.returncode != 0
    assert "readable" in proc.stdout
    assert (allowed / "ok.txt").read_text() == "ok\n"
    assert not (denied / "no.txt").exists()


@pytest.mark.integration
@pytest.mark.skipif(sys.platform != "darwin" or shutil.which("sandbox-exec") is None,
                    reason="macOS-only, requires sandbox-exec")
def test_macos_ssh_read_blocked(ws: Path, ah: Path) -> None:
    import subprocess
    import os

    ssh = Path(os.path.expanduser("~/.ssh"))
    if not ssh.exists():
        pytest.skip("no ~/.ssh on this machine")
    args = _sandbox.wrap_command(
        f"ls {ssh}",
        workspace=ws, alpi_home=ah, allow_network=False,
    )
    proc = subprocess.run(args, capture_output=True, text=True, timeout=10)
    assert proc.returncode != 0


@pytest.mark.integration
@pytest.mark.skipif(sys.platform != "darwin" or shutil.which("sandbox-exec") is None,
                    reason="macOS-only, requires sandbox-exec")
def test_macos_dev_null_writable(ws: Path, ah: Path) -> None:
    """Regression: git and other tools reopen /dev/null for r+w; the
    sandbox must not block that. Prior profile only granted file-write*
    in workspace/home/tmp and the sandboxed open(2) failed with
    ``Operation not permitted``."""
    import subprocess

    args = _sandbox.wrap_command(
        "echo hi > /dev/null && cat /dev/null && printf 'ok'",
        workspace=ws, alpi_home=ah, allow_network=False,
    )
    proc = subprocess.run(args, capture_output=True, text=True, timeout=10)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == "ok"


@pytest.mark.integration
@pytest.mark.skipif(sys.platform != "darwin" or shutil.which("sandbox-exec") is None,
                    reason="macOS-only, requires sandbox-exec")
def test_macos_git_log_works(ws: Path, ah: Path) -> None:
    """End-to-end for the reported bug: ``git log`` failed under the
    sandbox because git opens /dev/null for r+w on some plumbing
    paths. Initialise a throwaway repo inside the workspace and assert
    ``git log`` completes cleanly."""
    import subprocess

    init = subprocess.run(
        _sandbox.wrap_command(
            f"cd {ws} && git init -q && "
            "git -c user.email=a@b -c user.name=a commit "
            "--allow-empty -m init -q && "
            "git log --oneline",
            workspace=ws, alpi_home=ah, allow_network=False,
        ),
        capture_output=True, text=True, timeout=15,
    )
    assert init.returncode == 0, init.stderr
    assert "init" in init.stdout


@pytest.mark.integration
@pytest.mark.skipif(sys.platform != "darwin" or shutil.which("sandbox-exec") is None,
                    reason="macOS-only, requires sandbox-exec")
def test_macos_network_blocked_by_default(ws: Path, ah: Path) -> None:
    import subprocess

    args = _sandbox.wrap_command(
        "curl --max-time 3 -s https://example.com",
        workspace=ws, alpi_home=ah, allow_network=False,
    )
    proc = subprocess.run(args, capture_output=True, text=True, timeout=10)
    assert proc.returncode != 0


@pytest.mark.integration
@pytest.mark.skipif(not sys.platform.startswith("linux") or shutil.which("bwrap") is None,
                    reason="Linux-only, requires bwrap")
def test_linux_builds_bwrap_command(ws: Path, ah: Path) -> None:
    args = _sandbox.wrap_command("echo ok", workspace=ws, alpi_home=ah, allow_network=False)
    assert args[0] == "bwrap"
    assert "--unshare-net" in args
    assert str(ws) in args
    assert str(ah) in args


@pytest.mark.integration
@pytest.mark.skipif(not sys.platform.startswith("linux") or shutil.which("bwrap") is None,
                    reason="Linux-only, requires bwrap")
def test_linux_allow_network_drops_unshare_net(ws: Path, ah: Path) -> None:
    args = _sandbox.wrap_command("echo ok", workspace=ws, alpi_home=ah, allow_network=True)
    assert "--unshare-net" not in args


def test_linux_tmpfs_does_not_hide_tmp_backed_workspace() -> None:
    workspace = Path("/tmp/alpi-pytest/workspace")
    alpi_home = Path("/tmp/alpi-pytest/alpi_home")
    with patch.object(_sandbox, "sys") as sysmod, \
         patch.object(_sandbox.shutil, "which", return_value="/usr/bin/bwrap"):
        sysmod.platform = "linux"
        args = _sandbox.wrap_command(
            "echo ok", workspace=workspace, alpi_home=alpi_home, allow_network=False,
        )

    tmpfs = next(i for i in range(len(args) - 1) if args[i:i + 2] == ["--tmpfs", "/tmp"])
    workspace_dir = next(
        i for i in range(len(args) - 1) if args[i:i + 2] == ["--dir", str(workspace)]
    )
    workspace_bind = next(
        i for i in range(len(args) - 2)
        if args[i:i + 3] == ["--bind", str(workspace), str(workspace)]
    )

    assert tmpfs < workspace_dir < workspace_bind


def test_linux_root_is_read_only_after_writable_binds(ws: Path, ah: Path) -> None:
    with patch.object(_sandbox, "sys") as sysmod, \
         patch.object(_sandbox.shutil, "which", return_value="/usr/bin/bwrap"):
        sysmod.platform = "linux"
        args = _sandbox.wrap_command("echo ok", workspace=ws, alpi_home=ah, allow_network=False)

    workspace_bind = next(
        i for i in range(len(args) - 2) if args[i:i + 3] == ["--bind", str(ws), str(ws)]
    )
    alpi_home_bind = next(
        i for i in range(len(args) - 2) if args[i:i + 3] == ["--bind", str(ah), str(ah)]
    )
    remount_ro = next(
        i for i in range(len(args) - 1) if args[i:i + 2] == ["--remount-ro", "/"]
    )
    chdir = args.index("--chdir")

    assert workspace_bind < remount_ro < chdir
    assert alpi_home_bind < remount_ro < chdir


def test_linux_scoped_mounts_keep_workspace_and_home_read_only(
    ws: Path, ah: Path,
) -> None:
    allowed = ws / "assets"
    allowed.mkdir()
    with patch.object(_sandbox, "sys") as sysmod, \
         patch.object(_sandbox.shutil, "which", return_value="/usr/bin/bwrap"):
        sysmod.platform = "linux"
        args = _sandbox.wrap_command(
            "echo ok", workspace=ws, alpi_home=ah, allow_network=False,
            write_rules=(("subpath", allowed),),
        )

    workspace_ro = next(
        index for index in range(len(args) - 2)
        if args[index:index + 3] == ["--ro-bind", str(ws), str(ws)]
    )
    home_ro = next(
        index for index in range(len(args) - 2)
        if args[index:index + 3] == ["--ro-bind", str(ah), str(ah)]
    )
    allowed_bind = next(
        index for index in range(len(args) - 2)
        if args[index:index + 3] == ["--bind", str(allowed), str(allowed)]
    )
    assert allowed_bind > max(workspace_ro, home_ro)


@pytest.mark.integration
@pytest.mark.skipif(not sys.platform.startswith("linux") or shutil.which("bwrap") is None,
                    reason="Linux-only, requires bwrap")
def test_linux_workspace_write_allowed_escape_blocked(ws: Path, ah: Path) -> None:
    import subprocess

    args = _sandbox.wrap_command(
        f"echo inside > {ws}/ok.txt && cat {ws}/ok.txt",
        workspace=ws, alpi_home=ah, allow_network=False,
    )
    proc = subprocess.run(args, capture_output=True, text=True, timeout=10)
    assert proc.returncode == 0, proc.stderr

    escape = Path("/etc/alpi_sandbox_escape_probe")
    args = _sandbox.wrap_command(
        f"echo pwn > {escape}",
        workspace=ws, alpi_home=ah, allow_network=False,
    )
    proc = subprocess.run(args, capture_output=True, text=True, timeout=10)
    assert proc.returncode != 0
    assert not escape.exists()
