from __future__ import annotations

from pathlib import Path

from alpi import service
from alpi.core import _playwright


def _root(tmp_path: Path, cfg_text: str = "model: x\n") -> Path:
    root = tmp_path / "root"
    root.mkdir()
    (root / "config.yaml").write_text(cfg_text)
    return root


def test_prefetch_mode_defaults_auto_outside_docker(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("ALPI_PLATFORM", raising=False)
    assert service._prefetch_mode(_root(tmp_path)) == "auto"


def test_prefetch_mode_defaults_off_in_docker(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ALPI_PLATFORM", "docker")
    assert service._prefetch_mode(_root(tmp_path)) == "off"


def test_prefetch_mode_explicit_config_beats_docker_default(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ALPI_PLATFORM", "docker")
    root = _root(tmp_path, "model: x\nservice:\n  prefetch: all\n")
    assert service._prefetch_mode(root) == "all"


def test_browser_gate_false_when_denied_everywhere(tmp_path) -> None:
    root = _root(tmp_path, "model: x\ntools:\n  deny:\n    - browser\n")
    prof = root / "profiles" / "p1"
    prof.mkdir(parents=True)
    (prof / "config.yaml").write_text("model: x\ntools:\n  deny:\n    - browser\n")
    assert service._any_profile_allows_browser(root) is False


def test_browser_gate_true_when_any_profile_allows(tmp_path) -> None:
    root = _root(tmp_path, "model: x\ntools:\n  deny:\n    - browser\n")
    prof = root / "profiles" / "open"
    prof.mkdir(parents=True)
    (prof / "config.yaml").write_text("model: x\n")
    assert service._any_profile_allows_browser(root) is True


def test_knowledge_index_gate_requires_store_file(tmp_path) -> None:
    root = _root(tmp_path)
    assert service._any_profile_uses_knowledge_index(root) is False
    (root / "knowledge").mkdir()
    assert service._any_profile_uses_knowledge_index(root) is False
    (root / "knowledge.sqlite").write_text("x")
    assert service._any_profile_uses_knowledge_index(root) is True


def test_prune_removes_only_stale_chromium(tmp_path, monkeypatch) -> None:
    cache = tmp_path / "ms-playwright"
    for name in (
        "chromium-1208", "chromium-1217",
        "chromium_headless_shell-1208", "chromium_headless_shell-1217",
        "firefox-1511",
    ):
        (cache / name).mkdir(parents=True)
    monkeypatch.setattr(
        _playwright, "_wanted_chromium_dirs",
        lambda: {"chromium-1217", "chromium_headless_shell-1217"},
    )
    removed = _playwright._prune_stale_chromium(cache)
    assert removed == 2
    assert (cache / "chromium-1217").is_dir()
    assert (cache / "chromium_headless_shell-1217").is_dir()
    assert (cache / "firefox-1511").is_dir()
    assert not (cache / "chromium-1208").exists()


def test_prune_refuses_when_wanted_build_missing(tmp_path, monkeypatch) -> None:
    cache = tmp_path / "ms-playwright"
    (cache / "chromium-1208").mkdir(parents=True)
    monkeypatch.setattr(_playwright, "_wanted_chromium_dirs", lambda: {"chromium-9999"})
    assert _playwright._prune_stale_chromium(cache) == 0
    assert (cache / "chromium-1208").is_dir()


def test_ensure_weights_cached_does_not_prime_the_global(monkeypatch) -> None:
    from alpi.core import embed

    embed.set_default(None)
    loaded = []
    monkeypatch.setattr(
        embed.FastembedEmbedder, "_load", lambda self: loaded.append(self) or object(),
    )
    embed.ensure_weights_cached()
    assert len(loaded) == 1
    assert embed._DEFAULT is None
