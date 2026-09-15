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
MAX_KEYS = 4096


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

    def over(self, cap: int, now: float) -> bool:
        cutoff = now - WINDOW_SECONDS
        while self.stamps and self.stamps[0] < cutoff:
            self.stamps.popleft()
        return len(self.stamps) >= cap


class RateLimiter:
    """Keyed by peer pubkey (Ed25519 base64, same as the identity). One
    instance per server; thread-safe via the GIL for the data
    structures we touch (append / popleft / len)."""

    def __init__(self, default_per_minute: int = DEFAULT_PER_MINUTE, max_keys: int = MAX_KEYS) -> None:
        self._buckets: dict[str, _Bucket] = {}
        self._default = default_per_minute
        self._max_keys = max(1, int(max_keys))

    def _bucket_for(self, key: str, now: float) -> _Bucket:
        bucket = self._buckets.get(key)
        if bucket is None:
            if len(self._buckets) >= self._max_keys:
                self._sweep(now)
            bucket = self._buckets[key] = _Bucket()
        return bucket

    def _sweep(self, now: float) -> None:
        cutoff = now - WINDOW_SECONDS
        for key in [k for k, b in self._buckets.items() if not b.stamps or b.stamps[-1] < cutoff]:
            del self._buckets[key]
        while len(self._buckets) >= self._max_keys:
            oldest = min(self._buckets, key=lambda k: self._buckets[k].stamps[-1])
            del self._buckets[oldest]

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
        current = now if now is not None else time.monotonic()
        return self._bucket_for(peer_pubkey, current).admit(cap, current)

    def exceeded(
        self,
        peer_pubkey: str,
        peer_rate_limit: dict[str, Any] | None = None,
        *,
        now: float | None = None,
    ) -> bool:
        bucket = self._buckets.get(peer_pubkey)
        if bucket is None:
            return False
        over = bucket.over(self.cap_for(peer_rate_limit), now if now is not None else time.monotonic())
        if not bucket.stamps:
            self._buckets.pop(peer_pubkey, None)
        return over

    def reset(self, peer_pubkey: str | None = None) -> None:
        """Test hook — clear one peer's history (or all)."""
        if peer_pubkey is None:
            self._buckets.clear()
        else:
            self._buckets.pop(peer_pubkey, None)
