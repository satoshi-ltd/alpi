"""Bind-ip detection — Tailscale first, LAN fallback."""

from __future__ import annotations

from unittest.mock import patch

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
