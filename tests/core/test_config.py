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


def test_save_roundtrips(tmp_home_no_env: Path) -> None:
    config.seed_defaults(tmp_home_no_env)
    cfg = config.load(tmp_home_no_env)
    cfg.model = "openai/gpt-4o"
    cfg.tools.web_extract.model = "openrouter/google/gemini-2.0-flash-exp:free"
    config.save(cfg)

    reloaded = config.load(tmp_home_no_env)
    assert reloaded.model == "openai/gpt-4o"
    assert reloaded.tools.web_extract.model.startswith("openrouter/google/gemini")


def test_tools_section_defaults(tmp_home_no_env: Path) -> None:
    config.seed_defaults(tmp_home_no_env)
    cfg = config.load(tmp_home_no_env)
    assert cfg.tools.web_extract.model == ""
    assert cfg.tools.max_steps_per_turn == 40


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
