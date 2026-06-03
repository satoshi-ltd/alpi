"""ALP TCP bind resolution — ``service._resolve_alp_tcp``. ALP TCP is always-on
(default port 7423) when a local-safe bind resolves from the shared
``network.host``. The bind is separate from the advertised address: a hostname
or public IP isn't bound directly. No bindable address → Unix-only."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from alpi import service


def _cfg(network=None, alp=None, host=None):
    return SimpleNamespace(network=network or {}, alp=alp or {}, host=host or {})


def test_configured_private_ip_binds_itself(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ALPI_NETWORK_HOST", raising=False)
    monkeypatch.delenv("ALPI_ALP_TCP_PORT", raising=False)
    host, port = service._resolve_alp_tcp(_cfg({"host": "192.168.1.5"}), managed=False)
    assert (host, port) == ("192.168.1.5", service.DEFAULT_ALP_TCP_PORT)


def test_configured_tailscale_ip_binds_itself(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ALPI_NETWORK_HOST", raising=False)
    monkeypatch.delenv("ALPI_ALP_TCP_PORT", raising=False)
    host, port = service._resolve_alp_tcp(_cfg({"host": "100.64.0.9"}), managed=False)
    assert (host, port) == ("100.64.0.9", service.DEFAULT_ALP_TCP_PORT)


def test_configured_port_overrides_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ALPI_NETWORK_HOST", raising=False)
    monkeypatch.delenv("ALPI_ALP_TCP_PORT", raising=False)
    host, port = service._resolve_alp_tcp(
        _cfg({"host": "192.168.1.5"}, {"tcp_port": 9000}), managed=False,
    )
    assert (host, port) == ("192.168.1.5", 9000)


def test_hostname_binds_all_interfaces(monkeypatch: pytest.MonkeyPatch) -> None:
    """A reachable hostname is advertised, but bound as 0.0.0.0 — it isn't a
    local interface address."""
    monkeypatch.delenv("ALPI_NETWORK_HOST", raising=False)
    monkeypatch.delenv("ALPI_ALP_TCP_PORT", raising=False)
    host, port = service._resolve_alp_tcp(_cfg({"host": "home.internal"}), managed=False)
    assert (host, port) == ("0.0.0.0", service.DEFAULT_ALP_TCP_PORT)


def test_public_ip_refused_without_optin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ALPI_NETWORK_HOST", raising=False)
    monkeypatch.delenv("ALPI_ALP_TCP_PORT", raising=False)
    host, port = service._resolve_alp_tcp(_cfg({"host": "203.0.113.5"}), managed=False)
    assert host is None and port is None


def test_public_ip_binds_all_with_optin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ALPI_NETWORK_HOST", raising=False)
    monkeypatch.delenv("ALPI_ALP_TCP_PORT", raising=False)
    host, port = service._resolve_alp_tcp(
        _cfg({"host": "203.0.113.5"}, host={"allow_public_bind": True}), managed=False,
    )
    assert (host, port) == ("0.0.0.0", service.DEFAULT_ALP_TCP_PORT)


def test_env_host_overrides_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPI_NETWORK_HOST", "100.64.9.9")
    monkeypatch.setenv("ALPI_ALP_TCP_PORT", "7424")
    host, port = service._resolve_alp_tcp(
        _cfg({"host": "192.168.1.5"}, {"tcp_port": 7423}), managed=False,
    )
    assert (host, port) == ("100.64.9.9", 7424)


def test_docker_binds_all_interfaces(monkeypatch: pytest.MonkeyPatch) -> None:
    """In docker the bind is always 0.0.0.0 (runtime maps the published port),
    independent of the advertised network.host."""
    monkeypatch.delenv("ALPI_NETWORK_HOST", raising=False)
    monkeypatch.delenv("ALPI_ALP_TCP_PORT", raising=False)
    host, port = service._resolve_alp_tcp(_cfg({"host": "203.0.113.5"}), managed=True)
    assert (host, port) == ("0.0.0.0", service.DEFAULT_ALP_TCP_PORT)


def test_bare_metal_without_host_uses_autodetect(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ALPI_NETWORK_HOST", raising=False)
    monkeypatch.delenv("ALPI_ALP_TCP_PORT", raising=False)
    with patch("alpi.host.network.detect_bind_ip", return_value=("100.64.0.9", "tailscale")):
        host, port = service._resolve_alp_tcp(_cfg(), managed=False)
    assert (host, port) == ("100.64.0.9", service.DEFAULT_ALP_TCP_PORT)


def test_no_reachable_address_means_unix_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ALPI_NETWORK_HOST", raising=False)
    monkeypatch.delenv("ALPI_ALP_TCP_PORT", raising=False)
    with patch("alpi.host.network.detect_bind_ip", return_value=None):
        host, port = service._resolve_alp_tcp(_cfg(), managed=False)
    assert host is None and port is None


def test_garbage_env_port_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ALPI_NETWORK_HOST", raising=False)
    monkeypatch.setenv("ALPI_ALP_TCP_PORT", "nope")
    host, port = service._resolve_alp_tcp(
        _cfg({"host": "192.168.1.5"}, {"tcp_port": 7423}), managed=True,
    )
    assert port == 7423
