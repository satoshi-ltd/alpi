from __future__ import annotations

from pathlib import Path

from alpi import config as config_mod


def test_relay_loads_from_yaml(tmp_path: Path) -> None:
    home = tmp_path / "h"
    home.mkdir()
    (home / "config.yaml").write_text("model: m\nrelay:\n  peer: agora\n")
    cfg = config_mod.load(home)
    assert cfg.relay == {"peer": "agora"}


def test_relay_defaults_empty(tmp_path: Path) -> None:
    home = tmp_path / "h"
    home.mkdir()
    (home / "config.yaml").write_text("model: m\n")
    cfg = config_mod.load(home)
    assert cfg.relay == {}


def test_relay_survives_save_round_trip(tmp_path: Path) -> None:
    home = tmp_path / "h"
    home.mkdir()
    (home / "config.yaml").write_text("model: m\nrelay:\n  peer: agora\n")
    cfg = config_mod.load(home)
    config_mod.save(cfg)
    assert config_mod.load(home).relay == {"peer": "agora"}
