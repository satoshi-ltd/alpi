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


def test_parse_reads_a_shape_a_colour_or_both_in_any_order() -> None:
    assert appearance.parse("bell") == ("bell", None)
    assert appearance.parse("Pill teal") == ("pill", "#2cb3b5")
    assert appearance.parse("round") == ("round", None)
    assert appearance.parse("blue") == (None, "#3899e2")
    assert appearance.parse("Teal, Pill") == ("pill", "#2cb3b5")
    assert appearance.parse("pebble #ABCDEF") == ("pebble", "#abcdef")
    with pytest.raises(ValueError, match="pencil"):
        appearance.parse("pencil")


@pytest.mark.parametrize("legacy", ["shield", "rocket", "tree", "diamond", "alpaca"])
def test_parse_and_apply_refuse_a_legacy_fold_id(tmp_path: Path, legacy: str) -> None:
    with pytest.raises(ValueError, match=legacy):
        appearance.parse(f"{legacy} blue")
    home = tmp_path / "profiles" / "h"
    home.mkdir(parents=True)
    with pytest.raises(ValueError, match="shape must be one of"):
        appearance.apply(home, shape=legacy)
    assert not (home / "config.yaml").exists()


def test_apply_saves_the_pair_and_names_it(tmp_path: Path) -> None:
    home = tmp_path / "profiles" / "h"
    home.mkdir(parents=True)
    assert appearance.apply(home, "bell", "#3899e2") == "blue bell"
    saved = config.load(home).tui
    assert saved["shape"] == "bell" and saved["accent"] == "#3899e2" and "fold" not in saved
    assert appearance.apply(home, shape="heart") == "blue heart"
    assert appearance.apply(home, shape="Pebble") == "blue pebble"
    assert config.load(home).tui["accent"] == "#3899e2"
    with pytest.raises(ValueError):
        appearance.apply(home, shape="pencil")
    assert config.load(home).tui["shape"] == "pebble"


def test_an_untouched_profile_is_an_amber_round() -> None:
    assert appearance.pair_name({}) == "amber round"
    assert appearance.pair_name({"accent": "#123456", "shape": "pencil"}) == "round #123456"
    assert appearance.pair_name({"accent": "#3899e2", "fold": "shield"}) == "blue bell"
    assert appearance.pair_name({"accent": "#3899e2", "shape": "bell", "fold": "heart"}) == "blue bell"


def test_the_shape_is_the_value_and_only_a_stored_fold_is_translated() -> None:
    assert palette.SHAPES == ("round", "squircle", "drop", "dome", "pill", "clover", "cloud", "bean", "pebble", "arch", "heart", "bell")
    legacy = ("diamond", "house", "heart", "plane", "shield", "rocket", "star", "tree", "box", "crown", "feather", "bulb")
    assert [palette.legacy_shape(f) for f in legacy] == [
        "round", "arch", "heart", "drop", "bell", "pill", "clover", "pebble", "squircle", "dome", "cloud", "bean",
    ]
    assert [palette.shape_of(f) for f in legacy if f != "heart"] == [None] * 11
    assert all(palette.resolve_shape(f) == "round" for f in legacy if f != "heart")
    assert all(palette.resolve_shape(s) == palette.legacy_shape(s) == s for s in palette.SHAPES)
    assert palette.resolve_shape(" Bell ") == "bell"
    assert palette.resolve_shape(None) == palette.resolve_shape("pencil") == palette.resolve_shape(["bell"]) == "round"
    assert palette.shape_of("twin") is None and palette.shape_of("alpaca") is None
    listing = appearance.listing()
    assert listing.startswith("shapes: round, squircle, drop")
    assert "diamond" not in listing and "objects" not in listing


def test_the_tui_offers_shape_without_a_fold_alias_and_the_setup_menu_lists_appearance(tmp_path: Path) -> None:
    command = commands.lookup("shape")
    assert command is not None and command.method == "_cmd_shape" and command.usage == "[shape] [colour]"
    assert command.aliases == () and commands.lookup("fold") is None
    assert "origami" not in command.summary
    assert commands.complete("/fo") == []
    from alpi import cli

    (tmp_path / "profiles" / "h").mkdir(parents=True)
    assert cli._appearance_status(config.load(tmp_path / "profiles" / "h")) == "amber round"


def test_the_default_profile_is_twin_and_cannot_be_restyled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "root"
    root.mkdir()
    assert appearance.is_default(root) and not appearance.is_default(root / "profiles" / "doc")
    with pytest.raises(ValueError, match="brand mark"):
        appearance.apply(root, "bell", "#3899e2")
    assert not (root / "config.yaml").exists()
    assert appearance.pair_name({"fold": "shield"}, root) == "twin (brand mark)"
    from alpi import cli, ui

    assert cli._appearance_status(config.load(root)) == "twin (brand mark)"
    said: list[str] = []
    monkeypatch.setattr(ui, "ok_and_wait", said.append)
    cli._appearance_setup(root)
    assert said == [appearance.LOCKED_MESSAGE]


def test_every_colour_is_a_hue_and_pairs_with_its_shape_as_the_apps_ship() -> None:
    shipped = dict(re.findall(r'(\w+): "(\w+)"', re.search(r"ACCENT_SHAPES = \{([^}]*)\}", (REPO / "common" / "accents.mjs").read_text()).group(1)))
    assert appearance.SHAPE_OF == shipped
    assert sorted(appearance.SHAPE_OF.values()) == sorted(palette.SHAPES)
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
    assert all(t["shape"] == appearance.SHAPE_OF[appearance.accent_name(t["accent"])] for t in worn)
    assert all("fold" not in t for t in worn)
    assert all(t["show_cost"] is True and t["theme"] == "dark" for t in worn)
    assert appearance.accent_name(_create(tmp_path, "again")["accent"]) == appearance.ROULETTE[0]


def test_the_roulette_reuses_a_colour_freed_by_a_deleted_or_restyled_profile(tmp_path: Path) -> None:
    for name in ("a", "b", "c"):
        _create(tmp_path, name)
    appearance.apply(tmp_path / "profiles" / "b", "pill", "#2cb3b5")
    assert appearance.accent_name(_create(tmp_path, "d")["accent"]) == "blue"


def test_the_default_home_and_a_retired_grey_never_take_a_turn(tmp_path: Path) -> None:
    config.seed_defaults(tmp_path)
    assert "tui" not in config.seed_config_for(tmp_path)
    old = tmp_path / "profiles" / "old"
    old.mkdir(parents=True)
    (old / "config.yaml").write_text("tui:\n  accent: '#7e8792'\n  fold: box\n")
    assert palette.profile_accent({"accent": "#7e8792"}) == "#3ac9f3"
    assert appearance.next_pair(tmp_path / "profiles") == {"shape": "round", "accent": "#f0b447"}
    for name in appearance.ROULETTE[:-1]:
        _create(tmp_path, name + "-p")
    assert appearance.next_pair(tmp_path / "profiles")["accent"] == "#f0b447"


def test_apply_keeps_every_other_key_in_the_config(tmp_path: Path) -> None:
    home = tmp_path / "profiles" / "h"
    home.mkdir(parents=True)
    (home / "config.yaml").write_text("model: openai/gpt-x\nmemory:\n  review_interval: 3\ncustom_key: kept\ntui:\n  mode: dark\n")
    appearance.apply(home, "heart", "#f36a8a")
    import yaml
    raw = yaml.safe_load((home / "config.yaml").read_text())
    assert raw["memory"] == {"review_interval": 3}
    assert raw["custom_key"] == "kept"
    assert raw["tui"] == {"mode": "dark", "shape": "heart", "accent": "#f36a8a"}


def test_next_pair_skips_a_sibling_whose_config_does_not_load(tmp_path: Path) -> None:
    profiles = tmp_path / "profiles"
    (profiles / "broken").mkdir(parents=True)
    (profiles / "broken" / "config.yaml").write_text("model: [unclosed\n")
    (profiles / "odd").mkdir()
    (profiles / "odd" / "config.yaml").write_text("tui: dark\n")
    assert appearance.next_pair(profiles)["shape"] in palette.SHAPES


def _legacy(home: Path, text: str) -> Path:
    home.mkdir(parents=True, exist_ok=True)
    (home / "config.yaml").write_text(text)
    return home


def _snapshot(path: Path) -> tuple[bytes, int, int]:
    st = path.stat()
    return path.read_bytes(), st.st_mode, st.st_mtime_ns


def test_loading_a_legacy_fold_reads_its_shape_and_never_writes_the_file(tmp_path: Path) -> None:
    text = "model: openai/gpt-x  # keep me\ncustom_key: kept\ntui: {accent: '#3899e2', fold: shield, theme: light}\n"
    home = _legacy(tmp_path / "profiles" / "doc", text)
    path = home / "config.yaml"
    path.chmod(0o644)
    before = _snapshot(path)
    for _ in range(2):
        tui = config.load(home).tui
        assert tui["shape"] == "bell" and "fold" not in tui and tui["theme"] == "light"
    assert _snapshot(path) == before
    assert path.read_text() == text
    assert not list(home.glob(".config.yaml.*"))


def test_loading_a_symlinked_legacy_config_leaves_the_link_and_its_target_alone(tmp_path: Path) -> None:
    target = tmp_path / "repo" / "doc.yaml"
    target.parent.mkdir()
    target.write_text("tui:\n  fold: crown\n")
    home = tmp_path / "profiles" / "doc"
    home.mkdir(parents=True)
    (home / "config.yaml").symlink_to(target)
    before = _snapshot(target)
    assert config.load(home).tui["shape"] == "dome"
    assert (home / "config.yaml").is_symlink()
    assert _snapshot(target) == before


def test_a_legacy_config_gets_tui_shape_only_when_the_shape_is_saved(tmp_path: Path) -> None:
    import yaml

    home = _legacy(tmp_path / "profiles" / "doc", "model: openai/gpt-x\ncustom_key: kept\ntui:\n  fold: shield\n  theme: light\n")
    assert appearance.apply(home, colour="#3899e2") == "blue bell"
    raw = yaml.safe_load((home / "config.yaml").read_text())
    assert raw == {"model": "openai/gpt-x", "custom_key": "kept", "tui": {"fold": "shield", "theme": "light", "accent": "#3899e2"}}
    appearance.apply(home, shape="dome")
    raw = yaml.safe_load((home / "config.yaml").read_text())
    assert raw == {"model": "openai/gpt-x", "custom_key": "kept", "tui": {"theme": "light", "accent": "#3899e2", "shape": "dome"}}


def test_a_config_already_on_shapes_is_left_untouched(tmp_path: Path) -> None:
    text = "tui:\n  accent: '#3899e2'\n  shape: bell\n"
    home = _legacy(tmp_path / "profiles" / "doc", text)
    assert config.load(home).tui["shape"] == "bell"
    assert (home / "config.yaml").read_text() == text


def test_an_unknown_fold_reads_as_round_and_a_shape_already_set_wins(tmp_path: Path) -> None:
    unknown = _legacy(tmp_path / "profiles" / "a", "tui:\n  fold: pencil\n")
    assert config.load(unknown).tui["shape"] == "round"
    assert (unknown / "config.yaml").read_text() == "tui:\n  fold: pencil\n"
    both = _legacy(tmp_path / "profiles" / "b", "tui:\n  fold: heart\n  shape: bell\n")
    assert config.load(both).tui["shape"] == "bell"
    assert (both / "config.yaml").read_text() == "tui:\n  fold: heart\n  shape: bell\n"


def test_the_default_profile_reads_a_legacy_fold_as_twin_without_writing(tmp_path: Path) -> None:
    text = "model: x/y\ntui:\n  fold: alpaca\n  theme: light\n"
    root = _legacy(tmp_path / "root", text)
    assert config.load(root).tui["shape"] == "twin"
    assert (root / "config.yaml").read_text() == text
    assert appearance.pair_name(config.load(root).tui, root) == "twin (brand mark)"


def test_every_console_reader_resolves_a_legacy_fold(tmp_path: Path) -> None:
    from alpi import fold_art

    home = _legacy(tmp_path / "profiles" / "doc", "tui:\n  fold: plane\n  accent: '#df4b9d'\n")
    tui = config.load(home).tui
    assert appearance.current(tui) == ("drop", "#df4b9d")
    assert appearance.pair_name(tui, home) == "magenta drop"
    assert fold_art.identity(home, tui)[0] == "drop"
    assert appearance.current({"fold": "plane"})[0] == "drop"
