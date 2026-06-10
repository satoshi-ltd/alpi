from __future__ import annotations

import pytest

from alpi.tools._paths import resolve_path


@pytest.mark.parametrize("path", [
    "/Users/javi/.alpi/.env",
    "/Users/javi/.alpi/config.yaml",
    "/Users/javi/.alpi/profiles/mirai/.env",
    "/Users/javi/.alpi/profiles/work/config.yaml",
    "/home/foo/.alpi/.env",
    "/home/foo/.alpi/profiles/laptop/.env",
])
def test_alpi_profile_secrets_are_refused(path: str) -> None:
    with pytest.raises(ValueError, match="sensitive"):
        resolve_path(path)


@pytest.mark.parametrize("path", [
    "/Users/javi/.ssh/authorized_keys",
    "/Users/javi/.netrc",
    "/Users/javi/.npmrc",
    "/Users/javi/.aws/config",
    "/Users/javi/.config/gh/hosts.yml",
    "/Users/javi/.zshrc",
    "/Users/javi/.bashrc",
    "/Users/javi/Library/LaunchAgents/com.evil.plist",
    "/Users/javi/.alpi/skills/system/persist/secrets/key.txt",
])
def test_persistence_and_credential_files_are_refused(path: str) -> None:
    with pytest.raises(ValueError, match="sensitive"):
        resolve_path(path)


@pytest.mark.parametrize("path", [
    "/Users/javi/projects/myapp/.env",
    "/Users/javi/work/server/config.yaml",
    "/tmp/.env",
    "/Users/javi/.alpi/sessions/abc.json",
    "/Users/javi/.alpi/profiles/mirai/sessions/x.json",
    "/Users/javi/.alpi/logs/agent.log",
])
def test_workspace_paths_with_same_basename_pass(path: str, tmp_path) -> None:
    """A user's project may legitimately have a `.env` or `config.yaml`
    in the workspace; only the alpi-profile copies are off-limits."""
    try:
        resolve_path(path)
    except ValueError as e:
        assert "sensitive" not in str(e), f"unexpectedly blocked {path!r}: {e}"
