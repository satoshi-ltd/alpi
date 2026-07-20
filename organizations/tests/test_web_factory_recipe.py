import shutil
import subprocess
from pathlib import Path

import pytest

from alpi import recipes as r
from alpi.alp import peers as peers_mod
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
    assert spec["name"] == "proj-casa-bahia"
    assert spec["project"]["dest"] == "projects/casa-bahia"

    pipeline = wg._normalize_pipeline(spec["pipeline"])
    steps = wg.validate_pipeline_steps(pipeline, spec["pipeline_steps"])
    roster = set(spec["members"]) | {spec["hub"]}
    assert all(s["owner"] in roster for s in steps.values())

    assert "assets" in pipeline
    assert "assets" not in steps
    assert steps["intake"]["next"] == "content"
    for phase in ("intake", "content", "translation", "build"):
        assert "gate" in steps[phase]


def test_hotel_recipe_carries_briefing_and_start_task():
    rec = r.load_recipe(_RECIPES / "hotel.yaml")
    spec = r.resolve(rec, {"slug": "casa-bahia"})
    assert "Workgroup for hotel 'casa-bahia'" in spec["briefing"]
    assert spec["task"].startswith("@scout #task #intake")
    assert "Kickoff for proj-casa-bahia" in spec["task"]
    assert set(spec["project"]["seed"]["files"]) == {"intake.md"}
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
    assert wgo.meta.name == "proj-casa-bahia"
    assert "Workgroup for hotel 'casa-bahia'" in wgo.meta.briefing
    assert wgo.meta.pipeline == ("intake", "assets", "content", "translation", "build", "qa")
    assert len(wgo.members) == len(_MEMBERS) + 1  # members + hub

    dest = ws / "projects" / "casa-bahia"
    assert (dest / "brief.md").read_text() == "# Real client brief for casa-bahia"
    assert (dest / "intake.md").exists()

    from alpi.service import _all_hub_posts_decrypted
    texts = "\n".join(str(p.get("text") or "") for p in _all_hub_posts_decrypted(home, wgo))
    assert "@scout #task #intake" in texts
    assert "Kickoff for proj-casa-bahia" in texts
