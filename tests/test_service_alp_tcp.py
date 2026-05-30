"""ALP TCP bind resolution for containers — ``service._resolve_alp_tcp``."""

from __future__ import annotations

import pytest

from alpi import service


def test_config_used_when_no_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ALPI_ALP_TCP_HOST", raising=False)
    monkeypatch.delenv("ALPI_ALP_TCP_PORT", raising=False)
    host, port = service._resolve_alp_tcp(
        {"tcp_host": "100.1.2.3", "tcp_port": 7423}, managed=False,
    )
    assert (host, port) == ("100.1.2.3", 7423)


def test_env_overrides_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPI_ALP_TCP_HOST", "100.9.9.9")
    monkeypatch.setenv("ALPI_ALP_TCP_PORT", "7424")
    host, port = service._resolve_alp_tcp(
        {"tcp_host": "100.1.2.3", "tcp_port": 7423}, managed=True,
    )
    assert (host, port) == ("100.9.9.9", 7424)


def test_managed_binds_all_interfaces_when_port_set_without_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ALPI_ALP_TCP_HOST", raising=False)
    monkeypatch.setenv("ALPI_ALP_TCP_PORT", "7423")
    host, port = service._resolve_alp_tcp({}, managed=True)
    assert (host, port) == ("0.0.0.0", 7423)


def test_unmanaged_leaves_host_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ALPI_ALP_TCP_HOST", raising=False)
    monkeypatch.setenv("ALPI_ALP_TCP_PORT", "7423")
    host, port = service._resolve_alp_tcp({}, managed=False)
    assert host is None and port == 7423


def test_garbage_env_port_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ALPI_ALP_TCP_HOST", raising=False)
    monkeypatch.setenv("ALPI_ALP_TCP_PORT", "nope")
    host, port = service._resolve_alp_tcp({"tcp_port": 7423}, managed=True)
    assert port == 7423
