"""Workgroup CRUD over the host control plane.

Mirrors the surface that ``alpi workgroup …`` commands and the desktop
app expose. Mobile clients call these verbs to create / edit / manage
workgroups without shelling out to the CLI.
"""

from __future__ import annotations

from typing import Any

from alpi.host import server as host_server


def register(server: host_server.Server) -> None:
    server.register("host.workgroup.create", _create)
    server.register("host.workgroup.update", _update)
    server.register("host.workgroup.add_member", _add_member)
    server.register("host.workgroup.kick", _kick)
    server.register("host.workgroup.remove", _remove)
    server.register("host.workgroup.action", _action)
    server.register("host.workgroup.post", _post)


def _resolve_home(profile: str):
    from alpi.host.handlers import _resolve_home as _r
    return _r(profile)


def _check_id(value: str, kind: str) -> None:
    from alpi.host.handlers import _check_id as _c
    _c(value, kind)


def _resolve_peer(home, ref: str) -> str:
    """``ref`` can be a pinned peer id or a raw pubkey. Resolve to pubkey."""
    from alpi.alp import peers as peers_mod
    peer = peers_mod.get_by_id(home, ref)
    return peer.pubkey if peer else ref


def _emit_workgroup_changed(home, wg_id: str, action: str) -> None:
    from alpi import home as home_mod
    from alpi.host import events as host_events
    host_events.emit("workgroup_changed", {
        "profile": home_mod.profile_name(home),
        "wg_id": wg_id,
        "action": action,
    })


def _emit_workgroup_members(home, wg_id: str, members: int, key_version: int) -> None:
    from alpi import home as home_mod
    from alpi.host import events as host_events
    host_events.emit("workgroup_members", {
        "profile": home_mod.profile_name(home),
        "wg_id": wg_id,
        "members": members,
        "key_version": key_version,
    })


async def _create(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    profile = str(params.get("profile") or "")
    name = str(params.get("name") or "").strip()
    members_raw = params.get("members") or params.get("member_peer_ids") or []
    if not name:
        raise host_server.HandlerError(-32602, "invalid-params", data={"detail": "name required"})
    if not isinstance(members_raw, list):
        raise host_server.HandlerError(-32602, "invalid-params", data={"detail": "members must be a list"})

    home = _resolve_home(profile)
    pubkeys = [_resolve_peer(home, str(m).strip()) for m in members_raw if str(m).strip()]

    budget: dict[str, Any] = {}
    if params.get("budget_usd") is not None:
        try:
            budget["max_usd"] = float(params["budget_usd"])
        except (TypeError, ValueError):
            raise host_server.HandlerError(-32602, "invalid-params", data={"detail": "budget_usd must be a number"})

    briefing = str(params.get("briefing") or "").strip()

    # Ordered pipeline phase slugs — a list, or a comma-separated string from
    # a UI field. Empty = a normal deliberation workgroup.
    pipeline_raw = params.get("pipeline") or []
    if isinstance(pipeline_raw, str):
        pipeline_raw = [p.strip() for p in pipeline_raw.split(",") if p.strip()]

    pipeline_steps = params.get("pipeline_steps") or None
    quorum_raw = params.get("quorum_timeout_seconds")
    quorum = int(quorum_raw) if isinstance(quorum_raw, (int, float)) else 0

    from alpi import config as cfg_mod
    from alpi.alp import workgroup as wg_mod
    from alpi.alp.keys import load_or_generate

    hub_cfg = cfg_mod.load(home)
    hub_bio = (hub_cfg.public_bio or "").strip()
    hub_voice = (hub_cfg.tools.tts.voice or "").strip()
    try:
        wg = wg_mod.create(
            home,
            name=name,
            hub_kp=load_or_generate(home),
            member_pubkeys=pubkeys,
            budget=budget,
            briefing=briefing,
            pipeline=pipeline_raw,
            pipeline_steps=pipeline_steps,
            quorum_timeout_seconds=quorum,
            hub_bio=hub_bio,
            hub_voice=hub_voice,
        )
    except ValueError as e:
        raise host_server.HandlerError(-32602, "invalid-params", data={"detail": str(e)})

    _emit_workgroup_changed(home, wg.meta.id, "created")
    return {"wg_id": wg.meta.id, "members": len(wg.members)}


async def _update(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    profile = str(params.get("profile") or "")
    wg_id = str(params.get("wg_id") or "").strip()
    _check_id(wg_id, "wg_id")
    home = _resolve_home(profile)

    from alpi.alp import workgroup as wg_mod
    from alpi.alp.keys import load_or_generate

    wg = wg_mod.load(home, wg_id)
    if wg is None:
        raise host_server.HandlerError(-32004, "not-found", data={"detail": f"workgroup {wg_id!r} not found"})
    own_pubkey = load_or_generate(home).pubkey_b64()
    if wg.meta.hub_pubkey != own_pubkey:
        raise host_server.HandlerError(-32001, "forbidden", data={"detail": "only the hub can edit this workgroup"})

    clear_budget = bool(params.get("clear_budget", False))
    budget_usd = params.get("budget_usd")
    if budget_usd is not None and clear_budget:
        raise host_server.HandlerError(
            -32602, "invalid-params",
            data={"detail": "budget_usd and clear_budget are mutually exclusive"},
        )

    changes: list[str] = []
    briefing = params.get("briefing")
    if briefing is not None:
        wg.meta.briefing = str(briefing).strip()
        changes.append("briefing")
    pipeline = params.get("pipeline")
    if pipeline is not None:
        # List, or a comma-separated string from a UI field. Empty clears it.
        if isinstance(pipeline, str):
            pipeline = [p.strip() for p in pipeline.split(",") if p.strip()]
        try:
            wg.meta.pipeline = wg_mod._normalize_pipeline(pipeline)
        except ValueError as e:
            raise host_server.HandlerError(-32602, "invalid-params", data={"detail": str(e)})
        changes.append("pipeline")
    if clear_budget:
        wg.meta.budget = {}
        changes.append("budget cleared")
    elif budget_usd is not None:
        try:
            v = float(budget_usd)
        except (TypeError, ValueError):
            raise host_server.HandlerError(-32602, "invalid-params", data={"detail": "budget_usd must be a number"})
        if v <= 0:
            raise host_server.HandlerError(-32602, "invalid-params", data={"detail": "budget_usd must be > 0"})
        try:
            wg.meta.budget = wg_mod._validate_budget({"max_usd": v})
        except ValueError as e:
            raise host_server.HandlerError(-32602, "invalid-params", data={"detail": str(e)})
        changes.append(f"budget=${v:.2f}")
    auto_read = params.get("auto_read")
    if auto_read is not None:
        wg.meta.auto_read = bool(auto_read)
        changes.append(f"auto_read={wg.meta.auto_read}")

    if not changes:
        raise host_server.HandlerError(
            -32602, "invalid-params",
            data={"detail": "nothing to update — pass briefing, pipeline, budget_usd, clear_budget or auto_read"},
        )

    wg_mod._save_meta(wg_mod._wg_dir(home, wg_id), wg.meta)
    _emit_workgroup_changed(home, wg_id, "updated")
    return {"ok": True, "changes": changes}


async def _add_member(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    profile = str(params.get("profile") or "")
    wg_id = str(params.get("wg_id") or "").strip()
    member = str(params.get("member") or "").strip()
    if not member:
        raise host_server.HandlerError(-32602, "invalid-params", data={"detail": "member required"})
    _check_id(wg_id, "wg_id")
    home = _resolve_home(profile)
    target = _resolve_peer(home, member)

    from alpi.alp import workgroup as wg_mod
    from alpi.alp import workgroup_setup as wg_setup

    try:
        updated = wg_mod.add_member(home, wg_id, target)
    except ValueError as e:
        raise host_server.HandlerError(-32602, "invalid-params", data={"detail": str(e)})
    wg_setup._grant_workgroup_verbs(home, [target])
    _emit_workgroup_members(home, wg_id, len(updated.members), updated.meta.current_key_version)
    return {
        "ok": True,
        "key_version": updated.meta.current_key_version,
        "members": len(updated.members),
    }


async def _kick(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    profile = str(params.get("profile") or "")
    wg_id = str(params.get("wg_id") or "").strip()
    member = str(params.get("member") or "").strip()
    if not member:
        raise host_server.HandlerError(-32602, "invalid-params", data={"detail": "member required"})
    _check_id(wg_id, "wg_id")
    home = _resolve_home(profile)
    target = _resolve_peer(home, member)

    from alpi.alp import workgroup as wg_mod
    try:
        updated = wg_mod.kick(home, wg_id, target)
    except ValueError as e:
        raise host_server.HandlerError(-32602, "invalid-params", data={"detail": str(e)})
    _emit_workgroup_members(home, wg_id, len(updated.members), updated.meta.current_key_version)
    return {
        "ok": True,
        "key_version": updated.meta.current_key_version,
        "members": len(updated.members),
    }


async def _remove(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    """Hub-only: delete a workgroup (transcript + members) and cascade
    to local subscriptions on this machine. Mirrors ``workgroup remove``."""
    profile = str(params.get("profile") or "")
    wg_id = str(params.get("wg_id") or "").strip()
    _check_id(wg_id, "wg_id")
    home = _resolve_home(profile)

    from alpi.alp import workgroup as wg_mod
    from alpi.alp.keys import load_or_generate

    wg = wg_mod.load(home, wg_id)
    if wg is None:
        raise host_server.HandlerError(-32004, "not-found", data={"detail": f"workgroup {wg_id!r} not found"})
    own_pubkey = load_or_generate(home).pubkey_b64()
    if wg.meta.hub_pubkey != own_pubkey:
        raise host_server.HandlerError(-32001, "forbidden", data={"detail": "only the hub can remove this workgroup"})

    try:
        purged = wg_mod.remove(home, wg_id)
    except OSError as e:
        raise host_server.HandlerError(-32603, "internal-error", data={"detail": str(e)})

    _emit_workgroup_changed(home, wg_id, "removed")
    return {"ok": True, "purged": sorted(set(purged))}


_VALID_ACTIONS = {"pause", "resume", "leave"}


async def _action(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    """Pause / resume / leave a workgroup. ``pause`` and ``resume`` are
    hub-side mutations (no roundtrip); ``leave`` is a member-side ALP
    call to the hub."""
    action = str(params.get("action") or "").strip()
    if action not in _VALID_ACTIONS:
        raise host_server.HandlerError(-32602, "invalid-params", data={"detail": f"invalid action: {action!r}"})
    profile = str(params.get("profile") or "")
    wg_id = str(params.get("wg_id") or "").strip()
    _check_id(wg_id, "wg_id")
    home = _resolve_home(profile)

    from alpi.alp import workgroup_client as wc
    fn = getattr(wc, action)
    try:
        await fn(home, wg_id)
    except Exception as e:  # noqa: BLE001
        raise host_server.HandlerError(-32603, "internal-error", data={"detail": str(e)})
    # pause/resume/leave change observable state for every subscribed client; without an emit other apps would only notice on next manual reload.
    _emit_workgroup_changed(home, wg_id, action)
    return {"ok": True, "action": action}


async def _post(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    """Encrypt + post a message to a workgroup we are subscribed to."""
    profile = str(params.get("profile") or "")
    wg_id = str(params.get("wg_id") or "").strip()
    text = str(params.get("text") or "")
    if not text:
        raise host_server.HandlerError(-32602, "invalid-params", data={"detail": "text required"})
    _check_id(wg_id, "wg_id")
    home = _resolve_home(profile)

    from alpi.alp import workgroup_client as wc
    try:
        result = await wc.post(home, wg_id, text.encode("utf-8"))
    except Exception as e:  # noqa: BLE001
        raise host_server.HandlerError(-32603, "internal-error", data={"detail": str(e)})
    return {"ok": True, "seq": result.get("seq") if isinstance(result, dict) else None}


__all__ = ["register"]
