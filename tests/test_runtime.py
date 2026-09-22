"""Deployment-platform helpers — ``alpi.runtime``."""

from __future__ import annotations

import pytest

from alpi import runtime


def test_unset_is_not_docker(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ALPI_PLATFORM", raising=False)
    assert runtime.platform_id() == ""
    assert runtime.is_docker() is False


def test_docker(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPI_PLATFORM", "docker")
    assert runtime.is_docker() is True
    assert runtime.platform_id() == "docker"


def test_normalises_case_and_whitespace(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPI_PLATFORM", "  Docker ")
    assert runtime.platform_id() == "docker"
    assert runtime.is_docker() is True


def test_gateway_platform_is_not_docker(monkeypatch: pytest.MonkeyPatch) -> None:
    """A gateway id (telegram/email/etc) is a platform value but not the
    container runtime."""
    monkeypatch.setenv("ALPI_PLATFORM", "telegram")
    assert runtime.is_docker() is False


def test_a_scheduled_turn_does_not_erase_the_deployment_runtime(monkeypatch) -> None:
    # The scheduler overwrites ALPI_PLATFORM with "cron"; the runtime rides alongside it.
    monkeypatch.setenv("ALPI_PLATFORM", "cron")
    monkeypatch.setenv("ALPI_DEPLOY_RUNTIME", "docker")

    assert runtime.platform_id() == "docker"
    assert runtime.is_docker() is True


def test_a_scheduled_turn_on_a_host_install_is_still_not_docker(monkeypatch) -> None:
    monkeypatch.setenv("ALPI_PLATFORM", "cron")
    monkeypatch.delenv("ALPI_DEPLOY_RUNTIME", raising=False)

    assert runtime.is_docker() is False


def test_deploy_env_carries_a_runtime_and_never_a_turn_origin(monkeypatch) -> None:
    monkeypatch.setenv("ALPI_PLATFORM", "docker")
    monkeypatch.delenv("ALPI_DEPLOY_RUNTIME", raising=False)
    assert runtime.deploy_env() == {"ALPI_DEPLOY_RUNTIME": "docker"}

    monkeypatch.setenv("ALPI_PLATFORM", "cron")
    assert runtime.deploy_env() == {}, "a turn origin is not a runtime to carry"

    monkeypatch.delenv("ALPI_PLATFORM", raising=False)
    assert runtime.deploy_env() == {}
