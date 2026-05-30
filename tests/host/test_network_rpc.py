"""host.network.* — status / set_advertised / restart_host_server contract."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from alpi import config as cfg_mod
from alpi.host import network_rpc
from alpi.host import server as host_server
from alpi.host.network_rpc import _validate_advertised_host


def _bootstrap(tmp_path: Path) -> Path:
    home = tmp_path / "h"
    home.mkdir()
    cfg = cfg_mod.Config(home=home, model="openai/x")
    cfg_mod.save(cfg)
    return home



# --------------------------------------------------------------------
# _validate_advertised_host
# --------------------------------------------------------------------


def test_validate_accepts_rfc1918_lan() -> None:
    assert _validate_advertised_host("192.168.1.10") is None
    assert _validate_advertised_host("10.0.0.1") is None
    assert _validate_advertised_host("172.16.5.5") is None


def test_validate_accepts_tailscale_cgnat() -> None:
    assert _validate_advertised_host("100.114.140.25") is None
    assert _validate_advertised_host("100.64.0.1") is None


def test_validate_accepts_hostnames() -> None:
    assert _validate_advertised_host("myhost.local") is None
    assert _validate_advertised_host("alpi-mbp.ts.net") is None
    assert _validate_advertised_host("umbrel.local") is None
    assert _validate_advertised_host("a") is None  # single-label hostnames are legal


def test_validate_rejects_public_ip() -> None:
    err = _validate_advertised_host("8.8.8.8")
    assert err is not None and "public" in err.lower()


def test_validate_rejects_loopback() -> None:
    err = _validate_advertised_host("127.0.0.1")
    assert err is not None and "loopback" in err.lower()


def test_validate_rejects_unspecified() -> None:
    err = _validate_advertised_host("0.0.0.0")
    assert err is not None


def test_validate_rejects_multicast_linklocal_reserved() -> None:
    assert _validate_advertised_host("224.0.0.1") is not None
    assert _validate_advertised_host("169.254.1.1") is not None


def test_validate_rejects_malformed_hostname() -> None:
    err = _validate_advertised_host("not a valid host!")
    assert err is not None and "hostname" in err.lower()


def test_validate_rejects_empty_label() -> None:
    err = _validate_advertised_host("foo..bar")
    assert err is not None


# --------------------------------------------------------------------
# host.network.status
# --------------------------------------------------------------------


def _stub_probes(monkeypatch, *, tailscale=None, lan=None, udp_ip=None, udp_err=None, ifconfig=None):
    monkeypatch.setattr(
        "alpi.host.network_rpc._probe_endpoints",
        lambda: {
            "tailscale": tailscale,
            "lan": lan,
            "udp_ip": udp_ip,
            "udp_err": udp_err,
            "ifconfig": ifconfig,
        },
    )


@pytest.mark.asyncio
async def test_status_reports_in_use_host_and_port(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = _bootstrap(tmp_path)
    _stub_probes(monkeypatch, udp_err="no route")

    srv = host_server.Server(home=home)
    network_rpc.register(srv)
    resp = await srv._dispatch({"id": "n", "method": "host.network.status", "params": {}})
    result = resp["result"]
    assert result["scope_in_use"] is None
    assert result["host_in_use"] is None
    assert result["port"] == 49200
    assert result["candidates"]["tailscale"] is None
    assert result["candidates"]["lan"] is None
    assert result["candidates"]["configured"] is None


@pytest.mark.asyncio
async def test_status_reports_tailscale_when_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = _bootstrap(tmp_path)
    _stub_probes(monkeypatch, tailscale="100.114.140.25", lan="192.168.1.10")

    srv = host_server.Server(home=home)
    network_rpc.register(srv)
    resp = await srv._dispatch({"id": "n", "method": "host.network.status", "params": {}})
    result = resp["result"]
    assert result["scope_in_use"] == "tailscale"
    assert result["host_in_use"] == "100.114.140.25"
    assert result["candidates"]["tailscale"] == "100.114.140.25"
    assert result["candidates"]["lan"] == "192.168.1.10"


@pytest.mark.asyncio
async def test_status_reports_lan_when_no_tailscale(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = _bootstrap(tmp_path)
    _stub_probes(monkeypatch, lan="192.168.1.10")

    srv = host_server.Server(home=home)
    network_rpc.register(srv)
    resp = await srv._dispatch({"id": "n", "method": "host.network.status", "params": {}})
    result = resp["result"]
    assert result["scope_in_use"] == "lan"
    assert result["host_in_use"] == "192.168.1.10"


@pytest.mark.asyncio
async def test_status_probes_each_endpoint_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = _bootstrap(tmp_path)
    calls = {"n": 0}

    def fake_probes():
        calls["n"] += 1
        return {
            "tailscale": "100.114.140.25",
            "lan": "192.168.1.10",
            "udp_ip": "192.168.1.10",
            "udp_err": None,
            "ifconfig": "192.168.1.10",
        }

    monkeypatch.setattr("alpi.host.network_rpc._probe_endpoints", fake_probes)
    srv = host_server.Server(home=home)
    network_rpc.register(srv)
    await srv._dispatch({"id": "n", "method": "host.network.status", "params": {}})
    assert calls["n"] == 1, (
        f"_probe_endpoints called {calls['n']} times — the dedup that "
        "fixed the default-profile 5s hang has regressed"
    )


@pytest.mark.asyncio
async def test_status_resolves_docker_advertise_host(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = _bootstrap(tmp_path)
    monkeypatch.setenv("ALPI_PLATFORM", "docker")
    monkeypatch.setenv("ALPI_HOST_ADVERTISE_HOST", "alpi.tailnet.ts.net")
    _stub_probes(monkeypatch)

    srv = host_server.Server(home=home)
    network_rpc.register(srv)
    resp = await srv._dispatch({"id": "n", "method": "host.network.status", "params": {}})
    r = resp["result"]
    assert r["host_in_use"] == "alpi.tailnet.ts.net"
    assert r["scope_in_use"] == "docker"
    assert r["is_override"] is False
    assert r["candidates"]["docker"] == "alpi.tailnet.ts.net"


@pytest.mark.asyncio
async def test_status_docker_with_no_advertise_returns_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The container can't reach the host's Tailscale/LAN interface, so a
    probe hit must NOT be advertised — without the env it's unresolved."""
    home = _bootstrap(tmp_path)
    monkeypatch.setenv("ALPI_PLATFORM", "docker")
    monkeypatch.delenv("ALPI_HOST_ADVERTISE_HOST", raising=False)
    _stub_probes(monkeypatch, tailscale="100.114.140.25", lan="192.168.1.10")

    srv = host_server.Server(home=home)
    network_rpc.register(srv)
    resp = await srv._dispatch({"id": "n", "method": "host.network.status", "params": {}})
    assert resp["result"]["host_in_use"] is None
    assert resp["result"]["scope_in_use"] is None


@pytest.mark.asyncio
async def test_status_configured_overrides_docker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = _bootstrap(tmp_path)
    cfg = cfg_mod.load(home)
    cfg.host = {"tcp_host": "operator.set.example"}
    cfg_mod.save(cfg)
    monkeypatch.setenv("ALPI_PLATFORM", "docker")
    monkeypatch.setenv("ALPI_HOST_ADVERTISE_HOST", "ignored.ts.net")
    _stub_probes(monkeypatch)

    srv = host_server.Server(home=home)
    network_rpc.register(srv)
    resp = await srv._dispatch({"id": "n", "method": "host.network.status", "params": {}})
    assert resp["result"]["host_in_use"] == "operator.set.example"
    assert resp["result"]["is_override"] is True


@pytest.mark.asyncio
async def test_status_classifies_override_by_host_character(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """scope_in_use reflects the NETWORK CHARACTER of the host, not the resolution path. A configured Tailscale IP shows as 'tailscale' (not 'configured'); a configured hostname shows as 'custom'. `is_override` carries the resolution-path bit separately."""
    home = _bootstrap(tmp_path)
    monkeypatch.setattr("alpi.host.tailscale.detect_tailscale_ip", lambda: "100.114.140.25")
    monkeypatch.setattr("alpi.host.network._detect_lan_ip", lambda: "192.168.1.10")

    # Case 1: override IS the Tailscale IP → scope_in_use is "tailscale".
    cfg = cfg_mod.load(home)
    cfg.host = {"tcp_host": "100.114.140.25"}
    cfg_mod.save(cfg)
    srv = host_server.Server(home=home)
    network_rpc.register(srv)
    resp = await srv._dispatch({"id": "n", "method": "host.network.status", "params": {}})
    r = resp["result"]
    assert r["scope_in_use"] == "tailscale"
    assert r["host_in_use"] == "100.114.140.25"
    assert r["is_override"] is True
    assert r["candidates"]["configured"] == "100.114.140.25"

    # Case 2: override IS a private LAN IP → "lan".
    cfg.host = {"tcp_host": "192.168.1.10"}
    cfg_mod.save(cfg)
    resp = await srv._dispatch({"id": "n", "method": "host.network.status", "params": {}})
    r = resp["result"]
    assert r["scope_in_use"] == "lan"
    assert r["is_override"] is True

    # Case 3: override is a hostname → "custom" (real custom, not a network IP).
    cfg.host = {"tcp_host": "myhost.local"}
    cfg_mod.save(cfg)
    resp = await srv._dispatch({"id": "n", "method": "host.network.status", "params": {}})
    r = resp["result"]
    assert r["scope_in_use"] == "custom"
    assert r["host_in_use"] == "myhost.local"
    assert r["is_override"] is True


# --------------------------------------------------------------------
# host.network.set_advertised
# --------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_advertised_persists_host_and_device_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = _bootstrap(tmp_path)

    srv = host_server.Server(home=home)
    network_rpc.register(srv)
    resp = await srv._dispatch({
        "id": "n", "method": "host.network.set_advertised",
        "params": {"host": "myhost.local", "device_name": "javi-mbp"},
    })
    assert resp["result"] == {"ok": True, "restart_needed": True}

    cfg = cfg_mod.load(home)
    assert cfg.host["tcp_host"] == "myhost.local"
    assert cfg.host["device_name"] == "javi-mbp"


@pytest.mark.asyncio
async def test_set_advertised_empty_host_unsets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = _bootstrap(tmp_path)
    cfg = cfg_mod.load(home)
    cfg.host = {"tcp_host": "myhost.local"}
    cfg_mod.save(cfg)

    srv = host_server.Server(home=home)
    network_rpc.register(srv)
    resp = await srv._dispatch({
        "id": "n", "method": "host.network.set_advertised",
        "params": {"host": "", "device_name": ""},
    })
    assert resp["result"]["ok"] is True
    assert resp["result"]["restart_needed"] is True

    cfg2 = cfg_mod.load(home)
    assert "tcp_host" not in (cfg2.host or {})


@pytest.mark.asyncio
async def test_set_advertised_no_op_when_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = _bootstrap(tmp_path)
    cfg = cfg_mod.load(home)
    cfg.host = {"tcp_host": "myhost.local", "device_name": "x"}
    cfg_mod.save(cfg)

    srv = host_server.Server(home=home)
    network_rpc.register(srv)
    resp = await srv._dispatch({
        "id": "n", "method": "host.network.set_advertised",
        "params": {"host": "myhost.local", "device_name": "x"},
    })
    assert resp["result"] == {"ok": True, "restart_needed": False}


@pytest.mark.asyncio
async def test_set_advertised_rejects_public_ip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = _bootstrap(tmp_path)

    srv = host_server.Server(home=home)
    network_rpc.register(srv)
    resp = await srv._dispatch({
        "id": "n", "method": "host.network.set_advertised",
        "params": {"host": "8.8.8.8"},
    })
    assert "error" in resp
    assert resp["error"]["message"] == "invalid-host"
    assert "public" in resp["error"]["data"]["detail"].lower()
    cfg = cfg_mod.load(home)
    assert "tcp_host" not in (cfg.host or {})


@pytest.mark.asyncio
async def test_set_advertised_rejects_loopback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = _bootstrap(tmp_path)

    srv = host_server.Server(home=home)
    network_rpc.register(srv)
    resp = await srv._dispatch({
        "id": "n", "method": "host.network.set_advertised",
        "params": {"host": "127.0.0.1"},
    })
    assert "error" in resp
    assert resp["error"]["message"] == "invalid-host"


@pytest.mark.asyncio
async def test_set_advertised_rejects_garbage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = _bootstrap(tmp_path)

    srv = host_server.Server(home=home)
    network_rpc.register(srv)
    resp = await srv._dispatch({
        "id": "n", "method": "host.network.set_advertised",
        "params": {"host": "not a hostname!!!"},
    })
    assert "error" in resp
    assert resp["error"]["message"] == "invalid-host"


# --------------------------------------------------------------------
# host.network.restart_host_server
# --------------------------------------------------------------------


@pytest.mark.asyncio
async def test_restart_when_daemon_running(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = _bootstrap(tmp_path)
    monkeypatch.setattr("alpi.service.daemon_running_pid", lambda root: 4242)
    stop_calls: list[Any] = []
    monkeypatch.setattr(
        "alpi.service.stop_daemon",
        lambda root, timeout: stop_calls.append((root, timeout)),
    )

    srv = host_server.Server(home=home)
    network_rpc.register(srv)
    resp = await srv._dispatch({
        "id": "n", "method": "host.network.restart_host_server", "params": {},
    })
    assert resp["result"] == {"ok": True, "restarted": True}
    assert len(stop_calls) == 1


@pytest.mark.asyncio
async def test_restart_when_daemon_not_running(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = _bootstrap(tmp_path)
    monkeypatch.setattr("alpi.service.daemon_running_pid", lambda root: None)
    stop_calls: list[Any] = []
    monkeypatch.setattr(
        "alpi.service.stop_daemon",
        lambda root, timeout: stop_calls.append((root, timeout)),
    )

    srv = host_server.Server(home=home)
    network_rpc.register(srv)
    resp = await srv._dispatch({
        "id": "n", "method": "host.network.restart_host_server", "params": {},
    })
    assert resp["result"] == {"ok": True, "restarted": False}
    assert stop_calls == []


# --------------------------------------------------------------------
# Parameter semantics: absent key preserves, empty string unsets
# --------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_advertised_partial_call_with_only_host_preserves_device_name(
    tmp_path: Path,
) -> None:
    """Caller supplies only `host` → `device_name` stays untouched. Earlier the missing key was conflated with empty-string and silently wiped the other field."""
    home = _bootstrap(tmp_path)
    cfg = cfg_mod.load(home)
    cfg.host = {"tcp_host": "old.local", "device_name": "keep-me"}
    cfg_mod.save(cfg)

    srv = host_server.Server(home=home)
    network_rpc.register(srv)
    resp = await srv._dispatch({
        "id": "n", "method": "host.network.set_advertised",
        "params": {"host": "new.local"},
    })
    assert resp["result"]["ok"] is True

    cfg2 = cfg_mod.load(home)
    assert cfg2.host["tcp_host"] == "new.local"
    assert cfg2.host["device_name"] == "keep-me"


@pytest.mark.asyncio
async def test_set_advertised_partial_call_with_only_device_name_preserves_host(
    tmp_path: Path,
) -> None:
    home = _bootstrap(tmp_path)
    cfg = cfg_mod.load(home)
    cfg.host = {"tcp_host": "keep.me", "device_name": "old-name"}
    cfg_mod.save(cfg)

    srv = host_server.Server(home=home)
    network_rpc.register(srv)
    resp = await srv._dispatch({
        "id": "n", "method": "host.network.set_advertised",
        "params": {"device_name": "new-name"},
    })
    assert resp["result"]["ok"] is True

    cfg2 = cfg_mod.load(home)
    assert cfg2.host["tcp_host"] == "keep.me"
    assert cfg2.host["device_name"] == "new-name"


@pytest.mark.asyncio
async def test_set_advertised_explicit_empty_unsets_only_that_field(
    tmp_path: Path,
) -> None:
    home = _bootstrap(tmp_path)
    cfg = cfg_mod.load(home)
    cfg.host = {"tcp_host": "x.local", "device_name": "keep-me"}
    cfg_mod.save(cfg)

    srv = host_server.Server(home=home)
    network_rpc.register(srv)
    resp = await srv._dispatch({
        "id": "n", "method": "host.network.set_advertised",
        "params": {"host": ""},
    })
    assert resp["result"]["ok"] is True

    cfg2 = cfg_mod.load(home)
    assert "tcp_host" not in (cfg2.host or {})
    assert cfg2.host["device_name"] == "keep-me"


# --------------------------------------------------------------------
# Local-only enforcement: remote (WS) MUST NOT reach these verbs
# --------------------------------------------------------------------


def test_local_only_methods_include_all_network_verbs() -> None:
    """All three host.network.* RPCs are flagged local-only so a paired remote client cannot mutate daemon config or restart the host server over WS."""
    from alpi.host.server import _LOCAL_ONLY_METHODS
    assert "host.network.status" in _LOCAL_ONLY_METHODS
    assert "host.network.set_advertised" in _LOCAL_ONLY_METHODS
    assert "host.network.restart_host_server" in _LOCAL_ONLY_METHODS


@pytest.mark.asyncio
@pytest.mark.parametrize("method,params", [
    ("host.network.status", {}),
    ("host.network.set_advertised", {"host": "192.168.1.10"}),
    ("host.network.restart_host_server", {}),
])
async def test_network_verbs_blocked_over_remote_transport(
    tmp_path: Path, method: str, params: dict, monkeypatch,
) -> None:
    """Same shape as the devices guard test: paired-remote callers must hit the local-only gate (-32001 forbidden) regardless of token validity. Belt-and-braces over the symbol-presence smoke above."""
    import json
    from alpi import home as home_mod
    from alpi.host import devices

    home = _bootstrap(tmp_path)
    # devices.add() resolves the store via `home_mod._ROOT` — without this monkeypatch the parametrized cases would write "seed" rows into the developer's real ~/.alpi/host/devices.yaml on every test run.
    monkeypatch.setattr(home_mod, "_ROOT", tmp_path)
    devices._invalidate_cache()
    row = devices.add(label="seed")  # ensure token check is enforced
    srv = host_server.Server(home=home)
    devices.register(srv)
    network_rpc.register(srv)

    sent: list[dict] = []
    async def send(payload):
        sent.append(payload)

    body = {
        "id": "r",
        "method": method,
        "params": {**params, "auth_token": row["token"]},
    }
    await srv._handle_request(json.dumps(body), send, require_token=True)

    assert len(sent) == 1
    assert sent[0]["error"]["code"] == -32001
    assert sent[0]["error"]["message"] == "forbidden"


@pytest.mark.asyncio
async def test_network_status_allowed_over_local_unix_transport(
    tmp_path: Path,
) -> None:
    """Counterpart to the block test: same verb via the Unix socket (require_token=False) succeeds — the gate is transport-scoped."""
    import json
    home = _bootstrap(tmp_path)
    srv = host_server.Server(home=home)
    network_rpc.register(srv)

    sent: list[dict] = []
    async def send(payload):
        sent.append(payload)

    await srv._handle_request(
        json.dumps({"id": "r", "method": "host.network.status", "params": {}}),
        send,
        require_token=False,
    )
    assert len(sent) == 1
    assert "result" in sent[0]
    assert "scope_in_use" in sent[0]["result"]
