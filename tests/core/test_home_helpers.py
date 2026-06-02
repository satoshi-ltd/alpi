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


def test_effective_profile_env_profile_overlays_base(tmp_path: Path) -> None:
    """Daemon supervises many profiles in one process — each effective env must layer profile .env over a clean base so process-level vars (PATH) survive while per-profile secrets win on collision."""
    (tmp_path / ".env").write_text("OPENAI_API_KEY=from-profile\nALPI_TEST_X=yes\n")
    base = {"PATH": "/usr/bin", "OPENAI_API_KEY": "from-base"}

    env = home.effective_profile_env(tmp_path, base=base)

    assert env["PATH"].split(":")[-1] == "/usr/bin"  # base passes through (node bins may prepend)
    assert env["OPENAI_API_KEY"] == "from-profile"  # profile wins
    assert env["ALPI_TEST_X"] == "yes"


def test_effective_profile_env_extra_overrides_everything(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("ALPI_X=from-profile\n")
    env = home.effective_profile_env(
        tmp_path,
        base={"ALPI_X": "from-base"},
        extra={"ALPI_X": "from-extra", "ALPI_PLATFORM": "telegram"},
    )
    assert env["ALPI_X"] == "from-extra"
    assert env["ALPI_PLATFORM"] == "telegram"


def test_effective_profile_env_does_not_mutate_base(tmp_path: Path) -> None:
    """The returned dict must be a fresh copy — mutating it (e.g. setting ALPI_SKILL_NAME for one subprocess) must not leak into the next profile's effective env."""
    (tmp_path / ".env").write_text("FOO=bar\n")
    base = {"PATH": "/usr/bin"}
    env = home.effective_profile_env(tmp_path, base=base)
    env["ALPI_LEAK"] = "yes"
    assert "ALPI_LEAK" not in base


def test_find_home_by_pubkey_does_not_generate_missing_keys(
    tmp_path: Path,
) -> None:
    # Lookup must not load_or_generate — would surface ALP secrets from a read.
    from alpi.alp import keys as keys_mod

    root = tmp_path / ".alpi"
    root.mkdir()
    initialised = root / "profiles" / "real"
    initialised.mkdir(parents=True)
    uninitialised = root / "profiles" / "empty"
    uninitialised.mkdir(parents=True)
    target_kp = keys_mod.generate(initialised)

    found = home.find_home_by_pubkey(target_kp.pubkey_b64(), root=root)
    assert found == initialised
    assert not keys_mod.exists(uninitialised)
    assert not keys_mod.exists(root)

    missing = home.find_home_by_pubkey("NOT_A_REAL_PUBKEY", root=root)
    assert missing is None
    assert not keys_mod.exists(uninitialised)
    assert not keys_mod.exists(root)


def test_effective_profile_env_two_profiles_isolated(tmp_path: Path) -> None:
    a = tmp_path / "a"; a.mkdir()
    b = tmp_path / "b"; b.mkdir()
    (a / ".env").write_text("OPENAI_API_KEY=alice\n")
    (b / ".env").write_text("OPENAI_API_KEY=bob\n")
    base = {"PATH": "/usr/bin"}
    assert home.effective_profile_env(a, base=base)["OPENAI_API_KEY"] == "alice"
    assert home.effective_profile_env(b, base=base)["OPENAI_API_KEY"] == "bob"
