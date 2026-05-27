"""ALP peer list — ``~/.alpi/<profile>/peers.yaml``.

One file per profile. Each entry pins a remote agent's pubkey
and declares which methods that peer may invoke on us. Fail-
closed: peers not in the list are rejected at the transport
layer before payloads are parsed; methods not in ``allow`` are
rejected with ``-32001 capability-denied``.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

import yaml


_ALP_DIR = "alp"
_FILENAME = "peers.yaml"


@dataclass
class Peer:
    id: str                                        # human handle
    pubkey: str                                    # base64 Ed25519 public key — identity
    alias: str = ""                                # optional display label
    address: str | None = None                     # host:port for inter-machine; None for intra-profile
    allow: list[str] = field(default_factory=list)
    budget: dict[str, Any] = field(default_factory=dict)
    rate_limit: dict[str, Any] = field(default_factory=dict)

    def may_call(self, method: str) -> bool:
        """Capability check — empty allow list denies everything.
        ``workgroup.*`` bypasses the allow list; membership (enforced
        per-handler with ``-32008 workgroup-not-member``) is the real
        gate, and ``workgroup.join`` doesn't retroactively edit
        ``peers.yaml``."""
        if method.startswith("workgroup."):
            return True
        return method in self.allow


def path(home: Path) -> Path:
    return home / _ALP_DIR / _FILENAME


def load(home: Path) -> list[Peer]:
    """Read + parse the peer list. Missing / malformed → empty list,
    never raises. Invalid entries (missing id or pubkey) are skipped
    with no warning — the transport drops traffic for unknown peers
    anyway, so a broken entry is equivalent to 'peer not configured'."""
    p = path(home)
    if not p.exists():
        return []
    try:
        raw = yaml.safe_load(p.read_text()) or []
    except yaml.YAMLError:
        return []
    if not isinstance(raw, list):
        return []
    out: list[Peer] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        if "id" not in entry or "pubkey" not in entry:
            continue
        out.append(Peer(
            id=str(entry["id"]),
            pubkey=str(entry["pubkey"]),
            alias=str(entry.get("alias") or ""),
            address=entry.get("address"),
            allow=[str(m) for m in (entry.get("allow") or [])],
            budget=dict(entry.get("budget") or {}),
            rate_limit=dict(entry.get("rate_limit") or {}),
        ))
    return out


def save(home: Path, peers: list[Peer]) -> None:
    p = path(home)
    p.parent.mkdir(parents=True, exist_ok=True)
    data = [asdict(peer) for peer in peers]
    # Trim empty optional fields so the file stays minimal.
    for entry in data:
        if not entry.get("alias"):
            entry.pop("alias", None)
        if entry.get("address") is None:
            entry.pop("address", None)
        if not entry.get("budget"):
            entry.pop("budget", None)
        if not entry.get("rate_limit"):
            entry.pop("rate_limit", None)
    p.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True))


def get_by_id(home: Path, peer_id: str) -> Peer | None:
    for p in load(home):
        if p.id == peer_id:
            return p
    return None


def get_by_pubkey(home: Path, pubkey_b64: str) -> Peer | None:
    for p in load(home):
        if p.pubkey == pubkey_b64:
            return p
    return None


def add(home: Path, peer: Peer) -> None:
    peers = load(home)
    if any(p.id == peer.id for p in peers):
        raise ValueError(f"peer {peer.id!r} already exists; remove it first")
    if any(p.pubkey == peer.pubkey for p in peers):
        raise ValueError(f"peer with pubkey already pinned under a different id")
    peers.append(peer)
    save(home, peers)


def remove(home: Path, peer_id: str) -> bool:
    peers = load(home)
    before = len(peers)
    peers = [p for p in peers if p.id != peer_id]
    if len(peers) == before:
        return False
    save(home, peers)
    return True


def local_socket_path(peer: Peer) -> Path:
    # Pubkey-first; peer.id is a user-chosen alias, not a routing key.
    from alpi import home as home_mod
    match = home_mod.find_home_by_pubkey(peer.pubkey) if peer.pubkey else None
    if match is None:
        root = home_mod.alpi_root()
        match = root if peer.id == "default" else root / "profiles" / peer.id
    return match / "alp" / "alp.sock"
