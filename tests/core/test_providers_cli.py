"""``alpi providers add/remove-openrouter-model`` — used by the desktop
app to remember a model id alongside the OpenRouter API key."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from alpi import cli, config, home


def _setup_home(monkeypatch, tmp_path: Path) -> Path:
    monkeypatch.setattr(home, "_ROOT", tmp_path)
    monkeypatch.setenv("ALPI_HOME", str(tmp_path))
    return tmp_path


def test_add_openrouter_model_prepends_and_dedupes(monkeypatch, tmp_path: Path) -> None:
    h = _setup_home(monkeypatch, tmp_path)

    r1 = CliRunner().invoke(
        cli.main, ["providers", "add-openrouter-model", "anthropic/claude-3.5-sonnet"]
    )
    assert r1.exit_code == 0, r1.output

    r2 = CliRunner().invoke(
        cli.main, ["providers", "add-openrouter-model", "openai/gpt-4o-mini"]
    )
    assert r2.exit_code == 0, r2.output

    # Re-adding the first one moves it to the front (most-recent-first).
    r3 = CliRunner().invoke(
        cli.main, ["providers", "add-openrouter-model", "anthropic/claude-3.5-sonnet"]
    )
    assert r3.exit_code == 0, r3.output

    cfg = config.load(h)
    assert cfg.providers["openrouter"]["models"] == [
        "anthropic/claude-3.5-sonnet",
        "openai/gpt-4o-mini",
    ]


def test_add_openrouter_model_strips_prefix(monkeypatch, tmp_path: Path) -> None:
    h = _setup_home(monkeypatch, tmp_path)
    r = CliRunner().invoke(
        cli.main,
        ["providers", "add-openrouter-model", "openrouter/anthropic/claude-3.5-sonnet"],
    )
    assert r.exit_code == 0, r.output
    cfg = config.load(h)
    assert cfg.providers["openrouter"]["models"] == ["anthropic/claude-3.5-sonnet"]


def test_remove_openrouter_model(monkeypatch, tmp_path: Path) -> None:
    h = _setup_home(monkeypatch, tmp_path)
    CliRunner().invoke(cli.main, ["providers", "add-openrouter-model", "a/b"])
    CliRunner().invoke(cli.main, ["providers", "add-openrouter-model", "c/d"])

    r = CliRunner().invoke(cli.main, ["providers", "remove-openrouter-model", "a/b"])
    assert r.exit_code == 0, r.output
    cfg = config.load(h)
    assert cfg.providers["openrouter"]["models"] == ["c/d"]

    miss = CliRunner().invoke(
        cli.main, ["providers", "remove-openrouter-model", "nope/x"]
    )
    assert miss.exit_code != 0
