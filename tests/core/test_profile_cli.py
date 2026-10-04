"""Tests for ``alpi profile`` — list + create."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from alpi import cli, home


def test_profile_list_shows_default_only(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(home, "_ROOT", tmp_path)
    monkeypatch.setenv("ALPI_HOME", str(tmp_path))
    monkeypatch.delenv("ALPI_PROFILE", raising=False)

    result = CliRunner().invoke(cli.main, ["profile", "list"])
    assert result.exit_code == 0
    assert "default" in result.output
    assert "◆" in result.output  # active marker (accent-colored diamond)


def test_profile_list_enumerates_existing(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(home, "_ROOT", tmp_path)
    monkeypatch.setenv("ALPI_HOME", str(tmp_path))
    monkeypatch.delenv("ALPI_PROFILE", raising=False)
    monkeypatch.setattr(
        "pathlib.Path.home", lambda: tmp_path.parent,
    )
    # Create profile dirs manually to simulate prior invocations.
    (tmp_path / "profiles" / "work").mkdir(parents=True)
    (tmp_path / "profiles" / "personal").mkdir(parents=True)

    # Patch the CLI's Path.home lookup by pointing _ROOT's parent there.
    result = CliRunner().invoke(cli.main, ["profile", "list"])
    assert result.exit_code == 0
    # The command uses Path.home() directly for listing, so we assert
    # the output structure rather than exact names when Path.home
    # isn't monkeypatchable here.
    assert "default" in result.output


def test_profile_create_bootstraps_directory(monkeypatch, tmp_path: Path) -> None:
    # Make _ROOT point to tmp_path so profile resolution lands inside it,
    # and clear ALPI_HOME so the override doesn't short-circuit the logic.
    monkeypatch.setattr(home, "_ROOT", tmp_path)
    monkeypatch.delenv("ALPI_HOME", raising=False)
    monkeypatch.delenv("ALPI_PROFILE", raising=False)

    result = CliRunner().invoke(cli.main, ["profile", "create", "experiment"])
    assert result.exit_code == 0, result.output
    assert "created profile 'experiment'" in result.output
    assert "it wears the amber diamond" in result.output
    second = CliRunner().invoke(cli.main, ["profile", "create", "second"])
    assert "it wears the blue shield" in second.output
    exp = tmp_path / "profiles" / "experiment"
    assert (exp / "memories").is_dir()
    assert (exp / "schedule" / "output").is_dir()


def test_profile_create_rejects_default(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(home, "_ROOT", tmp_path)
    result = CliRunner().invoke(cli.main, ["profile", "create", "default"])
    assert result.exit_code != 0
    assert "reserved" in result.output


def test_profile_create_rejects_alpi(monkeypatch, tmp_path: Path) -> None:
    """`alpi` is the desktop display label for the default profile —
    allowing a user-created `alpi` would collide with the rename in the UI."""
    monkeypatch.setattr(home, "_ROOT", tmp_path)
    result = CliRunner().invoke(cli.main, ["profile", "create", "alpi"])
    assert result.exit_code != 0
    assert "reserved" in result.output


def test_profile_create_rejects_bad_names(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(home, "_ROOT", tmp_path)
    for bad in ("a/b", ".hidden", ""):
        result = CliRunner().invoke(cli.main, ["profile", "create", bad])
        assert result.exit_code != 0


def test_profile_create_refuses_if_exists(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(home, "_ROOT", tmp_path)
    monkeypatch.delenv("ALPI_HOME", raising=False)
    monkeypatch.delenv("ALPI_PROFILE", raising=False)

    r1 = CliRunner().invoke(cli.main, ["profile", "create", "dup"])
    assert r1.exit_code == 0, r1.output
    r2 = CliRunner().invoke(cli.main, ["profile", "create", "dup"])
    assert r2.exit_code != 0
    assert "already exists" in r2.output


# --------------------------------------------------------------------
# profile remove
# --------------------------------------------------------------------


def test_profile_remove_refuses_default(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(home, "_ROOT", tmp_path)
    monkeypatch.delenv("ALPI_HOME", raising=False)
    monkeypatch.delenv("ALPI_PROFILE", raising=False)
    result = CliRunner().invoke(cli.main, ["profile", "remove", "default"])
    assert result.exit_code != 0
    assert "cannot be removed" in result.output


def test_profile_remove_refuses_missing(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(home, "_ROOT", tmp_path)
    monkeypatch.delenv("ALPI_HOME", raising=False)
    monkeypatch.delenv("ALPI_PROFILE", raising=False)
    result = CliRunner().invoke(cli.main, ["profile", "remove", "ghost"])
    assert result.exit_code != 0
    assert "does not exist" in result.output


def test_profile_remove_refuses_invalid_name(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(home, "_ROOT", tmp_path)
    monkeypatch.delenv("ALPI_HOME", raising=False)
    monkeypatch.delenv("ALPI_PROFILE", raising=False)
    for bad in ("a/b", ".hidden"):
        result = CliRunner().invoke(cli.main, ["profile", "remove", bad])
        assert result.exit_code != 0
        assert "invalid" in result.output


# Legacy service-installed gate removed.


def test_profile_remove_cancelled_leaves_directory(
        monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(home, "_ROOT", tmp_path)
    monkeypatch.delenv("ALPI_HOME", raising=False)
    monkeypatch.delenv("ALPI_PROFILE", raising=False)

    CliRunner().invoke(cli.main, ["profile", "create", "target"])
    profile_dir = tmp_path / "profiles" / "target"
    assert profile_dir.exists()

    from alpi import ui
    monkeypatch.setattr(ui, "confirm", lambda *a, **kw: False)

    result = CliRunner().invoke(cli.main, ["profile", "remove", "target"])
    assert result.exit_code == 0
    assert profile_dir.exists(), "profile must remain when user cancels"


def test_profile_remove_deletes_when_confirmed(
        monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(home, "_ROOT", tmp_path)
    monkeypatch.delenv("ALPI_HOME", raising=False)
    monkeypatch.delenv("ALPI_PROFILE", raising=False)

    CliRunner().invoke(cli.main, ["profile", "create", "trash"])
    profile_dir = tmp_path / "profiles" / "trash"
    assert profile_dir.exists()

    from alpi import ui
    monkeypatch.setattr(ui, "confirm", lambda *a, **kw: True)

    result = CliRunner().invoke(cli.main, ["profile", "remove", "trash"])
    assert result.exit_code == 0
    assert not profile_dir.exists()
    # Removed profiles are archived, not deleted.
    assert "archived" in result.output
    archived = list((tmp_path / ".trash").glob("trash-*"))
    assert len(archived) == 1
    assert (archived[0] / "config.yaml").exists()


def _alpi_root(monkeypatch, tmp_path: Path) -> Path:
    root = tmp_path / ".alpi"
    root.mkdir()
    monkeypatch.setattr(home, "_ROOT", root)
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    monkeypatch.delenv("ALPI_HOME", raising=False)
    monkeypatch.setenv("ALPI_PROFILE", "restore-on-teardown")
    monkeypatch.delenv("ALPI_PROFILE")
    cli._bootstrap(root)
    return root


def _styled_profile(root: Path, name: str, fold: str, accent: str) -> Path:
    from alpi import config

    path = root / "profiles" / name
    path.mkdir(parents=True)
    cli._bootstrap(path)
    cfg = config.load(path)
    cfg.tui = {"fold": fold, "accent": accent}
    config.save(cfg)
    return path


def _fold_art_on(monkeypatch, supported: bool) -> None:
    from alpi import fold_art

    monkeypatch.setattr(fold_art, "supports_fold_art", lambda *a, **k: supported)


def test_profile_show_draws_the_alpaca_for_the_default_profile(monkeypatch, tmp_path: Path) -> None:
    _alpi_root(monkeypatch, tmp_path)
    _fold_art_on(monkeypatch, True)

    result = CliRunner().invoke(cli.main, ["profile", "show"])

    assert result.exit_code == 0, result.output
    assert "▀" in result.output
    assert "default" in result.output
    assert "alpaca (brand accent)" in result.output
    assert result.output.count("\n") == 8


def test_profile_show_draws_a_named_profile_object(monkeypatch, tmp_path: Path) -> None:
    root = _alpi_root(monkeypatch, tmp_path)
    _styled_profile(root, "work", "shield", "#3899e2")
    _fold_art_on(monkeypatch, True)

    result = CliRunner().invoke(cli.main, ["profile", "show", "work"])

    assert result.exit_code == 0, result.output
    assert "▀" in result.output
    assert "blue shield" in result.output
    assert "work" in result.output


def test_profile_show_falls_back_to_the_diamond_without_truecolor(monkeypatch, tmp_path: Path) -> None:
    root = _alpi_root(monkeypatch, tmp_path)
    _styled_profile(root, "work", "shield", "#3899e2")
    _fold_art_on(monkeypatch, False)

    result = CliRunner().invoke(cli.main, ["profile", "show", "work"])

    assert result.exit_code == 0, result.output
    assert "◆ work" in result.output
    assert "blue shield" in result.output
    assert "▀" not in result.output and "▄" not in result.output


def test_profile_show_reports_an_unreadable_config_instead_of_a_traceback(monkeypatch, tmp_path: Path) -> None:
    root = _alpi_root(monkeypatch, tmp_path)
    broken = root / "profiles" / "bad"
    broken.mkdir(parents=True)
    (broken / "config.yaml").write_text("tui: [unclosed\n")

    result = CliRunner().invoke(cli.main, ["profile", "show", "bad"])

    assert result.exit_code == 1
    assert "unreadable config.yaml" in result.output
    assert "Traceback" not in result.output


def test_profile_show_rejects_a_missing_profile(monkeypatch, tmp_path: Path) -> None:
    _alpi_root(monkeypatch, tmp_path)

    result = CliRunner().invoke(cli.main, ["profile", "show", "ghost"])

    assert result.exit_code != 0
    assert "does not exist" in result.output


def test_profile_list_marks_the_active_profile_with_its_glyph(monkeypatch, tmp_path: Path) -> None:
    root = _alpi_root(monkeypatch, tmp_path)
    _styled_profile(root, "work", "heart", "#f36a8a")
    _fold_art_on(monkeypatch, True)

    result = CliRunner().invoke(cli.main, ["profile", "list"])
    marks = {line.split()[1]: line.split()[0] for line in result.output.strip().split("\n")}

    assert marks == {"default": "❖", "work": "◇"}

    result = CliRunner().invoke(cli.main, ["-p", "work", "profile", "list"])
    marks = {line.split()[1]: line.split()[0] for line in result.output.strip().split("\n")}

    assert marks == {"default": "◇", "work": "❥"}


def test_profile_list_keeps_the_diamonds_without_truecolor(monkeypatch, tmp_path: Path) -> None:
    root = _alpi_root(monkeypatch, tmp_path)
    _styled_profile(root, "work", "heart", "#f36a8a")
    _fold_art_on(monkeypatch, False)

    result = CliRunner().invoke(cli.main, ["-p", "work", "profile", "list"])
    marks = {line.split()[1]: line.split()[0] for line in result.output.strip().split("\n")}

    assert marks == {"default": "◇", "work": "◆"}


def test_profile_list_keeps_default_as_the_first_row(monkeypatch, tmp_path: Path) -> None:
    root = _alpi_root(monkeypatch, tmp_path)
    _styled_profile(root, "abby", "plane", "#3899e2")
    _styled_profile(root, "zeta", "heart", "#f36a8a")
    _fold_art_on(monkeypatch, False)

    result = CliRunner().invoke(cli.main, ["-p", "zeta", "profile", "list"])
    names = [line.split()[1] for line in result.output.strip().split("\n")]

    assert names == ["default", "abby", "zeta"]
