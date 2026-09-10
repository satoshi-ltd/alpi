from __future__ import annotations

from types import SimpleNamespace

import pytest

from alpi.llm import _compute_cost_detail, _usage_cost, _with_openrouter_extras


def test_hidden_response_cost_alone_is_litellm_not_provider() -> None:
    r = SimpleNamespace(_hidden_params={"response_cost": 3.906e-05}, usage=None)
    assert _compute_cost_detail(r, "openrouter/x/y") == (3.906e-05, "litellm")


def test_usage_cost_reads_attr_and_model_dump() -> None:
    assert _usage_cost(SimpleNamespace(usage=SimpleNamespace(cost=0.0123))) == 0.0123
    usage = SimpleNamespace(model_dump=lambda: {"cost": 0.05})
    assert _usage_cost(SimpleNamespace(usage=usage)) == 0.05
    assert _usage_cost(SimpleNamespace(usage=SimpleNamespace())) is None


def test_cost_value_and_label_come_from_the_same_field() -> None:
    """litellm can stamp a DIFFERENT response_cost than the provider's usage.cost — billing must report the provider's number, never litellm's value under a provider label."""
    r = SimpleNamespace(
        _hidden_params={"response_cost": 0.01},
        usage=SimpleNamespace(cost=0.002),
    )
    assert _compute_cost_detail(r, "openrouter/x/y") == (0.002, "provider")


def test_openrouter_gets_usage_include_flag() -> None:
    model = "openrouter/deepseek/deepseek-v4-flash"
    k = _with_openrouter_extras({"model": model}, model)
    assert k["extra_body"]["usage"]["include"] is True


def test_openrouter_gets_alpi_attribution_headers() -> None:
    from alpi import __version__
    model = "openrouter/deepseek/deepseek-v4-flash"
    k = _with_openrouter_extras({"model": model}, model)
    assert k["extra_headers"]["X-Title"] == f"alpi/{__version__}"
    assert k["extra_headers"]["HTTP-Referer"] == "https://alpi.satoshi.ltd"


def test_openrouter_keeps_caller_headers() -> None:
    model = "openrouter/deepseek/deepseek-v4-flash"
    k = _with_openrouter_extras(
        {"model": model, "extra_headers": {"X-Title": "custom", "X-Other": "1"}},
        model,
    )
    assert k["extra_headers"]["X-Title"] == "custom"
    assert k["extra_headers"]["X-Other"] == "1"
    assert "HTTP-Referer" in k["extra_headers"]


def test_non_openrouter_kwargs_untouched() -> None:
    k = _with_openrouter_extras({"model": "gpt-4"}, "gpt-4")
    assert "extra_body" not in k
    assert "extra_headers" not in k


def test_compute_cost_prefers_reported() -> None:
    from alpi.llm import _compute_cost
    r = SimpleNamespace(_hidden_params={"response_cost": 0.002}, usage=None)
    assert _compute_cost(r, "openrouter/deepseek/deepseek-v4-flash") == 0.002


def test_compute_cost_openrouter_fallback_from_pricing(monkeypatch) -> None:
    import alpi.llm as llm
    monkeypatch.setattr(
        llm, "_openrouter_pricing",
        lambda: {"deepseek/deepseek-v4-flash": (1e-7, 2e-7)},
    )
    # unmapped model → _reported_cost None, completion_cost raises → pricing fallback
    r = SimpleNamespace(
        _hidden_params={},
        usage=SimpleNamespace(prompt_tokens=1000, completion_tokens=500),
    )
    cost = llm._compute_cost(r, "openrouter/deepseek/deepseek-v4-flash")
    assert abs(cost - (1000 * 1e-7 + 500 * 2e-7)) < 1e-12


def test_compute_cost_zero_when_no_pricing(monkeypatch) -> None:
    import alpi.llm as llm
    monkeypatch.setattr(llm, "_openrouter_pricing", lambda: {})
    r = SimpleNamespace(_hidden_params={}, usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5))
    assert llm._compute_cost(r, "openrouter/unknown/model") == 0.0


@pytest.mark.parametrize("suffix, expected", [
    (":nitro", (0.0002, "table-base")),
    (":free", (0.0, "none")),
    (":extended", (0.0, "none")),
])
def test_stream_cost_falls_back_only_for_nitro(monkeypatch, suffix, expected):
    import alpi.llm as llm
    import litellm
    monkeypatch.setattr(litellm, "completion_cost", lambda **kwargs: None)
    monkeypatch.setattr(llm, "_openrouter_pricing", lambda: {"x/y": (1e-7, 2e-7)})
    chunk = SimpleNamespace(usage=SimpleNamespace(prompt_tokens=1000, completion_tokens=500))
    result = llm._final_chunk(chunk, {}, "openrouter/x/y" + suffix)
    assert result["cost_usd"] == pytest.approx(expected[0])
    assert result["cost_source"] == expected[1]


@pytest.mark.parametrize("reported", [0.0, 0.017])
def test_nitro_reported_cost_wins(monkeypatch, reported):
    import alpi.llm as llm
    def unexpected_lookup():
        pytest.fail("Reported cost must not consult the price catalog")
    monkeypatch.setattr(llm, "_openrouter_pricing", unexpected_lookup)
    chunk = SimpleNamespace(usage=SimpleNamespace(cost=reported))
    assert llm._compute_cost_detail(chunk, "openrouter/x/y:nitro") == (reported, "provider")


def test_nitro_exact_catalog_price_wins(monkeypatch):
    import alpi.llm as llm
    import litellm
    monkeypatch.setattr(litellm, "completion_cost", lambda **kwargs: None)
    monkeypatch.setattr(llm, "_openrouter_pricing", lambda: {
        "x/y": (1e-7, 2e-7), "x/y:nitro": (3e-7, 4e-7),
    })
    chunk = SimpleNamespace(usage=SimpleNamespace(prompt_tokens=1000, completion_tokens=500))
    cost, source = llm._compute_cost_detail(chunk, "openrouter/x/y:nitro")
    assert cost == pytest.approx(0.0005)
    assert source == "table"


def test_final_chunk_carries_generation_id_and_provider():
    import alpi.llm as llm
    chunk = SimpleNamespace(
        id="gen-1789000023-QWErEBRKkhQRzrApGTgy", provider=None,
        usage=SimpleNamespace(cost=0.001),
    )
    result = llm._final_chunk(chunk, {}, "openrouter/x/y", "OpenInference")
    assert result["generation_id"] == "gen-1789000023-QWErEBRKkhQRzrApGTgy"
    assert result["provider"] == "OpenInference"


def test_final_chunk_falls_back_to_chunk_provider():
    import alpi.llm as llm
    chunk = SimpleNamespace(id=None, provider="DeepInfra", usage=SimpleNamespace(cost=0.001))
    result = llm._final_chunk(chunk, {}, "openrouter/x/y")
    assert result["provider"] == "DeepInfra"
    assert result["generation_id"] is None


@pytest.mark.parametrize('reported', [0.0, 0.0123])
def test_openrouter_wire_usage_survives_litellm_stream(monkeypatch, reported):
    import json
    import httpx
    import alpi.llm as llm
    captured = []

    def send(client, request, **kwargs):
        captured.append(json.loads(request.content))
        chunk = {
            'id': 'gen-local-test', 'created': 1,
            'model': 'deepseek/deepseek-v4-flash-0731',
            'choices': [{'index': 0, 'delta': {'content': 'ok', 'reasoning': 'New reasoning.'}, 'finish_reason': 'stop'}],
        }
        usage = dict(chunk, choices=[], usage={
            'prompt_tokens': 1000, 'completion_tokens': 10, 'total_tokens': 1010,
            'cost': reported,
            'prompt_tokens_details': {'cached_tokens': 800, 'cache_write_tokens': 50},
        })
        body = ''.join('data: ' + json.dumps(c) + '\n\n' for c in [chunk, usage]) + 'data: [DONE]\n\n'
        return httpx.Response(200, request=request, headers={'content-type': 'text/event-stream'}, content=body.encode())

    monkeypatch.setattr(httpx.Client, 'send', send)
    chunks = list(llm.stream(
        messages=[{'role': 'user', 'content': 'test'}, {
            'role': 'assistant', 'content': '', 'reasoning_content': 'Previous reasoning.',
            'tool_calls': [{'id': 'tc1', 'type': 'function', 'function': {'name': 'test', 'arguments': '{}'}}],
        }, {'role': 'tool', 'tool_call_id': 'tc1', 'content': 'ok'}],
        tools=[], model='openrouter/deepseek/deepseek-v4-flash-0731:nitro',
        api_key='local-test-only',
        extra_body={'session_id': 'alpi-test', 'reasoning': {'effort': 'medium'}},
    ))
    final = chunks[-1]
    assert ''.join(c.get('reasoning_delta', '') for c in chunks) == 'New reasoning.'
    assert final['cost_usd'] == reported
    assert final['cost_source'] == 'provider'
    assert final['cached_tokens'] == 800
    assert final['cache_write_tokens'] == 50
    assert final['input_tokens'] == 1000
    assert captured[0]['session_id'] == 'alpi-test'
    assert captured[0]['reasoning'] == {'effort': 'medium'}
    assistant = captured[0]['messages'][1]
    assert assistant.get('reasoning_content', assistant.get('reasoning')) == 'Previous reasoning.'


def test_extra_body_reaches_the_request_and_identity_comes_back(monkeypatch):
    import json
    import httpx
    import alpi.llm as llm
    captured = []

    def send(client, request, **kwargs):
        captured.append(json.loads(request.content))
        chunk = {
            'id': 'gen-pin-test', 'created': 1, 'provider': 'OpenInference',
            'model': 'deepseek/deepseek-v4-flash-0731',
            'choices': [{'index': 0, 'delta': {'content': 'ok'}, 'finish_reason': 'stop'}],
        }
        usage = dict(chunk, choices=[], usage={
            'prompt_tokens': 10, 'completion_tokens': 2, 'total_tokens': 12, 'cost': 0.001,
        })
        body = ''.join('data: ' + json.dumps(c) + '\n\n' for c in [chunk, usage]) + 'data: [DONE]\n\n'
        return httpx.Response(200, request=request, headers={'content-type': 'text/event-stream'}, content=body.encode())

    monkeypatch.setattr(httpx.Client, 'send', send)
    extra = {'session_id': 'alpi-test'}
    final = list(llm.stream(
        messages=[{'role': 'user', 'content': 'test'}], tools=[],
        model='openrouter/deepseek/deepseek-v4-flash-0731', api_key='local-test-only',
        extra_body=extra,
    ))[-1]
    assert captured[0]['session_id'] == 'alpi-test'
    assert captured[0]['usage'] == {'include': True}
    assert final['generation_id'] == 'gen-pin-test'
    assert final['cost_source'] == 'provider'


def test_streaming_drops_provider_but_keeps_generation_id(monkeypatch):
    """litellm rebuilds stream chunks without OpenRouter's provider field; the generation id is the recovery path."""
    import json
    import httpx
    import alpi.llm as llm

    def send(client, request, **kwargs):
        chunk = {
            'id': 'gen-stream-test', 'created': 1, 'provider': 'OpenInference', 'model': 'm',
            'choices': [{'index': 0, 'delta': {'content': 'ok'}, 'finish_reason': 'stop'}],
        }
        usage = dict(chunk, choices=[], usage={'prompt_tokens': 10, 'completion_tokens': 2, 'cost': 0.001})
        body = ''.join('data: ' + json.dumps(c) + '\n\n' for c in [chunk, usage]) + 'data: [DONE]\n\n'
        return httpx.Response(200, request=request, headers={'content-type': 'text/event-stream'}, content=body.encode())

    monkeypatch.setattr(httpx.Client, 'send', send)
    final = list(llm.stream(
        messages=[{'role': 'user', 'content': 't'}], tools=[],
        model='openrouter/x/y', api_key='local-test-only',
    ))[-1]
    assert final['generation_id'] == 'gen-stream-test'
    assert final['provider'] is None
