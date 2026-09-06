from __future__ import annotations

import json

import pytest

from alpi.tools import _state
from alpi.tools import workgroup as tool_mod
from alpi.tools.workgroup import WorkgroupPostTool


def test_posts_declare_only_new_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    async def post(*args, **kwargs):
        calls.append(kwargs)
        return {"seq": len(calls), "ts": "now"}

    monkeypatch.setattr(tool_mod.wc, "post", post)
    monkeypatch.setattr(tool_mod, "get_home", lambda: None)
    monkeypatch.setenv("ALPI_WORKGROUP_TURN_ID", "b" * 32)
    _state.reset_turn_usage()
    _state.bump_turn_usage(100, 10, 0.01, 80)

    assert WorkgroupPostTool().run(wg_id="wg_x", text="#working build").ok
    _state.bump_turn_usage(50, 5, 0.004, 40)
    assert WorkgroupPostTool().run(wg_id="wg_x", text="build complete").ok

    assert calls[0]["cost"] == {
        "tokens_in": 100,
        "tokens_out": 10,
        "usd": 0.01,
        "cached_in": 80,
        "measured_in": 100,
        "tokens": 110,
    }
    assert calls[1]["cost"] == {
        "tokens_in": 50,
        "tokens_out": 5,
        "usd": pytest.approx(0.004),
        "cached_in": 40,
        "measured_in": 50,
        "tokens": 55,
    }
    assert {call["turn_id"] for call in calls} == {"b" * 32}


def test_rejected_post_does_not_consume_pending_usage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    costs = []

    async def post(*args, **kwargs):
        costs.append(kwargs["cost"])
        if len(costs) == 1:
            raise ValueError("rejected")
        return {"seq": 1, "ts": "now"}

    monkeypatch.setattr(tool_mod.wc, "post", post)
    monkeypatch.setattr(tool_mod, "get_home", lambda: None)
    _state.reset_turn_usage()
    _state.bump_turn_usage(75, 4, 0.02, 60)

    assert not WorkgroupPostTool().run(wg_id="wg_x", text="first").ok
    assert WorkgroupPostTool().run(wg_id="wg_x", text="retry").ok
    assert costs[0] == costs[1]


@pytest.mark.parametrize(
    "error",
    [
        tool_mod.alp_client.RemoteError(-32005, "rate-limited"),
        tool_mod.alp_client.RemoteError(-32007, "target-busy"),
        OSError("connection reset"),
    ],
)
def test_transient_post_failure_is_preserved(
    monkeypatch: pytest.MonkeyPatch, error: Exception,
) -> None:
    async def post(*args, **kwargs):
        raise error

    monkeypatch.setattr(tool_mod.wc, "post", post)
    monkeypatch.setattr(tool_mod, "get_home", lambda: None)

    result = WorkgroupPostTool().run(wg_id="wg_x", text="handoff")

    assert not result.ok
    assert result.transient is True


def test_semantic_post_rejection_is_not_transient(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def post(*args, **kwargs):
        raise tool_mod.alp_client.RemoteError(-32012, "gate-failed")

    monkeypatch.setattr(tool_mod.wc, "post", post)
    monkeypatch.setattr(tool_mod, "get_home", lambda: None)

    result = WorkgroupPostTool().run(wg_id="wg_x", text="handoff")

    assert not result.ok
    assert result.transient is False


def test_dispatch_turn_posts_to_its_own_workgroup_even_with_a_mistyped_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []

    async def post(home, wg_id, text, cost=None, turn_id=None):
        calls.append(wg_id)
        return {"seq": 7, "ts": "2026-09-04T00:00:00Z"}

    monkeypatch.setattr(tool_mod.wc, "post", post)
    monkeypatch.setattr(tool_mod, "get_home", lambda: None)
    monkeypatch.setenv("ALPI_WORKGROUP_TURN_ID", "c" * 32)
    monkeypatch.setenv("ALPI_WORKGROUP_DISPATCH", "wg_y3qtl5shxutlhyxq")
    _state.set_undeclared_turn_usage_for_tests(0.0, 0) if hasattr(_state, "set_undeclared_turn_usage_for_tests") else None

    result = WorkgroupPostTool().run(wg_id="wg_y3qt5lshxutlhyxq", text="setup done")
    assert result.ok, result.error
    assert calls == ["wg_y3qtl5shxutlhyxq"]
    assert "replaced by this turn's workgroup" in result.output

    result = WorkgroupPostTool().run(text="setup done again")
    assert result.ok, result.error
    assert calls[-1] == "wg_y3qtl5shxutlhyxq"


def test_gate_less_continuation_appends_the_pending_recheck_to_the_qa_opener(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []

    async def post(home, wg_id, text, cost=None, turn_id=None):
        calls.append(text.decode())
        return {"seq": 8, "ts": "2026-09-05T00:00:00Z"}

    monkeypatch.setattr(tool_mod.wc, "post", post)
    monkeypatch.setattr(tool_mod, "get_home", lambda: None)
    monkeypatch.setenv("ALPI_WORKGROUP_DISPATCH", "wg_target")
    monkeypatch.setenv("ALPI_WORKGROUP_RECHECK_PHASE", "qa")
    monkeypatch.setenv(
        "ALPI_WORKGROUP_RECHECK_SUFFIX",
        " · Re-verify each retained finding: room count is wrong",
    )

    result = WorkgroupPostTool().run(text="@lens #task #qa · audit the build")

    assert result.ok
    assert calls == [
        "@lens #task #qa · audit the build · Re-verify each retained finding: room count is wrong",
    ]


def test_gate_less_recheck_is_appended_to_the_opener_line_not_trailing_prose(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []

    async def post(home, wg_id, text, cost=None, turn_id=None):
        calls.append(text.decode())
        return {"seq": 8, "ts": "2026-09-05T00:00:00Z"}

    monkeypatch.setattr(tool_mod.wc, "post", post)
    monkeypatch.setattr(tool_mod, "get_home", lambda: None)
    monkeypatch.setenv("ALPI_WORKGROUP_DISPATCH", "wg_target")
    monkeypatch.setenv("ALPI_WORKGROUP_RECHECK_PHASE", "qa")
    monkeypatch.setenv("ALPI_WORKGROUP_RECHECK_SUFFIX", " · retained finding")

    result = WorkgroupPostTool().run(
        text="@lens #task #qa · audit the build\nThis line is not the opener",
    )

    assert result.ok
    assert calls == [
        "@lens #task #qa · audit the build · retained finding\nThis line is not the opener",
    ]


def test_member_turn_rejects_a_bare_working_post_but_keeps_finalizer_continuations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []

    async def post(home, wg_id, text, cost=None, turn_id=None):
        calls.append(text.decode())
        return {"seq": 3, "ts": "2026-09-04T00:00:00Z"}

    monkeypatch.setattr(tool_mod.wc, "post", post)
    monkeypatch.setattr(tool_mod, "get_home", lambda: None)
    monkeypatch.setenv("ALPI_WORKGROUP_TURN_ID", "d" * 32)
    monkeypatch.setenv("ALPI_WORKGROUP_DISPATCH", "wg_target")
    monkeypatch.setenv("ALPI_WORKGROUP_MEMBER_TURN", "1")
    from alpi.tools import _state
    _state.reset_turn_usage()
    _state.set_turn_tools_run(3)

    rejected = WorkgroupPostTool().run(text="#working starting the content batch")
    assert not rejected.ok
    assert "post only your handoff" in rejected.error
    assert calls == []

    assert WorkgroupPostTool().run(text="#working half written; next pages (continuation)").ok
    assert WorkgroupPostTool().run(text="#content delivered: 14 files").ok
    assert len(calls) == 2


def test_member_turn_rejects_a_handoff_before_any_tool_ran(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from alpi.tools import _state

    calls = []

    async def post(home, wg_id, text, cost=None, turn_id=None):
        calls.append(text.decode())
        return {"seq": 4, "ts": "2026-09-04T00:00:00Z"}

    monkeypatch.setattr(tool_mod.wc, "post", post)
    monkeypatch.setattr(tool_mod, "get_home", lambda: None)
    monkeypatch.setenv("ALPI_WORKGROUP_TURN_ID", "e" * 32)
    monkeypatch.setenv("ALPI_WORKGROUP_DISPATCH", "wg_target")
    monkeypatch.setenv("ALPI_WORKGROUP_MEMBER_TURN", "1")
    _state.reset_turn_usage()

    rejected = WorkgroupPostTool().run(text="@muse acknowledging #assets task; reading the briefing")
    assert not rejected.ok
    assert "nothing ran this turn" in rejected.error
    assert WorkgroupPostTool().run(text="#working resuming after the budget (continuation)").ok

    _state.set_turn_tools_run(1)
    assert WorkgroupPostTool().run(text="#assets delivered: manifest reconciled").ok
    assert len(calls) == 2


def _scoped_member(monkeypatch, tmp_path, calls, *, round_seq="7", paths='["src/content/**"]', phase=None):
    from alpi.tools import _paths, _state

    async def post(home, wg_id, text, cost=None, turn_id=None):
        calls.append(text.decode())
        return {"seq": 5 + len(calls), "ts": "2026-09-05T00:00:00Z"}

    workspace = tmp_path / "ws"
    project = workspace / "projects" / "x"
    (project / "src" / "content").mkdir(parents=True, exist_ok=True)
    (project / "src" / "content" / "home.es.json").write_text("{}", encoding="utf-8")
    (project / "notes.md").write_text("draft", encoding="utf-8")
    monkeypatch.setattr(_paths, "_configured_workspace", lambda: workspace)
    monkeypatch.setattr(tool_mod.wc, "post", post)
    monkeypatch.setattr(tool_mod, "get_home", lambda: None)
    monkeypatch.setenv("ALPI_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("ALPI_WORKGROUP_TURN_ID", "f" * 32)
    monkeypatch.setenv("ALPI_WORKGROUP_DISPATCH", "wg_target")
    monkeypatch.setenv("ALPI_WORKGROUP_MEMBER_TURN", "1")
    monkeypatch.setenv("ALPI_WORKGROUP_ROUND_HUB_SEQ", round_seq)
    monkeypatch.setenv("ALPI_WORKGROUP_WRITE_SCOPE", '{"root": "projects/x", "paths": ' + paths + '}')
    if phase:
        monkeypatch.setenv("ALPI_WORKGROUP_PHASE", phase)
    _state.reset_turn_usage()
    _state.snapshot_write_scope()
    _state.set_turn_tools_run(3)
    return project, tmp_path / "home" / "alp" / "scope_baselines" / "wg_target-7.json"


def test_member_turn_in_a_scoped_phase_must_change_an_owned_file(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    calls = []
    project, baseline = _scoped_member(monkeypatch, tmp_path, calls)
    assert baseline.is_file()

    for text in (
        "Starting #translation. Reading the contract and locale set.",
        "#skip nothing to do\nbut here is some prose too",
        "still working, see (continuation) later",
    ):
        rejected = WorkgroupPostTool().run(text=text)
        assert not rejected.ok, text
        assert "none changed since the round opened" in rejected.error
    assert WorkgroupPostTool().run(text="#working half done; next pages (continuation)").ok
    assert baseline.is_file()

    (project / "notes.md").write_text("edited outside the scope", encoding="utf-8")
    assert not WorkgroupPostTool().run(text="#translation delivered").ok

    (project / "src" / "content" / "home.en.json").write_text('{"lang": "en"}', encoding="utf-8")
    assert WorkgroupPostTool().run(text="#translation delivered: home.en.json").ok
    assert not baseline.exists()
    assert calls == ["#working half done; next pages (continuation)", "#translation delivered: home.en.json"]


def test_a_pipeline_handoff_must_name_its_phase(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    calls = []
    project, _ = _scoped_member(monkeypatch, tmp_path, calls, paths='["work/**", "src/config/site.json"]', phase="intake")
    (project / "work").mkdir()
    (project / "work" / "intake.md").write_text("| rooms | suite |", encoding="utf-8")

    for text in ("Now the full site.json first pass.", "#intakes done", "wrote #content not this phase"):
        rejected = WorkgroupPostTool().run(text=text)
        assert not rejected.ok, text
        assert "post `#intake done" in rejected.error
    assert calls == []
    assert WorkgroupPostTool().run(text="#skip the brief has no rooms").ok
    assert WorkgroupPostTool().run(text="#intake done — wrote work/intake.md and site.json").ok
    assert WorkgroupPostTool().run(text="@mira #intake repair round 1 — palette fixed").ok
    assert WorkgroupPostTool().run(text="#INTAKE · PASS · verdict for the record").ok
    assert len(calls) == 4


def test_a_phase_without_paths_still_requires_its_token(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    calls = []
    _scoped_member(monkeypatch, tmp_path, calls, paths="[]", phase="research")
    rejected = WorkgroupPostTool().run(text="I started the research; more work remains")
    assert not rejected.ok
    assert "post `#research done" in rejected.error
    assert WorkgroupPostTool().run(text="#research done — three sources compared in work/research.md").ok
    assert len(calls) == 1


def test_the_phase_token_guard_only_applies_to_pipeline_member_turns(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    calls = []
    project, _ = _scoped_member(monkeypatch, tmp_path, calls)
    (project / "src" / "content" / "home.es.json").write_text('{"a": 1}', encoding="utf-8")
    assert WorkgroupPostTool().run(text="delivered the home copy without a phase token").ok


def test_a_skip_alone_is_a_legitimate_empty_delivery(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    calls = []
    _, baseline = _scoped_member(monkeypatch, tmp_path, calls)
    assert WorkgroupPostTool().run(text="#skip nothing to translate: the brief declares a single locale").ok
    assert not baseline.exists()


def test_baseline_survives_a_continuation_and_resets_on_a_new_round(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    from alpi.tools import _state

    calls = []
    project, baseline = _scoped_member(monkeypatch, tmp_path, calls)
    (project / "src" / "content" / "rooms.en.json").write_text("{}", encoding="utf-8")
    assert WorkgroupPostTool().run(text="#working rooms done; pages next (continuation)").ok

    _state.reset_turn_usage()
    _state.snapshot_write_scope()
    _state.set_turn_tools_run(2)
    assert WorkgroupPostTool().run(text="#translation delivered after verifying").ok
    assert not baseline.exists()

    monkeypatch.setenv("ALPI_WORKGROUP_ROUND_HUB_SEQ", "9")
    _state.reset_turn_usage()
    _state.snapshot_write_scope()
    _state.set_turn_tools_run(2)
    rejected = WorkgroupPostTool().run(text="#translation delivered again")
    assert not rejected.ok
    assert (tmp_path / "home" / "alp" / "scope_baselines" / "wg_target-9.json").is_file()


def test_an_unverifiable_scope_refuses_the_handoff(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    from alpi.tools import _paths, _state

    calls = []
    _scoped_member(monkeypatch, tmp_path, calls)
    monkeypatch.setattr(_paths, "_configured_workspace", lambda: None)
    _state.reset_turn_usage()
    _state.snapshot_write_scope()
    _state.set_turn_tools_run(2)

    rejected = WorkgroupPostTool().run(text="#translation delivered")
    assert not rejected.ok
    assert "cannot be verified" in rejected.error
    assert "no workspace is configured" in rejected.error
    assert WorkgroupPostTool().run(text="#working still going (continuation)").ok


def test_a_phase_without_paths_is_not_guarded(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    calls = []
    _scoped_member(monkeypatch, tmp_path, calls, paths="[]")
    assert WorkgroupPostTool().run(text="#qa verdict · QA PASS").ok


def test_build_phase_scope_counts_generated_trees_as_deliverables(
    monkeypatch: pytest.MonkeyPatch, tmp_path,
) -> None:
    from alpi.tools import _paths, _state

    calls = []

    async def post(home, wg_id, text, cost=None, turn_id=None):
        calls.append(text.decode())
        return {"seq": 9, "ts": "2026-09-05T00:00:00Z"}

    workspace = tmp_path / "ws"
    project = workspace / "projects" / "x"
    (project / "node_modules" / "pkg").mkdir(parents=True)
    (project / "node_modules" / "pkg" / "index.js").write_text("module.exports = 1", encoding="utf-8")
    monkeypatch.setattr(_paths, "_configured_workspace", lambda: workspace)
    monkeypatch.setattr(tool_mod.wc, "post", post)
    monkeypatch.setattr(tool_mod, "get_home", lambda: None)
    monkeypatch.setenv("ALPI_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("ALPI_WORKGROUP_TURN_ID", "a" * 32)
    monkeypatch.setenv("ALPI_WORKGROUP_DISPATCH", "wg_target")
    monkeypatch.setenv("ALPI_WORKGROUP_MEMBER_TURN", "1")
    monkeypatch.setenv("ALPI_WORKGROUP_WRITE_SCOPE", '{"root": "projects/x", "paths": ["dist/**", "public/img/**", ".astro/**", "src/env.d.ts"]}')
    _state.reset_turn_usage()
    _state.snapshot_write_scope()
    _state.set_turn_tools_run(2)

    assert not WorkgroupPostTool().run(text="#build complete").ok

    (project / "dist" / "es").mkdir(parents=True)
    (project / "dist" / "es" / "index.html").write_text("<h1>ok</h1>", encoding="utf-8")
    assert WorkgroupPostTool().run(text="#build complete: dist/ ready").ok
    assert calls == ["#build complete: dist/ ready"]


def test_baseline_state_is_never_counted_as_a_deliverable(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    from alpi.tools import _paths, _state

    calls = []
    _scoped_member(monkeypatch, tmp_path, calls, paths='["**"]')
    workspace = tmp_path / "ws"
    home_inside = workspace / "projects" / "x" / ".alpi"
    monkeypatch.setenv("ALPI_HOME", str(home_inside))
    monkeypatch.setattr(_paths, "_configured_workspace", lambda: workspace)
    _state.reset_turn_usage()
    _state.snapshot_write_scope()
    _state.set_turn_tools_run(2)
    assert (home_inside / "alp" / "scope_baselines" / "wg_target-7.json").is_file()

    rejected = WorkgroupPostTool().run(text="#setup complete")
    assert not rejected.ok
    assert "none changed since the round opened" in rejected.error


def test_baseline_is_bound_to_the_resolved_scope(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    from alpi.tools import _paths, _state

    calls = []
    _scoped_member(monkeypatch, tmp_path, calls)
    other = tmp_path / "ws-b"
    (other / "projects" / "x" / "src" / "content").mkdir(parents=True)
    (other / "projects" / "x" / "src" / "content" / "other.es.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(_paths, "_configured_workspace", lambda: other)
    _state.reset_turn_usage()
    _state.snapshot_write_scope()
    _state.set_turn_tools_run(2)

    rejected = WorkgroupPostTool().run(text="#translation delivered")
    assert not rejected.ok
    baseline = json.loads((tmp_path / "home" / "alp" / "scope_baselines" / "wg_target-7.json").read_text())
    assert baseline["scope"]["root"] == str((other / "projects" / "x").resolve())
    assert set(baseline["files"]) == {"src/content/other.es.json"}


def test_baselines_are_member_only_pruned_per_workgroup_and_written_atomically(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    from alpi.tools import _state

    calls = []
    _scoped_member(monkeypatch, tmp_path, calls)
    baselines = tmp_path / "home" / "alp" / "scope_baselines"
    stale = baselines / "wg_target-3.json"
    stale.write_text("{}", encoding="utf-8")
    unrelated = baselines / "wg_other-3.json"
    unrelated.write_text("{}", encoding="utf-8")

    monkeypatch.setenv("ALPI_WORKGROUP_ROUND_HUB_SEQ", "8")
    _state.reset_turn_usage()
    _state.snapshot_write_scope()
    assert sorted(p.name for p in baselines.glob("*")) == ["wg_other-3.json", "wg_target-8.json"]
    assert not list(baselines.glob(".baseline-*"))

    monkeypatch.setenv("ALPI_WORKGROUP_MEMBER_TURN", "0")
    monkeypatch.setenv("ALPI_WORKGROUP_ROUND_HUB_SEQ", "10")
    _state.reset_turn_usage()
    _state.snapshot_write_scope()
    assert not (baselines / "wg_target-10.json").exists()
