"""Embedding backend for local RAG.

Default: ``fastembed`` running the ONNX export of
``sentence-transformers/all-MiniLM-L6-v2`` (384-dim, ~90 MB). Numerically
equivalent to the original sentence-transformers checkpoint, ~10×
lighter at runtime (no torch). The model is loaded lazily so importing
this module costs nothing until the first ``embed()`` call. Tests
override via ``set_default()``.
"""

from __future__ import annotations

import logging
import threading
from typing import Protocol

log = logging.getLogger(__name__)


class Embedder(Protocol):
    name: str
    dim: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class FastembedEmbedder:
    name = "sentence-transformers/all-MiniLM-L6-v2"
    dim = 384

    def __init__(
        self,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
    ) -> None:
        self.name = model_name
        self._model = None
        self._lock = threading.Lock()

    def _load(self):
        if self._model is not None:
            return self._model
        with self._lock:
            if self._model is not None:
                return self._model
            from fastembed import TextEmbedding
            from alpi import home as home_mod

            # Persistent + backup-excluded (cache/ is in alpi.backup._EXCLUDE_DIRS).
            cache = home_mod.alpi_root() / "cache" / "fastembed"
            cache.mkdir(parents=True, exist_ok=True)
            self._model = TextEmbedding(model_name=self.name, cache_dir=str(cache))
            return self._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        model = self._load()
        vectors = list(model.embed(texts))
        return [v.tolist() for v in vectors]


_DEFAULT: Embedder | None = None


def default() -> Embedder:
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = FastembedEmbedder()
    return _DEFAULT


def set_default(embedder: Embedder | None) -> None:
    global _DEFAULT
    _DEFAULT = embedder


# Throwaway instance on purpose: priming _DEFAULT would park the ONNX session (~150MB RSS) in every daemon forever — here the weights land on disk, the session is released, and the first real embed() lazy-loads from cache.
def ensure_weights_cached() -> None:
    embedder = FastembedEmbedder()
    log.info("ensure_weights_cached: %s", embedder.name)
    embedder._load()
    embedder._model = None
