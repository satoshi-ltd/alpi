from __future__ import annotations

from alpi.alp import rate_limit as rl


def test_exceeded_checks_without_recording_and_admit_records() -> None:
    limiter = rl.RateLimiter(default_per_minute=2)

    assert limiter.exceeded("src", now=0.0) is False
    assert limiter.admit("src", None, now=0.0) is True
    assert limiter.admit("src", None, now=1.0) is True
    assert limiter.exceeded("src", now=2.0) is True
    assert limiter.exceeded("src", now=2.0) is True
    assert limiter.exceeded("other", now=2.0) is False


def test_buckets_are_bounded_and_expired_keys_are_swept() -> None:
    limiter = rl.RateLimiter(default_per_minute=5, max_keys=100)
    for index in range(10_000):
        limiter.admit(f"src-{index}", None, now=float(index) / 1000)

    assert len(limiter._buckets) <= 100

    later = 10.0 + rl.WINDOW_SECONDS + 1.0
    limiter.admit("fresh", None, now=later)
    assert set(limiter._buckets) == {"fresh"}

    assert limiter.exceeded("fresh", now=later + rl.WINDOW_SECONDS + 1.0) is False
    assert limiter._buckets == {}


def test_exceeded_clears_once_the_window_slides() -> None:
    limiter = rl.RateLimiter(default_per_minute=1)
    limiter.admit("src", None, now=10.0)

    assert limiter.exceeded("src", now=10.0 + rl.WINDOW_SECONDS - 0.01) is True
    assert limiter.exceeded("src", now=10.0 + rl.WINDOW_SECONDS + 0.01) is False
