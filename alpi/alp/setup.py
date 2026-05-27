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


_PING_TIMEOUT = alp_client.PING_TIMEOUT_SECONDS


def run(home: Path) -> None:
    """Top-level entry — shows identity + pinned peers, with add/remove."""
    from alpi.alp import pending as pending_mod

    kp = load_or_generate(home)
    while True:
        entries = peers_mod.load(home)
        probes = asyncio.run(_probe_all(home, entries, kp.pubkey_b64()))
        mismatches = _detect_local_mismatches(entries)
        pending_entries = pending_mod.load(home)

        items: list = []
        items.append(("Your identity", ("identity", None), _short_pubkey(kp.pubkey_b64())))
        if pending_entries:
            items.append(None)
            items.append(ui.Heading("Pending invites"))
            for pe in pending_entries:
                items.append((
                    f"? {_short_pubkey(pe.pubkey)}",
                    ("pending", pe.pubkey),
                    "tried to contact you — pin or discard",
                ))
        if entries:
            items.append(None)
        for peer in entries:
            status, _ = probes.get(peer.id, ("?", None))
            mismatch = mismatches.get(peer.id)
            glyph = "⚠" if mismatch else _status_dot(status)
            label = f"{glyph} @{peer.id}"
            detail = (
                f"pubkey mismatch — actual: {_short_pubkey(mismatch)}"
                if mismatch
                else _peer_detail(peer)
            )
            items.append((label, ("use", peer.id), detail))
        items.append(None)
        items.append(("+ Add peer", ("add", None), ""))
        if entries:
            items.append(("- Remove peer", ("remove", None), ""))

        result = ui.menu(
            ui.crumb("setup", "peers"),
            items,
            subtitle="pubkey + capabilities + reachability per peer",
            home=home,
            close="Back",
        )
        if result is None:
            return
        action, target = result
        if action == "identity":
            _show_identity(home, kp.pubkey_b64())
        elif action == "use":
            status, reason = probes.get(target, ("?", None))
            _inspect(
                home,
                target,
                status,
                reason,
                mismatches.get(target),
                kp.pubkey_b64(),
            )
        elif action == "add":
            _add(home)
        elif action == "remove":
            _remove(home, entries)
        elif action == "pending":
            _accept_or_discard_pending(home, target)


def _accept_or_discard_pending(home: Path, pubkey: str) -> None:
    from alpi.alp import pending as pending_mod

    ui.banner(
        ui.crumb("setup", "peers", "pending"),
        subtitle=f"incoming pubkey: {_short_pubkey(pubkey)}",
        home=home,
    )
    ui._console.print("")
    ui._console.print(f"  full pubkey: {pubkey}")
    ui._console.print("")
    ui.dim(
        "Verify out-of-band that this pubkey belongs to who you think it does\n"
        "before pinning. The protocol can't tell strangers from friends."
    )
    ui._console.print("")
    choice = ui.menu(
        "",
        [
            ("Accept — pin as peer", "accept", "link.ping + link.ask"),
            ("Discard", "discard", "drop from pending list"),
        ],
        home=home,
        close="Back",
    )
    if choice == "accept":
        peer_id = ui.text("Pin under id (e.g. 'builder')")
        if not peer_id:
            return
        peer_id = peer_id.strip()
        try:
            peers_mod.add(home, Peer(
                id=peer_id, pubkey=pubkey,
                allow=["link.ping", "link.ask"],
            ))
        except ValueError as e:
            ui.fail_and_wait(str(e))
            return
        pending_mod.remove(home, pubkey)
        ui.ok_and_wait(f"pinned @{peer_id}")
    elif choice == "discard":
        pending_mod.remove(home, pubkey)
        ui.ok_and_wait("discarded")


# Probe


async def _probe_all(
    home: Path,
    entries: list[Peer],
    self_pubkey: str,
) -> dict[str, tuple[str, str | None]]:
    """Fire a concurrent ``link.ping`` at every peer. 500ms timeout,
    returns a dict ``{peer_id: (status, reason)}`` where status is
    ``"on" | "off" | "unverified"``. Reason is the underlying error
    message when not online, else None."""
    if not entries:
        return {}
    tasks = [_probe_one(home, p, self_pubkey) for p in entries]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    out: dict[str, tuple[str, str | None]] = {}
    for p, r in zip(entries, results):
        if isinstance(r, tuple):
            out[p.id] = r
        else:
            out[p.id] = ("off", str(r) if r else None)
    return out


async def _probe_one(
    home: Path, peer: Peer, _self: str
) -> tuple[str, str | None]:
    kp = load_or_generate(home)
    try:
        if peer.address:
            host, _, port_s = peer.address.rpartition(":")
            if not host or not port_s.isdigit():
                return ("off", f"invalid address: {peer.address!r}")
            await alp_client.call_tcp(
                host=host,
                port=int(port_s),
                sender=kp,
                recipient_pubkey_b64=peer.pubkey,
                method="link.ping",
                params={"nonce": "setup"},
                timeout=_PING_TIMEOUT,
            )
            return ("on", None)
        socket_path = peers_mod.local_socket_path(peer)
        if not socket_path.exists():
            return ("off", f"socket missing: {socket_path}")
        await alp_client.call(
            socket_path=socket_path,
            sender=kp,
            recipient_pubkey_b64=peer.pubkey,
            method="link.ping",
            params={"nonce": "setup"},
            timeout=_PING_TIMEOUT,
        )
        return ("on", None)
    except alp_client.TargetOffline as e:
        return ("off", str(e))
    except (alp_client.ClientError, alp_client.RemoteError) as e:
        return ("unverified", str(e))
    except Exception as e:  # noqa: BLE001
        return ("off", str(e))


def _detect_local_mismatches(entries: list[Peer]) -> dict[str, str]:
    """For each pinned peer that corresponds to a local profile on this
    machine, compare the pinned pubkey against the profile's actual
    keypair. Returns ``{peer_id: actual_pubkey_b64}`` for mismatches."""
    from alpi.alp import keys as keys_mod

    out: dict[str, str] = {}
    for peer in entries:
        target = (
            Path.home() / ".alpi" if peer.id == "default"
            else Path.home() / ".alpi" / "profiles" / peer.id
        )
        if not keys_mod.exists(target):
            continue
        try:
            kp = keys_mod.load(target)
        except Exception:  # noqa: BLE001
            continue
        actual = kp.pubkey_b64()
        if actual != peer.pubkey:
            out[peer.id] = actual
    return out


# Display helpers


def _status_dot(status: str) -> str:
    if status == "on":
        return "●"
    if status == "unverified":
        return "◐"
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
    ui.banner(ui.crumb("setup", "peers", "identity"), subtitle="your ALP public key", home=home)
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


def _inspect(
    home: Path,
    peer_id: str,
    status: str,
    reason: str | None,
    mismatch: str | None,
    self_pubkey: str,
) -> None:
    peer = peers_mod.get_by_id(home, peer_id)
    if peer is None:
        ui.fail_and_wait(f"peer {peer_id!r} disappeared")
        return
    ui.banner(ui.crumb("setup", "peers", f"@{peer_id}"), subtitle="peer detail", home=home)
    ui._console.print("")
    status_label = {
        "on": "online",
        "off": "offline",
        "unverified": "unverified — handshake aborted",
        "?": "unknown",
    }.get(status, status)
    ui._console.print(f"  status   {status_label}")
    if reason and status != "on":
        ui._console.print(f"           [dim]{reason}[/dim]")
    ui._console.print(f"  pubkey   {peer.pubkey}")
    if mismatch:
        ui._console.print(
            f"           [bold red]⚠ mismatch — actual local key: {mismatch}[/bold red]"
        )
    if peer.alias:
        ui._console.print(f"  alias    {peer.alias}")
    if peer.address:
        ui._console.print(f"  address  {peer.address}")
    ui._console.print(f"  allow    {', '.join(peer.allow) or '(none)'}")
    ui._console.print("")
    if status == "unverified":
        ui.dim(
            f"Tip: @{peer_id} likely has not pinned your pubkey. Share it\n"
            "with them and have them add you in their setup → Peers → Add.\n"
        )
        ui._console.print("")
    if ui.confirm(
        f"Copy your pubkey to clipboard? (share with @{peer_id})", default=False
    ):
        _copy_to_clipboard(self_pubkey)
        ui.ok_and_wait("copied")
    else:
        ui.press_enter()


def _remove(home: Path, entries: list[Peer]) -> None:
    items = [(f"@{p.id}", p.id, _peer_detail(p)) for p in entries]
    peer_id = ui.menu(
        ui.crumb("setup", "peers", "remove"),
        items,
        subtitle="drop a pinned peer",
        home=home,
        close="Back",
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

    raw_id = ui.text("Peer id (short handle, e.g. builder, home-server):")
    if not raw_id:
        return ui.cancelled()
    peer_id = raw_id.strip().lower()
    if not peer_id:
        ui.fail_and_wait(f"invalid id: {raw_id!r}")
        return
    if not all(c.isalnum() or c in "-_" for c in peer_id):
        ui.fail_and_wait(
            f"invalid id: {peer_id!r} (use a-z, 0-9, '-', '_' only)"
        )
        return
    if peer_id != raw_id.strip():
        ui.dim(f"id normalized to {peer_id!r}")
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

    address = ui.text("Remote address (host:port for inter-machine; ENTER to skip):") or ""
    address = address.strip() or None
    if address is not None and not _valid_address(address):
        ui.fail_and_wait(f"invalid address: {address!r} — expected host:port with port 1-65535")
        return

    allow = _pick_capabilities()
    alias = ui.text("Alias (optional display label, ENTER to skip):") or ""

    peer = Peer(
        id=peer_id,
        pubkey=pubkey,
        alias=alias.strip(),
        address=address,
        allow=allow,
    )
    try:
        peers_mod.add(home, peer)
    except ValueError as e:
        ui.fail_and_wait(str(e))
        return
    transport = f"tcp {address}" if address else "unix socket (same machine)"
    ui.ok_and_wait(f"pinned @{peer_id} via {transport}")


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


def _valid_address(address: str) -> bool:
    """Accept ``host:port`` where host is non-empty and port is 1-65535.
    Host can be an IPv4, a hostname, or a Tailscale-style name; we don't
    resolve it here — a bad host just fails at dial time."""
    host, sep, port = address.rpartition(":")
    if not sep or not host or not port.isdigit():
        return False
    p = int(port)
    return 1 <= p <= 65535
