"""Phase-2 sandbox: macOS sandbox-exec / Linux bubblewrap wrappers."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from alf.tools import _sandbox


@pytest.fixture
def ws(tmp_path: Path) -> Path:
    d = tmp_path / "workspace"
    d.mkdir()
    return d


@pytest.fixture
def ah(tmp_path: Path) -> Path:
    d = tmp_path / "alf_home"
    d.mkdir()
    return d


def test_unsupported_platform_raises(ws: Path, ah: Path) -> None:
    with patch.object(_sandbox, "sys") as sysmod:
        sysmod.platform = "win32"
        with pytest.raises(_sandbox.SandboxUnavailable) as ei:
            _sandbox.wrap_command("ls", workspace=ws, alf_home=ah, allow_network=False)
        assert "win32" in str(ei.value)


def test_macos_missing_binary_raises(ws: Path, ah: Path) -> None:
    with patch.object(_sandbox, "sys") as sysmod, \
         patch.object(_sandbox.shutil, "which", return_value=None):
        sysmod.platform = "darwin"
        with pytest.raises(_sandbox.SandboxUnavailable) as ei:
            _sandbox.wrap_command("ls", workspace=ws, alf_home=ah, allow_network=False)
        assert "sandbox-exec" in str(ei.value)


def test_linux_missing_binary_raises(ws: Path, ah: Path) -> None:
    with patch.object(_sandbox, "sys") as sysmod, \
         patch.object(_sandbox.shutil, "which", return_value=None):
        sysmod.platform = "linux"
        with pytest.raises(_sandbox.SandboxUnavailable) as ei:
            _sandbox.wrap_command("ls", workspace=ws, alf_home=ah, allow_network=False)
        assert "bwrap" in str(ei.value)


@pytest.mark.skipif(sys.platform != "darwin" or shutil.which("sandbox-exec") is None,
                    reason="macOS-only, requires sandbox-exec")
def test_macos_builds_sandbox_exec_command(ws: Path, ah: Path) -> None:
    args = _sandbox.wrap_command("echo ok", workspace=ws, alf_home=ah, allow_network=False)
    assert args[0] == "sandbox-exec"
    assert "-p" in args
    assert args[-3:] == ["/bin/sh", "-c", "echo ok"]
    profile = args[args.index("-p") + 1]
    assert "(deny default)" in profile
    assert "(deny network*)" in profile


@pytest.mark.skipif(sys.platform != "darwin" or shutil.which("sandbox-exec") is None,
                    reason="macOS-only, requires sandbox-exec")
def test_macos_allow_network_flips_profile(ws: Path, ah: Path) -> None:
    args = _sandbox.wrap_command("echo ok", workspace=ws, alf_home=ah, allow_network=True)
    profile = args[args.index("-p") + 1]
    assert "(allow network*)" in profile


@pytest.mark.skipif(sys.platform != "darwin" or shutil.which("sandbox-exec") is None,
                    reason="macOS-only, requires sandbox-exec")
def test_macos_workspace_write_allowed_escape_blocked(ws: Path, ah: Path, tmp_path: Path) -> None:
    import subprocess

    args = _sandbox.wrap_command(
        f"echo inside > {ws}/ok.txt && cat {ws}/ok.txt",
        workspace=ws, alf_home=ah, allow_network=False,
    )
    proc = subprocess.run(args, capture_output=True, text=True, timeout=10)
    assert proc.returncode == 0, proc.stderr
    assert "inside" in proc.stdout

    escape = Path("/etc/alf_sandbox_escape_probe")
    args = _sandbox.wrap_command(
        f"echo pwn > {escape}",
        workspace=ws, alf_home=ah, allow_network=False,
    )
    proc = subprocess.run(args, capture_output=True, text=True, timeout=10)
    assert proc.returncode != 0
    assert not escape.exists()


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
        workspace=ws, alf_home=ah, allow_network=False,
    )
    proc = subprocess.run(args, capture_output=True, text=True, timeout=10)
    assert proc.returncode != 0


@pytest.mark.skipif(sys.platform != "darwin" or shutil.which("sandbox-exec") is None,
                    reason="macOS-only, requires sandbox-exec")
def test_macos_network_blocked_by_default(ws: Path, ah: Path) -> None:
    import subprocess

    args = _sandbox.wrap_command(
        "curl --max-time 3 -s https://example.com",
        workspace=ws, alf_home=ah, allow_network=False,
    )
    proc = subprocess.run(args, capture_output=True, text=True, timeout=10)
    assert proc.returncode != 0


@pytest.mark.skipif(not sys.platform.startswith("linux") or shutil.which("bwrap") is None,
                    reason="Linux-only, requires bwrap")
def test_linux_builds_bwrap_command(ws: Path, ah: Path) -> None:
    args = _sandbox.wrap_command("echo ok", workspace=ws, alf_home=ah, allow_network=False)
    assert args[0] == "bwrap"
    assert "--unshare-net" in args
    assert str(ws) in args
    assert str(ah) in args


@pytest.mark.skipif(not sys.platform.startswith("linux") or shutil.which("bwrap") is None,
                    reason="Linux-only, requires bwrap")
def test_linux_allow_network_drops_unshare_net(ws: Path, ah: Path) -> None:
    args = _sandbox.wrap_command("echo ok", workspace=ws, alf_home=ah, allow_network=True)
    assert "--unshare-net" not in args


@pytest.mark.skipif(not sys.platform.startswith("linux") or shutil.which("bwrap") is None,
                    reason="Linux-only, requires bwrap")
def test_linux_workspace_write_allowed_escape_blocked(ws: Path, ah: Path) -> None:
    import subprocess

    args = _sandbox.wrap_command(
        f"echo inside > {ws}/ok.txt && cat {ws}/ok.txt",
        workspace=ws, alf_home=ah, allow_network=False,
    )
    proc = subprocess.run(args, capture_output=True, text=True, timeout=10)
    assert proc.returncode == 0, proc.stderr

    escape = Path("/etc/alf_sandbox_escape_probe")
    args = _sandbox.wrap_command(
        f"echo pwn > {escape}",
        workspace=ws, alf_home=ah, allow_network=False,
    )
    proc = subprocess.run(args, capture_output=True, text=True, timeout=10)
    assert proc.returncode != 0
    assert not escape.exists()
