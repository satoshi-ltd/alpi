"""Host TCP listener (WebSocket) bind policy. Auto-detect prefers
Tailscale then private LAN; the operator may override with a private
hostname / VPN name, and a public IP only with an explicit opt-in.
Loopback / unspecified are always refused."""

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


@pytest.mark.parametrize("addr", ["127.0.0.1", "::", ""])
def test_server_refuses_unsafe_bind(tmp_path: Path, addr: str) -> None:
    """Loopback, IPv6 unspecified, empty — all rejected."""
    home = tmp_path / "h"
    home.mkdir()
    with pytest.raises(ValueError, match="private network"):
        host_server.Server(home=home, tcp_bind=(addr, 49200))


def test_server_accepts_unspecified_bind(tmp_path: Path) -> None:
    """0.0.0.0 is resolve_bind_host's safe default (docker, hostname/custom):
    all interfaces, accepted everywhere — not docker-gated."""
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


@pytest.mark.parametrize("addr", ["home-server.internal", "nas.tailnet.ts.net", "my-vpn-box"])
def test_server_accepts_custom_hostname_bind(tmp_path: Path, addr: str) -> None:
    """A private hostname / VPN / MagicDNS name is the operator's explicit choice."""
    home = tmp_path / "h"
    home.mkdir()
    srv = host_server.Server(home=home, tcp_bind=(addr, 49200))
    assert srv._tcp_bind == (addr, 49200)


def test_server_refuses_public_ip_without_optin(tmp_path: Path) -> None:
    home = tmp_path / "h"
    home.mkdir()
    with pytest.raises(ValueError, match="public IP|allow_public_bind"):
        host_server.Server(home=home, tcp_bind=("203.0.113.5", 49200))


def test_server_accepts_public_ip_with_optin(tmp_path: Path) -> None:
    home = tmp_path / "h"
    home.mkdir()
    srv = host_server.Server(
        home=home, tcp_bind=("203.0.113.5", 49200), allow_public_bind=True,
    )
    assert srv._tcp_bind == ("203.0.113.5", 49200)


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
async def test_start_binds_unix_socket_without_tcp(short_tmp: Path) -> None:
    # host.sock comes up on start() with no TCP/network resolution — the slow Tailscale detect is deferred to enable_tcp().
    home = short_tmp / "h"
    home.mkdir()
    srv = host_server.Server(home=home, tcp_bind=None)
    await srv.start()
    try:
        assert srv.socket_path().exists()
        assert srv._ws_server is None
    finally:
        await srv.stop()
    assert not srv.socket_path().exists()


@pytest.mark.asyncio
async def test_enable_tcp_refuses_public_bind_without_optin(short_tmp: Path) -> None:
    home = short_tmp / "h"
    home.mkdir()
    srv = host_server.Server(home=home, tcp_bind=None)
    await srv.start()
    try:
        with pytest.raises(ValueError):
            await srv.enable_tcp(("8.8.8.8", 49200))
        assert srv._ws_server is None
    finally:
        await srv.stop()


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
        staticmethod(lambda b, allow_public_bind=False: b),
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
async def test_enable_tcp_after_start_serves_websocket(short_tmp: Path, monkeypatch) -> None:
    # start() unix-only, then enable_tcp() dynamically binds a working WS listener.
    home = short_tmp / "h"
    home.mkdir()
    from alpi import home as home_mod
    monkeypatch.setattr(home_mod, "_ROOT", short_tmp)
    from alpi.host import devices as devices_mod
    row = devices_mod.add(label="test", role="member")

    with patch.object(
        host_server.Server, "_validate_tcp_bind",
        staticmethod(lambda b, allow_public_bind=False: b),
    ):
        srv = host_server.Server(home=home, tcp_bind=None)

        async def handler(_params, _server):
            return {"pong": True}

        srv.register("host.ping", handler)
        await srv.start()
        try:
            assert srv._ws_server is None
            await srv.enable_tcp(("127.0.0.1", 0))
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
async def test_run_host_keeps_unix_when_tcp_bind_fails(short_tmp: Path, monkeypatch) -> None:
    import asyncio
    from alpi import service
    from alpi import home as home_mod

    monkeypatch.setattr(home_mod, "_ROOT", short_tmp)
    monkeypatch.setattr("alpi.host.network.resolve_host_tcp_bind", lambda h: ("100.64.0.1", 49200))

    async def _boom(self, host, port):  # the WS listener fails to bind...
        raise OSError("address already in use")
    monkeypatch.setattr(host_server.Server, "_start_ws", _boom)

    task = asyncio.create_task(service._run_host(short_tmp, "default"))
    sock = short_tmp / "host" / "host.sock"
    try:
        for _ in range(150):
            if sock.exists():
                break
            await asyncio.sleep(0.02)
        assert sock.exists()  # ...but host.sock stays up and serving
        reader, writer = await asyncio.open_unix_connection(str(sock))
        writer.write(b'{"id":"r","method":"host.version"}\n')
        await writer.drain()
        line = await asyncio.wait_for(reader.readline(), timeout=2.0)
        assert b'"result"' in line
        writer.close()
        await writer.wait_closed()
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    assert not sock.exists()  # stop() cleaned up on cancel


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
        staticmethod(lambda b, allow_public_bind=False: b),
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
                      staticmethod(lambda b, allow_public_bind=False: b)):
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
                      staticmethod(lambda b, allow_public_bind=False: b)):
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


@pytest.mark.asyncio
async def test_ws_accepts_attachment_sized_messages(
    short_tmp: Path, monkeypatch,
) -> None:
    # 5 MiB message > the websockets library's 1 MiB default max_size — must be answered, not closed with 1009.
    home = short_tmp / "h"
    home.mkdir()
    from alpi import home as home_mod
    monkeypatch.setattr(home_mod, "_ROOT", short_tmp)
    from alpi.host import devices
    row = devices.add(label="test", role="member")

    with patch.object(host_server.Server, "_validate_tcp_bind",
                      staticmethod(lambda b, allow_public_bind=False: b)):
        srv = host_server.Server(home=home, tcp_bind=("127.0.0.1", 0))

        async def handler(params, _s):
            return {"echo_len": len(params.get("blob") or "")}

        srv.register("host.ping", handler)
        await srv.start()
        try:
            port = srv._ws_server.sockets[0].getsockname()[1]
            blob = "A" * (5 * 1024 * 1024)
            async with websockets.connect(
                f"ws://127.0.0.1:{port}", max_size=None,
            ) as ws:
                await ws.send(json.dumps({
                    "id": "1",
                    "method": "host.ping",
                    "params": {"auth_token": row["token"], "blob": blob},
                }))
                response = json.loads(await ws.recv())
            assert response["result"] == {"echo_len": len(blob)}
        finally:
            await srv.stop()


@pytest.mark.asyncio
async def test_ws_stages_multi_mib_attachment_and_rejects_over_cap(
    short_tmp: Path, monkeypatch,
) -> None:
    import base64 as b64mod
    from alpi.host import attachments_rpc

    home = short_tmp / "h"
    home.mkdir()
    from alpi import home as home_mod
    monkeypatch.setattr(home_mod, "_ROOT", short_tmp)
    from alpi.host import devices
    row = devices.add(label="test", role="member")

    with patch.object(host_server.Server, "_validate_tcp_bind",
                      staticmethod(lambda b, allow_public_bind=False: b)):
        srv = host_server.Server(home=home, tcp_bind=("127.0.0.1", 0))
        attachments_rpc.register(srv)
        await srv.start()
        try:
            port = srv._ws_server.sockets[0].getsockname()[1]
            png = b"\x89PNG\r\n\x1a\n" + b"\x00" * (2 * 1024 * 1024)
            over_text = "x" * (3 * 1024 * 1024)
            async with websockets.connect(
                f"ws://127.0.0.1:{port}", max_size=None,
            ) as ws:
                await ws.send(json.dumps({
                    "id": "1", "method": "host.attachments.stage",
                    "params": {
                        "auth_token": row["token"], "profile": "default",
                        "name": "big.png", "mime": "image/png",
                        "data_base64": b64mod.b64encode(png).decode(),
                    },
                }))
                staged = json.loads(await ws.recv())
                assert staged["result"]["ok"] is True
                assert staged["result"]["attachment"]["size"] == len(png)

                await ws.send(json.dumps({
                    "id": "2", "method": "host.attachments.stage",
                    "params": {
                        "auth_token": row["token"], "profile": "default",
                        "name": "big.txt", "mime": "text/plain",
                        "data_base64": b64mod.b64encode(over_text.encode()).decode(),
                    },
                }))
                rejected = json.loads(await ws.recv())
                assert rejected["error"]["code"] == -32602
                assert "cap" in rejected["error"]["message"]

                await ws.send(json.dumps({
                    "id": "3", "method": "host.attachments.stage",
                    "params": {
                        "auth_token": row["token"], "profile": "default",
                        "name": "ok.png", "mime": "image/png",
                        "data_base64": b64mod.b64encode(b"\x89PNG\r\n\x1a\nok").decode(),
                    },
                }))
                after = json.loads(await ws.recv())
                assert after["result"]["ok"] is True
        finally:
            await srv.stop()


@pytest.mark.asyncio
async def test_unix_socket_accepts_large_messages(short_tmp: Path) -> None:
    # >64 KiB line exceeds asyncio's default StreamReader limit — must be answered, not dropped.
    import asyncio
    home = short_tmp / "h"
    home.mkdir()
    srv = host_server.Server(home=home)

    async def handler(params, _s):
        return {"echo_len": len(params.get("blob") or "")}

    srv.register("host.ping", handler)
    await srv.start()
    try:
        reader, writer = await asyncio.open_unix_connection(
            path=str(srv.socket_path()), limit=host_server._max_message_bytes(),
        )
        blob = "A" * (256 * 1024)
        writer.write((json.dumps({
            "id": "1", "method": "host.ping", "params": {"blob": blob},
        }) + "\n").encode())
        await writer.drain()
        response = json.loads(await reader.readline())
        writer.close()
        await writer.wait_closed()
        assert response["result"] == {"echo_len": len(blob)}
    finally:
        await srv.stop()


def test_max_message_bytes_covers_the_attachment_cap() -> None:
    from alpi.attachments import MAX_FILE_BYTES
    import base64
    encoded = len(base64.b64encode(b"x" * MAX_FILE_BYTES))
    assert host_server._max_message_bytes() > encoded


def test_websocket_limits_read_daemon_environment(short_tmp: Path, monkeypatch) -> None:
    monkeypatch.setenv("ALPI_HOST_WS_AUTH_TIMEOUT", "12.5")
    monkeypatch.setenv("ALPI_HOST_WS_AUTH_RECHECK", "2.5")
    monkeypatch.setenv("ALPI_HOST_WS_CLOSE_TIMEOUT", "0.5")
    monkeypatch.setenv("ALPI_HOST_WS_REVOCATION_RETRY", "7.5")
    monkeypatch.setenv("ALPI_HOST_WS_MAX_CONNECTIONS", "64")
    monkeypatch.setenv("ALPI_HOST_WS_MAX_CONNECTIONS_PER_DEVICE", "6")
    monkeypatch.setenv("ALPI_HOST_WS_MAX_RPCS_PER_DEVICE", "5")

    server = host_server.Server(home=short_tmp)
    status = server.websocket_status()

    assert status["auth_timeout_seconds"] == 12.5
    assert status["auth_recheck_seconds"] == 2.5
    assert status["close_timeout_seconds"] == 0.5
    assert status["revocation_retry_seconds"] == 7.5
    assert status["connection_limit"] == 64
    assert status["connections_per_device_limit"] == 6
    assert status["rpcs_per_device_limit"] == 5


async def _start_security_test_server(short_tmp: Path, monkeypatch):
    from alpi import home as home_mod

    home = short_tmp / "h"
    home.mkdir(exist_ok=True)
    monkeypatch.setattr(home_mod, "_ROOT", short_tmp)
    with patch.object(
        host_server.Server, "_validate_tcp_bind",
        staticmethod(lambda bind, allow_public_bind=False: bind),
    ):
        server = host_server.Server(home=home, tcp_bind=("127.0.0.1", 0))

    async def ping(params, _server):
        return {"pong": params.get("value", True)}

    server.register("host.ping", ping)
    await server.start()
    port = server._ws_server.sockets[0].getsockname()[1]
    return server, f"ws://127.0.0.1:{port}"


def _ws_request(token: str, request_id: str = "1", **params) -> str:
    return json.dumps({
        "id": request_id,
        "method": "host.ping",
        "params": {"auth_token": token, **params},
    })


@pytest.mark.asyncio
async def test_websocket_exchanges_pairing_before_authentication(
    short_tmp: Path, monkeypatch,
) -> None:
    from alpi.host import connections

    server, url = await _start_security_test_server(short_tmp, monkeypatch)
    connections.register(server)
    row, pairing = connections.create_pairing_connection("Phone")
    try:
        async with websockets.connect(url) as ws:
            await ws.send(json.dumps({
                "id": "pair",
                "method": "host.connections.exchange_pairing",
                "params": {
                    "pairing_token": pairing["token"],
                    "client": "desktop",
                    "name": "MacBook",
                    "app_version": "1.0",
                },
            }))
            result = json.loads(await ws.recv())["result"]
            assert result["connection_id"] == row["id"]
            assert result["device_id"]
            assert connections.authenticate(result["token"]).valid
            with pytest.raises(websockets.ConnectionClosedOK):
                await ws.recv()

        async with websockets.connect(url) as replay:
            await replay.send(json.dumps({
                "id": "replay",
                "method": "host.connections.exchange_pairing",
                "params": {"pairing_token": pairing["token"]},
            }))
            error = json.loads(await replay.recv())["error"]
            assert error["code"] == -32011
            assert error["message"] == "pairing-used"
        assert server.websocket_status()["pairing_exchange_attempts"] == 2
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_authenticated_socket_cannot_call_pairing_exchange(
    short_tmp: Path, monkeypatch,
) -> None:
    from alpi.host import connections

    server, url = await _start_security_test_server(short_tmp, monkeypatch)
    connections.register(server)
    _connection, device = connections.create_connection("Member")
    _pending_connection, pairing = connections.create_pairing_connection("Phone")
    try:
        async with websockets.connect(url) as ws:
            await ws.send(_ws_request(device["token"], "auth"))
            assert json.loads(await ws.recv())["result"]["pong"] is True
            await ws.send(json.dumps({
                "id": "pair",
                "method": "host.connections.exchange_pairing",
                "params": {
                    "auth_token": device["token"],
                    "pairing_token": pairing["token"],
                },
            }))
            error = json.loads(await ws.recv())["error"]
            assert error["code"] == -32001
            assert error["message"] == "forbidden"
        assert connections.pairing_status(
            _pending_connection["id"], pairing["id"],
        )["status"] == "pending"
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_preauth_pairing_hides_unexpected_exception_details(
    short_tmp: Path, monkeypatch,
) -> None:
    server, url = await _start_security_test_server(short_tmp, monkeypatch)

    async def crash(_params, _server):
        raise RuntimeError("sensitive filesystem detail")

    server.register("host.connections.exchange_pairing", crash)
    try:
        async with websockets.connect(url) as ws:
            await ws.send(json.dumps({
                "id": "pair",
                "method": "host.connections.exchange_pairing",
                "params": {"pairing_token": "invalid"},
            }))
            error = json.loads(await ws.recv())["error"]
            assert error == {"code": -32603, "message": "internal-error"}
        assert server.websocket_status()["pairing_exchange_attempts"] == 1
    finally:
        await server.stop()


@pytest.mark.parametrize("method,params", [
    ("host.connections.list", {}),
    ("host.connections.create", {"label": "Unauthorized"}),
    ("host.connections.pairing_status", {
        "connection_id": "conn_unknown", "pairing_id": "pair_unknown",
    }),
    ("host.connections.cancel_pairing", {
        "connection_id": "conn_unknown", "pairing_id": "pair_unknown",
    }),
])
@pytest.mark.asyncio
async def test_first_frame_allows_only_pairing_exchange_without_authentication(
    short_tmp: Path, monkeypatch, method: str, params: dict,
) -> None:
    from alpi.host import connections

    server, url = await _start_security_test_server(short_tmp, monkeypatch)
    connections.register(server)
    try:
        async with websockets.connect(url) as ws:
            await ws.send(json.dumps({"id": "unauth", "method": method, "params": params}))
            error = json.loads(await ws.recv())["error"]
            assert error == {"code": -32000, "message": "auth-failed"}
            with pytest.raises(websockets.ConnectionClosedError):
                await ws.recv()
            assert ws.close_code == 1008
        assert connections.list_connections() == []
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_websocket_requires_authentication_before_deadline(
    short_tmp: Path, monkeypatch,
) -> None:
    server, url = await _start_security_test_server(short_tmp, monkeypatch)
    server._ws_auth_timeout = 0.05
    try:
        async with websockets.connect(url) as ws:
            with pytest.raises(websockets.ConnectionClosedError):
                await ws.recv()
            assert ws.close_code == 1008
        assert server.websocket_status()["auth_timeouts"] == 1
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_websocket_closes_after_invalid_authentication(
    short_tmp: Path, monkeypatch,
) -> None:
    server, url = await _start_security_test_server(short_tmp, monkeypatch)
    try:
        async with websockets.connect(url) as ws:
            await ws.send(_ws_request("invalid-token"))
            response = json.loads(await ws.recv())
            assert response["error"]["message"] == "auth-failed"
            with pytest.raises(websockets.ConnectionClosedError):
                await ws.recv()
            assert ws.close_code == 1008
        assert server.websocket_status()["auth_failures"] == 1
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_plain_http_requests_do_not_block_websocket_handshakes(
    short_tmp: Path, monkeypatch,
) -> None:
    server, url = await _start_security_test_server(short_tmp, monkeypatch)

    class PlainRequest:
        class Headers:
            @staticmethod
            def get_all(_name):
                return []

        headers = Headers()

    try:
        for _ in range(260):
            assert server._process_ws_handshake(None, PlainRequest()) is None

        async with websockets.connect(url) as ws:
            assert server.websocket_status()["handshakes"] == 1
            await ws.close()
    finally:
        await server.stop()


def test_handshake_hook_handles_duplicate_and_malformed_upgrade_headers(short_tmp: Path) -> None:
    class Headers:
        def __init__(self, values=None, error: Exception | None = None):
            self.values = values or []
            self.error = error

        def get_all(self, _name):
            if self.error is not None:
                raise self.error
            return self.values

    class Connection:
        def respond(self, status, body):
            return status, body

    server = host_server.Server(home=short_tmp)
    duplicate = type("Request", (), {"headers": Headers(["websocket", "websocket"])})()
    malformed = type("Request", (), {"headers": Headers(error=ValueError("bad header"))})()

    assert server._process_ws_handshake(Connection(), duplicate) is None
    status, _body = server._process_ws_handshake(Connection(), malformed)
    assert status == 400
    assert server.websocket_status()["protocol_failures"] == 1


@pytest.mark.asyncio
async def test_websocket_limits_global_active_connections(
    short_tmp: Path, monkeypatch,
) -> None:
    server, url = await _start_security_test_server(short_tmp, monkeypatch)
    server._ws_max_connections = 1
    try:
        first = await websockets.connect(url)
        try:
            with pytest.raises(websockets.InvalidStatus) as rejected:
                await websockets.connect(url)
            assert rejected.value.response.status_code == 503
        finally:
            await first.close()
        assert server.websocket_status()["handshakes_rejected"] == 1
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_websocket_limits_connections_per_device(
    short_tmp: Path, monkeypatch,
) -> None:
    from alpi.host import connections

    server, url = await _start_security_test_server(short_tmp, monkeypatch)
    _connection, device = connections.create_connection("Phone")
    server._ws_max_connections_per_device = 1
    try:
        async with websockets.connect(url) as first:
            await first.send(_ws_request(device["token"]))
            assert "result" in json.loads(await first.recv())
            async with websockets.connect(url) as second:
                await second.send(_ws_request(device["token"], "2"))
                rejected = json.loads(await second.recv())
                assert rejected["error"]["message"] == "too-many-connections"
                with pytest.raises(websockets.ConnectionClosedError):
                    await second.recv()
            await first.send(_ws_request(device["token"], "3"))
            assert "result" in json.loads(await first.recv())
        assert server.websocket_status()["device_connections_rejected"] == 1
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_websocket_cannot_change_device_identity(
    short_tmp: Path, monkeypatch,
) -> None:
    from alpi.host import connections

    server, url = await _start_security_test_server(short_tmp, monkeypatch)
    connection, first_device = connections.create_connection("Team")
    _connection, second_device = connections.add_device(connection["id"])
    try:
        async with websockets.connect(url) as ws:
            await ws.send(_ws_request(first_device["token"], "first"))
            assert "result" in json.loads(await ws.recv())

            await ws.send(_ws_request(second_device["token"], "second"))
            rejected = json.loads(await ws.recv())
            assert rejected["error"]["data"]["reason"] == "socket-identity-changed"
            with pytest.raises(websockets.ConnectionClosedError):
                await ws.recv()
            assert ws.close_code == 1008
        assert server.websocket_status()["auth_failures"] == 1
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_rpc_limit_is_per_device_and_keeps_other_device_working(
    short_tmp: Path, monkeypatch,
) -> None:
    import asyncio
    from alpi.host import connections

    server, url = await _start_security_test_server(short_tmp, monkeypatch)
    connection, first_device = connections.create_connection("Team")
    _connection, second_device = connections.add_device(connection["id"])
    server._ws_max_rpcs_per_device = 1
    started = asyncio.Event()
    release = asyncio.Event()

    async def wait_stream(_params, _server, send):
        started.set()
        await release.wait()
        await send({"done": True})

    server.register_stream("host.wait", wait_stream)
    first_stream = await websockets.connect(url)
    same_device = await websockets.connect(url)
    other_device = await websockets.connect(url)
    try:
        await first_stream.send(json.dumps({
            "id": "stream", "method": "host.wait",
            "params": {"auth_token": first_device["token"]},
        }))
        await asyncio.wait_for(started.wait(), timeout=1)

        await same_device.send(_ws_request(first_device["token"], "same"))
        rejected = json.loads(await same_device.recv())
        assert rejected["error"]["message"] == "too-many-requests"

        await other_device.send(_ws_request(second_device["token"], "other"))
        assert json.loads(await other_device.recv())["result"]["pong"] is True
        assert server.websocket_status()["device_rpcs_rejected"] == 1

        release.set()
        assert json.loads(await first_stream.recv()) == {"id": "stream", "done": True}
        await asyncio.sleep(0)
        assert server._ws_rpc_counts == {}
    finally:
        release.set()
        await first_stream.close()
        await same_device.close()
        await other_device.close()
        await server.stop()


@pytest.mark.asyncio
async def test_revoking_one_device_closes_only_its_websockets(
    short_tmp: Path, monkeypatch,
) -> None:
    import asyncio
    from alpi.host import connections

    server, url = await _start_security_test_server(short_tmp, monkeypatch)
    connection, revoked_device = connections.create_connection("Team")
    _connection, remaining_device = connections.add_device(connection["id"])
    server._ws_auth_recheck = 0.05
    stream_started = asyncio.Event()
    stream_cancelled = asyncio.Event()

    async def wait_stream(_params, _server, _send):
        stream_started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            stream_cancelled.set()
            raise

    server.register_stream("host.wait", wait_stream)
    revoked_ws = await websockets.connect(url)
    remaining_ws = await websockets.connect(url)
    try:
        await revoked_ws.send(json.dumps({
            "id": "revoked", "method": "host.wait",
            "params": {"auth_token": revoked_device["token"]},
        }))
        await remaining_ws.send(_ws_request(remaining_device["token"], "remaining"))
        await asyncio.wait_for(stream_started.wait(), timeout=1)
        assert "result" in json.loads(await remaining_ws.recv())

        assert connections.revoke_device(connection["id"], revoked_device["id"])
        with pytest.raises(websockets.ConnectionClosedError):
            await asyncio.wait_for(revoked_ws.recv(), timeout=1)
        assert revoked_ws.close_code == 1008
        await asyncio.wait_for(stream_cancelled.wait(), timeout=1)

        await remaining_ws.send(_ws_request(remaining_device["token"], "still-active"))
        assert "result" in json.loads(await remaining_ws.recv())
        assert server.websocket_status()["revoked_connections"] == 1
    finally:
        await revoked_ws.close()
        await remaining_ws.close()
        await server.stop()


@pytest.mark.parametrize("mutation", ["disable", "delete"])
@pytest.mark.asyncio
async def test_disabling_or_deleting_connection_closes_all_its_websockets(
    short_tmp: Path, monkeypatch, mutation: str,
) -> None:
    import asyncio
    from alpi.host import connections

    server, url = await _start_security_test_server(short_tmp, monkeypatch)
    connection, first_device = connections.create_connection("Team")
    _connection, second_device = connections.add_device(connection["id"])
    server._ws_auth_recheck = 0.05
    first_ws = await websockets.connect(url)
    second_ws = await websockets.connect(url)
    try:
        await first_ws.send(_ws_request(first_device["token"], "first"))
        await second_ws.send(_ws_request(second_device["token"], "second"))
        assert "result" in json.loads(await first_ws.recv())
        assert "result" in json.loads(await second_ws.recv())

        if mutation == "disable":
            assert connections.update_connection(connection["id"], status="disabled")
        else:
            assert connections.delete_connection(connection["id"])

        for ws in (first_ws, second_ws):
            with pytest.raises(websockets.ConnectionClosedError):
                await asyncio.wait_for(ws.recv(), timeout=1)
            assert ws.close_code == 1008
        assert server.websocket_status()["revoked_connections"] == 2
    finally:
        await first_ws.close()
        await second_ws.close()
        await server.stop()


@pytest.mark.asyncio
async def test_authorization_store_failure_closes_authenticated_websockets(
    short_tmp: Path, monkeypatch,
) -> None:
    import asyncio
    from alpi.host import connections

    server, url = await _start_security_test_server(short_tmp, monkeypatch)
    _connection, device = connections.create_connection("Phone")
    server._ws_auth_recheck = 0.05

    def fail_authorization_check():
        raise RuntimeError("store unavailable")

    monkeypatch.setattr(host_server, "_active_authorizations", fail_authorization_check)
    try:
        async with websockets.connect(url) as ws:
            await ws.send(_ws_request(device["token"]))
            assert "result" in json.loads(await ws.recv())
            with pytest.raises(websockets.ConnectionClosedError):
                await asyncio.wait_for(ws.recv(), timeout=1)
            assert ws.close_code == 1008
        assert server.websocket_status()["revoked_connections"] == 1
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_authentication_reads_external_revocation_without_cached_window(
    short_tmp: Path, monkeypatch,
) -> None:
    import yaml
    from alpi.host import connections

    server, url = await _start_security_test_server(short_tmp, monkeypatch)
    server._ws_auth_recheck = 60
    _connection, device = connections.create_connection("Phone")
    assert connections.authenticate(device["token"]).valid

    path = connections.store_path()
    data = yaml.safe_load(path.read_text())
    data["connections"][0]["status"] = "disabled"
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    try:
        async with websockets.connect(url) as ws:
            await ws.send(_ws_request(device["token"]))
            rejected = json.loads(await ws.recv())
            assert rejected["error"]["data"]["reason"] == "connection-disabled"
            with pytest.raises(websockets.ConnectionClosedError):
                await ws.recv()
            assert ws.close_code == 1008
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_revocation_repeats_cancellation_until_stream_exits(
    short_tmp: Path, monkeypatch,
) -> None:
    import asyncio
    from alpi.host import connections

    server, url = await _start_security_test_server(short_tmp, monkeypatch)
    connection, device = connections.create_connection("Phone")
    server._ws_auth_recheck = 0.05
    server._ws_revocation_retry = 0.05
    started = asyncio.Event()
    cancelled_twice = asyncio.Event()
    cancellations = 0

    async def stubborn_stream(_params, _server, _send):
        nonlocal cancellations
        started.set()
        while True:
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancellations += 1
                if cancellations == 1:
                    continue
                cancelled_twice.set()
                raise

    server.register_stream("host.wait", stubborn_stream)
    ws = await websockets.connect(url)
    try:
        await ws.send(json.dumps({
            "id": "wait", "method": "host.wait",
            "params": {"auth_token": device["token"]},
        }))
        await asyncio.wait_for(started.wait(), timeout=1)
        assert connections.revoke_device(connection["id"], device["id"])
        await asyncio.wait_for(cancelled_twice.wait(), timeout=1)
        await asyncio.sleep(0)
        assert server._ws_by_device == {}
        assert server._ws_rpc_counts == {}
        assert server.websocket_status()["revoked_connections"] == 1
    finally:
        await ws.close()
        await server.stop()


@pytest.mark.asyncio
async def test_stop_cancels_live_websocket_streams(
    short_tmp: Path, monkeypatch,
) -> None:
    import asyncio
    from alpi.host import connections

    server, url = await _start_security_test_server(short_tmp, monkeypatch)
    _connection, device = connections.create_connection("Phone")
    started = 0
    all_started = asyncio.Event()
    cancelled = 0

    async def live_stream(_params, _server, _send):
        nonlocal started, cancelled
        started += 1
        if started == 8:
            all_started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled += 1
            raise

    server.register_stream("host.wait", live_stream)
    sockets = [await websockets.connect(url) for _ in range(8)]
    server_connections = list(server._ws_connections)
    try:
        for index, ws in enumerate(sockets):
            await ws.send(json.dumps({
                "id": str(index), "method": "host.wait",
                "params": {"auth_token": device["token"]},
            }))
        await asyncio.wait_for(all_started.wait(), timeout=1)

        await asyncio.wait_for(server.stop(), timeout=2)

        assert cancelled == 8
        assert server._ws_connections == set()
        assert server._ws_by_device == {}
        assert server._ws_rpc_counts == {}
        assert all(connection.transport.is_closing() for connection in server_connections)
        assert all(ws.close_code == 1001 for ws in sockets)
    finally:
        for ws in sockets:
            await ws.close()
        await server.stop()


@pytest.mark.asyncio
async def test_connection_revocation_closes_devices_concurrently(short_tmp: Path) -> None:
    import asyncio

    class SlowSocket:
        async def close(self, **_kwargs):
            await asyncio.sleep(0.1)

    server = host_server.Server(home=short_tmp)
    first = SlowSocket()
    second = SlowSocket()
    server._ws_by_device[("connection", "first")].add(first)
    server._ws_by_device[("connection", "second")].add(second)

    started = asyncio.get_running_loop().time()
    closed = await server.close_connection_websockets("connection")
    elapsed = asyncio.get_running_loop().time() - started

    assert closed == 2
    assert elapsed < 0.18


@pytest.mark.asyncio
async def test_connection_revocation_does_not_cancel_calling_handler(short_tmp: Path) -> None:
    import asyncio

    class Socket:
        async def close(self, **_kwargs):
            return None

    server = host_server.Server(home=short_tmp)
    socket = Socket()

    async def revoke_self():
        task = asyncio.current_task()
        server._ws_by_device[("connection", "device")].add(socket)
        server._ws_tasks[socket] = task
        return await server.close_connection_websockets("connection")

    assert await revoke_self() == 1
