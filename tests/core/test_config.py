from pathlib import Path

from alpi import config


def test_seed_writes_defaults(tmp_home_no_env: Path) -> None:
    config.seed_defaults(tmp_home_no_env)
    assert (tmp_home_no_env / "config.yaml").exists()
    # Wizards are the onboarding path now.
    assert not (tmp_home_no_env / ".env.example").exists()


def test_load_uses_defaults_when_fresh(tmp_home_no_env: Path) -> None:
    """Fresh scaffold ships with an empty model — the setup wizard is the
    canonical path to pick one. See docs/MODELS.md for recommendations."""
    config.seed_defaults(tmp_home_no_env)
    cfg = config.load(tmp_home_no_env)
    assert cfg.home == tmp_home_no_env
    assert cfg.model == ""


def test_tts_auto_read_roundtrips(tmp_home_no_env: Path) -> None:
    config.seed_defaults(tmp_home_no_env)
    cfg = config.load(tmp_home_no_env)
    assert cfg.tools.tts.auto_read is False
    cfg.tools.tts.auto_read = True
    config.save(cfg)
    assert config.load(tmp_home_no_env).tools.tts.auto_read is True


def test_save_roundtrips(tmp_home_no_env: Path) -> None:
    config.seed_defaults(tmp_home_no_env)
    cfg = config.load(tmp_home_no_env)
    cfg.model = "openai/gpt-4o"
    cfg.tools.web_extract.model = "openrouter/google/gemini-2.0-flash-exp:free"
    config.save(cfg)

    reloaded = config.load(tmp_home_no_env)
    assert reloaded.model == "openai/gpt-4o"
    assert reloaded.tools.web_extract.model.startswith("openrouter/google/gemini")


def test_save_keeps_email_accounts_dropping_unknown_keys(tmp_home_no_env: Path) -> None:
    """email.accounts persists per-account rows; unknown per-account keys are dropped."""
    import yaml
    (tmp_home_no_env / "config.yaml").write_text(yaml.safe_dump({
        "email": {
            "accounts": {
                "me_work_com": {
                    "type": "imap", "address": "me@work.com",
                    "imap_host": "imap.work.com", "imap_port": 993,
                    "smtp_host": "smtp.work.com", "smtp_port": 587,
                    "password": "leaked", "poll_interval": 90,
                },
                "me_gmail_com": {
                    "type": "gmail", "address": "me@gmail.com",
                    "client_secret": "leaked",
                },
            },
        },
    }))

    cfg = config.load(tmp_home_no_env)
    config.save(cfg)

    on_disk = yaml.safe_load((tmp_home_no_env / "config.yaml").read_text())
    imap = on_disk["email"]["accounts"]["me_work_com"]
    assert imap == {
        "type": "imap", "address": "me@work.com",
        "imap_host": "imap.work.com", "imap_port": 993,
        "smtp_host": "smtp.work.com", "smtp_port": 587,
    }
    gmail = on_disk["email"]["accounts"]["me_gmail_com"]
    assert gmail == {"type": "gmail", "address": "me@gmail.com"}


def test_save_preserves_approval_allowlist(tmp_home_no_env: Path) -> None:
    """Regression: pre-v0.4.35 config.save() silently dropped approval.allowlist."""
    import yaml
    (tmp_home_no_env / "config.yaml").write_text(yaml.safe_dump({
        "tools": {"terminal": {"approval": {"allowlist": [
            "recursive rm", "sudo apt *", "git reset --hard origin/main",
        ]}}},
    }))

    cfg = config.load(tmp_home_no_env)
    assert cfg.tools.terminal.approval.allowlist == [
        "recursive rm", "sudo apt *", "git reset --hard origin/main",
    ]

    cfg.model = "openai/gpt-4o"
    config.save(cfg)

    reloaded = config.load(tmp_home_no_env)
    assert reloaded.model == "openai/gpt-4o"
    assert reloaded.tools.terminal.approval.allowlist == [
        "recursive rm", "sudo apt *", "git reset --hard origin/main",
    ]

    on_disk = yaml.safe_load((tmp_home_no_env / "config.yaml").read_text())
    assert on_disk["tools"]["terminal"]["approval"]["allowlist"] == [
        "recursive rm", "sudo apt *", "git reset --hard origin/main",
    ]


def test_tools_section_defaults(tmp_home_no_env: Path) -> None:
    config.seed_defaults(tmp_home_no_env)
    cfg = config.load(tmp_home_no_env)
    assert cfg.tools.web_extract.model == ""
    assert cfg.tools.max_steps_per_turn == 100
    assert cfg.tools.deny == []


def test_tools_deny_roundtrips(tmp_home_no_env: Path) -> None:
    import yaml
    (tmp_home_no_env / "config.yaml").write_text(yaml.safe_dump({
        "tools": {"deny": ["write_file", "terminal", "email"]},
    }))

    cfg = config.load(tmp_home_no_env)
    assert cfg.tools.deny == ["write_file", "terminal", "email"]

    cfg.model = "openai/gpt-4o"
    config.save(cfg)

    reloaded = config.load(tmp_home_no_env)
    assert reloaded.tools.deny == ["write_file", "terminal", "email"]

    on_disk = yaml.safe_load((tmp_home_no_env / "config.yaml").read_text())
    assert on_disk["tools"]["deny"] == ["write_file", "terminal", "email"]


def test_tools_deny_omitted_when_empty(tmp_home_no_env: Path) -> None:
    import yaml
    config.seed_defaults(tmp_home_no_env)
    cfg = config.load(tmp_home_no_env)
    cfg.model = "openai/gpt-4o"
    config.save(cfg)
    on_disk = yaml.safe_load((tmp_home_no_env / "config.yaml").read_text())
    assert "deny" not in (on_disk.get("tools") or {})


def test_tools_deny_string_does_not_iterate_chars(tmp_home_no_env: Path) -> None:
    """Hand-edit gotcha: ``deny: terminal`` (bare string) must collapse to ``[]``, not ``['t', 'e', 'r', ...]``."""
    import yaml
    (tmp_home_no_env / "config.yaml").write_text(yaml.safe_dump({
        "tools": {"deny": "terminal"},
    }))
    cfg = config.load(tmp_home_no_env)
    assert cfg.tools.deny == []


def test_tools_deny_strips_and_dedupes(tmp_home_no_env: Path) -> None:
    import yaml
    (tmp_home_no_env / "config.yaml").write_text(yaml.safe_dump({
        "tools": {"deny": [
            " write_file ", "terminal", "write_file", "", "  ", "email",
        ]},
    }))
    cfg = config.load(tmp_home_no_env)
    assert cfg.tools.deny == ["write_file", "terminal", "email"]


def test_resolve_model_plain() -> None:
    cfg = config.Config(
        home=Path("/tmp"),
        model="anthropic/claude-sonnet-4-6",
    )
    kwargs = config.resolve_model(cfg)
    assert kwargs == {"model": "anthropic/claude-sonnet-4-6"}


def test_resolve_model_ollama() -> None:
    cfg = config.Config(
        home=Path("/tmp"),
        model="home/llama3.1",
        providers={"ollama": [
            {"name": "home", "url": "http://localhost:11434"}
        ]},
    )
    kwargs = config.resolve_model(cfg)
    assert kwargs["model"] == "openai/llama3.1"
    assert kwargs["api_base"] == "http://localhost:11434/v1"
    assert kwargs["api_key"] == "dummy"


def test_resolve_model_reads_api_key_from_profile_env(tmp_path: Path, monkeypatch) -> None:
    """Cloud api keys live in <home>/.env and are bound per-call, never via os.environ.
    Regression: with `load_dotenv(override=True)` at config.load() the daemon would
    leak profile A's OPENAI_API_KEY into profile B's calls."""
    home_a = tmp_path / "a"; home_a.mkdir()
    home_b = tmp_path / "b"; home_b.mkdir()
    (home_a / ".env").write_text("OPENAI_API_KEY=A_KEY\n")
    # Profile B has no .env at all.

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    cfg_a = config.Config(home=home_a, model="openai/gpt-4o")
    cfg_b = config.Config(home=home_b, model="openai/gpt-4o")

    # Order matters: load A first, then resolve B. With the old global-env
    # behaviour, B would carry A's key.
    config.load(home_a)
    config.load(home_b)

    assert config.resolve_model(cfg_a)["api_key"] == "A_KEY"
    assert "api_key" not in config.resolve_model(cfg_b)
    # Also: config.load must NOT mutate os.environ.
    import os
    assert os.environ.get("OPENAI_API_KEY") is None


def test_resolve_model_profile_env_wins_over_os_environ(tmp_path: Path, monkeypatch) -> None:
    """Daemon-wide ALPI vars stay in os.environ, but per-provider keys
    must come from the profile's own .env when present."""
    home = tmp_path / "p"; home.mkdir()
    (home / ".env").write_text("ANTHROPIC_API_KEY=profile_key\n")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "global_leak")

    cfg = config.Config(home=home, model="anthropic/claude-sonnet-4-6")
    assert config.resolve_model(cfg)["api_key"] == "profile_key"


def test_paused_roundtrips(tmp_home_no_env: Path) -> None:
    config.seed_defaults(tmp_home_no_env)
    cfg = config.load(tmp_home_no_env)
    assert cfg.paused is False
    cfg.paused = True
    config.save(cfg)
    assert config.load(tmp_home_no_env).paused is True
