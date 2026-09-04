import json
import signal
import stat
import sys
import types
import pytest

from alpi.alp import pipeline_gates as gates
from alpi.alp import workgroup as wg_mod


LAUNCH_CHAIN = ("content", "translation", "build")


def _meta(steps, pipelines=None, launch_pipeline="content"):
    chains = {LAUNCH_CHAIN[0]: LAUNCH_CHAIN} if pipelines is None else pipelines
    return types.SimpleNamespace(
        pipeline_steps=steps,
        pipelines={k: tuple(v) for k, v in chains.items()},
        launch_pipeline=launch_pipeline,
    )


STEPS = {
    "content": {
        "owner": "quill",
        "task": "translate every source entry into the declared locales",
        "gate": {"cwd": "projects/casa", "argv": ["npm", "run", "content-check"]},
    },
    "translation": {"owner": "lingua", "task": "ship it",
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


def test_step_for_rejects_a_malformed_or_ownerless_successor():
    malformed = {**STEPS, "translation": "junk"}
    assert gates.step_for(_meta(malformed), "content") is None
    ownerless = {**STEPS, "translation": {"gate": {"cwd": "", "argv": ["true"]}}}
    assert gates.step_for(_meta(ownerless), "content") is None


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


def test_gate_log_does_not_recreate_a_removed_workgroup(tmp_path):
    from alpi.alp import subscription as sub_mod

    home = tmp_path / "home"
    wg_dir = home / "alp" / "workgroups" / "wg_removed"
    sub_mod.tombstone(home, wg_dir.name)
    step = gates.GateStep("intake", "scout", "", "", "", ("true",), "")

    with pytest.raises(FileNotFoundError):
        gates.write_gate_log(wg_dir, step, 10, True, "clean")

    assert not wg_dir.exists()


def test_gate_log_record_belongs_to_the_delivery_in_its_filename(tmp_path):
    step = gates.GateStep("content", "quill", "", "", "", ("true",), "")
    gates.write_gate_log(tmp_path, step, 7, True, "clean")
    log = tmp_path / "gates" / "content-7.log"
    record = json.loads(log.read_text())
    record["task_seq"] = 6
    log.write_text(json.dumps(record))

    assert gates.gate_log_record(tmp_path, "content", 7) is None
    assert gates.gate_log_verdict(tmp_path, "content", 7) is None


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
        id="wg_x", hub_pubkey="HUB",
        pipelines={"content": ("content", "translation")},
        launch_pipeline="content",
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
        id="wg_y", hub_pubkey="HUB",
        pipelines={"content": ("content", "translation")},
        launch_pipeline="content",
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
        lambda step, ws: (False, "\n".join([
            "Checking artifact: content",
            "PASS  config is valid",
            "INFO  optional collection is empty",
            "content thin: deluxe 49w < 50",
        ])),
    )
    service._GATE_ATTEMPTED.clear()

    out = await service._maybe_gate_advance(home, wg, recent, "HUB")
    assert isinstance(out, str) and "GATE content FAILED" in out and "49w" in out
    assert await service._maybe_gate_advance(home, wg, recent, "HUB") is None


def test_gate_findings_excerpt_drops_noise_and_keeps_complete_lines():
    from alpi.alp.pipeline_gates import findings_excerpt

    output = "\n".join([
        "Checking artifact: content",
        "PASS  config is valid",
        "INFO  optional collection is empty",
        "CHECK content FAILED — fix these before handoff:",
        "  src/content/offers/direct.es.json:2  NAME DIFFERS FROM INTAKE",
        "content check failed with 1 blocking finding.",
    ])

    excerpt = findings_excerpt(output, 120)

    assert "PASS" not in excerpt
    assert "INFO" not in excerpt
    assert not excerpt.startswith("ffers/")
    assert "NAME DIFFERS FROM INTAKE" in excerpt
    assert "1 blocking finding" in excerpt


def test_gate_findings_excerpt_keeps_the_tail_of_an_oversized_final_error():
    from alpi.alp.pipeline_gates import findings_excerpt

    output = "\n".join([
        *(f"WARN  stale diagnostic {i}" for i in range(20)),
        "CHECK content FAILED — " + ("x" * 180) + " FINAL ROOT CAUSE",
    ])

    excerpt = findings_excerpt(output, 96)

    assert len(excerpt) <= 96
    assert excerpt.startswith("…")
    assert "FINAL ROOT CAUSE" in excerpt
    assert "stale diagnostic" not in excerpt


def test_gate_findings_excerpt_honors_degenerate_limits():
    assert gates.findings_excerpt("long failure", 0) == ""
    assert gates.findings_excerpt("long failure", 1) == "…"


def test_default_gate_findings_include_every_blocking_line():
    findings = [
        f"  src/content/rooms/room-{index}.es.json:1  INVALID CONTENT SCHEMA: field {index}"
        for index in range(16)
    ]
    output = "\n".join([
        "Checking artifact: content",
        "CHECK content FAILED — fix these before handoff:",
        *findings,
        "content check failed with 16 blocking findings.",
    ])

    excerpt = gates.findings_excerpt(output)

    assert all(finding in excerpt for finding in findings)
    assert excerpt.count(findings[0]) == 1
    assert "16 blocking findings" in excerpt


@pytest.mark.asyncio
async def test_gate_advance_uses_owner_handoff_before_a_later_peer_post(
    tmp_path, monkeypatch,
):
    from alpi import service

    home = tmp_path / "hub"
    home.mkdir()
    wg = types.SimpleNamespace(meta=types.SimpleNamespace(
        id="wg_masked", hub_pubkey="HUB",
        pipelines={"content": ("content", "translation")},
        launch_pipeline="content",
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
async def test_gate_success_leaves_a_hub_owned_successor_actionable(
    tmp_path, monkeypatch,
):
    from alpi import service

    home = tmp_path / "hub"
    home.mkdir()
    steps = {
        "content": STEPS["content"],
        "review": {"owner": "mira", "task": "triage the review"},
    }
    wg = types.SimpleNamespace(meta=types.SimpleNamespace(
        id="wg_hub_next", hub_pubkey="HUB",
        pipelines={"content": ("content", "review")},
        launch_pipeline="content", pipeline_steps=steps, paused=False,
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
    monkeypatch.setattr(
        "alpi.alp.workgroup_client._hub_owns_phase",
        lambda h, candidate, slug: slug == "review",
    )
    posted: list[dict] = []

    async def fake_post(h, wid, text, cost=None):
        row = {"seq": 3 + len(posted), "from": "HUB", "text": text.decode()}
        posted.append(row)
        return {"seq": row["seq"]}

    cursor: list[int] = []
    monkeypatch.setattr("alpi.alp.workgroup_client.post", fake_post)
    monkeypatch.setattr(
        service, "_set_hub_responded_seq", lambda h, wid, seq: cursor.append(seq),
    )
    service._GATE_ATTEMPTED.clear()

    assert await service._maybe_gate_advance(home, wg, recent, "HUB") is True
    assert cursor == [posted[0]["seq"]]
    trigger, _ = service._should_dispatch(
        "mira", "HUB", [*recent, *posted], cursor[0],
        hub_pubkey="HUB", pipeline=True,
        hub_owned_phases=frozenset({"review"}),
    )
    assert trigger == f"hub-owned #task opened (seq #{posted[1]['seq']})"


@pytest.mark.asyncio
async def test_gate_does_not_advance_without_its_audit_log(
    tmp_path, monkeypatch,
):
    from alpi import service

    home = tmp_path / "hub"
    home.mkdir()
    wg = types.SimpleNamespace(meta=types.SimpleNamespace(
        id="wg_audit", hub_pubkey="HUB",
        pipelines={"content": ("content", "translation")},
        launch_pipeline="content",
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
        "owner": "muse", "task": "map the client media",
        "gate": {"cwd": "projects/casa", "argv": ["npm", "run", "assets:optimize"]},
    },
    "media-qa": {"owner": "lens", "gate": {"cwd": "projects/casa", "argv": ["true"]}},
}


def _op_meta():
    return types.SimpleNamespace(
        pipeline_steps=OP_STEPS,
        pipelines={
            "content": ("content", "translation", "build"),
            "media-update": ("media-update", "media-qa"),
        },
        launch_pipeline="content",
        paused=False,
    )


def test_step_for_resolves_a_dormant_chain_step():
    step = gates.step_for(_op_meta(), "media-update")
    assert (step.owner, step.next_phase, step.next_owner) == ("muse", "media-qa", "lens")
    assert step.argv == ("npm", "run", "assets:optimize")


def test_step_for_resolves_a_dormant_chain_terminal_step():
    step = gates.step_for(_op_meta(), "media-qa")
    assert step.owner == "lens" and step.next_phase == ""
    assert gates.next_task_text(step) is None


def test_step_for_resolves_a_chain_in_a_launchless_workgroup():
    meta = _op_meta()
    meta.launch_pipeline = None
    step = gates.step_for(meta, "media-update")
    assert step is not None and step.next_phase == "media-qa"


def test_step_for_still_rejects_a_phase_in_no_chain():
    meta = _op_meta()
    meta.pipeline_steps = {**OP_STEPS, "stray": {"owner": "lens", "gate": {"cwd": "", "argv": ["true"]}}}
    assert gates.step_for(meta, "stray") is None


def test_chain_for_picks_the_owning_chain():
    meta = _op_meta()
    assert gates.chain_for(meta, "content") == ("content", "translation", "build")
    assert gates.chain_for(meta, "media-qa") == ("media-update", "media-qa")
    assert gates.chain_for(meta, "nope") is None
    assert gates.chain_for(types.SimpleNamespace(pipelines={}), "x") == ()


def test_step_for_ignores_an_author_next_and_stays_in_its_own_chain():
    meta = _op_meta()
    meta.pipeline_steps = {**OP_STEPS, "media-update": {**OP_STEPS["media-update"], "next": "build"}}
    step = gates.step_for(meta, "media-update")
    assert step is not None and step.next_phase == "media-qa"


CHAINS = {
    "content": ("content", "translation", "build"),
    "media-update": ("media-update", "media-config", "media-qa"),
}
CHAIN_OWNERS = {
    "content": "quill", "translation": "lingua", "build": "pixel",
    "media-update": "muse", "media-config": "scout", "media-qa": "lens",
}


def _chain_meta(gated=True):
    steps = {
        phase: {
            "owner": owner, "task": f"run the {phase} phase",
            **({"gate": {"cwd": "p", "argv": ["true"]}} if gated else {}),
        }
        for phase, owner in CHAIN_OWNERS.items()
    }
    return types.SimpleNamespace(
        pipeline_steps=steps, pipelines=CHAINS, launch_pipeline="content",
    )


def test_step_next_phase_is_the_declared_successor_in_every_chain():
    meta = _chain_meta()
    for chain in CHAINS.values():
        for index, phase in enumerate(chain[:-1]):
            step = gates.step_for(meta, phase)
            assert step is not None
            assert step.next_phase == wg_mod.pipeline_successor(meta, phase)
            assert step.next_phase == chain[index + 1]
            assert step.next_owner == CHAIN_OWNERS[chain[index + 1]]


def test_every_chain_terminal_phase_has_no_successor():
    meta = _chain_meta()
    for chain in CHAINS.values():
        step = gates.step_for(meta, chain[-1])
        assert wg_mod.pipeline_successor(meta, chain[-1]) == ""
        assert step is not None and step.next_phase == ""
        assert gates.next_task_text(step) is None


def test_gated_and_gateless_chains_order_identically():
    gated, gateless = _chain_meta(), _chain_meta(gated=False)
    for chain in CHAINS.values():
        for phase in chain:
            assert (
                wg_mod.pipeline_successor(gated, phase)
                == wg_mod.pipeline_successor(gateless, phase)
            )
            assert gates.chain_for(gated, phase) == gates.chain_for(gateless, phase)
            assert gates.step_for(gateless, phase) is None
    assert gates.step_for(gated, "content").next_phase == "translation"


def test_exact_membership_wins_before_suffix_recovery():
    meta = _meta({}, pipelines={
        "content": ("content", "translation"),
        "content-fix": ("content-fix", "content-audit"),
    })
    assert wg_mod.canonical_pipeline_phase(meta, "content-fix") == (
        "content-fix", "content-fix",
    )
    assert wg_mod.pipeline_successor(meta, "content-fix") == "content-audit"


def test_a_declared_fix_phase_resolves_to_itself():
    meta = _meta({}, pipelines={"content": ("content", "content-fix", "build")})
    assert wg_mod.canonical_pipeline_phase(meta, "content-fix") == (
        "content", "content-fix",
    )
    assert wg_mod.pipeline_successor(meta, "content-fix") == "build"


@pytest.mark.parametrize("slug,base", [
    ("content-fix", "content"),
    ("content-recheck", "content"),
    ("translation-fix", "translation"),
    ("content-anything", "content"),
    ("content-fix-fix", "content"),
    ("content-rechecked", "content"),
    ("content-update", "content"),
    ("fix", None),
    ("nosuchphase-fix", None),
])
def test_any_suffix_recovers_to_its_declared_phase(slug, base):
    """A two-suffix allowlist froze a run for 80 minutes on an invented `-repair`."""
    meta = _meta({})
    resolved = wg_mod.canonical_pipeline_phase(meta, slug)
    if base is None:
        assert resolved is None
    else:
        assert resolved == ("content", base)


def test_a_declared_chain_phase_still_wins_over_its_prefix():
    meta = _meta({}, pipelines={
        "content": ("content", "build"),
        "content-update": ("content-update", "content-build"),
    })
    assert wg_mod.canonical_pipeline_phase(meta, "content-update") == (
        "content-update", "content-update",
    )


@pytest.mark.asyncio
async def test_gate_failure_posts_repair_note_to_the_owner(tmp_path, monkeypatch):
    from alpi import service

    home = tmp_path / "hub"
    home.mkdir()
    wg = types.SimpleNamespace(meta=types.SimpleNamespace(
        id="wg_r", hub_pubkey="HUB",
        pipelines={"content": ("content", "translation")},
        launch_pipeline="content",
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
        lambda step, ws: (False, "\n".join([
            "Checking artifact: content",
            "PASS  config is valid",
            "INFO  optional collection is empty",
            "content thin: deluxe 49w < 50",
        ])),
    )
    posted: list[str] = []

    async def fake_post(h, wid, text, cost=None):
        posted.append(text.decode())
        return {"seq": 3 + len(posted)}

    monkeypatch.setattr("alpi.alp.workgroup_client.post", fake_post)
    cursor: list[int] = []
    monkeypatch.setattr(service, "_set_hub_responded_seq", lambda h, w, s: cursor.append(s))
    service._GATE_ATTEMPTED.clear()
    service._GATE_REPAIRS.clear()
    service._GATE_REPAIR_RETRY.clear()

    out = await service._maybe_gate_advance(home, wg, recent, "HUB")
    assert out is True
    assert len(posted) == 1
    assert posted[0].startswith("@quill gate red on #content (repair round 1/3)")
    assert "49w" in posted[0]
    assert "PASS" not in posted[0]
    assert "INFO" not in posted[0]
    assert cursor and cursor[-1] == 4


@pytest.mark.asyncio
async def test_gate_repair_note_posts_all_blocking_findings(tmp_path, monkeypatch):
    from alpi import service

    home = tmp_path / "hub-complete-findings"
    home.mkdir()
    wg = types.SimpleNamespace(meta=types.SimpleNamespace(
        id="wg_complete_findings", hub_pubkey="HUB",
        pipelines={"content": ("content", "translation")},
        launch_pipeline="content", pipeline_steps=STEPS, paused=False,
    ))
    recent = [
        {"seq": 1, "from": "HUB", "text": "@quill #task #content write it"},
        {"seq": 2, "from": "QUILLPK", "text": "content complete"},
    ]
    findings = [
        f"src/content/rooms/room-{index}.es.json:1 INVALID CONTENT SCHEMA: field {index}"
        for index in range(16)
    ]
    monkeypatch.setattr(
        "alpi.alp.peers.load",
        lambda h: [types.SimpleNamespace(id="quill", pubkey="QUILLPK")],
    )
    monkeypatch.setattr(
        "alpi.alp.pipeline_gates.run_gate",
        lambda step, ws: (False, "\n".join(findings)),
    )
    posted = []

    async def fake_post(h, wid, text, cost=None):
        posted.append(text.decode())
        return {"seq": 3}

    monkeypatch.setattr("alpi.alp.workgroup_client.post", fake_post)
    monkeypatch.setattr(service, "_set_hub_responded_seq", lambda *a: None)
    service._GATE_ATTEMPTED.clear()
    service._GATE_REPAIRS.clear()
    service._GATE_REPAIR_RETRY.clear()

    assert await service._maybe_gate_advance(home, wg, recent, "HUB") is True
    assert all(finding in posted[0] for finding in findings)
    assert max(service._GATE_REPAIRS.values()) == 1


@pytest.mark.asyncio
async def test_gate_failure_past_the_repair_cap_wakes_the_hub(tmp_path, monkeypatch):
    from alpi import service

    home = tmp_path / "hub"
    home.mkdir()
    project = home / "projects" / "casa"
    project.mkdir(parents=True)
    wg = types.SimpleNamespace(meta=types.SimpleNamespace(
        id="wg_c", hub_pubkey="HUB",
        pipelines={"content": ("content", "translation")},
        launch_pipeline="content",
        pipeline_steps=STEPS, paused=False,
    ))
    monkeypatch.setattr(
        "alpi.alp.peers.load",
        lambda h: [types.SimpleNamespace(id="quill", pubkey="QUILLPK")],
    )
    monkeypatch.setattr(
        "alpi.alp.pipeline_gates.run_gate", lambda step, ws: (False, "still red"),
    )

    async def fake_post(h, wid, text, cost=None):
        return {"seq": 99}

    monkeypatch.setattr("alpi.alp.workgroup_client.post", fake_post)
    monkeypatch.setattr(service, "_set_hub_responded_seq", lambda *a: None)
    service._GATE_ATTEMPTED.clear()
    service._GATE_REPAIRS.clear()

    for attempt in range(1, 4):
        (project / "artifact.txt").write_text(f"repair {attempt}\n")
        recent = [
            {"seq": 1, "from": "HUB", "text": "@quill #task #content write it"},
            {"seq": 1 + attempt, "from": "QUILLPK", "text": f"delivery {attempt}"},
        ]
        assert await service._maybe_gate_advance(home, wg, recent, "HUB") is True

    recent = [
        {"seq": 1, "from": "HUB", "text": "@quill #task #content write it"},
        {"seq": 9, "from": "QUILLPK", "text": "delivery 4"},
    ]
    (project / "artifact.txt").write_text("repair 4\n")
    out = await service._maybe_gate_advance(home, wg, recent, "HUB")
    assert isinstance(out, str)
    assert isinstance(out, service._GateRepairExhausted)
    assert "GATE content FAILED after 4 repair rounds" in out
    assert "#done BLOCKED" in out
    assert "exactly once" in out
    assert "Do not re-open" in out
    assert "skipped" not in out.lower()


@pytest.mark.asyncio
async def test_failed_repair_note_does_not_exhaust_the_repair_ladder(
    tmp_path, monkeypatch,
):
    from alpi import service

    home = tmp_path / "hub-repair-post"
    home.mkdir()
    wg = types.SimpleNamespace(meta=types.SimpleNamespace(
        id="wg_repair_post", hub_pubkey="HUB",
        pipelines={"content": ("content", "translation")},
        launch_pipeline="content", pipeline_steps=STEPS, paused=False,
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
        "alpi.alp.pipeline_gates.run_gate", lambda step, ws: (False, "still red"),
    )

    async def failed_post(*args, **kwargs):
        raise OSError("temporary write failure")

    monkeypatch.setattr("alpi.alp.workgroup_client.post", failed_post)
    service._GATE_ATTEMPTED.clear()
    service._GATE_REPAIRS.clear()
    service._GATE_REPAIR_RETRY.clear()

    out = await service._maybe_gate_advance(home, wg, recent, "HUB")

    assert isinstance(out, str)
    assert not isinstance(out, service._GateRepairExhausted)
    assert "repair round 1/3 could not be delivered" in out
    assert "repair ladder is not exhausted" in out
    assert service._GATE_REPAIRS == {}
    assert service._GATE_REPAIR_RETRY


@pytest.mark.asyncio
async def test_failed_repair_note_retries_same_round_after_gate_cooldown(
    tmp_path, monkeypatch,
):
    from alpi import service

    home = tmp_path / "hub-repair-retry"
    home.mkdir()
    wg = types.SimpleNamespace(meta=types.SimpleNamespace(
        id="wg_repair_retry", hub_pubkey="HUB",
        pipelines={"content": ("content", "translation")},
        launch_pipeline="content", pipeline_steps=STEPS, paused=False,
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
        "alpi.alp.pipeline_gates.run_gate", lambda step, ws: (False, "still red"),
    )
    calls = 0
    posted: list[str] = []

    async def flaky_post(h, wid, text, cost=None):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OSError("temporary write failure")
        posted.append(text.decode())
        return {"seq": 3}

    monkeypatch.setattr("alpi.alp.workgroup_client.post", flaky_post)
    monkeypatch.setattr(service, "_GATE_RECHECK_SECONDS", 0)
    monkeypatch.setattr(service, "_set_hub_responded_seq", lambda *a: None)
    service._GATE_ATTEMPTED.clear()
    service._GATE_REPAIRS.clear()
    service._GATE_REPAIR_RETRY.clear()

    first = await service._maybe_gate_advance(home, wg, recent, "HUB")
    second = await service._maybe_gate_advance(home, wg, recent, "HUB")

    assert "could not be delivered" in first
    assert second is True
    assert posted and "repair round 1/3" in posted[0]
    assert max(service._GATE_REPAIRS.values()) == 1
    assert not service._GATE_REPAIR_RETRY


@pytest.mark.asyncio
async def test_gate_repair_exhaustion_dispatches_as_final_repair(
    tmp_path, monkeypatch,
):
    from alpi import service
    from alpi.alp.keys import load_or_generate

    home = tmp_path / "hub-exhausted"
    home.mkdir()
    hub_pubkey = load_or_generate(home).pubkey_b64()
    wg = types.SimpleNamespace(meta=types.SimpleNamespace(
        id="wg_exhausted", name="site", hub_pubkey=hub_pubkey, paused=False,
        pipelines={"setup": ("content",)}, launch_pipeline="setup",
        pipeline_steps={}, quorum_timeout_seconds=0,
    ))
    recent = [
        {"seq": 1, "from": hub_pubkey, "text": "@quill #task #content write it"},
        {"seq": 9, "from": "QUILLPK", "text": "delivery 4"},
    ]
    exhausted = service._GateRepairExhausted(
        "GATE content FAILED after 4 repair rounds — close exactly once and stop",
    )

    async def fake_gate(*args):
        return exhausted

    captured = {}

    def fake_turn(*args, **kwargs):
        captured["reason"] = args[4]
        captured.update(kwargs)
        return None

    monkeypatch.setattr(service, "_maybe_gate_advance", fake_gate)
    monkeypatch.setattr(service, "_should_dispatch", lambda *a, **k: (None, 9))
    monkeypatch.setattr(service, "_hub_owned_phases", lambda *a: frozenset())
    monkeypatch.setattr(service, "_hub_phase_turn_budget", lambda *a: 0)
    monkeypatch.setattr(service, "_phase_write_scope", lambda *a: {"root": "", "paths": []})
    monkeypatch.setattr(service, "_budget_blocks_dispatch", lambda *a: False)
    monkeypatch.setattr(service, "_latest_hub_task_seq_for", lambda *a: 1)
    monkeypatch.setattr(service, "_dispatch_workgroup_turn", fake_turn)
    monkeypatch.setattr(service, "_spawn_dispatch", lambda *a: None)

    await service._maybe_dispatch_for_hub(home, "mira", wg, recent)

    assert captured["reason"] == exhausted
    assert captured["final_repair"] is True
    assert captured["closure_only"] is True


@pytest.mark.asyncio
async def test_gate_advance_moves_the_hub_cursor_past_its_own_posts(tmp_path, monkeypatch):
    from alpi import service

    home = tmp_path / "hub"
    home.mkdir()
    wg = types.SimpleNamespace(meta=types.SimpleNamespace(
        id="wg_m", hub_pubkey="HUB",
        pipelines={"content": ("content", "translation")},
        launch_pipeline="content",
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
        "alpi.alp.pipeline_gates.run_gate", lambda step, ws: (True, "OK"),
    )
    seqs = iter([3, 4])

    async def fake_post(h, wid, text, cost=None):
        return {"seq": next(seqs)}

    monkeypatch.setattr("alpi.alp.workgroup_client.post", fake_post)
    cursor: list[int] = []
    monkeypatch.setattr(service, "_set_hub_responded_seq", lambda h, w, s: cursor.append(s))
    service._GATE_ATTEMPTED.clear()
    service._GATE_REPAIRS.clear()

    assert await service._maybe_gate_advance(home, wg, recent, "HUB") is True
    assert cursor == [4]


@pytest.mark.asyncio
async def test_each_delivery_gets_its_own_gate_run(tmp_path, monkeypatch):
    """Keyed by phase alone, a second delivery would replay the first verdict."""
    from alpi import service

    home = tmp_path / "hub"
    home.mkdir()
    wg = types.SimpleNamespace(meta=types.SimpleNamespace(
        id="wg_two", hub_pubkey="HUB",
        pipelines={"content": ("content", "translation")},
        launch_pipeline="content",
        pipeline_steps=STEPS, paused=False,
    ))
    monkeypatch.setattr(
        "alpi.alp.peers.load",
        lambda h: [types.SimpleNamespace(id="quill", pubkey="QUILLPK")],
    )
    runs: list[int] = []
    monkeypatch.setattr(
        "alpi.alp.pipeline_gates.run_gate",
        lambda step, ws: (runs.append(1), (False, "still thin"))[1],
    )

    async def fake_post(h, wid, text, cost=None):
        return {"seq": 99}

    monkeypatch.setattr("alpi.alp.workgroup_client.post", fake_post)
    monkeypatch.setattr(service, "_set_hub_responded_seq", lambda h, w, s: None)
    service._GATE_ATTEMPTED.clear()
    service._GATE_REPAIRS.clear()

    first = [
        {"seq": 1, "from": "HUB", "text": "@quill #task #content write it"},
        {"seq": 2, "from": "QUILLPK", "text": "content complete"},
    ]
    await service._maybe_gate_advance(home, wg, first, "HUB")
    await service._maybe_gate_advance(home, wg, first, "HUB")
    assert len(runs) == 1, "the same delivery must not be re-gated"

    second = first + [{"seq": 5, "from": "QUILLPK", "text": "fixed and re-delivered"}]
    await service._maybe_gate_advance(home, wg, second, "HUB")
    assert len(runs) == 2, "a new delivery must get its own gate run"


@pytest.mark.parametrize("payload", [
    "[]",
    '{"phase": "content", "task_seq": "oops", "passed": true}',
    '{"phase": "content", "task_seq": 7, "passed": "false"}',
])
def test_a_malformed_gate_record_never_reads_as_a_verdict(tmp_path, payload):
    """`passed: "false"` is truthy — a red gate must not read as green."""
    from alpi.alp import pipeline_gates as gates

    d = tmp_path / "wg"
    (d / "gates").mkdir(parents=True)
    (d / "gates" / "content-7.log").write_text(payload, encoding="utf-8")
    assert gates.gate_log_record(d, "content", 7) is None
    assert gates.gate_log_verdict(d, "content", 7) is None
