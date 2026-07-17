import json
import signal
import stat
import sys
import types
from pathlib import Path

import pytest

from alpi.alp import pipeline_gates as gates


def _meta(steps, pipeline=("content", "translation", "build")):
    return types.SimpleNamespace(pipeline_steps=steps, pipeline=pipeline)


STEPS = {
    "content": {
        "owner": "quill",
        "next": "translation",
        "task": "translate every source entry into the declared locales",
        "gate": {"cwd": "projects/casa", "argv": ["npm", "run", "content-check"]},
    },
    "translation": {"owner": "lingua", "next": "build", "task": "ship it",
                    "gate": {"cwd": "projects/casa", "argv": ["true"]}},
}


def test_step_for_resolves_owner_next_and_argv():
    step = gates.step_for(_meta(STEPS), "content")
    assert step.owner == "quill"
    assert step.next_phase == "translation"
    assert step.next_owner == "lingua"
    assert step.argv == ("npm", "run", "content-check")
    assert gates.step_for(_meta(STEPS), "qa") is None
    assert gates.step_for(_meta({}), "content") is None


@pytest.mark.parametrize("raw", [
    {"content": {"owner": "quill"}},
    {"content": {"gate": {"argv": ["true"]}}},
    {"content": {"owner": "quill", "gate": {"argv": "true"}}},
    {"content": {"owner": "quill", "gate": {"argv": [1, 2]}}},
    {"content": "junk"},
])
def test_step_for_rejects_malformed_specs(raw):
    assert gates.step_for(_meta(raw), "content") is None


def test_step_for_rejects_malformed_or_unknown_next_step():
    malformed = {**STEPS, "translation": "junk"}
    assert gates.step_for(_meta(malformed), "content") is None
    assert gates.step_for(_meta(STEPS, pipeline=("content",)), "content") is None


def test_run_gate_pass_and_fail(tmp_path):
    ws = tmp_path / "ws"
    (ws / "proj").mkdir(parents=True)
    ok_step = gates.GateStep("content", "quill", "", "", "", (sys.executable, "-c", "print('42 ok')"), "proj")
    passed, out = gates.run_gate(ok_step, ws)
    assert passed and "42 ok" in out

    bad_step = gates.GateStep("content", "quill", "", "", "", (sys.executable, "-c", "import sys; print('boom'); sys.exit(3)"), "proj")
    passed, out = gates.run_gate(bad_step, ws)
    assert not passed and "boom" in out


def test_run_gate_rejects_cwd_escape_and_missing(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    escape = gates.GateStep("content", "quill", "", "", "", ("true",), "../outside")
    passed, out = gates.run_gate(escape, ws)
    assert not passed and "escapes" in out

    missing = gates.GateStep("content", "quill", "", "", "", ("true",), "nope")
    passed, out = gates.run_gate(missing, ws)
    assert not passed and "missing" in out


def test_run_gate_env_is_minimal(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-secret")
    ws = tmp_path / "ws"
    ws.mkdir()
    step = gates.GateStep(
        "content", "quill", "", "", "",
        (sys.executable, "-c", "import os; print('LEAK' if os.environ.get('OPENROUTER_API_KEY') else 'clean')"),
        "",
    )
    passed, out = gates.run_gate(step, ws)
    assert passed and "clean" in out


def test_run_gate_bounds_output_and_replaces_invalid_utf8(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    script = (
        "import os; "
        f"os.write(1, b'x' * {gates.GATE_OUTPUT_CAP * 3} + b'\\xffEND')"
    )
    step = gates.GateStep(
        "content", "quill", "", "", "",
        (sys.executable, "-c", script), "",
    )
    passed, out = gates.run_gate(step, ws)
    assert passed
    assert len(out) <= gates.GATE_OUTPUT_CAP
    assert out.endswith("�END")


def test_run_gate_timeout_terminates_its_process_group(
    tmp_path, monkeypatch,
):
    ws = tmp_path / "ws"
    ws.mkdir()
    calls: list[int] = []
    real_killpg = gates.os.killpg

    def tracked_killpg(pid, sig):
        calls.append(sig)
        return real_killpg(pid, sig)

    monkeypatch.setattr(gates, "GATE_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(gates.os, "killpg", tracked_killpg)
    step = gates.GateStep(
        "content", "quill", "", "", "",
        (sys.executable, "-c", "import time; time.sleep(5)"), "",
    )
    passed, out = gates.run_gate(step, ws)
    assert not passed and "timed out" in out
    assert signal.SIGTERM in calls


def test_write_gate_log_is_private_and_capped(tmp_path):
    step = gates.GateStep("content", "quill", "translation", "lingua", "t", ("true",), "")
    gates.write_gate_log(tmp_path, step, 7, True, "x" * 100_000)
    log = tmp_path / "gates" / "content-7.log"
    assert log.exists()
    assert stat.S_IMODE(log.stat().st_mode) == 0o600
    record = json.loads(log.read_text())
    assert record["passed"] is True
    assert len(record["output"]) <= gates.GATE_LOG_CAP


def test_write_gate_log_surfaces_persistence_failure(tmp_path, monkeypatch):
    step = gates.GateStep("content", "quill", "", "", "", ("true",), "")

    def fail_replace(*args):
        raise OSError("disk full")

    monkeypatch.setattr(gates.os, "replace", fail_replace)
    with pytest.raises(OSError, match="disk full"):
        gates.write_gate_log(tmp_path, step, 7, True, "ok")


def test_done_and_next_task_text():
    step = gates.step_for(_meta(STEPS), "content")
    done = gates.done_text(step, "content-check OK\n24 entries valid")
    assert done.startswith("#done content verified · gate:npm")
    assert "24 entries valid" in done
    nxt = gates.next_task_text(step)
    assert nxt.startswith("@lingua #task #translation")
    terminal = gates.GateStep("qa", "lens", "", "", "", ("true",), "")
    assert gates.next_task_text(terminal) is None


@pytest.mark.asyncio
async def test_gate_advance_posts_done_and_next(tmp_path, monkeypatch):
    from alpi import service

    home = tmp_path / "hub"
    home.mkdir()
    wg = types.SimpleNamespace(meta=types.SimpleNamespace(
        id="wg_x", hub_pubkey="HUB", pipeline=("content", "translation"),
        pipeline_steps=STEPS, paused=False,
    ))
    recent = [
        {"seq": 1, "from": "HUB", "text": "@quill #task #content write it"},
        {"seq": 2, "from": "QUILLPK", "text": "content complete · 24 files"},
    ]
    monkeypatch.setattr(
        "alpi.alp.peers.load",
        lambda h: [types.SimpleNamespace(id="quill", pubkey="QUILLPK")],
    )
    monkeypatch.setattr(
        "alpi.alp.pipeline_gates.run_gate", lambda step, ws: (True, "content-check OK"),
    )
    posted: list[str] = []

    async def fake_post(h, wid, text, cost=None):
        posted.append(text.decode())
        return {"seq": 3 + len(posted)}

    monkeypatch.setattr("alpi.alp.workgroup_client.post", fake_post)
    monkeypatch.setattr(service, "_set_hub_responded_seq", lambda *a: None)
    service._GATE_ATTEMPTED.clear()

    out = await service._maybe_gate_advance(home, wg, recent, "HUB")
    assert out is True
    assert posted[0].startswith("#done content verified · gate:")
    assert posted[1].startswith("@lingua #task #translation")
    assert (home / "alp" / "workgroups" / "wg_x" / "gates" / "content-2.log").exists()

    posted.clear()
    assert await service._maybe_gate_advance(home, wg, recent, "HUB") is None
    assert posted == []


@pytest.mark.asyncio
async def test_gate_advance_failure_returns_reason(tmp_path, monkeypatch):
    from alpi import service

    home = tmp_path / "hub"
    home.mkdir()
    wg = types.SimpleNamespace(meta=types.SimpleNamespace(
        id="wg_y", hub_pubkey="HUB", pipeline=("content", "translation"),
        pipeline_steps=STEPS, paused=False,
    ))
    recent = [
        {"seq": 1, "from": "HUB", "text": "@quill #task #content write it"},
        {"seq": 2, "from": "QUILLPK", "text": "content complete"},
    ]
    monkeypatch.setattr(
        "alpi.alp.peers.load",
        lambda h: [types.SimpleNamespace(id="quill", pubkey="QUILLPK")],
    )
    monkeypatch.setattr(
        "alpi.alp.pipeline_gates.run_gate",
        lambda step, ws: (False, "content thin: deluxe 49w < 50"),
    )
    service._GATE_ATTEMPTED.clear()

    out = await service._maybe_gate_advance(home, wg, recent, "HUB")
    assert isinstance(out, str) and "GATE content FAILED" in out and "49w" in out
    assert await service._maybe_gate_advance(home, wg, recent, "HUB") is None


@pytest.mark.asyncio
async def test_gate_advance_uses_owner_handoff_before_a_later_peer_post(
    tmp_path, monkeypatch,
):
    from alpi import service

    home = tmp_path / "hub"
    home.mkdir()
    wg = types.SimpleNamespace(meta=types.SimpleNamespace(
        id="wg_masked", hub_pubkey="HUB", pipeline=("content", "translation"),
        pipeline_steps=STEPS, paused=False,
    ))
    recent = [
        {"seq": 1, "from": "HUB", "text": "@quill #task #content write it"},
        {"seq": 2, "from": "QUILLPK", "text": "content complete"},
        {"seq": 3, "from": "OTHERPK", "text": "review note"},
    ]
    monkeypatch.setattr(
        "alpi.alp.peers.load",
        lambda h: [types.SimpleNamespace(id="quill", pubkey="QUILLPK")],
    )
    monkeypatch.setattr(
        "alpi.alp.pipeline_gates.run_gate", lambda step, ws: (True, "ok"),
    )
    posted: list[str] = []

    async def fake_post(h, wid, text, cost=None):
        posted.append(text.decode())
        return {"seq": 4 + len(posted)}

    monkeypatch.setattr("alpi.alp.workgroup_client.post", fake_post)
    monkeypatch.setattr(service, "_set_hub_responded_seq", lambda *a: None)
    service._GATE_ATTEMPTED.clear()
    assert await service._maybe_gate_advance(home, wg, recent, "HUB") is True
    assert posted[0].startswith("#done content verified")


@pytest.mark.asyncio
async def test_gate_does_not_advance_without_its_audit_log(
    tmp_path, monkeypatch,
):
    from alpi import service

    home = tmp_path / "hub"
    home.mkdir()
    wg = types.SimpleNamespace(meta=types.SimpleNamespace(
        id="wg_audit", hub_pubkey="HUB", pipeline=("content", "translation"),
        pipeline_steps=STEPS, paused=False,
    ))
    recent = [
        {"seq": 1, "from": "HUB", "text": "@quill #task #content write it"},
        {"seq": 2, "from": "QUILLPK", "text": "content complete"},
    ]
    monkeypatch.setattr(
        "alpi.alp.peers.load",
        lambda h: [types.SimpleNamespace(id="quill", pubkey="QUILLPK")],
    )
    monkeypatch.setattr(
        "alpi.alp.pipeline_gates.run_gate", lambda step, ws: (True, "ok"),
    )
    def fail_log(*args):
        raise OSError("disk full")

    monkeypatch.setattr("alpi.alp.pipeline_gates.write_gate_log", fail_log)
    posted: list[str] = []

    async def fake_post(*args, **kwargs):
        posted.append("called")

    monkeypatch.setattr("alpi.alp.workgroup_client.post", fake_post)
    service._GATE_ATTEMPTED.clear()
    out = await service._maybe_gate_advance(home, wg, recent, "HUB")
    assert isinstance(out, str) and "audit FAILED" in out
    assert posted == []


def test_local_wake_registration_is_recoverable(tmp_path):
    from alpi.alp import wakes

    seen: list[str] = []
    wakes.register(tmp_path, seen.append)
    wakes.fire(tmp_path, "wg_fast")
    wakes.unregister(tmp_path)
    wakes.fire(tmp_path, "wg_ignored")
    assert seen == ["wg_fast"]
