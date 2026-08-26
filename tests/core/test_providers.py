from __future__ import annotations

import importlib
from pathlib import Path

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


def test_google_list_models_is_static() -> None:
    provider = google.Google()
    models = provider.list_models()
    assert [m.id for m in models] == [
        "gemini/gemini-2.5-pro",
        "gemini/gemini-2.5-flash",
        "gemini/gemini-2.0-flash",
    ]


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


def test_openrouter_curated_uses_current_deepseek_flash_alias() -> None:
    ids = {row["id"] for row in curated.load_curated("openrouter")}
    assert "~deepseek/deepseek-v4-flash-latest" in ids
    assert "deepseek/deepseek-v4-flash-0731" not in ids


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


def test_ollama_is_ollama_and_resolve_num_ctx(monkeypatch) -> None:
    fake = _FakeClient(
        tags={"models": [{"name": "llama3"}]},
        show={"parameters": "num_ctx 8192\n"},
    )
    monkeypatch.setattr(ollama.httpx, "Client", lambda timeout=0: fake)
    ollama._IS_OLLAMA_CACHE.clear()
    ollama._NUM_CTX_CACHE.clear()

    assert ollama.is_ollama("http://localhost:11434/v1") is True
    assert ollama.resolve_num_ctx("http://localhost:11434/v1", "llama3") == 8192


def test_ollama_is_ollama_fail_open(monkeypatch) -> None:
    fake = _FakeClient(fail=True)
    monkeypatch.setattr(ollama.httpx, "Client", lambda timeout=0: fake)
    ollama._IS_OLLAMA_CACHE.clear()

    assert ollama.is_ollama("http://localhost:11434") is False
