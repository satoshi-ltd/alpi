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
    """A network.host override that happens to be a Tailscale IP must still surface as scope='tailscale', not 'configured'. The user cares about network character; the override path is bookkeeping (`is_override=true`)."""
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
    assert resp["result"] == {"ok": True, "existed": True}
    assert devices.load() == []


@pytest.mark.asyncio
async def test_revoke_unknown_is_idempotent(short_tmp: Path) -> None:
    # Same UX rationale as host.peers.remove: the user's intent is "be gone".
    srv = host_server.Server(home=short_tmp)
    devices.register(srv)
    resp = await srv._dispatch({
        "id": "r",
        "method": "host.devices.revoke",
        "params": {"token_id": "deadbeef"},
    })
    assert resp["result"] == {"ok": True, "existed": False}


@pytest.mark.asyncio
async def test_revoke_idempotent_retry(short_tmp: Path) -> None:
    row = devices.add(label="x")
    srv = host_server.Server(home=short_tmp)
    devices.register(srv)
    first = await srv._dispatch({
        "id": "1", "method": "host.devices.revoke",
        "params": {"token_id": row["token"][-8:]},
    })
    second = await srv._dispatch({
        "id": "2", "method": "host.devices.revoke",
        "params": {"token_id": row["token"][-8:]},
    })
    assert first["result"] == {"ok": True, "existed": True}
    assert second["result"] == {"ok": True, "existed": False}


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
async def test_devices_list_blocked_for_members(short_tmp: Path) -> None:
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
    assert sent[0]["error"]["code"] == -32001
    assert sent[0]["error"]["data"]["detail"] == "admin role required"


@pytest.mark.asyncio
async def test_devices_list_allowed_for_admins(short_tmp: Path) -> None:
    admin = devices.add(label="laptop", role="admin")
    devices.add(label="phone", role="member")
    srv = host_server.Server(home=short_tmp)
    devices.register(srv)

    sent: list[dict] = []

    async def send(payload):
        sent.append(payload)

    body = {
        "id": "r", "method": "host.devices.list",
        "params": {"auth_token": admin["token"]},
    }
    await srv._handle_request(json.dumps(body), send, require_token=True)

    assert len(sent) == 1
    assert "error" not in sent[0]
    rows = sent[0]["result"]["devices"]
    assert {r["label"] for r in rows} == {"phone", "laptop"}
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


# Per-device profile scope


def test_add_default_scope_is_empty_list(short_tmp: Path) -> None:
    row = devices.add(label="x")
    assert row["profile_scope"] == []


def test_add_with_explicit_scope_preserves_names(short_tmp: Path) -> None:
    row = devices.add(label="phone", profile_scope=["work", "home"])
    assert row["profile_scope"] == ["work", "home"]


def test_add_normalises_scope_dedup_and_safe_chars(short_tmp: Path) -> None:
    row = devices.add(
        label="x",
        profile_scope=["work", "work", "bad name!", "", "valid_one-2"],
    )
    assert row["profile_scope"] == ["work", "valid_one-2"]


def test_set_profile_scope_round_trip(short_tmp: Path) -> None:
    row = devices.add(label="x")
    assert devices.set_profile_scope(row["token"], ["work"]) is True
    reloaded = next(d for d in devices.load() if d["token"] == row["token"])
    assert reloaded["profile_scope"] == ["work"]
    assert devices.set_profile_scope(row["token"], ["work"]) is False


def test_legacy_yaml_without_scope_defaults_to_empty(short_tmp: Path) -> None:
    devices._store_path().parent.mkdir(parents=True, exist_ok=True)
    devices._store_path().write_text(
        "- token: tok-legacy\n  label: pre-host-1\n  created: 100\n  role: member\n",
    )
    rows = devices.load()
    assert rows == [{
        "token": "tok-legacy", "label": "pre-host-1", "created": 100,
        "last_seen": None, "role": "member", "profile_scope": [],
    }]


def test_validate_and_lookup_returns_scope(short_tmp: Path) -> None:
    row = devices.add(label="x", role="member", profile_scope=["work"])
    valid, role, scope = devices.validate_and_lookup(row["token"])
    assert valid is True
    assert role == "member"
    assert scope == ["work"]


def test_validate_and_lookup_empty_for_unknown(short_tmp: Path) -> None:
    valid, role, scope = devices.validate_and_lookup("never-seen")
    assert (valid, role, scope) == (False, "", [])


@pytest.mark.asyncio
async def test_set_profiles_verb_updates_scope(short_tmp: Path) -> None:
    row = devices.add(label="phone", role="member")
    srv = host_server.Server(home=short_tmp)
    devices.register(srv)
    resp = await srv._dispatch({
        "id": "r", "method": "host.devices.set_profiles",
        "params": {"token_id": row["token"][-8:], "profiles": ["work", "home"]},
    })
    assert resp["result"] == {"ok": True, "profile_scope": ["work", "home"]}
    reloaded = next(d for d in devices.load() if d["token"] == row["token"])
    assert reloaded["profile_scope"] == ["work", "home"]


@pytest.mark.asyncio
async def test_set_profiles_refuses_admin_devices(short_tmp: Path) -> None:
    row = devices.add(label="laptop", role="admin")
    srv = host_server.Server(home=short_tmp)
    devices.register(srv)
    resp = await srv._dispatch({
        "id": "r", "method": "host.devices.set_profiles",
        "params": {"token_id": row["token"][-8:], "profiles": ["work"]},
    })
    assert resp["error"]["code"] == -32001
    assert "admin" in resp["error"]["data"]["detail"].lower()


@pytest.mark.asyncio
async def test_set_profiles_unknown_token_returns_404(short_tmp: Path) -> None:
    srv = host_server.Server(home=short_tmp)
    devices.register(srv)
    resp = await srv._dispatch({
        "id": "r", "method": "host.devices.set_profiles",
        "params": {"token_id": "deadbeef", "profiles": ["work"]},
    })
    assert resp["error"]["code"] == -32004


@pytest.mark.asyncio
async def test_promote_to_admin_clears_scope(short_tmp: Path) -> None:
    row = devices.add(label="phone", role="member", profile_scope=["work"])
    srv = host_server.Server(home=short_tmp)
    devices.register(srv)
    resp = await srv._dispatch({
        "id": "r", "method": "host.devices.promote",
        "params": {"token_id": row["token"][-8:]},
    })
    assert resp["result"]["role"] == "admin"
    reloaded = next(d for d in devices.load() if d["token"] == row["token"])
    assert reloaded["profile_scope"] == []


@pytest.mark.asyncio
async def test_scope_gate_allows_in_scope_profile(short_tmp: Path) -> None:
    row = devices.add(label="phone", role="member", profile_scope=["work"])
    srv = host_server.Server(home=short_tmp)
    devices.register(srv)

    async def send(payload):
        sent.append(payload)

    sent: list[dict] = []
    body = {
        "id": "r", "method": "host.profile.detail",
        "params": {"auth_token": row["token"], "profile": "work"},
    }
    await srv._handle_request(json.dumps(body), send, require_token=True)
    assert sent, "handler should have sent a response"
    err = sent[0].get("error") or {}
    assert err.get("message") != "forbidden", sent[0]


@pytest.mark.asyncio
async def test_scope_gate_blocks_out_of_scope_profile(short_tmp: Path) -> None:
    row = devices.add(label="phone", role="member", profile_scope=["work"])
    srv = host_server.Server(home=short_tmp)
    devices.register(srv)

    sent: list[dict] = []

    async def send(payload):
        sent.append(payload)

    body = {
        "id": "r", "method": "host.profile.detail",
        "params": {"auth_token": row["token"], "profile": "personal"},
    }
    await srv._handle_request(json.dumps(body), send, require_token=True)
    assert sent[0]["error"]["code"] == -32001
    assert "scope" in sent[0]["error"]["data"]["detail"]


@pytest.mark.asyncio
async def test_scope_gate_admin_bypasses_scope(short_tmp: Path) -> None:
    row = devices.add(label="laptop", role="admin")
    devices.set_profile_scope(row["token"], ["work"])
    srv = host_server.Server(home=short_tmp)
    devices.register(srv)

    sent: list[dict] = []

    async def send(payload):
        sent.append(payload)

    body = {
        "id": "r", "method": "host.profile.detail",
        "params": {"auth_token": row["token"], "profile": "personal"},
    }
    await srv._handle_request(json.dumps(body), send, require_token=True)
    err = sent[0].get("error") or {}
    assert err.get("message") != "forbidden", sent[0]


@pytest.mark.asyncio
async def test_scope_gate_empty_scope_allows_everything(short_tmp: Path) -> None:
    row = devices.add(label="phone", role="member")
    srv = host_server.Server(home=short_tmp)
    devices.register(srv)

    sent: list[dict] = []

    async def send(payload):
        sent.append(payload)

    body = {
        "id": "r", "method": "host.profile.detail",
        "params": {"auth_token": row["token"], "profile": "anything"},
    }
    await srv._handle_request(json.dumps(body), send, require_token=True)
    err = sent[0].get("error") or {}
    assert err.get("message") != "forbidden", sent[0]


@pytest.mark.asyncio
async def test_generate_accepts_profiles_param(short_tmp: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "alpi.host.network.resolve_host_endpoint",
        lambda root: ("100.1.2.3", "tailscale"),
    )
    srv = host_server.Server(home=short_tmp)
    devices.register(srv)
    resp = await srv._dispatch({
        "id": "r", "method": "host.devices.generate",
        "params": {"label": "phone", "role": "member", "profiles": ["work"]},
    })
    assert resp["result"]["profile_scope"] == ["work"]
    row = next(d for d in devices.load() if d["token"] == resp["result"]["token"])
    assert row["profile_scope"] == ["work"]


@pytest.mark.asyncio
async def test_generate_admin_ignores_profiles_param(short_tmp: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "alpi.host.network.resolve_host_endpoint",
        lambda root: ("100.1.2.3", "tailscale"),
    )
    srv = host_server.Server(home=short_tmp)
    devices.register(srv)
    resp = await srv._dispatch({
        "id": "r", "method": "host.devices.generate",
        "params": {"label": "laptop", "role": "admin", "profiles": ["work"]},
    })
    assert resp["result"]["profile_scope"] == []
    row = next(d for d in devices.load() if d["token"] == resp["result"]["token"])
    assert row["profile_scope"] == []


@pytest.mark.asyncio
async def test_scope_filters_profile_summaries(short_tmp: Path, monkeypatch) -> None:
    row = devices.add(label="phone", role="member", profile_scope=["work"])
    monkeypatch.setattr(
        "alpi.host.device_state._profiles",
        lambda: [{"name": "work", "home": "/x"}, {"name": "personal", "home": "/y"}],
    )
    monkeypatch.setattr(
        "alpi.host.device_state._profile_summary",
        lambda p: {"name": p["name"]},
    )
    from alpi.host import device_state as ds
    srv = host_server.Server(home=short_tmp)
    ds.register(srv)

    sent: list[dict] = []
    async def send(payload):
        sent.append(payload)

    body = {
        "id": "r", "method": "host.profile.summaries",
        "params": {"auth_token": row["token"]},
    }
    await srv._handle_request(json.dumps(body), send, require_token=True)
    names = {p["name"] for p in sent[0]["result"]["profiles"]}
    assert names == {"work"}


@pytest.mark.asyncio
async def test_scope_filters_profiles_list(short_tmp: Path, monkeypatch) -> None:
    row = devices.add(label="phone", role="member", profile_scope=["work"])
    monkeypatch.setattr(
        "alpi.host.device_state._profiles",
        lambda: [{"name": "work"}, {"name": "personal"}],
    )
    from alpi.host import device_state as ds
    srv = host_server.Server(home=short_tmp)
    ds.register(srv)

    sent: list[dict] = []
    async def send(payload):
        sent.append(payload)

    # _profiles_list returns the raw list; only run if call works.
    body = {
        "id": "r", "method": "host.profiles.list",
        "params": {"auth_token": row["token"]},
    }
    await srv._handle_request(json.dumps(body), send, require_token=True)
    out = sent[0]["result"]["profiles"]
    if out and isinstance(out[0], dict):
        names = {p.get("name") for p in out}
    else:
        names = set(out)
    assert names == {"work"}


def test_filter_helper_drops_out_of_scope_event_frame() -> None:
    from alpi.host.server import _filter_payload_by_scope
    frame = {"event": "chat.turn_done", "data": {"profile": "personal"}, "at": 1, "seq": 5}
    assert _filter_payload_by_scope("host.events.subscribe", frame, ["work"]) is None


def test_filter_helper_passes_in_scope_event_frame() -> None:
    from alpi.host.server import _filter_payload_by_scope
    frame = {"event": "chat.turn_done", "data": {"profile": "work"}, "at": 1, "seq": 5}
    assert _filter_payload_by_scope("host.events.subscribe", frame, ["work"]) == frame


def test_filter_helper_drops_out_of_scope_history_events() -> None:
    from alpi.host.server import _filter_payload_by_scope
    payload = {"id": "r", "result": {"events": [
        {"event": "x", "data": {"profile": "work"}},
        {"event": "y", "data": {"profile": "personal"}},
        {"event": "z", "data": {}},  # no profile → not dropped
    ], "next_seq": 10}}
    out = _filter_payload_by_scope("host.events.history", payload, ["work"])
    kept = [e["event"] for e in out["result"]["events"]]
    assert kept == ["x", "z"]


def test_filter_helper_filters_workgroups_list() -> None:
    from alpi.host.server import _filter_payload_by_scope
    payload = {"id": "r", "result": {"workgroups": [
        {"id": "1", "profile": "work"},
        {"id": "2", "profile": "personal"},
    ]}}
    out = _filter_payload_by_scope("host.workgroups.list", payload, ["work"])
    assert [w["id"] for w in out["result"]["workgroups"]] == ["1"]


def test_filter_helper_filters_pending_requests() -> None:
    from alpi.host.server import _filter_payload_by_scope
    payload = {"id": "r", "result": {"requests": [
        {"id": "a", "profile": "work"},
        {"id": "b", "profile": "personal"},
    ]}}
    out = _filter_payload_by_scope("host.approval.pending", payload, ["work"])
    assert [r["id"] for r in out["result"]["requests"]] == ["a"]


# Pending-orphan pruning


def test_prune_orphans_removes_old_pending(short_tmp: Path) -> None:
    import time
    now = int(time.time())
    devices.save([
        {"token": "old-pending", "label": "pending", "created": now - 48*3600,
         "last_seen": None, "role": "member", "profile_scope": []},
        {"token": "fresh-pending", "label": "pending", "created": now - 60,
         "last_seen": None, "role": "member", "profile_scope": []},
        {"token": "real-device", "label": "iPhone", "created": now - 48*3600,
         "last_seen": now - 100, "role": "member", "profile_scope": []},
    ])
    dropped = devices.prune_orphans(now=now)
    assert dropped == 1
    surviving = {d["token"] for d in devices.load()}
    assert surviving == {"fresh-pending", "real-device"}


def test_prune_orphans_keeps_pending_that_did_pair(short_tmp: Path) -> None:
    import time
    now = int(time.time())
    devices.save([
        # label is still "pending" but last_seen IS set → device did connect once; keep it.
        {"token": "ghost", "label": "pending", "created": now - 48*3600,
         "last_seen": now - 10000, "role": "member", "profile_scope": []},
    ])
    assert devices.prune_orphans(now=now) == 0
    assert len(devices.load()) == 1


def test_prune_orphans_no_op_when_clean(short_tmp: Path) -> None:
    devices.add(label="Phone")
    assert devices.prune_orphans() == 0
    assert len(devices.load()) == 1


@pytest.mark.asyncio
async def test_list_verb_prunes_orphans_lazily(short_tmp: Path) -> None:
    import time
    now = int(time.time())
    devices.save([
        {"token": "orphan", "label": "pending", "created": now - 48*3600,
         "last_seen": None, "role": "member", "profile_scope": []},
        {"token": "iphone", "label": "iPhone", "created": now - 100,
         "last_seen": now - 10, "role": "member", "profile_scope": []},
    ])
    srv = host_server.Server(home=short_tmp)
    devices.register(srv)
    resp = await srv._dispatch({
        "id": "r", "method": "host.devices.list", "params": {},
    })
    labels = [d["label"] for d in resp["result"]["devices"]]
    assert labels == ["iPhone"]
    # Underlying store mutated, not just the response.
    assert len(devices.load()) == 1


@pytest.mark.asyncio
async def test_scoped_member_blocked_when_profile_missing(short_tmp: Path) -> None:
    row = devices.add(label="phone", role="member", profile_scope=["work"])
    srv = host_server.Server(home=short_tmp)
    devices.register(srv)

    sent: list[dict] = []
    async def send(payload):
        sent.append(payload)

    body = {
        "id": "r", "method": "host.profile.detail",
        "params": {"auth_token": row["token"]},  # no profile field!
    }
    await srv._handle_request(json.dumps(body), send, require_token=True)
    assert sent[0]["error"]["code"] == -32001
    assert "explicit profile" in sent[0]["error"]["data"]["detail"]


@pytest.mark.asyncio
async def test_scoped_member_blocked_when_profile_empty(short_tmp: Path) -> None:
    row = devices.add(label="phone", role="member", profile_scope=["work"])
    srv = host_server.Server(home=short_tmp)
    devices.register(srv)

    sent: list[dict] = []
    async def send(payload):
        sent.append(payload)

    body = {
        "id": "r", "method": "host.profile.detail",
        "params": {"auth_token": row["token"], "profile": ""},
    }
    await srv._handle_request(json.dumps(body), send, require_token=True)
    assert sent[0]["error"]["code"] == -32001


@pytest.mark.asyncio
async def test_scope_free_methods_allowed_for_scoped_member(short_tmp: Path) -> None:
    row = devices.add(label="phone", role="member", profile_scope=["work"])
    srv = host_server.Server(home=short_tmp)
    devices.register(srv)

    sent: list[dict] = []
    async def send(payload):
        sent.append(payload)

    body = {
        "id": "r", "method": "host.version",
        "params": {"auth_token": row["token"]},
    }
    await srv._handle_request(json.dumps(body), send, require_token=True)
    err = sent[0].get("error") or {}
    assert err.get("message") != "forbidden", sent[0]


@pytest.mark.asyncio
async def test_generate_rejects_invalid_profile_name(short_tmp: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "alpi.host.network.resolve_host_endpoint",
        lambda root: ("100.1.2.3", "tailscale"),
    )
    srv = host_server.Server(home=short_tmp)
    devices.register(srv)
    resp = await srv._dispatch({
        "id": "r", "method": "host.devices.generate",
        "params": {
            "label": "phone", "role": "member",
            "profiles": ["work", "bad name!"],
        },
    })
    assert resp["error"]["code"] == -32602
    assert "invalid profile name" in resp["error"]["data"]["detail"]
    assert devices.load() == []  # no device persisted


@pytest.mark.asyncio
async def test_generate_rejects_non_list_profiles(short_tmp: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "alpi.host.network.resolve_host_endpoint",
        lambda root: ("100.1.2.3", "tailscale"),
    )
    srv = host_server.Server(home=short_tmp)
    devices.register(srv)
    resp = await srv._dispatch({
        "id": "r", "method": "host.devices.generate",
        "params": {"label": "phone", "role": "member", "profiles": "work"},
    })
    assert resp["error"]["code"] == -32602


@pytest.mark.asyncio
async def test_set_profiles_rejects_invalid_profile_name(short_tmp: Path) -> None:
    row = devices.add(label="phone", role="member")
    srv = host_server.Server(home=short_tmp)
    devices.register(srv)
    resp = await srv._dispatch({
        "id": "r", "method": "host.devices.set_profiles",
        "params": {"token_id": row["token"][-8:], "profiles": ["bad name!"]},
    })
    assert resp["error"]["code"] == -32602
    # scope was not changed
    reloaded = next(d for d in devices.load() if d["token"] == row["token"])
    assert reloaded["profile_scope"] == []


@pytest.mark.asyncio
async def test_scoped_member_can_call_workgroups_list_filtered(
    short_tmp: Path, monkeypatch,
) -> None:
    row = devices.add(label="phone", role="member", profile_scope=["work"])
    monkeypatch.setattr(
        "alpi.host.device_state._aggregate_workgroups",
        lambda profile: [
            {"id": "1", "profile": "work", "name": "ops"},
            {"id": "2", "profile": "personal", "name": "home"},
        ],
    )
    from alpi.host import device_state as ds
    srv = host_server.Server(home=short_tmp)
    ds.register(srv)

    sent: list[dict] = []
    async def send(payload):
        sent.append(payload)

    body = {
        "id": "r", "method": "host.workgroups.list",
        "params": {"auth_token": row["token"], "profile": None},
    }
    await srv._handle_request(json.dumps(body), send, require_token=True)

    assert "error" not in sent[0]
    rows = sent[0]["result"]["workgroups"]
    assert {w["id"] for w in rows} == {"1"}


@pytest.mark.asyncio
async def test_scoped_member_can_call_tools_list(short_tmp: Path) -> None:
    row = devices.add(label="phone", role="member", profile_scope=["work"])
    from alpi.host import tools as tools_mod
    srv = host_server.Server(home=short_tmp)
    tools_mod.register(srv)

    sent: list[dict] = []
    async def send(payload):
        sent.append(payload)

    body = {
        "id": "r", "method": "host.tools.list",
        "params": {"auth_token": row["token"]},
    }
    await srv._handle_request(json.dumps(body), send, require_token=True)

    assert "error" not in sent[0]
    assert isinstance(sent[0]["result"]["tools"], list)


@pytest.mark.asyncio
async def test_network_status_stays_local_only_for_remote_token(
    short_tmp: Path,
) -> None:
    # host.network.status is in _LOCAL_ONLY_METHODS; HOST.1 must not promote it through the scope-free allowlist.
    row = devices.add(label="phone", role="member")
    srv = host_server.Server(home=short_tmp)

    sent: list[dict] = []
    async def send(payload):
        sent.append(payload)

    body = {
        "id": "r", "method": "host.network.status",
        "params": {"auth_token": row["token"]},
    }
    await srv._handle_request(json.dumps(body), send, require_token=True)
    assert sent[0]["error"]["code"] == -32001
    assert sent[0]["error"]["data"]["detail"] == "method is local-only"


@pytest.mark.asyncio
async def test_profile_detail_redacts_settings_fields_for_member(
    short_tmp: Path,
) -> None:
    row = devices.add(label="phone", role="member")
    srv = host_server.Server(home=short_tmp)

    async def handler(_params, _server):
        return {
            "models": ["openrouter/anthropic/claude-3-opus"],
            "voice_id": "shimmer",
            "workspace": "/secret/workspace",
            "advertise_host": "10.0.0.1",
            "provider_keys": {"OPENAI": "sk-…"},
            "mcps": [{"name": "fs"}],
            "peers": [{"id": "@partner"}],
            "sandbox": "deny",
        }

    srv.register("host.profile.detail", handler)

    sent: list[dict] = []
    async def send(p): sent.append(p)
    body = {
        "id": "r", "method": "host.profile.detail",
        "params": {"auth_token": row["token"], "profile": "x"},
    }
    await srv._handle_request(json.dumps(body), send, require_token=True)

    assert "error" not in sent[0]
    result = sent[0]["result"]
    assert set(result.keys()) == {"models", "voice_id"}
    assert result["models"] == ["openrouter/anthropic/claude-3-opus"]
    assert result["voice_id"] == "shimmer"


@pytest.mark.asyncio
async def test_profile_detail_full_for_admin(short_tmp: Path) -> None:
    row = devices.add(label="laptop", role="admin")
    srv = host_server.Server(home=short_tmp)

    async def handler(_params, _server):
        return {
            "models": ["m"],
            "voice_id": "shimmer",
            "workspace": "/secret/workspace",
            "provider_keys": {"OPENAI": "sk-…"},
            "peers": [{"id": "@partner"}],
        }

    srv.register("host.profile.detail", handler)

    sent: list[dict] = []
    async def send(p): sent.append(p)
    body = {
        "id": "r", "method": "host.profile.detail",
        "params": {"auth_token": row["token"], "profile": "x"},
    }
    await srv._handle_request(json.dumps(body), send, require_token=True)

    result = sent[0]["result"]
    assert "workspace" in result
    assert "provider_keys" in result
    assert "peers" in result


@pytest.mark.asyncio
async def test_ollama_models_callable_by_scoped_member(short_tmp: Path) -> None:
    # Chat needs runtime model switching, so ollama_models is intentionally NOT in _ADMIN_METHODS. Scoped members still go through the per-call scope gate (host.providers.ollama_models takes a `profile` param).
    row = devices.add(label="phone", role="member", profile_scope=["work"])
    srv = host_server.Server(home=short_tmp)

    async def handler(_params, _server):
        return {"models": ["llama3:8b"], "errors": []}

    srv.register("host.providers.ollama_models", handler)

    sent: list[dict] = []
    async def send(p): sent.append(p)

    # In-scope: allowed
    body_ok = {
        "id": "ok", "method": "host.providers.ollama_models",
        "params": {"auth_token": row["token"], "profile": "work"},
    }
    await srv._handle_request(json.dumps(body_ok), send, require_token=True)
    assert "error" not in sent[0]
    assert sent[0]["result"]["models"] == ["llama3:8b"]

    # Out-of-scope: forbidden by HOST.1 gate
    body_blocked = {
        "id": "blocked", "method": "host.providers.ollama_models",
        "params": {"auth_token": row["token"], "profile": "secret"},
    }
    await srv._handle_request(json.dumps(body_blocked), send, require_token=True)
    assert sent[1]["error"]["code"] == -32001
    assert sent[1]["error"]["data"]["detail"] == "profile not in device scope"
