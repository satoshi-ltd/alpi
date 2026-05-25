"""Host TCP listener (WebSocket) — only binds to a Tailscale CGNAT
address, never to loopback / LAN / 0.0.0.0. Mobile / desktop clients
reach ``host.*`` over the user's tailnet, not over the local network."""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import websockets

from alpi.host import server as host_server
from alpi.host import tailscale as ts


@pytest.fixture
def short_tmp() -> Path:
    d = Path(tempfile.mkdtemp(prefix="alp-host-tcp-", dir="/tmp"))
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_is_tailscale_ip_accepts_cgnat_range() -> None:
    assert ts.is_tailscale_ip("100.64.0.1")
    assert ts.is_tailscale_ip("100.86.43.12")
    assert ts.is_tailscale_ip("100.127.255.254")


def test_is_tailscale_ip_rejects_other_addresses() -> None:
    assert not ts.is_tailscale_ip("127.0.0.1")
    assert not ts.is_tailscale_ip("0.0.0.0")
    assert not ts.is_tailscale_ip("192.168.1.1")
    assert not ts.is_tailscale_ip("10.0.0.5")
    assert not ts.is_tailscale_ip("8.8.8.8")
    # 100.0.0.0/8 outside the 100.64.0.0/10 CGNAT range
    assert not ts.is_tailscale_ip("100.63.255.255")
    assert not ts.is_tailscale_ip("100.128.0.0")
    assert not ts.is_tailscale_ip("not-an-ip")
    assert not ts.is_tailscale_ip("")


def test_detect_tailscale_ip_returns_none_when_binary_missing() -> None:
    empty = type("O", (), {"returncode": 0, "stdout": ""})()
    with patch("alpi.host.tailscale.shutil.which", return_value=None), \
         patch("alpi.host.tailscale.os.access", return_value=False), \
         patch("alpi.host.tailscale.subprocess.run", return_value=empty):
        assert ts.detect_tailscale_ip() is None


def test_detect_tailscale_ip_parses_cli_output() -> None:
    class FakeOut:
        returncode = 0
        stdout = "100.86.43.12\nfd7a:115c:a1e0::1\n"

    with patch("alpi.host.tailscale.shutil.which", return_value="/usr/bin/tailscale"), \
         patch("alpi.host.tailscale.subprocess.run", return_value=FakeOut()):
        assert ts.detect_tailscale_ip() == "100.86.43.12"


def test_detect_tailscale_ip_falls_back_to_app_bundle() -> None:
    """macOS App Store / DMG installs leave $PATH untouched; the .app
    bundle binary must still be picked up."""
    class FakeOut:
        returncode = 0
        stdout = "100.114.140.25\n"

    captured: dict[str, list[str]] = {}

    def fake_run(cmd, **_kwargs):
        captured["cmd"] = cmd
        return FakeOut()

    def fake_access(path: str, _mode: int) -> bool:
        return path == "/Applications/Tailscale.app/Contents/MacOS/Tailscale"

    with patch("alpi.host.tailscale.shutil.which", return_value=None), \
         patch("alpi.host.tailscale.os.access", side_effect=fake_access), \
         patch("alpi.host.tailscale.subprocess.run", side_effect=fake_run):
        assert ts.detect_tailscale_ip() == "100.114.140.25"
    assert captured["cmd"][0] == "/Applications/Tailscale.app/Contents/MacOS/Tailscale"


def test_detect_tailscale_ip_returns_none_when_cli_fails() -> None:
    class FakeOut:
        returncode = 1
        stdout = ""

    with patch("alpi.host.tailscale.shutil.which", return_value="/usr/bin/tailscale"), \
         patch("alpi.host.tailscale.subprocess.run", return_value=FakeOut()):
        assert ts.detect_tailscale_ip() is None


def test_detect_tailscale_ip_falls_back_to_ifconfig_when_cli_unusable() -> None:
    """Under launchd on macOS the App Store Tailscale binary refuses to
    dispatch subcommands without a GUI/keychain context — exit 0, empty
    stdout. Parsing ``ifconfig`` keeps detection working."""
    cli_out = type("O", (), {"returncode": 0, "stdout": ""})()
    ifconfig_out = type("O", (), {
        "returncode": 0,
        "stdout": (
            "lo0: flags=8049<UP,LOOPBACK> mtu 16384\n"
            "\tinet 127.0.0.1 netmask 0xff000000\n"
            "utun4: flags=8051<UP,POINTOPOINT,RUNNING> mtu 1280\n"
            "\tinet 100.114.140.25 --> 100.114.140.25 netmask 0xffffffff\n"
        ),
    })()

    def fake_run(cmd, **_kwargs):
        if cmd[0].endswith("ifconfig"):
            return ifconfig_out
        return cli_out

    def fake_which(name: str) -> str | None:
        return {"tailscale": "/usr/bin/tailscale", "ifconfig": "/sbin/ifconfig"}.get(name)

    with patch("alpi.host.tailscale.shutil.which", side_effect=fake_which), \
         patch("alpi.host.tailscale.subprocess.run", side_effect=fake_run):
        assert ts.detect_tailscale_ip() == "100.114.140.25"


@pytest.mark.parametrize("addr", ["0.0.0.0", "127.0.0.1", "::", ""])
def test_server_refuses_unsafe_bind(tmp_path: Path, addr: str) -> None:
    """Loopback, 0.0.0.0, IPv6 unspecified, empty — all rejected."""
    home = tmp_path / "h"
    home.mkdir()
    with pytest.raises(ValueError, match="Tailscale|private LAN"):
        host_server.Server(home=home, tcp_bind=(addr, 49200))


def test_server_allows_unspecified_bind_on_umbrel(
    tmp_path: Path, monkeypatch,
) -> None:
    monkeypatch.setenv("ALPI_PLATFORM", "umbrel")
    home = tmp_path / "h"
    home.mkdir()
    srv = host_server.Server(home=home, tcp_bind=("0.0.0.0", 49200))
    assert srv._tcp_bind == ("0.0.0.0", 49200)


@pytest.mark.parametrize(
    "addr",
    ["100.64.0.1", "100.114.140.25", "192.168.1.10", "10.0.0.5", "172.16.5.5"],
)
def test_server_accepts_tailscale_or_lan_bind(tmp_path: Path, addr: str) -> None:
    """Tailscale CGNAT and private RFC1918 ranges are allowed."""
    home = tmp_path / "h"
    home.mkdir()
    srv = host_server.Server(home=home, tcp_bind=(addr, 49200))
    assert srv._tcp_bind == (addr, 49200)


def test_server_refuses_invalid_port(tmp_path: Path) -> None:
    home = tmp_path / "h"
    home.mkdir()
    with pytest.raises(ValueError, match="port"):
        host_server.Server(home=home, tcp_bind=("100.64.0.1", 0))
    with pytest.raises(ValueError, match="port"):
        host_server.Server(home=home, tcp_bind=("100.64.0.1", 70000))


def test_server_without_tcp_bind_only_serves_unix_socket(tmp_path: Path) -> None:
    home = tmp_path / "h"
    home.mkdir()
    srv = host_server.Server(home=home)
    assert srv._tcp_bind is None


@pytest.mark.asyncio
async def test_server_accepts_calls_over_websocket_when_bound(
    short_tmp: Path, monkeypatch,
) -> None:
    """End-to-end: bind to 127.0.0.1 (after monkeypatching the validator
    to allow it) and confirm the same dispatcher answers JSON-RPC over
    WebSocket. The validator is the real safety boundary; this test
    exercises only the WS plumbing."""
    home = short_tmp / "h"
    home.mkdir()
    # Devices store reads from home_mod._ROOT — pin it inside short_tmp
    # so we don't pick up any real ~/.alpi/host/devices.yaml.
    from alpi import home as home_mod
    monkeypatch.setattr(home_mod, "_ROOT", short_tmp)

    from alpi.host import devices as devices_mod
    row = devices_mod.add(label="test", role="member")

    with patch.object(
        host_server.Server, "_validate_tcp_bind",
        staticmethod(lambda b: b),
    ):
        srv = host_server.Server(home=home, tcp_bind=("127.0.0.1", 0))

        async def handler(_params, _server):
            return {"pong": True}

        srv.register("host.ping", handler)
        await srv.start()
        try:
            assert srv._ws_server is not None
            sockets = srv._ws_server.sockets
            assert sockets
            port = sockets[0].getsockname()[1]
            async with websockets.connect(f"ws://127.0.0.1:{port}") as ws:
                await ws.send(json.dumps({
                    "id": "1", "method": "host.ping",
                    "params": {"auth_token": row["token"]},
                }))
                response = json.loads(await ws.recv())
            assert response["result"] == {"pong": True}
        finally:
            await srv.stop()


@pytest.mark.asyncio
async def test_server_accepts_multiple_calls_on_one_websocket(
    short_tmp: Path, monkeypatch,
) -> None:
    home = short_tmp / "h"
    home.mkdir()
    from alpi import home as home_mod
    monkeypatch.setattr(home_mod, "_ROOT", short_tmp)

    from alpi.host import devices as devices_mod
    row = devices_mod.add(label="test", role="member")

    with patch.object(
        host_server.Server, "_validate_tcp_bind",
        staticmethod(lambda b: b),
    ):
        srv = host_server.Server(home=home, tcp_bind=("127.0.0.1", 0))

        async def handler(params, _server):
            return {"pong": params["n"]}

        srv.register("host.ping", handler)
        await srv.start()
        try:
            assert srv._ws_server is not None
            port = srv._ws_server.sockets[0].getsockname()[1]
            async with websockets.connect(f"ws://127.0.0.1:{port}") as ws:
                await ws.send(json.dumps({
                    "id": "1", "method": "host.ping",
                    "params": {"auth_token": row["token"], "n": 1},
                }))
                first = json.loads(await ws.recv())
                await ws.send(json.dumps({
                    "id": "2", "method": "host.ping",
                    "params": {"auth_token": row["token"], "n": 2},
                }))
                second = json.loads(await ws.recv())
            assert first["result"] == {"pong": 1}
            assert second["result"] == {"pong": 2}
        finally:
            await srv.stop()


@pytest.mark.asyncio
async def test_ws_rejects_request_without_token_once_paired(
    short_tmp: Path, monkeypatch,
) -> None:
    """Once a device exists, missing/invalid tokens must hit auth-failed."""
    home = short_tmp / "h"
    home.mkdir()
    from alpi import home as home_mod
    monkeypatch.setattr(home_mod, "_ROOT", short_tmp)
    from alpi.host import devices
    devices.add(label="ipad")  # store no longer empty → enforcement on

    with patch.object(host_server.Server, "_validate_tcp_bind",
                      staticmethod(lambda b: b)):
        srv = host_server.Server(home=home, tcp_bind=("127.0.0.1", 0))

        async def handler(_p, _s):
            return {"pong": True}

        srv.register("host.ping", handler)
        await srv.start()
        try:
            port = srv._ws_server.sockets[0].getsockname()[1]
            async with websockets.connect(f"ws://127.0.0.1:{port}") as ws:
                await ws.send(json.dumps({
                    "id": "1", "method": "host.ping", "params": {},
                }))
                response = json.loads(await ws.recv())
            assert response["error"]["code"] == -32000
            assert response["error"]["message"] == "auth-failed"
        finally:
            await srv.stop()


@pytest.mark.asyncio
async def test_ws_accepts_request_with_valid_token(
    short_tmp: Path, monkeypatch,
) -> None:
    home = short_tmp / "h"
    home.mkdir()
    from alpi import home as home_mod
    monkeypatch.setattr(home_mod, "_ROOT", short_tmp)
    from alpi.host import devices
    row = devices.add(label="iphone")

    with patch.object(host_server.Server, "_validate_tcp_bind",
                      staticmethod(lambda b: b)):
        srv = host_server.Server(home=home, tcp_bind=("127.0.0.1", 0))

        async def handler(_p, _s):
            return {"pong": True}

        srv.register("host.ping", handler)
        await srv.start()
        try:
            port = srv._ws_server.sockets[0].getsockname()[1]
            async with websockets.connect(f"ws://127.0.0.1:{port}") as ws:
                await ws.send(json.dumps({
                    "id": "1",
                    "method": "host.ping",
                    "params": {"auth_token": row["token"]},
                }))
                response = json.loads(await ws.recv())
            assert response["result"] == {"pong": True}
        finally:
            await srv.stop()
