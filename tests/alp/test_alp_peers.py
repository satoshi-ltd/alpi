"""ALP peer list — load/save/add/remove + capability check."""

from __future__ import annotations

from pathlib import Path

import pytest

from alpi.alp import peers as peers_mod
from alpi.alp.peers import Peer


def test_load_missing_returns_empty(tmp_path: Path) -> None:
    assert peers_mod.load(tmp_path) == []


def test_save_and_load_roundtrip(tmp_path: Path) -> None:
    p = Peer(
        id="home-server", pubkey="AAA=", alias="NAS",
        address="nas.local:7423", allow=["link.ping", "link.ask"],
    )
    peers_mod.save(tmp_path, [p])
    loaded = peers_mod.load(tmp_path)
    assert len(loaded) == 1
    assert loaded[0].id == "home-server"
    assert loaded[0].allow == ["link.ping", "link.ask"]
    assert loaded[0].address == "nas.local:7423"


def test_save_trims_empty_optional_fields(tmp_path: Path) -> None:
    p = Peer(id="x", pubkey="AAA=", allow=["link.ping"])
    peers_mod.save(tmp_path, [p])
    text = peers_mod.path(tmp_path).read_text()
    assert "alias" not in text
    assert "address" not in text
    assert "budget" not in text


def test_get_by_id_and_pubkey(tmp_path: Path) -> None:
    peers_mod.save(tmp_path, [Peer(id="a", pubkey="PA==", allow=["link.ping"])])
    assert peers_mod.get_by_id(tmp_path, "a").pubkey == "PA=="
    assert peers_mod.get_by_pubkey(tmp_path, "PA==").id == "a"
    assert peers_mod.get_by_id(tmp_path, "missing") is None
    assert peers_mod.get_by_pubkey(tmp_path, "XX==") is None


def test_add_rejects_duplicate_id(tmp_path: Path) -> None:
    peers_mod.add(tmp_path, Peer(id="a", pubkey="P1==", allow=[]))
    with pytest.raises(ValueError, match="already exists"):
        peers_mod.add(tmp_path, Peer(id="a", pubkey="P2==", allow=[]))


def test_add_rejects_duplicate_pubkey(tmp_path: Path) -> None:
    peers_mod.add(tmp_path, Peer(id="a", pubkey="PA==", allow=[]))
    with pytest.raises(ValueError, match="pubkey already pinned"):
        peers_mod.add(tmp_path, Peer(id="b", pubkey="PA==", allow=[]))


def test_remove(tmp_path: Path) -> None:
    peers_mod.add(tmp_path, Peer(id="a", pubkey="PA==", allow=[]))
    assert peers_mod.remove(tmp_path, "a") is True
    assert peers_mod.load(tmp_path) == []
    assert peers_mod.remove(tmp_path, "a") is False


def test_may_call_is_fail_closed() -> None:
    p = Peer(id="a", pubkey="PA==", allow=[])
    assert p.may_call("link.ping") is False

    p2 = Peer(id="b", pubkey="PB==", allow=["link.ping"])
    assert p2.may_call("link.ping") is True
    assert p2.may_call("link.ask") is False


def test_malformed_yaml_returns_empty(tmp_path: Path) -> None:
    peers_mod.path(tmp_path).parent.mkdir(parents=True, exist_ok=True)
    peers_mod.path(tmp_path).write_text("::: not yaml :::")
    assert peers_mod.load(tmp_path) == []


def test_entries_missing_required_fields_are_skipped(tmp_path: Path) -> None:
    peers_mod.path(tmp_path).parent.mkdir(parents=True, exist_ok=True)
    peers_mod.path(tmp_path).write_text(
        "- id: a\n"
        "  pubkey: PA==\n"
        "  allow: [link.ping]\n"
        "- alias: orphan\n"
    )
    loaded = peers_mod.load(tmp_path)
    assert len(loaded) == 1
    assert loaded[0].id == "a"
