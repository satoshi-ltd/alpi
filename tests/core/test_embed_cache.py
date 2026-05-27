from __future__ import annotations

from pathlib import Path

from alpi.core import embed as embed_mod


def test_fastembed_cache_lands_under_alpi_root(tmp_path: Path, monkeypatch) -> None:
    # Container restart MUST re-use the model on /data, not re-download from HF.
    captured: dict = {}

    class FakeTextEmbedding:
        def __init__(self, model_name, cache_dir=None):
            captured["model_name"] = model_name
            captured["cache_dir"] = cache_dir

    monkeypatch.setattr("fastembed.TextEmbedding", FakeTextEmbedding)
    monkeypatch.setenv("ALPI_HOME", str(tmp_path))

    emb = embed_mod.FastembedEmbedder()
    emb._load()

    assert captured["cache_dir"] == str(tmp_path / "cache" / "fastembed")
    assert (tmp_path / "cache" / "fastembed").is_dir()


def test_fastembed_cache_excluded_from_backup() -> None:
    from alpi import backup
    assert "cache" in backup._EXCLUDE_DIRS
