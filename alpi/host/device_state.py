from __future__ import annotations

import base64
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

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
    server.register("host.profiles.list", _profiles_list)
    server.register("host.profile.summaries", _profile_summaries)
    server.register("host.profile.read_file", _profile_read_file)
    server.register("host.profile.storage", _profile_storage)
    server.register("host.config.set_field", _config_set_field)
    server.register("host.config.unset_field", _config_unset_field)
    server.register("host.gateway.status", _gateway_status)
    server.register("host.gateway.config", _gateway_config)
    server.register("host.skills.list", _skills_list)
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


async def _profiles_list(
    _params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    return {"profiles": _profiles()}


async def _profile_summaries(
    _params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    return {"profiles": [_profile_summary(p) for p in _profiles()]}


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
        "bio": cfg.public_bio or None,
        "workspace": cfg.workspace or None,
        "subsystems": {
            "gateway": cfg.service.get("gateway", True) is not False,
            "schedule": cfg.service.get("schedule", True) is not False,
            "alp": cfg.service.get("alp", True) is not False,
            "workgroups": cfg.service.get("workgroups", True) is not False,
        },
        "tcp_port": cfg.alp.get("tcp_port"),
        "tcp_host": cfg.alp.get("tcp_host"),
        "budget_daily_usd": cfg.budget.get("daily_usd"),
        "budget_daily_tokens": cfg.budget.get("daily_tokens"),
        "budget_used_usd": used_usd,
        "budget_used_tokens": used_tokens,
        "provider_keys": _provider_keys(home),
        "provider_ollama": _ollama_providers(cfg),
        "sandbox": cfg.tools.terminal.sandbox,
        "sandbox_allow_network": cfg.tools.terminal.allow_network,
        "voice_id": cfg.tools.tts.voice,
        "voice_autoplay": cfg.tools.tts.autoplay,
        "mcps": _mcp_servers(cfg),
        "counts": _counts(home),
        "latest_session": latest,
        "pubkey_b64": _profile_pubkey(home),
        "peers": _profile_peers(home),
        "models": _models(cfg, home),
    }


async def _profile_read_file(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    profile = str(params.get("profile") or "")
    rel_path = str(params.get("rel_path") or "")
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
    data = real.read_bytes()
    truncated = len(data) > READ_MAX_BYTES
    text = data[:READ_MAX_BYTES].decode("utf-8", errors="replace")
    if truncated:
        text += "\n...(truncated)\n"
    return {"text": text}


async def _profile_storage(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    home = _resolve_home(str(params.get("profile") or ""))
    rows = []
    for key, label, paths in [
        ("sessions", "sessions", [home / "sessions"]),
        ("audio", "audio", [home / "cache" / "tts", home / "cache" / "inbound"]),
        ("logs", "logs", [home / "logs"]),
        ("schedule", "schedule", [home / "schedule" / "output"]),
        ("workgroups", "workgroups", [home / "alp" / "workgroups", home / "alp" / "turns.jsonl"]),
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
    return {"storage": rows}


async def _config_set_field(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    home = _resolve_home(str(params.get("profile") or ""))
    key = str(params.get("key") or "")
    value = params.get("value")
    data = _load_user_yaml(home)
    _set_dotted(data, key, _coerce_config_value(key, value))
    _write_user_yaml(home, data)
    return {"ok": True}


async def _config_unset_field(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    home = _resolve_home(str(params.get("profile") or ""))
    key = str(params.get("key") or "")
    data = _load_user_yaml(home)
    _unset_dotted(data, key)
    _write_user_yaml(home, data)
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
    return {"skills": _skills(home)}


async def _workgroups_list(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    profile = params.get("profile")
    if profile:
        rows = _workgroups_for(str(profile))
    else:
        by_id: dict[str, dict[str, Any]] = {}
        for p in _profiles():
            for wg in _workgroups_for(p["name"]):
                old = by_id.get(wg["id"])
                if old is not None and old.get("is_hub"):
                    continue
                by_id[wg["id"]] = wg
        rows = list(by_id.values())
        rows.sort(key=lambda x: int(x.get("mtime") or 0), reverse=True)
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
    cfg = cfg_mod.load(_resolve_home(str(params.get("profile") or "")))
    models: list[str] = []
    try:
        import urllib.request

        for item in _ollama_providers(cfg):
            url = item["url"].rstrip("/") + "/api/tags"
            with urllib.request.urlopen(url, timeout=1.5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            for m in data.get("models") or []:
                name = m.get("name")
                if name:
                    models.append(f"{item['name']}/{name}")
    except Exception:  # noqa: BLE001
        pass
    return {"models": models}


def _load_user_yaml(home: Path) -> dict[str, Any]:
    path = home / "config.yaml"
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


def _write_user_yaml(home: Path, data: dict[str, Any]) -> None:
    (home / "config.yaml").write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


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
    if key in {"budget.daily_tokens"}:
        return int(value)
    if key in {"budget.daily_usd"}:
        return float(value)
    if str(value).lower() == "true":
        return True
    if str(value).lower() == "false":
        return False
    return "" if value is None else str(value)


def _daemon_pid() -> int | None:
    path = home_mod._ROOT / "service.pid"
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except Exception:  # noqa: BLE001
        return None


def _daemon_running() -> bool:
    pid = _daemon_pid()
    if not pid:
        return False
    return subprocess.run(
        ["kill", "-0", str(pid)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    ).returncode == 0


def _installed_via() -> str | None:
    home = Path.home()
    if (home / "Library/LaunchAgents/com.alpi.daemon.plist").exists():
        return "launchd"
    if (home / ".config/systemd/user/alpi-daemon.service").exists():
        return "systemd"
    return None


def _latest_chat_for(home: Path) -> dict[str, Any] | None:
    """Return the most recent session of ANY kind. The conversations
    list on mobile / sidebar on desktop need a single recency signal —
    a profile that only handled scheduled jobs or inbound gateway turns
    must still surface as 'recent'."""
    rows = host_sessions.list_sessions(home)
    if not rows:
        return None
    r = rows[0]
    return {
        "id": r["id"],
        "mtime": r["mtime"],
        "first_user": r["first_user"],
        "kind": r.get("kind"),
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
        "sessions": len(host_sessions.list_sessions(home)),
        "skills": len(_skills(home)),
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
    out = []
    if cfg.model:
        out.append(cfg.model)
    env = _env_keys(home)
    if env.get("OPENAI_API_KEY"):
        out.extend(_curated_ids_for("openai"))
    if env.get("ANTHROPIC_API_KEY"):
        out.extend(_curated_ids_for("anthropic"))
    for model in ((cfg.providers.get("openrouter") or {}).get("models") or []):
        out.append(f"openrouter/{model}")
    seen = set()
    return [m for m in out if not (m in seen or seen.add(m))]


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


def _skills(home: Path) -> list[dict[str, Any]]:
    root = home / "skills"
    rows = []
    if not root.exists():
        return rows
    for top in sorted(root.iterdir()):
        if not top.is_dir() or top.name.startswith("."):
            continue
        if (top / "SKILL.md").exists():
            rows.append({
                "category": None,
                "name": top.name,
                "description": _skill_description(top / "SKILL.md"),
            })
            continue
        for child in sorted(top.iterdir()):
            if child.is_dir() and not child.name.startswith(".") and (child / "SKILL.md").exists():
                rows.append({
                    "category": top.name,
                    "name": child.name,
                    "description": _skill_description(child / "SKILL.md"),
                })
    return rows


def _skill_description(path: Path) -> str | None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
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
            "paused": bool(meta.get("paused", False)),
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
        return [
            {"pubkey": str(pubkey), "bio": None, "joined": True}
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
