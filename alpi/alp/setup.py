"""Interactive setup for ALP peers — ``alpi setup → Peers``.

List loop with add / remove / view-identity actions. Status (online
/ offline) is probed per-peer via a quick ``link.ping``; remote
peers (inter-machine, ALP.2) surface as ``?`` until that transport
lands.
"""

from __future__ import annotations

import asyncio
import base64
from pathlib import Path

from alpi import ui
from alpi.alp import client as alp_client
from alpi.alp import peers as peers_mod
from alpi.alp.keys import load_or_generate
from alpi.alp.peers import Peer


_PING_TIMEOUT = 0.5


def run(home: Path) -> None:
    """Top-level entry — shows identity + pinned peers, with add/remove."""
    kp = load_or_generate(home)
    while True:
        entries = peers_mod.load(home)
        statuses = asyncio.run(_probe_all(home, entries, kp.pubkey_b64()))

        items: list = []
        items.append(("Your identity", ("identity", None), _short_pubkey(kp.pubkey_b64())))
        if entries:
            items.append(None)
        for peer in entries:
            label = f"{_status_dot(statuses.get(peer.id, '?'))} @{peer.id}"
            detail = _peer_detail(peer)
            items.append((label, ("use", peer.id), detail))
        items.append(None)
        items.append(("+ Add peer", ("add", None), ""))
        if entries:
            items.append(("- Remove peer", ("remove", None), ""))

        result = ui.menu(
            ui.crumb("setup", "peers"),
            items,
            subtitle="ALP — cross-profile & inter-machine agent links",
            home=home, close="Back",
        )
        if result is None:
            return
        action, target = result
        if action == "identity":
            _show_identity(home, kp.pubkey_b64())
        elif action == "use":
            _inspect(home, target, statuses.get(target, "?"))
        elif action == "add":
            _add(home)
        elif action == "remove":
            _remove(home, entries)


# Probe


async def _probe_all(
    home: Path, entries: list[Peer], self_pubkey: str,
) -> dict[str, str]:
    """Fire a concurrent ``link.ping`` at every peer. 500ms timeout,
    returns a dict ``{peer_id: "on"|"off"|"?"}``."""
    if not entries:
        return {}
    tasks = [_probe_one(home, p, self_pubkey) for p in entries]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return {p.id: (r if isinstance(r, str) else "off") for p, r in zip(entries, results)}


async def _probe_one(home: Path, peer: Peer, _self: str) -> str:
    if peer.address is not None:
        return "?"  # ALP.2 — skip until TCP transport lands.
    target_home = _target_home(peer.id)
    socket_path = target_home / "alp" / "alp.sock"
    if not socket_path.exists():
        return "off"
    try:
        kp = load_or_generate(home)
        await alp_client.call(
            socket_path=socket_path,
            sender=kp,
            recipient_pubkey_b64=peer.pubkey,
            method="link.ping",
            params={"nonce": "setup"},
            timeout=_PING_TIMEOUT,
        )
        return "on"
    except Exception:  # noqa: BLE001
        return "off"


def _target_home(peer_id: str) -> Path:
    if peer_id == "default":
        return Path.home() / ".alpi"
    return Path.home() / ".alpi" / "profiles" / peer_id


# Display helpers


def _status_dot(status: str) -> str:
    if status == "on":
        return "●"
    if status == "off":
        return "○"
    return "?"


def _peer_detail(peer: Peer) -> str:
    allow = ", ".join(sorted(peer.allow)) if peer.allow else "no capabilities"
    if peer.address:
        return f"{allow} · {peer.address}"
    return allow


def _short_pubkey(pubkey_b64: str) -> str:
    return f"{pubkey_b64[:8]}…{pubkey_b64[-4:]}"


# Identity page


def _show_identity(home: Path, pubkey_b64: str) -> None:
    ui.banner(ui.crumb("setup", "peers", "identity"),
              subtitle="your ALP public key", home=home)
    ui._console.print("")
    ui.dim(
        "Share this pubkey with peers who need to pin you. They paste\n"
        "it into their own setup → Peers → Add. Rotation invalidates\n"
        "every pinning — do it deliberately.\n"
    )
    ui._console.print("")
    ui._console.print(f"  [bold]{pubkey_b64}[/bold]")
    ui._console.print("")
    if ui.confirm("Copy to clipboard?", default=True):
        _copy_to_clipboard(pubkey_b64)
        ui.ok_and_wait("copied")
    else:
        ui.press_enter()


def _copy_to_clipboard(text: str) -> None:
    import shutil
    import subprocess
    import sys
    cmds: list[list[str]] = []
    if sys.platform == "darwin":
        cmds.append(["pbcopy"])
    else:
        if shutil.which("wl-copy"):
            cmds.append(["wl-copy"])
        if shutil.which("xclip"):
            cmds.append(["xclip", "-selection", "clipboard"])
        if shutil.which("xsel"):
            cmds.append(["xsel", "--clipboard", "--input"])
    for cmd in cmds:
        try:
            p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
            p.communicate(text.encode("utf-8"))
            if p.returncode == 0:
                return
        except Exception:  # noqa: BLE001
            continue


# Inspect / remove / add


def _inspect(home: Path, peer_id: str, status: str) -> None:
    peer = peers_mod.get_by_id(home, peer_id)
    if peer is None:
        ui.fail_and_wait(f"peer {peer_id!r} disappeared")
        return
    ui.banner(ui.crumb("setup", "peers", f"@{peer_id}"), subtitle="peer detail", home=home)
    ui._console.print("")
    status_label = {"on": "online", "off": "offline", "?": "remote (not probed)"}[status]
    ui._console.print(f"  status   {status_label}")
    ui._console.print(f"  pubkey   {peer.pubkey}")
    if peer.alias:
        ui._console.print(f"  alias    {peer.alias}")
    if peer.address:
        ui._console.print(f"  address  {peer.address}")
    ui._console.print(f"  allow    {', '.join(peer.allow) or '(none)'}")
    ui._console.print("")
    ui.press_enter()


def _remove(home: Path, entries: list[Peer]) -> None:
    items = [(f"@{p.id}", p.id, _peer_detail(p)) for p in entries]
    peer_id = ui.menu(
        ui.crumb("setup", "peers", "remove"), items,
        subtitle="drop a pinned peer",
        home=home, close="Back",
    )
    if not peer_id:
        return
    if not ui.confirm(f"Remove @{peer_id}?", default=False):
        ui.cancelled()
        return
    if peers_mod.remove(home, peer_id):
        ui.ok_and_wait(f"removed @{peer_id}")
    else:
        ui.fail_and_wait(f"no peer @{peer_id}")


def _add(home: Path) -> None:
    ui.banner(ui.crumb("setup", "peers", "add"), subtitle="pin a new peer", home=home)
    ui.dim(
        "Pair two alpis by exchanging pubkeys out-of-band (paste them\n"
        "into each other's setup). Fail-closed: peers not in the list\n"
        "are rejected before any payload is parsed.\n"
    )
    ui._console.print("")

    peer_id = ui.text("Peer id (short handle, e.g. mirai, home-server):")
    if not peer_id:
        return ui.cancelled()
    peer_id = peer_id.strip()
    if "/" in peer_id or " " in peer_id or ":" in peer_id:
        ui.fail_and_wait(f"invalid id: {peer_id!r}")
        return
    if peers_mod.get_by_id(home, peer_id) is not None:
        ui.fail_and_wait(f"@{peer_id} already pinned; remove it first")
        return

    pubkey = ui.text("Base64 pubkey (from their Your identity page):")
    if not pubkey:
        return ui.cancelled()
    pubkey = pubkey.strip()
    if not _valid_pubkey(pubkey):
        ui.fail_and_wait("not a valid Ed25519 pubkey (expected base64 of 32 bytes)")
        return
    if peers_mod.get_by_pubkey(home, pubkey) is not None:
        ui.fail_and_wait("that pubkey is already pinned under a different id")
        return

    allow = _pick_capabilities()
    alias = ui.text("Alias (optional display label, ENTER to skip):") or ""

    peer = Peer(id=peer_id, pubkey=pubkey, alias=alias.strip(), allow=allow)
    try:
        peers_mod.add(home, peer)
    except ValueError as e:
        ui.fail_and_wait(str(e))
        return
    ui.ok_and_wait(f"pinned @{peer_id}")


def _pick_capabilities() -> list[str]:
    """Ask for each ALP.1 verb individually. Default both on — that's
    the usual case and unchecking is one keystroke."""
    verbs = [
        ("link.ping", "health probe"),
        ("link.ask", "one-shot turn"),
        ("link.cancel", "abort an in-flight turn"),
    ]
    allow: list[str] = []
    for verb, desc in verbs:
        if ui.confirm(f"Allow {verb} ({desc})?", default=True):
            allow.append(verb)
    return allow


def _valid_pubkey(pubkey_b64: str) -> bool:
    try:
        raw = base64.b64decode(pubkey_b64, validate=True)
    except Exception:  # noqa: BLE001
        return False
    return len(raw) == 32
