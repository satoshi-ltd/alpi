from alpi import llm


def test_free_by_zero_pricing(monkeypatch):
    monkeypatch.setattr(llm, "_openrouter_pricing", lambda: {"x/y": (0.0, 0.0)})
    assert llm.is_free_model("openrouter/x/y") is True


def test_free_by_zero_pricing_without_free_suffix(monkeypatch):
    monkeypatch.setattr(llm, "_openrouter_pricing", lambda: {"deepseek/r1": (0.0, 0.0)})
    assert llm.is_free_model("openrouter/deepseek/r1") is True


def test_free_suffix_alone_is_not_free(monkeypatch):
    monkeypatch.setattr(llm, "_openrouter_pricing", lambda: {})
    assert llm.is_free_model("openrouter/deepseek/r1:free") is False


def test_paid_pricing_is_not_free(monkeypatch):
    monkeypatch.setattr(llm, "_openrouter_pricing", lambda: {"x/y": (1e-6, 2e-6)})
    assert llm.is_free_model("openrouter/x/y") is False


def test_non_openrouter_is_not_free():
    assert llm.is_free_model("anthropic/claude-opus-4") is False
