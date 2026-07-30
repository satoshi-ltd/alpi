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


OP_STEPS = {
    **STEPS,
    "build": {"owner": "pixel", "gate": {"cwd": "projects/casa", "argv": ["true"]}},
    "media-update": {
        "owner": "muse", "next": "media-qa", "task": "map the client media",
        "gate": {"cwd": "projects/casa", "argv": ["npm", "run", "assets:optimize"]},
    },
    "media-qa": {"owner": "lens", "gate": {"cwd": "projects/casa", "argv": ["true"]}},
}


def _op_meta():
    return types.SimpleNamespace(
        pipeline_steps=OP_STEPS,
        pipeline=("content", "translation", "build"),
        operations={"media-update": ("media-update", "media-qa")},
        paused=False,
    )


def test_step_for_resolves_operation_steps():
    step = gates.step_for(_op_meta(), "media-update")
    assert (step.owner, step.next_phase, step.next_owner) == ("muse", "media-qa", "lens")
    assert step.argv == ("npm", "run", "assets:optimize")


def test_step_for_resolves_an_operations_terminal_step():
    step = gates.step_for(_op_meta(), "media-qa")
    assert step.owner == "lens" and step.next_phase == ""
    assert gates.next_task_text(step) is None


def test_step_for_still_rejects_a_phase_in_no_chain():
    meta = _op_meta()
    meta.pipeline_steps = {**OP_STEPS, "stray": {"owner": "lens", "gate": {"cwd": "", "argv": ["true"]}}}
    assert gates.step_for(meta, "stray") is None


def test_chain_for_picks_the_owning_chain():
    meta = _op_meta()
    assert gates.chain_for(meta, "content") == ("content", "translation", "build")
    assert gates.chain_for(meta, "media-qa") == ("media-update", "media-qa")
    assert gates.chain_for(meta, "nope") is None
    assert gates.chain_for(types.SimpleNamespace(pipeline=(), operations={}), "x") == ()


def test_step_for_rejects_a_next_outside_its_own_chain():
    meta = _op_meta()
    meta.pipeline_steps = {**OP_STEPS, "media-update": {**OP_STEPS["media-update"], "next": "build"}}
    assert gates.step_for(meta, "media-update") is None


@pytest.mark.asyncio
async def test_operation_gate_posts_done_and_opens_its_next_step(tmp_path, monkeypatch):
    from alpi import service

    home = tmp_path / "hub"
    home.mkdir()
    wg = types.SimpleNamespace(meta=types.SimpleNamespace(
        id="wg_op", hub_pubkey="HUB", **{
            k: v for k, v in vars(_op_meta()).items()
        },
    ))
    recent = [
        {"seq": 1, "from": "HUB", "text": "@muse #task #media-update map the client media"},
        {"seq": 2, "from": "MUSEPK", "text": "manifest complete · 20 files mapped"},
    ]
    monkeypatch.setattr(
        "alpi.alp.peers.load",
        lambda h: [types.SimpleNamespace(id="muse", pubkey="MUSEPK")],
    )
    monkeypatch.setattr(
        "alpi.alp.pipeline_gates.run_gate", lambda step, ws: (True, "assets ready"),
    )
    posted: list[str] = []

    async def fake_post(h, wid, text, cost=None):
        posted.append(text.decode())
        return {"seq": 3 + len(posted)}

    monkeypatch.setattr("alpi.alp.workgroup_client.post", fake_post)
    monkeypatch.setattr(service, "_set_hub_responded_seq", lambda *a: None)
    service._GATE_ATTEMPTED.clear()

    assert await service._maybe_gate_advance(home, wg, recent, "HUB") is True
    assert posted[0].startswith("#done media-update verified · gate:")
    assert posted[1].startswith("@lens #task #media-qa")


@pytest.mark.asyncio
async def test_failing_operation_gate_does_not_advance(tmp_path, monkeypatch):
    from alpi import service

    home = tmp_path / "hub"
    home.mkdir()
    wg = types.SimpleNamespace(meta=types.SimpleNamespace(
        id="wg_op2", hub_pubkey="HUB", **{k: v for k, v in vars(_op_meta()).items()},
    ))
    recent = [
        {"seq": 1, "from": "HUB", "text": "@muse #task #media-update map it"},
        {"seq": 2, "from": "MUSEPK", "text": "manifest complete"},
    ]
    monkeypatch.setattr(
        "alpi.alp.peers.load",
        lambda h: [types.SimpleNamespace(id="muse", pubkey="MUSEPK")],
    )
    monkeypatch.setattr(
        "alpi.alp.pipeline_gates.run_gate",
        lambda step, ws: (False, "3 supplied slots have no derivative"),
    )
    posted: list[str] = []

    async def fake_post(h, wid, text, cost=None):
        posted.append(text.decode())
        return {"seq": 9}

    monkeypatch.setattr("alpi.alp.workgroup_client.post", fake_post)
    monkeypatch.setattr(service, "_set_hub_responded_seq", lambda *a: None)
    service._GATE_ATTEMPTED.clear()

    out = await service._maybe_gate_advance(home, wg, recent, "HUB")
    assert isinstance(out, str) and "derivative" in out
    assert posted == [], "a red gate never posts a #done"


@pytest.mark.parametrize("declared,ok", [
    ("media-qa", False),      # forward skip over media-config
    ("media-update", False),  # backwards
    ("", True),               # omitted → derived from the chain
    ("media-config", True),   # restates the chain
])
def test_operation_next_must_restate_the_chain_order(declared, ok):
    chain = ("media-update", "media-config", "media-qa")
    steps = {
        "media-update": {"owner": "muse", "gate": {"cwd": "p", "argv": ["true"]},
                         **({"next": declared} if declared else {})},
        "media-config": {"owner": "scout", "gate": {"cwd": "p", "argv": ["true"]}},
        "media-qa": {"owner": "lens", "gate": {"cwd": "p", "argv": ["true"]}},
    }
    meta = types.SimpleNamespace(
        pipeline_steps=steps, pipeline=("content",), operations={"media-update": chain},
    )
    step = gates.step_for(meta, "media-update")
    if not ok:
        assert step is None
    else:
        assert step is not None and step.next_phase == "media-config"
