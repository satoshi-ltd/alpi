from __future__ import annotations

import base64
from pathlib import Path

from alpi.alp import peers as peers_mod
from alpi.alp import setup as alp_setup


def _wizard(monkeypatch, answers: list[str], *, limit: bool = False) -> list[str]:
    said: list[str] = []
    replies = iter(answers)
    monkeypatch.setattr(alp_setup.ui, "banner", lambda *a, **kw: None)
    monkeypatch.setattr(alp_setup.ui, "dim", lambda *a, **kw: None)
    monkeypatch.setattr(alp_setup.ui, "text", lambda *a, **kw: next(replies))
    monkeypatch.setattr(
        alp_setup.ui, "confirm",
        lambda prompt, default=False, **kw: limit if prompt.startswith("Limit the tools") else default,
    )
    monkeypatch.setattr(alp_setup.ui, "ok_and_wait", lambda msg: said.append(f"ok: {msg}"))
    monkeypatch.setattr(alp_setup.ui, "fail_and_wait", lambda msg: said.append(f"fail: {msg}"))
    monkeypatch.setattr(alp_setup.ui._console, "print", lambda *a, **kw: said.append(" ".join(map(str, a))))
    return said


def test_pinning_from_the_wizard_stores_the_allowlist(tmp_path: Path, monkeypatch) -> None:
    key = base64.b64encode(b"k" * 32).decode()
    said = _wizard(monkeypatch, ["alexandra", key, "", "knowledge:search, alpi_knowledge", ""], limit=True)

    alp_setup._add(tmp_path)

    assert any(s.startswith("ok: pinned @alexandra") for s in said)
    assert peers_mod.get_by_id(tmp_path, "alexandra").allowed_tools() == frozenset({"knowledge:search", "alpi_knowledge"})


def test_limiting_tools_in_the_wizard_with_an_empty_list_allows_none(tmp_path: Path, monkeypatch) -> None:
    key = base64.b64encode(b"k" * 32).decode()
    _wizard(monkeypatch, ["alexandra", key, "", "", ""], limit=True)

    alp_setup._add(tmp_path)

    assert peers_mod.get_by_id(tmp_path, "alexandra").allowed_tools() == frozenset()


def test_not_limiting_tools_in_the_wizard_sets_no_policy(tmp_path: Path, monkeypatch) -> None:
    key = base64.b64encode(b"k" * 32).decode()
    _wizard(monkeypatch, ["alexandra", key, "", ""])

    alp_setup._add(tmp_path)

    assert peers_mod.get_by_id(tmp_path, "alexandra").allowed_tools() is None


def test_the_wizard_refuses_an_entry_that_is_not_a_tool_name(tmp_path: Path, monkeypatch) -> None:
    key = base64.b64encode(b"k" * 32).decode()
    said = _wizard(monkeypatch, ["alexandra", key, "", "rm -rf /", ""], limit=True)

    alp_setup._add(tmp_path)

    assert any(s.startswith("fail:") and "tools.allow" in s for s in said)
    assert peers_mod.get_by_id(tmp_path, "alexandra") is None


def test_the_peer_detail_shows_the_allowlist_or_why_it_is_refused(tmp_path: Path, monkeypatch) -> None:
    peers_mod.save(tmp_path, [
        peers_mod.Peer(id="a", pubkey="AAA=", allow=["link.ask"], tools={"allow": ["knowledge:search"]}),
        peers_mod.Peer(id="b", pubkey="BBB=", allow=["link.ask"], tools={"deny": ["terminal"]}),
        peers_mod.Peer(id="c", pubkey="CCC=", allow=["link.ask"]),
    ])
    shown: dict[str, list[str]] = {}
    for peer_id in ("a", "b", "c"):
        said = _wizard(monkeypatch, [])
        monkeypatch.setattr(alp_setup.ui, "press_enter", lambda *a, **kw: None)
        alp_setup._inspect(tmp_path, peer_id, "on", None, None, "SELF=")
        shown[peer_id] = [s for s in said if s.strip().startswith("tools")]

    assert shown["a"] == ["  tools    allow: knowledge:search"]
    assert "INVALID" in shown["b"][0] and "tools.allow" in shown["b"][0]
    assert shown["c"] == ["  tools    profile tools (no policy)"]
