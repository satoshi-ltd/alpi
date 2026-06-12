from __future__ import annotations

import pytest

from alpi.tools._paths import resolve_path


@pytest.mark.parametrize("path", [
    "/Users/user/.alpi/.env",
    "/Users/user/.alpi/config.yaml",
    "/Users/user/.alpi/profiles/mirai/.env",
    "/Users/user/.alpi/profiles/work/config.yaml",
    "/home/foo/.alpi/.env",
    "/home/foo/.alpi/profiles/laptop/.env",
])
def test_alpi_profile_secrets_are_refused(path: str) -> None:
    with pytest.raises(ValueError, match="sensitive"):
        resolve_path(path)


@pytest.mark.parametrize("path", [
    "/Users/user/.ssh/authorized_keys",
    "/Users/user/.netrc",
    "/Users/user/.npmrc",
    "/Users/user/.aws/config",
    "/Users/user/.config/gh/hosts.yml",
    "/Users/user/.zshrc",
    "/Users/user/.bashrc",
    "/Users/user/Library/LaunchAgents/com.evil.plist",
    "/Users/user/.alpi/skills/system/persist/secrets/key.txt",
])
def test_persistence_and_credential_files_are_refused(path: str) -> None:
    with pytest.raises(ValueError, match="sensitive"):
        resolve_path(path)


@pytest.mark.parametrize("path", [
    "/Users/user/projects/myapp/.env",
    "/Users/user/projects/myapp/.env.local",
    "/Users/user/projects/myapp/.env.production",
    "/Users/user/projects/myapp/.env.production.local",
    "/Users/user/projects/myapp/.envrc",
    "/Users/user/projects/myapp/.envrc.local",
    "/Users/user/projects/myapp/.envrc.example",
    "/tmp/.env",
])
def test_project_env_files_are_refused(path: str) -> None:
    with pytest.raises(ValueError, match="sensitive"):
        resolve_path(path)


@pytest.mark.parametrize("path", [
    "/Users/user/projects/myapp/.env.example",
    "/Users/user/projects/myapp/.env.sample",
    "/Users/user/projects/myapp/.env.template",
    "/Users/user/projects/myapp/.env.dist",
    "/Users/user/work/server/config.yaml",
    "/Users/user/.alpi/sessions/abc.json",
    "/Users/user/.alpi/profiles/mirai/sessions/x.json",
    "/Users/user/.alpi/logs/agent.log",
])
def test_readable_paths_pass(path: str) -> None:
    try:
        resolve_path(path)
    except ValueError as e:
        assert "sensitive" not in str(e), f"unexpectedly blocked {path!r}: {e}"
