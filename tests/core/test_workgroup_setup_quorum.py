from __future__ import annotations

from pathlib import Path

import pytest

from alpi.alp import workgroup_setup


@pytest.fixture(autouse=True)
def quiet(monkeypatch):
    for name in ("banner", "dim"):
        monkeypatch.setattr(f"alpi.ui.{name}", lambda *a, **kw: None)
    monkeypatch.setattr("alpi.ui._console.print", lambda *a, **kw: None)


def answers(monkeypatch, *values):
    it = iter(values)
    monkeypatch.setattr("alpi.ui.text", lambda *a, **kw: next(it))


def test_pick_quorum_keeps_the_default_on_enter(monkeypatch, tmp_path: Path) -> None:
    answers(monkeypatch, "")
    assert workgroup_setup._pick_quorum(tmp_path) == 0


def test_pick_quorum_asks_again_until_the_seconds_are_valid(monkeypatch, tmp_path: Path) -> None:
    answers(monkeypatch, "ten", "-5", "²", "1200")
    assert workgroup_setup._pick_quorum(tmp_path) == 1200


def test_pick_quorum_cancels_on_escape(monkeypatch, tmp_path: Path) -> None:
    answers(monkeypatch, None)
    assert workgroup_setup._pick_quorum(tmp_path) is None


def test_create_flow_hands_the_wait_to_the_workgroup(monkeypatch, tmp_path: Path) -> None:
    seen = {}
    monkeypatch.setattr(workgroup_setup, "_pick_members", lambda pinned, home: [])
    monkeypatch.setattr(workgroup_setup, "_pick_budget", lambda home: None)
    monkeypatch.setattr(workgroup_setup, "_pick_quorum", lambda home: 900)
    monkeypatch.setattr(workgroup_setup.peers_mod, "load", lambda home: {"p": object()})
    monkeypatch.setattr(workgroup_setup, "load_or_generate", lambda home: object())
    monkeypatch.setattr(workgroup_setup.wg_mod, "create", lambda home, **kw: seen.update(kw) or (_ for _ in ()).throw(ValueError("stop")))
    monkeypatch.setattr("alpi.ui.fail_and_wait", lambda *a, **kw: None)
    answers(monkeypatch, "ops", "")
    workgroup_setup._create_flow(tmp_path)
    assert seen["quorum_timeout_seconds"] == 900
