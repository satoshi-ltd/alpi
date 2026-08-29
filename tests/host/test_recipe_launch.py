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
from alpi.host import workgroup as host_wg

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


_CANONICAL_CHAINS = """pipelines:
  intake: [intake, content]
  media-update: [media-update, media-recheck]
launch: intake
"""

_RETIRED_CHAINS = """pipeline: [intake, content]
operations:
  media-update:
    steps: [media-update, media-recheck]
"""

_EXPECTED_CHAINS = {
    "intake": ("intake", "content"),
    "media-update": ("media-update", "media-recheck"),
}


def test_recipe_git_allows_slow_template_clones(monkeypatch):
    seen = {}

    def fake_run(*args, **kwargs):
        seen.update(kwargs)
        return subprocess.CompletedProcess(args[0], 0, stdout="", stderr="")

    monkeypatch.setattr(host_recipes.subprocess, "run", fake_run)

    host_recipes._git(["status"])

    assert seen["timeout"] == 300


def _project_recipe(repo: Path, with_brief: bool = False, retired: bool = False) -> str:
    inputs = "\ninputs:\n  brief: { dest: brief.md, required: true }\n" if with_brief else ""
    chains = _RETIRED_CHAINS if retired else _CANONICAL_CHAINS
    return f"""
hub: mira
members: [scout]
name: "proj-{{slug}}"
quorum_timeout_seconds: 120
briefing: "Hotel {{slug}}"
{chains}pipeline_steps:
  intake: {{ owner: scout, task: "start {{slug}}", gate: {{ argv: ["true"], cwd: "projects/{{slug}}" }} }}
  content: {{ owner: scout }}
  media-update: {{ owner: scout, task: "refresh media for {{slug}}" }}
  media-recheck: {{ owner: scout }}
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


_IDLE_RECIPE = """
hub: mira
members: [scout]
name: "idle-{slug}"
pipelines:
  media-update: [media-update, media-recheck]
pipeline_steps:
  media-update: { owner: scout, task: "refresh media for {slug}" }
  media-recheck: { owner: scout }
params:
  slug: { pattern: "^[a-z0-9-]+$" }
"""

_LAUNCHING_RECIPE = _IDLE_RECIPE + "launch: media-update\n"


def _bodies(home: Path, wg_id: str) -> list[str]:
    return [p["body"] for p in host_wg.decrypt_transcript(home, wg_id)]


def test_recipe_verb_gating_invariants():
    from alpi.host import server as host_server
    assert "host.workgroup.recipes.list" in host_server._ADMIN_METHODS
    assert "host.workgroup.launch_recipe" in host_server._ADMIN_METHODS
    assert "host.workgroup.trigger" in host_server._ADMIN_METHODS
    assert "host.workgroup.recipes.describe" in host_server._SCOPE_FREE_METHODS
    assert "host.workgroup.recipes.list" not in host_server._SCOPE_FREE_METHODS
    assert "host.workgroup.launch_recipe" not in host_server._SCOPE_FREE_METHODS
    assert "host.workgroup.trigger" not in host_server._SCOPE_FREE_METHODS


@pytest.mark.asyncio
async def test_list_saved_recipes_for_profile(tmp_path, monkeypatch):
    home = _hub_home(tmp_path)
    recipes = home / "recipes"
    recipes.mkdir()
    (recipes / "hotel.yaml").write_text(_IDLE_RECIPE)
    monkeypatch.setattr(host_recipes, "_resolve_home", lambda profile: home)

    result = await host_recipes._list({"profile": "mira"}, None)

    assert [r["id"] for r in result["recipes"]] == ["hotel"]
    assert result["recipes"][0]["hub"] == "mira"
    assert result["recipes"][0]["pipelines"] == {
        "media-update": ["media-update", "media-recheck"],
    }


@pytest.mark.asyncio
async def test_list_skips_invalid_and_foreign_hub_recipes(tmp_path, monkeypatch):
    home = _hub_home(tmp_path)
    recipes = home / "recipes"
    recipes.mkdir()
    (recipes / "hotel.yaml").write_text(_IDLE_RECIPE)
    (recipes / "foreign.yaml").write_text(_IDLE_RECIPE.replace("hub: mira", "hub: scout"))
    (recipes / "broken.yaml").write_text("hub: mira\n")
    monkeypatch.setattr(host_recipes, "_resolve_home", lambda profile: home)

    result = await host_recipes._list({"profile": "mira"}, None)

    assert [r["id"] for r in result["recipes"]] == ["hotel"]
    assert [r["id"] for r in result["invalid_recipes"]] == ["broken", "foreign"]


@pytest.mark.asyncio
async def test_describe_returns_shape_without_storing(tmp_path):
    res = await host_recipes._describe({"yaml": _CHAT_RECIPE}, None)
    assert res["hub"] == "mira"
    assert "topic" in res["params"]
    assert res["has_project"] is False
    assert res["task"] == "@scout discuss {topic}"
    assert res["pipelines"] == {}
    assert res["launch_pipeline"] is None
    assert res["pipeline_mode"] is False
    assert "pipeline" not in res
    assert "operations" not in res
    assert not (tmp_path / "recipes").exists()


@pytest.mark.asyncio
async def test_describe_reports_every_chain_and_the_launch_selector(tmp_path):
    res = await host_recipes._describe({"yaml": _project_recipe(tmp_path / "repo")}, None)
    assert res["pipelines"] == {
        "intake": ["intake", "content"],
        "media-update": ["media-update", "media-recheck"],
    }
    assert res["launch_pipeline"] == "intake"
    assert res["pipeline_mode"] is True
    assert "pipeline" not in res


@pytest.mark.asyncio
async def test_describe_distinguishes_idle_from_launching_recipe():
    idle = await host_recipes._describe({"yaml": _IDLE_RECIPE}, None)
    launching = await host_recipes._describe({"yaml": _LAUNCHING_RECIPE}, None)
    assert idle["pipelines"] == launching["pipelines"]
    assert idle["launch_pipeline"] is None
    assert idle["pipeline_mode"] is True
    assert launching["launch_pipeline"] == "media-update"
    assert launching["pipeline_mode"] is True
    assert "pipeline" not in idle
    assert "pipeline" not in launching


@pytest.mark.asyncio
@pytest.mark.parametrize("retired", [
    "pipeline: [intake]\n",
    "operations:\n  patch:\n    steps: [patch, patch-qa]\n",
])
async def test_describe_rejects_the_retired_shape(retired):
    from alpi.host import server as host_server
    with pytest.raises(host_server.HandlerError) as ei:
        await host_recipes._describe({"yaml": _IDLE_RECIPE + retired}, None)
    assert "declares retired" in str(ei.value.data)


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
    assert wg.meta.pipelines == _EXPECTED_CHAINS
    assert wg.meta.launch_pipeline == "intake"
    assert wg.meta.launch_chain == ("intake", "content")
    assert wg_mod.dormant_pipelines(wg.meta) == {
        "media-update": ("media-update", "media-recheck"),
    }
    assert wg.meta.pipeline_steps["intake"]["gate"] == {
        "argv": ["true"], "cwd": "projects/casa-bahia",
    }
    assert "next" not in wg.meta.pipeline_steps["intake"]
    assert wg.meta.quorum_timeout_seconds == 120
    assert wg.meta.launch["recipe_id"] == "recipe"
    assert wg.meta.launch["params"] == {"slug": "casa-bahia"}
    assert wg.meta.launch["template_commit"]

    transcript = (home / "alp" / "workgroups" / wg.meta.id / "transcript.jsonl").read_text()
    assert transcript.strip()
    assert _bodies(home, wg.meta.id) == ["@scout #task #intake · start casa-bahia"]


@pytest.mark.asyncio
async def test_launch_rejects_a_recipe_on_the_retired_shape(tmp_path):
    repo = _fixture_repo(tmp_path)
    home = _hub_home(tmp_path)
    _pin_member(home, "scout")

    with pytest.raises(ValueError, match="declares retired"):
        await host_recipes.launch(
            home, _project_recipe(repo, retired=True), {"slug": "casa-dos"},
        )
    assert not (tmp_path / "ws" / "projects" / "casa-dos").exists()
    root = home / "alp" / "workgroups"
    assert not (list(root.glob("wg_*")) if root.exists() else [])


@pytest.mark.asyncio
async def test_launch_launchless_pipeline_recipe_posts_no_kickoff(tmp_path):
    home = _hub_home(tmp_path)
    _pin_member(home, "scout")

    result = await host_recipes.launch(home, _IDLE_RECIPE, {"slug": "casa-bahia"})

    wg = wg_mod.load(home, result["workgroup_id"])
    assert wg.meta.name == "idle-casa-bahia"
    assert wg.meta.pipelines == {"media-update": ("media-update", "media-recheck")}
    assert wg.meta.launch_pipeline is None
    assert wg.meta.launch_chain == ()
    assert wg.meta.pipeline_steps["media-update"]["task"] == "refresh media for casa-bahia"
    assert (home / "alp" / "workgroups" / wg.meta.id / "transcript.jsonl").read_text() == ""
    assert _bodies(home, wg.meta.id) == []


@pytest.mark.asyncio
async def test_launch_selected_chain_kickoff_comes_from_its_first_phase(tmp_path):
    home = _hub_home(tmp_path)
    _pin_member(home, "scout")

    result = await host_recipes.launch(home, _LAUNCHING_RECIPE, {"slug": "casa-bahia"})

    wg = wg_mod.load(home, result["workgroup_id"])
    assert wg.meta.launch_pipeline == "media-update"
    assert _bodies(home, wg.meta.id) == [
        "@scout #task #media-update · refresh media for casa-bahia",
    ]


@pytest.mark.asyncio
async def test_launch_rejects_step_owner_outside_roster(tmp_path):
    repo = _fixture_repo(tmp_path)
    home = _hub_home(tmp_path)
    _pin_member(home, "scout")
    recipe = _project_recipe(repo).replace(
        "content: { owner: scout }", "content: { owner: ghost }",
    )
    with pytest.raises(ValueError, match="is not in the roster"):
        await host_recipes.launch(home, recipe, {"slug": "casa-bahia"})
    assert not (tmp_path / "ws" / "projects" / "casa-bahia").exists()
    assert not (list((home / "alp" / "workgroups").glob("wg_*")) if (home / "alp" / "workgroups").exists() else [])


@pytest.mark.asyncio
async def test_launch_rejects_gate_on_hub_owned_phase_after_interpolation(tmp_path):
    repo = _fixture_repo(tmp_path)
    home = _hub_home(tmp_path)
    _pin_member(home, "scout")
    recipe = _project_recipe(repo).replace(
        "intake: { owner: scout,", 'intake: { owner: "{lead}",',
    ).replace(
        '  slug: { pattern: "^[a-z0-9-]+$" }',
        '  slug: { pattern: "^[a-z0-9-]+$" }\n  lead: { pattern: "^[a-z]+$" }',
    )
    with pytest.raises(ValueError, match="hub-owned"):
        await host_recipes.launch(home, recipe, {"slug": "casa-bahia", "lead": "mira"})
    assert not (tmp_path / "ws" / "projects" / "casa-bahia").exists()
    assert not (list((home / "alp" / "workgroups").glob("wg_*")) if (home / "alp" / "workgroups").exists() else [])


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
    assert wg.meta.pipelines == {}
    assert wg.meta.launch_pipeline is None
    assert wg.meta.launch_chain == ()
    assert wg_mod.is_pipeline_workgroup(wg.meta) is False
    assert _bodies(home, wg.meta.id) == ["@scout discuss pricing"]


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
async def test_launch_seeds_brief_before_kickoff(tmp_path, monkeypatch):
    from alpi.alp import workgroup_client as wc_mod
    repo = _fixture_repo(tmp_path)
    home = _hub_home(tmp_path)
    _pin_member(home, "scout")
    dest = tmp_path / "ws" / "projects" / "casa-bahia"

    seen = {}
    orig_post = wc_mod.post

    async def spy_post(*args, **kwargs):
        seen["brief"] = (dest / "brief.md").read_text()
        return await orig_post(*args, **kwargs)

    monkeypatch.setattr(wc_mod, "post", spy_post)

    await host_recipes.launch(
        home, _project_recipe(repo, with_brief=True), {"slug": "casa-bahia"},
        inputs={"brief": "# Real client brief\nfacts here"},
    )
    assert seen["brief"] == "# Real client brief\nfacts here"


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
async def test_launch_verb_loads_saved_recipe_by_id(tmp_path, monkeypatch):
    home = _hub_home(tmp_path)
    _pin_member(home, "scout")
    recipes = home / "recipes"
    recipes.mkdir()
    (recipes / "chat.yaml").write_text(_CHAT_RECIPE)
    monkeypatch.setattr(host_recipes, "_resolve_home", lambda p: home)

    result = await host_recipes._launch(
        {"profile": "mira", "recipe_id": "chat", "params": {"topic": "pricing"}}, None,
    )

    wg = wg_mod.load(home, result["workgroup_id"])
    assert wg.meta.name == "debate-pricing"


@pytest.mark.asyncio
async def test_launch_verb_keeps_supplied_yaml_import_path(tmp_path, monkeypatch):
    home = _hub_home(tmp_path)
    _pin_member(home, "scout")
    recipes = home / "recipes"
    recipes.mkdir()
    (recipes / "chat.yaml").write_text(_CHAT_RECIPE.replace("debate-", "saved-"))
    monkeypatch.setattr(host_recipes, "_resolve_home", lambda p: home)

    result = await host_recipes._launch(
        {
            "profile": "mira",
            "yaml": _CHAT_RECIPE,
            "recipe_id": "chat",
            "params": {"topic": "pricing"},
        },
        None,
    )

    wg = wg_mod.load(home, result["workgroup_id"])
    assert wg.meta.name == "debate-pricing"


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
