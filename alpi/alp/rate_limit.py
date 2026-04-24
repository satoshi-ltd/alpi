"""Per-peer rate limiting for ALP — sliding-window counter in RAM.

Cap comes from ``peer.rate_limit.per_minute`` in ``peers.yaml``
(default 60). Over-cap requests get JSON-RPC ``-32005``. In-memory by
design: fresh window on daemon restart beats leaving a peer locked out.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any


DEFAULT_PER_MINUTE = 60
WINDOW_SECONDS = 60.0


@dataclass
class _Bucket:
    """Sliding-window counter backed by a deque of monotonic timestamps."""

    stamps: "deque[float]" = field(default_factory=deque)

    def admit(self, cap: int, now: float) -> bool:
        """Return True if another request fits under ``cap`` per
        ``WINDOW_SECONDS``. Prunes stamps older than the window first."""
        cutoff = now - WINDOW_SECONDS
        while self.stamps and self.stamps[0] < cutoff:
            self.stamps.popleft()
        if len(self.stamps) >= cap:
            return False
        self.stamps.append(now)
        return True


class RateLimiter:
    """Keyed by peer pubkey (Ed25519 base64, same as the identity). One
    instance per server; thread-safe via the GIL for the data
    structures we touch (append / popleft / len)."""

    def __init__(self, default_per_minute: int = DEFAULT_PER_MINUTE) -> None:
        self._buckets: dict[str, _Bucket] = {}
        self._default = default_per_minute

    def cap_for(self, peer_rate_limit: dict[str, Any] | None) -> int:
        if not peer_rate_limit:
            return self._default
        val = peer_rate_limit.get("per_minute")
        if not isinstance(val, int) or val <= 0:
            return self._default
        return val

    def admit(
        self,
        peer_pubkey: str,
        peer_rate_limit: dict[str, Any] | None,
        *,
        now: float | None = None,
    ) -> bool:
        """True if this request is within the peer's budget, False if
        it has exceeded and should be rejected with ``-32005``."""
        cap = self.cap_for(peer_rate_limit)
        bucket = self._buckets.setdefault(peer_pubkey, _Bucket())
        return bucket.admit(cap, now if now is not None else time.monotonic())

    def reset(self, peer_pubkey: str | None = None) -> None:
        """Test hook — clear one peer's history (or all)."""
        if peer_pubkey is None:
            self._buckets.clear()
        else:
            self._buckets.pop(peer_pubkey, None)
