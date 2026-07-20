"""Stateless recipe launch: client sends recipe content, daemon stores no catalogue."""

from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
import uuid
from pathlib import Path, PurePosixPath
from typing import Any

from alpi.host import server as host_server


class LaunchError(ValueError):
    pass


_STAGING = ".recipe-staging"
_CLONE_TIMEOUT = 120


def register(server: host_server.Server) -> None:
    server.register("host.workgroup.recipes.describe", _describe)
    server.register("host.workgroup.launch_recipe", _launch)


def _resolve_home(profile: str) -> Path:
    from alpi.host.handlers import _resolve_home as _r
    return _r(profile)


def _workspace(home: Path) -> Path:
    from alpi import config as cfg_mod
    return cfg_mod.load(home).workspace_path or home


def _git(args: list[str], cwd: Path | None = None) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=str(cwd) if cwd else None,
        capture_output=True, text=True, timeout=_CLONE_TIMEOUT,
    )
    if proc.returncode != 0:
        raise LaunchError(f"git {args[0]} failed: {(proc.stderr or proc.stdout).strip()[:300]}")
    return proc.stdout.strip()


def _json_merge(base: Any, patch: dict) -> Any:
    if not isinstance(base, dict) or not isinstance(patch, dict):
        return patch
    out = dict(base)
    for k, v in patch.items():
        out[k] = _json_merge(out.get(k), v) if isinstance(v, dict) else v
    return out


def _apply_seed(root: Path, seed: dict) -> None:
    for rel, patch in (seed.get("json_merge") or {}).items():
        target = (root / rel).resolve()
        target.relative_to(root.resolve())
        if not target.is_file():
            raise LaunchError(f"seed json_merge target missing in template: {rel}")
        data = json.loads(target.read_text())
        target.write_text(json.dumps(_json_merge(data, patch), ensure_ascii=False, indent=2) + "\n")
    for rel, content in (seed.get("files") or {}).items():
        target = (root / rel).resolve()
        target.relative_to(root.resolve())
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(str(content))


def _write_input(root: Path, rel: str, content: str) -> None:
    target = (root / rel).resolve()
    target.relative_to(root.resolve())
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)


def _nested(a: PurePosixPath, b: PurePosixPath) -> bool:
    return len(b.parts) > len(a.parts) and b.parts[: len(a.parts)] == a.parts


def _validate_input_dests(inputs: dict) -> None:
    seen: list[tuple[str, PurePosixPath]] = []
    for name, ispec in inputs.items():
        dest = str(ispec.get("dest") or "")
        p = PurePosixPath(dest)
        if not dest or dest == "." or p.is_absolute() or ".." in p.parts:
            raise LaunchError(f"input {name!r} resolves to an invalid dest: {dest!r}")
        seen.append((name, p))
    for i, (n1, p1) in enumerate(seen):
        for n2, p2 in seen[i + 1:]:
            if p1 == p2:
                raise LaunchError(f"inputs {n1!r} and {n2!r} resolve to the same dest: {p1}")
            if _nested(p1, p2) or _nested(p2, p1):
                raise LaunchError(f"inputs {n1!r} and {n2!r} resolve to nested dests: {p1} vs {p2}")


def _apply_assets(dest: Path, assets_src: Path) -> None:
    if not assets_src.is_dir():
        raise LaunchError(f"assets source is not a directory: {assets_src}")
    target = dest / "assets"
    target.mkdir(parents=True, exist_ok=True)
    for f in sorted(assets_src.iterdir()):
        if f.is_file() and not f.name.startswith("."):
            shutil.copy2(f, target / f.name)


def _prepare_project(workspace: Path, spec_project: dict) -> tuple[Path, str]:
    dest = (workspace / spec_project["dest"]).resolve()
    dest.relative_to(workspace.resolve())
    if dest.exists():
        raise LaunchError(f"project destination already exists: {spec_project['dest']}")
    staging = workspace / _STAGING
    staging.mkdir(parents=True, exist_ok=True)
    tmp = staging / uuid.uuid4().hex
    repo = str(spec_project["template_repo"])
    if repo.startswith("-"):
        raise LaunchError(f"template_repo must not start with '-': {repo!r}")
    try:
        _git(["clone", "--quiet", "--", repo, str(tmp)])
        commit = _git(["rev-parse", "HEAD"], cwd=tmp)
        _apply_seed(tmp, spec_project.get("seed") or {})
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            tmp.replace(dest)
        except OSError as e:
            raise LaunchError(f"could not place project at {spec_project['dest']}: {e}")
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    return dest, commit


def _kickoff_text(task: str, pipeline: tuple[str, ...], steps: dict) -> str:
    if task:
        return task
    if not pipeline:
        return ""
    first = pipeline[0]
    step = steps.get(first) or {}
    owner = step.get("owner")
    if not owner:
        return ""
    body = step.get("task") or f"run the {first} phase"
    return f"@{owner} #task #{first} · {body}"


async def launch(
    home: Path, recipe_yaml: str, params: dict[str, str],
    briefing_override: str | None = None, recipe_id: str = "recipe",
    inputs: dict[str, str] | None = None, assets_src: Path | None = None,
) -> dict[str, Any]:
    from alpi import home as home_mod
    from alpi import recipes as recipes_mod
    from alpi.alp import peers as peers_mod
    from alpi.alp import workgroup as wg_mod
    from alpi.alp import workgroup_client as wc
    from alpi.alp.keys import load_or_generate

    recipe = recipes_mod.parse_recipe(recipe_yaml, recipe_id)
    spec = recipes_mod.resolve(recipe, params)

    profile = home_mod.profile_name(home)
    if spec["hub"] != profile:
        raise LaunchError(f"recipe hub {spec['hub']!r} is not this profile {profile!r}")
    peers = {p.id: p for p in peers_mod.load(home)}
    unpinned = [m for m in spec["members"] if m != profile and m not in peers]
    if unpinned:
        raise LaunchError(f"recipe members not pinned as peers of {profile}: {unpinned}")
    pipeline = wg_mod._normalize_pipeline(spec["pipeline"])
    steps = wg_mod.validate_pipeline_steps(pipeline, spec["pipeline_steps"])
    roster = set(spec["members"]) | {profile}
    for phase, st in steps.items():
        if st["owner"] not in roster:
            raise LaunchError(f"pipeline_steps[{phase!r}].owner {st['owner']!r} is not in the roster")

    declared_inputs = spec.get("inputs") or {}
    supplied_inputs = {str(k): v for k, v in (inputs or {}).items()}
    unknown_inputs = set(supplied_inputs) - set(declared_inputs)
    if unknown_inputs:
        raise LaunchError(f"unknown input(s) supplied: {sorted(unknown_inputs)}")
    for iname, ispec in declared_inputs.items():
        val = supplied_inputs.get(iname)
        if ispec.get("required", True) and not (val is not None and str(val).strip()):
            raise LaunchError(f"required input {iname!r} is empty")
    _validate_input_dests(declared_inputs)

    workspace = _workspace(home)
    project_path: str | None = None
    template_commit = ""
    created_dest: Path | None = None
    created_wg_dir: Path | None = None
    briefing = spec["briefing"]
    if briefing_override is not None:
        briefing = recipes_mod._PARAM_TOKEN.sub(
            lambda m: spec["params"].get(m.group(1), m.group(0)), briefing_override,
        )
    try:
        if spec["project"]:
            created_dest, template_commit = await asyncio.to_thread(
                _prepare_project, workspace, spec["project"],
            )
            project_path = str(created_dest)
            for iname, ispec in declared_inputs.items():
                val = supplied_inputs.get(iname)
                if val is None or str(val) == "":
                    continue
                await asyncio.to_thread(_write_input, created_dest, ispec["dest"], str(val))
            if assets_src is not None:
                await asyncio.to_thread(_apply_assets, created_dest, assets_src)
        provenance = {
            "recipe_id": recipe.recipe_id,
            "recipe_digest": recipe.digest,
            "params": spec["params"],
            "project": (spec["project"] or {}).get("dest") if spec["project"] else None,
            "template_commit": template_commit or None,
        }
        wg = wg_mod.create(
            home, name=spec["name"], hub_kp=load_or_generate(home),
            member_pubkeys=[peers[m].pubkey for m in spec["members"] if m in peers],
            budget={"max_usd": spec["budget_usd"]} if spec["budget_usd"] else {},
            briefing=briefing,
            pipeline=pipeline, pipeline_steps=steps,
            quorum_timeout_seconds=spec["quorum_timeout_seconds"],
            launch=provenance,
        )
        created_wg_dir = home / "alp" / "workgroups" / wg.meta.id
        kick = _kickoff_text(spec["task"], pipeline, steps)
        if kick:
            await wc.post(home, wg.meta.id, kick.encode())
    except BaseException:
        if created_wg_dir is not None:
            wg_mod.destroy(home, created_wg_dir.name)
        if created_dest is not None:
            shutil.rmtree(created_dest, ignore_errors=True)
        raise
    return {"workgroup_id": wg.meta.id, "project_path": project_path}


async def _describe(params: dict[str, Any], _server: host_server.Server) -> dict[str, Any]:
    from alpi import recipes as recipes_mod
    yaml_text = str((params or {}).get("yaml") or "")
    recipe_id = str((params or {}).get("recipe_id") or "recipe")
    if not yaml_text.strip():
        raise host_server.HandlerError(-32602, "invalid-params", data={"detail": "empty recipe yaml"})
    try:
        r = recipes_mod.parse_recipe(yaml_text, recipe_id)
    except recipes_mod.RecipeError as e:
        raise host_server.HandlerError(-32602, "invalid-params", data={"detail": str(e)})
    return {
        "id": r.recipe_id, "digest": r.digest, "hub": r.hub,
        "members": list(r.members), "name": r.name, "briefing": r.briefing,
        "task": r.task, "params": r.params, "inputs": r.inputs, "pipeline": list(r.pipeline),
        "has_project": r.project is not None,
    }


async def _launch(params: dict[str, Any], _server: host_server.Server) -> dict[str, Any]:
    home = _resolve_home(str((params or {}).get("profile") or ""))
    yaml_text = str((params or {}).get("yaml") or "")
    recipe_id = str((params or {}).get("recipe_id") or "recipe")
    if not yaml_text.strip():
        raise host_server.HandlerError(-32602, "invalid-params", data={"detail": "empty recipe yaml"})
    supplied = (params or {}).get("params") or {}
    if not isinstance(supplied, dict):
        raise host_server.HandlerError(-32602, "invalid-params", data={"detail": "params must be a mapping"})
    briefing = (params or {}).get("briefing")
    supplied_inputs = (params or {}).get("inputs") or {}
    if not isinstance(supplied_inputs, dict):
        raise host_server.HandlerError(-32602, "invalid-params", data={"detail": "inputs must be a mapping"})
    for k, v in supplied_inputs.items():
        if not isinstance(v, str):
            raise host_server.HandlerError(-32602, "invalid-params", data={"detail": f"input {k!r} must be a string"})
    try:
        result = await launch(
            home, yaml_text, supplied, briefing_override=briefing,
            recipe_id=recipe_id, inputs={str(k): v for k, v in supplied_inputs.items()},
        )
    except ValueError as e:
        raise host_server.HandlerError(-32602, "invalid-params", data={"detail": str(e)})
    from alpi.host import workgroup_admin
    workgroup_admin._emit_workgroup_changed(home, result["workgroup_id"], "created")
    return result
