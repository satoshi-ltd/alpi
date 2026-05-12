"""ALP message envelope — build, sign, verify.

The JSON-RPC 2.0 request / response envelope wraps every ALP
message (see ``docs/ALP.md`` §Envelope). Each envelope carries an
``alp`` block with the protocol version, sender and recipient
pubkeys, timestamp, nonce, and Ed25519 signature over the
canonical JSON of the envelope-sans-signature.

This module handles the cryptographic shape only. Transport
(Unix socket, Noise over TCP) and method dispatch (``link.ask``
et al.) live elsewhere.
"""

from __future__ import annotations

import json
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from cryptography.exceptions import InvalidSignature

from alpi.alp import PROTOCOL_VERSION
from alpi.alp.keys import Keypair, decode_pubkey


NONCE_BYTES = 16
TS_SKEW_MAX = timedelta(minutes=2)      # reject envelopes whose ts drifts more than this
REPLAY_WINDOW = timedelta(minutes=5)    # (from, nonce) pairs remembered this long


class EnvelopeError(ValueError):
    """Parent class for any envelope-level failure."""


class BadSignature(EnvelopeError):
    """Signature verification failed."""


class BadVersion(EnvelopeError):
    """``alp.v`` does not match what this implementation speaks."""


class StaleTimestamp(EnvelopeError):
    """``alp.ts`` is more than ``TS_SKEW_MAX`` off the receiver's clock."""


class ReplayDetected(EnvelopeError):
    """A ``(from, nonce)`` pair was seen within ``REPLAY_WINDOW``."""


class WrongRecipient(EnvelopeError):
    """``alp.to`` does not match the local node's identity."""


class WrongSender(EnvelopeError):
    """``alp.from`` does not match the expected peer for this exchange."""


class IdMismatch(EnvelopeError):
    """JSON-RPC ``id`` of the response does not match the request."""


@dataclass
class Envelope:
    """Parsed representation of an ALP message — helpful for tests
    and introspection. The wire form is the JSON object; this
    dataclass is the in-memory view."""

    jsonrpc: str            # always "2.0"
    id: str
    method: str | None      # present on requests, absent on responses
    params: dict[str, Any] | None
    result: Any | None
    error: dict[str, Any] | None
    alp: dict[str, Any]     # the signed block


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_nonce_hex() -> str:
    return secrets.token_hex(NONCE_BYTES)


def _canonical_bytes(data: dict[str, Any]) -> bytes:
    """Deterministic JSON — stable across runs, stable across
    implementations that agree on ``sort_keys=True`` + no extra
    whitespace + unicode escapes disabled (so UTF-8 bytes are
    identical)."""
    return json.dumps(
        data, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")


def build_request(
    *,
    sender: Keypair,
    recipient_pubkey_b64: str,
    method: str,
    params: dict[str, Any] | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Assemble + sign a JSON-RPC request envelope ready for the wire."""
    body: dict[str, Any] = {
        "jsonrpc": "2.0",
        "id": request_id or _new_nonce_hex(),
        "method": method,
        "params": params or {},
        "alp": {
            "v": PROTOCOL_VERSION,
            "from": sender.pubkey_b64(),
            "to": recipient_pubkey_b64,
            "ts": _now().isoformat().replace("+00:00", "Z"),
            "nonce": _new_nonce_hex(),
        },
    }
    body["alp"]["sig"] = _sign(body, sender)
    return body


def build_response(
    *,
    sender: Keypair,
    recipient_pubkey_b64: str,
    request_id: str,
    result: Any = None,
    error: dict[str, Any] | None = None,
    stream: str | None = None,
) -> dict[str, Any]:
    """Assemble + sign a response envelope. Exactly one of ``result``
    or ``error`` must be set. ``stream`` is an optional marker for
    streaming handlers — ``"chunk"`` for intermediate frames,
    ``"final"`` for the last one. Absent = single non-streaming reply."""
    if (result is None) == (error is None):
        raise ValueError("response must carry exactly one of result / error")
    body: dict[str, Any] = {
        "jsonrpc": "2.0",
        "id": request_id,
        "alp": {
            "v": PROTOCOL_VERSION,
            "from": sender.pubkey_b64(),
            "to": recipient_pubkey_b64,
            "ts": _now().isoformat().replace("+00:00", "Z"),
            "nonce": _new_nonce_hex(),
        },
    }
    if error is None:
        body["result"] = result
    else:
        body["error"] = error
    if stream is not None:
        body["stream"] = stream
    body["alp"]["sig"] = _sign(body, sender)
    return body


def _sign(body: dict[str, Any], sender: Keypair) -> str:
    """Sign the envelope with the ``sig`` field stripped. Returns
    the base64 of the raw 64-byte Ed25519 signature."""
    import base64
    payload = _stripped_for_signing(body)
    sig = sender.sign(_canonical_bytes(payload))
    return base64.b64encode(sig).decode("ascii")


def _stripped_for_signing(body: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of ``body`` with ``alp.sig`` removed so sign and
    verify hash exactly the same bytes."""
    alp = {k: v for k, v in body["alp"].items() if k != "sig"}
    out = dict(body)
    out["alp"] = alp
    return out


def verify(
    body: dict[str, Any],
    *,
    now: datetime | None = None,
    replay_cache: "ReplayCache | None" = None,
    expected_to: str | None = None,
    expected_from: str | None = None,
    expected_id: str | None = None,
) -> Envelope:
    """Validate the envelope end to end.

    Checks (in order, fail fast):
      1. Structural shape — ``alp`` block with all required fields.
      2. Protocol version matches ``PROTOCOL_VERSION``.
      3. Timestamp within ``TS_SKEW_MAX`` of ``now``.
      4. Signature verifies against the ``from`` pubkey.
      5. ``(from, nonce)`` not in the replay cache.
      6. ``alp.to == expected_to`` when set (cross-target replay guard).
      7. ``alp.from == expected_from`` when set (response sender pin).
      8. ``body.id == expected_id`` when set (request/response binding).

    Raises the subclass of ``EnvelopeError`` matching the first
    failing check. Returns a parsed ``Envelope`` on success.
    """
    import base64

    if not isinstance(body, dict) or "alp" not in body:
        raise EnvelopeError("missing alp block")
    alp = body["alp"]
    for field_name in ("v", "from", "to", "ts", "nonce", "sig"):
        if field_name not in alp:
            raise EnvelopeError(f"alp.{field_name} missing")

    if alp["v"] != PROTOCOL_VERSION:
        raise BadVersion(
            f"alp.v={alp['v']} not supported (this node speaks {PROTOCOL_VERSION})",
        )

    ts = _parse_iso(alp["ts"])
    delta = (now or _now()) - ts
    if abs(delta) > TS_SKEW_MAX:
        raise StaleTimestamp(f"ts off by {delta}")

    sig = base64.b64decode(alp["sig"])
    payload = _canonical_bytes(_stripped_for_signing(body))
    try:
        decode_pubkey(alp["from"]).verify(sig, payload)
    except InvalidSignature as e:
        raise BadSignature("signature did not verify") from e

    if replay_cache is not None:
        replay_cache.check_and_record(alp["from"], alp["nonce"])

    if expected_to is not None and alp["to"] != expected_to:
        raise WrongRecipient(
            f"alp.to={alp['to'][:12]}… does not match local id "
            f"{expected_to[:12]}…",
        )
    if expected_from is not None and alp["from"] != expected_from:
        raise WrongSender(
            f"alp.from={alp['from'][:12]}… does not match expected peer "
            f"{expected_from[:12]}…",
        )
    if expected_id is not None and body.get("id") != expected_id:
        raise IdMismatch(
            f"response id={body.get('id')!r} does not match request "
            f"id={expected_id!r}",
        )

    return Envelope(
        jsonrpc=body.get("jsonrpc", ""),
        id=body.get("id", ""),
        method=body.get("method"),
        params=body.get("params"),
        result=body.get("result"),
        error=body.get("error"),
        alp=alp,
    )


def _parse_iso(ts: str) -> datetime:
    """Parse ``alp.ts``. Accepts either ``+00:00`` or trailing ``Z``."""
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    return datetime.fromisoformat(ts)


@dataclass
class ReplayCache:
    """In-memory cache of ``(from, nonce)`` pairs seen within
    ``REPLAY_WINDOW``. Per-process; not shared across restarts — the
    timestamp skew bound limits what an attacker can replay across a
    restart (two minutes)."""

    window: timedelta = field(default_factory=lambda: REPLAY_WINDOW)
    _seen: dict[tuple[str, str], float] = field(default_factory=dict)

    def check_and_record(self, from_: str, nonce: str) -> None:
        key = (from_, nonce)
        now = time.monotonic()
        self._evict(now)
        if key in self._seen:
            raise ReplayDetected(f"nonce already used by {from_}")
        self._seen[key] = now

    def _evict(self, now: float) -> None:
        cutoff = now - self.window.total_seconds()
        stale = [k for k, v in self._seen.items() if v < cutoff]
        for k in stale:
            del self._seen[k]
