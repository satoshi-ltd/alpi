from __future__ import annotations

import httpx
import litellm
import pytest

from alpi import llm
from alpi.llm_errors import DETAIL_MAX_CHARS, MESSAGES, classify, explain


def _make(cls, message: str = "provider said no", **extra):
    try:
        return cls(message=message, model="m", llm_provider="openrouter", **extra)
    except TypeError:
        response = httpx.Response(403, request=httpx.Request("POST", "https://provider.test"))
        return cls(message=message, model="m", llm_provider="openrouter", response=response, **extra)


@pytest.mark.parametrize(("exc", "code"), [
    (_make(litellm.RateLimitError), "rate_limited"),
    (_make(litellm.AuthenticationError), "auth"),
    (_make(litellm.PermissionDeniedError), "forbidden"),
    (_make(litellm.NotFoundError), "model_unavailable"),
    (_make(litellm.ContextWindowExceededError), "context_length"),
    (_make(litellm.ContentPolicyViolationError), "content_policy"),
    (_make(litellm.Timeout), "timeout"),
    (_make(litellm.ServiceUnavailableError), "provider_unavailable"),
    (_make(litellm.InternalServerError), "provider_unavailable"),
    (_make(litellm.APIConnectionError), "provider_unavailable"),
    (_make(litellm.BadRequestError), "bad_request"),
    (llm.ProviderStalled("no bytes for 60 s"), "timeout"),
    (llm.ProviderStreamDeadline("stream deadline"), "timeout"),
    (RuntimeError("something odd"), "unknown"),
])
def test_known_failures_get_their_class(exc: Exception, code: str) -> None:
    assert classify(exc) == code
    assert explain(exc).message == MESSAGES[code]


def test_an_out_of_credit_rate_limit_is_credit_not_rate_limiting() -> None:
    exc = _make(litellm.RateLimitError, "You exceeded your current quota, please check your plan and billing")

    assert classify(exc) == "insufficient_credit"


def test_a_402_from_the_provider_is_credit() -> None:
    exc = _make(litellm.APIError, "Insufficient credits", status_code=402)

    assert classify(exc) == "insufficient_credit"


def test_a_context_overflow_reported_as_a_bad_request_is_recognised_by_its_text() -> None:
    exc = _make(litellm.BadRequestError, "This model's maximum context length is 128000 tokens")

    assert classify(exc) == "context_length"


def test_the_real_cause_inside_a_wrapper_decides() -> None:
    inner = _make(litellm.RateLimitError, "slow down")
    wrapper = litellm.exceptions.MidStreamFallbackError(
        message="fallback failed", model="m", llm_provider="openrouter",
        original_exception=inner,
    )

    assert classify(wrapper) == "rate_limited"


def test_a_cause_chained_with_raise_from_decides() -> None:
    try:
        try:
            raise _make(litellm.AuthenticationError, "bad key")
        except litellm.AuthenticationError as inner:
            raise RuntimeError("call failed") from inner
    except RuntimeError as outer:
        assert classify(outer) == "auth"


def test_the_detail_is_redacted_and_capped_and_names_the_class() -> None:
    exc = _make(litellm.AuthenticationError, "Incorrect API key provided: sk-abcdefghijklmnopqrstuvwxyz0123456789 " + "x" * 2000)

    detail = explain(exc).detail

    assert "sk-abcdefghijklmnop" not in detail
    assert "[REDACTED]" in detail
    assert "AuthenticationError" in detail.split(":")[0]
    assert len(detail) <= DETAIL_MAX_CHARS


def test_the_message_never_carries_provider_text() -> None:
    exc = _make(litellm.RateLimitError, "OpenrouterException - {'error': {'message': 'secret-ish'}}")

    assert "Openrouter" not in explain(exc).message
    assert "secret-ish" not in explain(exc).message


@pytest.mark.parametrize(("exc", "code"), [
    (_make(litellm.Timeout, "timeout; see billing docs"), "timeout"),
    (_make(litellm.InternalServerError, "Internal error: context length computation failed"), "provider_unavailable"),
    (_make(litellm.ServiceUnavailableError, "upstream: model foo-1 not found in region cache"), "provider_unavailable"),
    (_make(litellm.RateLimitError, "The model gemini-x is overloaded, not available right now"), "rate_limited"),
    (_make(litellm.BadRequestError, "invalid tool arg: billing_address is required"), "bad_request"),
    (_make(litellm.BadRequestError, "connection timed out to host is not valid"), "bad_request"),
    (_make(litellm.BadRequestError, "Model gpt-x does not support parameter temperature; unknown value"), "bad_request"),
    (_make(litellm.APIError, "payload too large", status_code=413), "context_length"),
    (_make(litellm.APIError, "unprocessable", status_code=422), "bad_request"),
    (_make(litellm.APIError, "boom", status_code=502), "provider_unavailable"),
])
def test_loose_words_never_override_a_structural_signal(exc: Exception, code: str) -> None:
    assert classify(exc) == code


@pytest.mark.parametrize(("message", "code"), [
    ("Your input was flagged by moderation", "content_policy"),
    ("Key limit exceeded (total limit)", "insufficient_credit"),
    ("Model is not available in your region", "forbidden"),
    ("Request not allowed", "forbidden"),
])
def test_a_403_is_only_an_auth_problem_when_nothing_else_explains_it(message: str, code: str) -> None:
    assert classify(_make(litellm.PermissionDeniedError, message)) == code


def test_a_plain_401_is_a_rejected_key() -> None:
    assert classify(_make(litellm.APIError, "unauthorized", status_code=401)) == "auth"


@pytest.mark.parametrize(("exc", "code"), [
    (httpx.ReadTimeout(""), "timeout"),
    (httpx.ConnectTimeout(""), "timeout"),
    (TimeoutError(), "timeout"),
    (httpx.ConnectError("refused"), "provider_unavailable"),
    (httpx.RemoteProtocolError("peer closed"), "provider_unavailable"),
    (ConnectionResetError("reset"), "provider_unavailable"),
])
def test_raw_transport_errors_are_recognised(exc: Exception, code: str) -> None:
    assert classify(exc) == code


@pytest.mark.parametrize(("message", "code"), [
    ("The input token count (1200000) exceeds the maximum number of tokens allowed (1048576)", "context_length"),
    ("LLM Provider NOT provided. Pass in the LiteLLM provider you are trying to call. model=foo/bar", "model_unavailable"),
    ("No endpoints found for deepseek/deepseek-x", "model_unavailable"),
])
def test_provider_phrasings_of_a_bad_request(message: str, code: str) -> None:
    assert classify(_make(litellm.BadRequestError, message)) == code


def test_the_detail_does_not_repeat_the_class_name_litellm_already_prefixes() -> None:
    exc = _make(litellm.AuthenticationError, "bad key")

    assert explain(exc).detail.count("AuthenticationError") == 1


def test_a_hostile_exception_cannot_break_the_error_path() -> None:
    class Hostile(Exception):
        original_exception = "not an exception"

        def __str__(self) -> str:
            raise RuntimeError("no text for you")

    explained = explain(Hostile())

    assert explained.code == "unknown"
    assert explained.detail == "Hostile"
