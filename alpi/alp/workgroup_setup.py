"""Interactive setup for ALP workgroups — ``alpi setup → ALP → Workgroups``.

Lists workgroups this profile is **hub of** (created here) and
**member of** (joined remotely), with detail panes that show the
decrypted transcript and the management actions (pause / resume /
leave / kick) appropriate for the role.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from alpi import ui
from alpi.alp import client as alp_client
from alpi.alp import peers as peers_mod
from alpi.alp import subscription as sub_mod
from alpi.alp import workgroup as wg_mod
from alpi.alp import workgroup_client as wc_mod
from alpi.alp.keys import load_or_generate


def run(home: Path) -> None:
    while True:
        hub_wgs = wg_mod.list_workgroups(home)
        sub_wgs = sub_mod.load(home)
        items: list = []

        if hub_wgs:
            items.append(ui.Heading("Hub of"))
            for wg in hub_wgs:
                label = wg.meta.name
                detail = _hub_detail(home, wg)
                items.append((label, ("hub", wg.meta.id), detail))

        if sub_wgs:
            items.append(ui.Heading("Member of"))
            for sub in sub_wgs:
                label = sub.name or sub.wg_id
                items.append((label, ("sub", sub.wg_id),
                              f"hub @{sub.hub_id} · seq {sub.last_seq}"))

        items.append(("+ Create workgroup", ("create", None), "you become the hub"))
        items.append(("+ Join workgroup",   ("join", None),
                      "subscribe to one a peer is hosting"))

        result = ui.menu(
            ui.crumb("setup", "workgroups"),
            items,
            subtitle="hub-anchored shared transcripts",
            home=home,
            close="Back",
        )
        if result is None:
            return
        action, target = result
        if action == "hub":
            _hub_detail_view(home, target)
        elif action == "sub":
            _sub_detail_view(home, target)
        elif action == "create":
            _create_flow(home)
        elif action == "join":
            _join_flow(home)


# Hub-of detail


def _hub_detail(home: Path, wg) -> str:
    parts: list[str] = [f"{len(wg.members)} members"]
    if wg.meta.paused:
        parts.append("paused")
    if wg.meta.budget:
        led = _read_ledger(home, wg.meta.id)
        if "max_usd" in wg.meta.budget:
            parts.append(f"${led.get('usd', 0):.2f} / ${wg.meta.budget['max_usd']:.2f}")
        elif "max_tokens" in wg.meta.budget:
            parts.append(f"{led.get('tokens', 0):,} / {wg.meta.budget['max_tokens']:,} tok")
    return " · ".join(parts)


def _read_ledger(home: Path, wg_id: str) -> dict[str, Any]:
    p = home / "alp" / "workgroups" / wg_id / "ledger.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError:
        return {}


def _hub_detail_view(home: Path, wg_id: str) -> None:
    while True:
        wg = wg_mod.load(home, wg_id)
        if wg is None:
            ui.fail_and_wait(f"workgroup {wg_id!r} disappeared")
            return
        post_count = _post_count(home, wg_id)
        ui.banner(
            ui.crumb("setup", "workgroups", wg.meta.name),
            subtitle=f"hub · {wg.meta.id}",
            home=home,
        )
        items: list = [
            ui.Heading("Workgroup"),
            ("Read messages", "transcript",
             f"{post_count} message{'s' if post_count != 1 else ''}"),
            ("Members",         "members",
             f"{len(wg.members)} pinned"),
            ("Briefing",        "briefing",
             _preview(wg.meta.briefing) if wg.meta.briefing else "(empty)"),
            ("Budget",          "budget", _budget_summary(home, wg)),
            ui.Heading("Maintenance"),
            ("Pause" if not wg.meta.paused else "Resume",
             "pause" if not wg.meta.paused else "resume",
             "freeze posts" if not wg.meta.paused else "re-admit posts"),
            ("Kick member",      "kick",   "drop a peer + rotate group key"),
            ("Delete workgroup", "delete", "remove from disk"),
        ]
        choice = ui.menu("", items, home=home, close="Back")
        if choice is None:
            return
        if choice == "transcript":
            _show_transcript_hub(home, wg)
        elif choice == "members":
            _show_members(home, wg)
        elif choice == "budget":
            _edit_budget(home, wg)
        elif choice == "briefing":
            _edit_briefing(home, wg)
        elif choice == "pause":
            wg.meta.paused = True
            from alpi.alp.workgroup import _utcnow, _save_meta, _wg_dir
            wg.meta.paused_at = _utcnow()
            wg.meta.paused_by = load_or_generate(home).pubkey_b64()
            _save_meta(_wg_dir(home, wg_id), wg.meta)
            ui.ok_and_wait(f"{wg.meta.name} paused")
        elif choice == "resume":
            wg.meta.paused = False
            wg.meta.paused_at = ""
            wg.meta.paused_by = ""
            from alpi.alp.workgroup import _save_meta, _wg_dir
            _save_meta(_wg_dir(home, wg_id), wg.meta)
            ui.ok_and_wait(f"{wg.meta.name} resumed")
        elif choice == "kick":
            _kick_flow(home, wg)
        elif choice == "delete":
            if _delete_flow(home, wg):
                return


def _post_count(home: Path, wg_id: str) -> int:
    p = home / "alp" / "workgroups" / wg_id / "transcript.jsonl"
    if not p.exists():
        return 0
    return sum(1 for line in p.read_text().splitlines() if line.strip())


def _show_members(home: Path, wg) -> None:
    aliases = _alias_map(home)
    kp = load_or_generate(home)
    accent = ui._accent_hex(home) or ""
    spend = _spend_per_member(home, wg)
    ui.banner(
        ui.crumb("setup", "workgroups", wg.meta.name, "members"),
        subtitle=f"{len(wg.members)} pinned · hub-anchored roster",
        home=home,
    )
    for m in wg.members:
        who = aliases.get(m.pubkey, m.pubkey[:12] + "…")
        flag = "joined" if m.joined else "invited"
        if m.pubkey == wg.meta.hub_pubkey:
            flag = "hub"
        spent = spend.get(m.pubkey, {"usd": 0.0, "tokens": 0, "posts": 0})
        suffix = (
            f"  [dim]· ${spent['usd']:.2f} · {spent['tokens']:,} tok"
            f" · {spent['posts']} posts[/dim]"
        )
        if m.pubkey == kp.pubkey_b64() and accent:
            ui._console.print(
                f"  [b {accent}]{who}[/b {accent}]  [dim]{flag}[/dim]{suffix}",
            )
        else:
            ui._console.print(f"  [b]{who}[/b]  [dim]{flag}[/dim]{suffix}")
    ui._console.print("")
    ui.press_enter()


def _spend_per_member(home: Path, wg) -> dict[str, dict[str, Any]]:
    """Aggregate workgroup transcript by author. Each post may carry
    an optional ``cost: {usd, tokens}`` declaration; we sum them per
    pubkey to give the wizard a quick "who's burning what" view."""
    kp = load_or_generate(home)
    member = wg.member(kp.pubkey_b64())
    out: dict[str, dict[str, Any]] = {}
    for entry in _read_transcript(home, wg.meta.id):
        author = str(entry.get("from") or "")
        bucket = out.setdefault(author, {"usd": 0.0, "tokens": 0, "posts": 0})
        bucket["posts"] += 1
        cost = entry.get("cost") or {}
        if isinstance(cost, dict):
            bucket["usd"] += float(cost.get("usd", 0.0) or 0.0)
            bucket["tokens"] += int(cost.get("tokens", 0) or 0)
    return out


def _show_transcript_hub(home: Path, wg) -> None:
    """The hub holds ciphertext only — open with the hub's own sealed
    key + private key so the operator can audit posts."""
    kp = load_or_generate(home)
    member = wg.member(kp.pubkey_b64())
    if member is None:
        ui.fail_and_wait("hub is not a member of its own workgroup — corrupt state")
        return
    group_key = wg_mod.open_sealed_group_key(member.sealed_key, kp)
    posts = _read_transcript(home, wg.meta.id)
    _print_transcript(home, posts, _decrypter_for_version(home, wg, kp))
    ui.press_enter()


def _decrypter_for_version(home: Path, wg, kp):
    """Hub may have rotated keys; the hub's `members.yaml` only stores
    the CURRENT sealed key. Past versions can't be decrypted on the
    hub side (that's by design — past keys are gone). Fall back to a
    placeholder for stale ciphertext."""
    cur_sealed = wg.member(kp.pubkey_b64()).sealed_key
    cur_version = wg.member(kp.pubkey_b64()).key_version

    def _open(post: dict[str, Any]) -> str:
        v = int(post.get("key_version", 1))
        if v != cur_version:
            return f"[v{v} key rotated out of hub state]"
        try:
            group_key = wg_mod.open_sealed_group_key(cur_sealed, kp)
            return wg_mod.decrypt_post(
                group_key, post["nonce"], post["ciphertext"],
            ).decode("utf-8", errors="replace")
        except Exception as e:  # noqa: BLE001
            return f"[decrypt failed: {e}]"

    return _open


def _print_transcript(home: Path, posts: list[dict[str, Any]], decrypt) -> None:
    ui._console.print("")
    if not posts:
        ui.dim("  (no posts yet)")
        ui._console.print("")
        return
    aliases = _alias_map(home)
    for p in posts:
        who = aliases.get(p["from"], p["from"][:12] + "…")
        text = decrypt(p)
        ui._console.print(f"  [dim]#{p['seq']}[/dim] [b]{who}[/b]  {text}")
    ui._console.print("")


def _alias_map(home: Path) -> dict[str, str]:
    """Map base64 pubkey → human label using this profile's peers.yaml
    plus the profile's own keypair (rendered with the actual profile
    name so members see consistent ``@<id>`` everywhere instead of an
    abstract ``@me``)."""
    from alpi.home import _ROOT
    out: dict[str, str] = {}
    kp = load_or_generate(home)
    if home == _ROOT:
        own = "default"
    else:
        try:
            own = home.relative_to(_ROOT / "profiles").parts[0]
        except Exception:  # noqa: BLE001
            own = "me"
    out[kp.pubkey_b64()] = f"@{own}"
    for p in peers_mod.load(home):
        out[p.pubkey] = f"@{p.id}"
    return out


def _read_transcript(home: Path, wg_id: str) -> list[dict[str, Any]]:
    """Local read — hub uses this for the audit view; members go
    through ``workgroup_client.pull`` instead so the cursor advances."""
    p = home / "alp" / "workgroups" / wg_id / "transcript.jsonl"
    if not p.exists():
        return []
    out: list[dict[str, Any]] = []
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


# Member-of detail


def _sub_detail_view(home: Path, wg_id: str) -> None:
    while True:
        sub = sub_mod.get(home, wg_id)
        if sub is None:
            ui.dim("subscription removed")
            return
        ui.banner(
            ui.crumb("setup", "workgroups", sub.name or wg_id),
            subtitle=f"member · hub @{sub.hub_id} · {wg_id}",
            home=home,
        )
        ui._console.print("")
        ui._console.print(f"  hub      @{sub.hub_id}")
        ui._console.print(f"  cursor   seq {sub.last_seq}")
        ui._console.print(f"  keys     v{sub.latest_version()} (cached)")
        ui._console.print("")
        items = [
            ("Read new messages", "pull",   "fetch + decrypt anything new"),
            ("Send a message",    "post",   "encrypt + send to the hub"),
            ("Pause workgroup",   "pause",  "any member can"),
            ("Resume workgroup",  "resume", "any member can"),
            ("Leave",             "leave",  "drop subscription + hub rekeys"),
        ]
        choice = ui.menu("", items, home=home, close="Back")
        if choice is None:
            return
        if choice == "pull":
            _pull_flow(home, wg_id)
        elif choice == "post":
            _post_flow(home, wg_id)
        elif choice == "pause":
            _safe(lambda: asyncio.run(wc_mod.pause(home, wg_id)),
                  "paused", f"pause {wg_id}")
        elif choice == "resume":
            _safe(lambda: asyncio.run(wc_mod.resume(home, wg_id)),
                  "resumed", f"resume {wg_id}")
        elif choice == "leave":
            if not ui.confirm("Leave the workgroup?", default=False):
                continue
            _safe(lambda: asyncio.run(wc_mod.leave(home, wg_id)),
                  "left", f"leave {wg_id}")
            return


def _pull_flow(home: Path, wg_id: str) -> None:
    try:
        posts, head = asyncio.run(wc_mod.pull(home, wg_id))
    except Exception as e:  # noqa: BLE001
        ui.fail_and_wait(f"pull failed: {e}")
        return
    aliases = _alias_map(home)
    ui.banner(ui.crumb("setup", "workgroups", wg_id, "transcript"),
              subtitle=f"head seq {head}", home=home)
    ui._console.print("")
    if not posts:
        ui.dim("  (no new posts since last pull)")
    else:
        for p in posts:
            who = aliases.get(p["from"], p["from"][:12] + "…")
            ui._console.print(f"  [dim]#{p['seq']}[/dim] [b]{who}[/b]  {p['text']}")
    ui._console.print("")
    ui.press_enter()


def _post_flow(home: Path, wg_id: str) -> None:
    text = ui.text("Message:")
    if not text:
        return
    try:
        result = asyncio.run(wc_mod.post(home, wg_id, text.encode("utf-8")))
    except alp_client.RemoteError as e:
        ui.fail_and_wait(f"hub rejected: {e.code} {e.message}")
        return
    except Exception as e:  # noqa: BLE001
        ui.fail_and_wait(f"post failed: {e}")
        return
    ui.ok_and_wait(f"posted seq {result.get('seq')}")


def _safe(fn, ok_msg: str, fail_label: str) -> None:
    try:
        fn()
    except alp_client.RemoteError as e:
        ui.fail_and_wait(f"{fail_label}: {e.code} {e.message}")
        return
    except Exception as e:  # noqa: BLE001
        ui.fail_and_wait(f"{fail_label}: {e}")
        return
    ui.ok_and_wait(ok_msg)


# Create flow (hub side)


def _create_flow(home: Path) -> None:
    ui.banner(
        ui.crumb("setup", "workgroups", "create"),
        subtitle="you become the hub of the new workgroup",
        home=home,
    )
    ui.dim(
        "Workgroups are hub-anchored — your alpi holds the transcript\n"
        "and the group key state. Members must already be pinned in\n"
        "your peers.yaml; pick them from the roster below."
    )
    ui._console.print("")

    name = ui.text("Workgroup name (e.g. design, research, ops):")
    if not name:
        return ui.cancelled()
    name = name.strip()

    briefing = ui.text(
        "Briefing — what is this workgroup for? "
        "(one paragraph, ENTER to skip):",
    )
    if briefing is None:
        return ui.cancelled()
    briefing = (briefing or "").strip()

    # Pick members from peers.yaml
    pinned = peers_mod.load(home)
    if not pinned:
        ui.fail_and_wait("no peers pinned — add some in setup → Peers first")
        return
    member_pks = _pick_members(pinned, home)
    if member_pks is None:
        return ui.cancelled()

    # Optional budget
    budget = _pick_budget(home)
    if budget is False:
        return ui.cancelled()

    auto_kickoff = ui.confirm(
        "Auto-kickoff? (members start engaging as soon as their "
        "service polls — set off for exploratory workgroups)",
        default=True,
    )

    kp = load_or_generate(home)
    try:
        wg = wg_mod.create(
            home, name=name, hub_kp=kp,
            member_pubkeys=member_pks, budget=budget or {},
            briefing=briefing, auto_kickoff=bool(auto_kickoff),
        )
    except ValueError as e:
        ui.fail_and_wait(str(e))
        return
    granted = _grant_workgroup_verbs(home, member_pks)
    summary = f"created {wg.meta.id} · {len(wg.members)} members"
    if granted:
        summary += f" · granted workgroup verbs to {granted} peer(s)"
    ui.ok_and_wait(summary)


_WORKGROUP_VERBS = (
    "workgroup.join", "workgroup.post", "workgroup.pull",
    "workgroup.leave", "workgroup.pause", "workgroup.resume",
)


def _grant_workgroup_verbs(home: Path, member_pks: list[str]) -> int:
    """Make sure every invited peer has the workgroup verbs in their
    ``allow`` list — otherwise the hub would reject their `join` at
    the capability gate. Idempotent: only adds verbs that aren't
    already there. Returns the number of peers we actually touched."""
    pinned = peers_mod.load(home)
    touched = 0
    for peer in pinned:
        if peer.pubkey not in member_pks:
            continue
        missing = [v for v in _WORKGROUP_VERBS if v not in peer.allow]
        if not missing:
            continue
        peer.allow = list(peer.allow) + missing
        touched += 1
    if touched:
        peers_mod.save(home, pinned)
    return touched


def _pick_members(pinned, home: Path) -> list[str] | None:
    selected: list[str] = []
    while True:
        items: list = []
        for p in pinned:
            mark = "[x]" if p.pubkey in selected else "[ ]"
            items.append((f"{mark} @{p.id}", ("toggle", p.pubkey),
                          p.alias or p.pubkey[:12] + "…"))
        items.append(None)
        items.append(("Done", ("done", None),
                      f"{len(selected)} member(s) selected"))
        result = ui.menu(
            ui.crumb("setup", "workgroups", "create", "members"),
            items,
            subtitle="toggle peers to invite",
            home=home,
            close="Back",
        )
        if result is None:
            return None
        action, value = result
        if action == "done":
            return selected
        if action == "toggle":
            if value in selected:
                selected.remove(value)
            else:
                selected.append(value)


def _budget_summary(home: Path, wg) -> str:
    if not wg.meta.budget:
        return "no cap"
    led = _read_ledger(home, wg.meta.id)
    parts: list[str] = []
    if "max_usd" in wg.meta.budget:
        parts.append(f"${led.get('usd', 0):.2f} / ${wg.meta.budget['max_usd']:.2f}")
    if "max_tokens" in wg.meta.budget:
        parts.append(
            f"{led.get('tokens', 0):,} / {wg.meta.budget['max_tokens']:,} tok",
        )
    return " · ".join(parts)


def _edit_briefing(home: Path, wg) -> None:
    """Edit the workgroup's plaintext briefing on the hub. Set what
    this workgroup is for; a clear briefing is the anchor every member
    agent reads on every turn."""
    from alpi.alp.workgroup import _save_meta, _wg_dir

    ui.banner(
        ui.crumb("setup", "workgroups", wg.meta.name, "briefing"),
        subtitle="what is this workgroup for?",
        home=home,
    )
    ui.dim(
        "The briefing is plaintext on the hub — visible to anyone with\n"
        "filesystem access, not part of the encrypted transcript. It\n"
        "anchors what the workgroup exists for; member agents read it\n"
        "on every turn to stay aligned."
    )
    ui._console.print("")
    raw = ui.text(
        f"Briefing (current: {_preview(wg.meta.briefing) or '(empty)'}):",
        default=wg.meta.briefing,
    )
    if raw is None:
        return ui.cancelled()
    wg.meta.briefing = (raw or "").strip()
    _save_meta(_wg_dir(home, wg.meta.id), wg.meta)
    ui.ok_and_wait("briefing updated")


def _preview(text: str, limit: int = 60) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _edit_budget(home: Path, wg) -> None:
    """Edit-in-place over the wizard. Same prompts as create; the
    current values surface as defaults and the user can blank either
    field to clear it. Empty + empty = no cap."""
    from alpi.alp.workgroup import _save_meta, _wg_dir, _validate_budget

    cur = wg.meta.budget or {}
    cur_usd = str(cur.get("max_usd")) if "max_usd" in cur else ""
    cur_tokens = str(cur.get("max_tokens")) if "max_tokens" in cur else ""

    ui.banner(
        ui.crumb("setup", "workgroups", wg.meta.name, "budget"),
        subtitle="lifetime cap — paid (USD) and/or local (tokens)",
        home=home,
    )
    ui.dim(
        "Empty = clear that cap. Set both to keep both gates active\n"
        "(whichever trips first freezes posts). Profile-level daily\n"
        "budget keeps applying on top of this either way."
    )
    ui._console.print("")

    usd_s = ui.text(
        f"Lifetime USD cap (empty to clear) [{cur_usd}]:", default=cur_usd,
    )
    if usd_s is None:
        return ui.cancelled()
    usd_s = (usd_s or "").strip()

    tokens_s = ui.text(
        f"Lifetime token cap (empty to clear) [{cur_tokens}]:", default=cur_tokens,
    )
    if tokens_s is None:
        return ui.cancelled()
    tokens_s = (tokens_s or "").strip()

    new: dict[str, Any] = {}
    if usd_s:
        try:
            v = float(usd_s)
        except ValueError:
            ui.fail_and_wait(f"not a number: {usd_s!r}")
            return
        if v <= 0:
            ui.fail_and_wait("USD cap must be > 0")
            return
        new["max_usd"] = v
    if tokens_s:
        try:
            v_int = int(tokens_s)
        except ValueError:
            ui.fail_and_wait(f"not an integer: {tokens_s!r}")
            return
        if v_int <= 0:
            ui.fail_and_wait("token cap must be > 0")
            return
        new["max_tokens"] = v_int

    try:
        wg.meta.budget = _validate_budget(new) if new else {}
    except ValueError as e:
        ui.fail_and_wait(str(e))
        return
    _save_meta(_wg_dir(home, wg.meta.id), wg.meta)
    if not wg.meta.budget:
        ui.ok_and_wait("budget cleared — no workgroup-level cap")
    else:
        ui.ok_and_wait(f"budget updated · {_budget_summary(home, wg)}")


def _pick_budget(home: Path) -> dict[str, Any] | bool | None:
    """Same shape as the profile-budget wizard: ask for both caps,
    empty = skip. Set what you care about; both can coexist (each
    gates independently). Returns the budget dict, ``None`` if the
    user declined to set one, or ``False`` on cancel/invalid input."""
    ui.banner(
        ui.crumb("setup", "workgroups", "create", "budget"),
        subtitle="lifetime spend cap (optional, project-scoped)",
        home=home,
    )
    ui.dim(
        "Paid models → set a USD cap. Local / free models → set a token\n"
        "cap. Leave both empty for no ceiling. Both can be set; whichever\n"
        "trips first freezes posts in this workgroup."
    )
    ui._console.print("")
    if not ui.confirm("Set a lifetime budget?", default=False):
        return None
    ui._console.print("")

    usd_s = ui.text("Lifetime USD cap (empty to skip):")
    if usd_s is None:
        return False
    usd_s = (usd_s or "").strip()

    tokens_s = ui.text("Lifetime token cap (empty to skip):")
    if tokens_s is None:
        return False
    tokens_s = (tokens_s or "").strip()

    out: dict[str, Any] = {}
    if usd_s:
        try:
            v = float(usd_s)
        except ValueError:
            ui.fail_and_wait(f"not a number: {usd_s!r}")
            return False
        if v <= 0:
            ui.fail_and_wait("USD cap must be > 0")
            return False
        out["max_usd"] = v
    if tokens_s:
        try:
            v_int = int(tokens_s)
        except ValueError:
            ui.fail_and_wait(f"not an integer: {tokens_s!r}")
            return False
        if v_int <= 0:
            ui.fail_and_wait("token cap must be > 0")
            return False
        out["max_tokens"] = v_int
    return out or None


# Join flow (member side)


def _join_flow(home: Path) -> None:
    ui.banner(
        ui.crumb("setup", "workgroups", "join"),
        subtitle="subscribe to a workgroup hosted by a peer",
        home=home,
    )
    ui.dim(
        "Out-of-band: the hub creates the workgroup with your pubkey\n"
        "in its roster, then shares the workgroup id (e.g. wg_xxxxxx)\n"
        "with you. Pick the hub from your pinned peers and paste the id."
    )
    ui._console.print("")

    pinned = peers_mod.load(home)
    if not pinned:
        ui.fail_and_wait("no peers pinned — add the hub in setup → Peers first")
        return

    items = [(f"@{p.id}", p.id, p.alias or p.pubkey[:12] + "…") for p in pinned]
    hub_id = ui.menu(
        ui.crumb("setup", "workgroups", "join", "hub"),
        items, subtitle="hub of the workgroup", home=home, close="Back",
    )
    if hub_id is None:
        return
    wg_id = ui.text("Workgroup id (wg_xxxxxx):")
    if not wg_id:
        return ui.cancelled()
    wg_id = wg_id.strip()
    try:
        sub = asyncio.run(wc_mod.join(home, hub_id, wg_id))
    except alp_client.RemoteError as e:
        ui.fail_and_wait(f"hub rejected: {e.code} {e.message}")
        return
    except Exception as e:  # noqa: BLE001
        ui.fail_and_wait(f"join failed: {e}")
        return
    ui.ok_and_wait(f"joined {sub.name or wg_id} via @{hub_id}")


# Kick flow (hub)


def _kick_flow(home: Path, wg) -> None:
    kp = load_or_generate(home)
    aliases = _alias_map(home)
    items = []
    for m in wg.members:
        if m.pubkey == kp.pubkey_b64():
            continue  # can't kick yourself
        label = aliases.get(m.pubkey, m.pubkey[:12] + "…")
        items.append((label, m.pubkey, "rotate group key on drop"))
    if not items:
        ui.dim("no other members to kick.")
        ui.press_enter()
        return
    target = ui.menu(
        ui.crumb("setup", "workgroups", wg.meta.id, "kick"),
        items, home=home, close="Back",
    )
    if target is None:
        return
    label = aliases.get(target, target[:12] + "…")
    if not ui.confirm(f"Kick {label} and rotate the group key?", default=False):
        return ui.cancelled()
    try:
        wg_mod.kick(home, wg.meta.id, target)
    except ValueError as e:
        ui.fail_and_wait(str(e))
        return
    ui.ok_and_wait("kicked + rekeyed")


# Delete flow (hub-side, local destructive)


def _delete_flow(home: Path, wg) -> bool:
    if not ui.confirm(
        f"Delete workgroup {wg.meta.name} permanently? This wipes the "
        "transcript and all member entries on this hub.",
        default=False,
    ):
        ui.cancelled()
        return False
    import shutil
    shutil.rmtree(home / "alp" / "workgroups" / wg.meta.id, ignore_errors=True)
    ui.ok_and_wait(f"deleted {wg.meta.id}")
    return True
