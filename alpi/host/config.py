from __future__ import annotations

import asyncio
import re
import time
from pathlib import Path
from typing import Any

from alpi import config as cfg_mod
from alpi.home import RESERVED_PROFILE_NAMES
from alpi.host import server as host_server


_ENV_KEY_RE = re.compile(r"^[A-Z_][A-Z0-9_]{0,63}$")
_PROTECTED_ENV_KEYS = frozenset({
    "HOME", "PATH", "USER", "ALPI_HOME", "ALPI_PROFILE",
    "PYTHONPATH", "TMPDIR", "LANG", "LC_ALL",
})

__all__ = ["RESERVED_PROFILE_NAMES"]


def _check_env_key(key: str) -> str:
    key = (key or "").strip()
    if not _ENV_KEY_RE.match(key):
        raise host_server.HandlerError(
            -32602, "invalid-params",
            data={"detail": "key must match [A-Z_][A-Z0-9_]* (max 64 chars)"},
        )
    if key in _PROTECTED_ENV_KEYS:
        raise host_server.HandlerError(
            -32001, "forbidden",
            data={"detail": f"{key!r} is reserved and cannot be touched"},
        )
    return key


def register(server: host_server.Server) -> None:
    server.register("host.providers.set_key", _providers_set_key)
    server.register("host.providers.unset_key", _providers_unset_key)
    server.register("host.providers.add_ollama", _providers_add_ollama)
    server.register("host.providers.remove_ollama", _providers_remove_ollama)
    server.register(
        "host.providers.add_openrouter_model", _providers_add_or_model,
    )
    server.register(
        "host.providers.remove_openrouter_model", _providers_remove_or_model,
    )
    server.register("host.peers.add", _peers_add)
    server.register("host.peers.remove", _peers_remove)
    server.register("host.peers.pending_list", _peers_pending_list)
    server.register("host.peers.pending_accept", _peers_pending_accept)
    server.register("host.peers.pending_discard", _peers_pending_discard)
    server.register("host.profile.create", _profile_create)
    server.register("host.profile.delete", _profile_delete)
    server.register("host.identity.draft", _identity_draft)
    server.register("host.mcp.add", _mcp_add)
    server.register("host.mcp.remove", _mcp_remove)
    server.register("host.mcp.tools", _mcp_tools)
    server.register("host.email.add", _email_add)
    server.register("host.email.remove", _email_remove)
    server.register("host.email.gmail.begin", _gmail_begin)
    server.register("host.email.gmail.exchange", _gmail_exchange)
    server.register("host.sandbox.set", _sandbox_set)
    server.register("host.sandbox.network", _sandbox_network)
    server.register("host.voice.set_voice", _voice_set_voice)
    server.register("host.voice.set_auto_read", _voice_set_auto_read)
    server.register("host.voice.preview", _voice_preview)
    server.register("host.voice.script", _voice_script)


def _resolve_home(profile: str) -> Path:
    from alpi.host.handlers import _resolve_home as _r
    return _r(profile)


def _params(d: dict[str, Any], *keys: str) -> tuple[Any, ...]:
    return tuple(d.get(k) for k in keys)


def _emit_config_changed(home: Path, scope: str) -> None:
    """Notify subscribers that this profile's config (cfg.yaml or .env) changed. Lazy-imported to keep `alpi.host.config` importable in contexts without an event bus."""
    from alpi import home as home_mod
    from alpi.host import device_state
    from alpi.host import events as host_events
    profile = home_mod.profile_name(home)
    # Drop the cached summary BEFORE the event, or the reload it triggers re-reads the stale one.
    device_state.invalidate_summary(profile)
    host_events.emit("config_changed", {"profile": profile, "scope": scope})


def _emit_email_changed(home: Path, account_id: str, action: str) -> None:
    from alpi import home as home_mod
    from alpi.host import events as host_events
    host_events.emit("email_changed", {
        "profile": home_mod.profile_name(home),
        "id": account_id,
        "action": action,
    })


def _emit_peers_changed(home: Path, action: str, peer_id: str = "") -> None:
    from alpi import home as home_mod
    from alpi.host import events as host_events
    host_events.emit("peers_changed", {
        "profile": home_mod.profile_name(home),
        "action": action,
        "peer_id": peer_id,
    })


def _emit_profile_changed(name: str, action: str) -> None:
    from alpi.host import device_state
    from alpi.host import events as host_events
    device_state.invalidate_summary()
    host_events.emit("profile_changed", {
        "profile": name,
        "action": action,
    })


async def _providers_set_key(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    from alpi.model_selector import _append_env

    profile, key, value = _params(params, "profile", "key", "value")
    if value is None:
        raise host_server.HandlerError(
            -32602, "invalid-params", data={"detail": "value required"},
        )
    key = _check_env_key(str(key or ""))
    value_str = str(value)
    if "\n" in value_str or "\r" in value_str:
        raise host_server.HandlerError(
            -32602, "invalid-params",
            data={"detail": "value must not contain newlines"},
        )
    home = _resolve_home(str(profile or ""))
    cfg = cfg_mod.load(home)
    _append_env(cfg.env_path, key, value_str)
    if _is_email_env_key(key):
        _emit_email_changed(home, key, "configured")
    else:
        _emit_config_changed(home, scope="env")
    return {"ok": True}


async def _providers_unset_key(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    from alpi.model_selector import unset_provider_key

    profile, key = _params(params, "profile", "key")
    key = _check_env_key(str(key or ""))
    home = _resolve_home(str(profile or ""))
    cfg = cfg_mod.load(home)
    model_cleared = unset_provider_key(cfg, key)
    if _is_email_env_key(key):
        _emit_email_changed(home, key, "cleared")
    else:
        _emit_config_changed(home, scope="env")
    return {"ok": True, "model_cleared": model_cleared}


async def _providers_add_ollama(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    profile, name, url = _params(params, "profile", "name", "url")
    if not name or not url:
        raise host_server.HandlerError(
            -32602, "invalid-params", data={"detail": "name and url required"},
        )
    name = str(name).strip()
    url = str(url).strip().rstrip("/")
    home = _resolve_home(str(profile or ""))
    cfg = cfg_mod.load(home)
    taken = {e.get("name") for e in cfg.providers.get("ollama", []) or []}
    if name in taken:
        raise host_server.HandlerError(
            -32008, "name-taken",
            data={"detail": f"ollama server {name!r} already exists"},
        )
    cfg.providers.setdefault("ollama", []).append({"name": name, "url": url})
    cfg_mod.save(cfg)
    _emit_config_changed(home, scope="providers")
    return {"ok": True}


async def _providers_remove_ollama(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    profile, name = _params(params, "profile", "name")
    home = _resolve_home(str(profile or ""))
    cfg = cfg_mod.load(home)
    items = cfg.providers.get("ollama", []) or []
    keep = [e for e in items if e.get("name") != name]
    if len(keep) == len(items):
        raise host_server.HandlerError(
            -32004, "not-found", data={"detail": f"no ollama server {name!r}"},
        )
    cfg.providers["ollama"] = keep
    model_cleared = bool(name) and cfg.model.startswith(f"{name}/")
    if model_cleared:
        cfg.model = ""
    cfg_mod.save(cfg)
    _emit_config_changed(home, scope="providers")
    return {"ok": True, "model_cleared": model_cleared}


async def _providers_add_or_model(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    profile, model = _params(params, "profile", "model")
    suffix = str(model or "").strip()
    if suffix.startswith("openrouter/"):
        suffix = suffix.split("/", 1)[1]
    if not suffix:
        raise host_server.HandlerError(
            -32602, "invalid-params", data={"detail": "model required"},
        )
    home = _resolve_home(str(profile or ""))
    cfg = cfg_mod.load(home)
    or_cfg = cfg.providers.setdefault("openrouter", {})
    models = or_cfg.setdefault("models", [])
    if suffix in models:
        models.remove(suffix)
    models.insert(0, suffix)
    cfg_mod.save(cfg)
    _emit_config_changed(home, scope="providers")
    return {"ok": True}


async def _providers_remove_or_model(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    profile, model = _params(params, "profile", "model")
    suffix = str(model or "").strip()
    if suffix.startswith("openrouter/"):
        suffix = suffix.split("/", 1)[1]
    home = _resolve_home(str(profile or ""))
    cfg = cfg_mod.load(home)
    or_cfg = cfg.providers.get("openrouter") or {}
    models = list(or_cfg.get("models") or [])
    if suffix not in models:
        raise host_server.HandlerError(
            -32004, "not-found", data={"detail": f"no openrouter model {suffix!r}"},
        )
    models.remove(suffix)
    or_cfg["models"] = models
    cfg.providers["openrouter"] = or_cfg
    cfg_mod.save(cfg)
    _emit_config_changed(home, scope="providers")
    return {"ok": True}


async def _peers_add(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    from alpi.alp import peers as peers_mod

    profile = str(params.get("profile") or "")
    peer_id = str(params.get("id") or "").strip()
    pubkey = str(params.get("pubkey") or "").strip()
    address = params.get("address")
    allow = params.get("allow") or ["link.ping", "link.ask"]
    if not peer_id or not pubkey:
        raise host_server.HandlerError(
            -32602, "invalid-params", data={"detail": "id and pubkey required"},
        )
    home = _resolve_home(profile)
    peer = peers_mod.Peer(
        id=peer_id,
        pubkey=pubkey,
        address=str(address) if address else None,
        allow=list(allow),
    )
    peers_mod.add(home, peer)
    _emit_peers_changed(home, "added", peer_id)
    return {"ok": True}


async def _peers_remove(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    from alpi.alp import peers as peers_mod

    profile = str(params.get("profile") or "")
    peer_id = str(params.get("id") or "").strip()
    if not peer_id:
        raise host_server.HandlerError(
            -32602, "invalid-params", data={"detail": "id required"},
        )
    home = _resolve_home(profile)
    existed = peers_mod.remove(home, peer_id)
    if existed:
        _emit_peers_changed(home, "removed", peer_id)
    return {"ok": True, "existed": existed}


async def _peers_pending_list(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    from alpi.alp import pending as pending_mod

    home = _resolve_home(str(params.get("profile") or ""))
    rows = pending_mod.to_dicts(pending_mod.load(home))
    locals_by_pubkey = _local_profile_pubkeys()
    for row in rows:
        match = locals_by_pubkey.get(row.get("pubkey", ""))
        if match:
            row["local_profile"] = match
    return {"pending": rows}


def _local_profile_pubkeys() -> dict[str, str]:
    # Read-only — never load_or_generate; that would materialise ALP secrets from a pending_list lookup.
    from alpi import home as home_mod
    from alpi.alp import keys as keys_mod

    out: dict[str, str] = {}
    root = home_mod._ROOT
    if keys_mod.exists(root):
        try:
            out[keys_mod.load(root).pubkey_b64()] = "default"
        except Exception:  # noqa: BLE001
            pass
    profiles_root = root / "profiles"
    if profiles_root.exists():
        for prof_dir in profiles_root.iterdir():
            if not prof_dir.is_dir() or not keys_mod.exists(prof_dir):
                continue
            try:
                out[keys_mod.load(prof_dir).pubkey_b64()] = prof_dir.name
            except Exception:  # noqa: BLE001
                continue
    return out


async def _peers_pending_accept(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    from alpi.alp import peers as peers_mod
    from alpi.alp import pending as pending_mod

    profile = str(params.get("profile") or "")
    pubkey = str(params.get("pubkey") or "").strip()
    peer_id = str(params.get("id") or "").strip()
    allow = params.get("allow") or ["link.ping", "link.ask"]
    if not pubkey or not peer_id:
        raise host_server.HandlerError(
            -32602, "invalid-params", data={"detail": "id and pubkey required"},
        )
    home = _resolve_home(profile)
    entries = pending_mod.load(home)
    match = next((e for e in entries if e.pubkey == pubkey), None)
    if match is None:
        raise host_server.HandlerError(
            -32004, "not-found", data={"detail": "pubkey not in pending list"},
        )
    address = params.get("address") or match.address
    peer = peers_mod.Peer(
        id=peer_id,
        pubkey=pubkey,
        address=str(address) if address else None,
        allow=list(allow),
    )
    peers_mod.add(home, peer)
    pending_mod.remove(home, pubkey)
    _emit_peers_changed(home, "accepted", peer_id)
    return {"ok": True}


async def _peers_pending_discard(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    from alpi.alp import pending as pending_mod

    home = _resolve_home(str(params.get("profile") or ""))
    pubkey = str(params.get("pubkey") or "").strip()
    if not pubkey:
        raise host_server.HandlerError(
            -32602, "invalid-params", data={"detail": "pubkey required"},
        )
    existed = pending_mod.remove(home, pubkey)
    if existed:
        _emit_peers_changed(home, "discarded")
    return {"ok": True, "existed": existed}


async def _profile_create(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    from alpi import home as home_mod
    from alpi.cli import _bootstrap

    name = str(params.get("name") or "")
    if not name:
        raise host_server.HandlerError(
            -32602, "invalid-params",
            data={"detail": "name required"},
        )
    try:
        home_mod.validate_profile_name(name)
    except home_mod.InvalidProfileName as e:
        raise host_server.HandlerError(
            -32602, "invalid-params", data={"detail": str(e)},
        )
    h = home_mod.home_for(name)
    if h.exists() and any(h.iterdir()):
        raise host_server.HandlerError(
            -32008, "name-taken",
            data={"detail": f"profile {name!r} already exists"},
        )
    _bootstrap(h)
    _emit_profile_changed(name, "created")
    return {"ok": True, "home": str(h)}


async def _identity_draft(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    import asyncio

    from alpi import config as config_mod
    from alpi import home as home_mod
    from alpi import identity

    name = str(params.get("profile") or "").strip()
    if not name:
        raise host_server.HandlerError(
            -32602, "invalid-params", data={"detail": "profile required"},
        )
    h = home_mod.home_for(name)
    if not h.exists():
        raise host_server.HandlerError(
            -32004, "not-found", data={"detail": f"no profile {name!r}"},
        )
    cfg = config_mod.load(h)
    try:
        bio = await asyncio.to_thread(identity.draft_bio_from_agent, h, cfg)
    except ValueError as e:
        raise host_server.HandlerError(
            -32010, "draft-failed", data={"detail": str(e)},
        )
    except Exception as e:  # noqa: BLE001
        raise host_server.HandlerError(
            -32010, "draft-failed", data={"detail": f"draft failed: {e}"},
        )
    return {"bio": bio}


async def _profile_delete(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    import time as _time

    name = str(params.get("name") or "").strip()
    force = bool(params.get("force", False))
    if not name or name == "default":
        raise host_server.HandlerError(
            -32602, "invalid-params",
            data={"detail": "the default profile cannot be removed"},
        )
    from alpi import home as home_mod
    h = home_mod.home_for(name)
    if not h.exists() or not h.is_dir():
        raise host_server.HandlerError(
            -32004, "not-found", data={"detail": f"no profile {name!r}"},
        )
    # Guard against resolution outside ``profiles/``.
    profiles_root = home_mod._ROOT / "profiles"
    if h.parent.resolve() != profiles_root.resolve():
        raise host_server.HandlerError(
            -32602, "invalid-params",
            data={"detail": f"refusing to archive {h} — not under {profiles_root}"},
        )
    # The daemon is one-per-machine; ``force`` is a legacy flag from
    # the per-profile install era and now has nothing to do — the
    # daemon picks up the change on its next restart.
    _ = force
    # Archive instead of deleting in place.
    trash_root = home_mod._ROOT / ".trash"
    trash_root.mkdir(parents=True, exist_ok=True)
    stamp = _time.strftime("%Y%m%d-%H%M%S")
    archived = trash_root / f"{name}-{stamp}"
    h.rename(archived)
    _emit_profile_changed(name, "deleted")
    return {"ok": True, "archived_at": str(archived)}


async def _mcp_add(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    name = str(params.get("name") or "").strip()
    command = str(params.get("command") or "").strip()
    args = list(params.get("args") or [])
    env = dict(params.get("env") or {})
    if not name or ":" in name or "/" in name or name.startswith("."):
        raise host_server.HandlerError(
            -32602, "invalid-params", data={"detail": f"invalid name {name!r}"},
        )
    if not command:
        raise host_server.HandlerError(
            -32602, "invalid-params", data={"detail": "command required"},
        )
    home = _resolve_home(str(params.get("profile") or ""))
    cfg = cfg_mod.load(home)
    cfg.raw.setdefault("mcp", {}).setdefault("servers", {})[name] = {
        "command": command,
        "args": [str(a) for a in args],
        "env": {str(k): str(v) for k, v in env.items()},
    }
    cfg_mod.save(cfg)
    _emit_config_changed(home, scope="mcp")
    return {"ok": True}


async def _mcp_remove(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    name = str(params.get("name") or "").strip()
    home = _resolve_home(str(params.get("profile") or ""))
    cfg = cfg_mod.load(home)
    servers = cfg.raw.get("mcp", {}).get("servers", {}) or {}
    if name not in servers:
        raise host_server.HandlerError(
            -32004, "not-found", data={"detail": f"no MCP {name!r}"},
        )
    del servers[name]
    cfg.raw["mcp"]["servers"] = servers
    cfg_mod.save(cfg)
    _emit_config_changed(home, scope="mcp")
    return {"ok": True}


async def _mcp_tools(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    name = str(params.get("name") or "").strip()
    home = _resolve_home(str(params.get("profile") or ""))
    cfg = cfg_mod.load(home)
    spec = ((cfg.raw.get("mcp") or {}).get("servers") or {}).get(name)
    if not spec:
        raise host_server.HandlerError(
            -32004, "not-found", data={"detail": f"no MCP {name!r}"},
        )

    from alpi.home import effective_profile_env
    from alpi.mcp.client import MCPClient, MCPError

    def _probe() -> list[dict[str, Any]]:
        client = MCPClient(
            name=name,
            command=str(spec.get("command") or ""),
            args=[str(a) for a in (spec.get("args") or [])],
            env={str(k): str(v) for k, v in (spec.get("env") or {}).items()},
            env_base=effective_profile_env(home),
        )
        client.start(timeout=10.0)
        try:
            return [
                {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.input_schema,
                }
                for t in client.list_tools()
            ]
        finally:
            client.stop()

    try:
        tools = await asyncio.to_thread(_probe)
    except MCPError as e:
        raise host_server.HandlerError(
            -32603, "internal-error", data={"detail": str(e)},
        ) from e
    return {"server": name, "tools": tools}


def _is_email_env_key(key: str) -> bool:
    return key.startswith("EMAIL__") or key in ("GMAIL_CLIENT_ID", "GMAIL_CLIENT_SECRET")


# In-memory pending OAuth handles, keyed by ``state``. The verifier is
# the PKCE secret — it lives only on the daemon between begin/exchange.
# A daemon restart between the two clears them (TTL-bounded anyway), so
# the client must restart the flow; that's preferable to persisting a
# secret blob across restarts for a 5-minute window.
_GMAIL_BEGIN_TTL = 300
_pending_gmail: dict[str, dict[str, Any]] = {}


def _gc_pending_gmail() -> None:
    now = time.time()
    expired = [
        s for s, rec in _pending_gmail.items() if now - rec["created"] > _GMAIL_BEGIN_TTL
    ]
    for s in expired:
        _pending_gmail.pop(s, None)


def _validate_loopback_redirect_uri(uri: str) -> None:
    """Reject anything that isn't a loopback http URI.

    Google's "Desktop app" OAuth client only accepts loopback redirect
    targets, and we want to mirror that contract on the daemon side —
    if a future client sneaks in a non-loopback URI, the token would
    end up at someone else's HTTP endpoint. Cheap guardrail."""
    from urllib.parse import urlparse
    try:
        parsed = urlparse(uri)
    except ValueError as exc:
        raise host_server.HandlerError(
            -32602, "invalid-params",
            data={"detail": f"redirect_uri unparseable: {exc}"},
        )
    if parsed.scheme != "http":
        raise host_server.HandlerError(
            -32602, "invalid-params",
            data={"detail": "redirect_uri scheme must be http (loopback)"},
        )
    if parsed.hostname not in ("127.0.0.1", "localhost"):
        raise host_server.HandlerError(
            -32602, "invalid-params",
            data={"detail": "redirect_uri host must be 127.0.0.1 or localhost"},
        )
    try:
        port = parsed.port
    except ValueError:
        port = None
    if port is None or not (1 <= port <= 65535):
        raise host_server.HandlerError(
            -32602, "invalid-params",
            data={"detail": "redirect_uri must specify a valid port"},
        )


async def _gmail_begin(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    """Persist Gmail OAuth credentials and start a consent flow.

    The client supplies its own ``redirect_uri`` — typically a
    loopback on the **client machine**, where the browser actually
    runs. The daemon stashes the PKCE verifier under ``state`` until
    ``host.email.gmail.exchange`` comes back with the code."""
    from alpi.mail import gmail_auth
    from alpi.model_selector import _append_env

    home = _resolve_home(str(params.get("profile") or ""))
    cfg = cfg_mod.load(home)
    existing = _read_env_file(cfg.env_path)

    client_id = str(params.get("client_id") or "").strip() or existing.get("GMAIL_CLIENT_ID", "")
    client_secret = (
        str(params.get("client_secret") or "").strip()
        or existing.get("GMAIL_CLIENT_SECRET", "")
    )
    address = str(params.get("address") or "").strip()
    redirect_uri = str(params.get("redirect_uri") or "").strip()
    if not redirect_uri:
        raise host_server.HandlerError(
            -32602, "invalid-params",
            data={"detail": "redirect_uri is required (client-side loopback URL)"},
        )
    _validate_loopback_redirect_uri(redirect_uri)

    if not client_id or not client_secret:
        raise host_server.HandlerError(
            -32602, "invalid-params",
            data={"detail": "client_id and client_secret are required"},
        )

    for key, val in (
        ("GMAIL_CLIENT_ID", client_id),
        ("GMAIL_CLIENT_SECRET", client_secret),
    ):
        _append_env(cfg.env_path, key, val)

    _gc_pending_gmail()
    try:
        handle = gmail_auth.prepare(home, redirect_uri=redirect_uri)
    except gmail_auth.GmailAuthError as exc:
        raise host_server.HandlerError(
            -32603, "internal", data={"detail": str(exc)},
        )
    _pending_gmail[handle.state] = {
        "code_verifier": handle.code_verifier,
        "redirect_uri": handle.redirect_uri,
        "home": home,
        "address": address,
        "created": time.time(),
    }
    return {"auth_url": handle.auth_url, "state": handle.state}


async def _gmail_exchange(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    """Finalize the consent flow. The client posts ``state`` + ``code`` it
    captured from its own loopback redirect."""
    from alpi.mail import gmail_auth

    state = str(params.get("state") or "").strip()
    code = str(params.get("code") or "").strip()
    if not state or not code:
        raise host_server.HandlerError(
            -32602, "invalid-params",
            data={"detail": "state and code are required"},
        )

    _gc_pending_gmail()
    record = _pending_gmail.pop(state, None)
    if record is None:
        raise host_server.HandlerError(
            -32602, "invalid-params",
            data={"detail": "unknown or expired state — restart the auth flow"},
        )

    from alpi.mail import accounts as accounts_mod

    home: Path = record["home"]
    address = str(record.get("address") or "")
    account_id = accounts_mod.slug(address) if address else ""
    try:
        token = gmail_auth.exchange(
            home,
            account_id,
            code=code,
            code_verifier=record["code_verifier"],
            redirect_uri=record["redirect_uri"],
        )
    except gmail_auth.GmailAuthError as exc:
        raise host_server.HandlerError(
            -32603, "internal", data={"detail": str(exc)},
        )
    token_email = (token.email or "").strip()
    # Google authorizes whatever account the user picked in the browser, not necessarily the typed address — refuse the mismatch and wipe the token written under the requested id so config never points at the wrong inbox.
    if address and token_email and token_email.lower() != address.lower():
        try:
            accounts_mod.gmail_token_path(home, account_id).unlink()
        except OSError:
            pass
        raise host_server.HandlerError(
            -32602, "invalid-params",
            data={"detail": (
                f"authorized {token_email!r} but you asked to add {address!r} — "
                "token discarded; restart and sign in with the matching account"
            )},
        )
    final_address = address or token_email
    account_id = account_id or accounts_mod.slug(token_email)
    if account_id:
        try:
            accounts_mod.add_gmail(home, address=final_address)
        except ValueError as e:
            try:
                accounts_mod.gmail_token_path(home, account_id).unlink()
            except OSError:
                pass
            raise host_server.HandlerError(
                -32602, "invalid-params", data={"detail": str(e)},
            )
    _emit_email_changed(home, account_id, "authorized")
    return {"id": account_id, "email": token.email}


def _read_env_file(env_path: Path) -> dict[str, str]:
    if not env_path.exists():
        return {}
    out: dict[str, str] = {}
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        out[key.strip()] = value.strip()
    return out


async def _email_add(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    from alpi.mail import accounts as accounts_mod

    address = str(params.get("address") or "").strip()
    password = str(params.get("password") or "")
    imap_host = str(params.get("imap_host") or "").strip()
    smtp_host = str(params.get("smtp_host") or "").strip()
    if not address or not imap_host or not smtp_host:
        raise host_server.HandlerError(
            -32602, "invalid-params",
            data={"detail": "address, imap_host, smtp_host are required"},
        )
    home = _resolve_home(str(params.get("profile") or ""))
    # Empty password is fine on an edit (preserve the stored one); a new account must set one.
    if not password and accounts_mod.get_account(home, accounts_mod.slug(address)) is None:
        raise host_server.HandlerError(
            -32602, "invalid-params",
            data={"detail": "password is required for a new account"},
        )
    try:
        account_id = accounts_mod.add_imap(
            home,
            address=address,
            password=password,
            imap_host=imap_host,
            smtp_host=smtp_host,
            imap_port=_email_port(params.get("imap_port"), 993),
            smtp_port=_email_port(params.get("smtp_port"), 587),
        )
    except (ValueError, TypeError) as e:
        raise host_server.HandlerError(
            -32602, "invalid-params", data={"detail": str(e)},
        )
    _emit_email_changed(home, account_id, "configured")
    return {"ok": True, "id": account_id}


async def _email_remove(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    from alpi.mail import accounts as accounts_mod

    account_id = str(params.get("id") or "").strip()
    if not accounts_mod.valid_id(account_id):
        raise host_server.HandlerError(
            -32602, "invalid-params", data={"detail": "valid account id required"},
        )
    home = _resolve_home(str(params.get("profile") or ""))
    existed = accounts_mod.remove_account(home, account_id)
    _emit_email_changed(home, account_id, "removed")
    return {"ok": True, "existed": existed}


def _email_port(value: Any, default: int) -> int:
    if value is None or value == "":
        return default
    port = int(value)
    if not (1 <= port <= 65535):
        raise ValueError(f"port out of range (1-65535): {port}")
    return port


def _bool_state(params: dict[str, Any]) -> bool:
    state = str(params.get("state") or "").strip().lower()
    if state not in ("on", "off"):
        raise host_server.HandlerError(
            -32602, "invalid-params", data={"detail": "state must be 'on' or 'off'"},
        )
    return state == "on"


async def _sandbox_set(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    on = _bool_state(params)
    home = _resolve_home(str(params.get("profile") or ""))
    cfg = cfg_mod.load(home)
    cfg.tools.terminal.sandbox = on
    if not on:
        # ``allow_network`` is meaningless without sandbox.
        cfg.tools.terminal.allow_network = False
    cfg_mod.save(cfg)
    _emit_config_changed(home, scope="sandbox")
    return {"ok": True}


async def _sandbox_network(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    on = _bool_state(params)
    home = _resolve_home(str(params.get("profile") or ""))
    cfg = cfg_mod.load(home)
    if not cfg.tools.terminal.sandbox:
        raise host_server.HandlerError(
            -32008, "precondition-failed",
            data={"detail": "sandbox must be enabled first"},
        )
    cfg.tools.terminal.allow_network = on
    cfg_mod.save(cfg)
    _emit_config_changed(home, scope="sandbox")
    return {"ok": True}


async def _voice_set_voice(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    voice_id = str(params.get("voice_id") or "").strip()
    if not voice_id:
        raise host_server.HandlerError(
            -32602, "invalid-params", data={"detail": "voice_id required"},
        )
    home = _resolve_home(str(params.get("profile") or ""))
    cfg = cfg_mod.load(home)
    cfg.tools.tts.voice = voice_id
    cfg_mod.save(cfg)
    _emit_config_changed(home, scope="voice")
    return {"ok": True}


async def _voice_set_auto_read(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    home = _resolve_home(str(params.get("profile") or ""))
    cfg = cfg_mod.load(home)
    cfg.tools.tts.auto_read = bool(params.get("enabled"))
    cfg_mod.save(cfg)
    _emit_config_changed(home, scope="voice")
    return {"ok": True}


# Localized "Hello, I am Alpi" greetings used for the preview sample. Lang prefix
# is the bit before the first `-` in the Azure voice id (`es-MX-DaliaNeural` → `es`).
_PREVIEW_PHRASES = {
    "en": "Hi, I'm Alpi.",
    "es": "Hola, soy Alpi.",
    "fr": "Bonjour, je suis Alpi.",
    "de": "Hallo, ich bin Alpi.",
    "it": "Ciao, sono Alpi.",
    "pt": "Olá, sou Alpi.",
}


def _preview_phrase_for(voice_id: str) -> str:
    head = (voice_id or "").split("-", 1)[0].lower()
    return _PREVIEW_PHRASES.get(head, _PREVIEW_PHRASES["en"])


_VOICE_PREVIEW_MAX_CHARS = 700  # must fit voice.SCRIPT_MAX_CHARS scripts; still a DoS guard against multi-MB base64 replies.


async def _voice_preview(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    """Synthesize a short Azure voice greeting and return base64-mp3. Stateless — no on-disk cache."""
    import base64
    import tempfile

    try:
        import edge_tts  # noqa: F401  (lazy import — keeps the daemon cold path light)
    except ImportError as e:
        raise host_server.HandlerError(
            -32000, "tts-unavailable",
            data={"detail": f"edge_tts not installed: {e}"},
        ) from e

    voice_id = str((params or {}).get("voice_id") or "").strip()
    if not voice_id:
        raise host_server.HandlerError(
            -32602, "invalid-params", data={"detail": "voice_id required"},
        )
    text = str((params or {}).get("text") or "").strip() or _preview_phrase_for(voice_id)
    if len(text) > _VOICE_PREVIEW_MAX_CHARS:
        # DoS guard: an oversized text would ship multi-MB of base64 back over the socket.
        raise host_server.HandlerError(
            -32602, "invalid-params",
            data={"detail": f"text exceeds {_VOICE_PREVIEW_MAX_CHARS} chars"},
        )

    # Write to a tmp file then read back — keeps the existing edge_tts helper
    # API stable (it's a file-based interface) without coupling to the agent's
    # cache directory layout.
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        out_path = tmp.name
    try:
        from alpi.tools.tts import _synthesize  # reuse the same helper the agent uses

        try:
            await _synthesize(text, voice_id, Path(out_path))
        except Exception as e:  # noqa: BLE001
            raise host_server.HandlerError(
                -32000, "tts-failed", data={"detail": str(e) or e.__class__.__name__},
            ) from e
        try:
            audio_bytes = Path(out_path).read_bytes()
        except OSError as e:
            raise host_server.HandlerError(
                -32603, "internal-error", data={"detail": f"read mp3: {e}"},
            ) from e
    finally:
        try:
            Path(out_path).unlink(missing_ok=True)
        except OSError:
            pass

    return {
        "voice_id": voice_id,
        "text": text,
        "audio_b64": base64.b64encode(audio_bytes).decode("ascii"),
        "mime": "audio/mpeg",
    }


async def _voice_script(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    profile = str((params or {}).get("profile") or "")
    text = str((params or {}).get("text") or "").strip()
    if not text:
        raise host_server.HandlerError(
            -32602, "invalid-params", data={"detail": "text required"},
        )
    home = _resolve_home(profile)
    from alpi.host import voice as host_voice

    script, source = await asyncio.to_thread(host_voice.script_for, home, text)
    return {"script": script, "source": source}
