"""Per-device pairing tokens — store, verbs, middleware."""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

import pytest

from alpi.host import devices
from alpi.host import server as host_server


@pytest.fixture
def short_tmp(monkeypatch):
    d = Path(tempfile.mkdtemp(prefix="alp-host-devs-", dir="/tmp"))
    from alpi import home as home_mod
    monkeypatch.setattr(home_mod, "_ROOT", d)
    devices._invalidate_cache()
    try:
        yield d
    finally:
        devices._invalidate_cache()
        shutil.rmtree(d, ignore_errors=True)


def test_empty_store_loads_empty(short_tmp: Path) -> None:
    assert devices.load() == []


def test_add_persists(short_tmp: Path) -> None:
    row = devices.add(label="iPhone")
    loaded = devices.load()
    assert len(loaded) == 1
    assert loaded[0]["token"] == row["token"]
    assert loaded[0]["label"] == "iPhone"


def test_is_valid_round_trip(short_tmp: Path) -> None:
    row = devices.add(label="x")
    assert devices.is_valid(row["token"])
    assert not devices.is_valid("nope")
    assert not devices.is_valid("")


def test_revoke(short_tmp: Path) -> None:
    row = devices.add(label="x")
    assert devices.revoke(row["token"]) is True
    assert devices.is_valid(row["token"]) is False
    assert devices.revoke(row["token"]) is False  # idempotent


def test_touch_updates_last_seen(short_tmp: Path) -> None:
    row = devices.add(label="x")
    assert row["last_seen"] is None
    devices.touch(row["token"])
    assert devices.load()[0]["last_seen"] is not None


def test_rename(short_tmp: Path) -> None:
    row = devices.add(label="pending")
    devices.rename(row["token"], "iPhone")
    assert devices.load()[0]["label"] == "iPhone"


@pytest.mark.asyncio
async def test_list_verb_redacts_token(short_tmp: Path) -> None:
    row = devices.add(label="iPhone")
    srv = host_server.Server(home=short_tmp)
    devices.register(srv)
    resp = await srv._dispatch({
        "id": "r", "method": "host.devices.list", "params": {},
    })
    assert "result" in resp
    listed = resp["result"]["devices"]
    assert len(listed) == 1
    assert listed[0]["label"] == "iPhone"
    assert listed[0]["token_id"] == row["token"][-8:]
    assert "token" not in listed[0]


@pytest.mark.asyncio
async def test_generate_verb_returns_full_token_with_network(
    short_tmp: Path, monkeypatch,
) -> None:
    from alpi.host import network as net

    monkeypatch.setattr(net, "resolve_host_endpoint", lambda h: ("100.64.0.1", "tailscale"))
    monkeypatch.setattr(net, "resolve_host_tcp_port", lambda h: 49200)
    monkeypatch.setattr(net, "resolve_host_pairing_name", lambda h: "alpi-mac")

    srv = host_server.Server(home=short_tmp)
    devices.register(srv)
    resp = await srv._dispatch({
        "id": "r",
        "method": "host.devices.generate",
        "params": {"label": "iPad"},
    })
    result = resp["result"]
    assert result["token"]
    assert result["label"] == "iPad"
    assert result["host"] == "100.64.0.1"
    assert result["scope"] == "tailscale"
    assert result["is_override"] is False
    assert result["port"] == 49200
    assert result["pairing_name"] == "alpi-mac"
    assert len(devices.load()) == 1


@pytest.mark.asyncio
async def test_generate_verb_classifies_configured_override_by_host_character(
    short_tmp: Path, monkeypatch,
) -> None:
    """A cfg.host.tcp_host override that happens to be a Tailscale IP must still surface as scope='tailscale', not 'configured'. The user cares about network character; the override path is bookkeeping (`is_override=true`)."""
    from alpi.host import network as net

    monkeypatch.setattr(net, "resolve_host_endpoint", lambda h: ("100.114.140.25", "configured"))
    monkeypatch.setattr(net, "resolve_host_tcp_port", lambda h: 49200)
    monkeypatch.setattr(net, "resolve_host_pairing_name", lambda h: "alpi-mac")

    srv = host_server.Server(home=short_tmp)
    devices.register(srv)
    resp = await srv._dispatch({
        "id": "r",
        "method": "host.devices.generate",
        "params": {"label": "iPhone"},
    })
    result = resp["result"]
    assert result["host"] == "100.114.140.25"
    assert result["scope"] == "tailscale"  # NOT "configured"
    assert result["is_override"] is True


@pytest.mark.asyncio
async def test_generate_verb_classifies_hostname_override_as_custom(
    short_tmp: Path, monkeypatch,
) -> None:
    from alpi.host import network as net

    monkeypatch.setattr(net, "resolve_host_endpoint", lambda h: ("myhost.local", "configured"))
    monkeypatch.setattr(net, "resolve_host_tcp_port", lambda h: 49200)
    monkeypatch.setattr(net, "resolve_host_pairing_name", lambda h: "alpi-mac")

    srv = host_server.Server(home=short_tmp)
    devices.register(srv)
    resp = await srv._dispatch({
        "id": "r",
        "method": "host.devices.generate",
        "params": {"label": "iPad"},
    })
    result = resp["result"]
    assert result["scope"] == "custom"
    assert result["is_override"] is True


@pytest.mark.asyncio
async def test_generate_verb_refuses_when_no_endpoint(
    short_tmp: Path, monkeypatch,
) -> None:
    """Without an advertised host the verb must NOT save a token —
    a token without a way to reach the daemon is a UX trap (orphan
    devices in the list, no QR, user can't recover without revoking)."""
    from alpi.host import network as net

    monkeypatch.setattr(net, "resolve_host_endpoint", lambda h: None)

    srv = host_server.Server(home=short_tmp)
    devices.register(srv)
    resp = await srv._dispatch({
        "id": "r",
        "method": "host.devices.generate",
        "params": {"label": "Phone"},
    })
    assert "error" in resp
    assert resp["error"]["code"] == -32010
    assert resp["error"]["message"] == "no-advertised-host"
    assert len(devices.load()) == 0


@pytest.mark.asyncio
async def test_revoke_verb(short_tmp: Path) -> None:
    row = devices.add(label="x")
    srv = host_server.Server(home=short_tmp)
    devices.register(srv)
    resp = await srv._dispatch({
        "id": "r",
        "method": "host.devices.revoke",
        "params": {"token_id": row["token"][-8:]},
    })
    assert resp["result"]["ok"]
    assert devices.load() == []


@pytest.mark.asyncio
async def test_revoke_unknown_returns_not_found(short_tmp: Path) -> None:
    srv = host_server.Server(home=short_tmp)
    devices.register(srv)
    resp = await srv._dispatch({
        "id": "r",
        "method": "host.devices.revoke",
        "params": {"token_id": "deadbeef"},
    })
    assert resp["error"]["code"] == -32004


def test_check_token_fail_closed_when_store_empty(short_tmp: Path) -> None:
    from alpi.host.server import _check_token

    assert _check_token({"params": {}}) is False
    assert _check_token({"params": {"auth_token": "anything"}}) is False


def test_check_token_enforces_once_store_has_entries(short_tmp: Path) -> None:
    from alpi.host.server import _check_token

    row = devices.add(label="x")
    assert _check_token({"params": {}}) is False
    assert _check_token({"params": {"auth_token": "wrong"}}) is False
    assert _check_token({"params": {"auth_token": row["token"]}}) is True


def test_check_token_touches_last_seen_on_match(short_tmp: Path) -> None:
    from alpi.host.server import _check_token

    row = devices.add(label="x")
    assert devices.load()[0]["last_seen"] is None
    _check_token({"params": {"auth_token": row["token"]}})
    assert devices.load()[0]["last_seen"] is not None


@pytest.mark.asyncio
@pytest.mark.parametrize("method", [
    "host.devices.generate",
    "host.devices.revoke",
    "host.devices.rename",
    "host.devices.promote",
    "host.devices.demote",
])
async def test_devices_mutations_require_admin_role(
    short_tmp: Path, method: str,
) -> None:
    row = devices.add(label="seed", role="member")
    srv = host_server.Server(home=short_tmp)
    devices.register(srv)

    sent: list[dict] = []

    async def send(payload):
        sent.append(payload)

    body = {
        "id": "r",
        "method": method,
        "params": {"auth_token": row["token"], "token_id": row["token"][-8:], "label": "x"},
    }
    await srv._handle_request(json.dumps(body), send, require_token=True)

    assert len(sent) == 1
    assert sent[0]["error"]["code"] == -32001
    assert sent[0]["error"]["message"] == "forbidden"
    assert "admin role required" in sent[0]["error"]["data"]["detail"]


@pytest.mark.asyncio
async def test_devices_list_open_to_members(short_tmp: Path) -> None:
    member = devices.add(label="phone", role="member")
    devices.add(label="laptop", role="admin")
    srv = host_server.Server(home=short_tmp)
    devices.register(srv)

    sent: list[dict] = []

    async def send(payload):
        sent.append(payload)

    body = {
        "id": "r", "method": "host.devices.list",
        "params": {"auth_token": member["token"]},
    }
    await srv._handle_request(json.dumps(body), send, require_token=True)

    assert len(sent) == 1
    assert "error" not in sent[0]
    rows = sent[0]["result"]["devices"]
    assert {r["label"] for r in rows} == {"phone", "laptop"}
    assert {r["role"] for r in rows} == {"member", "admin"}
    # Full tokens stay server-side regardless of who's asking.
    assert all("token" not in r for r in rows)


@pytest.mark.asyncio
@pytest.mark.parametrize("method", [
    "host.devices.generate",
    "host.devices.revoke",
    "host.devices.promote",
    "host.devices.demote",
])
async def test_devices_mutations_allowed_for_admin(
    short_tmp: Path, monkeypatch, method: str,
) -> None:
    admin = devices.add(label="laptop", role="admin")
    target = devices.add(label="victim", role="member")
    srv = host_server.Server(home=short_tmp)
    devices.register(srv)

    from alpi.host import network as net_mod
    monkeypatch.setattr(net_mod, "resolve_host_endpoint", lambda _r: ("100.0.0.1", "tailscale"))
    monkeypatch.setattr(net_mod, "resolve_host_tcp_port", lambda _r: 49200)
    monkeypatch.setattr(net_mod, "resolve_host_pairing_name", lambda _r: "alpi")
    monkeypatch.setattr(net_mod, "classify_scope", lambda _h, _s: "tailscale")

    sent: list[dict] = []

    async def send(payload):
        sent.append(payload)

    body = {
        "id": "r", "method": method,
        "params": {
            "auth_token": admin["token"],
            "token_id": target["token"][-8:],
            "label": "renamed",
        },
    }
    await srv._handle_request(json.dumps(body), send, require_token=True)

    assert len(sent) == 1, sent
    assert "error" not in sent[0], sent[0]


@pytest.mark.asyncio
async def test_devices_promote_demote_flip_role(short_tmp: Path) -> None:
    admin = devices.add(label="laptop", role="admin")
    target = devices.add(label="phone", role="member")
    srv = host_server.Server(home=short_tmp)
    devices.register(srv)

    sent: list[dict] = []

    async def send(p):
        sent.append(p)

    promote = {
        "id": "1", "method": "host.devices.promote",
        "params": {"auth_token": admin["token"], "token_id": target["token"][-8:]},
    }
    await srv._handle_request(json.dumps(promote), send, require_token=True)
    assert sent[-1]["result"]["role"] == "admin"
    assert any(d["token"] == target["token"] and d["role"] == "admin" for d in devices.load())

    demote = {
        "id": "2", "method": "host.devices.demote",
        "params": {"auth_token": admin["token"], "token_id": target["token"][-8:]},
    }
    await srv._handle_request(json.dumps(demote), send, require_token=True)
    assert sent[-1]["result"]["role"] == "member"
    assert any(d["token"] == target["token"] and d["role"] == "member" for d in devices.load())


@pytest.mark.asyncio
@pytest.mark.parametrize("method", sorted(host_server._ADMIN_METHODS))
async def test_every_admin_method_rejects_member_token(
    short_tmp: Path, method: str,
) -> None:
    member = devices.add(label="phone", role="member")
    srv = host_server.Server(home=short_tmp)
    devices.register(srv)

    sent: list[dict] = []

    async def send(p):
        sent.append(p)

    body = {
        "id": "x", "method": method,
        "params": {"auth_token": member["token"]},
    }
    await srv._handle_request(json.dumps(body), send, require_token=True)

    assert len(sent) == 1, f"{method}: no response"
    err = sent[0].get("error")
    assert err is not None, f"{method}: should have been forbidden, got {sent[0]}"
    assert err["code"] == -32001, f"{method}: wrong code {err}"
    assert "admin role required" in err.get("data", {}).get("detail", ""), method


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method",
    [
        "host.clarification.respond",
        "host.clarification.pending",
    ],
)
async def test_clarification_rpc_is_member_callable(
    short_tmp: Path, method: str,
) -> None:
    """A ``member`` device that can chat with the agent must also be able to
    answer the agent's clarification questions. Approval stays admin-only
    because it authorizes commands; clarification only resolves a question.
    Member tokens MUST pass the admin gate for these two methods (the call
    can still fail downstream for unrelated reasons — e.g. unknown
    request_id — but never with ``-32001 admin role required``)."""
    member = devices.add(label="phone", role="member")
    srv = host_server.Server(home=short_tmp)
    devices.register(srv)
    # Wire the real clarification handlers so the dispatch reaches them.
    from alpi.host import clarification as host_clar
    host_clar.register(srv)

    sent: list[dict] = []

    async def send(p):
        sent.append(p)

    body = {
        "id": "x", "method": method,
        "params": {
            "auth_token": member["token"],
            # Bogus request_id is fine — we only care that the gate doesn't
            # short-circuit with "admin role required".
            "request_id": "deadbeef",
            "choice": "X",
        },
    }
    await srv._handle_request(json.dumps(body), send, require_token=True)

    assert len(sent) == 1
    err = sent[0].get("error")
    if err is not None:
        assert "admin role required" not in err.get("data", {}).get("detail", ""), method
    host_clar._reset_for_tests()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "rel_path",
    [
        # Top-level daemon directories.
        ".env",
        "./.env",
        ".env.local",
        ".envrc",
        "secrets/gmail_token.json",
        "secrets/api_keys.json",
        "host/devices.yaml",
        "gateway/telegram-state.json",
        "cache/update_check.json",
        # Nested directories — the prefix-only check used to miss these.
        "alp/secrets/identity.key",
        "skills/personal/foo/secrets/token.json",
        "skills/personal/foo/.env",
        "workspace/.env",
        "workspace/sub/.env.local",
        # Case-insensitive — matters on macOS HFS+/APFS default.
        "Secrets/anything",
        "WORKSPACE/.ENV",
        # Common private-key extensions.
        "memories/id_rsa.pem",
        "skills/foo/server.key",
        "data/cert.p12",
        # Path escape.
        "../outside.txt",
    ],
)
async def test_profile_read_file_denies_secret_paths(
    short_tmp: Path, rel_path: str,
) -> None:
    from alpi.host import device_state

    admin = devices.add(label="laptop", role="admin")
    home = short_tmp / "profiles" / "default"
    home.mkdir(parents=True)

    from alpi.host import handlers as host_handlers
    import unittest.mock as _mock
    with _mock.patch.object(host_handlers, "_resolve_home", return_value=home):
        srv = host_server.Server(home=short_tmp)
        device_state.register(srv)
        sent: list[dict] = []

        async def send(p):
            sent.append(p)

        body = {
            "id": "x", "method": "host.profile.read_file",
            "params": {
                "auth_token": admin["token"],
                "profile": "default", "rel_path": rel_path,
            },
        }
        await srv._handle_request(json.dumps(body), send, require_token=True)

    assert len(sent) == 1
    err = sent[0].get("error")
    assert err is not None, f"{rel_path}: not blocked — got {sent[0]}"
    assert err["code"] == -32001, err


@pytest.mark.asyncio
async def test_profile_read_file_blocks_symlink_into_denied_subtree(
    short_tmp: Path,
) -> None:
    from alpi.host import device_state

    admin = devices.add(label="laptop", role="admin")
    home = short_tmp / "profiles" / "default"
    (home / "secrets").mkdir(parents=True)
    (home / "secrets" / "gmail_token.json").write_text("REAL_TOKEN")
    (home / "memories").mkdir(parents=True)
    # User content directory points at a daemon-internal file via symlink.
    (home / "memories" / "innocent.md").symlink_to(home / "secrets" / "gmail_token.json")

    from alpi.host import handlers as host_handlers
    import unittest.mock as _mock
    with _mock.patch.object(host_handlers, "_resolve_home", return_value=home):
        srv = host_server.Server(home=short_tmp)
        device_state.register(srv)
        sent: list[dict] = []

        async def send(p):
            sent.append(p)

        body = {
            "id": "x", "method": "host.profile.read_file",
            "params": {
                "auth_token": admin["token"],
                "profile": "default", "rel_path": "memories/innocent.md",
            },
        }
        await srv._handle_request(json.dumps(body), send, require_token=True)

    assert sent[0].get("error", {}).get("code") == -32001


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "rel_path",
    [
        "alp/peers.yaml",
        "alp/workgroups/abc/transcript.jsonl",
        "memories/USER.md",
        "skills/personal/foo/SKILL.md",
        "workspace/notes.md",
        "logs/agent.log",
    ],
)
async def test_profile_read_file_allows_member_visible_content(
    short_tmp: Path, rel_path: str,
) -> None:
    from alpi.host import device_state

    member = devices.add(label="phone", role="member")
    home = short_tmp / "profiles" / "default"
    target = home / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("legit content")

    from alpi.host import handlers as host_handlers
    import unittest.mock as _mock
    with _mock.patch.object(host_handlers, "_resolve_home", return_value=home):
        srv = host_server.Server(home=short_tmp)
        device_state.register(srv)
        sent: list[dict] = []

        async def send(p):
            sent.append(p)

        body = {
            "id": "x", "method": "host.profile.read_file",
            "params": {
                "auth_token": member["token"],
                "profile": "default", "rel_path": rel_path,
            },
        }
        await srv._handle_request(json.dumps(body), send, require_token=True)

    assert "error" not in sent[0], f"{rel_path}: false positive — {sent[0]}"
    assert sent[0]["result"]["text"] == "legit content"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method", ["host.devices.generate", "host.profile.delete", "host.daemon.restart"],
)
async def test_empty_store_does_not_open_admin_methods_over_ws(
    short_tmp: Path, method: str,
) -> None:
    srv = host_server.Server(home=short_tmp)
    devices.register(srv)
    sent: list[dict] = []

    async def send(p):
        sent.append(p)

    for params in ({}, {"auth_token": "anything"}, {"auth_token": ""}):
        sent.clear()
        body = {"id": "x", "method": method, "params": params}
        await srv._handle_request(json.dumps(body), send, require_token=True)
        err = sent[0].get("error")
        assert err is not None, f"{method} {params} leaked through with empty store"
        assert err["code"] == -32000, (method, params, err)
        assert err["message"] == "auth-failed"


def test_legacy_yaml_without_role_defaults_to_member(short_tmp: Path) -> None:
    import yaml as _yaml
    path = devices._store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_yaml.safe_dump([
        {"token": "tok-legacy", "label": "Old MacBook", "created": 1, "last_seen": None},
    ]))
    devices._invalidate_cache()
    rows = devices.load()
    assert rows[0]["role"] == "member"
    # And the dispatcher refuses admin methods to the legacy device.
    valid, role = devices.validate_and_lookup_role("tok-legacy")
    assert valid is True
    assert role == "member"


def test_validate_and_touch_throttles_writes(short_tmp: Path, monkeypatch) -> None:
    """Two rapid hits within ``min_interval`` must not rewrite devices.yaml —
    otherwise every paired client's poll loop fsyncs the file every RPC."""
    row = devices.add(label="x")
    path = devices._store_path()
    base_mtime = path.stat().st_mtime_ns

    fake_now = float(int(devices.time.time()))
    monkeypatch.setattr(devices.time, "time", lambda: fake_now)
    devices._invalidate_cache()

    assert devices.validate_and_touch(row["token"], min_interval=60) is True
    first_mtime = path.stat().st_mtime_ns
    assert first_mtime != base_mtime  # initial last_seen=None forces a write.

    assert devices.validate_and_touch(row["token"], min_interval=60) is True
    assert path.stat().st_mtime_ns == first_mtime  # throttled — no rewrite.

    monkeypatch.setattr(devices.time, "time", lambda: fake_now + 61)
    assert devices.validate_and_touch(row["token"], min_interval=60) is True
    assert path.stat().st_mtime_ns != first_mtime  # past the window → writes again.


def test_validate_and_touch_fail_closed_when_store_empty(short_tmp: Path) -> None:
    assert devices.validate_and_touch("") is False
    assert devices.validate_and_touch("anything") is False
    valid, role = devices.validate_and_lookup_role("anything")
    assert valid is False
    assert role == ""


def test_validate_and_touch_rejects_unknown_when_populated(short_tmp: Path) -> None:
    row = devices.add(label="x")
    assert devices.validate_and_touch("nope") is False
    assert devices.validate_and_touch("") is False
    assert devices.validate_and_touch(row["token"]) is True


def test_save_is_atomic_no_tmp_leftover(short_tmp: Path) -> None:
    """Crash-safe save: tmp file gets renamed onto the real path, never left around."""
    devices.add(label="x")
    path = devices._store_path()
    tmp = path.with_suffix(path.suffix + ".tmp")
    assert path.exists()
    assert not tmp.exists()


@pytest.mark.asyncio
async def test_devices_verbs_allowed_over_local_unix_transport(
    short_tmp: Path,
) -> None:
    """Same verb, but called locally (no token gate) succeeds — the
    block is transport-scoped, not method-scoped."""
    devices.add(label="seed")
    srv = host_server.Server(home=short_tmp)
    devices.register(srv)

    sent: list[dict] = []

    async def send(payload):
        sent.append(payload)

    body = {"id": "r", "method": "host.devices.list", "params": {}}
    await srv._handle_request(json.dumps(body), send, require_token=False)

    assert len(sent) == 1
    assert "result" in sent[0]
    assert "devices" in sent[0]["result"]
