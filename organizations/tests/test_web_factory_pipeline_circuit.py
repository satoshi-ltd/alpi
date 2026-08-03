"""The whole circuit on the real recipe: launch, then every post-launch chain by trigger."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from alpi import recipes as r
from alpi.alp import peers as peers_mod
from alpi.alp import workgroup as wg_mod
from alpi.alp import workgroup_client as wc
from alpi.alp.keys import load_or_generate
from alpi.alp.peers import Peer
from alpi.host import recipes as host_recipes
from alpi.host import workgroup as host_wg

_RECIPES = Path(__file__).resolve().parents[1] / "web-factory" / "recipes"
_MEMBERS = ["scout", "quill", "lingua", "muse", "pixel", "lens"]


def _git(args, cwd):
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=str(cwd), check=True, capture_output=True, text=True,
    )


@pytest.fixture
def factory(tmp_path: Path, monkeypatch):
    from alpi import home as home_mod

    repo = tmp_path / "base"
    repo.mkdir()
    (repo / "README.md").write_text("base")
    _git(["init", "-q"], repo)
    _git(["add", "-A"], repo)
    _git(["commit", "-q", "-m", "base"], repo)

    root = tmp_path / "root"
    home = root / "profiles" / "mira"
    home.mkdir(parents=True)
    monkeypatch.setattr(home_mod, "_ROOT", root)
    load_or_generate(home)
    ws = tmp_path / "ws"
    ws.mkdir()
    (home / "config.yaml").write_text(f"model: ''\nworkspace: {ws}\n")
    for m in _MEMBERS:
        mh = root / "profiles" / m
        mh.mkdir(parents=True, exist_ok=True)
        pk = load_or_generate(mh).pubkey_b64()
        peers_mod.add(home, Peer(
            id=m, pubkey=pk,
            allow=["workgroup.join", "workgroup.post", "workgroup.pull"],
        ))
    yaml_text = (_RECIPES / "hotel.yaml").read_text().replace(
        "git@github.com:satoshi-ltd/alpi-mirai-web-factory.git", str(repo),
    )
    return home, yaml_text


def _bodies(home: Path, wg_id: str) -> list[str]:
    return [p["body"] for p in host_wg.decrypt_transcript(home, wg_id)]


@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
@pytest.mark.asyncio
async def test_launch_then_every_post_launch_chain_is_triggerable(factory) -> None:
    home, yaml_text = factory
    result = await host_recipes.launch(
        home, yaml_text, {"slug": "casa-bahia"}, recipe_id="hotel",
        inputs={"brief": "# brief"},
    )
    wg_id = result["workgroup_id"]
    meta = wg_mod.load(home, wg_id).meta
    assert meta.launch_pipeline == "setup"
    assert _bodies(home, wg_id) == [
        "@pixel #task #setup · initialize the cloned hotel project at "
        "projects/casa-bahia.\n",
    ]

    run = host_wg.fold_task_state(home, wg_id)["pipeline_run"]
    assert run["pipeline"] == "setup"
    assert run["status"] == "running"
    assert run["phases"][0]["state"] == "current"
    assert [p["state"] for p in run["phases"][1:]] == ["pending"] * 7

    # One at a time: starting a chain over the live launch run stops it, and the
    # stopped phase is reported as preempted rather than done.
    stopping = await wc.trigger_pipeline(home, wg_id, "media-update")
    assert stopping["stopped"] == {
        "pipeline": "setup", "phase": "setup", "status": "running",
        "open_task": "setup", "same_pipeline": False,
    }
    state = host_wg.fold_task_state(home, wg_id)
    assert state["pipeline_run"]["pipeline"] == "media-update"
    assert next(
        c for c in state["closed"] if c["slug"] == "setup"
    )["result"].startswith("preempted by")

    for key in ("media-update", "content-update", "review"):
        chain = meta.pipelines[key]
        spec = meta.pipeline_steps[chain[0]]
        expected = f"@{spec['owner']} #task #{chain[0]} · {spec['task']}"
        posted = await wc.trigger_pipeline(home, wg_id, key)
        assert posted["pipeline"] == key and posted["phase"] == chain[0]
        assert _bodies(home, wg_id)[-1] == expected
        run = host_wg.fold_task_state(home, wg_id)["pipeline_run"]
        assert run["pipeline"] == key
        assert run["current_phase"] == chain[0]
        assert [p["slug"] for p in run["phases"]] == list(chain)


def _append_hub(home: Path, wg_id: str, body: str) -> None:
    import json

    kp = load_or_generate(home)
    wg = wg_mod.load(home, wg_id)
    me = wg.member(kp.pubkey_b64())
    group_key = wg_mod.open_sealed_group_key(me.sealed_key, kp)
    path = home / "alp" / "workgroups" / wg_id / "transcript.jsonl"
    lines = [ln for ln in path.read_text().splitlines() if ln.strip()]
    nonce, ct = wg_mod.encrypt_post(group_key, body.encode())
    seq = len(lines) + 1
    path.write_text("\n".join(lines + [json.dumps({
        "seq": seq, "ts": f"2026-07-30T00:00:{seq:02d}Z", "from": kp.pubkey_b64(),
        "key_version": me.key_version, "nonce": nonce, "ciphertext": ct,
    }, separators=(",", ":"))]) + "\n")


@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
@pytest.mark.asyncio
async def test_an_idle_variant_of_the_recipe_posts_no_kickoff(factory) -> None:
    home, yaml_text = factory
    idle = yaml_text.replace("launch: setup\n", "").replace(
        "task: |\n  @pixel #task #setup · initialize the cloned hotel project at projects/{slug}.\n",
        "",
    )
    rec = r.parse_recipe(idle, "hotel-idle")
    assert rec.launch_pipeline is None
    assert set(rec.pipelines) == {"setup", "media-update", "content-update", "review"}

    result = await host_recipes.launch(
        home, idle, {"slug": "casa-idle"}, recipe_id="hotel-idle",
        inputs={"brief": "# brief"},
    )
    wg_id = result["workgroup_id"]
    assert _bodies(home, wg_id) == []
    assert host_wg.fold_task_state(home, wg_id)["pipeline_run"] is None

    meta = wg_mod.load(home, wg_id).meta
    assert meta.launch_pipeline is None
    assert wg_mod.is_pipeline_workgroup(meta)

    posted = await wc.trigger_pipeline(home, wg_id, "review")
    assert posted["phase"] == "review"
    run = host_wg.fold_task_state(home, wg_id)["pipeline_run"]
    assert run["pipeline"] == "review" and run["status"] == "running"


@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
@pytest.mark.asyncio
async def test_a_launchless_meta_writes_no_legacy_projection(factory) -> None:
    home, yaml_text = factory
    idle = yaml_text.replace("launch: setup\n", "").replace(
        "task: |\n  @pixel #task #setup · initialize the cloned hotel project at projects/{slug}.\n",
        "",
    )
    result = await host_recipes.launch(
        home, idle, {"slug": "casa-idle-2"}, recipe_id="hotel-idle",
        inputs={"brief": "# brief"},
    )
    raw = (home / "alp" / "workgroups" / result["workgroup_id"] / "meta.yaml").read_text()
    assert "pipelines:" in raw
    assert "\npipeline:" not in raw
    assert "operations:" not in raw
    assert "next:" not in raw
