"""Pure recipe model: load/validate/resolve. Creates nothing — the host launch service materialises a resolved recipe."""

from __future__ import annotations

import hashlib
import re as _re
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

_PARAM_TOKEN = re.compile(r"\{([a-z0-9_]+)\}")
_RECIPE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


class RecipeError(ValueError):
    pass


@dataclass(frozen=True)
class Recipe:
    recipe_id: str
    digest: str
    hub: str
    members: tuple[str, ...]
    name: str
    briefing: str
    task: str
    quorum_timeout_seconds: int
    budget_usd: float | None
    pipelines: dict
    launch_pipeline: str | None
    pipeline_steps: dict
    params: dict
    inputs: dict
    project: dict | None
    raw: dict = field(default_factory=dict)

    @property
    def launch_chain(self) -> tuple[str, ...]:
        return tuple(self.pipelines.get(self.launch_pipeline or "", ()))


_TASK_SLUG_RE = _re.compile(r"#([a-z0-9][a-z0-9_-]*)")


def _coerce_pipelines(recipe_id: str, data: dict) -> tuple[dict, str | None]:
    """A recipe is the ONLY place chains are declared; the retired `pipeline`/`operations` pair is rejected."""
    from alpi.alp import workgroup as wg_mod

    try:
        wg_mod.reject_retired_keys(data, f"recipe {recipe_id!r}")
        pipelines = wg_mod.normalize_pipelines(data.get("pipelines"))
        return pipelines, wg_mod.normalize_launch_pipeline(
            pipelines, data.get("launch"),
        )
    except ValueError as e:
        raise RecipeError(f"recipe {recipe_id!r} {e}" if str(e).startswith(("pipeline", "launch", "phase", "duplicate")) else str(e))


def _check_launch_semantics(
    recipe_id: str, pipelines: dict, launch_pipeline: str | None,
    steps: dict, task: str,
) -> None:
    if steps and not pipelines:
        raise RecipeError(
            f"recipe {recipe_id!r} declares pipeline_steps without any pipeline; gate "
            "specs with no chain to order them would run unconstrained"
        )
    for key, chain in pipelines.items():
        missing = [slug for slug in chain if not (steps.get(slug) or {}).get("owner")]
        if missing:
            raise RecipeError(
                f"recipe {recipe_id!r} pipeline {key!r} has phases with no owner in "
                f"pipeline_steps: {missing}"
            )
        spec = steps.get(chain[0]) or {}
        if not str(spec.get("task") or "").strip():
            raise RecipeError(
                f"recipe {recipe_id!r} pipeline {key!r} cannot be triggered: its first "
                f"phase {chain[0]!r} must declare both an owner and a task"
            )
    if not task:
        return
    if pipelines and launch_pipeline is None:
        raise RecipeError(
            f"recipe {recipe_id!r} declares pipelines with no `launch` but also a `task`; "
            "an idle pipeline workgroup posts no kickoff — drop the task or select a launch"
        )
    if launch_pipeline is not None:
        first = pipelines[launch_pipeline][0]
        if first not in set(_TASK_SLUG_RE.findall(task.lower())):
            raise RecipeError(
                f"recipe {recipe_id!r} task must open the launch pipeline's first phase "
                f"`#{first}`"
            )


def _coerce_members(raw: Any) -> tuple[str, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise RecipeError("members must be a list of peer ids")
    return tuple(str(m).strip() for m in raw if str(m).strip())


def _coerce_params(raw: Any) -> dict:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise RecipeError("params must be a mapping of name → {pattern}")
    out: dict = {}
    for name, spec in raw.items():
        name = str(name)
        if not _PARAM_TOKEN.fullmatch("{" + name + "}"):
            raise RecipeError(f"param name {name!r} must match [a-z0-9_]+")
        spec = spec or {}
        if not isinstance(spec, dict):
            raise RecipeError(f"param {name!r} spec must be a mapping")
        pattern = spec.get("pattern")
        if pattern is not None:
            try:
                re.compile(str(pattern))
            except re.error as e:
                raise RecipeError(f"param {name!r} pattern is not valid regex: {e}")
        out[name] = {"pattern": (str(pattern) if pattern is not None else None)}
    return out


def _coerce_inputs(raw: Any, has_project: bool) -> dict:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise RecipeError("inputs must be a mapping of name → {dest, label?, placeholder?, required?}")
    if raw and not has_project:
        raise RecipeError("inputs require a project block — each input seeds a file in the clone")
    out: dict = {}
    for name, spec in raw.items():
        name = str(name)
        if not _PARAM_TOKEN.fullmatch("{" + name + "}"):
            raise RecipeError(f"input name {name!r} must match [a-z0-9_]+")
        spec = spec or {}
        if not isinstance(spec, dict):
            raise RecipeError(f"input {name!r} spec must be a mapping")
        dest = str(spec.get("dest") or "").strip()
        if not dest:
            raise RecipeError(f"input {name!r} requires a dest (relative file path in the project)")
        if dest.startswith("/") or ".." in Path(dest).parts:
            raise RecipeError(f"input {name!r} dest must be a relative path inside the project: {dest!r}")
        out[name] = {
            "dest": dest,
            "label": str(spec.get("label") or name),
            "placeholder": str(spec.get("placeholder") or ""),
            "required": bool(spec.get("required", True)),
        }
    return out


def parse_recipe(text: str, recipe_id: str) -> Recipe:
    if not _RECIPE_ID_RE.match(recipe_id):
        raise RecipeError(f"recipe id {recipe_id!r} must match [a-z0-9][a-z0-9_-]*")
    try:
        data = yaml.safe_load(text) or {}
    except yaml.YAMLError as e:
        raise RecipeError(f"recipe {recipe_id!r} is not valid YAML: {e}")
    if not isinstance(data, dict):
        raise RecipeError(f"recipe {recipe_id!r} must be a YAML mapping")

    hub = str(data.get("hub") or "").strip()
    if not hub:
        raise RecipeError(f"recipe {recipe_id!r} missing 'hub'")
    name = str(data.get("name") or "").strip()
    if not name:
        raise RecipeError(f"recipe {recipe_id!r} missing 'name'")

    budget_usd = data.get("budget_usd")
    if budget_usd is not None:
        try:
            budget_usd = float(budget_usd)
        except (TypeError, ValueError):
            raise RecipeError(f"recipe {recipe_id!r} budget_usd must be a number")

    pipelines, launch_pipeline = _coerce_pipelines(recipe_id, data)

    if data.get("pipeline_steps") is not None and not isinstance(data["pipeline_steps"], dict):
        raise RecipeError(f"recipe {recipe_id!r} pipeline_steps must be a mapping")
    from alpi.alp import workgroup as wg_mod
    try:
        steps = wg_mod.validate_pipeline_steps(pipelines, data.get("pipeline_steps"))
    except ValueError as e:
        raise RecipeError(f"recipe {recipe_id!r} {e}")
    task = str(data.get("task") or "")
    _check_launch_semantics(recipe_id, pipelines, launch_pipeline, steps, task.strip())

    project = data.get("project")
    if project is not None:
        if not isinstance(project, dict):
            raise RecipeError(f"recipe {recipe_id!r} project must be a mapping")
        if not str(project.get("template_repo") or "").strip():
            raise RecipeError(f"recipe {recipe_id!r} project.template_repo required")
        if not str(project.get("dest") or "").strip():
            raise RecipeError(f"recipe {recipe_id!r} project.dest required")
        seed = project.get("seed") or {}
        if seed and not isinstance(seed, dict):
            raise RecipeError(f"recipe {recipe_id!r} project.seed must be a mapping")
        for key, val in seed.items():
            if key not in ("json_merge", "files"):
                raise RecipeError(f"recipe {recipe_id!r} project.seed unknown op {key!r} — use json_merge or files")
            if not isinstance(val, dict):
                raise RecipeError(f"recipe {recipe_id!r} project.seed.{key} must be a mapping of path → value")

    digest = "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
    return Recipe(
        recipe_id=recipe_id,
        digest=digest,
        hub=hub,
        members=_coerce_members(data.get("members")),
        name=name,
        briefing=str(data.get("briefing") or ""),
        task=task,
        quorum_timeout_seconds=int(data.get("quorum_timeout_seconds") or 0),
        budget_usd=budget_usd,
        pipelines=pipelines,
        launch_pipeline=launch_pipeline,
        pipeline_steps=steps,
        params=_coerce_params(data.get("params")),
        inputs=_coerce_inputs(data.get("inputs"), project is not None),
        project=project,
        raw=data,
    )


def load_recipe(path: Path) -> Recipe:
    return parse_recipe(path.read_text(), path.stem)


def _placeholders(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, str):
        found.update(_PARAM_TOKEN.findall(value))
    elif isinstance(value, dict):
        for v in value.values():
            found |= _placeholders(v)
    elif isinstance(value, (list, tuple)):
        for v in value:
            found |= _placeholders(v)
    return found


def _interp(value: Any, params: dict) -> Any:
    if isinstance(value, str):
        return _PARAM_TOKEN.sub(lambda m: params[m.group(1)], value)
    if isinstance(value, dict):
        return {k: _interp(v, params) for k, v in value.items()}
    if isinstance(value, list):
        return [_interp(v, params) for v in value]
    return value


def resolve(recipe: Recipe, params: dict[str, str]) -> dict:
    # Single-pass, non-recursive interpolation; raises on any param/placeholder contract breach.
    clean: dict[str, str] = {}
    for k, v in (params or {}).items():
        if isinstance(v, bool) or not isinstance(v, (str, int, float)):
            raise RecipeError(f"param {k!r} must be a string/number, got {type(v).__name__}")
        sv = str(v)
        if "\n" in sv or "\r" in sv:
            raise RecipeError(f"param {k!r} must not contain newlines")
        clean[str(k)] = sv
    params = clean

    declared = recipe.params
    missing_declared = [name for name in declared if name not in params]
    if missing_declared:
        raise RecipeError(f"missing required param(s): {sorted(missing_declared)}")
    unknown = set(params) - set(declared)
    if unknown:
        raise RecipeError(f"unknown param(s) supplied: {sorted(unknown)}")
    for name, value in params.items():
        pat = declared[name]["pattern"]
        if pat and not re.fullmatch(pat, value):
            raise RecipeError(f"param {name!r}={value!r} does not match {pat!r}")

    used = _placeholders([recipe.name, recipe.briefing, recipe.task, recipe.pipeline_steps, recipe.project, recipe.inputs])
    undeclared = used - set(declared)
    if undeclared:
        raise RecipeError(f"recipe uses undeclared placeholder(s): {sorted(undeclared)}")
    missing = used - set(params)
    if missing:
        raise RecipeError(f"placeholder(s) with no value: {sorted(missing)}")

    return {
        "recipe_id": recipe.recipe_id,
        "recipe_digest": recipe.digest,
        "params": params,
        "hub": recipe.hub,
        "members": list(recipe.members),
        "name": _interp(recipe.name, params),
        "briefing": _interp(recipe.briefing, params),
        "task": _interp(recipe.task, params),
        "quorum_timeout_seconds": recipe.quorum_timeout_seconds,
        "budget_usd": recipe.budget_usd,
        "pipelines": {k: list(v) for k, v in (recipe.pipelines or {}).items()},
        "launch_pipeline": recipe.launch_pipeline,
        "pipeline_steps": _interp(recipe.pipeline_steps, params),
        "inputs": _interp(recipe.inputs, params),
        "project": _interp(recipe.project, params) if recipe.project else None,
    }
