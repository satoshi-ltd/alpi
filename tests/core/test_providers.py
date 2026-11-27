from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from alpi.providers.base import ModelInfo, Provider
from alpi.providers import curated, google, openrouter

ollama = importlib.import_module("alpi.providers.ollama")


def test_provider_has_key_uses_environment(monkeypatch) -> None:
    class DummyProvider(Provider):
        name = "dummy"
        display = "Dummy"
        api_key_env = "DUMMY_PROVIDER_KEY"

        def list_models(self) -> list[ModelInfo]:
            return []

    provider = DummyProvider()
    monkeypatch.delenv("DUMMY_PROVIDER_KEY", raising=False)
    assert provider.has_key() is False
    monkeypatch.setenv("DUMMY_PROVIDER_KEY", "secret")
    assert provider.has_key() is True


def test_provider_has_key_accepts_explicit_env(monkeypatch) -> None:
    """Daemon needs to ask "does THIS profile have the key?" without leaking other profiles' env into the lookup."""
    class DummyProvider(Provider):
        name = "dummy"
        display = "Dummy"
        api_key_env = "DUMMY_PROVIDER_KEY"

        def list_models(self) -> list[ModelInfo]:
            return []

    provider = DummyProvider()
    monkeypatch.setenv("DUMMY_PROVIDER_KEY", "in-os-env")
    # Empty env explicitly says "this profile has no key" — must override os.environ.
    assert provider.has_key(env={}) is False
    assert provider.has_key(env={"DUMMY_PROVIDER_KEY": "alice"}) is True
    # Default still falls back to os.environ for legacy callers.
    assert provider.has_key() is True


def test_google_and_groq_offer_the_curated_models_under_their_litellm_prefix() -> None:
    from alpi.providers import groq

    assert [m.id for m in google.Google().list_models()] == [
        "gemini/gemini-4-carbon", "gemini/gemini-4-neon", "gemini/gemini-4-hydrogen", "gemini/gemini-3.5-flash-lite",
    ]
    assert [m.id for m in groq.Groq().list_models()] == ["groq/openai/gpt-oss-120b", "groq/openai/gpt-oss-20b"]
    assert all(m.note for m in google.Google().list_models() + groq.Groq().list_models())


def test_every_model_a_keyed_provider_offers_has_a_window_price_and_tools() -> None:
    import alpi.llm  # noqa: F401
    import litellm

    from alpi import providers

    for provider in providers.builtin():
        if provider.name == "openrouter" or not provider.api_key_env:
            continue
        for model in provider.list_models():
            info = litellm.model_cost.get(model.id) or litellm.model_cost.get(model.id.split("/", 1)[1])
            assert info, model.id
            assert info.get("max_input_tokens", 0) >= 100_000 and info.get("input_cost_per_token", 0) > 0, model.id
            assert info.get("supports_function_calling"), model.id


def test_the_curated_google_and_groq_models_are_in_alpi_native_catalogue() -> None:
    from alpi.providers.curated import load_curated
    from alpi.providers.native import catalogue

    native = catalogue()
    for provider, prefix in (("google", "gemini/"), ("groq", "groq/")):
        for entry in load_curated(provider):
            assert native.get(prefix + entry["id"], {}).get("max_input_tokens", 0) >= 100_000, entry["id"]


def test_openrouter_list_models_reads_config(monkeypatch, tmp_path: Path) -> None:
    cfg = type("Cfg", (), {
        "providers": {"openrouter": {"models": ["foo/bar", "baz"]}},
    })()
    monkeypatch.setattr(openrouter.cfg_mod, "load", lambda home: cfg)
    monkeypatch.setattr(openrouter, "get_home", lambda: tmp_path)
    monkeypatch.setattr(openrouter, "load_curated", lambda provider: [
        {"id": "baz", "note": "duplicate"},
        {"id": "deepseek/vision", "note": "vision"},
    ])

    models = openrouter.OpenRouter().list_models()

    assert [m.id for m in models] == [
        "openrouter/foo/bar", "openrouter/baz", "openrouter/deepseek/vision",
    ]
    assert [m.display for m in models] == ["foo/bar", "baz", "deepseek/vision"]
    assert models[-1].note == "vision"


def test_curated_load_curated_returns_copy(monkeypatch) -> None:
    monkeypatch.setattr(curated, "_load_all", lambda: {
        "google": [{"id": "gemini/flash"}],
    })

    models = curated.load_curated("google")
    assert models == [{"id": "gemini/flash"}]
    models.append({"id": "mutated"})
    assert curated.load_curated("google") == [{"id": "gemini/flash"}]


def test_openrouter_curated_offers_no_floating_id() -> None:
    """A `~` id redirects to whatever the vendor ships next, so a scheduled fleet changes model with no config change; every alias in OpenRouter's catalog carries that prefix."""
    ids = {row["id"] for row in curated.load_curated("openrouter")}
    assert not [i for i in ids if i.startswith("~")]
    assert "deepseek/deepseek-v4-flash-0731" in ids


def test_openrouter_curated_includes_glm_5_3_flash() -> None:
    rows = {row["id"]: row for row in curated.load_curated("openrouter")}
    assert rows["z-ai/glm-5.3-flash"] == {
        "id": "z-ai/glm-5.3-flash",
        "note": "text+image+video · up to 1.25M · reasoning always on, defaults to max",
        "reasoning": True,
    }


def test_ollama_helpers_cover_root_and_size() -> None:
    assert ollama._root("http://localhost:11434/v1/") == "http://localhost:11434"
    assert ollama._root("http://localhost:11434/") == "http://localhost:11434"
    assert ollama._fmt_size(50 * 1024 * 1024) == "50 MB"
    assert ollama._fmt_size(2 * 1024**3) == "2.0 GB"


def test_ollama_connections_filters_and_strips() -> None:
    providers = ollama.connections([
        {"name": " home ", "url": "http://localhost:11434/"},
        {"name": "", "url": "http://example"},
        {"name": "bad", "url": ""},
    ])

    assert len(providers) == 1
    assert providers[0].name == "home"
    assert providers[0].url == "http://localhost:11434"
    assert providers[0].display == "home"


class _FakeResp:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("boom")

    def json(self):
        return self._payload


class _FakeClient:
    def __init__(self, *, tags=None, show=None, fail=False):
        self.tags = tags or {}
        self.show = show or {}
        self.fail = fail
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def get(self, url):
        self.calls.append(("get", url))
        if self.fail:
            raise RuntimeError("network")
        return _FakeResp(self.tags)

    def post(self, url, json):
        self.calls.append(("post", url, json))
        if self.fail:
            raise RuntimeError("network")
        return _FakeResp(self.show)


def test_ollama_resolve_num_ctx_reads_the_modelfile_value(monkeypatch) -> None:
    fake = _FakeClient(show={"parameters": "num_ctx 8192\n"})
    monkeypatch.setattr(ollama.httpx, "Client", lambda timeout=0: fake)
    monkeypatch.setattr(ollama, "_NUM_CTX_CACHE", {})

    assert ollama.resolve_num_ctx("http://localhost:11434/v1", "llama3") == 8192
    assert fake.calls == [("post", "http://localhost:11434/api/show", {"name": "llama3"})]


@pytest.mark.parametrize(("show", "expected"), [
    ({"model_info": {"qwen3_5.context_length": 262144}}, 32768),
    ({"model_info": {"tiny.context_length": 8192}}, 8192),
    ({"parameters": "num_ctx 131072", "model_info": {"big.context_length": 262144}}, 131072),
    ({}, 32768),
])
def test_ollama_asks_for_the_model_maximum_only_when_the_modelfile_says_so(monkeypatch, show, expected) -> None:
    monkeypatch.setattr(ollama.httpx, "Client", lambda timeout=0: _FakeClient(show=show))
    monkeypatch.setattr(ollama, "_NUM_CTX_CACHE", {})

    assert ollama.resolve_num_ctx("http://box:11434", "m") == expected


def test_ollama_context_size_is_one_answer_for_every_spelling_of_the_server_url(monkeypatch) -> None:
    fake = _FakeClient(show={"parameters": "num_ctx 8192"})
    monkeypatch.setattr(ollama.httpx, "Client", lambda timeout=0: fake)
    monkeypatch.setattr(ollama, "_NUM_CTX_CACHE", {})

    sizes = {ollama.resolve_num_ctx(url, "m") for url in ("http://box:11434/v1", "http://box:11434/", "http://box:11434")}

    assert sizes == {8192} and len(fake.calls) == 1


def test_ollama_context_size_is_not_pinned_to_the_guess_made_while_the_server_was_down(monkeypatch) -> None:
    now = [1000.0]
    monkeypatch.setattr(ollama.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(ollama, "_NUM_CTX_CACHE", {})
    monkeypatch.setattr(ollama, "_NUM_CTX_MISS", {})
    down = _FakeClient(fail=True)
    monkeypatch.setattr(ollama.httpx, "Client", lambda timeout=0: down)
    assert ollama.resolve_num_ctx("http://box:11434", "m") == 32768
    assert ollama.resolve_num_ctx("http://box:11434", "m") == 32768
    assert len(down.calls) == 1

    up = _FakeClient(show={"parameters": "num_ctx 8192"})
    monkeypatch.setattr(ollama.httpx, "Client", lambda timeout=0: up)
    now[0] += ollama._NUM_CTX_MISS_TTL - 1
    assert ollama.resolve_num_ctx("http://box:11434", "m") == 32768 and up.calls == []
    now[0] += 2
    assert ollama.resolve_num_ctx("http://box:11434", "m") == 8192


def test_a_turn_keeps_the_size_it_first_resolved_even_when_the_server_comes_back(monkeypatch) -> None:
    now = [1000.0]
    monkeypatch.setattr(ollama.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(ollama, "_NUM_CTX_CACHE", {})
    monkeypatch.setattr(ollama, "_NUM_CTX_MISS", {})
    monkeypatch.setattr(ollama.httpx, "Client", lambda timeout=0: _FakeClient(fail=True))

    with ollama.one_size_per_turn():
        budget = ollama.resolve_num_ctx("http://box:11434/v1", "m")
        monkeypatch.setattr(ollama.httpx, "Client", lambda timeout=0: _FakeClient(show={"parameters": "num_ctx 8192"}))
        now[0] += ollama._NUM_CTX_MISS_TTL + 1
        sent = ollama.call_kwargs({"model": "ollama_chat/m", "api_base": "http://box:11434", "messages": []})["num_ctx"]

    assert (budget, sent) == (32768, 32768)
    assert ollama.resolve_num_ctx("http://box:11434", "m") == 8192


def test_ollama_supports_thinking_reads_the_capabilities_list(monkeypatch) -> None:
    fake = _FakeClient(show={"capabilities": ["completion", "tools", "thinking"]})
    monkeypatch.setattr(ollama.httpx, "Client", lambda timeout=0: fake)
    ollama._THINKING_CACHE.clear()

    assert ollama.supports_thinking("http://localhost:11434/v1", "gpt-oss:20b") is True
    assert ollama.supports_thinking("http://localhost:11434/v1", "gpt-oss:20b") is True
    assert fake.calls == [("post", "http://localhost:11434/api/show", {"name": "gpt-oss:20b"})]


def test_ollama_supports_thinking_is_false_without_the_capability(monkeypatch) -> None:
    for show in ({"capabilities": ["completion", "tools"]}, {}):
        fake = _FakeClient(show=show)
        monkeypatch.setattr(ollama.httpx, "Client", lambda timeout=0, fake=fake: fake)
        ollama._THINKING_CACHE.clear()

        assert ollama.supports_thinking("http://localhost:11434", "llama3") is False


def test_ollama_supports_thinking_retries_a_failed_lookup_after_the_miss_ttl(monkeypatch) -> None:
    clients = iter([_FakeClient(fail=True), _FakeClient(show={"capabilities": ["thinking"]})])
    now = [1000.0]
    monkeypatch.setattr(ollama.httpx, "Client", lambda timeout=0: next(clients))
    monkeypatch.setattr(ollama.time, "monotonic", lambda: now[0])
    ollama._THINKING_CACHE.clear()

    assert ollama.supports_thinking("http://remote:11434", "m") is False
    now[0] += ollama._THINKING_MISS_TTL - 1
    assert ollama.supports_thinking("http://remote:11434", "m") is False
    now[0] += 2
    assert ollama.supports_thinking("http://remote:11434", "m") is True


def test_the_curated_anthropic_and_openai_lists_are_the_current_models() -> None:
    from alpi.providers.curated import load_curated

    assert [m["id"] for m in load_curated("anthropic")] == ["claude-fable-5-2", "claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"]
    assert [m["id"] for m in load_curated("openai")] == ["gpt-6.2-astra", "gpt-6.2-sol", "gpt-6.1-terra", "gpt-6-luna"]
    for provider in ("anthropic", "openai"):
        assert all(m.get("reasoning") is True for m in load_curated(provider)), provider


def test_every_curated_native_model_has_a_real_window_and_price() -> None:
    import litellm

    from alpi.providers.curated import load_curated

    for provider in ("anthropic", "openai"):
        for entry in load_curated(provider):
            info = litellm.model_cost.get(entry["id"])
            assert info, entry["id"]
            assert info.get("max_input_tokens", 0) >= 200_000, entry["id"]
            assert info.get("input_cost_per_token", 0) > 0, entry["id"]


def test_every_curated_openrouter_model_is_in_the_openrouter_window_table() -> None:
    from pathlib import Path

    import yaml

    from alpi.providers.curated import load_curated

    table = yaml.safe_load((Path(__file__).resolve().parents[2] / "alpi" / "providers" / "openrouter_models.yaml").read_text())
    for entry in load_curated("openrouter"):
        assert entry["id"] in table, entry["id"]


def test_every_curated_native_model_is_in_alpi_native_catalogue() -> None:
    from alpi.providers.curated import load_curated
    from alpi.providers.native import catalogue

    native = catalogue()
    for provider in ("openai", "anthropic"):
        for entry in load_curated(provider):
            info = native.get(entry["id"])
            assert info, entry["id"]
            assert info["max_input_tokens"] >= 200_000 and info["input_cost_per_token"] > 0, entry["id"]
            assert "supports_vision" in info, entry["id"]


def test_the_native_catalogue_fills_only_what_litellm_lacks() -> None:
    from alpi.providers import native

    class Fake:
        model_cost = {"claude-opus-5-5": {"max_input_tokens": 1}}
        registered: dict = {}

        def register_model(self, models):
            self.registered.update(models)

    fake = Fake()
    added = native.register(fake)
    assert "claude-opus-5-5" not in added and "claude-opus-5-5" not in fake.registered
    assert "claude-sonnet-5-5" in added and fake.registered["claude-sonnet-5-5"]["max_input_tokens"] >= 200_000
