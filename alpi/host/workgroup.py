from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from alpi.alp import subscription as sub_mod
from alpi.alp import workgroup as wg_mod
from alpi.alp.keys import load_or_generate


def decrypt_transcript(
    home: Path,
    wg_id: str,
    *,
    after_seq: int | None = None,
    limit: int | None = None,
    tail: bool = False,
) -> list[dict[str, Any]]:
    """Return decrypted transcript posts, oldest-first.

    Pagination is mandatory once a transcript grows past a few hundred posts:
    decrypt cost is per-post (libsodium AEAD + JSON parse), so even with the
    group key opened once the linear walk dominates for chatty hubs. Callers
    pass ``after_seq`` for incremental updates or ``tail=True`` with ``limit``
    for first-paint of a large transcript.
    """
    raw = _read_jsonl(home, wg_id)
    if not raw:
        return []

    if after_seq is not None:
        raw = [p for p in raw if int(p.get("seq", 0)) > int(after_seq)]
        if not raw:
            return []
    if tail and limit is not None and limit > 0 and len(raw) > limit:
        raw = raw[-limit:]
    elif limit is not None and limit > 0 and len(raw) > limit:
        raw = raw[:limit]

    kp = load_or_generate(home)

    hub_dir = home / "alp" / "workgroups" / wg_id
    if (hub_dir / "members.yaml").exists():
        return _decrypt_as_hub(home, wg_id, kp, raw)

    sub = sub_mod.get(home, wg_id)
    if sub is not None:
        return _decrypt_as_member(sub, kp, raw)

    return []


def _read_jsonl(home: Path, wg_id: str) -> list[dict[str, Any]]:
    p = home / "alp" / "workgroups" / wg_id / "transcript.jsonl"
    if not p.exists():
        return []
    out: list[dict[str, Any]] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(entry, dict):
            out.append(entry)
    return out


def _decrypt_as_hub(
    home: Path, wg_id: str, kp, raw: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    wg = wg_mod.load(home, wg_id)
    if wg is None:
        return []
    me = wg.member(kp.pubkey_b64())
    if me is None:
        return []
    cur_version = me.key_version
    # Open the sealed group key ONCE outside the loop — used to be reopened per-post (O(N) Curve25519 unseals on every transcript fetch, ~10ms each on a busy hub).
    try:
        group_key = wg_mod.open_sealed_group_key(me.sealed_key, kp)
    except Exception as e:  # noqa: BLE001
        # Hub cannot unseal its own key — degrade gracefully, never return half-decrypted state.
        group_key = None
        unseal_error = str(e)
    else:
        unseal_error = ""

    handles = _handle_map(home, wg)
    out: list[dict[str, Any]] = []
    for post in raw:
        v = int(post.get("key_version", 1))
        sender_pk = str(post.get("from") or "")
        body: str
        if v != cur_version:
            body = f"[v{v} key rotated out of hub state]"
        elif group_key is None:
            body = f"[decrypt failed: {unseal_error}]"
        else:
            try:
                body = wg_mod.decrypt_post(
                    group_key, post["nonce"], post["ciphertext"],
                ).decode("utf-8", errors="replace")
            except Exception as e:  # noqa: BLE001
                body = f"[decrypt failed: {e}]"
        out.append(_envelope(post, sender_pk, handles.get(sender_pk, ""), body))
    return out


def _decrypt_as_member(
    sub, kp, raw: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for post in raw:
        sender_pk = str(post.get("from") or "")
        try:
            body = sub_mod.decrypt_post(sub, kp, post).decode(
                "utf-8", errors="replace",
            )
        except Exception as e:  # noqa: BLE001
            body = f"[decrypt failed: {e}]"
        out.append(_envelope(post, sender_pk, "", body))
    return out


def _handle_map(home: Path, wg) -> dict[str, str]:
    out: dict[str, str] = {}
    try:
        from alpi.alp import peers as peers_mod

        for p in peers_mod.load(home):
            out[p.pubkey] = f"@{p.id}"
    except Exception:  # noqa: BLE001
        pass
    try:
        from alpi.alp.keys import load_or_generate as _load

        kp = _load(home)
        out.setdefault(kp.pubkey_b64(), f"@{_local_handle(home)}")
    except Exception:  # noqa: BLE001
        pass
    return out


def _local_handle(home: Path) -> str:
    parts = home.parts
    if "profiles" in parts:
        i = parts.index("profiles")
        if i + 1 < len(parts):
            return parts[i + 1]
    return "default"


def _envelope(
    post: dict[str, Any], sender_pk: str, handle: str, body: str,
) -> dict[str, Any]:
    return {
        "seq": int(post.get("seq", 0)),
        "at": str(post.get("ts") or ""),
        "from_pubkey": sender_pk,
        "from": handle,
        "body": body,
        "key_version": int(post.get("key_version", 1)),
        "cost": post.get("cost") or {},
    }
