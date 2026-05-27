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


def test_local_socket_path_resolves_by_pubkey_first(tmp_path, monkeypatch) -> None:
    from alpi import home as home_mod
    from alpi.alp import keys as keys_mod

    root = tmp_path / ".alpi"
    root.mkdir()
    target = root / "profiles" / "real_name"
    target.mkdir(parents=True)
    target_kp = keys_mod.generate(target)
    monkeypatch.setattr(home_mod, "_ROOT", root)
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))

    peer = Peer(
        id="totally_random_alias",
        pubkey=target_kp.pubkey_b64(),
        allow=["link.ping"],
    )
    assert peers_mod.local_socket_path(peer) == target / "alp" / "alp.sock"


def test_local_socket_path_falls_back_to_peer_id_when_pubkey_unknown(
    tmp_path, monkeypatch,
) -> None:
    from alpi import home as home_mod

    root = tmp_path / ".alpi"
    root.mkdir()
    monkeypatch.setattr(home_mod, "_ROOT", root)
    monkeypatch.delenv("ALPI_HOME", raising=False)

    peer = Peer(id="remote", pubkey="REMOTE_NOT_LOCAL", allow=["link.ping"])
    expected = root / "profiles" / "remote" / "alp" / "alp.sock"
    assert peers_mod.local_socket_path(peer) == expected


def test_local_socket_path_default_profile(tmp_path, monkeypatch) -> None:
    from alpi import home as home_mod

    root = tmp_path / ".alpi"
    root.mkdir()
    monkeypatch.setattr(home_mod, "_ROOT", root)
    monkeypatch.delenv("ALPI_HOME", raising=False)

    peer = Peer(id="default", pubkey="UNKNOWN", allow=["link.ping"])
    assert peers_mod.local_socket_path(peer) == root / "alp" / "alp.sock"


def test_local_socket_path_honors_alpi_home_on_fallback(
    tmp_path, monkeypatch,
) -> None:
    alt_root = tmp_path / "alt-root"
    alt_root.mkdir()
    monkeypatch.setenv("ALPI_HOME", str(alt_root))
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path / "noise"))

    peer = Peer(id="remote", pubkey="REMOTE_NOT_LOCAL", allow=["link.ping"])
    assert peers_mod.local_socket_path(peer) == alt_root / "profiles" / "remote" / "alp" / "alp.sock"

    peer_default = Peer(id="default", pubkey="UNKNOWN", allow=["link.ping"])
    assert peers_mod.local_socket_path(peer_default) == alt_root / "alp" / "alp.sock"


def test_local_socket_path_resolves_alias_by_pubkey_under_alpi_home(
    tmp_path, monkeypatch,
) -> None:
    from alpi import home as home_mod
    from alpi.alp import keys as keys_mod

    alt_root = tmp_path / "alt-root"
    real_target = alt_root / "profiles" / "real_name"
    real_target.mkdir(parents=True)
    target_kp = keys_mod.generate(real_target)

    monkeypatch.setenv("ALPI_HOME", str(alt_root))
    monkeypatch.setattr(home_mod, "_ROOT", tmp_path / "noise-default")
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path / "noise"))

    peer = Peer(
        id="completely_unrelated_alias",
        pubkey=target_kp.pubkey_b64(),
        allow=["link.ping"],
    )
    assert peers_mod.local_socket_path(peer) == real_target / "alp" / "alp.sock"
