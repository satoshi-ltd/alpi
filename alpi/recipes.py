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
_RECIPE_SUFFIXES = (".yaml", ".yml")


class RecipeError(ValueError):
    pass


MAX_RECIPE_BYTES = 64 * 1024
MAX_RECIPE_DEPTH = 32
_INT = "tag:yaml.org,2002:int"
_FLOAT = "tag:yaml.org,2002:float"


class _RecipeLoader(yaml.SafeLoader):
    _depth = 0

    def compose_node(self, parent, index):  # noqa: ANN001, ANN201
        if self.check_event(yaml.events.AliasEvent):
            raise yaml.composer.ComposerError(
                None, None, "aliases are not allowed in a recipe", self.peek_event().start_mark,
            )
        self._depth += 1
        try:
            if self._depth > MAX_RECIPE_DEPTH:
                raise yaml.composer.ComposerError(
                    None, None, f"a recipe nests deeper than {MAX_RECIPE_DEPTH} levels", self.peek_event().start_mark,
                )
            return super().compose_node(parent, index)
        finally:
            self._depth -= 1


# YAML 1.1 base-60 numbers (1:2:3) parse in quadratic time; a recipe never needs them.
_RecipeLoader.yaml_implicit_resolvers = {
    first: [(tag, rx) for tag, rx in resolvers if tag not in (_INT, _FLOAT)]
    for first, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
_RecipeLoader.add_implicit_resolver(
    _INT, re.compile(r"^(?:[-+]?0b[0-1_]+|[-+]?0[0-7_]+|[-+]?(?:0|[1-9][0-9_]*)|[-+]?0x[0-9a-fA-F_]+)$"),
    list("-+0123456789"),
)
_RecipeLoader.add_implicit_resolver(
    _FLOAT, re.compile(r"^(?:[-+]?(?:[0-9][0-9_]*)\.[0-9_]*(?:[eE][-+][0-9]+)?|\.[0-9][0-9_]*(?:[eE][-+][0-9]+)?|[-+]?\.(?:inf|Inf|INF)|\.(?:nan|NaN|NAN))$"),
    list("-+0123456789."),
)


def load_recipe_yaml(text: str) -> Any:
    if len(text.encode("utf-8", errors="replace")) > MAX_RECIPE_BYTES:
        raise RecipeError(f"recipe is larger than {MAX_RECIPE_BYTES // 1024} KB")
    return yaml.load(text, Loader=_RecipeLoader)


def _scalar(recipe_id: str, data: dict, key: str) -> str:
    value = data.get(key)
    if value is None or isinstance(value, bool):
        return ""
    if isinstance(value, (str, int, float)):
        return str(value)
    raise RecipeError(f"recipe {recipe_id!r} {key} must be text")


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
    steps: dict, task: str, hub: str,
) -> None:
    if steps and not pipelines:
        raise RecipeError(
            f"recipe {recipe_id!r} declares pipeline_steps without any pipeline; gate "
            "specs with no chain to order them would run unconstrained"
        )
    # Gate owners resolve through peers.load(); the hub is not its own peer, so a hub-owned gate never runs.
    gated_hub = sorted(
        phase for phase, spec in steps.items()
        if spec.get("gate") and spec["owner"].lower() == hub.lower()
    )
    if gated_hub:
        raise RecipeError(
            f"recipe {recipe_id!r} declares a gate on hub-owned phase(s) {gated_hub}; "
            "a gate verifies a member's delivery — assign a member owner or drop the gate"
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
        from alpi.alp import tasks as tasks_mod
        first = pipelines[launch_pipeline][0]
        # The parsed opener, not a substring: "#media-update … #intake" must not pass for launch=intake.
        events = tasks_mod.parse_post(task.lower(), 0, "hub", hub_pubkey="hub")
        opener = next((e.slug for e in events if e.kind == "task"), "")
        if opener != first:
            raise RecipeError(
                f"recipe {recipe_id!r} task must open the launch pipeline's first phase "
                f"`#{first}` as its `#task` slug (parsed `#{opener or 'none'}`)"
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


def _coerce_exclude(recipe_id: str, raw: Any) -> list[str]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise RecipeError(f"recipe {recipe_id!r} project.exclude must be a list of relative paths")
    out: list[str] = []
    for item in raw:
        if not isinstance(item, str) or not item.strip():
            raise RecipeError(f"recipe {recipe_id!r} project.exclude entries must be non-empty strings")
        if any(ord(ch) < 32 or ord(ch) == 127 for ch in item):
            raise RecipeError(f"recipe {recipe_id!r} project.exclude entries must not contain control characters")
        path = item.strip().strip("/")
        parts = path.split("/")
        if not path or any(part in ("", ".", "..") for part in parts) or any(ch in path for ch in "*?[!\\"):
            raise RecipeError(f"recipe {recipe_id!r} project.exclude entry must be a plain relative path: {item!r}")
        if path not in out:
            out.append(path)
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
    if not _RECIPE_ID_RE.fullmatch(recipe_id):
        raise RecipeError(f"recipe id {recipe_id!r} must match [a-z0-9][a-z0-9_-]*")
    try:
        data = load_recipe_yaml(text) or {}
    except yaml.YAMLError as e:
        raise RecipeError(f"recipe {recipe_id!r} is not valid YAML: {e}")
    except RecipeError:
        raise
    except (RecursionError, ValueError, OverflowError) as e:
        raise RecipeError(f"recipe {recipe_id!r} cannot be read: {type(e).__name__}")
    if not isinstance(data, dict):
        raise RecipeError(f"recipe {recipe_id!r} must be a YAML mapping")

    hub = _scalar(recipe_id, data, "hub").strip()
    if not hub:
        raise RecipeError(f"recipe {recipe_id!r} missing 'hub'")
    name = _scalar(recipe_id, data, "name").strip()
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
    task = _scalar(recipe_id, data, "task")
    _check_launch_semantics(recipe_id, pipelines, launch_pipeline, steps, task.strip(), hub)

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
        project["exclude"] = _coerce_exclude(recipe_id, project.get("exclude"))

    try:
        quorum_timeout_seconds = int(data.get("quorum_timeout_seconds") or 0)
    except (TypeError, ValueError):
        raise RecipeError(f"recipe {recipe_id!r} quorum_timeout_seconds must be a whole number of seconds")

    digest = "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
    return Recipe(
        recipe_id=recipe_id,
        digest=digest,
        hub=hub,
        members=_coerce_members(data.get("members")),
        name=name,
        briefing=_scalar(recipe_id, data, "briefing"),
        task=task,
        quorum_timeout_seconds=quorum_timeout_seconds,
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


def saved_recipe_path(home: Path, recipe_id: str) -> Path:
    if not _RECIPE_ID_RE.fullmatch(recipe_id):
        raise RecipeError(f"recipe id {recipe_id!r} must match [a-z0-9][a-z0-9_-]*")
    root = home / "recipes"
    if root.is_symlink():
        raise RecipeError(f"saved recipe directory must not be a symlink: {root}")
    for suffix in _RECIPE_SUFFIXES:
        path = root / f"{recipe_id}{suffix}"
        if path.is_file() and not path.is_symlink():
            return path
    raise RecipeError(f"saved recipe {recipe_id!r} not found in {root}")


def load_saved_recipe(home: Path, recipe_id: str) -> tuple[Recipe, str]:
    path = saved_recipe_path(home, recipe_id)
    text = path.read_text(encoding="utf-8")
    return parse_recipe(text, recipe_id), text


def list_saved_recipes(home: Path) -> list[Recipe]:
    recipes, invalid = scan_saved_recipes(home)
    if invalid:
        raise RecipeError(invalid[0]["detail"])
    return recipes


def scan_saved_recipes(home: Path) -> tuple[list[Recipe], list[dict[str, str]]]:
    root = home / "recipes"
    if root.is_symlink():
        raise RecipeError(f"saved recipe directory must not be a symlink: {root}")
    if not root.is_dir():
        return [], []
    out: list[Recipe] = []
    invalid: list[dict[str, str]] = []
    candidates: dict[str, list[Path]] = {}
    for path in sorted(root.iterdir(), key=lambda p: p.name):
        if path.suffix not in _RECIPE_SUFFIXES or path.is_symlink() or not path.is_file():
            continue
        candidates.setdefault(path.stem, []).append(path)
    for recipe_id, paths in candidates.items():
        if len(paths) > 1:
            invalid.append({
                "id": recipe_id,
                "detail": f"duplicate saved recipe id {recipe_id!r} in {root}",
            })
            continue
        try:
            out.append(parse_recipe(paths[0].read_text(encoding="utf-8"), recipe_id))
        except (OSError, UnicodeError, RecipeError) as e:
            invalid.append({"id": recipe_id, "detail": str(e)})
    return out, invalid


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

    project = _interp(recipe.project, params) if recipe.project else None
    if project is not None:
        project["exclude"] = _coerce_exclude(recipe.recipe_id, project.get("exclude"))

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
        "project": project,
    }
