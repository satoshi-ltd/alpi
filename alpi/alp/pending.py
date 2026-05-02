from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


_FILENAME = "alp/pending_peers.yaml"
_CAP = 20


@dataclass
class Pending:
    pubkey: str
    first_seen: float
    last_seen: float
    address: str | None = None


def _path(home: Path) -> Path:
    return home / _FILENAME


def load(home: Path) -> list[Pending]:
    p = _path(home)
    if not p.exists():
        return []
    try:
        raw = yaml.safe_load(p.read_text()) or []
    except Exception:  # noqa: BLE001
        return []
    out: list[Pending] = []
    for entry in raw if isinstance(raw, list) else []:
        if not isinstance(entry, dict):
            continue
        pk = str(entry.get("pubkey") or "").strip()
        if not pk:
            continue
        out.append(Pending(
            pubkey=pk,
            first_seen=float(entry.get("first_seen") or 0.0),
            last_seen=float(entry.get("last_seen") or 0.0),
            address=entry.get("address") or None,
        ))
    return out


def save(home: Path, entries: list[Pending]) -> None:
    p = _path(home)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = [
        {
            "pubkey": e.pubkey,
            "first_seen": e.first_seen,
            "last_seen": e.last_seen,
            **({"address": e.address} if e.address else {}),
        }
        for e in entries
    ]
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True))
    import os as _os
    _os.chmod(tmp, 0o600)
    _os.replace(tmp, p)


def record(home: Path, pubkey: str, address: str | None = None) -> None:
    if not pubkey:
        return
    entries = load(home)
    now = time.time()
    for e in entries:
        if e.pubkey == pubkey:
            e.last_seen = now
            if address and not e.address:
                e.address = address
            save(home, entries)
            return
    entries.append(Pending(pubkey=pubkey, first_seen=now, last_seen=now, address=address))
    if len(entries) > _CAP:
        entries.sort(key=lambda x: x.last_seen, reverse=True)
        entries = entries[:_CAP]
    save(home, entries)


def remove(home: Path, pubkey: str) -> bool:
    entries = load(home)
    keep = [e for e in entries if e.pubkey != pubkey]
    if len(keep) == len(entries):
        return False
    save(home, keep)
    return True


def to_dicts(entries: list[Pending]) -> list[dict[str, Any]]:
    return [
        {
            "pubkey": e.pubkey,
            "first_seen": e.first_seen,
            "last_seen": e.last_seen,
            "address": e.address,
        }
        for e in entries
    ]
