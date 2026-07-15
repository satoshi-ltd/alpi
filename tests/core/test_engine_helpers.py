from __future__ import annotations

from pathlib import Path

from alpi import config
from alpi.engine import _last_peer_reply, _maybe_load_mcps, _result_for_log
from alpi.session import ASSISTANT_CAP, TOOL_RESULT_CAP
from alpi.session import ToolLog


def test_result_for_log_truncates_normal_tools() -> None:
    long = "x" * (TOOL_RESULT_CAP * 3)
    out = _result_for_log("web_search", long)
    assert len(out) <= TOOL_RESULT_CAP
    assert out.endswith("…")


def test_result_for_log_keeps_peer_reply_under_assistant_cap() -> None:
    reply = "y" * (TOOL_RESULT_CAP * 3)
    payload = reply + "\n\n---\ntokens: in=1 out=2 · cost=$0.0001"
    assert len(payload) <= ASSISTANT_CAP
    assert _result_for_log("peer", payload) == reply


def test_result_for_log_strips_peer_usage_before_truncating() -> None:
    reply = "x" * max(0, ASSISTANT_CAP - 5)
    payload = reply + "\n\n---\ntokens: in=1 out=2 · cost=$0.0001"
    out = _result_for_log("peer", payload)
    assert out == reply
    assert "---" not in out
    assert "tokens:" not in out


def test_result_for_log_bounds_huge_peer_reply() -> None:
    huge = "z" * (ASSISTANT_CAP * 2)
    out = _result_for_log("peer", huge)
    assert len(out.encode("utf-8")) <= ASSISTANT_CAP
    assert out.endswith("…")


def test_result_for_log_bounds_multibyte_peer_reply_by_bytes() -> None:
    huge = "á" * ASSISTANT_CAP
    out = _result_for_log("peer", huge)
    assert len(out.encode("utf-8")) <= ASSISTANT_CAP
    assert out.endswith("…")


def test_last_peer_reply_accepts_legacy_result_with_usage_footer() -> None:
    logs = [
        ToolLog(
            at=1.0,
            name="peer",
            args={},
            result="Visible answer.\n\n---\ntokens: in=1 out=2 · cost=$0.0001",
            ok=True,
            duration_s=0.1,
        )
    ]
    assert _last_peer_reply(logs) == "Visible answer."


def test_maybe_load_mcps_skips_when_no_servers(tmp_path: Path) -> None:
    cfg = config.Config(home=tmp_path, model="", raw={})
    assert _maybe_load_mcps(cfg) == {}


def test_maybe_load_mcps_delegates_to_registry(monkeypatch, tmp_path: Path) -> None:
    cfg = config.Config(
        home=tmp_path,
        model="",
        raw={"mcp": {"servers": {"demo": {"command": "echo"}}}},
    )
    seen = {}

    def fake_mcp_tools_for(received):
        seen["cfg"] = received
        return {"demo__x": object}

    monkeypatch.setattr("alpi.mcp.registry.mcp_tools_for", fake_mcp_tools_for)

    assert _maybe_load_mcps(cfg) == {"demo__x": object}
    assert seen["cfg"] is cfg
