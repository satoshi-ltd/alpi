from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from alpi import config, palette

ACCENTS = (
    ("amber", "#f0b447"),
    ("orange", "#f28832"),
    ("vermilion", "#f05940"),
    ("rose", "#f36a8a"),
    ("magenta", "#df4b9d"),
    ("violet", "#9b5ad9"),
    ("indigo", "#6572e4"),
    ("blue", "#3899e2"),
    ("sky", "#3ac9f3"),
    ("teal", "#2cb3b5"),
    ("green", "#3ec173"),
    ("lime", "#9fc93e"),
)
_HEX = {name: hex_ for name, hex_ in ACCENTS}
FOLD_OF = {
    "amber": "diamond", "vermilion": "house", "rose": "heart", "magenta": "plane", "blue": "shield", "teal": "rocket",
    "violet": "star", "green": "tree", "sky": "box", "indigo": "crown", "lime": "feather", "orange": "bulb",
}
ROULETTE = ("amber", "blue", "vermilion", "green", "violet", "orange", "teal", "magenta", "lime", "indigo", "rose", "sky")
LOCKED_KEYS = frozenset({"tui.fold", "tui.accent"})
LOCKED_MESSAGE = "the default profile always wears the alpaca in the brand accent"


def is_default(home: Path | str) -> bool:
    return Path(home).parent.name != "profiles"


def accent_hex(text: str | None) -> str | None:
    value = (text or "").strip().lower()
    if value in _HEX:
        return _HEX[value]
    if len(value) == 7 and value.startswith("#") and all(c in "0123456789abcdef" for c in value[1:]):
        return value
    return None


def accent_name(hex_value: str | None) -> str | None:
    value = (hex_value or "").strip().lower()
    return next((name for name, hex_ in ACCENTS if hex_ == value), None)


def current(tui: dict[str, Any] | None) -> tuple[str, str]:
    fold = palette.resolve_fold((tui or {}).get("fold"))
    accent = str((tui or {}).get("accent") or palette.DEFAULT_PROFILE_COLOUR).strip().lower()
    return fold, accent


def pair_name(tui: dict[str, Any] | None, home: Path | str | None = None) -> str:
    if home is not None and is_default(home):
        return f"{palette.ALPACA_FOLD} (brand accent)"
    fold, accent = current(tui)
    colour = accent_name(accent)
    return f"{colour} {fold}" if colour else f"{fold} {accent}"


def parse(text: str) -> tuple[str | None, str | None]:
    fold = colour = None
    for word in (text or "").replace(",", " ").split():
        lowered = word.lower()
        if lowered in palette.FOLDS:
            fold = lowered
        elif accent_hex(word):
            colour = accent_hex(word)
        else:
            raise ValueError(f"{word!r} is neither one of the twelve objects nor a colour")
    return fold, colour


def apply(home: Path, fold: str | None = None, colour: str | None = None) -> str:
    if is_default(home):
        raise ValueError(LOCKED_MESSAGE)
    if fold is not None and fold not in palette.FOLDS:
        raise ValueError(f"fold must be one of {', '.join(palette.FOLDS)}")
    path = home / "config.yaml"
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}
    raw = raw if isinstance(raw, dict) else {}
    tui = dict(raw["tui"]) if isinstance(raw.get("tui"), dict) else {}
    if fold is not None:
        tui["fold"] = fold
    if colour is not None:
        tui["accent"] = colour
    raw["tui"] = tui
    config.atomic_write_yaml(path, raw)
    return pair_name(tui)


def next_pair(profiles_dir: Path, exclude: str | None = None) -> dict[str, str]:
    worn = dict.fromkeys(ROULETTE, 0)
    if profiles_dir.is_dir():
        for home in profiles_dir.iterdir():
            if not home.is_dir() or home.name.startswith(".") or home.name == exclude or not (home / "config.yaml").exists():
                continue
            try:
                colour = accent_name(palette.canonical_accent(current(config.load(home).tui)[1]))
            except Exception:  # noqa: BLE001
                continue
            if colour in worn:
                worn[colour] += 1
    colour = min(ROULETTE, key=lambda name: (worn[name], ROULETTE.index(name)))
    return {"fold": FOLD_OF[colour], "accent": _HEX[colour]}


def listing() -> str:
    objects = ", ".join(palette.FOLDS)
    colours = ", ".join(name for name, _ in ACCENTS)
    return f"objects: {objects}\ncolours: {colours} (or a #hex)"
