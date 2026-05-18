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


def test_telegram_token_owner_finds_duplicate_across_profiles(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("TELEGRAM_BOT_TOKEN=botA\n")
    (tmp_path / "profiles" / "doc").mkdir(parents=True)
    (tmp_path / "profiles" / "doc" / ".env").write_text("TELEGRAM_BOT_TOKEN=botB\n")
    (tmp_path / "profiles" / "teacher").mkdir(parents=True)

    # Teacher tries to use botA → already owned by default.
    assert home.telegram_token_owner(
        "botA", exclude=tmp_path / "profiles" / "teacher", root=tmp_path,
    ) == "default"

    # Default rewriting its own token is allowed.
    assert home.telegram_token_owner("botA", exclude=tmp_path, root=tmp_path) is None

    # Doc rewriting its own token is allowed.
    assert home.telegram_token_owner(
        "botB", exclude=tmp_path / "profiles" / "doc", root=tmp_path,
    ) is None

    # Unique token has no owner.
    assert home.telegram_token_owner("brand-new", root=tmp_path) is None

    # Empty token is never owned.
    assert home.telegram_token_owner("", root=tmp_path) is None


def test_read_profile_env_strips_quotes_and_skips_comments(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text(
        "# header comment\n"
        "PLAIN=abc\n"
        'DOUBLE="quoted-value"\n'
        "SINGLE='other'\n"
        "  PADDED  =   spaced   \n"
        "EMPTY=\n"
        "no_equals_line\n"
    )
    env = home.read_profile_env(tmp_path)
    assert env["PLAIN"] == "abc"
    assert env["DOUBLE"] == "quoted-value"
    assert env["SINGLE"] == "other"
    assert env["PADDED"] == "spaced"
    assert env["EMPTY"] == ""
    assert "no_equals_line" not in env


def test_telegram_token_owner_matches_quoted_token(tmp_path: Path) -> None:
    # If a profile stores the token quoted, the duplicate check must still see it.
    (tmp_path / ".env").write_text('TELEGRAM_BOT_TOKEN="bot-quoted"\n')
    (tmp_path / "profiles" / "teacher").mkdir(parents=True)
    assert home.telegram_token_owner(
        "bot-quoted", exclude=tmp_path / "profiles" / "teacher", root=tmp_path,
    ) == "default"


def test_read_profile_env_missing_file_returns_empty(tmp_path: Path) -> None:
    assert home.read_profile_env(tmp_path) == {}
