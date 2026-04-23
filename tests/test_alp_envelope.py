"""ALP envelope — build / sign / verify / replay."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from alpi.alp import PROTOCOL_VERSION, envelope as env
from alpi.alp.keys import Keypair, generate


@pytest.fixture
def alice_bob(tmp_path: Path) -> tuple[Keypair, Keypair]:
    a = generate(tmp_path / "alice")
    b = generate(tmp_path / "bob")
    return a, b


# Build + verify roundtrip


def test_request_roundtrips_through_verify(alice_bob) -> None:
    alice, bob = alice_bob
    body = env.build_request(
        sender=alice,
        recipient_pubkey_b64=bob.pubkey_b64(),
        method="link.ping",
        params={"nonce": "abc"},
    )
    parsed = env.verify(body)
    assert parsed.method == "link.ping"
    assert parsed.params == {"nonce": "abc"}
    assert parsed.alp["from"] == alice.pubkey_b64()
    assert parsed.alp["to"] == bob.pubkey_b64()
    assert parsed.alp["v"] == PROTOCOL_VERSION


def test_response_roundtrips_through_verify(alice_bob) -> None:
    alice, bob = alice_bob
    body = env.build_response(
        sender=bob,
        recipient_pubkey_b64=alice.pubkey_b64(),
        request_id="req-123",
        result={"nonce": "abc", "version": 1, "agent_name": "bob"},
    )
    parsed = env.verify(body)
    assert parsed.id == "req-123"
    assert parsed.result["agent_name"] == "bob"
    assert parsed.error is None


def test_response_must_carry_result_xor_error(alice_bob) -> None:
    alice, _ = alice_bob
    with pytest.raises(ValueError):
        env.build_response(
            sender=alice, recipient_pubkey_b64=alice.pubkey_b64(),
            request_id="x", result={"ok": True}, error={"code": -1, "message": ""},
        )
    with pytest.raises(ValueError):
        env.build_response(
            sender=alice, recipient_pubkey_b64=alice.pubkey_b64(),
            request_id="x",
        )


# Signature checks


def test_tampered_body_fails_signature(alice_bob) -> None:
    alice, bob = alice_bob
    body = env.build_request(
        sender=alice, recipient_pubkey_b64=bob.pubkey_b64(),
        method="link.ask", params={"prompt": "hi"},
    )
    body["params"]["prompt"] = "hi; rm -rf /"   # in-flight tamper
    with pytest.raises(env.BadSignature):
        env.verify(body)


def test_wrong_signer_pubkey_fails(alice_bob, tmp_path: Path) -> None:
    alice, bob = alice_bob
    body = env.build_request(
        sender=alice, recipient_pubkey_b64=bob.pubkey_b64(),
        method="link.ping", params={"nonce": "abc"},
    )
    # Pretend the message came from some third party whose key we know:
    mallory = generate(tmp_path / "mallory")
    body["alp"]["from"] = mallory.pubkey_b64()
    with pytest.raises(env.BadSignature):
        env.verify(body)


# Version check


def test_unknown_version_rejected(alice_bob) -> None:
    alice, bob = alice_bob
    body = env.build_request(
        sender=alice, recipient_pubkey_b64=bob.pubkey_b64(),
        method="link.ping",
    )
    body["alp"]["v"] = PROTOCOL_VERSION + 99
    # Re-sign so signature isn't the reason we reject (isolate the check).
    body["alp"]["sig"] = env._sign(body, alice)
    with pytest.raises(env.BadVersion):
        env.verify(body)


# Timestamp skew


def test_stale_timestamp_rejected(alice_bob) -> None:
    alice, bob = alice_bob
    body = env.build_request(
        sender=alice, recipient_pubkey_b64=bob.pubkey_b64(),
        method="link.ping",
    )
    # Verify with a clock 10 minutes ahead — ts window is 2 minutes.
    ten_min_ahead = datetime.now(timezone.utc) + timedelta(minutes=10)
    with pytest.raises(env.StaleTimestamp):
        env.verify(body, now=ten_min_ahead)


def test_clock_skew_within_window_is_fine(alice_bob) -> None:
    alice, bob = alice_bob
    body = env.build_request(
        sender=alice, recipient_pubkey_b64=bob.pubkey_b64(),
        method="link.ping",
    )
    almost = datetime.now(timezone.utc) + timedelta(seconds=90)
    # 90s is under the 2-min bound; should pass.
    env.verify(body, now=almost)


# Replay cache


def test_replay_of_same_envelope_detected(alice_bob) -> None:
    alice, bob = alice_bob
    body = env.build_request(
        sender=alice, recipient_pubkey_b64=bob.pubkey_b64(),
        method="link.ping",
    )
    cache = env.ReplayCache()
    env.verify(body, replay_cache=cache)
    with pytest.raises(env.ReplayDetected):
        env.verify(body, replay_cache=cache)


def test_different_nonces_from_same_sender_are_fine(alice_bob) -> None:
    alice, bob = alice_bob
    cache = env.ReplayCache()
    for _ in range(3):
        body = env.build_request(
            sender=alice, recipient_pubkey_b64=bob.pubkey_b64(),
            method="link.ping",
        )
        env.verify(body, replay_cache=cache)


def test_replay_cache_evicts_old_entries() -> None:
    cache = env.ReplayCache(window=timedelta(milliseconds=50))
    cache.check_and_record("pk", "nonce-1")
    time.sleep(0.08)
    # After the window passes, the same nonce should be accepted again.
    cache.check_and_record("pk", "nonce-1")


# Shape failures


def test_missing_alp_block_rejected() -> None:
    with pytest.raises(env.EnvelopeError):
        env.verify({"jsonrpc": "2.0", "id": "x", "method": "link.ping"})


def test_missing_sig_field_rejected(alice_bob) -> None:
    alice, bob = alice_bob
    body = env.build_request(
        sender=alice, recipient_pubkey_b64=bob.pubkey_b64(),
        method="link.ping",
    )
    del body["alp"]["sig"]
    with pytest.raises(env.EnvelopeError):
        env.verify(body)


def test_verify_returns_envelope_dataclass(alice_bob) -> None:
    alice, bob = alice_bob
    body = env.build_request(
        sender=alice, recipient_pubkey_b64=bob.pubkey_b64(),
        method="link.ask", params={"prompt": "hello"},
    )
    parsed = env.verify(body)
    assert isinstance(parsed, env.Envelope)
    assert parsed.method == "link.ask"
    assert parsed.result is None
    assert parsed.error is None
