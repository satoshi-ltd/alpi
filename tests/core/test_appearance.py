from __future__ import annotations

import re
from pathlib import Path

import pytest

from alpi import appearance, config, palette
from alpi.tui import commands

REPO = Path(__file__).resolve().parents[2]


def test_the_console_palette_is_the_one_the_apps_ship() -> None:
    shipped = re.findall(r'\["(\w+)", "(#[0-9a-f]{6})"\]', (REPO / "common" / "accents.mjs").read_text())
    assert list(appearance.ACCENTS) == shipped


def test_parse_reads_an_object_a_colour_or_both_in_any_order() -> None:
    assert appearance.parse("shield") == ("shield", None)
    assert appearance.parse("blue") == (None, "#3899e2")
    assert appearance.parse("Teal, Rocket") == ("rocket", "#2cb3b5")
    assert appearance.parse("tree #ABCDEF") == ("tree", "#abcdef")
    with pytest.raises(ValueError, match="pencil"):
        appearance.parse("pencil")


def test_apply_saves_the_pair_and_names_it(tmp_path: Path) -> None:
    home = tmp_path / "profiles" / "h"
    home.mkdir(parents=True)
    assert appearance.apply(home, "shield", "#3899e2") == "blue shield"
    saved = config.load(home).tui
    assert saved["fold"] == "shield" and saved["accent"] == "#3899e2"
    assert appearance.apply(home, fold="heart") == "blue heart"
    assert config.load(home).tui["accent"] == "#3899e2"
    with pytest.raises(ValueError):
        appearance.apply(home, fold="pencil")
    assert config.load(home).tui["fold"] == "heart"


def test_an_untouched_profile_is_an_amber_diamond() -> None:
    assert appearance.pair_name({}) == "amber diamond"
    assert appearance.pair_name({"accent": "#123456", "fold": "pencil"}) == "diamond #123456"


def test_the_tui_offers_fold_and_the_setup_menu_lists_appearance(tmp_path: Path) -> None:
    command = commands.lookup("fold")
    assert command is not None and command.method == "_cmd_fold" and command.usage == "[object] [colour]"
    assert [c.name for c in commands.complete("/fo")] == ["fold"]
    from alpi import cli

    (tmp_path / "profiles" / "h").mkdir(parents=True)
    assert cli._appearance_status(config.load(tmp_path / "profiles" / "h")) == "amber diamond"


def test_the_default_profile_is_the_alpaca_and_cannot_be_restyled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "root"
    root.mkdir()
    assert appearance.is_default(root) and not appearance.is_default(root / "profiles" / "doc")
    with pytest.raises(ValueError, match="alpaca"):
        appearance.apply(root, "shield", "#3899e2")
    assert not (root / "config.yaml").exists()
    assert appearance.pair_name({"fold": "shield"}, root) == "alpaca (brand accent)"
    from alpi import cli, ui

    assert cli._appearance_status(config.load(root)) == "alpaca (brand accent)"
    said: list[str] = []
    monkeypatch.setattr(ui, "ok_and_wait", said.append)
    cli._appearance_setup(root)
    assert said == [appearance.LOCKED_MESSAGE]


def test_every_colour_is_a_hue_and_folds_into_its_object_as_the_apps_ship() -> None:
    shipped = dict(re.findall(r'(\w+): "(\w+)"', re.search(r"ACCENT_FOLDS = \{([^}]*)\}", (REPO / "common" / "accents.mjs").read_text()).group(1)))
    assert appearance.FOLD_OF == shipped
    assert sorted(appearance.ROULETTE) == sorted(name for name, _ in appearance.ACCENTS)
    assert "graphite" not in dict(appearance.ACCENTS)


def _create(root: Path, name: str) -> dict:
    home = root / "profiles" / name
    home.mkdir(parents=True)
    config.seed_defaults(home)
    return config.load(home).tui


def test_new_profiles_take_the_next_colour_of_the_roulette_without_repeating(tmp_path: Path) -> None:
    worn = [_create(tmp_path, f"p{i}") for i in range(len(appearance.ROULETTE))]
    assert [appearance.accent_name(t["accent"]) for t in worn] == list(appearance.ROULETTE)
    assert all(t["fold"] == appearance.FOLD_OF[appearance.accent_name(t["accent"])] for t in worn)
    assert all(t["show_cost"] is True and t["theme"] == "dark" for t in worn)
    assert appearance.accent_name(_create(tmp_path, "again")["accent"]) == appearance.ROULETTE[0]


def test_the_roulette_reuses_a_colour_freed_by_a_deleted_or_restyled_profile(tmp_path: Path) -> None:
    for name in ("a", "b", "c"):
        _create(tmp_path, name)
    appearance.apply(tmp_path / "profiles" / "b", "rocket", "#2cb3b5")
    assert appearance.accent_name(_create(tmp_path, "d")["accent"]) == "blue"


def test_the_default_home_and_a_retired_grey_never_take_a_turn(tmp_path: Path) -> None:
    config.seed_defaults(tmp_path)
    assert "tui" not in config.seed_config_for(tmp_path)
    old = tmp_path / "profiles" / "old"
    old.mkdir(parents=True)
    (old / "config.yaml").write_text("tui:\n  accent: '#7e8792'\n  fold: box\n")
    assert palette.profile_accent({"accent": "#7e8792"}) == "#3ac9f3"
    assert appearance.next_pair(tmp_path / "profiles") == {"fold": "diamond", "accent": "#f0b447"}
    for name in appearance.ROULETTE[:-1]:
        _create(tmp_path, name + "-p")
    assert appearance.next_pair(tmp_path / "profiles")["accent"] == "#f0b447"
