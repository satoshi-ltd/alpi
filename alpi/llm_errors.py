from __future__ import annotations

import re
from dataclasses import dataclass

from alpi._redact import redact

DETAIL_MAX_CHARS = 500

MESSAGES = {
    "context_length": "This conversation no longer fits the model's context window.",
    "insufficient_credit": "The model provider account is out of credit or over its quota.",
    "auth": "The model provider rejected the API key.",
    "forbidden": "The model provider refused access to this model or request.",
    "model_unavailable": "The model is not available from its provider.",
    "content_policy": "The model provider refused this request under its content policy.",
    "rate_limited": "The model provider is rate limiting requests. Try again in a moment.",
    "timeout": "The model took too long to answer. Try again.",
    "provider_unavailable": "The model provider is having trouble right now. Try again in a moment.",
    "bad_request": "The model provider rejected the request.",
    "unknown": "The model call failed.",
}

_CONTEXT_TEXT = re.compile(
    r"context[ _]?(length|window)|maximum context|too many tokens|prompt is too long|input is too long"
    r"|input token count|exceeds the maximum number of tokens",
    re.I,
)
_CREDIT_TEXT = re.compile(
    r"insufficient[ _](credit|funds|balance|quota)|out of credit|credit balance|exceeded your current quota"
    r"|payment required|more credits|key limit exceeded|spend limit",
    re.I,
)
_MODEL_TEXT = re.compile(
    r"model[^.\n]{0,80}(not found|does not exist|not available)|no endpoints found|llm provider not provided",
    re.I,
)
_MODERATION_TEXT = re.compile(r"flagged|moderation|content policy|safety", re.I)
_TIMEOUT_TEXT = re.compile(r"timed? ?out", re.I)
_OVERLOAD_TEXT = re.compile(r"overloaded|temporarily unavailable|service unavailable|bad gateway", re.I)
_TIMEOUT_NAMES = frozenset({
    "Timeout", "APITimeoutError", "ProviderStalled", "ProviderStreamDeadline",
    "ReadTimeout", "ConnectTimeout", "PoolTimeout", "WriteTimeout",
})
_UNAVAILABLE_NAMES = frozenset({
    "ServiceUnavailableError", "InternalServerError", "BadGatewayError", "APIConnectionError",
    "ConnectError", "RemoteProtocolError", "ReadError", "WriteError", "NetworkError",
})


@dataclass(frozen=True)
class Explained:
    code: str
    message: str
    detail: str


def _chain(exc: BaseException) -> list[BaseException]:
    seen: set[int] = set()
    out: list[BaseException] = []
    cur: BaseException | None = exc
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        out.append(cur)
        nxt = getattr(cur, "original_exception", None) or cur.__cause__
        cur = nxt if isinstance(nxt, BaseException) else None
    return out


def _text(item: BaseException) -> str:
    try:
        return str(item)
    except Exception:  # noqa: BLE001
        return type(item).__name__


def _status(chain: list[BaseException]) -> int | None:
    for item in chain:
        value = getattr(item, "status_code", None)
        if isinstance(value, str) and value.isdigit():
            value = int(value)
        if isinstance(value, int):
            return value
    return None


def _detail(exc: BaseException) -> str:
    name = type(exc).__name__
    text = " ".join(str(redact(_text(exc))).split())
    if not text:
        return name
    if not text.startswith((name, f"litellm.{name}")):
        text = f"{name}: {text}"
    return text if len(text) <= DETAIL_MAX_CHARS else text[: DETAIL_MAX_CHARS - 1] + "…"


def _classify_request_error(text: str, status: int | None) -> str:
    if status == 413 or _CONTEXT_TEXT.search(text):
        return "context_length"
    if _CREDIT_TEXT.search(text):
        return "insufficient_credit"
    if _MODEL_TEXT.search(text):
        return "model_unavailable"
    return "bad_request"


def classify(exc: BaseException) -> str:
    chain = _chain(exc)
    names = {type(item).__name__ for item in chain}
    status = _status(chain)
    text = " ".join(_text(item) for item in chain)
    if "ContextWindowExceededError" in names:
        return "context_length"
    if names & _TIMEOUT_NAMES or status == 408 or any(isinstance(item, TimeoutError) for item in chain):
        return "timeout"
    if "ContentPolicyViolationError" in names:
        return "content_policy"
    if "AuthenticationError" in names or status == 401:
        return "auth"
    if "PermissionDeniedError" in names or status == 403:
        if _MODERATION_TEXT.search(text):
            return "content_policy"
        return "insufficient_credit" if _CREDIT_TEXT.search(text) else "forbidden"
    if status == 402:
        return "insufficient_credit"
    if "NotFoundError" in names or status == 404:
        return "model_unavailable"
    if "RateLimitError" in names or status == 429:
        return "insufficient_credit" if _CREDIT_TEXT.search(text) else "rate_limited"
    if (
        names & _UNAVAILABLE_NAMES
        or (status is not None and status >= 500)
        or any(isinstance(item, ConnectionError) for item in chain)
    ):
        return "provider_unavailable"
    if "BadRequestError" in names or status in {400, 413, 422} or (status is not None and 400 <= status < 500):
        return _classify_request_error(text, status)
    if "APIError" in names:
        return "provider_unavailable"
    if _CONTEXT_TEXT.search(text):
        return "context_length"
    if _TIMEOUT_TEXT.search(text):
        return "timeout"
    if _OVERLOAD_TEXT.search(text):
        return "provider_unavailable"
    return "unknown"


def explain(exc: BaseException) -> Explained:
    code = classify(exc)
    return Explained(code=code, message=MESSAGES[code], detail=_detail(exc))
