"""Member-side workgroup helpers."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from alpi.alp import client as alp_client
from alpi.alp import peers as peers_mod
from alpi.alp import subscription as sub_mod
from alpi.alp import tasks as tasks_mod
from alpi.alp import workgroup as wg_mod
from alpi.alp.keys import Keypair, load_or_generate


def _last_hub_seq(posts: list[dict], hub_pubkey: str) -> int:
    """Highest hub-authored seq in `posts`, or 0."""
    best = 0
    for p in posts:
        if str(p.get("from") or "") == hub_pubkey:
            seq = int(p.get("seq", 0))
            if seq > best:
                best = seq
    return best


def _current_round_posts(
    posts: list[dict], hub_pubkey: str,
) -> list[dict]:
    """Posts after the latest hub post."""
    cutoff = _last_hub_seq(posts, hub_pubkey)
    if cutoff == 0:
        return list(posts)
    return [p for p in posts if int(p.get("seq", 0)) > cutoff]


def _check_member_rotation(
    posts: list[dict], own_pubkey: str, hub_pubkey: str,
    plaintext: str = "",
) -> None:
    """Reject posts that would violate member rotation."""
    round_posts = _current_round_posts(posts, hub_pubkey)
    own_in_round = [
        p for p in round_posts
        if str(p.get("from") or "") == own_pubkey
    ]
    new_is_working = tasks_mod.is_working(plaintext)
    prior_working = sum(
        1 for p in own_in_round
        if tasks_mod.is_working(str(p.get("text") or ""))
    )
    prior_consuming = len(own_in_round) - prior_working

    if new_is_working:
        if prior_working >= 1:
            raise ValueError(
                "turn-rotation: you already posted `#working` in "
                "this round. Wait until you have substantive "
                "content or `#skip` to post again."
            )
        return
    if prior_consuming >= 1:
        raise ValueError(
            "turn-rotation: you already posted in the current "
            "round (since the hub's last post). Stay silent until "
            "the hub speaks again."
        )


def _check_member_round_fresh(
    posts: list[dict], hub_pubkey: str,
) -> None:
    """Reject stale-round posts when the dispatcher already advanced."""
    raw = os.environ.get("ALPI_WORKGROUP_ROUND_HUB_SEQ", "").strip()
    if not raw:
        return
    try:
        trigger_seq = int(raw)
    except ValueError:
        return
    current = _last_hub_seq(posts, hub_pubkey)
    if current > trigger_seq:
        raise ValueError(
            f"stale-round: the hub posted again (seq #{current}) "
            f"while this turn was thinking — your reaction was for "
            f"round seq #{trigger_seq}. Aborting; the next poller "
            f"tick will re-evaluate against fresh state."
        )


def _check_substantive(plaintext: str) -> None:
    """Reject empty posts before they burn a slot."""
    if not (plaintext or "").strip():
        raise ValueError(
            "empty post — silence in a workgroup is the absence of "
            "a workgroup_post call, not an empty post."
        )


_FULL_QUORUM_TIMEOUT_SECONDS = 10 * 60


def _opener_post(
    posts: list[dict], hub_pubkey: str,
) -> dict | None:
    """Return the active `#task` opener, if any."""
    opener: dict | None = None
    for p in posts:
        if str(p.get("from") or "") != hub_pubkey:
            continue
        events = tasks_mod.parse_post(
            str(p.get("text") or ""),
            int(p.get("seq", 0)),
            str(p.get("from") or ""),
        )
        if any(e.kind == "task" for e in events):
            opener = p
        elif any(e.kind == "done" for e in events):
            opener = None
    return opener


def _check_hub_rotation(
    posts: list[dict], own_pubkey: str, plaintext: str,
    member_pubkeys: list[str] | None = None,
) -> None:
    """Reject hub back-to-back content or premature `#done`."""
    if not posts:
        return
    last_contributing = None
    for p in reversed(posts):
        if not tasks_mod.is_working(str(p.get("text") or "")):
            last_contributing = p
            break
    is_back_to_back = (
        last_contributing is not None
        and str(last_contributing.get("from") or "") == own_pubkey
    )

    if tasks_mod.is_task(plaintext):
        return

    if tasks_mod.is_done(plaintext):
        opener = _opener_post(posts, own_pubkey)
        if opener is None:
            if not is_back_to_back:
                return
            raise ValueError(
                "turn-rotation: no active task to close, and you "
                "(hub) were the most recent poster. Wait for a "
                "member to speak before posting again."
            )
        opener_seq = int(opener.get("seq", 0))
        in_task = [
            p for p in posts if int(p.get("seq", 0)) > opener_seq
        ]

        def _is_marker_only(text: str) -> bool:
            return tasks_mod.is_skip(text) or tasks_mod.is_working(text)

        non_hub_substantive = any(
            str(p.get("from") or "") != own_pubkey
            and not _is_marker_only(str(p.get("text") or ""))
            for p in in_task
        )
        age = _opener_age_seconds(opener)
        if not non_hub_substantive and age < _FULL_QUORUM_TIMEOUT_SECONDS:
            raise ValueError(
                "closure-quorum: no substantive peer input yet. "
                f"Wait for content or the {_FULL_QUORUM_TIMEOUT_SECONDS // 60}-minute timeout "
                f"({int(age)}s elapsed)."
            )
        expected = [
            pk for pk in (member_pubkeys or [])
            if pk and pk != own_pubkey
        ]
        if expected:
            spoken = {
                str(p.get("from") or "")
                for p in in_task
                if not tasks_mod.is_working(
                    str(p.get("text") or "")
                )
            }
            pending = [pk for pk in expected if pk not in spoken]
            if pending and age < _FULL_QUORUM_TIMEOUT_SECONDS:
                short = [f"{pk[:12]}…" for pk in pending]
                raise ValueError(
                    f"closure-quorum: {len(pending)} member(s) still "
                    f"pending ({', '.join(short)}); wait for content, "
                    f"`#skip`, or timeout."
                )
        return  # Closure is allowed.

    if not is_back_to_back:
        return  # Someone else spoke last; new round, hub may speak.
    raise ValueError(
        "turn-rotation: hub spoke last. Wait for a member or use `#done`."
    )


def _opener_age_seconds(opener: dict) -> float:
    """Seconds since the opener timestamp; 0 on parse failure."""
    import datetime as _dt
    ts = str(opener.get("ts") or "").strip()
    if not ts:
        return 0.0
    try:
        opened_dt = _dt.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ")
        opened_dt = opened_dt.replace(tzinfo=_dt.timezone.utc)
    except ValueError:
        return 0.0
    return (_dt.datetime.now(tz=_dt.timezone.utc) - opened_dt).total_seconds()


@dataclass
class _Resolved:
    socket_path: Path | None
    host: str | None
    port: int | None
    hub_pubkey: str

    def is_tcp(self) -> bool:
        return self.host is not None and self.port is not None


def _resolve_hub(home: Path, peer_id: str) -> _Resolved:
    """Resolve the hub and transport from `peers.yaml`."""
    peer = peers_mod.get_by_id(home, peer_id)
    if peer is None:
        raise ValueError(f"peer {peer_id!r} not pinned in this profile's peers.yaml")
    if peer.address:
        host, _, port_s = peer.address.rpartition(":")
        if not host or not port_s.isdigit():
            raise ValueError(f"peer {peer_id!r} has invalid address {peer.address!r}")
        return _Resolved(
            socket_path=None, host=host, port=int(port_s), hub_pubkey=peer.pubkey,
        )
    socket_path = _intra_socket_path(peer_id)
    return _Resolved(
        socket_path=socket_path, host=None, port=None, hub_pubkey=peer.pubkey,
    )


def _intra_socket_path(peer_id: str) -> Path:
    """Return the intra-machine socket path for `peer_id`."""
    if peer_id == "default":
        return Path.home() / ".alpi" / "alp" / "alp.sock"
    return Path.home() / ".alpi" / "profiles" / peer_id / "alp" / "alp.sock"


async def _call(home: Path, kp: Keypair, peer_id: str, method: str,
                params: dict[str, Any]) -> dict[str, Any]:
    res = _resolve_hub(home, peer_id)
    if res.is_tcp():
        return await alp_client.call_tcp(
            host=res.host, port=res.port,
            sender=kp, recipient_pubkey_b64=res.hub_pubkey,
            method=method, params=params,
        )
    return await alp_client.call(
        socket_path=res.socket_path,
        sender=kp, recipient_pubkey_b64=res.hub_pubkey,
        method=method, params=params,
    )


async def join(home: Path, peer_id: str, wg_id: str) -> sub_mod.Subscription:
    """Join the hub and persist the subscription locally; broadcasts public_bio + voice on the way in."""
    kp = load_or_generate(home)
    from alpi import config as _cfg
    cfg = _cfg.load(home)
    bio = (cfg.public_bio or "").strip()
    voice = (cfg.tools.tts.voice or "").strip()
    params: dict[str, Any] = {"workgroup_id": wg_id}
    if bio:
        params["bio"] = bio
    if voice:
        params["voice"] = voice
    result = await _call(home, kp, peer_id, "workgroup.join", params)
    res = _resolve_hub(home, peer_id)
    sub = sub_mod.get(home, wg_id) or sub_mod.Subscription(
        wg_id=wg_id,
        name=str(result.get("name") or ""),
        hub_id=peer_id,
        hub_pubkey=res.hub_pubkey,
    )
    if not sub.joined_at:
        import datetime as _dt
        sub.joined_at = _dt.datetime.now(tz=_dt.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ",
        )
    if not sub.name:
        sub.name = str(result.get("name") or "")
    sub.briefing = str(result.get("briefing") or "")
    sub.upsert_key(int(result.get("key_version", 1)), str(result["sealed_key"]))
    _absorb_roster(sub, result.get("members"))
    sub_mod.upsert(home, sub)
    return sub


def _absorb_roster(sub: sub_mod.Subscription, raw) -> None:
    """Normalize roster shapes into `roster` plus `roster_bios`/`roster_voices`."""
    if not raw:
        return
    seen: dict[str, str] = {}
    bios: dict[str, str] = {}
    voices: dict[str, str] = {}
    for entry in raw:
        if isinstance(entry, dict) and "pubkey" in entry:
            pk = str(entry["pubkey"])
            seen[pk] = str(entry.get("last_seen_at") or "")
            bio = str(entry.get("bio") or "").strip()
            if bio:
                bios[pk] = bio
            voice = str(entry.get("voice") or "").strip()
            if voice:
                voices[pk] = voice
        elif isinstance(entry, str):
            seen[entry] = ""
    if seen:
        sub.roster = seen
    sub.roster_bios = bios
    sub.roster_voices = voices


async def post(
    home: Path, wg_id: str, text: bytes,
    cost: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Encrypt `text` under the latest key and send it to the hub."""
    kp = load_or_generate(home)

    try:
        _plaintext = text.decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        _plaintext = ""
    _check_substantive(_plaintext)

    wg = wg_mod.load(home, wg_id)
    if wg is not None and wg.meta.hub_pubkey == kp.pubkey_b64():
        result = _post_as_hub(home, wg, kp, text, cost)
        _emit_wg_post(home, wg_id, result)
        if tasks_mod.is_done(_plaintext):
            try:
                from alpi.host import events as host_events
                from alpi.home import profile_name
                host_events.emit("wg.done", {
                    "profile": profile_name(home),
                    "wg_id": wg_id,
                    "seq": result.get("seq") if isinstance(result, dict) else None,
                    "summary": _plaintext[:200],
                })
            except Exception:  # noqa: BLE001
                pass
        return result

    sub = sub_mod.get(home, wg_id)
    if sub is None:
        raise ValueError(
            f"not subscribed to {wg_id!r} — run `alpi workgroup join` first",
        )
    try:
        plaintext = text.decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        plaintext = ""
    found_markers = tasks_mod.has_markers(plaintext)
    if found_markers:
        raise ValueError(
            "only the workgroup hub may post #"
            + "/#".join(found_markers)
            + " markers — non-hub members must stay silent."
        )

    try:
        await pull(home, wg_id)
    except Exception:  # noqa: BLE001
        pass
    sub = sub_mod.get(home, wg_id) or sub
    posts_view = list(sub.recent_posts or [])
    _check_member_round_fresh(posts_view, sub.hub_pubkey)
    _check_member_rotation(
        posts_view, kp.pubkey_b64(), sub.hub_pubkey, plaintext,
    )

    version = sub.latest_version()
    if version == 0:
        raise ValueError(f"no group key cached for {wg_id!r}; re-join")
    sealed = sub.sealed_for(version)
    group_key = wg_mod.open_sealed_group_key(sealed, kp)
    nonce, ct = wg_mod.encrypt_post(group_key, text)
    params: dict[str, Any] = {
        "workgroup_id": wg_id,
        "key_version": version,
        "nonce": nonce,
        "ciphertext": ct,
    }
    if cost:
        params["cost"] = cost
    result = await _call(home, kp, sub.hub_id, "workgroup.post", params)
    _emit_wg_post(home, wg_id, result)
    return result


def _emit_wg_post(home: Path, wg_id: str, result: dict[str, Any] | None) -> None:
    """wg.post fires on every successful post; wg.done is reserved for #done markers."""
    try:
        from alpi.host import events as host_events
        from alpi.home import profile_name
        host_events.emit("wg.post", {
            "profile": profile_name(home),
            "wg_id": wg_id,
            "seq": result.get("seq") if isinstance(result, dict) else None,
        })
    except Exception:  # noqa: BLE001
        pass


def _post_as_hub(
    home: Path, wg, kp: Keypair, text: bytes,
    cost: dict[str, Any] | None,
) -> dict[str, Any]:
    """Write a hub post directly into the local transcript."""
    import datetime as _dt
    import json
    from alpi.alp.workgroup import (
        _append_transcript, _gate_post, _load_ledger, _save_ledger,
        _read_transcript, _wg_dir,
    )

    own = wg.member(kp.pubkey_b64())
    if own is None:
        raise ValueError("hub is not a member of its own workgroup")
    if wg.meta.paused:
        raise ValueError("workgroup is paused")

    cost_dict = dict(cost) if cost else {}
    d = _wg_dir(home, wg.meta.id)
    ledger = _load_ledger(d)

    try:
        _gate_post(wg.meta, ledger, cost_dict)
    except Exception as e:  # noqa: BLE001
        raise ValueError(str(e)) from e

    existing_raw = _read_transcript(d)

    try:
        group_key_for_check = wg_mod.open_sealed_group_key(
            own.sealed_key, kp,
        )
    except Exception:  # noqa: BLE001
        group_key_for_check = None
    existing: list[dict[str, Any]] = []
    for entry in existing_raw:
        if (
            group_key_for_check is None
            or int(entry.get("key_version", 1)) != own.key_version
        ):
            existing.append({**entry, "text": ""})
            continue
        try:
            decrypted_bytes = wg_mod.decrypt_post(
                group_key_for_check,
                entry["nonce"],
                entry["ciphertext"],
            )
            existing.append({
                **entry,
                "text": decrypted_bytes.decode("utf-8", errors="replace"),
            })
        except Exception:  # noqa: BLE001
            existing.append({**entry, "text": ""})

    try:
        plaintext = text.decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        plaintext = ""

    if tasks_mod.is_skip(plaintext):
        raise ValueError(
            "hub-cannot-skip: `#skip` is the member-side pass "
            "signal. As hub you don't skip your own task — open "
            "with `#task`, contribute substantively, or close "
            "with `#done`."
        )
    if tasks_mod.is_working(plaintext):
        raise ValueError(
            "hub-cannot-working: `#working` is the member-side "
            "heartbeat for slow tool work. As hub you orchestrate "
            "the workgroup — you don't need to signal processing. "
            "Either post substantive prose to push the discussion "
            "forward, or post `#done` when the deliverable is in "
            "the transcript."
        )

    member_pubkeys = [m.pubkey for m in wg.members]
    _check_hub_rotation(
        existing, kp.pubkey_b64(), plaintext, member_pubkeys,
    )

    group_key = wg_mod.open_sealed_group_key(own.sealed_key, kp)
    nonce, ct = wg_mod.encrypt_post(group_key, text)

    seq = (existing[-1]["seq"] + 1) if existing else 1
    ts = _dt.datetime.now(tz=_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    entry: dict[str, Any] = {
        "seq": seq, "ts": ts, "from": kp.pubkey_b64(),
        "key_version": own.key_version, "nonce": nonce, "ciphertext": ct,
    }
    declared_usd = float(cost_dict.get("usd", 0.0)) if cost_dict else 0.0
    declared_tokens = int(cost_dict.get("tokens", 0)) if cost_dict else 0
    if declared_usd or declared_tokens:
        entry["cost"] = {"usd": declared_usd, "tokens": declared_tokens}
    _append_transcript(d, entry)

    ledger["usd"] = float(ledger.get("usd", 0.0)) + declared_usd
    ledger["tokens"] = int(ledger.get("tokens", 0)) + declared_tokens
    ledger["posts"] = int(ledger.get("posts", 0)) + 1
    _save_ledger(d, ledger)
    return {"seq": seq, "ts": ts}


async def pull(
    home: Path, wg_id: str, *, since: int | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """Fetch, decrypt, and cache new posts."""
    kp = load_or_generate(home)
    sub = sub_mod.get(home, wg_id)
    if sub is None:
        raise ValueError(
            f"not subscribed to {wg_id!r} — run `alpi workgroup join` first",
        )
    cursor = sub.last_seq if since is None else int(since)
    raw = await _call(home, kp, sub.hub_id, "workgroup.pull",
                      {"workgroup_id": wg_id, "since": cursor})

    server_version = int(raw.get("current_key_version", 1))
    new_sealed = str(raw.get("sealed_key") or "")
    if new_sealed and sub.sealed_for(server_version) != new_sealed:
        sub.upsert_key(server_version, new_sealed)

    decrypted: list[dict[str, Any]] = []
    for p in raw.get("posts") or []:
        try:
            text = sub_mod.decrypt_post(sub, kp, p).decode("utf-8", errors="replace")
        except Exception as e:  # noqa: BLE001
            text = f"[decrypt failed: {e}]"
        decrypted.append({**p, "text": text})

    head = int(raw.get("head", cursor))
    if head > sub.last_seq:
        sub.last_seq = head
    sub.append_recent(decrypted)
    _absorb_roster(sub, raw.get("members"))
    sub_mod.upsert(home, sub)

    _emit_wg_mentions(
        home, wg_id, decrypted,
        own_pubkey=kp.pubkey_b64(), min_seq=cursor,
    )

    return decrypted, head


def _emit_wg_mentions(
    home: Path, wg_id: str, posts: list[dict[str, Any]],
    *, own_pubkey: str, min_seq: int = 0,
) -> None:
    """Emit ``wg.mention`` for pulled posts that mention the local profile; skip self-posts and ``seq <= min_seq`` so re-pulls don't duplicate."""
    try:
        from alpi.alp import tasks as tasks_mod
        from alpi.home import profile_name
        from alpi.host import events as host_events
    except Exception:  # noqa: BLE001
        return

    me = (profile_name(home) or "").lower()
    if not me:
        return

    for p in posts:
        if int(p.get("seq") or 0) <= min_seq:
            continue
        if str(p.get("from") or "") == own_pubkey:
            continue
        text = str(p.get("text") or "")
        if not text:
            continue
        mentioned = {m.lower() for m in tasks_mod.mentions_in(text)}
        if me not in mentioned:
            continue
        try:
            host_events.emit("wg.mention", {
                "profile": profile_name(home),
                "wg_id": wg_id,
                "seq": int(p.get("seq") or 0),
                "from": str(p.get("from") or ""),
                "summary": text[:200],
            })
        except Exception:  # noqa: BLE001
            pass


async def leave(home: Path, wg_id: str) -> dict[str, Any]:
    """Leave the workgroup and purge the local subscription."""
    kp = load_or_generate(home)
    sub = sub_mod.get(home, wg_id)
    if sub is None:
        raise ValueError(f"not subscribed to {wg_id!r}")
    result: dict[str, Any] = {}
    try:
        result = await _call(home, kp, sub.hub_id, "workgroup.leave",
                             {"workgroup_id": wg_id})
    except Exception as e:  # noqa: BLE001
        result = {
            "workgroup_id": wg_id,
            "hub_unreachable": True,
            "hub_error": f"{type(e).__name__}: {e}",
        }
    sub_mod.remove(home, wg_id)
    return result


async def pause(home: Path, wg_id: str) -> dict[str, Any]:
    return await _set_paused(home, wg_id, True)


async def resume(home: Path, wg_id: str) -> dict[str, Any]:
    return await _set_paused(home, wg_id, False)


async def _set_paused(home: Path, wg_id: str, paused: bool) -> dict[str, Any]:
    from alpi.alp import workgroup as wg_mod
    kp = load_or_generate(home)
    own_pubkey = kp.pubkey_b64()
    wg = wg_mod.load(home, wg_id)
    if wg is not None and wg.meta.hub_pubkey == own_pubkey:
        if wg.meta.paused != paused:
            wg.meta.paused = paused
            wg.meta.paused_at = wg_mod._utcnow() if paused else ""
            wg.meta.paused_by = own_pubkey if paused else ""
            wg_mod._save_meta(wg_mod._wg_dir(home, wg_id), wg.meta)
        return {
            "workgroup_id": wg_id,
            "paused": paused,
            "paused_at": wg.meta.paused_at,
            "paused_by": wg.meta.paused_by,
        }
    raise ValueError(
        "only the workgroup hub may pause / resume this workgroup"
    )
