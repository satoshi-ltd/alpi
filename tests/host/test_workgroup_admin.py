"""Workgroup admin host verbs — create / update / add_member / remove."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest

from alpi.alp.keys import load_or_generate
from alpi.host import server as host_server
from alpi.host import workgroup_admin


@pytest.fixture
def short_tmp():
    d = Path(tempfile.mkdtemp(prefix="alp-host-wgadmin-", dir="/tmp"))
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


def _seed(home: Path) -> None:
    home.mkdir(parents=True, exist_ok=True)
    load_or_generate(home)


@pytest.mark.asyncio
async def test_create_workgroup_returns_id(short_tmp: Path, monkeypatch) -> None:
    home = short_tmp / "h"
    _seed(home)
    from alpi import home as home_mod
    monkeypatch.setattr(home_mod, "_ROOT", short_tmp)
    monkeypatch.setattr(home_mod, "home_for", lambda profile: home)

    srv = host_server.Server(home=home)
    workgroup_admin.register(srv)

    body = {
        "id": "r",
        "method": "host.workgroup.create",
        "params": {"profile": "default", "name": "research", "members": []},
    }
    resp = await srv._dispatch(body)
    assert "result" in resp, resp
    assert resp["result"]["wg_id"]
    assert resp["result"]["members"] == 1  # hub itself


@pytest.mark.asyncio
async def test_create_workgroup_never_declares_a_pipeline(short_tmp: Path, monkeypatch) -> None:
    home = short_tmp / "h"
    _seed(home)
    from alpi import home as home_mod
    from alpi.alp import workgroup as wg_mod
    monkeypatch.setattr(home_mod, "_ROOT", short_tmp)
    monkeypatch.setattr(home_mod, "home_for", lambda profile: home)

    srv = host_server.Server(home=home)
    workgroup_admin.register(srv)

    for i, extra in enumerate((
        {"pipeline": "intake, content, build, qa"},
        {"pipeline": ["Intake", "QA"]},
        {"pipeline_steps": {"intake": {"owner": "scout"}}},
        {},
    )):
        resp = await srv._dispatch({
            "id": f"r{i}", "method": "host.workgroup.create",
            "params": {"profile": "default", "name": f"factory{i}", "members": [], **extra},
        })
        wg = wg_mod.load(home, resp["result"]["wg_id"])
        assert wg.meta.pipelines == {}, extra
        assert wg.meta.pipeline_steps == {}, extra
        assert wg.meta.launch_chain == (), extra


@pytest.mark.asyncio
async def test_create_rejects_empty_name(short_tmp: Path, monkeypatch) -> None:
    home = short_tmp / "h"
    _seed(home)
    from alpi import home as home_mod
    monkeypatch.setattr(home_mod, "_ROOT", short_tmp)
    monkeypatch.setattr(home_mod, "home_for", lambda profile: home)

    srv = host_server.Server(home=home)
    workgroup_admin.register(srv)

    resp = await srv._dispatch({
        "id": "r",
        "method": "host.workgroup.create",
        "params": {"profile": "default", "name": "", "members": []},
    })
    assert resp["error"]["code"] == -32602


@pytest.mark.asyncio
async def test_update_briefing_round_trip(short_tmp: Path, monkeypatch) -> None:
    home = short_tmp / "h"
    _seed(home)
    from alpi import home as home_mod
    monkeypatch.setattr(home_mod, "_ROOT", short_tmp)
    monkeypatch.setattr(home_mod, "home_for", lambda profile: home)

    srv = host_server.Server(home=home)
    workgroup_admin.register(srv)

    create = await srv._dispatch({
        "id": "r1",
        "method": "host.workgroup.create",
        "params": {"profile": "default", "name": "research", "members": []},
    })
    wg_id = create["result"]["wg_id"]

    update = await srv._dispatch({
        "id": "r2",
        "method": "host.workgroup.update",
        "params": {"profile": "default", "wg_id": wg_id, "briefing": "scope: weekly menu"},
    })
    assert update["result"]["ok"]
    assert "briefing" in update["result"]["changes"]


@pytest.mark.asyncio
async def test_update_rejects_any_pipeline_edit(short_tmp: Path, monkeypatch) -> None:
    home = short_tmp / "h"
    _seed(home)
    from alpi import home as home_mod
    from alpi.alp import workgroup as wg_mod
    monkeypatch.setattr(home_mod, "_ROOT", short_tmp)
    monkeypatch.setattr(home_mod, "home_for", lambda profile: home)

    srv = host_server.Server(home=home)
    workgroup_admin.register(srv)

    create = await srv._dispatch({
        "id": "r1", "method": "host.workgroup.create",
        "params": {"profile": "default", "name": "factory", "members": []},
    })
    wg_id = create["result"]["wg_id"]

    for i, pipeline in enumerate(("intake, build, qa", ["intake", "qa"], "")):
        upd = await srv._dispatch({
            "id": f"u{i}", "method": "host.workgroup.update",
            "params": {"profile": "default", "wg_id": wg_id, "pipeline": pipeline},
        })
        assert upd["error"]["code"] == -32602, pipeline
        assert "declared by a recipe" in upd["error"]["data"]["detail"], pipeline
        assert wg_mod.load(home, wg_id).meta.pipelines == {}, pipeline


def test_workgroup_list_rows_carry_chains_without_the_retired_key(short_tmp: Path) -> None:
    home = short_tmp / "h"
    _seed(home)
    from alpi.alp import workgroup as wg_mod
    from alpi.host.device_state import _hub_workgroups

    kp = load_or_generate(home)
    wg_mod.create(
        home,
        name="factory",
        hub_kp=kp,
        member_pubkeys=[],
        pipelines={"intake": ["intake", "build", "qa"]},
        launch_pipeline="intake",
    )

    rows = _hub_workgroups(home, "default")
    assert rows[0]["pipelines"] == {"intake": ["intake", "build", "qa"]}
    assert rows[0]["launch_pipeline"] == "intake"
    assert rows[0]["pipeline_mode"] is True
    assert rows[0]["needs_relaunch"] is False
    assert "pipeline" not in rows[0]
    assert "operations" not in rows[0]


def test_workgroup_list_ignores_runtime_directory_without_meta(short_tmp: Path) -> None:
    home = short_tmp / "h"
    orphan = home / "alp" / "workgroups" / "wg_orphan" / "gates"
    orphan.mkdir(parents=True)
    (orphan / "intake-10.log").write_text("stale\n")

    from alpi.host.device_state import _hub_workgroups

    assert _hub_workgroups(home, "default") == []


def test_workgroup_list_rows_expose_pipeline_queue_position(short_tmp: Path) -> None:
    from alpi.alp import pipeline_queue
    from alpi.alp import workgroup as wg_mod
    from alpi.host.device_state import _hub_workgroups

    home = short_tmp / "h"
    _seed(home)
    wg = wg_mod.create(
        home, name="factory", hub_kp=load_or_generate(home), member_pubkeys=[],
        pipelines={"intake": ["intake"]}, launch_pipeline="intake",
    )
    pipeline_queue.enqueue(home, wg.meta.id, "intake")

    row = _hub_workgroups(home, "default", include_pipeline_status=True)[0]
    assert row["pipeline_status"] == "queued"
    assert row["queued_pipeline"] == "intake"
    assert row["queue_position"] == 1


@pytest.mark.asyncio
async def test_workgroups_list_includes_pipeline_status_only_when_requested(
    short_tmp: Path, monkeypatch,
) -> None:
    from alpi import home as home_mod
    from alpi.alp import workgroup as wg_mod
    from alpi.host import device_state

    home = short_tmp / "h"
    _seed(home)
    monkeypatch.setattr(home_mod, "_ROOT", short_tmp)
    monkeypatch.setattr(home_mod, "home_for", lambda profile: home)
    wg = wg_mod.create(
        home, name="factory", hub_kp=load_or_generate(home), member_pubkeys=[],
        pipelines={"intake": ["intake"]}, launch_pipeline="intake",
    )
    monkeypatch.setattr(
        device_state, "_pipeline_status",
        lambda resolved_home, wg_id: (
            "completed" if resolved_home == home and wg_id == wg.meta.id else None
        ),
    )
    srv = host_server.Server(home=home)
    device_state.register(srv)

    lean = await srv._dispatch({
        "id": "lean", "method": "host.workgroups.list",
        "params": {"profile": "default"},
    })
    rich = await srv._dispatch({
        "id": "rich", "method": "host.workgroups.list",
        "params": {"profile": "default", "include_pipeline_status": True},
    })

    assert "pipeline_status" not in lean["result"]["workgroups"][0]
    assert rich["result"]["workgroups"][0]["pipeline_status"] == "completed"


@pytest.mark.asyncio
async def test_workgroups_list_includes_the_active_pipeline_phase(
    short_tmp: Path, monkeypatch,
) -> None:
    from alpi import home as home_mod
    from alpi.alp import workgroup as wg_mod
    from alpi.host import device_state

    home = short_tmp / "h"
    _seed(home)
    monkeypatch.setattr(home_mod, "_ROOT", short_tmp)
    monkeypatch.setattr(home_mod, "home_for", lambda profile: home)
    wg_mod.create(
        home, name="factory", hub_kp=load_or_generate(home), member_pubkeys=[],
        pipelines={"setup": ["setup", "content"]}, launch_pipeline="setup",
    )
    monkeypatch.setattr(device_state, "_pipeline_status", lambda _home, _wg_id: "running")
    monkeypatch.setattr(device_state, "_pipeline_phase", lambda _home, _wg_id: "content")
    srv = host_server.Server(home=home)
    device_state.register(srv)

    rich = await srv._dispatch({
        "id": "rich", "method": "host.workgroups.list",
        "params": {"profile": "default", "include_pipeline_status": True},
    })

    row = rich["result"]["workgroups"][0]
    assert row["pipeline_status"] == "running"
    assert row["pipeline_phase"] == "content"


def test_aggregate_workgroups_folds_each_deduplicated_row_once(monkeypatch) -> None:
    from alpi.host import device_state

    profiles = [{"name": "member"}, {"name": "hub"}]
    rows = {
        "member": [{
            "id": "wg_shared", "profile": "member", "is_hub": False, "mtime": 1,
        }],
        "hub": [{
            "id": "wg_shared", "profile": "hub", "is_hub": True, "mtime": 2,
        }],
    }
    calls = []
    monkeypatch.setattr(device_state, "_profiles", lambda: profiles)
    monkeypatch.setattr(
        device_state, "_workgroups_for",
        lambda profile, include_pipeline_status=False: rows[profile],
    )
    monkeypatch.setattr(
        device_state, "_resolve_home", lambda profile: Path(f"/{profile}"),
    )
    monkeypatch.setattr(
        device_state, "_pipeline_status",
        lambda home, wg_id: calls.append((home, wg_id)) or "running",
    )
    monkeypatch.setattr(
        "alpi.alp.pipeline_queue.positions", lambda _home: {},
    )

    result = device_state._aggregate_workgroups(
        None, include_pipeline_status=True,
    )

    assert result == [{
        "id": "wg_shared", "profile": "hub", "is_hub": True, "mtime": 2,
        "pipeline_status": "running", "queued_pipeline": None,
        "queue_position": None,
    }]
    assert calls == [(Path("/hub"), "wg_shared")]


def test_workgroup_list_flags_a_retired_shape_as_needs_relaunch(short_tmp: Path) -> None:
    """The poller refuses to load such a workgroup, so its row must not read as a healthy deliberation wg."""
    import yaml

    home = short_tmp / "h"
    _seed(home)
    from alpi.alp import workgroup as wg_mod
    from alpi.host.device_state import _hub_workgroups

    wg = wg_mod.create(
        home, name="factory", hub_kp=load_or_generate(home), member_pubkeys=[],
        pipelines={"intake": ["intake", "qa"]}, launch_pipeline="intake",
    )
    meta_path = wg_mod._wg_dir(home, wg.meta.id) / "meta.yaml"
    raw = yaml.safe_load(meta_path.read_text())
    raw["pipeline"] = ["intake", "qa"]
    meta_path.write_text(yaml.safe_dump(raw))

    rows = _hub_workgroups(home, "default")
    assert rows[0]["needs_relaunch"] is True
    assert rows[0]["pipelines"] == {}
    assert rows[0]["pipeline_mode"] is False
    assert wg_mod.load(home, wg.meta.id) is None


@pytest.mark.asyncio
async def test_remove_workgroup_clears_dir(short_tmp: Path, monkeypatch) -> None:
    home = short_tmp / "h"
    _seed(home)
    from alpi import home as home_mod
    monkeypatch.setattr(home_mod, "_ROOT", short_tmp)
    monkeypatch.setattr(home_mod, "home_for", lambda profile: home)

    srv = host_server.Server(home=home)
    workgroup_admin.register(srv)

    create = await srv._dispatch({
        "id": "r1",
        "method": "host.workgroup.create",
        "params": {"profile": "default", "name": "research", "members": []},
    })
    wg_id = create["result"]["wg_id"]
    wg_dir = home / "alp" / "workgroups" / wg_id
    assert wg_dir.exists()

    remove = await srv._dispatch({
        "id": "r2",
        "method": "host.workgroup.remove",
        "params": {"profile": "default", "wg_id": wg_id},
    })
    assert remove["result"]["ok"]
    assert not wg_dir.exists()


@pytest.mark.asyncio
async def test_create_emits_workgroup_changed(short_tmp: Path, monkeypatch) -> None:
    from alpi import home as home_mod
    from alpi.host import events as host_events

    home = short_tmp / "h"
    _seed(home)
    monkeypatch.setattr(home_mod, "_ROOT", short_tmp)
    monkeypatch.setattr(home_mod, "home_for", lambda profile: home)
    srv = host_server.Server(home=home)
    workgroup_admin.register(srv)

    captured: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        host_events, "emit",
        lambda kind, data=None: captured.append((kind, data or {})),
    )

    resp = await srv._dispatch({
        "id": "r",
        "method": "host.workgroup.create",
        "params": {"profile": "default", "name": "research", "members": []},
    })
    wg_id = resp["result"]["wg_id"]
    assert any(
        k == "workgroup_changed" and d.get("wg_id") == wg_id
        and d.get("action") == "created"
        for k, d in captured
    )


@pytest.mark.asyncio
async def test_action_rejects_unknown(short_tmp: Path, monkeypatch) -> None:
    home = short_tmp / "h"
    _seed(home)
    from alpi import home as home_mod
    monkeypatch.setattr(home_mod, "_ROOT", short_tmp)
    monkeypatch.setattr(home_mod, "home_for", lambda profile: home)

    srv = host_server.Server(home=home)
    workgroup_admin.register(srv)

    resp = await srv._dispatch({
        "id": "r",
        "method": "host.workgroup.action",
        "params": {"profile": "default", "wg_id": "deadbeef", "action": "explode"},
    })
    assert resp["error"]["code"] == -32602


@pytest.mark.asyncio
async def test_remove_archives_spend_before_deleting(short_tmp: Path, monkeypatch) -> None:
    home = short_tmp / "h"
    _seed(home)
    from alpi import home as home_mod
    monkeypatch.setattr(home_mod, "_ROOT", short_tmp)
    monkeypatch.setattr(home_mod, "home_for", lambda profile: home)

    srv = host_server.Server(home=home)
    workgroup_admin.register(srv)
    create = await srv._dispatch({
        "id": "a1", "method": "host.workgroup.create",
        "params": {"profile": "default", "name": "research", "members": []},
    })
    wg_id = create["result"]["wg_id"]
    import json as json_mod
    (home / "alp" / "workgroups" / wg_id / "transcript.jsonl").write_text(
        json_mod.dumps({
            "seq": 1, "ts": 1.0, "from": "x", "key_version": 1,
            "nonce": "n", "ciphertext": "c",
            "cost": {"usd": 0.5, "tokens_in": 10, "tokens_out": 5},
        }) + "\n"
    )

    remove = await srv._dispatch({
        "id": "a2", "method": "host.workgroup.remove",
        "params": {"profile": "default", "wg_id": wg_id},
    })
    assert remove["result"]["ok"]

    from alpi import ledger
    records = ledger.read_archive(home)
    rec = next((r for r in records if r["kind"] == "workgroup" and r["id"] == wg_id), None)
    assert rec is not None
    assert rec["cost_usd"] == 0.5


@pytest.mark.asyncio
async def test_remove_aborts_when_spend_archive_fails(short_tmp: Path, monkeypatch) -> None:
    home = short_tmp / "h"
    _seed(home)
    from alpi import home as home_mod
    monkeypatch.setattr(home_mod, "_ROOT", short_tmp)
    monkeypatch.setattr(home_mod, "home_for", lambda profile: home)

    srv = host_server.Server(home=home)
    workgroup_admin.register(srv)
    create = await srv._dispatch({
        "id": "f1", "method": "host.workgroup.create",
        "params": {"profile": "default", "name": "research", "members": []},
    })
    wg_id = create["result"]["wg_id"]
    wg_dir = home / "alp" / "workgroups" / wg_id

    def boom(*_a, **_kw):
        raise OSError("disk full")

    monkeypatch.setattr("alpi.ledger.archive_entity", boom)
    resp = await srv._dispatch({
        "id": "f2", "method": "host.workgroup.remove",
        "params": {"profile": "default", "wg_id": wg_id},
    })
    assert "error" in resp
    assert "spend archive failed" in str(resp["error"])
    assert wg_dir.exists()


@pytest.mark.asyncio
async def test_remove_aborts_when_delete_fails(short_tmp: Path, monkeypatch) -> None:
    from alpi import home as home_mod
    from alpi.host import events as host_events

    home = short_tmp / "h"
    _seed(home)
    monkeypatch.setattr(home_mod, "_ROOT", short_tmp)
    monkeypatch.setattr(home_mod, "home_for", lambda profile: home)
    srv = host_server.Server(home=home)
    workgroup_admin.register(srv)

    create = await srv._dispatch({
        "id": "d1", "method": "host.workgroup.create",
        "params": {"profile": "default", "name": "research", "members": []},
    })
    wg_id = create["result"]["wg_id"]
    wg_dir = home / "alp" / "workgroups" / wg_id

    captured: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        host_events, "emit",
        lambda kind, data=None: captured.append((kind, data or {})),
    )

    import shutil as real_shutil
    real_rmtree = real_shutil.rmtree

    def boom(path, *a, **kw):
        if str(path).rstrip("/").endswith(wg_id):
            raise OSError("permission denied")
        return real_rmtree(path, *a, **kw)

    monkeypatch.setattr("alpi.alp.workgroup._shutil.rmtree", boom)
    resp = await srv._dispatch({
        "id": "d2", "method": "host.workgroup.remove",
        "params": {"profile": "default", "wg_id": wg_id},
    })

    assert "error" in resp
    assert "permission denied" in str(resp["error"])
    assert wg_dir.exists()
    from alpi.alp import subscription as sub_mod
    assert wg_id not in sub_mod.tombstones(home)
    assert not any(
        k == "workgroup_changed" and d.get("action") == "removed"
        for k, d in captured
    )


def _pipeline_factory(short_tmp: Path, home: Path):
    """Hub workgroup with a launch chain, a dormant chain and a gated first phase."""
    from alpi.alp import peers as peers_mod
    from alpi.alp import workgroup as wg_mod

    owner_home = short_tmp / "scout"
    owner_home.mkdir(parents=True, exist_ok=True)
    owner_pubkey = load_or_generate(owner_home).pubkey_b64()
    peers_mod.add(home, peers_mod.Peer(id="scout", pubkey=owner_pubkey))
    return wg_mod.create(
        home,
        name="factory",
        hub_kp=load_or_generate(home),
        member_pubkeys=[owner_pubkey],
        pipelines={"intake": ["intake", "content"], "media": ["media", "publish"]},
        launch_pipeline="intake",
        pipeline_steps={
            "intake": {
                "owner": "scout", "task": "gather the brief",
                "gate": {"argv": ["astro", "check"], "cwd": "site"},
            },
            "content": {"owner": "scout"},
            "publish": {"owner": "scout"},
        },
    )


def _transcript_lines(home: Path, wg_id: str) -> list[str]:
    p = home / "alp" / "workgroups" / wg_id / "transcript.jsonl"
    if not p.exists():
        return []
    return [line for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


def _admin_server(short_tmp: Path, home: Path, monkeypatch):
    from alpi import home as home_mod
    monkeypatch.setattr(home_mod, "_ROOT", short_tmp)
    monkeypatch.setattr(home_mod, "home_for", lambda profile: home)
    srv = host_server.Server(home=home)
    workgroup_admin.register(srv)
    return srv


@pytest.mark.asyncio
async def test_trigger_posts_the_declared_opener(short_tmp: Path, monkeypatch) -> None:
    home = short_tmp / "h"
    _seed(home)
    srv = _admin_server(short_tmp, home, monkeypatch)
    wg = _pipeline_factory(short_tmp, home)

    resp = await srv._dispatch({
        "id": "t1", "method": "host.workgroup.trigger",
        "params": {"profile": "default", "wg_id": wg.meta.id, "pipeline": "intake"},
    })
    assert resp["result"] == {
        "ok": True, "pipeline": "intake", "phase": "intake", "seq": 1,
        "stopped": None,
    }

    from alpi.host import workgroup as data_workgroup
    posts = data_workgroup.decrypt_transcript(home, wg.meta.id)
    assert [p["body"] for p in posts] == ["@scout #task #intake · gather the brief"]


@pytest.mark.asyncio
async def test_trigger_rejects_unknown_pipeline(short_tmp: Path, monkeypatch) -> None:
    home = short_tmp / "h"
    _seed(home)
    srv = _admin_server(short_tmp, home, monkeypatch)
    wg = _pipeline_factory(short_tmp, home)

    resp = await srv._dispatch({
        "id": "t2", "method": "host.workgroup.trigger",
        "params": {"profile": "default", "wg_id": wg.meta.id, "pipeline": "ghost"},
    })
    assert resp["error"]["message"] == "pipeline-unknown"
    assert _transcript_lines(home, wg.meta.id) == []


@pytest.mark.asyncio
async def test_trigger_rejects_paused_workgroup(short_tmp: Path, monkeypatch) -> None:
    home = short_tmp / "h"
    _seed(home)
    srv = _admin_server(short_tmp, home, monkeypatch)
    wg = _pipeline_factory(short_tmp, home)

    paused = await srv._dispatch({
        "id": "p1", "method": "host.workgroup.action",
        "params": {"profile": "default", "wg_id": wg.meta.id, "action": "pause"},
    })
    assert paused["result"]["ok"]

    resp = await srv._dispatch({
        "id": "t3", "method": "host.workgroup.trigger",
        "params": {"profile": "default", "wg_id": wg.meta.id, "pipeline": "intake"},
    })
    assert resp["error"]["message"] == "workgroup-paused"
    assert _transcript_lines(home, wg.meta.id) == []


@pytest.mark.asyncio
async def test_trigger_stops_the_run_that_was_in_flight(
    short_tmp: Path, monkeypatch,
) -> None:
    """Pipelines run one at a time: the host verb reports what it stopped."""
    home = short_tmp / "h"
    _seed(home)
    srv = _admin_server(short_tmp, home, monkeypatch)
    wg = _pipeline_factory(short_tmp, home)

    first = await srv._dispatch({
        "id": "t4", "method": "host.workgroup.trigger",
        "params": {"profile": "default", "wg_id": wg.meta.id, "pipeline": "intake"},
    })
    assert first["result"]["ok"] and first["result"]["stopped"] is None

    resp = await srv._dispatch({
        "id": "t5", "method": "host.workgroup.trigger",
        "params": {"profile": "default", "wg_id": wg.meta.id, "pipeline": "intake"},
    })
    assert resp["result"]["ok"] is True
    assert resp["result"]["stopped"] == {
        "pipeline": "intake", "phase": "intake", "status": "running",
        "open_task": "intake", "same_pipeline": True,
    }
    assert len(_transcript_lines(home, wg.meta.id)) == 2


@pytest.mark.asyncio
async def test_trigger_rejects_pipeline_without_opener_contract(
    short_tmp: Path, monkeypatch,
) -> None:
    home = short_tmp / "h"
    _seed(home)
    srv = _admin_server(short_tmp, home, monkeypatch)
    wg = _pipeline_factory(short_tmp, home)

    resp = await srv._dispatch({
        "id": "t6", "method": "host.workgroup.trigger",
        "params": {"profile": "default", "wg_id": wg.meta.id, "pipeline": "media"},
    })
    assert resp["error"]["message"] == "pipeline-trigger-contract-missing"
    assert _transcript_lines(home, wg.meta.id) == []


@pytest.mark.asyncio
async def test_update_leaves_declared_chains_untouched(
    short_tmp: Path, monkeypatch,
) -> None:
    home = short_tmp / "h"
    _seed(home)
    from alpi.alp import workgroup as wg_mod
    srv = _admin_server(short_tmp, home, monkeypatch)
    wg = _pipeline_factory(short_tmp, home)

    resp = await srv._dispatch({
        "id": "u1", "method": "host.workgroup.update",
        "params": {"profile": "default", "wg_id": wg.meta.id,
                   "pipeline": ["intake", "content", "build"]},
    })
    assert resp["error"]["code"] == -32602
    assert "declared by a recipe" in resp["error"]["data"]["detail"]

    meta = wg_mod.load(home, wg.meta.id).meta
    assert meta.launch_pipeline == "intake"
    assert meta.launch_chain == ("intake", "content")
    assert wg_mod.dormant_pipelines(meta) == {"media": ("media", "publish")}


@pytest.mark.asyncio
async def test_update_cannot_clear_the_launch_selector(
    short_tmp: Path, monkeypatch,
) -> None:
    home = short_tmp / "h"
    _seed(home)
    from alpi.alp import workgroup as wg_mod
    srv = _admin_server(short_tmp, home, monkeypatch)
    wg = _pipeline_factory(short_tmp, home)

    resp = await srv._dispatch({
        "id": "u2", "method": "host.workgroup.update",
        "params": {"profile": "default", "wg_id": wg.meta.id, "pipeline": ""},
    })
    assert resp["error"]["code"] == -32602
    assert "declared by a recipe" in resp["error"]["data"]["detail"]

    meta = wg_mod.load(home, wg.meta.id).meta
    assert meta.launch_pipeline == "intake"
    assert meta.pipelines == {
        "intake": ("intake", "content"), "media": ("media", "publish"),
    }


@pytest.mark.asyncio
async def test_update_still_edits_the_briefing_beside_declared_chains(
    short_tmp: Path, monkeypatch,
) -> None:
    home = short_tmp / "h"
    _seed(home)
    from alpi.alp import workgroup as wg_mod
    srv = _admin_server(short_tmp, home, monkeypatch)
    wg = _pipeline_factory(short_tmp, home)

    resp = await srv._dispatch({
        "id": "u3", "method": "host.workgroup.update",
        "params": {"profile": "default", "wg_id": wg.meta.id, "briefing": "ship it"},
    })
    assert resp["result"]["ok"]
    assert "briefing" in resp["result"]["changes"]

    meta = wg_mod.load(home, wg.meta.id).meta
    assert meta.briefing == "ship it"
    assert meta.launch_pipeline == "intake"
    assert meta.pipelines == {
        "intake": ("intake", "content"), "media": ("media", "publish"),
    }


@pytest.mark.asyncio
async def test_workgroups_list_rows_carry_safe_pipeline_shape(
    short_tmp: Path, monkeypatch,
) -> None:
    import json as json_mod

    from alpi.alp import subscription as sub_mod
    from alpi.host import device_state

    home = short_tmp / "h"
    _seed(home)
    srv = _admin_server(short_tmp, home, monkeypatch)
    device_state.register(srv)
    wg = _pipeline_factory(short_tmp, home)

    sub = sub_mod.Subscription(
        wg_id="subscribedwg",
        name="remote-factory",
        hub_id="mirai",
        hub_pubkey="cGs=",
    )
    sub.absorb_pipeline_state({
        "pipelines": {"intake": ["intake", "content"], "media": ["media", "publish"]},
        "launch_pipeline": "intake",
        "pipeline_mode": True,
        "phase_map": {
            "intake": {"owner": "scout", "task": "gather the brief"},
            "content": {"owner": "quill"},
        },
    })
    sub_mod.upsert(home, sub)

    resp = await srv._dispatch({
        "id": "l1", "method": "host.workgroups.list",
        "params": {"profile": "default"},
    })
    rows = {r["id"]: r for r in resp["result"]["workgroups"]}
    hub_row = rows[wg.meta.id]
    sub_row = rows["subscribedwg"]

    for row in (hub_row, sub_row):
        assert row["pipelines"] == {
            "intake": ["intake", "content"], "media": ["media", "publish"],
        }
        assert row["launch_pipeline"] == "intake"
        assert row["pipeline_mode"] is True
        assert row["needs_relaunch"] is False
        assert "pipeline" not in row
        assert "operations" not in row
        assert row["phase_map"]["intake"] == {
            "owner": "scout", "task": "gather the brief",
        }
        for spec in row["phase_map"].values():
            assert set(spec) <= {"owner", "task"}
        dumped = json_mod.dumps(row)
        assert "argv" not in dumped
        assert "astro" not in dumped
        assert "gate" not in dumped

    assert hub_row["is_hub"] is True
    assert sub_row["is_hub"] is False
