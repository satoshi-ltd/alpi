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


def test_resolve_host_endpoint_prefers_configured_host(tmp_path: Path) -> None:
    home = tmp_path / "h"
    home.mkdir()
    cfg = cfg_mod.Config(home=home, model="")
    cfg.host = {"tcp_host": "100.123.17.103"}
    cfg_mod.save(cfg)

    with patch("alpi.host.network.detect_bind_ip", return_value=("192.168.1.10", "lan")):
        endpoint = network.resolve_host_endpoint(home)

    assert endpoint == ("100.123.17.103", "configured")


def test_resolve_host_endpoint_uses_umbrel_domain_hint(
    tmp_path: Path, monkeypatch,
) -> None:
    home = tmp_path / "h"
    home.mkdir()
    cfg_mod.save(cfg_mod.Config(home=home, model=""))
    monkeypatch.setenv("ALPI_PLATFORM", "umbrel")
    monkeypatch.setenv("DEVICE_DOMAIN_NAME", "umbrel.local")

    assert network.resolve_host_endpoint(home) == ("umbrel.local", "umbrel")


def test_resolve_host_tcp_bind_uses_unspecified_inside_umbrel(
    tmp_path: Path, monkeypatch,
) -> None:
    home = tmp_path / "h"
    home.mkdir()
    cfg_mod.save(cfg_mod.Config(home=home, model=""))
    monkeypatch.setenv("ALPI_PLATFORM", "umbrel")

    assert network.resolve_host_tcp_bind(home) == ("0.0.0.0", 49200)


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
        assert network._detect_lan_ip() == "192.168.1.42"


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
        assert network._detect_lan_ip() is None


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
        assert network._detect_lan_ip() is None


def test_lan_parser_recognises_10_8() -> None:
    fake_out = type("O", (), {
        "returncode": 0,
        "stdout": "tun0: \n\tinet 10.8.0.5 --> 10.8.0.5\n",
    })()
    with patch("alpi.host.network.shutil.which", return_value="/sbin/ifconfig"), \
         patch("alpi.host.network.subprocess.run", return_value=fake_out):
        assert network._detect_lan_ip() == "10.8.0.5"


def test_lan_parser_recognises_172_16_12() -> None:
    fake_out = type("O", (), {
        "returncode": 0,
        "stdout": "br0: \n\tinet 172.20.5.5 netmask 0xfff00000\n",
    })()
    with patch("alpi.host.network.shutil.which", return_value="/sbin/ifconfig"), \
         patch("alpi.host.network.subprocess.run", return_value=fake_out):
        assert network._detect_lan_ip() == "172.20.5.5"
