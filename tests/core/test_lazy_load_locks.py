"""Concurrency safety of the lazy loaders (embedder, OCR, chromium)."""

from __future__ import annotations

import threading

import pytest

from alpi.core import _playwright as pw_mod
from alpi.core import embed as embed_mod
from alpi.tools import workspace as ws


@pytest.fixture(autouse=True)
def _reset_global_state():
    pw_mod.reset_for_testing()
    yield
    pw_mod.reset_for_testing()
    ws._ocr_reader_cache = None


def _race(callable_, n=10):
    threads = [threading.Thread(target=callable_) for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()


def test_embedder_loads_once_under_concurrency(monkeypatch):
    calls = {"n": 0}

    class FakeTextEmbedding:
        def __init__(self, model_name, cache_dir=None):
            calls["n"] += 1
            calls["cache_dir"] = cache_dir

    monkeypatch.setattr("fastembed.TextEmbedding", FakeTextEmbedding)
    emb = embed_mod.FastembedEmbedder()
    _race(emb._load, n=10)
    assert calls["n"] == 1


def test_ocr_reader_loads_once_under_concurrency(monkeypatch):
    calls = {"n": 0}

    class FakeRapidOCR:
        def __init__(self, **kw):
            calls["n"] += 1

    monkeypatch.setattr(ws, "_ocr_reader_cache", None)
    monkeypatch.setattr("rapidocr_onnxruntime.RapidOCR", FakeRapidOCR)
    _race(ws._ocr_reader, n=10)
    assert calls["n"] == 1


def test_chromium_install_runs_once_under_concurrency(monkeypatch):
    pw_mod.reset_for_testing()
    calls = {"n": 0}

    def fake_run(*a, **kw):
        calls["n"] += 1

    monkeypatch.setattr("subprocess.run", fake_run)
    _race(pw_mod.ensure_chromium, n=10)
    assert calls["n"] == 1


def test_chromium_install_is_idempotent_after_success(monkeypatch):
    pw_mod.reset_for_testing()
    calls = {"n": 0}

    def fake_run(*a, **kw):
        calls["n"] += 1

    monkeypatch.setattr("subprocess.run", fake_run)
    pw_mod.ensure_chromium()
    pw_mod.ensure_chromium()
    pw_mod.ensure_chromium()
    assert calls["n"] == 1
