from __future__ import annotations

import asyncio
import base64
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from alpi import __version__ as _alpi_version
from alpi import config as cfg_mod
from alpi import home as home_mod
from alpi.host import sessions as host_sessions
from alpi.host import server as host_server

READ_MAX_BYTES = 256 * 1024
KNOWN_PROVIDER_KEYS = (
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "OPENROUTER_API_KEY",
    "GEMINI_API_KEY",
)
GATEWAY_ENV_KEYS = {
    "telegram": (("TELEGRAM_BOT_TOKEN", True), ("TELEGRAM_ALLOWED_CHAT_IDS", False)),
    "imap": (
        ("IMAP_ADDRESS", False),
        ("IMAP_PASSWORD", True),
        ("IMAP_HOST", False),
        ("IMAP_PORT", False),
        ("SMTP_HOST", False),
        ("SMTP_PORT", False),
        ("IMAP_ALLOWED_SENDERS", False),
    ),
    "gmail": (
        ("GMAIL_CLIENT_ID", False),
        ("GMAIL_CLIENT_SECRET", True),
        ("GMAIL_ALLOWED_SENDERS", False),
    ),
    "matrix": (
        ("MATRIX_HOMESERVER_URL", False),
        ("MATRIX_USER_ID", False),
        ("MATRIX_ACCESS_TOKEN", True),
        ("MATRIX_DEVICE_ID", False),
        ("MATRIX_ALLOWED_ROOMS", False),
        ("MATRIX_ALLOWED_SENDERS", False),
    ),
}


def register(server: host_server.Server) -> None:
    server.register("host.version", _host_version)
    server.register("host.profiles.list", _profiles_list)
    server.register("host.profile.summaries", _profile_summaries)
    server.register("host.profile.detail", _profile_detail)
    server.register("host.profile.read_file", _profile_read_file)
    server.register("host.profile.storage", _profile_storage)
    server.register("host.config.set_field", _config_set_field)
    server.register("host.config.unset_field", _config_unset_field)
    server.register("host.gateway.status", _gateway_status)
    server.register("host.gateway.config", _gateway_config)
    server.register("host.skills.list", _skills_list)
    server.register("host.skill.read", _skill_read)
    server.register("host.workgroups.list", _workgroups_list)
    server.register("host.workgroup.members", _workgroup_members)
    server.register("host.providers.ollama_models", _ollama_models)


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
    from alpi.host import devices as devices_mod
    token = str((params or {}).get("auth_token") or "")
    role = "admin"
    if token:
        valid, looked_up = devices_mod.validate_and_lookup_role(token)
        role = looked_up if valid else "member"
    from alpi import updater
    return {
        "agent_name": "alpi",
        "version": _alpi_version,
        "update_available": updater.available_update() or "",
        "device_name": device_name,
        "device_id": _ensure_device_id(server.home),
        "role": role,
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
    return await asyncio.to_thread(
        lambda: {"profiles": [_profile_summary(p) for p in _profiles()]},
    )


async def _profile_detail(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    """Heavy companion to ``host.profile.summaries`` — peers, mcps, models, provider keys, sandbox/voice. Called lazily by settings/profile/gateways screens; never by inbox polls."""
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
        "subsystems": {
            "gateway": cfg.service.get("gateway", True) is not False,
            "schedule": cfg.service.get("schedule", True) is not False,
            "alp": cfg.service.get("alp", True) is not False,
            "workgroups": cfg.service.get("workgroups", True) is not False,
        },
        "budget_daily_usd": cfg.budget.get("daily_usd"),
        "budget_used_usd": used_usd,
        "budget_used_tokens": used_tokens,
        "counts": _counts(home),
        "latest_session": latest,
        "pubkey_b64": _profile_pubkey(home),
        # Lightweight "is the profile chat-ready?" hint so inbox/empty-state can decide without paying the cost of a host.profile.detail roundtrip per profile.
        "has_any_provider": _has_any_provider(home, cfg),
    }


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
        "model_reasoning_effort": cfg.model_reasoning.effort,
        "model_reasoning_supported": supports_reasoning(cfg.model),
    }


# Sensitive content `read_file` must never expose, no matter the caller's role. Component-based so nested directories (skills/foo/secrets/, alp/secrets/, workspace/.env) are caught — top-level prefix matching wasn't enough.
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
    if home.resolve() not in (real, *real.parents):
        raise host_server.HandlerError(
            -32602, "invalid-params", data={"detail": "path escapes home"},
        )
    # Belt-and-braces: even after symlink resolution, refuse if the real path lands inside a denied subtree of the same home (symlinked secrets directory).
    try:
        denied_real = real.relative_to(home.resolve())
        if _is_denied_read_path(str(denied_real)):
            raise host_server.HandlerError(
                -32001, "forbidden",
                data={"detail": "resolved path holds daemon secrets"},
            )
    except ValueError:
        pass
    data = real.read_bytes()
    truncated = len(data) > READ_MAX_BYTES
    text = data[:READ_MAX_BYTES].decode("utf-8", errors="replace")
    if truncated:
        text += "\n...(truncated)\n"
    return {"text": text}


def _storage_rows(home: Path) -> list[dict[str, Any]]:
    rows = []
    for key, label, paths in [
        ("sessions", "sessions", [home / "sessions"]),
        ("skills", "skills", [home / "skills"]),
        ("memories", "memories", [home / "memories"]),
        ("rag", "rag", [home / "rag"]),
        ("outputs", "outputs", [home / "outputs"]),
        ("audio", "audio", [home / "cache" / "tts", home / "cache" / "inbound"]),
        ("logs", "logs", [home / "logs"]),
        ("schedule", "schedule", [home / "schedule" / "output"]),
        ("workgroups", "workgroups", [home / "alp" / "workgroups", home / "alp" / "turns.jsonl"]),
        ("gateway", "gateway", [home / "gateway" / "sessions"]),
        ("mentions", "mentions", [home / "mentions"]),
    ]:
        size = 0
        count = 0
        for path in paths:
            s, c = _path_stats(path)
            size += s
            count += c
        rows.append({
            "key": key,
            "label": label,
            "path": str(paths[0]),
            "size_bytes": size,
            "file_count": count,
        })
    return rows


async def _profile_storage(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    home = _resolve_home(str(params.get("profile") or ""))
    # _path_stats does os.walk over sessions/, cache/, logs/, schedule/output/ and alp/workgroups/ — easily seconds on a busy profile.
    return {"storage": await asyncio.to_thread(_storage_rows, home)}


def _emit_config_changed(home: Path, scope: str) -> None:
    from alpi import home as home_mod
    from alpi.host import events as host_events
    host_events.emit("config_changed", {
        "profile": home_mod.profile_name(home),
        "scope": scope,
    })


async def _config_set_field(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    home = _resolve_home(str(params.get("profile") or ""))
    key = str(params.get("key") or "")
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
    data = _load_user_yaml(home)
    _unset_dotted(data, key)
    _write_user_yaml(home, data)
    _emit_config_changed(home, scope=key.split(".", 1)[0] or "field")
    return {"ok": True}


async def _gateway_status(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    home = _resolve_home(str(params.get("profile") or ""))
    env = _env_keys(home)
    rows = [
        {"name": "telegram", "configured": bool(env.get("TELEGRAM_BOT_TOKEN"))},
        {"name": "imap", "configured": bool(env.get("IMAP_ADDRESS"))},
        {
            "name": "gmail",
            "configured": bool(env.get("GMAIL_CLIENT_ID"))
            or (home / "secrets" / "gmail_token.json").exists(),
        },
        {"name": "matrix", "configured": bool(env.get("MATRIX_ACCESS_TOKEN"))},
    ]
    return {"gateways": rows}


async def _gateway_config(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    home = _resolve_home(str(params.get("profile") or ""))
    name = str(params.get("name") or "")
    env = _env_keys(home)
    out: dict[str, str] = {}
    for key, secret in GATEWAY_ENV_KEYS.get(name, ()):
        value = env.get(key)
        if value:
            out[key] = _mask_key(value) if secret else value
    return {"config": out}


async def _skills_list(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    home = _resolve_home(str(params.get("profile") or ""))
    # ``include_body`` defaults to False — keeps listings under a few KB even with dozens of skills. Clients ask for ``host.skill.read`` when they actually need the SKILL.md text.
    include_body = bool((params or {}).get("include_body", False))
    rows = await asyncio.to_thread(_skills, home, include_body=include_body)
    return {"skills": rows}


async def _skill_read(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    """Return one skill's full SKILL.md (capped at ``_SKILL_BODY_MAX``). Callers identify the skill by ``category`` + ``name`` — same shape ``host.skills.list`` returns. Path traversal would otherwise let a malicious client read arbitrary files under ``$HOME``."""
    home = _resolve_home(str((params or {}).get("profile") or ""))
    name = str((params or {}).get("name") or "").strip()
    category = (params or {}).get("category")
    category = str(category).strip() if category else None
    if not name or "/" in name or name.startswith("."):
        raise host_server.HandlerError(
            -32602, "invalid-params", data={"detail": "name required and must not contain path separators"},
        )
    if category is not None and ("/" in category or category.startswith(".")):
        raise host_server.HandlerError(
            -32602, "invalid-params", data={"detail": "category must not contain path separators"},
        )
    skill_md = (home / "skills" / category / name / "SKILL.md") if category else (home / "skills" / name / "SKILL.md")
    if not skill_md.exists():
        raise host_server.HandlerError(
            -32004, "not-found", data={"detail": f"no SKILL.md at {skill_md}"},
        )
    row = await asyncio.to_thread(
        _skill_row, skill_md, category=category, name=name, include_body=True,
    )
    return {"skill": row}


def _aggregate_workgroups(profile: str | None) -> list[dict[str, Any]]:
    if profile:
        return _workgroups_for(str(profile))
    by_id: dict[str, dict[str, Any]] = {}
    for p in _profiles():
        for wg in _workgroups_for(p["name"]):
            old = by_id.get(wg["id"])
            if old is not None and old.get("is_hub"):
                continue
            by_id[wg["id"]] = wg
    rows = list(by_id.values())
    rows.sort(key=lambda x: int(x.get("mtime") or 0), reverse=True)
    return rows


async def _workgroups_list(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    profile = params.get("profile")
    rows = await asyncio.to_thread(_aggregate_workgroups, profile)
    return {"workgroups": rows}


async def _workgroup_members(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    home = _resolve_home(str(params.get("profile") or ""))
    wg_id = str(params.get("wg_id") or "")
    from alpi.host.handlers import _check_id

    _check_id(wg_id, "wg_id")
    members_path = home / "alp" / "workgroups" / wg_id / "members.yaml"
    if members_path.exists():
        return {"members": _members_yaml(members_path.read_text(encoding="utf-8"))}
    subs_path = home / "alp" / "secrets" / "subscriptions.yaml"
    if subs_path.exists():
        return {
            "members": _subscription_roster(
                subs_path.read_text(encoding="utf-8"), wg_id,
            ),
        }
    return {"members": []}


async def _ollama_models(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    # Per-server error surfacing — the original implementation swallowed every
    # exception with `except Exception: pass`, so clients couldn't tell "no
    # Ollama configured" apart from "configured but unreachable". Now each
    # server is polled independently and any failure is returned in `errors`
    # as `{name, url, detail}` so UIs can show which one failed and why.
    import urllib.error
    import urllib.request

    cfg = cfg_mod.load(_resolve_home(str(params.get("profile") or "")))
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
    """Return the most recent chat session only.

    The desktop profile view should never reopen a workgroup / gateway
    session as if it were the user's normal chat history.
    """
    for row in host_sessions.list_sessions(home):
        if row.get("kind") != "chat":
            continue
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
    return None


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
        "sessions": len(host_sessions.list_sessions(home)),
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


def _skills(home: Path, *, include_body: bool = False) -> list[dict[str, Any]]:
    """List skills under ``<home>/skills``. ``include_body=False`` is the hot-path default — reading the markdown body costs ~32KB per skill and is wasted bytes for listings (inbox, settings); detail views call ``host.skill.read`` instead."""
    root = home / "skills"
    rows = []
    if not root.exists():
        return rows
    for top in sorted(root.iterdir()):
        if not top.is_dir() or top.name.startswith("."):
            continue
        if (top / "SKILL.md").exists():
            rows.append(_skill_row(top / "SKILL.md", category=None, name=top.name, include_body=include_body))
            continue
        for child in sorted(top.iterdir()):
            if child.is_dir() and not child.name.startswith(".") and (child / "SKILL.md").exists():
                rows.append(_skill_row(child / "SKILL.md", category=top.name, name=child.name, include_body=include_body))
    return rows


def _count_skill_dirs(home: Path) -> int:
    """Cheap count for summaries — never opens SKILL.md so listings don't pay the ~32KB-per-skill read cost the body path does."""
    root = home / "skills"
    if not root.exists():
        return 0
    n = 0
    for top in sorted(root.iterdir()):
        if not top.is_dir() or top.name.startswith("."):
            continue
        if (top / "SKILL.md").exists():
            n += 1
            continue
        for child in sorted(top.iterdir()):
            if child.is_dir() and not child.name.startswith(".") and (child / "SKILL.md").exists():
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




def _workgroups_for(profile: str) -> list[dict[str, Any]]:
    home = _resolve_home(profile)
    rows = _hub_workgroups(home, profile) + _subscribed_workgroups(home, profile)
    rows.sort(key=lambda x: int(x.get("mtime") or 0), reverse=True)
    return rows


def _hub_workgroups(home: Path, profile: str) -> list[dict[str, Any]]:
    root = home / "alp" / "workgroups"
    if not root.exists():
        return []
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
        out.append({
            "id": path.name,
            "profile": profile,
            "name": meta.get("name"),
            "briefing": meta.get("briefing"),
            "pipeline": meta.get("pipeline") if isinstance(meta.get("pipeline"), list) else [],
            "paused": bool(meta.get("paused", False)),
            "auto_read": bool(meta.get("auto_read", False)),
            "members": len(members) if isinstance(members, list) else 0,
            "mtime": mtime,
            "path": str(path),
            "budget_usd": budget.get("max_usd"),
            "spent_usd": float(ledger.get("usd") or 0.0),
            "is_hub": True,
            "hub_id": profile,
        })
    return out


def _subscribed_workgroups(home: Path, profile: str) -> list[dict[str, Any]]:
    path = home / "alp" / "secrets" / "subscriptions.yaml"
    data = _load_yaml(path)
    if not isinstance(data, list):
        return []
    try:
        mtime = int(path.stat().st_mtime)
    except OSError:
        mtime = 0
    out = []
    for sub in data:
        if not isinstance(sub, dict):
            continue
        roster = sub.get("roster") or {}
        out.append({
            "id": sub.get("wg_id", ""),
            "profile": profile,
            "name": sub.get("name"),
            "briefing": sub.get("briefing"),
            "pipeline": sub.get("pipeline") if isinstance(sub.get("pipeline"), list) else [],
            "paused": False,
            "members": len(roster) if isinstance(roster, dict) else 0,
            "mtime": mtime,
            "path": str(path),
            "budget_usd": None,
            "spent_usd": 0.0,
            "is_hub": False,
            "hub_id": sub.get("hub_id"),
        })
    return out


def _members_yaml(text: str) -> list[dict[str, Any]]:
    data = yaml.safe_load(text) or []
    if not isinstance(data, list):
        return []
    return [
        {
            "pubkey": str(row.get("pubkey") or ""),
            "bio": row.get("bio"),
            "voice": row.get("voice"),
            "joined": bool(row.get("joined", False)),
        }
        for row in data
        if isinstance(row, dict)
    ]


def _subscription_roster(text: str, wg_id: str) -> list[dict[str, Any]]:
    data = yaml.safe_load(text) or []
    for row in data if isinstance(data, list) else []:
        if not isinstance(row, dict) or row.get("wg_id") != wg_id:
            continue
        roster = row.get("roster") or {}
        if not isinstance(roster, dict):
            return []
        voices_raw = row.get("roster_voices") or {}
        voices = voices_raw if isinstance(voices_raw, dict) else {}
        bios_raw = row.get("roster_bios") or {}
        bios = bios_raw if isinstance(bios_raw, dict) else {}
        return [
            {
                "pubkey": str(pubkey),
                "bio": bios.get(pubkey),
                "voice": voices.get(pubkey),
                "joined": True,
            }
            for pubkey in roster.keys()
        ]
    return []


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
