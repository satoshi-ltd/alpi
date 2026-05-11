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

            self._model = TextEmbedding(model_name=self.name)
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


def ensure_weights_cached() -> None:
    """Pre-download embedder weights to the fastembed cache.

    Instantiating ``TextEmbedding`` downloads the ONNX model files but
    keeps the in-memory footprint tiny (~100 MB for the ONNX session)
    compared to the torch-based variant (~600 MB). Pre-warming this
    from the daemon makes the first ``search_workspace`` instant.
    """
    log.info("ensure_weights_cached: %s", default().name)
    default()._load()
