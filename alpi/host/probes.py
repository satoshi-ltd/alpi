from __future__ import annotations

import asyncio
from typing import Any

from alpi.host import server as host_server


def register(server: host_server.Server) -> None:
    server.register("host.gateway.probe", _gateway_probe)
    server.register("host.peers.ping", _peers_ping)
    server.register("host.model.ctx_window", _model_ctx_window)


def _resolve_home(profile: str):
    from alpi.host.handlers import _resolve_home as _r
    return _r(profile)


_GATEWAYS = {"telegram", "imap", "gmail", "matrix"}


async def _gateway_probe(
    params: dict[str, Any], _server: host_server.Server,
) -> dict[str, Any]:
    profile = str(params.get("profile") or "")
    name = str(params.get("name") or "")
    if name not in _GATEWAYS:
        raise host_server.HandlerError(
            -32602, "invalid-params",
            data={"detail": f"unknown gateway {name!r}"},
        )
    home = _resolve_home(profile)

    return await asyncio.get_running_loop().run_in_executor(
        None, _gateway_probe_blocking, home, name,
    )


def _gateway_probe_blocking(home, name: str) -> dict[str, Any]:
    import json

    env = _read_profile_env(home)

    if name == "telegram":
        token = (env.get("TELEGRAM_BOT_TOKEN") or "").strip()
        if not token:
            return {"status": "off"}
        try:
            import urllib.request as _ur
            with _ur.urlopen(
                f"https://api.telegram.org/bot{token}/getMe", timeout=2.0,
            ) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            if body.get("ok"):
                return {"status": "on"}
            return {"status": "error", "reason": "token rejected"}
        except Exception as e:  # noqa: BLE001
            return {"status": "error", "reason": str(e)[:80]}

    if name == "imap":
        addr = (env.get("IMAP_ADDRESS") or "").strip()
        if not addr:
            return {"status": "off"}
        host = (env.get("IMAP_HOST") or "").strip() or "imap.gmail.com"
        try:
            port = int((env.get("IMAP_PORT") or "993").strip() or "993")
        except ValueError:
            port = 993
        try:
            import socket as _s
            with _s.create_connection((host, port), timeout=2.0):
                return {"status": "on"}
        except Exception as e:  # noqa: BLE001
            return {"status": "error", "reason": str(e)[:80]}

    if name == "gmail":
        client_id = (env.get("GMAIL_CLIENT_ID") or "").strip()
        token_path = home / "secrets" / "gmail_token.json"
        if not client_id and not token_path.exists():
            return {"status": "off"}
        if not token_path.exists():
            return {"status": "error", "reason": "no token file"}
        try:
            tok = json.loads(token_path.read_text())
            expiry = tok.get("expiry") or tok.get("expires_at")
            refresh = tok.get("refresh_token")
            if not refresh and expiry:
                import datetime as _dt
                exp = _dt.datetime.fromisoformat(expiry.replace("Z", "+00:00"))
                if exp < _dt.datetime.now(_dt.timezone.utc):
                    return {"status": "error", "reason": "token expired"}
            return {"status": "on"}
        except Exception as e:  # noqa: BLE001
            return {"status": "error", "reason": str(e)[:80]}

    if name == "matrix":
        token = (env.get("MATRIX_ACCESS_TOKEN") or "").strip()
        url = (env.get("MATRIX_HOMESERVER_URL") or "").strip()
        if not token or not url:
            return {"status": "off"}
        try:
            import urllib.request as _ur
            req = _ur.Request(
                f"{url.rstrip('/')}/_matrix/client/r0/account/whoami",
                headers={"Authorization": f"Bearer {token}"},
            )
            with _ur.urlopen(req, timeout=2.0) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            if body.get("user_id"):
                return {"status": "on"}
            return {"status": "error", "reason": "whoami missing user_id"}
        except Exception as e:  # noqa: BLE001
            return {"status": "error", "reason": str(e)[:80]}

    return {"status": "off"}


def _read_profile_env(home) -> dict[str, str]:
    out: dict[str, str] = {}
    env_path = home / ".env"
    try:
        lines = env_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return out
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        out[key.strip()] = value.strip().strip('"').strip("'")
    return out


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
            target_home = (
                Path.home() / ".alpi" if peer_id == "default"
                else Path.home() / ".alpi" / "profiles" / peer_id
            )
            socket_path = target_home / "alp" / "alp.sock"
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
