from __future__ import annotations

import base64
import json
import time
import urllib.parse
from pathlib import Path
from typing import Any

import httpx
import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from alpi import config as cfg_mod
from alpi import llm, llm_errors
from alpi.providers import chatgpt, chatgpt_responses

_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _jwks() -> list[dict[str, str]]:
    numbers = _KEY.public_key().public_numbers()
    return [{
        "kty": "RSA", "kid": "k1", "alg": "RS256",
        "n": _b64(numbers.n.to_bytes(256, "big")), "e": _b64(numbers.e.to_bytes(3, "big")),
    }]


def _id_token(*, client_id: str = "oaiapp_1", nonce: str, sub: str = "user-1", **claims: Any) -> str:
    body = {"iss": chatgpt.ISSUER, "aud": client_id, "sub": sub, "email": "a@example.com", "nonce": nonce, "exp": time.time() + 600, **claims}
    signed = f"{_b64(json.dumps({'alg': 'RS256', 'kid': 'k1'}).encode())}.{_b64(json.dumps(body).encode())}"
    return f"{signed}.{_b64(_KEY.sign(signed.encode(), padding.PKCS1v15(), hashes.SHA256()))}"


@pytest.fixture
def web(monkeypatch):
    calls: list[tuple[str, str, dict[str, Any]]] = []
    answers: dict[str, Any] = {}

    def fake_send(self, request, **kw):
        url = str(request.url)
        if request.headers.get("content-type", "").startswith("application/json"):
            sent = json.loads(request.content or b"{}")
        else:
            sent = {k: v[0] for k, v in urllib.parse.parse_qs(request.content.decode()).items()}
        sent = {**sent, "_auth": request.headers.get("authorization", "")}
        calls.append((request.method, url, sent))
        answer = answers.get(url)
        if callable(answer):
            answer = answer(sent)
        if answer is None:
            return httpx.Response(404, json={"error": "unexpected request"}, request=request)
        status, body = answer
        if isinstance(body, bytes):
            return httpx.Response(status, content=body, headers={"content-type": "text/event-stream"}, request=request)
        return httpx.Response(status, json=body, request=request)

    monkeypatch.setattr(httpx.Client, "send", fake_send)
    return calls, answers


def _tokens(nonce: str, **over: Any) -> dict[str, Any]:
    return {
        "access_token": "at-1", "refresh_token": "rt-1", "id_token": _id_token(nonce=nonce), "token_type": "Bearer", "expires_in": 3600,
        "scope": "chatgpt.tokens.use.direct email offline_access openid profile resource.invoke", **over,
    }


def _sign_in(tmp_home: Path, web, **token_over: Any) -> dict[str, Any]:
    calls, answers = web
    attempt = chatgpt.begin(tmp_home, 1455)
    answers[chatgpt.TOKEN_URL] = (200, _tokens(attempt.nonce, **token_over))
    answers[chatgpt.MODELS_URL] = (200, {"models": [
        {"slug": "gpt-6.2-sol", "display_name": "GPT-6.2 Sol", "visibility": "list"},
        {"slug": "internal", "display_name": "Hidden", "visibility": "hide"},
    ]})
    return chatgpt.finish(tmp_home, attempt, {"code": "c-1", "state": attempt.state, "client_id": "oaiapp_1"}, keys=_jwks())


def _query(url: str) -> dict[str, str]:
    return {k: v[0] for k, v in urllib.parse.parse_qs(urllib.parse.urlsplit(url).query).items()}


def test_a_first_sign_in_registers_alpi_with_the_documented_request(tmp_home: Path) -> None:
    attempt = chatgpt.begin(tmp_home, 1455)
    sent = _query(attempt.url)

    assert attempt.url.startswith("https://auth.openai.com/api/accounts/authorize?")
    assert sent["client_id"] == "dynamic_agent_client" and sent["agent_name_hint"] == "alpi"
    assert sent["redirect_uri"] == "http://127.0.0.1:1455/auth/callback" and sent["response_type"] == "code"
    assert sent["scope"] == "openid profile email offline_access resource.invoke chatgpt.tokens.use.direct"
    assert sent["resource"] == "https://api.openai.com/v1" and sent["code_challenge_method"] == "S256"
    assert sent["state"] == attempt.state and sent["nonce"] == attempt.nonce
    assert sent["ext_agent_host_id"].startswith("urn:uuid:") and sent["ext_agent_host_id"] == chatgpt.host_id()
    assert "id_token_hint" not in sent and "login_hint" not in sent


def test_the_code_is_exchanged_and_the_credential_saved_owner_only(tmp_home: Path, web) -> None:
    calls, _ = web
    record = _sign_in(tmp_home, web)

    exchange = next(c for c in calls if c[1] == chatgpt.TOKEN_URL)[2]
    assert {k: exchange[k] for k in ("grant_type", "client_id", "code", "redirect_uri", "resource")} == {
        "grant_type": "authorization_code", "client_id": "oaiapp_1", "code": "c-1",
        "redirect_uri": "http://127.0.0.1:1455/auth/callback", "resource": "https://api.openai.com/v1",
    }
    assert exchange["code_verifier"] and "client_secret" not in exchange
    assert record["first_sign_in"] is True and chatgpt.signed_in(tmp_home)
    path = tmp_home / "secrets" / "chatgpt.json"
    assert path.stat().st_mode & 0o777 == 0o600
    assert not [p for p in path.parent.iterdir() if p.stat().st_mode & 0o077] and path.parent.stat().st_mode & 0o077 == 0
    from alpi import audit
    assert not [c for c in audit._audit_permissions(tmp_home) if c.name == "secrets/" and c.status == "fail"]
    saved = json.loads(path.read_text())
    assert (saved["client_id"], saved["subject"], saved["email"], saved["refresh_token"]) == ("oaiapp_1", "user-1", "a@example.com", "rt-1")
    assert "ext_agent_host_id" not in saved
    assert chatgpt.models(tmp_home) == [{"slug": "gpt-6.2-sol", "display_name": "GPT-6.2 Sol"}]


def test_a_later_sign_in_reuses_the_issued_client_and_hints_the_account(tmp_home: Path, web) -> None:
    _sign_in(tmp_home, web)

    sent = _query(chatgpt.begin(tmp_home, 54321).url)

    assert sent["client_id"] == "oaiapp_1" and "agent_name_hint" not in sent
    assert sent["login_hint"] == "a@example.com" and sent["id_token_hint"].count(".") == 2
    assert sent["redirect_uri"] == "http://127.0.0.1:54321/auth/callback"
    assert sent["ext_agent_host_id"] == chatgpt.host_id()


@pytest.mark.parametrize(("query", "code"), [
    ({"code": "c", "state": "other", "client_id": "oaiapp_1"}, "state_mismatch"),
    ({"error": "access_denied", "state": "STATE"}, "access_denied"),
    ({"code": "c", "state": "STATE"}, "registration_incomplete"),
    ({"code": "c", "state": "STATE", "client_id": "dynamic_agent_client"}, "registration_incomplete"),
    ({"state": "STATE", "client_id": "oaiapp_1"}, "no_code"),
])
def test_a_callback_that_is_not_this_attempt_saves_nothing(tmp_home: Path, web, query, code) -> None:
    attempt = chatgpt.begin(tmp_home, 1455)
    query = {k: (attempt.state if v == "STATE" else v) for k, v in query.items()}

    with pytest.raises(chatgpt.PlanError) as failed:
        chatgpt.finish(tmp_home, attempt, query, keys=_jwks())

    assert failed.value.code == code and not chatgpt.record_path(tmp_home).exists()
    assert not [c for c in web[0] if c[1] == chatgpt.TOKEN_URL]


@pytest.mark.parametrize("claims", [
    {"nonce": "another"}, {"iss": "https://evil.example"}, {"aud": "oaiapp_other"}, {"exp": 1.0}, {"sub": ""},
])
def test_an_id_token_for_another_sign_in_is_refused(tmp_home: Path, web, claims) -> None:
    _, answers = web
    attempt = chatgpt.begin(tmp_home, 1455)
    answers[chatgpt.TOKEN_URL] = (200, _tokens(attempt.nonce, id_token=_id_token(**{"nonce": attempt.nonce, **claims})))

    with pytest.raises(chatgpt.PlanError) as failed:
        chatgpt.finish(tmp_home, attempt, {"code": "c", "state": attempt.state, "client_id": "oaiapp_1"}, keys=_jwks())

    assert failed.value.code == "id_token_invalid" and not chatgpt.signed_in(tmp_home)
    assert chatgpt.load(tmp_home) == {"issuer": chatgpt.ISSUER, "client_id": "oaiapp_1"}
    assert _query(chatgpt.begin(tmp_home, 1455).url)["client_id"] == "oaiapp_1"


def test_an_id_token_signed_by_someone_else_is_refused(tmp_home: Path) -> None:
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token = _id_token(nonce="n")
    signed = token.rsplit(".", 1)[0]
    forged = f"{signed}.{_b64(other.sign(signed.encode(), padding.PKCS1v15(), hashes.SHA256()))}"

    assert chatgpt.verify_id_token(token, client_id="oaiapp_1", nonce="n", keys=_jwks())["sub"] == "user-1"
    with pytest.raises(chatgpt.PlanError):
        chatgpt.verify_id_token(forged, client_id="oaiapp_1", nonce="n", keys=_jwks())
    with pytest.raises(chatgpt.PlanError):
        chatgpt.verify_id_token(token, client_id="oaiapp_1", nonce="n", keys=[{**_jwks()[0], "kid": "k2"}])


def test_a_returning_sign_in_cannot_swap_the_account_or_the_registration(tmp_home: Path, web) -> None:
    _, answers = web
    _sign_in(tmp_home, web)
    attempt = chatgpt.begin(tmp_home, 1455)

    with pytest.raises(chatgpt.PlanError) as other_client:
        chatgpt.finish(tmp_home, attempt, {"code": "c", "state": attempt.state, "client_id": "oaiapp_2"}, keys=_jwks())
    answers[chatgpt.TOKEN_URL] = (200, _tokens(attempt.nonce, id_token=_id_token(nonce=attempt.nonce, sub="user-2"), refresh_token="rt-other"))
    with pytest.raises(chatgpt.PlanError) as other_account:
        chatgpt.finish(tmp_home, attempt, {"code": "c", "state": attempt.state}, keys=_jwks())

    assert (other_client.value.code, other_account.value.code) == ("client_mismatch", "account_mismatch")
    assert chatgpt.load(tmp_home)["refresh_token"] == "rt-1"


def test_a_sign_in_without_plan_permission_is_kept_but_not_used(tmp_home: Path, web) -> None:
    _sign_in(tmp_home, web, scope="email openid profile")

    assert not chatgpt.signed_in(tmp_home) and chatgpt.models(tmp_home) == []
    with pytest.raises(chatgpt.NotSignedIn):
        chatgpt.access_token(tmp_home)


def test_a_token_near_expiry_is_refreshed_once_and_the_replacement_saved(tmp_home: Path, web) -> None:
    calls, answers = web
    _sign_in(tmp_home, web)
    assert chatgpt.access_token(tmp_home) == "at-1"
    record = chatgpt.load(tmp_home)
    chatgpt._save(tmp_home, {**record, "saved_at": time.time() - 3500})
    calls.clear()
    answers[chatgpt.TOKEN_URL] = (200, {"access_token": "at-2", "refresh_token": "rt-2", "expires_in": 3600, "scope": " ".join(record["scopes"])})

    assert chatgpt.access_token(tmp_home) == "at-2" and chatgpt.access_token(tmp_home) == "at-2"

    refreshes = [c[2] for c in calls if c[1] == chatgpt.TOKEN_URL]
    assert len(refreshes) == 1
    assert {k: v for k, v in refreshes[0].items() if k != "_auth"} == {
        "grant_type": "refresh_token", "client_id": "oaiapp_1", "refresh_token": "rt-1", "resource": "https://api.openai.com/v1",
    }
    saved = chatgpt.load(tmp_home)
    assert (saved["refresh_token"], saved["id_token"] == record["id_token"], saved["client_id"]) == ("rt-2", True, "oaiapp_1")


def test_a_dead_refresh_token_ends_the_session_and_a_server_error_does_not(tmp_home: Path, web) -> None:
    _, answers = web
    _sign_in(tmp_home, web)
    chatgpt._save(tmp_home, {**chatgpt.load(tmp_home), "saved_at": 0})

    answers[chatgpt.TOKEN_URL] = (503, {"error": "temporarily_unavailable"})
    with pytest.raises(chatgpt.PlanError) as outage:
        chatgpt.access_token(tmp_home)
    assert outage.value.retryable and chatgpt.load(tmp_home)["refresh_token"] == "rt-1"

    answers[chatgpt.TOKEN_URL] = (400, {"error": "invalid_grant"})
    with pytest.raises(chatgpt.NotSignedIn):
        chatgpt.access_token(tmp_home)
    saved = chatgpt.load(tmp_home)
    assert "refresh_token" not in saved and "access_token" not in saved and saved["client_id"] == "oaiapp_1"


def test_signing_out_revokes_the_session_and_keeps_the_registration(tmp_home: Path, web) -> None:
    calls, answers = web
    _sign_in(tmp_home, web)
    answers[chatgpt.DISCOVERY_URL] = (200, {"revocation_endpoint": "https://auth.openai.com/oauth/revoke"})
    answers["https://auth.openai.com/oauth/revoke"] = (200, {})

    assert chatgpt.logout(tmp_home) is True

    revoke = next(c for c in calls if c[1].endswith("/oauth/revoke"))[2]
    assert (revoke["token"], revoke["token_type_hint"], revoke["client_id"]) == ("rt-1", "refresh_token", "oaiapp_1")
    saved = chatgpt.load(tmp_home)
    assert saved["client_id"] == "oaiapp_1" and saved["email"] == "a@example.com"
    assert not {"access_token", "refresh_token", "id_token"} & set(saved) and not chatgpt.signed_in(tmp_home)
    assert "id_token_hint" not in _query(chatgpt.begin(tmp_home, 1455).url)


def test_a_sign_out_openai_does_not_confirm_still_deletes_the_tokens(tmp_home: Path, web) -> None:
    _sign_in(tmp_home, web)

    assert chatgpt.logout(tmp_home, forget=True) is False
    assert not chatgpt.record_path(tmp_home).exists()


def test_the_agent_cannot_read_the_credential_with_its_file_tools(tmp_home: Path, web) -> None:
    from alpi.tools._paths import _always_private_area

    _sign_in(tmp_home, web)
    path = chatgpt.record_path(tmp_home)

    assert _always_private_area(path, path.resolve(), for_write=False) == "secrets"


_TOOLS = [{"type": "function", "function": {"name": "read_file", "description": "d", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}}}}]
_HISTORY = [
    {"role": "system", "content": "You are alpi."},
    {"role": "user", "content": [{"type": "text", "text": "look"}, {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}}]},
    {"role": "assistant", "content": "", "tool_calls": [{"id": "call_1", "type": "function", "function": {"name": "read_file", "arguments": "{\"path\": \"a\"}"}}]},
    {"role": "tool", "tool_call_id": "call_1", "content": "body"},
    {"role": "system", "content": "[note] be brief"},
    {"role": "assistant", "content": "Done."},
]


def test_the_request_is_the_one_the_plan_route_accepts() -> None:
    body = chatgpt_responses.request_body({
        "model": "chatgpt-plan/gpt-6.2-sol", "messages": _HISTORY, "tools": _TOOLS, "tool_choice": "required",
        "parallel_tool_calls": False, "reasoning_effort": "high", "max_tokens": 900, "temperature": 0.2,
        "timeout": 30, "chatgpt_home": "/x", "stream_options": {"include_usage": True}, "metadata": {"a": "b"},
    })

    assert body == {
        "model": "gpt-6.2-sol", "store": False, "stream": True, "instructions": "You are alpi.",
        "input": [
            {"role": "user", "content": [{"type": "input_text", "text": "look"}, {"type": "input_image", "image_url": "data:image/png;base64,AAAA"}]},
            {"type": "function_call", "call_id": "call_1", "namespace": "alpi", "name": "read_file", "arguments": "{\"path\": \"a\"}"},
            {"type": "function_call_output", "call_id": "call_1", "output": "body"},
            {"role": "developer", "content": "[note] be brief"},
            {"role": "assistant", "content": "Done."},
        ],
        "tools": [{"type": "namespace", "name": "alpi", "description": "The tools alpi gives this agent.", "tools": [
            {"type": "function", "strict": False, "name": "read_file", "description": "d", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}}},
        ]}],
        "tool_choice": "required", "parallel_tool_calls": False, "reasoning": {"summary": "auto", "effort": "high"},
    }


def _sse(*events: dict[str, Any]) -> bytes:
    return "".join(f"event: {e['type']}\ndata: {json.dumps(e)}\n\n" for e in events).encode()


_USAGE = {"input_tokens": 120, "output_tokens": 30, "input_tokens_details": {"cached_tokens": 100}}
_REPLY = _sse(
    {"type": "response.created", "response": {"id": "resp_1"}},
    {"type": "response.reasoning_summary_text.delta", "delta": "thinking"},
    {"type": "response.output_text.delta", "delta": "Hel"},
    {"type": "response.output_text.delta", "delta": "lo"},
    {"type": "response.output_item.added", "output_index": 1, "item": {"type": "function_call", "call_id": "call_a", "name": "read_file", "namespace": "alpi", "arguments": ""}},
    {"type": "response.function_call_arguments.delta", "output_index": 1, "delta": "{\"path\":"},
    {"type": "response.function_call_arguments.delta", "output_index": 1, "delta": " \"a\"}"},
    {"type": "response.output_item.added", "output_index": 2, "item": {"type": "function_call", "call_id": "call_b", "name": "read_file", "arguments": "{}"}},
    {"type": "response.completed", "response": {"id": "resp_1", "usage": _USAGE}},
)


class _Runtime:
    first_byte_timeout_s = 5
    stream_idle_timeout_s = 5
    stream_max_duration_s = 10
    max_retries = 1
    retry_backoff_s = 0.01


def _plan_kwargs(tmp_home: Path) -> dict[str, Any]:
    cfg_mod.seed_defaults(tmp_home)
    cfg = cfg_mod.load(tmp_home)
    cfg.model = "chatgpt-plan/gpt-6.2-sol"
    cfg.model_reasoning.effort = "high"
    return cfg_mod.resolve_model(cfg)


def test_a_plan_turn_streams_text_reasoning_calls_and_usage_with_the_saved_token(tmp_home: Path, web) -> None:
    calls, answers = web
    _sign_in(tmp_home, web)
    answers[chatgpt.RESPONSES_URL] = (200, _REPLY)
    kwargs = _plan_kwargs(tmp_home)
    assert kwargs == {"model": "chatgpt-plan/gpt-6.2-sol", "chatgpt_home": str(tmp_home), "reasoning_effort": "high"}

    out = list(llm.stream(messages=_HISTORY, tools=_TOOLS, rt=_Runtime, **kwargs))

    sent = next(c for c in calls if c[1] == chatgpt.RESPONSES_URL)[2]
    assert sent["_auth"] == "Bearer at-1" and sent["store"] is False and sent["stream"] is True and sent["model"] == "gpt-6.2-sol"
    assert "".join(c.get("text_delta", "") for c in out[:-1]) == "Hello"
    assert "".join(c.get("reasoning_delta", "") for c in out[:-1]) == "thinking"
    final = out[-1]
    assert final["tool_calls"] == [
        {"id": "call_a", "name": "read_file", "arguments": "{\"path\": \"a\"}"}, {"id": "call_b", "name": "read_file", "arguments": "{}"},
    ]
    assert (final["input_tokens"], final["output_tokens"], final["cached_tokens"]) == (120, 30, 100)
    assert (final["cost_usd"], final["cost_source"], final["finish_reason"], final["provider"]) == (0.0, "plan", "tool_calls", "chatgpt-plan")


def test_a_background_call_on_the_plan_returns_the_whole_reply(tmp_home: Path, web) -> None:
    _, answers = web
    _sign_in(tmp_home, web)
    answers[chatgpt.RESPONSES_URL] = (200, _REPLY)

    out = llm.complete(messages=_HISTORY, tools=_TOOLS, max_tokens=500, **_plan_kwargs(tmp_home))

    assert out.content == "Hello" and [c["id"] for c in out.tool_calls] == ["call_a", "call_b"]
    assert (out.input_tokens, out.output_tokens, out.cached_tokens, out.cost_usd, out.cost_source) == (120, 30, 100, 0.0, "plan")
    assert "max_output_tokens" not in web[0][-1][2] and "max_tokens" not in web[0][-1][2]


def test_a_reached_plan_limit_is_not_retried_and_points_at_chatgpt_usage(tmp_home: Path, web) -> None:
    calls, answers = web
    _sign_in(tmp_home, web)
    answers[chatgpt.RESPONSES_URL] = (429, {"error": {"code": "subscription_sharing_usage_limit_exceeded", "message": "limit"}})

    with pytest.raises(chatgpt.PlanError) as failed:
        list(llm.stream(messages=_HISTORY, tools=_TOOLS, rt=_Runtime, **_plan_kwargs(tmp_home)))

    assert len([c for c in calls if c[1] == chatgpt.RESPONSES_URL]) == 1
    explained = llm_errors.explain(failed.value)
    assert explained.code == "insufficient_credit" and "https://chatgpt.com/settings/usage" in explained.message


def test_a_limit_that_arrives_mid_stream_fails_the_same_way(tmp_home: Path, web) -> None:
    _, answers = web
    _sign_in(tmp_home, web)
    answers[chatgpt.RESPONSES_URL] = (200, _sse(
        {"type": "response.output_text.delta", "delta": "Hel"},
        {"type": "response.failed", "response": {"error": {"code": "subscription_sharing_usage_limit_exceeded", "message": "limit"}}},
    ))

    with pytest.raises(chatgpt.PlanError) as failed:
        list(llm.stream(messages=_HISTORY, tools=_TOOLS, rt=_Runtime, **_plan_kwargs(tmp_home)))

    assert llm_errors.classify(failed.value) == "insufficient_credit"


def test_a_stream_cut_before_completion_is_retried_and_a_refused_sign_in_is_not(tmp_home: Path, web) -> None:
    calls, answers = web
    _sign_in(tmp_home, web)
    replies = iter([(200, _sse({"type": "response.output_item.added", "output_index": 0, "item": {"type": "function_call", "call_id": "x", "name": "read_file"}})), (200, _REPLY)])
    answers[chatgpt.RESPONSES_URL] = lambda sent: next(replies)

    out = list(llm.stream(messages=_HISTORY, tools=_TOOLS, rt=_Runtime, **_plan_kwargs(tmp_home)))

    assert [c["id"] for c in out[-1]["tool_calls"]] == ["call_a", "call_b"] and {"retry_reset": True} in out
    calls.clear()
    answers[chatgpt.TOKEN_URL] = (200, {"access_token": "at-2", "refresh_token": "rt-2", "expires_in": 3600})
    answers[chatgpt.RESPONSES_URL] = (401, {"error": {"code": "invalid_token", "message": "signed identity not accepted"}})
    with pytest.raises(chatgpt.PlanError) as failed:
        list(llm.stream(messages=_HISTORY, tools=_TOOLS, rt=_Runtime, **_plan_kwargs(tmp_home)))
    assert [(c[1], c[2]["_auth"]) for c in calls] == [
        (chatgpt.RESPONSES_URL, "Bearer at-1"), (chatgpt.TOKEN_URL, ""), (chatgpt.RESPONSES_URL, "Bearer at-2"),
    ]
    explained = llm_errors.explain(failed.value)
    assert explained.code == "auth" and "alpi chatgpt login" in explained.message


def test_a_profile_that_never_signed_in_is_told_how(tmp_home: Path, web) -> None:
    with pytest.raises(chatgpt.NotSignedIn) as failed:
        list(llm.stream(messages=_HISTORY, tools=_TOOLS, rt=_Runtime, **_plan_kwargs(tmp_home)))

    explained = llm_errors.explain(failed.value)
    assert explained.code == "auth" and "alpi chatgpt login" in explained.message and web[0] == []


def test_plan_models_answer_capability_questions_as_their_openai_ids_without_litellm_login(tmp_home: Path, monkeypatch) -> None:
    import socket

    from alpi import attachments, ctx_window, prompt_cache
    from alpi.providers import reasoning

    attempts: list[Any] = []
    monkeypatch.setattr(socket.socket, "connect", lambda self, address, *a: attempts.append(address) or (_ for _ in ()).throw(PermissionError()))
    model = "chatgpt-plan/gpt-6.2-sol"
    cfg_mod.seed_defaults(tmp_home)
    cfg = cfg_mod.load(tmp_home)

    assert attachments.vision_status(model) == "yes" and attachments.model_context_tokens(model) == 922000
    assert ctx_window.resolve(tmp_home, cfg, model) == 922000
    assert reasoning.supports_reasoning(model) and not reasoning.supports_reasoning("chatgpt-plan/gpt-4o")
    assert prompt_cache.cache_kwargs_for_model(model) == {}
    assert llm._provider_bound({"model": model, "messages": _HISTORY})["messages"] is _HISTORY
    assert attempts == []


def test_a_home_without_a_secrets_folder_gets_one_only_its_owner_can_enter(tmp_path: Path, web, monkeypatch) -> None:
    from alpi import audit

    home = tmp_path / "fresh"
    home.mkdir()
    monkeypatch.setenv("ALPI_HOME", str(home))

    _sign_in(home, web)

    for path in (home / "secrets", home / "secrets" / "chatgpt.json", home / "secrets" / "chatgpt-host"):
        assert path.stat().st_mode & 0o077 == 0, path
    assert not [c for c in audit._audit_permissions(home) if c.name == "secrets/"]


def test_a_token_refused_before_its_expiry_is_renewed_once_and_the_turn_goes_on(tmp_home: Path, web) -> None:
    calls, answers = web
    _sign_in(tmp_home, web)
    answers[chatgpt.TOKEN_URL] = (200, {"access_token": "at-2", "refresh_token": "rt-2", "expires_in": 3600})
    answers[chatgpt.RESPONSES_URL] = lambda sent: (200, _REPLY) if sent["_auth"] == "Bearer at-2" else (401, {"detail": "expired"})

    out = list(llm.stream(messages=_HISTORY, tools=_TOOLS, rt=_Runtime, **_plan_kwargs(tmp_home)))

    assert "".join(c.get("text_delta", "") for c in out[:-1]) == "Hello" and chatgpt.load(tmp_home)["refresh_token"] == "rt-2"


@pytest.mark.parametrize("failure", [httpx.ReadTimeout("slow"), httpx.ConnectError("down"), httpx.RemoteProtocolError("cut")])
def test_a_dropped_connection_is_retried_like_on_any_other_provider(tmp_home: Path, web, monkeypatch, failure) -> None:
    _, answers = web
    _sign_in(tmp_home, web)
    fake_send = httpx.Client.send
    state = {"failed": False}

    def flaky(self, request, **kw):
        if str(request.url) == chatgpt.RESPONSES_URL and not state["failed"]:
            state["failed"] = True
            raise failure
        return fake_send(self, request, **kw)

    monkeypatch.setattr(httpx.Client, "send", flaky)
    answers[chatgpt.RESPONSES_URL] = (200, _REPLY)

    out = list(llm.stream(messages=_HISTORY, tools=_TOOLS, rt=_Runtime, **_plan_kwargs(tmp_home)))

    assert {"retry_reset": True} in out and out[-1]["finish_reason"] == "tool_calls"


@pytest.mark.parametrize(("status", "body", "retried"), [
    (500, {"error": {"code": "server_error", "message": "boom"}}, True),
    (503, {"detail": "direct routing unavailable"}, True),
    (429, {"error": {"code": "rate_limit_exceeded", "message": "slow down"}}, True),
    (503, {"error": {"code": "subscription_sharing_usage_unavailable", "message": "later"}}, True),
    (403, {"error": {"code": "subscription_sharing_user_not_eligible", "message": "no"}}, False),
    (400, {"error": {"code": "subscription_sharing_unsupported_capability", "message": "no", "param": "tools"}}, False),
])
def test_which_plan_failures_are_worth_asking_again(tmp_home: Path, web, status, body, retried) -> None:
    calls, answers = web
    _sign_in(tmp_home, web)
    answers[chatgpt.RESPONSES_URL] = (status, body)
    calls.clear()

    with pytest.raises(chatgpt.PlanError) as failed:
        list(llm.stream(messages=_HISTORY, tools=_TOOLS, rt=_Runtime, **_plan_kwargs(tmp_home)))

    assert len(calls) == (2 if retried else 1) and llm.is_transient(failed.value) is retried
    if body.get("error", {}).get("param"):
        assert "param: tools" in str(failed.value)


def test_a_server_error_mid_stream_is_retried(tmp_home: Path, web) -> None:
    _, answers = web
    _sign_in(tmp_home, web)
    replies = iter([(200, _sse({"type": "response.failed", "response": {"error": {"code": "server_error", "message": "boom"}}})), (200, _REPLY)])
    answers[chatgpt.RESPONSES_URL] = lambda sent: next(replies)

    assert list(llm.stream(messages=_HISTORY, tools=_TOOLS, rt=_Runtime, **_plan_kwargs(tmp_home)))[-1]["finish_reason"] == "tool_calls"


def test_the_sign_in_is_kept_when_the_model_list_cannot_be_read(tmp_home: Path, web) -> None:
    calls, answers = web
    attempt = chatgpt.begin(tmp_home, 1455)
    answers[chatgpt.TOKEN_URL] = (200, _tokens(attempt.nonce))
    answers[chatgpt.MODELS_URL] = (200, b"<html>not json</html>")

    record = chatgpt.finish(tmp_home, attempt, {"code": "c", "state": attempt.state, "client_id": "oaiapp_1"}, keys=_jwks())

    assert chatgpt.signed_in(tmp_home) and record["first_sign_in"] and chatgpt.models(tmp_home) == []
    answers[chatgpt.MODELS_URL] = (200, {"models": [{"slug": "gpt-6-luna", "display_name": "GPT-6 Luna", "visibility": "list"}]})
    assert chatgpt.refresh_models(tmp_home) == [{"slug": "gpt-6-luna", "display_name": "GPT-6 Luna"}]
    assert chatgpt.models(tmp_home)[0]["slug"] == "gpt-6-luna"


def test_a_failed_exchange_is_a_plan_error_and_keeps_the_issued_client(tmp_home: Path, web, monkeypatch) -> None:
    attempt = chatgpt.begin(tmp_home, 1455)
    monkeypatch.setattr(httpx.Client, "send", lambda self, request, **kw: (_ for _ in ()).throw(httpx.ConnectError("down")))

    with pytest.raises(chatgpt.PlanError) as failed:
        chatgpt.finish(tmp_home, attempt, {"code": "c", "state": attempt.state, "client_id": "oaiapp_1"}, keys=_jwks())

    assert failed.value.code == "unreachable" and failed.value.retryable
    again = _query(chatgpt.begin(tmp_home, 1455).url)
    assert again["client_id"] == "oaiapp_1" and "agent_name_hint" not in again and "prompt" not in again


def test_only_the_browser_that_carries_this_attempt_ends_the_wait() -> None:
    assert chatgpt.callback_answer("/favicon.ico", "S")[:2] == (404, None)
    assert chatgpt.callback_answer("/auth/callback?code=x&state=other", "S")[:2] == (400, None)
    assert chatgpt.callback_answer("/auth/callback", "S")[:2] == (400, None)
    assert chatgpt.callback_answer("/auth/callback?code=x&state=S&client_id=c", "S")[:2] == (200, {"code": "x", "state": "S", "client_id": "c"})
    status, query, text = chatgpt.callback_answer("/auth/callback?error=access_denied&state=S", "S")
    assert (status, query["error"]) == (200, "access_denied") and "not completed" in text


@pytest.mark.integration
def test_the_local_listener_ignores_strangers_and_survives_a_silent_connection(tmp_home: Path, web, monkeypatch) -> None:
    import socket
    import threading
    import urllib.request

    _, answers = web
    answers[chatgpt.MODELS_URL] = (200, {"models": []})
    shown: list[str] = []
    monkeypatch.setattr(chatgpt, "CALLBACK_PORT", 0)
    monkeypatch.setattr(chatgpt, "verify_id_token", lambda token, **kw: {"sub": "user-1", "email": "a@example.com"})
    monkeypatch.setattr(chatgpt._Callback, "timeout", 0.3)

    def browser() -> None:
        while not shown:
            time.sleep(0.01)
        sent = _query(shown[0])
        base = sent["redirect_uri"]
        answers[chatgpt.TOKEN_URL] = (200, _tokens(sent["nonce"]))
        port = int(urllib.parse.urlsplit(base).port)
        silent = socket.create_connection(("127.0.0.1", port))
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            opener.open(f"{base}?code=evil&state=forged", timeout=5)
        except Exception:  # noqa: BLE001
            pass
        opener.open(f"{base}?code=c&state={sent['state']}&client_id=oaiapp_1", timeout=5)
        silent.close()

    real_send = httpx.Client.send
    thread = threading.Thread(target=browser)
    thread.start()
    record = chatgpt.login(tmp_home, show=shown.append, open_browser=False, timeout=20)
    thread.join()

    assert record["client_id"] == "oaiapp_1" and chatgpt.signed_in(tmp_home)
    assert "id_token_hint" not in shown[0] and real_send is httpx.Client.send


def test_plan_use_declined_earlier_asks_for_consent_and_is_not_welcomed_until_granted(tmp_home: Path, web) -> None:
    declined = _sign_in(tmp_home, web, scope="email openid profile")
    assert declined["first_sign_in"] is False

    again = chatgpt.begin(tmp_home, 1455)

    assert _query(again.url)["prompt"] == "consent"
    web[1][chatgpt.TOKEN_URL] = (200, _tokens(again.nonce))
    granted = chatgpt.finish(tmp_home, again, {"code": "c", "state": again.state}, keys=_jwks())
    assert granted["first_sign_in"] is True and "prompt" not in _query(chatgpt.begin(tmp_home, 1455).url)


def test_the_address_shown_to_the_person_carries_no_id_token(tmp_home: Path, web) -> None:
    _sign_in(tmp_home, web)

    attempt = chatgpt.begin(tmp_home, 1455)

    assert "id_token_hint" in _query(attempt.url) and "id_token_hint" not in _query(attempt.shown_url)
    assert _query(attempt.shown_url)["state"] == attempt.state


def test_an_elliptic_curve_signature_and_a_list_audience_verify(tmp_home: Path) -> None:
    from cryptography.hazmat.primitives.asymmetric import ec, utils

    key = ec.generate_private_key(ec.SECP256R1())
    numbers = key.public_key().public_numbers()
    jwk = {"kty": "EC", "crv": "P-256", "kid": "e1", "x": _b64(numbers.x.to_bytes(32, "big")), "y": _b64(numbers.y.to_bytes(32, "big"))}
    body = {"iss": chatgpt.ISSUER, "aud": ["other", "oaiapp_1"], "sub": "u", "nonce": "n", "exp": time.time() - 30}
    signed = f"{_b64(json.dumps({'alg': 'ES256', 'kid': 'e1'}).encode())}.{_b64(json.dumps(body).encode())}"
    r, s = utils.decode_dss_signature(key.sign(signed.encode(), ec.ECDSA(hashes.SHA256())))
    token = f"{signed}.{_b64(r.to_bytes(32, 'big') + s.to_bytes(32, 'big'))}"

    assert chatgpt.verify_id_token(token, client_id="oaiapp_1", nonce="n", keys=[jwk])["sub"] == "u"
    for bad in (f"{_b64(b'[1]')}.{_b64(b'{}')}.{_b64(b'x')}", "a.b", token.replace("ES256"[:0], "", 1)[:-4] + "AAAA"):
        with pytest.raises(chatgpt.PlanError):
            chatgpt.verify_id_token(bad, client_id="oaiapp_1", nonce="n", keys=[jwk])
    with pytest.raises(chatgpt.PlanError):
        chatgpt.verify_id_token(token, client_id="oaiapp_1", nonce="n", keys=[{**jwk, "kty": "RSA", "n": "AQAB", "e": "AQAB"}])


def test_two_callers_at_expiry_spend_the_refresh_token_once(tmp_home: Path, web) -> None:
    import threading

    calls, answers = web
    _sign_in(tmp_home, web)
    chatgpt._save(tmp_home, {**chatgpt.load(tmp_home), "saved_at": 0})
    calls.clear()

    def slow(sent):
        time.sleep(0.2)
        return 200, {"access_token": "at-2", "refresh_token": "rt-2", "expires_in": 3600}

    answers[chatgpt.TOKEN_URL] = slow
    got: list[str] = []
    threads = [threading.Thread(target=lambda: got.append(chatgpt.access_token(tmp_home))) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert got == ["at-2"] * 4 and len([c for c in calls if c[1] == chatgpt.TOKEN_URL]) == 1


def test_text_arguments_and_refusals_that_arrive_only_whole_are_not_lost(tmp_home: Path, web) -> None:
    _, answers = web
    _sign_in(tmp_home, web)
    reply = _sse(
        {"type": "response.output_text.done", "output_index": 0, "text": "Whole text. "},
        {"type": "response.refusal.delta", "output_index": 1, "delta": "I cannot."},
        {"type": "response.output_item.added", "output_index": 2, "item": {"type": "function_call", "call_id": "c1", "name": "read_file"}},
        {"type": "response.function_call_arguments.done", "output_index": 2, "arguments": "{\"path\": \"a\"}"},
        {"type": "response.output_item.done", "output_index": 2, "item": {"type": "function_call", "call_id": "c1", "name": "read_file", "arguments": "{\"path\": \"a\"}"}},
        {"type": "response.output_item.done", "output_index": 3, "item": {"type": "function_call", "call_id": "c2", "name": "read_file", "arguments": "{}"}},
    )
    answers[chatgpt.RESPONSES_URL] = (200, reply + b'data: {"type": "response.completed", "response": {"id": "r", "usage": {}}}')

    out = list(llm.stream(messages=_HISTORY, tools=_TOOLS, rt=_Runtime, **_plan_kwargs(tmp_home)))

    assert "".join(c.get("text_delta", "") for c in out[:-1]) == "Whole text. I cannot."
    assert out[-1]["tool_calls"] == [
        {"id": "c1", "name": "read_file", "arguments": "{\"path\": \"a\"}"}, {"id": "c2", "name": "read_file", "arguments": "{}"},
    ]


@pytest.mark.parametrize(("details", "finish"), [({"reason": "max_output_tokens"}, "length"), ({"reason": "content_filter"}, "content_filter"), (None, "length")])
def test_an_incomplete_response_says_why(tmp_home: Path, web, details, finish) -> None:
    _, answers = web
    _sign_in(tmp_home, web)
    answers[chatgpt.RESPONSES_URL] = (200, _sse(
        {"type": "response.output_text.delta", "delta": "par"},
        {"type": "response.incomplete", "response": {"id": "r", "usage": _USAGE, "incomplete_details": details}},
    ))

    assert list(llm.stream(messages=_HISTORY, tools=_TOOLS, rt=_Runtime, **_plan_kwargs(tmp_home)))[-1]["finish_reason"] == finish


def test_a_later_system_message_never_rewrites_the_instructions() -> None:
    body = chatgpt_responses.request_body({"model": "chatgpt-plan/m", "messages": [
        {"role": "system", "content": "PROMPT"}, {"role": "system", "content": "[summary] earlier turns"}, {"role": "user", "content": "hi"},
    ]})

    assert body["instructions"] == "PROMPT"
    assert body["input"] == [{"role": "developer", "content": "[summary] earlier turns"}, {"role": "user", "content": "hi"}]
    assert "tools" not in body and "tool_choice" not in body


def test_a_call_without_a_profile_home_never_looks_for_a_credential_in_the_working_directory(tmp_path: Path, monkeypatch, web) -> None:
    (tmp_path / "secrets").mkdir()
    (tmp_path / "secrets" / "chatgpt.json").write_text(json.dumps({"access_token": "cwd", "refresh_token": "r", "saved_at": time.time(), "expires_in": 3600, "scopes": [chatgpt.PLAN_SCOPE]}))
    monkeypatch.chdir(tmp_path)

    with pytest.raises(chatgpt.NotSignedIn):
        list(chatgpt_responses.stream({"model": "chatgpt-plan/m", "messages": []}))
    assert web[0] == []


def test_text_reaches_the_caller_while_the_reply_is_still_arriving() -> None:
    served: list[str] = []

    class _Slow:
        def iter_lines(self):
            for event in (
                {"type": "response.output_text.delta", "delta": "first"},
                {"type": "response.output_text.delta", "delta": "second"},
                {"type": "response.completed", "response": {"id": "r", "usage": {}}},
            ):
                for line in (f"data: {json.dumps(event)}", ""):
                    served.append(line)
                    yield line

    chunks = chatgpt_responses._converted(_Slow())

    assert next(chunks).choices[0].delta.content == "first"
    assert len(served) == 2
    assert [c.choices[0].delta.content for c in chunks][0] == "second"


def test_a_stale_first_registration_cannot_replace_the_one_that_finished(tmp_home: Path, web) -> None:
    _, answers = web
    stale = chatgpt.begin(tmp_home, 1455)
    _sign_in(tmp_home, web)

    with pytest.raises(chatgpt.PlanError) as failed:
        chatgpt.finish(tmp_home, stale, {"code": "c", "state": stale.state, "client_id": "oaiapp_other"}, keys=_jwks())

    saved = chatgpt.load(tmp_home)
    assert failed.value.code == "superseded" and (saved["client_id"], saved["refresh_token"]) == ("oaiapp_1", "rt-1")


@pytest.mark.parametrize("body", [{"refresh_token": "r"}, ["not", "an", "object"], {"access_token": ""}, b"<html>"])
def test_a_token_answer_without_an_access_token_is_a_plan_error(tmp_home: Path, web, body) -> None:
    _, answers = web
    attempt = chatgpt.begin(tmp_home, 1455)
    answers[chatgpt.TOKEN_URL] = (200, body)

    with pytest.raises(chatgpt.PlanError) as failed:
        chatgpt.finish(tmp_home, attempt, {"code": "c", "state": attempt.state, "client_id": "oaiapp_1"}, keys=_jwks())

    assert failed.value.code == "bad_token_response" and not chatgpt.signed_in(tmp_home)


def test_an_odd_expiry_in_the_token_answer_does_not_break_the_sign_in(tmp_home: Path, web) -> None:
    _sign_in(tmp_home, web, expires_in="soon")

    assert chatgpt.load(tmp_home)["expires_in"] == 3600 and chatgpt.access_token(tmp_home) == "at-1"


def test_a_state_that_is_not_ascii_is_just_another_wrong_state(tmp_home: Path) -> None:
    assert chatgpt.callback_answer("/auth/callback?state=%C3%A9&code=x", "S")[:2] == (400, None)
    attempt = chatgpt.begin(tmp_home, 1455)
    with pytest.raises(chatgpt.PlanError) as failed:
        chatgpt.finish(tmp_home, attempt, {"code": "c", "state": "é"}, keys=_jwks())
    assert failed.value.code == "state_mismatch"


@pytest.mark.parametrize(("error", "expected"), [
    (chatgpt.PlanError("cut", code="stream_interrupted", retryable=True), "provider_unavailable"),
    (chatgpt_responses._plan_error("server_error", "boom", None), "provider_unavailable"),
    (chatgpt_responses._plan_error("rate_limit_exceeded", "slow", None), "rate_limited"),
    (chatgpt_responses._plan_error("subscription_sharing_usage_unavailable", "later", 503), "provider_unavailable"),
    (chatgpt_responses._plan_error("subscription_sharing_user_not_eligible", "no", 403), "forbidden"),
])
def test_a_plan_failure_after_the_stream_opened_still_gets_its_class(error, expected) -> None:
    assert llm_errors.classify(error) == expected


def test_a_timeout_on_the_plan_route_is_still_a_timeout() -> None:
    try:
        try:
            raise httpx.ReadTimeout("slow")
        except httpx.HTTPError as exc:
            raise chatgpt.unreachable(exc, "for this request") from exc
    except chatgpt.PlanError as wrapped:
        assert llm_errors.classify(wrapped) == "timeout" and llm.is_transient(wrapped)


def test_calls_and_text_parts_without_an_output_index_stay_apart(tmp_home: Path, web) -> None:
    _, answers = web
    _sign_in(tmp_home, web)
    answers[chatgpt.RESPONSES_URL] = (200, _sse(
        {"type": "response.output_text.delta", "output_index": 0, "content_index": 0, "delta": "A"},
        {"type": "response.output_text.done", "output_index": 0, "content_index": 1, "text": "B"},
        {"type": "response.output_item.done", "item": {"type": "function_call", "id": "fc_1", "call_id": "c1", "name": "read_file", "arguments": "{}"}},
        {"type": "response.output_item.done", "item": {"type": "function_call", "id": "fc_2", "call_id": "c2", "name": "read_file", "arguments": "{}"}},
        {"type": "response.completed", "response": {"id": "r", "usage": {}}},
    ))

    out = list(llm.stream(messages=_HISTORY, tools=_TOOLS, rt=_Runtime, **_plan_kwargs(tmp_home)))

    assert "".join(c.get("text_delta", "") for c in out[:-1]) == "AB" and [c["id"] for c in out[-1]["tool_calls"]] == ["c1", "c2"]


def test_a_reasoning_model_is_asked_for_its_summary_with_or_without_an_effort() -> None:
    ask = lambda model, **kw: chatgpt_responses.request_body({"model": model, "messages": [{"role": "user", "content": "hi"}], **kw})

    assert ask("chatgpt-plan/gpt-6-luna")["reasoning"] == {"summary": "auto"}
    assert ask("chatgpt-plan/gpt-6.2-sol", reasoning_effort="low")["reasoning"] == {"summary": "auto", "effort": "low"}
    assert "reasoning" not in ask("chatgpt-plan/gpt-4o")


def _cli(tmp_home: Path, monkeypatch, *args: str, input: str | None = None):
    from click.testing import CliRunner

    from alpi import cli

    monkeypatch.setenv("ALPI_SKIP_UPDATE_CHECK", "1")
    return CliRunner().invoke(cli.main, ["chatgpt", *args], input=input)


def test_the_console_finishes_a_sign_in_from_a_pasted_address_and_gives_the_profile_a_model(tmp_home: Path, web, monkeypatch) -> None:
    _, answers = web
    cfg_mod.save(cfg_mod.Config(home=tmp_home, model=""))
    begun: list[chatgpt.Attempt] = []
    real_begin = chatgpt.begin
    monkeypatch.setattr(chatgpt, "begin", lambda home, port: begun.append(real_begin(home, port)) or begun[-1])
    monkeypatch.setattr(chatgpt, "verify_id_token", lambda token, **kw: {"sub": "user-1", "email": "a@example.com"})
    answers[chatgpt.TOKEN_URL] = (200, {"access_token": "at-1", "refresh_token": "rt-1", "id_token": "h.b.s", "expires_in": 3600, "scope": f"openid {chatgpt.PLAN_SCOPE}"})
    answers[chatgpt.MODELS_URL] = (200, {"models": [{"slug": "gpt-6.2-sol", "display_name": "GPT-6.2 Sol", "visibility": "list"}]})

    import click

    monkeypatch.setattr(click, "prompt", lambda *a, **k: f"http://127.0.0.1:1455/auth/callback?code=c&state={begun[-1].state}&client_id=oaiapp_1")
    done = _cli(tmp_home, monkeypatch, "login", "--paste")

    assert done.exit_code == 0, done.output
    assert "https://auth.openai.com/api/accounts/authorize?" in done.output and "id_token_hint" not in done.output
    assert "model set to chatgpt-plan/gpt-6.2-sol" in done.output and "Using ChatGPT plan · a@example.com" in done.output
    assert chatgpt.signed_in(tmp_home) and cfg_mod.load(tmp_home).model == "chatgpt-plan/gpt-6.2-sol"


def test_a_pasted_address_that_is_not_the_answer_is_refused_in_the_console(tmp_home: Path, web, monkeypatch) -> None:
    import click

    monkeypatch.setattr(click, "prompt", lambda *a, **k: "127.0.0.1:1455/auth/callback?code=c&state=whatever")
    done = _cli(tmp_home, monkeypatch, "login", "--paste")

    assert done.exit_code != 0 and "copy the whole address" in done.output and not chatgpt.signed_in(tmp_home)


def test_console_logout_clears_a_plan_model_and_forget_deletes_the_registration(tmp_home: Path, web, monkeypatch) -> None:
    _sign_in(tmp_home, web)
    cfg_mod.save(cfg_mod.Config(home=tmp_home, model="chatgpt-plan/gpt-6.2-sol"))

    out = _cli(tmp_home, monkeypatch, "logout")

    assert out.exit_code == 0 and "now unset" in out.output and "did not confirm" in out.output
    assert cfg_mod.load(tmp_home).model == "" and chatgpt.load(tmp_home)["client_id"] == "oaiapp_1"
    assert "not signed in (last account: a@example.com)" in _cli(tmp_home, monkeypatch, "status").output

    _cli(tmp_home, monkeypatch, "logout", "--forget")
    assert not chatgpt.record_path(tmp_home).exists()
    assert _cli(tmp_home, monkeypatch, "logout").output.strip() == "not signed in"


def test_a_model_that_refuses_the_reasoning_block_is_asked_again_without_it(tmp_home: Path, web) -> None:
    calls, answers = web
    _sign_in(tmp_home, web)
    answers[chatgpt.RESPONSES_URL] = lambda sent: (
        (400, {"error": {"code": "unsupported_parameter", "message": "no reasoning", "param": "reasoning.summary"}}) if "reasoning" in sent else (200, _REPLY)
    )
    calls.clear()

    out = list(llm.stream(messages=_HISTORY, tools=_TOOLS, rt=_Runtime, **_plan_kwargs(tmp_home)))

    sent = [c[2] for c in calls if c[1] == chatgpt.RESPONSES_URL]
    assert ["reasoning" in body for body in sent] == [True, False] and out[-1]["finish_reason"] == "tool_calls"
