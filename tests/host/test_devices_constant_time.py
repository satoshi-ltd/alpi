import hmac
import inspect

from alpi.host import devices as devices_mod


def test_tokens_match_uses_compare_digest():
    src = inspect.getsource(devices_mod._tokens_match)
    assert "compare_digest" in src, (
        "_tokens_match must delegate to hmac.compare_digest for constant-time compare"
    )


def test_tokens_match_handles_unicode_without_raising():
    assert devices_mod._tokens_match("🔑secret", "🔑secret") is True
    assert devices_mod._tokens_match("🔑secret", "ascii") is False
    assert devices_mod._tokens_match("ascii", "🔑secret") is False
    assert devices_mod._tokens_match("café", "café") is True


def test_tokens_match_returns_true_on_equal_tokens():
    tok = "abcdefghijABCDEFGHIJ0123456789ab"
    assert devices_mod._tokens_match(tok, tok) is True


def test_tokens_match_returns_false_on_different_lengths():
    assert devices_mod._tokens_match("short", "shorter") is False
    assert devices_mod._tokens_match("longer", "long") is False


def test_tokens_match_returns_false_on_empty_inputs():
    assert devices_mod._tokens_match("", "anything") is False
    assert devices_mod._tokens_match("anything", "") is False
    assert devices_mod._tokens_match("", "") is False


def test_tokens_match_matches_hmac_compare_digest_on_same_length_diff():
    a = "X" * 32
    b = "Y" * 32
    assert devices_mod._tokens_match(a, b) is False
    assert devices_mod._tokens_match(a, b) is hmac.compare_digest(a, b)


def test_devices_module_does_not_use_plain_equality_on_secret_tokens():
    src = inspect.getsource(devices_mod)
    for needle in ('d["token"] == token', "d['token'] == token"):
        assert needle not in src, (
            f"plain `==` on the secret token returned to devices.py: {needle!r}. "
            f"Use _tokens_match() / hmac.compare_digest."
        )
