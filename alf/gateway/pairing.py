"""Pairing — map an external chat (platform + chat_id) to an alf profile.

Stored in ~/.alf/gateway/pairing.json:

    {
      "telegram:123456789": {"profile": "default", "allow": true},
      "webhook:abc":        {"profile": "work",    "allow": true}
    }

v0 is mono-user: we mostly check that an incoming chat is in the allowlist.
Multi-user routing per profile is wired but trivial in practice.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Pairing:
    profile: str
    allow: bool


class PairingStore:
    def __init__(self, home: Path):
        self.path = home / "gateway" / "pairing.json"

    def _load(self) -> dict[str, dict]:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text())

    def _save(self, data: dict[str, dict]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=2))

    def get(self, platform: str, chat_id: str) -> Pairing | None:
        entry = self._load().get(f"{platform}:{chat_id}")
        if not entry:
            return None
        return Pairing(profile=entry.get("profile", "default"),
                       allow=bool(entry.get("allow", False)))

    def set(self, platform: str, chat_id: str, profile: str = "default",
            allow: bool = True) -> None:
        data = self._load()
        data[f"{platform}:{chat_id}"] = {"profile": profile, "allow": allow}
        self._save(data)
