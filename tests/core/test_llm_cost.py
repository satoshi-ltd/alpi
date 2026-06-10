from __future__ import annotations

from types import SimpleNamespace

from alpi.llm import _reported_cost, _with_openrouter_extras


def test_reported_cost_prefers_hidden_response_cost() -> None:
    r = SimpleNamespace(_hidden_params={"response_cost": 3.906e-05}, usage=None)
    assert _reported_cost(r) == 3.906e-05


def test_reported_cost_reads_usage_cost_attr() -> None:
    r = SimpleNamespace(_hidden_params={}, usage=SimpleNamespace(cost=0.0123))
    assert _reported_cost(r) == 0.0123


def test_reported_cost_reads_usage_cost_via_model_dump() -> None:
    usage = SimpleNamespace(model_dump=lambda: {"cost": 0.05})
    r = SimpleNamespace(_hidden_params={}, usage=usage)
    assert _reported_cost(r) == 0.05


def test_reported_cost_none_when_absent() -> None:
    r = SimpleNamespace(_hidden_params={}, usage=SimpleNamespace())
    assert _reported_cost(r) is None


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
