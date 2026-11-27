from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from alpi import config as cfg_mod
from alpi import llm, prompt_cache

ollama = importlib.import_module("alpi.providers.ollama")


@pytest.fixture(autouse=True)
def _litellm_table_as_found():
    import litellm

    before = {k for k in litellm.model_cost if k.startswith("ollama_chat/")}
    yield
    for key in [k for k in litellm.model_cost if k.startswith("ollama_chat/") and k not in before]:
        del litellm.model_cost[key]


@pytest.fixture
def ollama_kwargs(tmp_home: Path, monkeypatch) -> dict[str, Any]:
    monkeypatch.setattr(ollama, "_NUM_CTX_CACHE", {("http://box:11434", "qwen3:8b"): 8192})
    return cfg_mod.resolve_model(_profile(tmp_home, "box/qwen3:8b", ollama_url="http://box:11434"))

TOOLS = [{"type": "function", "function": {"name": "read_file", "description": "d", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}}}}]
TOOL_LOOP = [
    {"role": "system", "content": "SYS " * 50},
    {"role": "user", "content": "hi"},
    {"role": "assistant", "content": "", "tool_calls": [{"id": "call_1", "type": "function", "function": {"name": "read_file", "arguments": "{\"path\": \"a\"}"}}]},
    {"role": "tool", "tool_call_id": "call_1", "content": "body"},
]


class _Runtime:
    first_byte_timeout_s = 5
    stream_idle_timeout_s = 5
    stream_max_duration_s = 10
    max_retries = 0
    retry_backoff_s = 0.01


def _requests(monkeypatch, kwargs: dict[str, Any], *, stream: bool = True, messages=TOOL_LOOP) -> list[tuple[str, dict]]:
    seen: list[tuple[str, dict]] = []

    def fake_send(self, request, **kw):
        seen.append((str(request.url), json.loads(request.content or b"{}")))
        raise RuntimeError("stop before the network")

    monkeypatch.setattr(httpx.Client, "send", fake_send)
    try:
        if stream:
            list(llm.stream(messages=messages, tools=TOOLS, rt=_Runtime, **kwargs))
        else:
            llm.complete(messages=messages, tools=TOOLS, num_retries=0, **kwargs)
    except Exception:  # noqa: BLE001
        pass
    assert seen, "no request reached the transport"
    return seen


def _profile(tmp_home: Path, model: str, effort: str = "", ollama_url: str = "", env: str = "") -> cfg_mod.Config:
    cfg_mod.seed_defaults(tmp_home)
    (tmp_home / ".env").write_text(env)
    cfg = cfg_mod.load(tmp_home)
    cfg.model = model
    cfg.model_reasoning.effort = effort
    if ollama_url:
        cfg.providers["ollama"] = [{"name": "box", "url": ollama_url}]
    return cfg


def _call_kwargs(cfg: cfg_mod.Config) -> dict[str, Any]:
    kwargs = cfg_mod.resolve_model(cfg)
    kwargs.update(prompt_cache.cache_kwargs_for_model(kwargs.get("model", ""), kwargs.get("api_base")))
    return kwargs


@pytest.mark.parametrize("stream", [True, False])
def test_ollama_gets_the_context_size_where_its_api_reads_it(tmp_home: Path, monkeypatch, stream: bool) -> None:
    from alpi import ctx_window

    monkeypatch.setattr(ollama, "_NUM_CTX_CACHE", {("http://box:11434", "qwen3:8b"): 8192})
    monkeypatch.setattr(ollama, "supports_thinking", lambda url, model: True)
    cfg = _profile(tmp_home, "box/qwen3:8b", effort="high", ollama_url="http://box:11434/v1")
    assert ctx_window.resolve(tmp_home, cfg, cfg.model) == 8192

    seen = _requests(monkeypatch, {**_call_kwargs(cfg), "max_tokens": 77}, stream=stream)

    assert [url for url, _ in seen] == ["http://box:11434/api/chat"]
    body = seen[0][1]
    assert body["model"] == "qwen3:8b" and body["stream"] is stream
    assert body["options"] == {"num_predict": 77, "num_ctx": 8192}
    assert body["think"] is True
    assert body["tools"][0]["function"]["name"] == "read_file"
    assert body["messages"][2]["tool_calls"] == [{"function": {"name": "read_file", "arguments": {"path": "a"}}}]


def test_ollama_ignores_the_parameters_its_native_route_does_not_take(tmp_home: Path, monkeypatch) -> None:
    monkeypatch.setattr(ollama, "_NUM_CTX_CACHE", {("http://box:11434", "qwen3:8b"): 8192})
    cfg = _profile(tmp_home, "box/qwen3:8b", ollama_url="http://box:11434")

    seen = _requests(monkeypatch, {**_call_kwargs(cfg), "tool_choice": "required", "parallel_tool_calls": False})

    assert [url for url, _ in seen] == ["http://box:11434/api/chat"]
    assert "tool_choice" not in seen[0][1] and "parallel_tool_calls" not in seen[0][1]


def test_a_direct_anthropic_tool_only_turn_carries_no_placeholder_text(tmp_home: Path, monkeypatch) -> None:
    cfg = _profile(tmp_home, "anthropic/claude-sonnet-5-5", env="ANTHROPIC_API_KEY=sk-ant-test\n")

    body = _requests(monkeypatch, _call_kwargs(cfg))[-1][1]

    assert body["messages"][1] == {"role": "assistant", "content": [{"type": "tool_use", "id": "call_1", "name": "read_file", "input": {"path": "a"}}]}
    assert "sanitised" not in json.dumps(body)
    assert TOOL_LOOP[2]["content"] == ""


def test_a_direct_gemini_call_is_one_request_with_the_effort_and_no_empty_part(tmp_home: Path, monkeypatch) -> None:
    cfg = _profile(tmp_home, "gemini/gemini-4-carbon", effort="high", env="GEMINI_API_KEY=g-test\n")
    kwargs = _call_kwargs(cfg)
    assert "cache_control_injection_points" not in kwargs

    big = [{"role": "system", "content": "You are alpi, a careful agent. " * 2500}, *TOOL_LOOP[1:]]
    seen = _requests(monkeypatch, kwargs, messages=big)

    assert len(seen) == 1 and "streamGenerateContent" in seen[0][0] and "cachedContents" not in seen[0][0]
    body = seen[0][1]
    assert "cachedContent" not in body
    assert body["generationConfig"]["thinkingConfig"]["thinkingLevel"] == "high"
    assert [list(part) for part in body["contents"][1]["parts"]] == [["function_call", "thoughtSignature"]]


def test_a_direct_openai_reasoning_turn_asks_not_to_be_stored(tmp_home: Path, monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_API_BASE", raising=False)
    cfg = _profile(tmp_home, "openai/gpt-6.2-sol", effort="high", env="OPENAI_API_KEY=sk-test\n")

    url, body = _requests(monkeypatch, _call_kwargs(cfg))[-1]

    assert url == "https://api.openai.com/v1/responses"
    assert body["store"] is False and body["reasoning"] == {"effort": "high"}


def test_store_is_sent_only_to_openai_itself(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_API_BASE", raising=False)
    base = {"messages": [{"role": "user", "content": "hi"}]}
    assert llm._provider_bound({**base, "model": "gpt-6-luna"})["store"] is False
    assert llm._provider_bound({**base, "model": "openai/gpt-6-luna"})["store"] is False
    assert llm._provider_bound({**base, "model": "openai/gpt-6-luna", "store": True})["store"] is True
    assert "store" not in llm._provider_bound({**base, "model": "openai/some-model", "api_base": "http://gateway:4000/v1"})
    for model in ("openrouter/openai/gpt-6-luna", "anthropic/claude-haiku-5-5", "groq/openai/gpt-oss-20b"):
        assert "store" not in llm._provider_bound({**base, "model": model}), model


def test_only_direct_anthropic_and_gemini_get_the_tool_only_text_removed() -> None:
    answered = {"role": "assistant", "content": "", "tool_calls": []}
    for model, expected in (
        ("anthropic/claude-haiku-5-5", None), ("gemini/gemini-4-neon", None),
        ("openrouter/anthropic/claude-haiku-5.5", ""), ("openai/gpt-6-luna", ""), ("openrouter/deepseek/deepseek-v4.1-flash", ""),
    ):
        out = llm._provider_bound({"model": model, "messages": [*TOOL_LOOP, answered]})["messages"]
        assert out[2].get("content", "missing") == expected, model
        assert out[4] == answered, model
    assert TOOL_LOOP[2]["content"] == ""


def test_a_whitespace_only_tool_turn_is_sent_without_text_and_a_spoken_one_keeps_it() -> None:
    call = TOOL_LOOP[2]["tool_calls"]
    blank = {"role": "assistant", "content": " \n", "tool_calls": call}
    spoken = {"role": "assistant", "content": "Reading it.", "tool_calls": call}
    out = llm._provider_bound({"model": "anthropic/claude-haiku-5-5", "messages": [blank, spoken]})["messages"]
    assert out == [{**blank, "content": None}, spoken]


def test_an_ollama_model_is_registered_so_litellm_never_asks_a_default_server(tmp_home: Path, monkeypatch) -> None:
    import litellm

    from alpi import attachments

    monkeypatch.setitem(litellm.model_cost, "ollama_chat/fresh-model:1b", {})
    monkeypatch.delitem(litellm.model_cost, "ollama_chat/fresh-model:1b")
    asked: list[str] = []
    monkeypatch.setattr(litellm.module_level_client, "post", lambda *a, **k: asked.append(str(k.get("url"))))
    cfg = _profile(tmp_home, "box/fresh-model:1b", ollama_url="http://box:11434")

    model = cfg_mod.resolve_model(cfg)["model"]

    assert model == "ollama_chat/fresh-model:1b"
    assert prompt_cache.cache_kwargs_for_model(model, "http://box:11434") == {}
    assert attachments.vision_status(model) == "no"
    assert attachments.model_context_tokens(model) is None
    assert asked == []


def _ollama_replies(monkeypatch, lines: list[dict]) -> list[tuple[str, dict]]:
    raw = "".join(json.dumps(line) + "\n" for line in lines).encode()
    seen: list[tuple[str, dict]] = []

    def fake_send(self, request, **kw):
        seen.append((str(request.url), json.loads(request.content or b"{}")))
        return httpx.Response(200, content=raw, request=request)

    monkeypatch.setattr(httpx.Client, "send", fake_send)
    return seen


def _ollama_chunk(**message) -> dict:
    return {"model": "qwen3:8b", "message": {"role": "assistant", "content": "", **message}, "done": False}


def _ollama_call(index: int, arguments: dict, call_id: str | None = "srv") -> dict:
    call = {"function": {"index": index, "name": "read_file", "arguments": arguments}}
    return {**call, "id": f"{call_id}_{index}"} if call_id else call


_OLLAMA_DONE = {"model": "qwen3:8b", "message": {"role": "assistant", "content": ""}, "done": True, "done_reason": "stop", "prompt_eval_count": 321, "eval_count": 45}


def test_ollama_tool_calls_streamed_one_per_chunk_stay_separate_calls(ollama_kwargs, monkeypatch) -> None:
    seen = _ollama_replies(monkeypatch, [
        _ollama_chunk(thinking="plan"),
        _ollama_chunk(content="Reading. "),
        _ollama_chunk(tool_calls=[_ollama_call(0, {"path": "a"})]),
        _ollama_chunk(tool_calls=[_ollama_call(1, {"path": "b"})]),
        _ollama_chunk(tool_calls=[_ollama_call(2, {})]),
        _ollama_chunk(tool_calls=[_ollama_call(3, {}, call_id=None)]),
        _OLLAMA_DONE,
    ])

    out = list(llm.stream(messages=TOOL_LOOP[:2], tools=TOOLS, rt=_Runtime, **ollama_kwargs))

    assert [url for url, _ in seen] == ["http://box:11434/api/chat"]
    final = out[-1]
    assert [(c["name"], c["arguments"]) for c in final["tool_calls"]] == [
        ("read_file", '{"path": "a"}'), ("read_file", '{"path": "b"}'), ("read_file", "{}"), ("read_file", "{}"),
    ]
    ids = [c["id"] for c in final["tool_calls"]]
    assert all(ids) and len(set(ids)) == 4
    assert "".join(c.get("text_delta", "") for c in out[:-1]) == "Reading. "
    assert "".join(c.get("reasoning_delta", "") for c in out[:-1]) == "plan"
    assert (final["input_tokens"], final["output_tokens"], final["finish_reason"]) == (321, 45, "tool_calls")


def test_two_ollama_tool_calls_in_one_chunk_stay_separate_calls(ollama_kwargs, monkeypatch) -> None:
    _ollama_replies(monkeypatch, [_ollama_chunk(tool_calls=[_ollama_call(0, {"path": "a"}), _ollama_call(1, {"path": "b"})]), _OLLAMA_DONE])

    final = list(llm.stream(messages=TOOL_LOOP[:2], tools=TOOLS, rt=_Runtime, **ollama_kwargs))[-1]

    assert [c["arguments"] for c in final["tool_calls"]] == ['{"path": "a"}', '{"path": "b"}']


def test_an_openai_style_stream_still_joins_the_fragments_of_one_call() -> None:
    from types import SimpleNamespace as NS

    def chunk(index: int, call_id: str | None, name: str | None, arguments: str) -> NS:
        call = NS(index=index, id=call_id, function=NS(name=name, arguments=arguments))
        return NS(choices=[NS(delta=NS(content="", tool_calls=[call]), finish_reason=None)])

    accum: dict = {}
    for piece in (chunk(0, "call_a", "read_file", '{"pa'), chunk(0, None, None, 'th": "a"}'), chunk(1, "call_b", "read_file", "{}")):
        llm._normalize_chunk(piece, accum)

    assert accum == {
        0: {"id": "call_a", "name": "read_file", "arguments": '{"path": "a"}'},
        1: {"id": "call_b", "name": "read_file", "arguments": "{}"},
    }


def test_a_complete_ollama_reply_carries_its_calls_text_and_usage(ollama_kwargs, monkeypatch) -> None:
    reply = {**_OLLAMA_DONE, "message": {"role": "assistant", "content": "Done.", "thinking": "plan", "tool_calls": [_ollama_call(0, {"path": "a"}), _ollama_call(1, {})]}}
    seen = _ollama_replies(monkeypatch, [reply])

    out = llm.complete(messages=TOOL_LOOP[:2], tools=TOOLS, **ollama_kwargs)

    assert [(url, body["options"], body["stream"]) for url, body in seen] == [("http://box:11434/api/chat", {"num_ctx": 8192}, False)]
    assert len({c["id"] for c in out.tool_calls}) == 2 and all(c["id"] for c in out.tool_calls)
    assert out.content == "Done." and (out.input_tokens, out.output_tokens) == (321, 45)
    assert [(c["name"], c["arguments"]) for c in out.tool_calls] == [("read_file", '{"path": "a"}'), ("read_file", "{}")]


def test_an_old_history_with_a_broken_tool_call_still_reaches_ollama(ollama_kwargs, monkeypatch) -> None:
    calls = [
        {"id": "c1", "function": {"name": "read_file", "arguments": ""}},
        {"id": "c2", "type": "function", "function": {"name": "read_file", "arguments": '{"path": "a'}},
        {"id": "c3", "type": "function", "function": {"name": "read_file", "arguments": '{"path": "b"}'}},
        {"id": "c4", "function": {"name": "read_file", "arguments": '{"path": "c"}'}},
        {"id": "c5", "type": "function", "function": {"name": "read_file", "arguments": "[1]"}},
        "not a call",
    ]
    history = [*TOOL_LOOP[:2], {"role": "assistant", "content": "", "tool_calls": calls}]

    seen = _requests(monkeypatch, ollama_kwargs, messages=history)

    assert [url for url, _ in seen] == ["http://box:11434/api/chat"]
    assert [c["function"]["arguments"] for c in seen[0][1]["messages"][2]["tool_calls"]] == [{}, {}, {"path": "b"}, {"path": "c"}, {}]
    assert calls[0]["function"]["arguments"] == "" and "type" not in calls[0]


def test_an_effort_litellm_would_refuse_for_a_gemini_id_is_left_out() -> None:
    base = {"messages": [{"role": "user", "content": "hi"}], "reasoning_effort": "high"}
    assert "reasoning_effort" not in llm._provider_bound({**base, "model": "gemini/gemini-2.5-flash-preview-09-2025"})
    assert llm._provider_bound({**base, "model": "gemini/gemini-4-carbon"})["reasoning_effort"] == "high"
    assert llm._provider_bound({**base, "model": "anthropic/claude-haiku-5-5"})["reasoning_effort"] == "high"


def test_a_gemini_id_litellm_refuses_an_effort_for_still_sends_its_request(tmp_home: Path, monkeypatch) -> None:
    cfg = _profile(tmp_home, "gemini/gemini-2.5-flash-preview-09-2025", effort="high", env="GEMINI_API_KEY=g-test\n")

    seen = _requests(monkeypatch, _call_kwargs(cfg))

    assert "streamGenerateContent" in seen[0][0]
