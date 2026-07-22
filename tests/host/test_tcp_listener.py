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
    with pytest.raises(ValueError, match="Tailscale|private LAN"):
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
