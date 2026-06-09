from __future__ import annotations

import asyncio
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from alpi import home as home_mod
from alpi.host import server as host_server

USAGE_SPAN_DAYS = 14
_DEFAULT_PRICE_OUT = 0.6 / 1e6
_SAFE_ID = re.compile(r"^[A-Za-z0-9_-]+$")


def register(server: host_server.Server) -> None:
    server.register("host.usage.daily", _usage_daily)
    server.register("host.usage.workgroup.daily", _workgroup_usage_daily)


def _resolve_home(profile: str) -> Path:
    if not profile or not _SAFE_ID.match(profile):
        raise host_server.HandlerError(
            -32602, "invalid-params", data={"detail": "profile fails [A-Za-z0-9_-]+"},
        )
    return home_mod.home_for(profile)


def _utc_today() -> date:
    return datetime.now(timezone.utc).date()


def _window(
    by_day: dict[str, dict[str, Any]], today: date, span: int,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i in range(span - 1, -1, -1):
        iso = (today - timedelta(days=i)).isoformat()
        b = by_day.get(iso) or {"tokIn": 0, "tokOut": 0, "cost": 0.0}
        out.append({
            "iso": iso,
            "tokIn": int(b["tokIn"]),
            "tokOut": int(b["tokOut"]),
            "cost": round(float(b["cost"]), 6),
        })
    return out


def bucket_history(
    history: dict[str, Any], today: date, span: int = USAGE_SPAN_DAYS,
) -> list[dict[str, Any]]:
    by_day: dict[str, dict[str, Any]] = {}
    for iso, h in (history or {}).items():
        if not isinstance(h, dict):
            continue
        by_day[iso] = {
            "tokIn": int(h.get("tokens_in") or 0),
            "tokOut": int(h.get("tokens_out") or 0),
            "cost": float(h.get("usd") or 0.0),
        }
    return _window(by_day, today, span)


def _iso_day(ts_str: Any) -> date | None:
    if not ts_str:
        return None
    s = str(ts_str).replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).date()


def bucket_workgroup(
    entries: list[dict[str, Any]], today: date, span: int = USAGE_SPAN_DAYS,
) -> list[dict[str, Any]]:
    by_day: dict[str, dict[str, Any]] = {}
    for e in entries:
        cost = e.get("cost") or {}
        if not cost:
            continue
        day = _iso_day(e.get("ts"))
        if day is None:
            continue
        b = by_day.setdefault(day.isoformat(), {"tokIn": 0, "tokOut": 0, "cost": 0.0})
        tin = cost.get("tokens_in")
        tout = cost.get("tokens_out")
        if tin is not None or tout is not None:
            b["tokIn"] += int(tin or 0)
            b["tokOut"] += int(tout or 0)
        else:
            b["tokIn"] += int(cost.get("tokens") or 0)
        b["cost"] += float(cost.get("usd") or 0.0)
    return _window(by_day, today, span)


def price_out(model: str) -> float:
    m = str(model or "")
    try:
        from alpi import llm
        if m.startswith("openrouter/"):
            price = llm._openrouter_pricing().get(m.split("/", 1)[1])
            if price and price[1] > 0:
                return float(price[1])
        import litellm
        info = litellm.model_cost.get(m) or {}
        out = info.get("output_cost_per_token")
        if out:
            return float(out)
    except Exception:  # noqa: BLE001
        pass
    return _DEFAULT_PRICE_OUT


def compute_daily(home: Path, today: date | None = None) -> list[dict[str, Any]]:
    from alpi import ledger
    history = ledger.snapshot(home).get("history") or {}
    return bucket_history(history, today or _utc_today())


def compute_workgroup_daily(
    home: Path, wg_id: str, today: date | None = None,
) -> list[dict[str, Any]]:
    from alpi.alp import workgroup as alp_wg
    entries = alp_wg._read_transcript(alp_wg._wg_dir(home, wg_id))
    return bucket_workgroup(entries, today or _utc_today())


def _profile_model(home: Path) -> str:
    try:
        from alpi import config as cfg_mod
        return cfg_mod.load(home).model or ""
    except Exception:  # noqa: BLE001
        return ""


async def _usage_daily(params: dict[str, Any], _server: host_server.Server) -> dict[str, Any]:
    profile = str((params or {}).get("profile") or "")
    home = _resolve_home(profile)
    days = await asyncio.to_thread(compute_daily, home)
    return {"days": days, "priceOut": price_out(_profile_model(home))}


async def _workgroup_usage_daily(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    profile = str((params or {}).get("profile") or "")
    wg_id = str((params or {}).get("wg_id") or "").strip()
    home = _resolve_home(profile)
    if not wg_id or not _SAFE_ID.match(wg_id):
        raise host_server.HandlerError(
            -32602, "invalid-params", data={"detail": "wg_id fails [A-Za-z0-9_-]+"},
        )
    days = await asyncio.to_thread(compute_workgroup_daily, home, wg_id)
    return {"days": days, "priceOut": price_out(_profile_model(home))}
