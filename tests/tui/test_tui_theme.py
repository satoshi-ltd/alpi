from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

from alpi import config, ui
from alpi.tui import themes

TOKENS = Path(__file__).resolve().parents[2] / "common" / "tokens.mjs"


def _object(name: str) -> dict[str, str]:
    src = TOKENS.read_text()
    m = re.search(rf"\bconst\s+{name}\s*=\s*\{{(.*?)^\s*\}}\s*;?", src, re.S | re.M)
    assert m, f"{name} not found in tokens.mjs"
    pairs = re.findall(r"""^\s*["']?(\w+)["']?\s*:\s*["']([^"']+)["']""", m.group(1), re.M)
    return {k: v.strip().lower() for k, v in pairs}


@pytest.mark.parametrize("mode,palette", [("dark", themes.DARK), ("light", themes.LIGHT)])
def test_tui_palettes_mirror_the_shared_tokens(mode: str, palette: dict) -> None:
    tokens = _object(mode)
    for key, value in palette.items():
        assert tokens[key] == value.lower(), f"{mode}.{key}"


def test_tui_status_colours_mirror_the_shared_tokens() -> None:
    assert {k: v.lower() for k, v in themes.STATUS.items()} == _object("status")


@pytest.mark.parametrize("dark", [True, False])
def test_built_theme_uses_the_token_values(dark: bool) -> None:
    palette = themes.DARK if dark else themes.LIGHT
    theme = themes.build_theme(None, dark=dark)
    tokens = _object("dark" if dark else "light")
    status = _object("status")
    assert theme.accent.lower() == tokens["accent"]
    assert theme.primary.lower() == tokens["accent"]
    assert theme.background.lower() == tokens["bg"]
    assert theme.surface.lower() == tokens["bgPane"]
    assert theme.panel.lower() == tokens["bgElev"]
    assert theme.foreground.lower() == tokens["ink"]
    assert theme.variables["text-muted"].lower() == tokens["ink3"] == palette["ink3"].lower()
    assert theme.success.lower() == status["success"]
    assert theme.warning.lower() == tokens["warningText"] == palette["warningText"].lower()
    assert theme.warning.lower() != theme.accent.lower()
    assert theme.error.lower() == status["danger"]


@pytest.mark.parametrize("configured", [None, "", "#f0b447", "#c8a24e", "#8A5A0A"])
def test_brand_accents_follow_the_mode_token(configured) -> None:
    assert themes.resolve_accent(configured, dark=True) == "#f0b447"
    assert themes.resolve_accent(configured, dark=False) == "#8a5a0a"


def test_a_custom_accent_is_kept() -> None:
    assert themes.resolve_accent("#ff0088", dark=True) == "#ff0088"
    assert themes.resolve_accent("#ff0088", dark=False) == "#ff0088"


def test_console_defaults_use_the_brand_accent() -> None:
    assert config.DEFAULT_CONFIG["tui"]["accent"] == _object("dark")["accent"]
    assert ui.DEFAULT_ACCENT == _object("dark")["accent"]


def test_token_parser_tolerates_formatting(tmp_path, monkeypatch) -> None:
    fake = tmp_path / "tokens.mjs"
    fake.write_text("export const dark = {\n  'bg' : '#0A0D11',\n  ink:\"#E6EDF3\" ,\n};\n")
    monkeypatch.setattr(sys.modules[__name__], "TOKENS", fake)
    assert _object("dark") == {"bg": "#0a0d11", "ink": "#e6edf3"}


@pytest.mark.parametrize("tui,expected", [
    ({}, "#f0b447"),
    ({"accent": "#c8a24e"}, "#f0b447"),
    ({"accent": "#c8a24e", "theme": "light"}, "#8a5a0a"),
    ({"theme": "light"}, "#8a5a0a"),
    ({"accent": "#123456", "theme": "light"}, "#123456"),
])
def test_console_accent_goes_through_the_same_resolver(tui, expected, tmp_path) -> None:
    import yaml

    from alpi import palette

    assert palette.profile_accent(tui) == expected
    (tmp_path / "config.yaml").write_text(yaml.safe_dump({"tui": tui}))
    assert ui._accent_hex(tmp_path) == expected


def test_cli_has_no_legacy_accent_fallback() -> None:
    src = (Path(__file__).resolve().parents[2] / "alpi" / "cli.py").read_text()
    assert "#c8a24e" not in src
