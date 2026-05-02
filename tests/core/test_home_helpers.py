"""Tests for helper functions in ``alpi.home``."""

from __future__ import annotations

from pathlib import Path

from alpi import home


def test_agent_path_points_to_memories_agent_md(tmp_path: Path) -> None:
    assert home.agent_path(tmp_path) == tmp_path / "memories" / "AGENT.md"


def test_format_bytes_uses_human_friendly_units() -> None:
    assert home.format_bytes(999) == "999B"
    assert home.format_bytes(1024) == "1KB"
    assert home.format_bytes(1024 * 1024) == "1.0MB"


def test_shorten_home_collapses_current_user_home(monkeypatch) -> None:
    fake_home = Path("/Users/javi")
    monkeypatch.setattr(home.Path, "home", staticmethod(lambda: fake_home))
    assert home.shorten_home(fake_home) == "~"
    assert home.shorten_home(fake_home / "git" / "alf") == "~/git/alf"


def test_profile_size_label_skips_profiles_dir(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(home, "_SIZE_CACHE", {})
    (tmp_path / "keep.txt").write_text("x" * 10)
    (tmp_path / "profiles").mkdir()
    (tmp_path / "profiles" / "ignored.txt").write_text("x" * 10_000)

    label = home.profile_size_label(tmp_path)

    assert label == "10B"
    assert home.profile_size_label(tmp_path) == "10B"
