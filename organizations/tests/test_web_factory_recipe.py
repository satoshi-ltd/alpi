import shutil
import subprocess
import types
from pathlib import Path

import pytest

from alpi import recipes as r
from alpi.alp import peers as peers_mod
from alpi.alp import pipeline_gates
from alpi.alp import workgroup as wg
from alpi.alp.keys import load_or_generate
from alpi.alp.peers import Peer
from alpi.host import recipes as host_recipes

_RECIPES = Path(__file__).resolve().parents[1] / "web-factory" / "recipes"
_MEMBERS = ["scout", "quill", "lingua", "muse", "pixel", "lens"]


def test_hotel_recipe_resolves_and_forms_valid_workgroup():
    rec = r.load_recipe(_RECIPES / "hotel.yaml")
    assert rec.hub == "mira"
    assert set(rec.members) == {"scout", "quill", "lingua", "muse", "pixel", "lens"}

    spec = r.resolve(rec, {"slug": "casa-bahia"})
    assert spec["name"] == "site-casa-bahia"
    assert spec["project"]["dest"] == "projects/casa-bahia"

    pipelines = wg.normalize_pipelines(spec["pipelines"])
    launch = wg.normalize_launch_pipeline(pipelines, spec["launch_pipeline"])
    steps = wg.validate_pipeline_steps(pipelines, spec["pipeline_steps"])
    roster = set(spec["members"]) | {spec["hub"]}
    assert all(s["owner"] in roster for s in steps.values())

    assert launch == "setup"
    pipeline = pipelines["setup"]
    assert pipeline[0] == "setup"
    meta = types.SimpleNamespace(pipelines=pipelines, launch_pipeline=launch)
    assert wg.pipeline_successor(meta, "intake") == "assets"
    assert steps["setup"]["gate"]["argv"] == ["npm", "run", "check:setup"]
    assert steps["assets"]["gate"]["argv"] == ["npm", "run", "check:assets"]
    for phase in ("setup", "enrich", "intake", "assets", "content", "translation", "build"):
        assert "gate" in steps[phase]
    for phase in ("qa", "media-qa", "content-qa", "review-qa"):
        assert "gate" not in steps[phase], phase
        assert steps[phase]["owner"] == "lens" or phase == "review-qa"
    assert steps["enrich"]["gate"]["argv"] == ["npm", "run", "check:enrichment"]
    # 900s ceilings measured live: beachmate enrich 2x, abad translation 1x, beachmate chain content 1x.
    for phase in ("enrich", "intake", "content", "translation"):
        assert steps[phase]["turn_budget_s"] == 1800


def test_enrich_is_its_own_phase_before_intake():
    """Research and config authoring share an owner but never a context window."""
    rec = r.load_recipe(_RECIPES / "hotel.yaml")
    meta = types.SimpleNamespace(
        pipelines=rec.pipelines, launch_pipeline=rec.launch_pipeline,
    )
    assert rec.launch_chain.index("enrich") == rec.launch_chain.index("intake") - 1
    assert wg.pipeline_successor(meta, "setup") == "enrich"
    assert wg.pipeline_successor(meta, "enrich") == "intake"
    assert rec.pipeline_steps["enrich"]["owner"] == "scout"
    assert rec.pipeline_steps["intake"]["owner"] == "scout"


def test_hotel_recipe_carries_briefing_and_start_task():
    rec = r.load_recipe(_RECIPES / "hotel.yaml")
    spec = r.resolve(rec, {"slug": "casa-bahia"})
    assert "Workgroup for hotel 'casa-bahia'" in spec["briefing"]
    assert "Working language" in spec["briefing"]
    # Chains are hydrated into member context now; narrating them twice went stale.
    for op in ("#review", "#media-update", "#content-update"):
        assert op not in spec["briefing"]
    assert spec["task"].startswith("@pixel #task #setup")
    assert set(spec["project"]["seed"]["files"]) == {"work/intake.md"}
    intake_seed = spec["project"]["seed"]["files"]["work/intake.md"]
    assert "## Canonical slugs" in intake_seed
    assert "| collection | slug | name | composition |" in intake_seed
    assert spec["inputs"]["brief"]["dest"] == "brief.md"
    assert spec["inputs"]["brief"]["required"] is True


def test_hotel_recipe_slug_pattern_enforced():
    rec = r.load_recipe(_RECIPES / "hotel.yaml")
    with pytest.raises(r.RecipeError, match="does not match"):
        r.resolve(rec, {"slug": "Casa Bahia"})
    with pytest.raises(r.RecipeError, match="missing required"):
        r.resolve(rec, {})


def _git(args, cwd):
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=str(cwd), check=True, capture_output=True, text=True,
    )


@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
@pytest.mark.asyncio
async def test_hotel_recipe_launches_full_workgroup(tmp_path):
    repo = tmp_path / "base"
    repo.mkdir()
    (repo / "README.md").write_text("base")
    (repo / "package.json").write_text(
        '{"scripts": {"check:enrichment": '
        '"node -e \\"process.exit('
        "require('fs').readFileSync('work/enrichment.md','utf8')"
        ".includes('## Verified facts') ? 0 : 1)\\\"\"}}",
    )
    _git(["init", "-q"], repo)
    _git(["add", "-A"], repo)
    _git(["commit", "-q", "-m", "base"], repo)

    home = tmp_path / "profiles" / "mira"
    home.mkdir(parents=True)
    load_or_generate(home)
    ws = tmp_path / "ws"
    ws.mkdir()
    (home / "config.yaml").write_text(f"model: ''\nworkspace: {ws}\n")
    for m in _MEMBERS:
        mh = home.parent / m
        mh.mkdir(parents=True, exist_ok=True)
        pk = load_or_generate(mh).pubkey_b64()
        peers_mod.add(home, Peer(id=m, pubkey=pk, allow=["workgroup.join", "workgroup.post", "workgroup.pull"]))

    yaml_text = (_RECIPES / "hotel.yaml").read_text().replace(
        "git@github.com:satoshi-ltd/alpi-mirai-web-factory.git", str(repo),
    )
    result = await host_recipes.launch(
        home, yaml_text, {"slug": "casa-bahia"}, recipe_id="hotel",
        inputs={"brief": "# Real client brief for casa-bahia"},
    )

    wgo = wg.load(home, result["workgroup_id"])
    assert wgo.meta.name == "site-casa-bahia"
    assert "Workgroup for hotel 'casa-bahia'" in wgo.meta.briefing
    assert wgo.meta.launch_pipeline == "setup"
    assert wgo.meta.launch_chain == (
        "setup", "enrich", "intake", "assets", "content", "translation", "build", "qa",
    )
    assert set(wgo.meta.pipelines) == {
        "setup", "media-update", "content-update", "review",
    }
    assert len(wgo.members) == len(_MEMBERS) + 1  # members + hub

    dest = ws / "projects" / "casa-bahia"
    assert (dest / "brief.md").read_text() == "# Real client brief for casa-bahia"
    assert (dest / "work" / "intake.md").exists()

    step = pipeline_gates.step_for(wgo.meta, "enrich")
    assert step is not None
    assert pipeline_gates.run_gate(step, ws)[0] is False
    enrichment = dest / "work" / "enrichment.md"
    enrichment.write_text("plain prose only\n")
    assert pipeline_gates.run_gate(step, ws)[0] is False
    enrichment.write_text(
        "## Verified facts\n"
        "- Rooftop pool. [src: official-site + booking]\n",
    )
    assert pipeline_gates.run_gate(step, ws)[0] is True

    from alpi.service import _all_hub_posts_decrypted
    texts = "\n".join(str(p.get("text") or "") for p in _all_hub_posts_decrypted(home, wgo))
    assert "@pixel #task #setup" in texts


def test_explicitly_skipped_enrich_advances_to_intake():
    import types

    from alpi import service

    rec = r.load_recipe(_RECIPES / "hotel.yaml")
    wgo = types.SimpleNamespace(
        meta=types.SimpleNamespace(
            id="wg1", name="site-x", hub_pubkey="HUB",
            pipelines=rec.pipelines, launch_pipeline=rec.launch_pipeline,
        ),
    )
    skipped = [
        {"seq": 1, "from": "HUB", "text": "@scout #task #enrich go"},
        {"seq": 2, "from": "HUB", "text": "#done skipped · web tools disabled"},
    ]
    assert service._next_pipeline_phase(wgo, skipped)[0] == "intake"


def test_media_update_is_declared_not_remembered():
    """Phase 2 chains from the recipe; six stalls in one day traced to hub recall."""
    rec = r.load_recipe(_RECIPES / "hotel.yaml")
    chain = rec.pipelines.get("media-update")
    assert chain == ("media-update", "media-config", "media-build", "media-qa")
    owners = [rec.pipeline_steps[s]["owner"] for s in chain]
    assert owners == ["muse", "scout", "pixel", "lens"], (
        "step 2 is scout on purpose: the logo and gallery keys are what the chain "
        "kept dropping, leaving optimized derivatives no page referenced"
    )
    for slug in chain[:-1]:
        assert rec.pipeline_steps[slug].get("gate"), f"{slug} closes on a gate, not on a claim"
    assert "gate" not in rec.pipeline_steps["media-qa"], (
        "qa phases are verdict-owned: a declared gate auto-verified over a QA FAIL "
        "twice on v7"
    )
    assert "media-update" not in rec.launch_chain, "a dormant chain must not auto-run after qa"


def test_every_post_launch_protocol_is_a_named_chain():
    """Prose protocols drifted; four declared chains cannot."""
    rec = r.load_recipe(_RECIPES / "hotel.yaml")
    assert set(rec.pipelines) == {"setup", "media-update", "content-update", "review"}
    assert rec.pipelines["content-update"] == (
        "content-update", "content-copy", "content-locales",
        "content-build", "content-qa",
    )
    assert [rec.pipeline_steps[s]["owner"] for s in rec.pipelines["content-update"]] == [
        "scout", "quill", "lingua", "pixel", "lens",
    ]
    assert rec.pipelines["review"] == (
        "review", "review-config", "review-content", "review-translation",
        "review-media", "review-build", "review-qa", "review-close",
    )
    assert [rec.pipeline_steps[s]["owner"] for s in rec.pipelines["review"]] == [
        "mira", "scout", "quill", "lingua", "muse", "pixel", "lens", "mira",
    ]
    for key, chain in rec.pipelines.items():
        first = rec.pipeline_steps[chain[0]]
        assert first.get("owner") and first.get("task"), (
            f"{key} must be triggerable: its first phase declares owner + task"
        )


def test_no_phase_declares_next():
    """Order lives in the chain; a second authority is how launch and operations diverged."""
    import yaml

    raw = yaml.safe_load((_RECIPES / "hotel.yaml").read_text())
    assert "operations" not in raw and "pipeline" not in raw
    assert raw["launch"] == "setup"
    for phase, step in raw["pipeline_steps"].items():
        assert "next" not in step, f"{phase} still declares next"


def test_content_update_is_never_swallowed_by_content():
    rec = r.load_recipe(_RECIPES / "hotel.yaml")
    meta = types.SimpleNamespace(
        pipelines=rec.pipelines, launch_pipeline=rec.launch_pipeline,
    )
    assert wg.canonical_pipeline_phase(meta, "content-update") == (
        "content-update", "content-update",
    )
    assert wg.canonical_pipeline_phase(meta, "content-fix") == ("setup", "content")
    assert wg.canonical_pipeline_phase(meta, "content-recheck") == ("setup", "content")
