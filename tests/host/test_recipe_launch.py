import json
import shutil
import subprocess
from pathlib import Path

import pytest

from alpi.alp import peers as peers_mod
from alpi.alp import workgroup as wg_mod
from alpi.alp.keys import load_or_generate
from alpi.alp.peers import Peer
from alpi.host import recipes as host_recipes

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")


def _git(args, cwd):
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=str(cwd), check=True, capture_output=True, text=True,
    )


def _fixture_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "base-repo"
    (repo / "src" / "config").mkdir(parents=True)
    (repo / "src" / "config" / "site.json").write_text(json.dumps({
        "theme": "boutique", "brand": {"name": ""}, "locales": ["es"],
        "pages": {"blog": False, "rooms": True},
    }, indent=2))
    (repo / "scripts").mkdir()
    (repo / "scripts" / "intake-check.mjs").write_text("process.exit(0)")
    _git(["init", "-q"], repo)
    _git(["add", "-A"], repo)
    _git(["commit", "-q", "-m", "base"], repo)
    return repo


def _hub_home(tmp_path: Path) -> Path:
    home = tmp_path / "profiles" / "mira"
    home.mkdir(parents=True)
    load_or_generate(home)
    ws = tmp_path / "ws"
    ws.mkdir()
    (home / "config.yaml").write_text(f"model: ''\nworkspace: {ws}\n")
    return home


def _pin_member(home: Path, name: str, pubkey: str | None = None) -> str:
    mh = home.parent / name
    mh.mkdir(parents=True, exist_ok=True)
    pk = pubkey if pubkey is not None else load_or_generate(mh).pubkey_b64()
    peers_mod.add(home, Peer(id=name, pubkey=pk, allow=["workgroup.join", "workgroup.post", "workgroup.pull"]))
    return pk


def _project_recipe(repo: Path, with_brief: bool = False) -> str:
    inputs = "\ninputs:\n  brief: { dest: brief.md, required: true }\n" if with_brief else ""
    return f"""
hub: mira
members: [scout]
name: "proj-{{slug}}"
quorum_timeout_seconds: 120
briefing: "Hotel {{slug}}"
pipeline: [intake, content]
pipeline_steps:
  intake: {{ owner: scout, next: content, task: "start {{slug}}", gate: {{ argv: ["true"], cwd: "projects/{{slug}}" }} }}
  content: {{ owner: scout }}
params:
  slug: {{ pattern: "^[a-z0-9-]+$" }}
{inputs}project:
  template_repo: "{repo}"
  dest: "projects/{{slug}}"
  seed:
    json_merge:
      src/config/site.json: {{ tier: pro, pages: {{ blog: true }} }}
"""


_CHAT_RECIPE = """
hub: mira
members: [scout]
name: "debate-{topic}"
task: "@scout discuss {topic}"
params:
  topic: { required: true }
"""


def test_recipe_verb_gating_invariants():
    from alpi.host import server as host_server
    assert "host.workgroup.launch_recipe" in host_server._ADMIN_METHODS
    assert "host.workgroup.recipes.describe" in host_server._SCOPE_FREE_METHODS
    assert "host.workgroup.launch_recipe" not in host_server._SCOPE_FREE_METHODS


@pytest.mark.asyncio
async def test_describe_returns_shape_without_storing(tmp_path):
    res = await host_recipes._describe({"yaml": _CHAT_RECIPE}, None)
    assert res["hub"] == "mira"
    assert "topic" in res["params"]
    assert res["has_project"] is False
    assert res["task"] == "@scout discuss {topic}"
    assert not (tmp_path / "recipes").exists()


@pytest.mark.asyncio
async def test_describe_rejects_empty_and_invalid():
    from alpi.host import server as host_server
    with pytest.raises(host_server.HandlerError):
        await host_recipes._describe({"yaml": "   "}, None)
    with pytest.raises(host_server.HandlerError):
        await host_recipes._describe({"yaml": "just a string, not a mapping"}, None)


@pytest.mark.asyncio
async def test_launch_project_recipe_end_to_end(tmp_path):
    repo = _fixture_repo(tmp_path)
    home = _hub_home(tmp_path)
    _pin_member(home, "scout")

    result = await host_recipes.launch(home, _project_recipe(repo), {"slug": "casa-bahia"})

    assert result["workgroup_id"].startswith("wg_")
    dest = tmp_path / "ws" / "projects" / "casa-bahia"
    assert result["project_path"] == str(dest)
    site = json.loads((dest / "src" / "config" / "site.json").read_text())
    assert site["tier"] == "pro"
    assert site["pages"]["blog"] is True
    assert site["pages"]["rooms"] is True
    assert site["theme"] == "boutique"
    assert (dest / ".git").is_dir()

    wg = wg_mod.load(home, result["workgroup_id"])
    assert wg.meta.name == "proj-casa-bahia"
    assert wg.meta.pipeline == ("intake", "content")
    assert wg.meta.pipeline_steps["intake"]["gate"]["cwd"] == "projects/casa-bahia"
    assert wg.meta.quorum_timeout_seconds == 120
    assert wg.meta.launch["recipe_id"] == "recipe"
    assert wg.meta.launch["params"] == {"slug": "casa-bahia"}
    assert wg.meta.launch["template_commit"]

    transcript = (home / "alp" / "workgroups" / wg.meta.id / "transcript.jsonl").read_text()
    assert transcript.strip()


@pytest.mark.asyncio
async def test_launch_rolls_back_project_on_create_failure(tmp_path):
    repo = _fixture_repo(tmp_path)
    home = _hub_home(tmp_path)
    _pin_member(home, "scout", pubkey="not-a-valid-pubkey")

    with pytest.raises(ValueError):
        await host_recipes.launch(home, _project_recipe(repo), {"slug": "casa-bahia"})

    assert not (tmp_path / "ws" / "projects" / "casa-bahia").exists()
    assert not any((home / "alp" / "workgroups").glob("wg_*")) if (home / "alp" / "workgroups").exists() else True


@pytest.mark.asyncio
async def test_launch_rolls_back_workgroup_and_project_on_kickoff_failure(tmp_path, monkeypatch):
    repo = _fixture_repo(tmp_path)
    home = _hub_home(tmp_path)
    _pin_member(home, "scout")

    async def boom(*a, **k):
        raise RuntimeError("kickoff post failed")
    monkeypatch.setattr("alpi.alp.workgroup_client.post", boom)

    with pytest.raises(RuntimeError):
        await host_recipes.launch(home, _project_recipe(repo), {"slug": "casa-bahia"})

    assert not (tmp_path / "ws" / "projects" / "casa-bahia").exists()
    wg_root = home / "alp" / "workgroups"
    assert not (list(wg_root.glob("wg_*")) if wg_root.exists() else [])


@pytest.mark.asyncio
async def test_launch_rejects_option_injection_via_template_repo(tmp_path):
    home = _hub_home(tmp_path)
    _pin_member(home, "scout")
    evil = """
hub: mira
members: [scout]
name: "x-{n}"
task: "hi"
params: { n: { required: true } }
project:
  template_repo: "--upload-pack=touch /tmp/pwned"
  dest: "projects/{n}"
"""
    with pytest.raises(ValueError, match="must not start with"):
        await host_recipes.launch(home, evil, {"n": "1"})


@pytest.mark.asyncio
async def test_launch_deliberation_recipe_no_project(tmp_path):
    home = _hub_home(tmp_path)
    _pin_member(home, "scout")
    result = await host_recipes.launch(home, _CHAT_RECIPE, {"topic": "pricing"})
    assert result["project_path"] is None
    wg = wg_mod.load(home, result["workgroup_id"])
    assert wg.meta.name == "debate-pricing"
    assert wg.meta.pipeline == ()


@pytest.mark.asyncio
async def test_launch_rejects_dest_collision(tmp_path):
    repo = _fixture_repo(tmp_path)
    home = _hub_home(tmp_path)
    _pin_member(home, "scout")
    (tmp_path / "ws" / "projects" / "casa-bahia").mkdir(parents=True)
    with pytest.raises(ValueError, match="already exists"):
        await host_recipes.launch(home, _project_recipe(repo), {"slug": "casa-bahia"})


@pytest.mark.asyncio
async def test_launch_rejects_unpinned_member(tmp_path):
    home = _hub_home(tmp_path)
    ghost = """
hub: mira
members: [ghost]
name: "x-{n}"
task: "hi"
params: { n: { required: true } }
"""
    with pytest.raises(ValueError, match="not pinned"):
        await host_recipes.launch(home, ghost, {"n": "1"})


@pytest.mark.asyncio
async def test_launch_rejects_hub_mismatch(tmp_path):
    home = _hub_home(tmp_path)
    other = """
hub: someone-else
members: []
name: "x-{n}"
task: "hi"
params: { n: { required: true } }
"""
    with pytest.raises(ValueError, match="not this profile"):
        await host_recipes.launch(home, other, {"n": "1"})


@pytest.mark.asyncio
async def test_launch_seeds_brief_and_assets_before_kickoff(tmp_path, monkeypatch):
    from alpi.alp import workgroup_client as wc_mod
    repo = _fixture_repo(tmp_path)
    home = _hub_home(tmp_path)
    _pin_member(home, "scout")
    assets_in = tmp_path / "assets_in"
    assets_in.mkdir()
    (assets_in / "hero.jpg").write_bytes(b"img")
    dest = tmp_path / "ws" / "projects" / "casa-bahia"

    seen = {}
    orig_post = wc_mod.post

    async def spy_post(*args, **kwargs):
        seen["brief"] = (dest / "brief.md").read_text()
        seen["asset"] = (dest / "assets" / "hero.jpg").read_bytes()
        return await orig_post(*args, **kwargs)

    monkeypatch.setattr(wc_mod, "post", spy_post)

    await host_recipes.launch(
        home, _project_recipe(repo, with_brief=True), {"slug": "casa-bahia"},
        inputs={"brief": "# Real client brief\nfacts here"}, assets_src=assets_in,
    )
    assert seen["brief"] == "# Real client brief\nfacts here"
    assert seen["asset"] == b"img"


@pytest.mark.asyncio
async def test_launch_rejects_missing_required_input(tmp_path):
    repo = _fixture_repo(tmp_path)
    home = _hub_home(tmp_path)
    _pin_member(home, "scout")

    with pytest.raises(ValueError, match="required input 'brief' is empty"):
        await host_recipes.launch(home, _project_recipe(repo, with_brief=True), {"slug": "casa-bahia"})
    assert not (tmp_path / "ws" / "projects" / "casa-bahia").exists()
    assert not (list((home / "alp" / "workgroups").glob("wg_*")) if (home / "alp" / "workgroups").exists() else [])


@pytest.mark.asyncio
async def test_launch_rejects_unknown_input(tmp_path):
    repo = _fixture_repo(tmp_path)
    home = _hub_home(tmp_path)
    _pin_member(home, "scout")

    with pytest.raises(ValueError, match="unknown input"):
        await host_recipes.launch(
            home, _project_recipe(repo), {"slug": "casa-bahia"}, inputs={"ghost": "x"},
        )
    assert not (tmp_path / "ws" / "projects" / "casa-bahia").exists()


@pytest.mark.asyncio
async def test_launch_writes_input_verbatim(tmp_path):
    repo = _fixture_repo(tmp_path)
    home = _hub_home(tmp_path)
    _pin_member(home, "scout")
    raw = "  leading spaces\nmiddle\n"
    await host_recipes.launch(
        home, _project_recipe(repo, with_brief=True), {"slug": "casa-bahia"}, inputs={"brief": raw},
    )
    assert (tmp_path / "ws" / "projects" / "casa-bahia" / "brief.md").read_text() == raw


@pytest.mark.asyncio
async def test_launch_optional_input_omitted_ok(tmp_path):
    repo = _fixture_repo(tmp_path)
    home = _hub_home(tmp_path)
    _pin_member(home, "scout")
    recipe = _project_recipe(repo).replace(
        "\nproject:", "\ninputs:\n  notes: { dest: notes.md, required: false }\nproject:",
    )
    await host_recipes.launch(home, recipe, {"slug": "casa-bahia"})
    dest = tmp_path / "ws" / "projects" / "casa-bahia"
    assert dest.exists()
    assert not (dest / "notes.md").exists()


def _input_recipe(repo: Path, inputs_yaml: str, name: str = "proj-x", params_yaml: str = "") -> str:
    return f"""
hub: mira
members: [scout]
name: "{name}"
{params_yaml}inputs:
{inputs_yaml}
project:
  template_repo: "{repo}"
  dest: "projects/x"
"""


@pytest.mark.asyncio
async def test_launch_rejects_interpolated_dest_traversal(tmp_path):
    repo = _fixture_repo(tmp_path)
    home = _hub_home(tmp_path)
    _pin_member(home, "scout")
    recipe = _input_recipe(
        repo, "  brief: { dest: '{slug}/brief.md' }", name="proj-{slug}", params_yaml="params: { slug: {} }\n",
    )
    with pytest.raises(ValueError, match="invalid dest"):
        await host_recipes.launch(home, recipe, {"slug": ".."}, inputs={"brief": "x"})
    assert not (tmp_path / "ws" / "projects" / "x").exists()


@pytest.mark.asyncio
async def test_launch_rejects_duplicate_input_dests(tmp_path):
    repo = _fixture_repo(tmp_path)
    home = _hub_home(tmp_path)
    _pin_member(home, "scout")
    recipe = _input_recipe(repo, "  a: { dest: shared.md }\n  b: { dest: shared.md }")
    with pytest.raises(ValueError, match="same dest"):
        await host_recipes.launch(home, recipe, {}, inputs={"a": "1", "b": "2"})
    assert not (tmp_path / "ws" / "projects" / "x").exists()


@pytest.mark.asyncio
async def test_launch_rejects_nested_input_dests(tmp_path):
    repo = _fixture_repo(tmp_path)
    home = _hub_home(tmp_path)
    _pin_member(home, "scout")
    recipe = _input_recipe(repo, "  a: { dest: docs }\n  b: { dest: docs/a.md }")
    with pytest.raises(ValueError, match="nested dest"):
        await host_recipes.launch(home, recipe, {}, inputs={"a": "1", "b": "2"})


@pytest.mark.asyncio
async def test_launch_verb_rejects_non_string_input(tmp_path, monkeypatch):
    from alpi.host import server as host_server
    monkeypatch.setattr(host_recipes, "_resolve_home", lambda p: tmp_path)
    with pytest.raises(host_server.HandlerError) as ei:
        await host_recipes._launch(
            {"profile": "mira", "yaml": "hub: mira\nname: n\n", "inputs": {"brief": 123}}, None,
        )
    assert "must be a string" in str(ei.value.data)


@pytest.mark.asyncio
async def test_launch_interpolates_briefing_override(tmp_path):
    repo = _fixture_repo(tmp_path)
    home = _hub_home(tmp_path)
    _pin_member(home, "scout")
    result = await host_recipes.launch(
        home, _project_recipe(repo), {"slug": "casa-bahia"},
        briefing_override="Workgroup for hotel '{slug}' — edited",
    )
    wg = wg_mod.load(home, result["workgroup_id"])
    assert wg.meta.briefing == "Workgroup for hotel 'casa-bahia' — edited"


@pytest.mark.asyncio
async def test_launch_rolls_back_inputs_on_bad_assets(tmp_path):
    repo = _fixture_repo(tmp_path)
    home = _hub_home(tmp_path)
    _pin_member(home, "scout")
    not_a_dir = tmp_path / "afile"
    not_a_dir.write_text("x")

    with pytest.raises(ValueError, match="assets source is not a directory"):
        await host_recipes.launch(
            home, _project_recipe(repo), {"slug": "casa-bahia"}, assets_src=not_a_dir,
        )
    assert not (tmp_path / "ws" / "projects" / "casa-bahia").exists()
    assert not any((home / "alp" / "workgroups").glob("wg_*")) if (home / "alp" / "workgroups").exists() else True


@pytest.mark.asyncio
async def test_create_destroys_workgroup_on_auto_join_failure(tmp_path, monkeypatch):
    home = _hub_home(tmp_path)
    scout_pk = _pin_member(home, "scout")

    def boom(*a, **k):
        raise RuntimeError("auto-join failed")
    monkeypatch.setattr(wg_mod, "_auto_join_local_members", boom)

    with pytest.raises(RuntimeError):
        wg_mod.create(home, name="proj-x", hub_kp=load_or_generate(home), member_pubkeys=[scout_pk])
    assert not (list((home / "alp" / "workgroups").glob("wg_*")) if (home / "alp" / "workgroups").exists() else [])


def test_destroy_purges_local_subscription(tmp_path, monkeypatch):
    from alpi.alp import subscription as sub_mod
    monkeypatch.setattr("alpi.home._ROOT", tmp_path)
    home = _hub_home(tmp_path)
    hub_kp = load_or_generate(home)
    scout_pk = _pin_member(home, "scout")
    scout_home = home.parent / "scout"
    peers_mod.add(scout_home, Peer(id="mira", pubkey=hub_kp.pubkey_b64(), allow=["workgroup.pull"]))

    wg = wg_mod.create(home, name="proj-x", hub_kp=hub_kp, member_pubkeys=[scout_pk])
    assert sub_mod.get(scout_home, wg.meta.id) is not None

    purged = wg_mod.destroy(home, wg.meta.id)
    assert "scout" in purged
    assert sub_mod.get(scout_home, wg.meta.id) is None
    assert not (home / "alp" / "workgroups" / wg.meta.id).exists()
