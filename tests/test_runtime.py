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
