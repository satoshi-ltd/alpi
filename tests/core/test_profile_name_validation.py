from pathlib import Path

import pytest

from alpi import home as home_mod
from alpi.home import InvalidProfileName, validate_profile_name


VALID = ["work", "personal", "build.debug", "a1", "abc-xyz", "A", "0", "abc.123", "a_b"]
INVALID = [
    "../escape", "..", ".", ".hidden", "a/b", "a\\b", "/abs", "\\abs",
    "../../etc", "name with space", "name\twith\ttab", "name\nwith\nnl",
    "-leading-dash", ".leading", "", "..foo", "foo/..", "foo/../bar",
]
RESERVED = ["alpi"]


@pytest.mark.parametrize("name", VALID)
def test_validate_accepts_safe_names(name: str) -> None:
    assert validate_profile_name(name) == name


@pytest.mark.parametrize("name", INVALID)
def test_validate_rejects_unsafe_names(name: str) -> None:
    with pytest.raises(InvalidProfileName):
        validate_profile_name(name)


@pytest.mark.parametrize("name", ["default", "alpi"])
def test_validate_rejects_reserved_aliases(name: str) -> None:
    with pytest.raises(InvalidProfileName, match="reserved"):
        validate_profile_name(name)


def test_get_home_rejects_alpi_alias_via_flag(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(home_mod, "_ROOT", tmp_path)
    monkeypatch.delenv("ALPI_HOME", raising=False)
    monkeypatch.delenv("ALPI_PROFILE", raising=False)
    with pytest.raises(InvalidProfileName):
        home_mod.get_home("alpi")


def test_cli_flag_rejects_alpi_alias(monkeypatch, tmp_path: Path) -> None:
    from click.testing import CliRunner
    from alpi.cli import main

    monkeypatch.setattr(home_mod, "_ROOT", tmp_path)
    monkeypatch.delenv("ALPI_HOME", raising=False)
    monkeypatch.delenv("ALPI_PROFILE", raising=False)

    runner = CliRunner()
    result = runner.invoke(main, ["-p", "alpi", "profile", "list"])
    assert result.exit_code != 0
    assert "reserved" in result.output.lower()


@pytest.mark.parametrize("name", ["../escape", "a/b", ".hidden", "..", ""])
def test_get_home_rejects_traversal_via_flag(monkeypatch, tmp_path: Path, name: str) -> None:
    monkeypatch.setattr(home_mod, "_ROOT", tmp_path)
    monkeypatch.delenv("ALPI_HOME", raising=False)
    monkeypatch.delenv("ALPI_PROFILE", raising=False)
    if name == "":
        assert home_mod.get_home(name) == tmp_path
        return
    with pytest.raises(InvalidProfileName):
        home_mod.get_home(name)


@pytest.mark.parametrize("name", ["../escape", "a/b", ".hidden", ".."])
def test_get_home_rejects_traversal_via_env(monkeypatch, tmp_path: Path, name: str) -> None:
    monkeypatch.setattr(home_mod, "_ROOT", tmp_path)
    monkeypatch.delenv("ALPI_HOME", raising=False)
    monkeypatch.setenv("ALPI_PROFILE", name)
    with pytest.raises(InvalidProfileName):
        home_mod.get_home(None)


def test_home_for_rejects_traversal(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(home_mod, "_ROOT", tmp_path)
    with pytest.raises(InvalidProfileName):
        home_mod.home_for("../escape")
    with pytest.raises(InvalidProfileName):
        home_mod.home_for("a/b")


def test_get_home_accepts_valid_name(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(home_mod, "_ROOT", tmp_path)
    monkeypatch.delenv("ALPI_HOME", raising=False)
    monkeypatch.delenv("ALPI_PROFILE", raising=False)
    assert home_mod.get_home("work") == tmp_path / "profiles" / "work"


def test_get_home_default_keyword_returns_root(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(home_mod, "_ROOT", tmp_path)
    monkeypatch.delenv("ALPI_HOME", raising=False)
    monkeypatch.delenv("ALPI_PROFILE", raising=False)
    assert home_mod.get_home("default") == tmp_path


def test_cli_flag_rejects_traversal(monkeypatch, tmp_path: Path) -> None:
    from click.testing import CliRunner
    from alpi.cli import main

    monkeypatch.setattr(home_mod, "_ROOT", tmp_path)
    monkeypatch.delenv("ALPI_HOME", raising=False)
    monkeypatch.delenv("ALPI_PROFILE", raising=False)

    runner = CliRunner()
    result = runner.invoke(main, ["-p", "../escape", "profile", "list"])
    assert result.exit_code != 0
    assert "invalid profile name" in result.output.lower()
