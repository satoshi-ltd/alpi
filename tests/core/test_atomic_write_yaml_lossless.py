from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from alpi import yamlfast
from alpi.config import atomic_write_yaml

# U+0085 is the one the pure emitter loses; the rest are line/paragraph separators and controls a folding emitter could also eat.
HOSTILE = (
    "a\x85b",
    "\x85",
    "line break",
    "para break",
    "nbsp here",
    "bom﻿here",
    "vtab\x0bhere",
    "ff\x0chere",
    "ctrl\x1c\x1d\x1e",
    "crlf\r\nhere",
    "trailing   ",
    "  leading",
    "tab\there",
    "acentos áéíóú ñ",
    "emoji 🚀",
    "x" * 400 + "\x85" + "y" * 400,
)


@pytest.mark.parametrize("value", HOSTILE)
def test_written_scalar_survives_its_own_round_trip(
    tmp_path: Path, value: str,
) -> None:
    p = tmp_path / "out.yaml"
    atomic_write_yaml(p, {"k": value, "nested": [{"deep": value}]})
    for loader in (yamlfast.safe_load, yaml.safe_load):
        back = loader(p.read_text(encoding="utf-8"))
        assert back["k"] == value, loader
        assert back["nested"][0]["deep"] == value, loader


@pytest.mark.parametrize("value", HOSTILE)
def test_written_key_survives_its_own_round_trip(
    tmp_path: Path, value: str,
) -> None:
    p = tmp_path / "out.yaml"
    atomic_write_yaml(p, {value: "v"})
    assert yamlfast.safe_load(p.read_text(encoding="utf-8")) == {value: "v"}


def test_config_save_round_trips_a_hostile_value(tmp_path: Path) -> None:
    from alpi import config as config_mod

    cfg = config_mod.load(tmp_path)
    cfg.public_bio = "senior\x85engineer"
    cfg.workspace = "/git/pro ject"
    config_mod.save(cfg)
    reloaded = config_mod.load(tmp_path)
    assert reloaded.public_bio == cfg.public_bio
    assert reloaded.workspace == cfg.workspace


def test_device_state_config_write_round_trips_a_hostile_value(
    tmp_path: Path,
) -> None:
    from alpi.host import device_state

    device_state._write_user_yaml(tmp_path, {"public_bio": "a\x85b"})
    assert device_state._load_user_yaml(tmp_path) == {"public_bio": "a\x85b"}


def test_peers_save_round_trips_a_hostile_value(tmp_path: Path) -> None:
    from alpi.alp import peers as peers_mod

    peers_mod.save(tmp_path, [peers_mod.Peer(
        id="bob", pubkey="P" * 44, alias="ops\x85lead", allow=["link.ping"],
    )])
    stored = peers_mod.load(tmp_path)
    assert [p.alias for p in stored] == ["ops\x85lead"]


def test_subscriptions_save_round_trips_a_hostile_value(tmp_path: Path) -> None:
    from alpi.alp import subscription as sub_mod

    sub_mod._raw_cache.clear()
    sub = sub_mod.Subscription(
        wg_id="wg_a", name="site", hub_id="hub", hub_pubkey="H" * 44,
        briefing="ship\x85it",
    )
    sub.recent_posts = [{"seq": 1, "text": "done\x85already"}]
    sub_mod.save(tmp_path, [sub])
    sub_mod._raw_cache.clear()
    stored = sub_mod.load(tmp_path)
    assert stored[0].briefing == "ship\x85it"
    assert stored[0].recent_posts[0]["text"] == "done\x85already"


def test_seed_config_round_trips(tmp_path: Path) -> None:
    from alpi import config as config_mod

    config_mod.seed_defaults(tmp_path)
    raw = yamlfast.safe_load((tmp_path / "config.yaml").read_text())
    assert raw == config_mod.seed_config_for(tmp_path)


def test_a_lone_surrogate_raises_instead_of_writing_a_broken_file(
    tmp_path: Path,
) -> None:
    p = tmp_path / "out.yaml"
    atomic_write_yaml(p, {"k": "good"})
    with pytest.raises(UnicodeEncodeError):
        atomic_write_yaml(p, {"k": "bad\ud800"})
    assert yamlfast.safe_load(p.read_text(encoding="utf-8")) == {"k": "good"}
    assert list(tmp_path.glob(".out.yaml.*")) == []


@pytest.mark.parametrize("value", HOSTILE)
def test_the_no_libyaml_fallback_is_lossless_too(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, value: str,
) -> None:
    monkeypatch.setattr(yamlfast, "_DUMPER", yaml.SafeDumper)
    monkeypatch.setattr(yamlfast, "HAS_LIBYAML", False)
    p = tmp_path / "fallback.yaml"
    atomic_write_yaml(p, {"k": value})
    text = p.read_text()
    assert yaml.load(text, Loader=yaml.SafeLoader)["k"] == value
    assert yamlfast.safe_load(text)["k"] == value


def test_the_fallback_is_what_actually_changes_the_setting() -> None:
    with_libyaml = yamlfast.safe_dump({"k": "acentos áé"}, sort_keys=False, allow_unicode=True)
    assert "á" in with_libyaml


def test_the_fallback_refuses_a_lone_surrogate_like_libyaml_does(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(yamlfast, "_DUMPER", yaml.SafeDumper)
    monkeypatch.setattr(yamlfast, "HAS_LIBYAML", False)
    p = tmp_path / "surrogate.yaml"
    atomic_write_yaml(p, {"k": "fine"})
    before = p.read_bytes()
    with pytest.raises(UnicodeEncodeError):
        atomic_write_yaml(p, {"k": "bad\ud800"})
    assert p.read_bytes() == before
    assert not list(tmp_path.glob(".*.tmp"))


def test_the_fallback_refuses_a_surrogate_anywhere_in_the_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(yamlfast, "_DUMPER", yaml.SafeDumper)
    monkeypatch.setattr(yamlfast, "HAS_LIBYAML", False)
    for payload in (
        {"k": ["ok", {"deep": "bad\udfff"}]},
        {"bad\ud800": "value"},
        [["ok"], ["nested", "bad\ud888"]],
    ):
        with pytest.raises(UnicodeEncodeError):
            atomic_write_yaml(tmp_path / "x.yaml", payload)


def test_a_file_the_fallback_wrote_opens_under_libyaml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(yamlfast, "_DUMPER", yaml.SafeDumper)
    monkeypatch.setattr(yamlfast, "HAS_LIBYAML", False)
    p = tmp_path / "cross.yaml"
    atomic_write_yaml(p, {"k": [v for v in HOSTILE]})
    monkeypatch.undo()
    assert yamlfast.safe_load(p.read_text())["k"] == list(HOSTILE)
