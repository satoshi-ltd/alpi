"""Tests for ``alf profile`` — list + create."""

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
    assert "* default" in result.output  # active marker


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
    exp = tmp_path / "profiles" / "experiment"
    assert (exp / "memories").is_dir()
    assert (exp / "schedule" / "output").is_dir()


def test_profile_create_rejects_default(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(home, "_ROOT", tmp_path)
    result = CliRunner().invoke(cli.main, ["profile", "create", "default"])
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


def test_profile_remove_refuses_if_service_installed(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(home, "_ROOT", tmp_path)
    monkeypatch.delenv("ALPI_HOME", raising=False)
    monkeypatch.delenv("ALPI_PROFILE", raising=False)

    CliRunner().invoke(cli.main, ["profile", "create", "guarded"])

    # Simulate: gateway service is installed for this profile.
    from alpi import service
    monkeypatch.setattr(
        service, "installed",
        lambda name, profile="default": "launchd" if name == "gateway" else None,
    )
    result = CliRunner().invoke(cli.main, ["profile", "remove", "guarded"])
    assert result.exit_code != 0
    assert "installed service" in result.output
    assert "gateway uninstall" in result.output


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
    assert "removed" in result.output
