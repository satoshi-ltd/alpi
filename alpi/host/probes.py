from __future__ import annotations

import asyncio
from typing import Any

from alpi.host import server as host_server


def register(server: host_server.Server) -> None:
    server.register("host.email.probe", _email_probe)
    server.register("host.peers.ping", _peers_ping)
    server.register("host.model.ctx_window", _model_ctx_window)


def _resolve_home(profile: str):
    from alpi.host.handlers import _resolve_home as _r
    return _r(profile)


async def _email_probe(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    from alpi.mail import accounts as accounts_mod

    profile = str(params.get("profile") or "")
    account_id = str(params.get("id") or "")
    home = _resolve_home(profile)
    account = accounts_mod.get_account(home, account_id)
    if account is None:
        raise host_server.HandlerError(
            -32602, "invalid-params",
            data={"detail": f"unknown email account {account_id!r}"},
        )

    return await asyncio.get_running_loop().run_in_executor(
        None, _email_probe_blocking, home, account_id, account,
    )


def _email_probe_blocking(home, account_id: str, account: dict) -> dict[str, Any]:
    import json
    from alpi.mail import accounts as accounts_mod

    if account.get("type") == "gmail":
        token_path = accounts_mod.gmail_token_path(home, account_id)
        if not token_path.exists():
            return {"status": "off"}
        try:
            tok = json.loads(token_path.read_text())
            expiry = tok.get("expiry") or tok.get("expires_at")
            refresh = tok.get("refresh_token")
            if not refresh and expiry:
                import datetime as _dt
                exp = _dt.datetime.fromisoformat(str(expiry).replace("Z", "+00:00"))
                if exp < _dt.datetime.now(_dt.timezone.utc):
                    return {"status": "error", "reason": "token expired"}
            return {"status": "on"}
        except Exception as e:  # noqa: BLE001
            return {"status": "error", "reason": str(e)[:80]}

    host = str(account.get("imap_host") or "").strip()
    if not host:
        return {"status": "off"}
    try:
        port = int(account.get("imap_port") or 993)
    except (TypeError, ValueError):
        port = 993
    try:
        import socket as _s
        with _s.create_connection((host, port), timeout=2.0):
            return {"status": "on"}
    except Exception as e:  # noqa: BLE001
        return {"status": "error", "reason": str(e)[:80]}


async def _peers_ping(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    profile = str(params.get("profile") or "")
    peer_id = str(params.get("peer_id") or "")
    if not peer_id:
        raise host_server.HandlerError(-32602, "invalid-params", data={"detail": "peer_id required"})
    home = _resolve_home(profile)

    from alpi.alp import client as alp_client
    from alpi.alp import peers as peers_mod
    from alpi.alp.keys import load_or_generate
    from pathlib import Path

    peer = peers_mod.get_by_id(home, peer_id)
    if peer is None:
        return {"status": "off", "reason": f"no peer {peer_id!r}"}

    sender = load_or_generate(home)
    # UI liveness check — default 30s freezes the dropdown on unreachable peers.
    try:
        if peer.address:
            host_, _, port_s = peer.address.rpartition(":")
            if not host_ or not port_s.isdigit():
                return {"status": "off", "reason": f"invalid address {peer.address!r}"}
            result = await alp_client.call_tcp(
                host=host_, port=int(port_s),
                sender=sender, recipient_pubkey_b64=peer.pubkey,
                method="link.ping", params={"nonce": "host-probe"},
                timeout=alp_client.PING_TIMEOUT_SECONDS,
            )
        else:
            socket_path = peers_mod.local_socket_path(peer)
            if not socket_path.exists():
                return {"status": "off", "reason": "target socket not found"}
            result = await alp_client.call(
                socket_path=socket_path,
                sender=sender, recipient_pubkey_b64=peer.pubkey,
                method="link.ping", params={"nonce": "host-probe"},
                timeout=alp_client.PING_TIMEOUT_SECONDS,
            )
    except alp_client.TargetOffline as e:
        return {"status": "off", "reason": f"target-offline: {e}"[:120]}
    except alp_client.ClientError as e:
        return {"status": "unverified", "reason": f"transport-error: {e}"[:120]}
    except alp_client.RemoteError as e:
        return {"status": "unverified", "reason": f"remote-error: {e}"[:120]}
    except Exception as e:  # noqa: BLE001
        return {"status": "off", "reason": str(e)[:120]}

    return {
        "status": "on",
        "agent_name": result.get("agent_name"),
        "version": result.get("version"),
        "nonce": result.get("nonce"),
    }


async def _model_ctx_window(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    profile = str(params.get("profile") or "")
    model = str(params.get("model") or "")
    if not model:
        raise host_server.HandlerError(-32602, "invalid-params", data={"detail": "model required"})
    home = _resolve_home(profile)
    from alpi import config as cfg_mod
    from alpi import ctx_window
    cfg = cfg_mod.load(home)
    return {"ctx_window": int(ctx_window.resolve(home, cfg, model))}


__all__ = ["register"]
