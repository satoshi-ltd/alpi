"""Bind-ip detection — Tailscale first, LAN fallback."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from alpi import config as cfg_mod
from alpi.host import network


def test_returns_none_when_neither_tailscale_nor_lan() -> None:
    with patch("alpi.host.network.detect_tailscale_ip", return_value=None), \
         patch("alpi.host.network._detect_lan_ip", return_value=None):
        assert network.detect_bind_ip() is None


def test_prefers_tailscale_when_present() -> None:
    with patch("alpi.host.network.detect_tailscale_ip", return_value="100.86.43.12"), \
         patch("alpi.host.network._detect_lan_ip", return_value="192.168.1.10"):
        ip, scope = network.detect_bind_ip()
        assert ip == "100.86.43.12"
        assert scope == "tailscale"


def test_falls_back_to_lan() -> None:
    with patch("alpi.host.network.detect_tailscale_ip", return_value=None), \
         patch("alpi.host.network._detect_lan_ip", return_value="192.168.1.10"):
        ip, scope = network.detect_bind_ip()
        assert ip == "192.168.1.10"
        assert scope == "lan"


def test_detect_bind_ip_is_cached_per_process() -> None:
    network.detect_bind_ip.cache_clear()
    calls = {"n": 0}

    def fake_ts() -> str:
        calls["n"] += 1
        return "100.64.0.9"

    with patch("alpi.host.network.detect_tailscale_ip", side_effect=fake_ts):
        first = network.detect_bind_ip()
        second = network.detect_bind_ip()
    assert first == ("100.64.0.9", "tailscale")
    assert second == ("100.64.0.9", "tailscale")
    assert calls["n"] == 1  # the (blocking) probe is reused across calls, not re-run on every one


def test_resolve_bind_host_docker_is_all_interfaces() -> None:
    assert network.resolve_bind_host("home.example.com", is_docker=True, allow_public=False) == "0.0.0.0"


def test_resolve_bind_host_auto_uses_detected_ip() -> None:
    with patch("alpi.host.network.detect_bind_ip", return_value=("100.64.0.9", "tailscale")):
        assert network.resolve_bind_host(None, is_docker=False, allow_public=False) == "100.64.0.9"


def test_resolve_bind_host_auto_none_when_undetectable() -> None:
    with patch("alpi.host.network.detect_bind_ip", return_value=None):
        assert network.resolve_bind_host(None, is_docker=False, allow_public=False) is None


def test_resolve_bind_host_private_ip_binds_itself() -> None:
    assert network.resolve_bind_host("192.168.1.5", is_docker=False, allow_public=False) == "192.168.1.5"
    assert network.resolve_bind_host("100.64.0.9", is_docker=False, allow_public=False) == "100.64.0.9"


def test_resolve_bind_host_hostname_binds_all_interfaces() -> None:
    # Advertised as the hostname, but a name is not a local interface → 0.0.0.0.
    assert network.resolve_bind_host("nas.tailnet.ts.net", is_docker=False, allow_public=False) == "0.0.0.0"


def test_resolve_bind_host_public_ip_gated() -> None:
    assert network.resolve_bind_host("8.8.8.8", is_docker=False, allow_public=False) is None
    assert network.resolve_bind_host("8.8.8.8", is_docker=False, allow_public=True) == "0.0.0.0"


def test_resolve_bind_host_loopback_is_none() -> None:
    assert network.resolve_bind_host("127.0.0.1", is_docker=False, allow_public=True) is None


def test_resolve_host_tcp_bind_hostname_binds_all_interfaces(tmp_path: Path) -> None:
    home = tmp_path / "h"
    home.mkdir()
    cfg = cfg_mod.Config(home=home, model="")
    cfg.network = {"host": "home-server.internal"}
    cfg_mod.save(cfg)
    assert network.resolve_host_tcp_bind(home) == ("0.0.0.0", 49200)


def test_resolve_host_tcp_bind_public_ip_refused_without_optin(tmp_path: Path) -> None:
    home = tmp_path / "h"
    home.mkdir()
    cfg = cfg_mod.Config(home=home, model="")
    cfg.network = {"host": "8.8.8.8"}
    cfg_mod.save(cfg)
    assert network.resolve_host_tcp_bind(home) is None


def test_resolve_host_tcp_bind_public_ip_with_optin(tmp_path: Path) -> None:
    home = tmp_path / "h"
    home.mkdir()
    cfg = cfg_mod.Config(home=home, model="")
    cfg.network = {"host": "8.8.8.8"}
    cfg.host = {"allow_public_bind": True}
    cfg_mod.save(cfg)
    assert network.resolve_host_tcp_bind(home) == ("0.0.0.0", 49200)


def test_resolve_host_endpoint_prefers_configured_host(tmp_path: Path) -> None:
    home = tmp_path / "h"
    home.mkdir()
    cfg = cfg_mod.Config(home=home, model="")
    cfg.network = {"host": "100.123.17.103"}
    cfg_mod.save(cfg)

    with patch("alpi.host.network.detect_bind_ip", return_value=("192.168.1.10", "lan")):
        endpoint = network.resolve_host_endpoint(home)

    assert endpoint == ("100.123.17.103", "configured")


def test_network_host_env_is_the_container_address(monkeypatch) -> None:
    # ALPI_NETWORK_HOST is the single container address knob — the host plane's
    # docker advertise hint reads it (ALP reads it in service._resolve_alp_tcp).
    monkeypatch.setenv("ALPI_NETWORK_HOST", "100.64.7.7")
    assert network._advertise_host_hint() == "100.64.7.7"


def test_resolve_host_tcp_bind_binds_all_interfaces_in_docker(
    tmp_path: Path, monkeypatch,
) -> None:
    home = tmp_path / "h"
    home.mkdir()
    cfg_mod.save(cfg_mod.Config(home=home, model=""))
    monkeypatch.setenv("ALPI_PLATFORM", "docker")

    assert network.resolve_host_tcp_bind(home) == ("0.0.0.0", 49200)


def test_resolve_host_endpoint_uses_advertise_env_in_docker(
    tmp_path: Path, monkeypatch,
) -> None:
    home = tmp_path / "h"
    home.mkdir()
    cfg_mod.save(cfg_mod.Config(home=home, model=""))
    monkeypatch.setenv("ALPI_PLATFORM", "docker")
    monkeypatch.setenv("ALPI_NETWORK_HOST", "100.86.43.12")

    assert network.resolve_host_endpoint(home) == ("100.86.43.12", "docker")


def test_resolve_host_endpoint_none_in_docker_without_advertise(
    tmp_path: Path, monkeypatch,
) -> None:
    home = tmp_path / "h"
    home.mkdir()
    cfg_mod.save(cfg_mod.Config(home=home, model=""))
    monkeypatch.setenv("ALPI_PLATFORM", "docker")
    monkeypatch.delenv("ALPI_NETWORK_HOST", raising=False)
    monkeypatch.delenv("DEVICE_DOMAIN_NAME", raising=False)
    monkeypatch.delenv("DEVICE_HOSTNAME", raising=False)

    assert network.resolve_host_endpoint(home) is None


def test_resolve_host_tcp_port_env_override(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "h"
    home.mkdir()
    cfg_mod.save(cfg_mod.Config(home=home, model=""))
    monkeypatch.setenv("ALPI_HOST_TCP_PORT", "49201")

    assert network.resolve_host_tcp_port(home) == 49201
    monkeypatch.setenv("ALPI_PLATFORM", "docker")
    assert network.resolve_host_tcp_bind(home) == ("0.0.0.0", 49201)


def test_resolve_host_tcp_port_ignores_garbage_env(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "h"
    home.mkdir()
    cfg_mod.save(cfg_mod.Config(home=home, model=""))
    monkeypatch.setenv("ALPI_HOST_TCP_PORT", "not-a-port")

    assert network.resolve_host_tcp_port(home) == 49200


def test_resolve_host_pairing_name_prefers_configured_value(
    tmp_path: Path, monkeypatch,
) -> None:
    home = tmp_path / "h"
    home.mkdir()
    cfg = cfg_mod.Config(home=home, model="")
    cfg.host = {"device_name": "Umbrel"}
    cfg_mod.save(cfg)
    monkeypatch.setenv("DEVICE_HOSTNAME", "ignored-host")
    monkeypatch.setattr("alpi.host.network.socket.gethostname", lambda: "cded386e8d10")

    assert network.resolve_host_pairing_name(home) == "Umbrel"


def test_resolve_host_pairing_name_falls_back_to_device_hostname(
    tmp_path: Path, monkeypatch,
) -> None:
    home = tmp_path / "h"
    home.mkdir()
    cfg_mod.save(cfg_mod.Config(home=home, model=""))
    monkeypatch.setenv("DEVICE_HOSTNAME", "Umbrel Home")

    assert network.resolve_host_pairing_name(home) == "Umbrel Home"


def test_resolve_host_pairing_name_falls_back_to_system_hostname(
    tmp_path: Path, monkeypatch,
) -> None:
    home = tmp_path / "h"
    home.mkdir()
    cfg_mod.save(cfg_mod.Config(home=home, model=""))
    monkeypatch.delenv("DEVICE_HOSTNAME", raising=False)
    monkeypatch.setattr("alpi.host.network.socket.gethostname", lambda: "MacBook-Pro-M4.local")

    assert network.resolve_host_pairing_name(home) == "MacBook-Pro-M4.local"


def test_lan_parser_extracts_private_address() -> None:
    fake_out = type("O", (), {
        "returncode": 0,
        "stdout": (
            "lo0: flags=8049<UP,LOOPBACK> mtu 16384\n"
            "\tinet 127.0.0.1 netmask 0xff000000\n"
            "en0: flags=8863<UP,BROADCAST> mtu 1500\n"
            "\tinet 192.168.1.42 netmask 0xffffff00 broadcast 192.168.1.255\n"
        ),
    })()
    with patch("alpi.host.network.shutil.which", return_value="/sbin/ifconfig"), \
         patch("alpi.host.network.subprocess.run", return_value=fake_out):
        assert network._detect_lan_ip_via_ifconfig() == "192.168.1.42"


def test_lan_parser_skips_loopback() -> None:
    fake_out = type("O", (), {
        "returncode": 0,
        "stdout": (
            "lo0: flags=8049<UP,LOOPBACK> mtu 16384\n"
            "\tinet 127.0.0.1 netmask 0xff000000\n"
        ),
    })()
    with patch("alpi.host.network.shutil.which", return_value="/sbin/ifconfig"), \
         patch("alpi.host.network.subprocess.run", return_value=fake_out):
        assert network._detect_lan_ip_via_ifconfig() is None


def test_lan_parser_skips_public_address() -> None:
    fake_out = type("O", (), {
        "returncode": 0,
        "stdout": (
            "en0: flags=8863<UP,BROADCAST> mtu 1500\n"
            "\tinet 8.8.8.8 netmask 0xff000000\n"
        ),
    })()
    with patch("alpi.host.network.shutil.which", return_value="/sbin/ifconfig"), \
         patch("alpi.host.network.subprocess.run", return_value=fake_out):
        assert network._detect_lan_ip_via_ifconfig() is None


def test_lan_parser_recognises_10_8() -> None:
    fake_out = type("O", (), {
        "returncode": 0,
        "stdout": "tun0: \n\tinet 10.8.0.5 --> 10.8.0.5\n",
    })()
    with patch("alpi.host.network.shutil.which", return_value="/sbin/ifconfig"), \
         patch("alpi.host.network.subprocess.run", return_value=fake_out):
        assert network._detect_lan_ip_via_ifconfig() == "10.8.0.5"


def test_lan_parser_recognises_172_16_12() -> None:
    fake_out = type("O", (), {
        "returncode": 0,
        "stdout": "br0: \n\tinet 172.20.5.5 netmask 0xfff00000\n",
    })()
    with patch("alpi.host.network.shutil.which", return_value="/sbin/ifconfig"), \
         patch("alpi.host.network.subprocess.run", return_value=fake_out):
        assert network._detect_lan_ip_via_ifconfig() == "172.20.5.5"
