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
    pipeline: tuple[str, ...]
    pipeline_steps: dict
    operations: dict
    params: dict
    inputs: dict
    project: dict | None
    raw: dict = field(default_factory=dict)


_PIPELINE_SLUG_RE = _re.compile(r"^[a-z0-9][a-z0-9_-]*$")


def _coerce_operations(
    recipe_id: str, raw: Any, steps: dict, pipeline: tuple[str, ...],
) -> dict:
    # Chains must be disjoint: a slug in two of them would make the active chain depend on YAML order.
    if raw is None:
        return {}
    if not pipeline:
        raise RecipeError(
            f"recipe {recipe_id!r} declares operations without a pipeline; operations are "
            "post-launch chains and the launch pipeline drives continuation"
        )
    if not isinstance(raw, dict):
        raise RecipeError(f"recipe {recipe_id!r} operations must be a mapping")
    out: dict[str, tuple[str, ...]] = {}
    claimed: dict[str, str] = {}
    for name, body in raw.items():
        name = str(name).strip().lower()
        if not name:
            raise RecipeError(f"recipe {recipe_id!r} operations has an empty name")
        if not isinstance(body, dict):
            raise RecipeError(f"recipe {recipe_id!r} operations[{name!r}] must be a mapping")
        ordered = body.get("steps")
        if not isinstance(ordered, list) or not ordered:
            raise RecipeError(
                f"recipe {recipe_id!r} operations[{name!r}].steps must be a non-empty list"
            )
        slugs = tuple(str(x).strip().lower() for x in ordered)
        if slugs[0] != name:
            raise RecipeError(
                f"recipe {recipe_id!r} operations[{name!r}] must start with a step named "
                f"{name!r} so `#task #{name}` opens it; got {slugs[0]!r}"
            )
        if len(set(slugs)) != len(slugs):
            raise RecipeError(f"recipe {recipe_id!r} operations[{name!r}].steps has duplicates")
        for slug in slugs:
            if not _PIPELINE_SLUG_RE.match(slug):
                raise RecipeError(
                    f"recipe {recipe_id!r} operations[{name!r}] step {slug!r} is not a valid slug"
                )
            if slug not in steps:
                raise RecipeError(
                    f"recipe {recipe_id!r} operations[{name!r}] step {slug!r} has no "
                    "pipeline_steps entry"
                )
            if slug in pipeline:
                raise RecipeError(
                    f"recipe {recipe_id!r} operations[{name!r}] step {slug!r} is also a launch "
                    "pipeline phase; chains must be disjoint"
                )
            owner = claimed.get(slug)
            if owner is not None:
                raise RecipeError(
                    f"recipe {recipe_id!r} step {slug!r} belongs to operations {owner!r} and "
                    f"{name!r}; chains must be disjoint"
                )
            claimed[slug] = name
        if name in out:
            raise RecipeError(f"recipe {recipe_id!r} has duplicate operation {name!r}")
        out[name] = slugs
    # Order is checked only once every chain is known to be disjoint.
    for name, slugs in out.items():
        for i, slug in enumerate(slugs):
            declared = str((steps.get(slug) or {}).get("next") or "")
            successor = slugs[i + 1] if i + 1 < len(slugs) else ""
            if declared and declared != successor:
                raise RecipeError(
                    f"recipe {recipe_id!r} operations[{name!r}] step {slug!r} declares "
                    f"next={declared!r} but steps order the successor as "
                    f"{successor or '<none>'!r}"
                )
    return out

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

    pipeline = data.get("pipeline") or []
    if not isinstance(pipeline, list):
        raise RecipeError(f"recipe {recipe_id!r} pipeline must be a list")

    steps = data.get("pipeline_steps") or {}
    if not isinstance(steps, dict):
        raise RecipeError(f"recipe {recipe_id!r} pipeline_steps must be a mapping")

    operations = _coerce_operations(
        recipe_id, data.get("operations"), steps,
        tuple(str(x).strip().lower() for x in pipeline),
    )

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
        task=str(data.get("task") or ""),
        quorum_timeout_seconds=int(data.get("quorum_timeout_seconds") or 0),
        budget_usd=budget_usd,
        pipeline=tuple(str(p).strip() for p in pipeline),
        pipeline_steps=steps,
        operations=operations,
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
        "pipeline": list(recipe.pipeline),
        "pipeline_steps": _interp(recipe.pipeline_steps, params),
        "operations": {k: list(v) for k, v in (recipe.operations or {}).items()},
        "inputs": _interp(recipe.inputs, params),
        "project": _interp(recipe.project, params) if recipe.project else None,
    }
