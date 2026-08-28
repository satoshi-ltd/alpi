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
    server.register("host.connections.summary", _connections_summary)
    server.register("host.connections.usage_daily", _connection_usage_daily)


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
        row = {
            "iso": iso,
            "tokIn": int(b["tokIn"]),
            "tokOut": int(b["tokOut"]),
            "cost": round(float(b["cost"]), 6),
        }
        if "cachedIn" in b:
            row["cachedIn"] = int(b["cachedIn"])
            row["measuredIn"] = int(b["measuredIn"])
        out.append(row)
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
        cached = int(h.get("tokens_cached") or 0)
        measured = int(h.get("tokens_measured") or 0)
        if cached > 0 or measured > 0:
            by_day[iso]["cachedIn"] = cached
            by_day[iso]["measuredIn"] = measured
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
        b = by_day.setdefault(day.isoformat(), {
            "tokIn": 0, "tokOut": 0, "cost": 0.0, "cachedIn": 0, "measuredIn": 0,
        })
        tin = cost.get("tokens_in")
        tout = cost.get("tokens_out")
        if tin is not None or tout is not None:
            b["tokIn"] += int(tin or 0)
            b["tokOut"] += int(tout or 0)
        else:
            b["tokIn"] += int(cost.get("tokens") or 0)
        cached = cost.get("cached_in")
        if cached is not None:
            b["cachedIn"] += int(cached or 0)
            # cached_in without measured_in exists on disk; its denominator is tokens_in, never 0.
            b["measuredIn"] += int(cost.get("measured_in", tin or 0) or 0)
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


def compute_total30(home: Path, today: date | None = None) -> dict[str, Any]:
    """Whole-retention totals (ledger keeps 30 days) for the 'monthly cost' number next to the 14-day chart."""
    from alpi import ledger
    history = ledger.snapshot(home).get("history") or {}
    days = bucket_history(history, today or _utc_today(), span=30)
    return {
        "spanDays": 30,
        "cost": round(sum(d["cost"] for d in days), 6),
        "tokIn": sum(d["tokIn"] for d in days),
        "tokOut": sum(d["tokOut"] for d in days),
    }


def compute_workgroup_daily(
    home: Path, wg_id: str, today: date | None = None,
) -> list[dict[str, Any]]:
    from alpi.alp import workgroup as alp_wg
    directory = alp_wg._wg_dir(home, wg_id)
    entries = alp_wg._read_transcript(directory)
    entries.extend(alp_wg._load_ledger(directory).get("settlements") or [])
    return bucket_workgroup(entries, today or _utc_today())


def _profile_model(home: Path) -> str:
    try:
        from alpi import config as cfg_mod
        return cfg_mod.load(home).model or ""
    except Exception:  # noqa: BLE001
        return ""


def daily_payload(home: Path) -> dict[str, Any]:
    """Canonical usage payload — host.usage.daily and the profile snapshot's usage section must stay identical."""
    return {
        "days": compute_daily(home),
        "total30": compute_total30(home),
        "priceOut": price_out(_profile_model(home)),
    }


async def _usage_daily(params: dict[str, Any], _server: host_server.Server) -> dict[str, Any]:
    profile = str((params or {}).get("profile") or "")
    home = _resolve_home(profile)
    # price_out imports litellm (slow first import) and may fetch OpenRouter pricing — keep it off the loop too.
    return await asyncio.to_thread(daily_payload, home)


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
    def _payload() -> dict[str, Any]:
        return {
            "days": compute_workgroup_daily(home, wg_id),
            "priceOut": price_out(_profile_model(home)),
        }
    return await asyncio.to_thread(_payload)


def compute_connection_daily(
    connection_id: str, today: date | None = None,
) -> list[dict[str, Any]]:
    day = today or _utc_today()
    return compute_all_connections_daily(day).get(
        connection_id,
        _window({}, day, USAGE_SPAN_DAYS),
    )


def compute_all_connections_daily(
    today: date | None = None,
) -> dict[str, list[dict[str, Any]]]:
    from alpi import ledger
    day = today or _utc_today()
    by_connection: dict[str, dict[str, dict[str, Any]]] = {}
    for profile in home_mod.list_profiles(home_mod._ROOT):
        snapshot = ledger.snapshot(home_mod.home_for(profile))
        for iso, entry in (snapshot.get("history") or {}).items():
            allocated_in = 0
            allocated_out = 0
            allocated_cost = 0.0
            for connection_id, row in ((entry or {}).get("by_connection") or {}).items():
                bucket = by_connection.setdefault(connection_id, {}).setdefault(
                    iso,
                    {"tokIn": 0, "tokOut": 0, "cost": 0.0},
                )
                tokens_in = int((row or {}).get("tokens_in") or 0)
                tokens_out = int((row or {}).get("tokens_out") or 0)
                cost = float((row or {}).get("usd") or 0.0)
                bucket["tokIn"] += tokens_in
                bucket["tokOut"] += tokens_out
                bucket["cost"] += cost
                allocated_in += tokens_in
                allocated_out += tokens_out
                allocated_cost += cost
            residual_in = max(0, int((entry or {}).get("tokens_in") or 0) - allocated_in)
            residual_out = max(0, int((entry or {}).get("tokens_out") or 0) - allocated_out)
            residual_cost = max(0.0, float((entry or {}).get("usd") or 0.0) - allocated_cost)
            if residual_in or residual_out or residual_cost:
                host = by_connection.setdefault("host", {}).setdefault(
                    iso,
                    {"tokIn": 0, "tokOut": 0, "cost": 0.0},
                )
                host["tokIn"] += residual_in
                host["tokOut"] += residual_out
                host["cost"] += residual_cost
    return {
        connection_id: _window(by_day, day, USAGE_SPAN_DAYS)
        for connection_id, by_day in by_connection.items()
    }


def _session_counts() -> tuple[dict[str, int], dict[str, float]]:
    from alpi.host.sessions import list_sessions
    counts: dict[str, int] = {}
    activity: dict[str, float] = {}
    for profile in home_mod.list_profiles(home_mod._ROOT):
        for row in list_sessions(home_mod.home_for(profile)):
            connection_id = str(row.get("connection_id") or "host")
            counts[connection_id] = counts.get(connection_id, 0) + 1
            activity[connection_id] = max(
                activity.get(connection_id, 0.0),
                float(row.get("updated_at") or 0.0),
            )
    return counts, activity


def connections_summary() -> dict[str, Any]:
    from alpi.host.connections import list_connections, public_connection
    counts, activity = _session_counts()
    now = int(datetime.now(timezone.utc).timestamp())
    all_usage = compute_all_connections_daily()
    host_days = all_usage.get("host", _window({}, _utc_today(), USAGE_SPAN_DAYS))
    rows: list[dict[str, Any]] = [{
        "id": "host",
        "label": "Host",
        "status": "active",
        "role": "admin",
        "profile_scope": [],
        "devices": [],
        "last_seen": now,
        "sessions": counts.get("host", 0),
        "usage_days": host_days,
        "cost_14d": round(sum(float(d["cost"]) for d in host_days), 6),
        "tokens_14d": sum(int(d["tokIn"]) + int(d["tokOut"]) for d in host_days),
    }]
    for stored in list_connections():
        row = public_connection(stored)
        days = all_usage.get(row["id"], _window({}, _utc_today(), USAGE_SPAN_DAYS))
        row["last_seen"] = max(
            int(row.get("last_seen") or 0),
            int(activity.get(row["id"], 0)),
        ) or None
        row["sessions"] = counts.get(row["id"], 0)
        row["usage_days"] = days
        row["cost_14d"] = round(sum(float(d["cost"]) for d in days), 6)
        row["tokens_14d"] = sum(int(d["tokIn"]) + int(d["tokOut"]) for d in days)
        rows.append(row)
    return {
        "connections": rows,
        "totals": {
            "paired": len(rows) - 1,
            "connected": sum(
                1 for row in rows[1:]
                if row["status"] == "active" and now - int(row.get("last_seen") or 0) < 180
            ),
            "sessions": sum(counts.values()),
            "cost_14d": round(sum(
                float(day["cost"])
                for days in all_usage.values()
                for day in days
            ), 6),
        },
    }


async def _connections_summary(
    _params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    return await asyncio.to_thread(connections_summary)


async def _connection_usage_daily(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    connection_id = str((params or {}).get("connection_id") or "")
    if not connection_id:
        raise host_server.HandlerError(-32602, "invalid-params", data={"detail": "connection_id required"})
    return {"days": await asyncio.to_thread(compute_connection_daily, connection_id)}
