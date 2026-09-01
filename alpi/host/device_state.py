from __future__ import annotations

import asyncio
import base64
import json
import os
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from alpi import __version__ as _alpi_version
from alpi import config as cfg_mod
from alpi import home as home_mod
from alpi.host import sessions as host_sessions
from alpi.host import server as host_server
from alpi.host.connection_context import current as current_connection, owns_connection

READ_MAX_BYTES = 256 * 1024
KNOWN_PROVIDER_KEYS = (
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "OPENROUTER_API_KEY",
    "GEMINI_API_KEY",
)


def register(server: host_server.Server) -> None:
    server.register("host.version", _host_version)
    server.register("host.profiles.list", _profiles_list)
    server.register("host.profile.summaries", _profile_summaries)
    server.register("host.profile.detail", _profile_detail)
    server.register("host.profile.read_file", _profile_read_file)
    server.register("host.profile.memory_usage", _profile_memory_usage)
    server.register("host.profile.memory_read", _profile_memory_read)
    server.register("host.profile.memory_write", _profile_memory_write)
    server.register("host.profile.storage", _profile_storage)
    server.register("host.cleanup.plan", _cleanup_plan)
    server.register("host.cleanup.apply", _cleanup_apply)
    server.register("host.config.set_field", _config_set_field)
    server.register("host.config.unset_field", _config_unset_field)
    server.register("host.email.status", _email_status)
    server.register("host.email.config", _email_config)
    server.register("host.skills.list", _skills_list)
    server.register("host.skill.read", _skill_read)
    server.register("host.skill.file", _skill_file)
    server.register("host.workgroups.list", _workgroups_list)
    server.register("host.workgroup.members", _workgroup_members)
    server.register("host.providers.ollama_models", _ollama_models)
    server.register("host.settings.profile_snapshot", _profile_snapshot)


def _resolve_home(profile: str) -> Path:
    from alpi.host.handlers import _resolve_home as _r

    return _r(profile)


def _profiles() -> list[dict[str, Any]]:
    root = home_mod._ROOT
    out: list[dict[str, Any]] = []
    if root.exists():
        out.append({"name": "default", "home": str(root), "is_default": True})
    profiles_root = root / "profiles"
    if profiles_root.exists():
        for path in sorted(profiles_root.iterdir()):
            if path.is_dir():
                out.append({
                    "name": path.name,
                    "home": str(path),
                    "is_default": False,
                })
    return out


async def _host_version(
    params: dict[str, Any], server: host_server.Server,
) -> dict[str, Any]:
    try:
        cfg = cfg_mod.load(home_mod.get_home())
        device_name = str((cfg.host or {}).get("device_name") or "").strip()
    except Exception:  # noqa: BLE001
        device_name = ""
    # The Unix-socket caller carries no token but is sovereign — report admin so the local desktop still unlocks the full UI without a separate "is local" probe.
    from alpi.host.connection_context import current
    from alpi.host.connections import authenticate
    token = str((params or {}).get("auth_token") or "")
    auth = authenticate(token) if token else None
    role = auth.role if auth and auth.valid else ("member" if token else "admin")
    context = current()
    from alpi import updater
    return {
        "agent_name": "alpi",
        "version": _alpi_version,
        "update_available": updater.available_update() or "",
        "device_name": device_name,
        "device_id": _ensure_device_id(server.home),
        "role": role,
        "connection_id": context.connection_id,
        "connection_device_id": context.device_id,
    }


def _ensure_device_id(home: Path) -> str:
    # Atomic create-or-read so two concurrent first-call clients cannot mint distinct ids and race the write — the loser's O_EXCL fails and it falls through to read the winner's value.
    import os
    import uuid
    path = home / "host" / "device_id"
    try:
        existing = path.read_text(encoding="utf-8").strip()
        if existing:
            return existing
    except OSError:
        pass
    new_id = uuid.uuid4().hex
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        try:
            os.write(fd, new_id.encode("utf-8"))
        finally:
            os.close(fd)
        return new_id
    except FileExistsError:
        try:
            existing = path.read_text(encoding="utf-8").strip()
            if existing:
                return existing
        except OSError:
            pass
        return ""
    except OSError:
        return ""


async def _profiles_list(
    _params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    return {"profiles": _profiles()}


async def _profile_summaries(
    _params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    """Hot path: inbox/sidebar listing for every connected profile. Returns only the lightweight ``_profile_summary`` shape — settings/profile screens fetch the heavy bits per-profile via ``host.profile.detail``. Pre-split this was ~10KB/profile; now ~1KB."""
    return {"profiles": [dict(r) for r in await _summaries_coalesced()]}


async def _profile_detail(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    """Heavy companion to ``host.profile.summaries`` — peers, mcps, models, provider keys, sandbox/voice. Called lazily by settings/profile/email screens; never by inbox polls."""
    profile = str((params or {}).get("profile") or "")
    home = _resolve_home(profile)
    if not home.exists():
        raise host_server.HandlerError(
            -32004, "not-found", data={"detail": f"no profile {profile!r}"},
        )
    return await asyncio.to_thread(_profile_detail_payload, home)


def _profile_summary(row: dict[str, Any]) -> dict[str, Any]:
    home = Path(row["home"])
    cfg = cfg_mod.load(home)
    used_usd, used_tokens = _today_ledger(home)
    latest = _latest_chat_for(home)
    return {
        **row,
        "running": _daemon_running(),
        "pid": _daemon_pid(),
        "installed_via": _installed_via(),
        "model": cfg.model or None,
        "accent": cfg.tui.get("accent"),
        "voice_id": cfg.tools.tts.voice,
        "bio": cfg.public_bio or None,
        "paused": cfg.paused,
        "budget_daily_usd": cfg.budget.get("daily_usd"),
        "budget_used_usd": used_usd,
        "budget_used_tokens": used_tokens,
        "counts": _counts(home),
        "latest_session": latest,
        "pubkey_b64": _profile_pubkey(home),
        # Lightweight "is the profile chat-ready?" hint so inbox/empty-state can decide without paying the cost of a host.profile.detail roundtrip per profile.
        "has_any_provider": _has_any_provider(home, cfg),
    }


_SUMMARY_TTL_S = 3.0
# Keyed by (connection, profile): latest_session is connection-scoped, so a shared entry would leak previews across connections.
_summary_cache: dict[tuple[str, str], tuple[float, dict[str, Any]]] = {}
_summary_gen: dict[str, int] = {}
_summary_state_lock = threading.Lock()
_summary_gate: tuple[Any, asyncio.Lock] | None = None


def invalidate_summary(profile: str | None = None) -> None:
    with _summary_state_lock:
        if profile is None:
            _summary_cache.clear()
            for name in _summary_gen:
                _summary_gen[name] += 1
        else:
            name = str(profile)
            for key in [k for k in _summary_cache if k[1] == name]:
                _summary_cache.pop(key, None)
            _summary_gen[name] = _summary_gen.get(name, 0) + 1


def _summary_rows() -> list[dict[str, Any]]:
    connection_id = current_connection().connection_id
    rows: list[dict[str, Any]] = []
    for row in _profiles():
        name = str(row["name"])
        key = (connection_id, name)
        with _summary_state_lock:
            hit = _summary_cache.get(key)
            fresh = hit is not None and time.monotonic() - hit[0] < _SUMMARY_TTL_S
            # Registering the generation here is what lets a concurrent full clear bump it.
            gen = _summary_gen.setdefault(name, 0)
        if fresh:
            rows.append(hit[1])
            continue
        value = _profile_summary(row)
        with _summary_state_lock:
            if _summary_gen.get(name, 0) == gen:
                _summary_cache[key] = (time.monotonic(), value)
        rows.append(value)
    return rows


async def _summaries_coalesced() -> list[dict[str, Any]]:
    global _summary_gate

    loop = asyncio.get_running_loop()
    if _summary_gate is None or _summary_gate[0] is not loop:
        _summary_gate = (loop, asyncio.Lock())
    async with _summary_gate[1]:
        return await asyncio.to_thread(_summary_rows)


def _has_any_provider(home: Path, cfg: cfg_mod.Config) -> bool:
    if (cfg.providers.get("ollama") or []):
        return True
    if ((cfg.providers.get("openrouter") or {}).get("models") or []):
        return True
    env = _env_keys(home)
    return any(env.get(k) for k in KNOWN_PROVIDER_KEYS)


def _profile_detail_payload(home: Path) -> dict[str, Any]:
    cfg = cfg_mod.load(home)
    from alpi.providers.reasoning import supports_reasoning
    return {
        "workspace": cfg.workspace or None,
        "tcp_port": cfg.alp.get("tcp_port"),
        "advertise_host": (cfg.network or {}).get("host"),  # shared accessible address
        "provider_keys": _provider_keys(home),
        "provider_ollama": _ollama_providers(cfg),
        "sandbox": cfg.tools.terminal.sandbox,
        "sandbox_allow_network": cfg.tools.terminal.allow_network,
        "voice_id": cfg.tools.tts.voice,
        "voice_auto_read": cfg.tools.tts.auto_read,
        "mcps": _mcp_servers(cfg),
        "peers": _profile_peers(home),
        "models": _models(cfg, home),
        "vision_model": cfg.tools.read_image.model,
        "model_reasoning_effort": cfg.model_reasoning.effort,
        "model_reasoning_supported": supports_reasoning(cfg.model),
        "tiers": {
            name: {
                "model": tier.model,
                "effort": tier.effort,
                "reasoning_supported": bool(tier.model) and supports_reasoning(tier.model),
            }
            for name, tier in (("fast", cfg.tiers.fast), ("deep", cfg.tiers.deep))
        },
    }


# Sensitive content `read_file` must never expose, no matter the caller's role. Component-based so nested directories (skills/foo/secrets/, alp/secrets/, workspace/.env) are caught — top-level prefix matching wasn't enough.
# Keeps denying legacy `gateway/` state (telegram tokens, etc.) on profiles upgraded from 0.9, even though 0.10 no longer writes there.
_TOP_LEVEL_DENY = frozenset({"host", "gateway", "cache"})
_DENIED_COMPONENT = "secrets"
_DENIED_BASENAME_PREFIX = ".env"
_DENIED_EXTENSIONS = (".pem", ".key", ".p12", ".pfx", ".keystore")


def _is_denied_read_path(rel_path: str) -> bool:
    import os
    rel = os.path.normpath(rel_path).replace("\\", "/")
    if rel.startswith("../") or rel == ".." or rel.startswith("/"):
        return True
    if rel in (".", ""):
        return False
    parts = [p for p in rel.split("/") if p]
    parts_lower = [p.lower() for p in parts]
    if any(p == _DENIED_COMPONENT for p in parts_lower):
        return True
    if parts_lower[0] in _TOP_LEVEL_DENY:
        return True
    basename = parts_lower[-1]
    if basename.startswith(_DENIED_BASENAME_PREFIX):
        return True
    if any(basename.endswith(ext) for ext in _DENIED_EXTENSIONS):
        return True
    return False


async def _profile_read_file(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    profile = str(params.get("profile") or "")
    rel_path = str(params.get("rel_path") or "")
    if _is_denied_read_path(rel_path):
        raise host_server.HandlerError(
            -32001, "forbidden",
            data={"detail": "path holds daemon secrets and cannot be read via host.profile.read_file"},
        )
    home = _resolve_home(profile)
    abs_path = home / rel_path
    try:
        real = abs_path.resolve(strict=True)
    except OSError as e:
        raise host_server.HandlerError(
            -32004, "not-found", data={"detail": str(e)},
        ) from None
    home_real = home.resolve()
    if home_real not in (real, *real.parents):
        raise host_server.HandlerError(
            -32602, "invalid-params", data={"detail": "path escapes home"},
        )
    rel_real = real.relative_to(home_real)
    # Denied-secrets AND member-scope both test the symlink-resolved path — a textual rel_path check is defeated by alp/../ and alp/-rooted symlinks.
    if _is_denied_read_path(str(rel_real)):
        raise host_server.HandlerError(
            -32001, "forbidden",
            data={"detail": "resolved path holds daemon secrets"},
        )
    from alpi.host.connection_context import current
    if current().role != "admin" and rel_real.parts[:1] != ("alp",):
        raise host_server.HandlerError(
            -32001, "forbidden",
            data={"detail": "path is admin-only over remote connections"},
        )
    data = real.read_bytes()
    truncated = len(data) > READ_MAX_BYTES
    text = data[:READ_MAX_BYTES].decode("utf-8", errors="replace")
    if truncated:
        text += "\n...(truncated)\n"
    return {"text": text}


def _memory_usage_blocking(home: Path) -> dict[str, Any]:
    from alpi.memory import MemoryStore

    store = MemoryStore(home)
    paths = {
        "AGENT.md": store.agent_path,
        "USER.md": store.user_path,
        "MEMORY.md": store.memory_path,
    }
    out: dict[str, Any] = {}
    for name, (used, limit) in store.usage().items():
        p = paths.get(name)
        updated_at = None
        if p is not None and p.exists():
            try:
                updated_at = p.stat().st_mtime
            except OSError:
                updated_at = None
        out[name] = {
            "used": used,
            "limit": limit,
            "pct": round(used / limit * 100) if limit else None,
            "over": bool(limit and used > limit),
            "updated_at": updated_at,
        }
    return out


async def _profile_memory_usage(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    import asyncio

    profile = str(params.get("profile") or "")
    home = _resolve_home(profile)
    return {"files": await asyncio.to_thread(_memory_usage_blocking, home)}


async def _profile_memory_read(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    from alpi.memory import MemoryStore

    import asyncio

    profile = str(params.get("profile") or "")
    name = str(params.get("name") or "")
    store = MemoryStore(_resolve_home(profile))
    try:
        text, rev = await asyncio.to_thread(store.read_with_rev, name)
    except ValueError as e:
        raise host_server.HandlerError(-32602, "invalid-params", data={"detail": str(e)}) from None
    return {"text": text, "rev": rev}


async def _profile_memory_write(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    import asyncio

    from alpi import home as home_mod
    from alpi.host import events as host_events
    from alpi.memory import MemoryConflict, MemoryStore

    profile = str(params.get("profile") or "")
    name = str(params.get("name") or "")
    text = params.get("text")
    expected_rev = params.get("rev")
    if not isinstance(text, str):
        raise host_server.HandlerError(
            -32602, "invalid-params", data={"detail": "text must be a string"},
        )
    if not isinstance(expected_rev, str) or not expected_rev:
        raise host_server.HandlerError(
            -32602, "invalid-params",
            data={"detail": "rev is required — read the file first to get its revision"},
        )
    home = _resolve_home(profile)
    store = MemoryStore(home)
    try:
        rev = await asyncio.to_thread(store.replace, name, text, expected_rev=expected_rev)
    except MemoryConflict as e:
        raise host_server.HandlerError(
            -32009, "conflict", data={"detail": str(e), "rev": e.current_rev},
        ) from None
    except ValueError as e:
        raise host_server.HandlerError(-32602, "invalid-params", data={"detail": str(e)}) from None
    host_events.emit("memory_changed", {"profile": home_mod.profile_name(home), "name": name})
    return {"ok": True, "rev": rev}


def _storage_rows(home: Path) -> list[dict[str, Any]]:
    out = home_mod.out_root(home)
    specs = [
        ("sessions", "sessions", [home / "sessions"]),
        ("skills", "skills", [home / "skills"]),
        ("memories", "memories", [home / "memories"]),
        ("knowledge", "knowledge", [home / "knowledge.sqlite"]),
        ("outputs", "outputs", [home / "outputs"]),
        ("generated", "generated", [out] if out is not None else []),
        ("audio", "audio", [home / "cache" / "tts", home / "cache" / "inbound"]),
        ("logs", "logs", [home / "logs"]),
        ("schedule", "schedule", [home / "schedule" / "output"]),
        ("workgroups", "workgroups", [home / "alp" / "workgroups", home / "alp" / "turns.jsonl"]),
        ("mentions", "mentions", [home / "mentions"]),
        ("attachments", "attachments", [home / "host" / "attachments" / "tmp"]),
    ]
    rows = []
    for key, label, paths in specs:
        size = 0
        count = 0
        for path in paths:
            s, c = _path_stats(path)
            size += s
            count += c
        rows.append({
            "key": key,
            "label": label,
            "path": str(paths[0]) if paths else str(home / "out"),
            "size_bytes": size,
            "file_count": count,
        })
    return rows


_STORAGE_TTL_S = 30.0
_storage_cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}
_storage_cache_lock = threading.Lock()


def _clear_storage_cache() -> None:
    with _storage_cache_lock:
        _storage_cache.clear()


def _storage_rows_cached(home: Path) -> list[dict[str, Any]]:
    key = str(home)
    with _storage_cache_lock:
        hit = _storage_cache.get(key)
        if hit is not None and time.monotonic() - hit[0] < _STORAGE_TTL_S:
            return [dict(r) for r in hit[1]]
    rows = _storage_rows(home)
    with _storage_cache_lock:
        _storage_cache[key] = (time.monotonic(), rows)
    return [dict(r) for r in rows]


async def _profile_storage(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    home = _resolve_home(str(params.get("profile") or ""))
    # _path_stats does os.walk over sessions/, cache/, logs/, schedule/output/ and alp/workgroups/ — easily seconds on a busy profile.
    return {"storage": await asyncio.to_thread(_storage_rows_cached, home)}


def _emit_config_changed(home: Path, scope: str) -> None:
    from alpi import home as home_mod
    from alpi.host import events as host_events
    profile = home_mod.profile_name(home)
    invalidate_summary(profile)
    host_events.emit("config_changed", {"profile": profile, "scope": scope})


async def _cleanup_plan(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    from alpi import cleanup
    home = _resolve_home(str((params or {}).get("profile") or ""))
    return {"categories": await asyncio.to_thread(cleanup.plan, home)}


async def _cleanup_apply(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    from alpi import cleanup
    home = _resolve_home(str((params or {}).get("profile") or ""))
    raw_keys = (params or {}).get("keys")
    keys = [str(k) for k in raw_keys] if isinstance(raw_keys, list) else []
    if not keys:
        raise host_server.HandlerError(
            -32602, "invalid-params", data={"detail": "keys (list) required"},
        )
    results = [await asyncio.to_thread(cleanup.apply, home, k) for k in keys]
    if any(r.get("removed") for r in results):
        _clear_storage_cache()
    return {"results": results}


async def _config_set_field(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    home = _resolve_home(str(params.get("profile") or ""))
    key = str(params.get("key") or "")
    _reject_removed_config_key(key)
    if key == "host.endpoints":
        raise host_server.HandlerError(
            -32602,
            "invalid-params",
            data={
                "detail": (
                    "host.endpoints must be changed through "
                    "host.network.set_advertised"
                ),
            },
        )
    value = params.get("value")
    data = _load_user_yaml(home)
    coerced = _coerce_config_value(key, value)
    if key == "model_reasoning.effort":
        from alpi.providers.reasoning import normalise_effort, supports_reasoning
        normalised = normalise_effort(coerced)
        current_model = str(data.get("model") or "")
        # Refuse to persist effort when the current model can't act on it — otherwise profile.detail would report effort="high" + supported=false, which is confusing dead state. The user can resolve it by setting effort AFTER switching to a supported model.
        if normalised and supports_reasoning(current_model):
            _set_dotted(data, key, normalised)
        else:
            _unset_dotted(data, key)
            if isinstance(data.get("model_reasoning"), dict) and not data["model_reasoning"]:
                data.pop("model_reasoning", None)
    elif key == "model":
        _set_dotted(data, key, coerced)
        # Switching to an unsupported model auto-clears the effort so the dropdown disappears without a stale value lurking.
        from alpi.providers.reasoning import supports_reasoning
        if not supports_reasoning(str(coerced)):
            _unset_dotted(data, "model_reasoning.effort")
            if isinstance(data.get("model_reasoning"), dict) and not data["model_reasoning"]:
                data.pop("model_reasoning", None)
    elif key in ("tiers.fast.model", "tiers.deep.model"):
        from alpi.providers.reasoning import supports_reasoning
        tier = key.split(".")[1]
        model_val = str(coerced or "").strip()
        # Empty model clears the whole tier — a tier without a model has no meaning.
        if not model_val:
            _unset_dotted(data, f"tiers.{tier}")
        else:
            _set_dotted(data, key, model_val)
            if not supports_reasoning(model_val):
                _unset_dotted(data, f"tiers.{tier}.effort")
        _prune_empty_tiers(data)
    elif key in ("tiers.fast.effort", "tiers.deep.effort"):
        from alpi.providers.reasoning import normalise_effort, supports_reasoning
        tier = key.split(".")[1]
        normalised = normalise_effort(coerced)
        tier_model = str(((data.get("tiers") or {}).get(tier) or {}).get("model") or "")
        if normalised and tier_model and supports_reasoning(tier_model):
            _set_dotted(data, key, normalised)
        else:
            _unset_dotted(data, key)
        _prune_empty_tiers(data)
    elif key == "tools.read_image.model":
        model_val = str(coerced or "").strip()
        if model_val:
            _set_dotted(data, key, model_val)
        else:
            _unset_dotted(data, key)
            _prune_empty_read_image(data)
    else:
        _set_dotted(data, key, coerced)
    _write_user_yaml(home, data)
    _emit_config_changed(home, scope=key.split(".", 1)[0] or "field")
    return {"ok": True}


async def _config_unset_field(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    home = _resolve_home(str(params.get("profile") or ""))
    key = str(params.get("key") or "")
    _reject_removed_config_key(key)
    data = _load_user_yaml(home)
    _unset_dotted(data, key)
    _prune_empty_tiers(data)
    if key == "tools.read_image.model":
        _prune_empty_read_image(data)
    _write_user_yaml(home, data)
    _emit_config_changed(home, scope=key.split(".", 1)[0] or "field")
    return {"ok": True}


def _reject_removed_config_key(key: str) -> None:
    if key == "service" or key.startswith("service."):
        raise host_server.HandlerError(
            -32602,
            "invalid-params",
            data={
                "detail": (
                    "service switches were removed; daemon capabilities "
                    "are always available"
                ),
            },
        )


async def _email_status(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    from alpi.mail import accounts as accounts_mod
    home = _resolve_home(str(params.get("profile") or ""))
    return {"accounts": accounts_mod.list_accounts(home)}


async def _email_config(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    from alpi.mail import accounts as accounts_mod
    home = _resolve_home(str(params.get("profile") or ""))
    account_id = str(params.get("id") or "")
    account = accounts_mod.get_account(home, account_id)
    if account is None:
        return {"config": None}
    out = {k: v for k, v in account.items() if k != "id"}
    if str(account.get("type")) == "gmail":
        out["password_set"] = accounts_mod.gmail_token_path(home, account_id).exists()
    else:
        env = _env_keys(home)
        out["password_set"] = bool(env.get(accounts_mod.password_env_key(account_id)))
    return {"id": account_id, "config": out}


async def _skills_list(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    home = _resolve_home(str(params.get("profile") or ""))
    # ``include_body`` defaults to False — keeps listings under a few KB even with dozens of skills. Clients ask for ``host.skill.read`` when they actually need the SKILL.md text.
    include_body = bool((params or {}).get("include_body", False))
    rows = await asyncio.to_thread(_skills_overview, home, include_body)
    return {"skills": rows}


def _skills_overview(home: Path, include_body: bool) -> list[dict[str, Any]]:
    from alpi.home import effective_profile_env
    from alpi.tools import skill as skill_mod

    rows = _skills(home, include_body=include_body)
    env = effective_profile_env(home)
    cfg = skill_mod._load_cfg_raw(home)
    for row in rows:
        skill_dir = Path(row["path"]).parent
        meta = skill_mod._frontmatter(skill_dir / "SKILL.md")
        status, reason = skill_mod.skill_status(meta, env=env, cfg_raw=cfg)
        row["status"] = status
        row["reason"] = reason
        row["size"] = skill_mod.skill_dir_size(skill_dir)
        row["keywords"] = skill_mod.skill_keywords(meta)
    return rows


_SKILL_SEGMENT_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def _skill_meta(profile: str, name: str, category: Any) -> tuple[Path, Path, str | None]:
    home = _resolve_home(profile)
    if (home / "skills").is_symlink():
        raise host_server.HandlerError(
            -32602, "invalid-params", data={"detail": "skills root must not be a symlink"},
        )
    name = str(name or "").strip()
    category = str(category).strip() if category else None
    if not _SKILL_SEGMENT_RE.match(name):
        raise host_server.HandlerError(
            -32602, "invalid-params", data={"detail": "name must match [A-Za-z0-9_-]+"},
        )
    if category is not None and not _SKILL_SEGMENT_RE.match(category):
        raise host_server.HandlerError(
            -32602, "invalid-params", data={"detail": "category must match [A-Za-z0-9_-]+"},
        )
    skill_dir = (home / "skills" / category / name) if category else (home / "skills" / name)
    if category is not None and (home / "skills" / category).is_symlink():
        raise host_server.HandlerError(
            -32602, "invalid-params", data={"detail": "category must not be a symlink"},
        )
    if skill_dir.is_symlink():
        raise host_server.HandlerError(
            -32602, "invalid-params", data={"detail": "skill directory must not be a symlink"},
        )
    if (home / "skills").resolve() not in skill_dir.resolve().parents:
        raise host_server.HandlerError(
            -32602, "invalid-params", data={"detail": "skill path escapes the skills directory"},
        )
    return home, skill_dir, category


async def _skill_read(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    p = params or {}
    home, skill_dir, category = _skill_meta(str(p.get("profile") or ""), p.get("name"), p.get("category"))
    skill_md = skill_dir / "SKILL.md"
    if skill_md.is_symlink():
        raise host_server.HandlerError(
            -32602, "invalid-params", data={"detail": "SKILL.md must not be a symlink"},
        )
    if not skill_md.exists():
        raise host_server.HandlerError(
            -32004, "not-found", data={"detail": f"no SKILL.md at {skill_md}"},
        )
    row = await asyncio.to_thread(_skill_detail, home, skill_md, category, skill_dir.name)
    return {"skill": row}


def _skill_detail(home: Path, skill_md: Path, category: str | None, name: str) -> dict[str, Any]:
    from alpi.home import effective_profile_env
    from alpi.tools import skill as skill_mod

    env = effective_profile_env(home)
    cfg = skill_mod._load_cfg_raw(home)
    return skill_mod.skill_detail_payload(skill_md, category=category, name=name, env=env, cfg_raw=cfg)


async def _skill_file(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    from alpi.tools import skill as skill_mod

    p = params or {}
    _home, skill_dir, _category = _skill_meta(str(p.get("profile") or ""), p.get("name"), p.get("category"))
    path = str(p.get("path") or "").strip()
    try:
        row = await asyncio.to_thread(skill_mod.skill_file_read, skill_dir, path)
    except PermissionError as e:
        raise host_server.HandlerError(-32603, "forbidden", data={"detail": str(e)})
    except FileNotFoundError as e:
        raise host_server.HandlerError(-32004, "not-found", data={"detail": str(e)})
    except (ValueError, OSError) as e:
        raise host_server.HandlerError(-32602, "invalid-params", data={"detail": str(e)})
    return {"file": row}


def _aggregate_workgroups(
    profile: str | None, *, include_pipeline_status: bool = False,
) -> list[dict[str, Any]]:
    if profile:
        return _workgroups_for(
            str(profile), include_pipeline_status=include_pipeline_status,
        )
    by_id: dict[str, dict[str, Any]] = {}
    for p in _profiles():
        for wg in _workgroups_for(
            p["name"], include_pipeline_status=False,
        ):
            old = by_id.get(wg["id"])
            if old is not None and old.get("is_hub"):
                continue
            by_id[wg["id"]] = wg
    rows = list(by_id.values())
    if include_pipeline_status:
        queued_by_home: dict[Path, dict[str, dict[str, Any]]] = {}
        from alpi.alp import pipeline_queue

        for row in rows:
            home = _resolve_home(str(row.get("profile") or ""))
            queue_item = None
            if row.get("is_hub"):
                if home not in queued_by_home:
                    queued_by_home[home] = pipeline_queue.positions(home)
                queue_item = queued_by_home[home].get(str(row.get("id") or ""))
            row["pipeline_status"] = (
                "queued" if queue_item else _pipeline_status(home, str(row.get("id") or ""))
            )
            row["queued_pipeline"] = queue_item.get("pipeline") if queue_item else None
            row["queue_position"] = queue_item.get("position") if queue_item else None
    rows.sort(key=lambda x: int(x.get("mtime") or 0), reverse=True)
    return rows


async def _workgroups_list(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    profile = params.get("profile")
    include_pipeline_status = params.get("include_pipeline_status") is True
    rows = await asyncio.to_thread(
        _aggregate_workgroups,
        profile,
        include_pipeline_status=include_pipeline_status,
    )
    return {"workgroups": rows}


def _safe_section(fn) -> dict[str, Any]:
    try:
        return fn()
    except Exception as e:  # noqa: BLE001
        return {"error": {"code": -32603, "message": "internal-error", "data": {"detail": str(e)}}}


def _snapshot_payload(
    home: Path, profile: str, wanted: frozenset[str] | None = None,
) -> dict[str, Any]:
    from concurrent.futures import ThreadPoolExecutor

    from alpi.host.usage import daily_payload
    from alpi.mail import accounts as accounts_mod
    from alpi.scheduler import jobs_store

    def _schedules() -> dict[str, Any]:
        try:
            return {"jobs": jobs_store.read(home)}
        except jobs_store.CorruptJobsFile as e:
            return {
                "error": {"code": -32603, "message": "internal-error", "data": {"detail": f"jobs.json corrupt: {e}"}},
            }

    sections: dict[str, Any] = {
        "detail": lambda: _profile_detail_payload(home),
        "usage": lambda: daily_payload(home),
        "workgroups": lambda: {"workgroups": _aggregate_workgroups(profile)},
        "email": lambda: {"accounts": accounts_mod.list_accounts(home)},
        "storage": lambda: {"storage": _storage_rows_cached(home)},
    }
    if wanted is not None:
        sections = {k: fn for k, fn in sections.items() if k in wanted}
    include_schedules = wanted is None or "schedules" in wanted
    # Sections fan out to threads so storage's os.walk never serializes behind the cheap reads.
    with ThreadPoolExecutor(max_workers=len(sections) + 2) as pool:
        futures = {k: pool.submit(_safe_section, fn) for k, fn in sections.items()}
        schedules_future = pool.submit(_schedules) if include_schedules else None
        out: dict[str, Any] = {k: f.result() for k, f in futures.items()}
        if schedules_future is not None:
            out["schedules"] = schedules_future.result()
    return out


async def _profile_snapshot(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    profile = str((params or {}).get("profile") or "")
    home = _resolve_home(profile)
    if not home.exists():
        raise host_server.HandlerError(
            -32004, "not-found", data={"detail": f"no profile {profile!r}"},
        )
    raw_sections = (params or {}).get("sections")
    wanted = None
    if isinstance(raw_sections, list) and raw_sections:
        wanted = frozenset(str(s) for s in raw_sections)
    return await asyncio.to_thread(_snapshot_payload, home, profile, wanted)


async def _workgroup_members(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    home = _resolve_home(str(params.get("profile") or ""))
    wg_id = str(params.get("wg_id") or "")
    from alpi.host.handlers import _check_id

    _check_id(wg_id, "wg_id")
    return {"members": await asyncio.to_thread(_workgroup_members_payload, home, wg_id)}


def _workgroup_members_payload(home: Path, wg_id: str) -> list[dict[str, Any]]:
    from alpi.alp import subscription as sub_mod
    from alpi.alp import workgroup as wg_mod

    wg = wg_mod.load(home, wg_id)
    if wg is not None:
        return [
            {
                "pubkey": member.pubkey,
                "bio": member.bio or None,
                "voice": member.voice or None,
                "joined": member.joined,
            }
            for member in wg.members
        ]
    sub = sub_mod.get(home, wg_id)
    if sub is None:
        return []
    return [
        {
            "pubkey": str(pubkey),
            "bio": sub.roster_bios.get(pubkey),
            "voice": sub.roster_voices.get(pubkey),
            "joined": True,
        }
        for pubkey in sub.roster
    ]


async def _ollama_models(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    home = _resolve_home(str(params.get("profile") or ""))
    # Sync HTTP probes (1.5s timeout each) — never run them on the loop.
    return await asyncio.to_thread(_poll_ollama_models, home)


def _poll_ollama_models(home: Path) -> dict[str, Any]:
    # Per-server failures go to `errors` — "no Ollama configured" must stay distinguishable from "unreachable".
    import urllib.error
    import urllib.request

    cfg = cfg_mod.load(home)
    models: list[str] = []
    errors: list[dict[str, str]] = []
    for item in _ollama_providers(cfg):
        name = item["name"]
        url = item["url"].rstrip("/") + "/api/tags"
        try:
            with urllib.request.urlopen(url, timeout=1.5) as resp:
                payload = resp.read().decode("utf-8")
            data = json.loads(payload)
            for m in data.get("models") or []:
                tag = m.get("name")
                if tag:
                    models.append(f"{name}/{tag}")
        except urllib.error.URLError as e:
            reason = getattr(e, "reason", e)
            errors.append({"name": name, "url": item["url"], "detail": f"{reason}"})
        except TimeoutError:
            errors.append({"name": name, "url": item["url"], "detail": "timeout (1.5s)"})
        except json.JSONDecodeError as e:
            errors.append({"name": name, "url": item["url"], "detail": f"bad json: {e.msg}"})
        except Exception as e:  # noqa: BLE001
            errors.append({"name": name, "url": item["url"], "detail": str(e) or e.__class__.__name__})
    return {"models": models, "errors": errors}


def _load_user_yaml(home: Path) -> dict[str, Any]:
    path = home / "config.yaml"
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


def _write_user_yaml(home: Path, data: dict[str, Any]) -> None:
    # Atomic tmp+fsync+rename — same writer as ``config.save`` so a daemon crash mid-write never leaves a truncated config.yaml.
    from alpi.config import atomic_write_yaml
    atomic_write_yaml(home / "config.yaml", data)


def _prune_empty_tiers(data: dict[str, Any]) -> None:
    tiers = data.get("tiers")
    if not isinstance(tiers, dict):
        return
    for name in list(tiers):
        if isinstance(tiers[name], dict) and not tiers[name]:
            tiers.pop(name)
    if not tiers:
        data.pop("tiers", None)


def _prune_empty_read_image(data: dict[str, Any]) -> None:
    tools = data.get("tools")
    if not isinstance(tools, dict):
        return
    if isinstance(tools.get("read_image"), dict) and not tools["read_image"]:
        tools.pop("read_image", None)
    if not tools:
        data.pop("tools", None)


def _set_dotted(data: dict[str, Any], key: str, value: Any) -> None:
    parts = [p for p in key.split(".") if p]
    if not parts:
        raise host_server.HandlerError(
            -32602, "invalid-params", data={"detail": "key required"},
        )
    cur = data
    for part in parts[:-1]:
        child = cur.get(part)
        if not isinstance(child, dict):
            child = {}
            cur[part] = child
        cur = child
    cur[parts[-1]] = value


def _unset_dotted(data: dict[str, Any], key: str) -> None:
    parts = [p for p in key.split(".") if p]
    cur = data
    for part in parts[:-1]:
        child = cur.get(part)
        if not isinstance(child, dict):
            return
        cur = child
    if parts:
        cur.pop(parts[-1], None)


def _coerce_config_value(key: str, value: Any) -> Any:
    if key in {"alp.tcp_port", "host.tcp_port"}:
        return int(value)
    if key in {"budget.daily_usd"}:
        return float(value)
    if str(value).lower() == "true":
        return True
    if str(value).lower() == "false":
        return False
    return "" if value is None else str(value)


def _daemon_pid() -> int | None:
    from alpi import service
    return service.daemon_running_pid(home_mod._ROOT)


def _daemon_running() -> bool:
    # service.daemon_running_pid already does the os.kill probe + starttime validation.
    return _daemon_pid() is not None


def _installed_via() -> str | None:
    home = Path.home()
    if (home / "Library/LaunchAgents/com.alpi.daemon.plist").exists():
        return "launchd"
    if (home / ".config/systemd/user/alpi-daemon.service").exists():
        return "systemd"
    return None


def _latest_chat_for(home: Path) -> dict[str, Any] | None:
    """Chat kind only: the profile view must never reopen a workgroup session as normal chat history."""
    row = host_sessions.latest_chat_summary(home, can_read=owns_connection)
    if not row:
        return None
    return {
        "id": row["id"],
        "mtime": row["mtime"],
        "updated_at": row.get("updated_at"),
        "started_at": row.get("started_at"),
        "first_user": row["first_user"],
        "last_user": row.get("last_user"),
        "last_assistant": row.get("last_assistant"),
        "kind": row.get("kind"),
    }


def _today_ledger(home: Path) -> tuple[float, int]:
    try:
        data = json.loads((home / "logs" / "ledger.json").read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return 0.0, 0
    if data.get("day") != datetime.now(timezone.utc).strftime("%Y-%m-%d"):
        return 0.0, 0
    prof = data.get("profile") or {}
    return float(prof.get("usd") or 0.0), int(prof.get("tokens") or 0)


def _provider_keys(home: Path) -> list[dict[str, str]]:
    env = _env_keys(home)
    return [
        {"env": key, "preview": _mask_key(env[key])}
        for key in KNOWN_PROVIDER_KEYS
        if env.get(key)
    ]


def _ollama_providers(cfg: cfg_mod.Config) -> list[dict[str, str]]:
    return [
        {"name": str(e.get("name") or ""), "url": str(e.get("url") or "")}
        for e in (cfg.providers.get("ollama") or [])
        if isinstance(e, dict)
    ]


def _mcp_servers(cfg: cfg_mod.Config) -> list[dict[str, Any]]:
    servers = ((cfg.raw.get("mcp") or {}).get("servers") or {})
    out = []
    for name, value in servers.items():
        if not isinstance(value, dict):
            continue
        out.append({
            "name": str(name),
            "command": str(value.get("command") or ""),
            "args": [str(x) for x in value.get("args") or []],
            "env_keys": list((value.get("env") or {}).keys()),
        })
    return out


def _counts(home: Path) -> dict[str, int]:
    return {
        "peers": _yaml_entry_count(home / "alp" / "peers.yaml", "- id:"),
        "workgroups": _subdir_count(home / "alp" / "workgroups"),
        "sessions": host_sessions.count_sessions(home),
        "skills": _count_skill_dirs(home),
        "memory_bytes": _path_stats(home / "memories")[0],
    }


def _path_stats(path: Path) -> tuple[int, int]:
    if path.is_file():
        return path.stat().st_size, 1
    if not path.exists():
        return 0, 0
    size = 0
    count = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            p = Path(root) / name
            try:
                size += p.stat().st_size
                count += 1
            except OSError:
                pass
    return size, count


def _subdir_count(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for p in path.iterdir() if p.is_dir())


def _yaml_entry_count(path: Path, prefix: str) -> int:
    try:
        return sum(
            1 for line in path.read_text(encoding="utf-8").splitlines()
            if line.startswith(prefix)
        )
    except OSError:
        return 0


def _profile_pubkey(home: Path) -> str | None:
    try:
        pem = (home / "alp" / "secrets" / "alp_key.pub").read_text(encoding="utf-8")
        inner = "".join(line for line in pem.splitlines() if not line.startswith("-----"))
        raw = base64.b64decode(inner)[-32:]
        return base64.b64encode(raw).decode("ascii")
    except Exception:  # noqa: BLE001
        return None


def _profile_peers(home: Path) -> list[dict[str, Any]]:
    try:
        from alpi.alp import peers as peers_mod

        return [
            {
                "id": p.id,
                "pubkey": p.pubkey,
                "address": p.address,
                "alias": p.alias,
                "allow": p.allow,
            }
            for p in peers_mod.load(home)
        ]
    except Exception:  # noqa: BLE001
        return []


def _models(cfg: cfg_mod.Config, home: Path) -> list[str]:
    env = _env_keys(home)
    out = []
    if cfg.model and _model_provider_available(cfg.model, env):
        out.append(cfg.model)
    if env.get("OPENAI_API_KEY"):
        out.extend(_curated_ids_for("openai"))
    if env.get("ANTHROPIC_API_KEY"):
        out.extend(_curated_ids_for("anthropic"))
    if env.get("OPENROUTER_API_KEY"):
        for model in ((cfg.providers.get("openrouter") or {}).get("models") or []):
            out.append(f"openrouter/{model}")
        out.extend(_curated_ids_for("openrouter"))
    seen = set()
    return [m for m in out if not (m in seen or seen.add(m))]


def _model_provider_available(model: str, env: dict[str, str]) -> bool:
    # Ollama ids are "<server>/<model>" — no builtin prefix matches, so they stay visible.
    from alpi import providers as prov_mod

    head = model.split("/", 1)[0]
    for p in prov_mod.builtin():
        if (p.model_prefix or p.name) == head:
            return bool(p.api_key_env) and bool(env.get(p.api_key_env))
    return True


def _curated_ids_for(provider: str) -> list[str]:
    path = Path(__file__).parents[1] / "providers" / "curated_models.yaml"
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except OSError:
        return []
    return [f"{provider}/{row['id']}" for row in data.get(provider, []) if row.get("id")]


def _env_keys(home: Path) -> dict[str, str]:
    out = {}
    try:
        lines = (home / ".env").read_text(encoding="utf-8").splitlines()
    except OSError:
        return out
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        out[key.strip()] = value.strip().strip('"').strip("'")
    return out


def _mask_key(value: str) -> str:
    if len(value) <= 8:
        return "•" * len(value)
    return f"{value[:3]}…{value[-4:]}"


def _real_skill(d: Path) -> bool:
    # symlinked dirs / SKILL.md could resolve outside <home>/skills and leak files.
    if not d.is_dir() or d.is_symlink():
        return False
    md = d / "SKILL.md"
    return md.is_file() and not md.is_symlink()


def _skills(home: Path, *, include_body: bool = False) -> list[dict[str, Any]]:
    """List skills under ``<home>/skills``. ``include_body=False`` is the hot-path default — reading the markdown body costs ~32KB per skill and is wasted bytes for listings (inbox, settings); detail views call ``host.skill.read`` instead."""
    root = home / "skills"
    rows = []
    if not root.exists() or root.is_symlink():
        return rows
    for top in sorted(root.iterdir()):
        if not top.is_dir() or top.is_symlink() or top.name.startswith("."):
            continue
        if _real_skill(top):
            rows.append(_skill_row(top / "SKILL.md", category=None, name=top.name, include_body=include_body))
            continue
        for child in sorted(top.iterdir()):
            if not child.name.startswith(".") and _real_skill(child):
                rows.append(_skill_row(child / "SKILL.md", category=top.name, name=child.name, include_body=include_body))
    return rows


def _count_skill_dirs(home: Path) -> int:
    """Cheap count for summaries — never opens SKILL.md so listings don't pay the ~32KB-per-skill read cost the body path does."""
    root = home / "skills"
    if not root.exists() or root.is_symlink():
        return 0
    n = 0
    for top in sorted(root.iterdir()):
        if not top.is_dir() or top.is_symlink() or top.name.startswith("."):
            continue
        if _real_skill(top):
            n += 1
            continue
        for child in sorted(top.iterdir()):
            if not child.name.startswith(".") and _real_skill(child):
                n += 1
    return n


_SKILL_BODY_MAX = 32_000


def _skill_row(
    skill_md: Path,
    *,
    category: str | None,
    name: str,
    include_body: bool = True,
) -> dict[str, Any]:
    try:
        text = skill_md.read_text(encoding="utf-8")
    except OSError:
        text = ""
    description = _skill_description_from_text(text)
    row: dict[str, Any] = {
        "category": category,
        "name": name,
        "description": description,
        "path": str(skill_md),
    }
    if include_body:
        body = _skill_body_from_text(text)
        if len(body) > _SKILL_BODY_MAX:
            body = body[:_SKILL_BODY_MAX] + "\n\n…(truncated)"
        row["body"] = body
    return row


def _skill_description_from_text(text: str) -> str | None:
    if not text.startswith("---"):
        return None
    for line in text.splitlines()[1:]:
        line = line.strip()
        if line == "---":
            break
        if line.startswith("description:"):
            value = line.split(":", 1)[1].strip().strip('"').strip("'")
            return value or None
    return None


def _skill_body_from_text(text: str) -> str:
    if not text.startswith("---"):
        return text
    lines = text.splitlines()
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return "\n".join(lines[i + 1:]).lstrip("\n")
    return text




def _pipeline_row(raw: dict[str, Any]) -> dict[str, Any]:
    """Definitions only — this row never decrypts, so run state comes from ``host.workgroup.tasks``."""
    from alpi.alp import subscription as sub_mod
    from alpi.alp import workgroup as wg_mod

    needs_relaunch = False
    try:
        pipelines, launch = wg_mod.pipelines_from_raw(raw)
    except ValueError:
        # Retired shape: the poller refuses to load this workgroup, so the row must not read as healthy.
        pipelines, launch, needs_relaunch = {}, None, True
    declared_mode = raw.get("pipeline_mode")
    steps = raw.get("pipeline_steps")
    phase_map = (
        sub_mod.coerce_phase_map(steps if isinstance(steps, dict) else None)
        or sub_mod.coerce_phase_map(raw.get("phase_map"))
    )
    return {
        "pipelines": {k: list(v) for k, v in pipelines.items()},
        "launch_pipeline": launch,
        "pipeline_mode": (
            bool(declared_mode) if declared_mode is not None else bool(pipelines)
        ),
        "phase_map": phase_map,
        "needs_relaunch": needs_relaunch,
    }


def _workgroups_for(
    profile: str, *, include_pipeline_status: bool = False,
) -> list[dict[str, Any]]:
    home = _resolve_home(profile)
    rows = _hub_workgroups(
        home, profile, include_pipeline_status=include_pipeline_status,
    ) + _subscribed_workgroups(
        home, profile, include_pipeline_status=include_pipeline_status,
    )
    rows.sort(key=lambda x: int(x.get("mtime") or 0), reverse=True)
    return rows


def _pipeline_status(home: Path, wg_id: str) -> str | None:
    from alpi.host import workgroup as host_workgroup

    state = host_workgroup.fold_task_state(home, wg_id)
    run = state.get("pipeline_run") if isinstance(state, dict) else None
    if not isinstance(run, dict):
        return None
    return str(run.get("status") or "") or None


def _hub_workgroups(
    home: Path, profile: str, *, include_pipeline_status: bool = False,
) -> list[dict[str, Any]]:
    root = home / "alp" / "workgroups"
    if not root.exists():
        return []
    if include_pipeline_status:
        from alpi.alp import pipeline_queue
        queued = pipeline_queue.positions(home)
    else:
        queued = {}
    out = []
    for path in sorted(root.iterdir()):
        if not path.is_dir():
            continue
        meta = _load_yaml(path / "meta.yaml")
        members = _load_yaml(path / "members.yaml")
        ledger = _load_json(path / "ledger.json")
        transcript = path / "transcript.jsonl"
        try:
            mtime = int((transcript if transcript.exists() else path).stat().st_mtime)
        except OSError:
            mtime = 0
        budget = meta.get("budget") if isinstance(meta.get("budget"), dict) else {}
        queue_item = queued.get(path.name)
        pipeline_status = "queued" if queue_item else None
        if include_pipeline_status and pipeline_status is None:
            pipeline_status = _pipeline_status(home, path.name)
        row = {
            "id": path.name,
            "profile": profile,
            "name": meta.get("name"),
            "briefing": meta.get("briefing"),
            **_pipeline_row(meta),
            "paused": bool(meta.get("paused", False)),
            "auto_read": bool(meta.get("auto_read", False)),
            "members": len(members) if isinstance(members, list) else 0,
            "mtime": mtime,
            "path": str(path),
            "budget_usd": budget.get("max_usd"),
            "spent_usd": float(ledger.get("usd") or 0.0),
            "is_hub": True,
            "hub_id": profile,
        }
        if include_pipeline_status:
            row.update({
                "pipeline_status": pipeline_status,
                "queued_pipeline": queue_item.get("pipeline") if queue_item else None,
                "queue_position": queue_item.get("position") if queue_item else None,
            })
        out.append(row)
    return out


def _subscribed_workgroups(
    home: Path, profile: str, *, include_pipeline_status: bool = False,
) -> list[dict[str, Any]]:
    from alpi.alp import subscription as sub_mod

    path = sub_mod.path(home)
    data = sub_mod.load(home)
    try:
        mtime = int(path.stat().st_mtime)
    except OSError:
        mtime = 0
    out = []
    for sub in data:
        roster = sub.roster or {}
        row = {
            "id": sub.wg_id,
            "profile": profile,
            "name": sub.name,
            "briefing": sub.briefing,
            "pipelines": {k: list(v) for k, v in sub.pipelines.items()},
            "launch_pipeline": sub.launch_pipeline,
            "pipeline_mode": sub.pipeline_mode,
            "phase_map": {
                slug: {
                    key: value
                    for key, value in spec.items()
                    if key in {"owner", "task"}
                }
                for slug, spec in sub.phase_map.items()
            },
            "needs_relaunch": False,
            "paused": sub.paused,
            "members": len(roster) if isinstance(roster, dict) else 0,
            "mtime": _subscription_mtime(sub, mtime),
            "path": str(path),
            "budget_usd": None,
            "spent_usd": 0.0,
            "is_hub": False,
            "hub_id": sub.hub_id,
        }
        if include_pipeline_status:
            row["pipeline_status"] = (
                _pipeline_status(home, sub.wg_id)
                if sub.pipeline_mode
                else None
            )
        out.append(row)
    return out


def _subscription_mtime(sub: Any, fallback: int) -> int:
    stamps = [
        str(post.get("ts") or post.get("at") or "")
        for post in sub.recent_posts or []
        if isinstance(post, dict)
    ]
    for stamp in [*reversed(stamps), str(sub.joined_at or "")]:
        try:
            return int(datetime.fromisoformat(stamp.replace("Z", "+00:00")).timestamp())
        except (TypeError, ValueError):
            continue
    return fallback


def _load_yaml(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:  # noqa: BLE001
        return {}


def _load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001
        return {}
