from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from alpi import config as cfg_mod
from alpi.host import server as host_server


_ENV_KEY_RE = re.compile(r"^[A-Z_][A-Z0-9_]{0,63}$")
# Reserved keys the daemon needs for itself.
_PROTECTED_ENV_KEYS = frozenset({
    "HOME", "PATH", "USER", "ALPI_HOME", "ALPI_PROFILE",
    "PYTHONPATH", "TMPDIR", "LANG", "LC_ALL",
})


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
    server.register("host.mcp.add", _mcp_add)
    server.register("host.mcp.remove", _mcp_remove)
    server.register("host.gateway.remove", _gateway_remove)
    server.register_stream("host.gateway.gmail_authorize", _gmail_authorize)
    server.register("host.sandbox.set", _sandbox_set)
    server.register("host.sandbox.network", _sandbox_network)
    server.register("host.voice.set_voice", _voice_set_voice)
    server.register("host.voice.autoplay", _voice_autoplay)


def _resolve_home(profile: str) -> Path:
    from alpi.host.handlers import _resolve_home as _r
    return _r(profile)


def _params(d: dict[str, Any], *keys: str) -> tuple[Any, ...]:
    return tuple(d.get(k) for k in keys)


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
    return {"ok": True}


async def _providers_unset_key(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    from alpi.model_selector import _remove_env_key

    profile, key = _params(params, "profile", "key")
    key = _check_env_key(str(key or ""))
    home = _resolve_home(str(profile or ""))
    cfg = cfg_mod.load(home)
    _remove_env_key(cfg.env_path, key)
    if key in os.environ:
        os.environ.pop(key, None)
    return {"ok": True}


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
    cfg_mod.save(cfg)
    return {"ok": True}


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
    if not peers_mod.remove(home, peer_id):
        raise host_server.HandlerError(
            -32004, "not-found", data={"detail": f"no peer @{peer_id}"},
        )
    return {"ok": True}


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
    """Map ``pubkey -> profile_name`` for local profiles."""
    from alpi import home as home_mod
    from alpi.alp.keys import load_or_generate as _load

    out: dict[str, str] = {}
    root = home_mod._ROOT
    try:
        kp = _load(root)
        out[kp.pubkey_b64()] = "default"
    except Exception:  # noqa: BLE001
        pass
    profiles_root = root / "profiles"
    if profiles_root.exists():
        for prof_dir in profiles_root.iterdir():
            if not prof_dir.is_dir():
                continue
            try:
                kp = _load(prof_dir)
                out[kp.pubkey_b64()] = prof_dir.name
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
    if not pending_mod.remove(home, pubkey):
        raise host_server.HandlerError(
            -32004, "not-found", data={"detail": "pubkey not in pending list"},
        )
    return {"ok": True}


async def _profile_create(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    from alpi import home as home_mod
    from alpi.cli import _bootstrap

    name = str(params.get("name") or "").strip()
    if not name or name == "default":
        raise host_server.HandlerError(
            -32602, "invalid-params",
            data={"detail": "name required and cannot be 'default'"},
        )
    if "/" in name or name.startswith(".") or not name.replace("-", "").replace("_", "").isalnum():
        raise host_server.HandlerError(
            -32602, "invalid-params", data={"detail": f"invalid name {name!r}"},
        )
    h = home_mod.home_for(name)
    if h.exists() and any(h.iterdir()):
        raise host_server.HandlerError(
            -32008, "name-taken",
            data={"detail": f"profile {name!r} already exists"},
        )
    _bootstrap(h)
    return {"ok": True, "home": str(h)}


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
    return {"ok": True}


_GATEWAY_ENV_KEYS = {
    "telegram": ("TELEGRAM_BOT_TOKEN", "TELEGRAM_ALLOWED_CHAT_IDS"),
    "imap": (
        "IMAP_ADDRESS", "IMAP_PASSWORD", "IMAP_HOST", "IMAP_SMTP_HOST",
        "IMAP_ALLOWED_SENDERS",
    ),
    "gmail": (
        "GMAIL_CLIENT_ID", "GMAIL_CLIENT_SECRET", "GMAIL_ALLOWED_SENDERS",
    ),
    "matrix": (
        "MATRIX_HOMESERVER_URL", "MATRIX_USER_ID", "MATRIX_ACCESS_TOKEN",
        "MATRIX_DEVICE_ID", "MATRIX_ALLOWED_ROOMS", "MATRIX_ALLOWED_SENDERS",
    ),
}


async def _gmail_authorize(
    params: dict[str, Any],
    _server: host_server.Server,
    send_frame,
) -> None:
    import asyncio
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
    senders_raw = params.get("allowed_senders")
    if senders_raw is None:
        senders = existing.get("GMAIL_ALLOWED_SENDERS", "")
    else:
        senders = ",".join(
            s.strip().lower() for s in str(senders_raw).split(",") if s.strip()
        )

    if not client_id or not client_secret:
        await send_frame({
            "event": "error",
            "text": "client_id and client_secret are required",
        })
        return

    for key, val in (
        ("GMAIL_CLIENT_ID", client_id),
        ("GMAIL_CLIENT_SECRET", client_secret),
        ("GMAIL_ALLOWED_SENDERS", senders),
    ):
        _append_env(cfg.env_path, key, val)
        os.environ[key] = val

    await send_frame({"event": "browser_opened"})

    loop = asyncio.get_running_loop()
    try:
        token = await loop.run_in_executor(None, lambda: gmail_auth.first_run(home))
        await send_frame({"event": "authorized", "email": token.email})
    except gmail_auth.GmailAuthError as exc:
        await send_frame({"event": "error", "text": str(exc)})
    except Exception as exc:  # noqa: BLE001
        await send_frame({"event": "error", "text": f"unexpected: {exc!r}"})


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


async def _gateway_remove(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    from alpi.model_selector import _remove_env_key

    name = str(params.get("name") or "").strip()
    if name not in _GATEWAY_ENV_KEYS:
        raise host_server.HandlerError(
            -32602, "invalid-params",
            data={"detail": f"unknown gateway {name!r}"},
        )
    home = _resolve_home(str(params.get("profile") or ""))
    cfg = cfg_mod.load(home)
    for key in _GATEWAY_ENV_KEYS[name]:
        _remove_env_key(cfg.env_path, key)
    if name == "gmail":
        token = home / "secrets" / "gmail_token.json"
        if token.exists():
            try:
                token.unlink()
            except OSError:
                pass
    return {"ok": True}


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
    return {"ok": True}


async def _voice_autoplay(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    on = _bool_state(params)
    home = _resolve_home(str(params.get("profile") or ""))
    cfg = cfg_mod.load(home)
    cfg.tools.tts.autoplay = on
    cfg_mod.save(cfg)
    return {"ok": True}
