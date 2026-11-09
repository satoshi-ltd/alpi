from __future__ import annotations

import contextvars
import copy
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from fnmatch import fnmatchcase


_allowed: contextvars.ContextVar[frozenset[str] | None] = contextvars.ContextVar(
    "alpi_tool_policy_allowed", default=None,
)
_label: contextvars.ContextVar[str] = contextvars.ContextVar("alpi_tool_policy_label", default="")
_withheld: contextvars.ContextVar[frozenset[str]] = contextvars.ContextVar(
    "alpi_tool_policy_withheld", default=frozenset(),
)
_fenced: contextvars.ContextVar[bool] = contextvars.ContextVar("alpi_tool_policy_fenced", default=False)


@contextmanager
def use(
    allowed: Iterable[str] | None,
    label: str,
    withheld: Iterable[str] = (),
    *,
    fence_without_policy: bool = False,
    fenced: bool = False,
) -> Iterator[None]:
    entries = None if allowed is None else frozenset(str(a).strip() for a in allowed if str(a).strip())
    allowed_token = _allowed.set(entries)
    label_token = _label.set(label)
    withheld_token = _withheld.set(frozenset(withheld) if (entries is None or fenced) else frozenset())
    fenced_token = _fenced.set(fenced or (fence_without_policy and entries is None))
    try:
        yield
    finally:
        _fenced.reset(fenced_token)
        _withheld.reset(withheld_token)
        _label.reset(label_token)
        _allowed.reset(allowed_token)


def fences_private_areas() -> bool:
    return _fenced.get()


def allowed() -> frozenset[str] | None:
    return _allowed.get()


def effective_denies(profile_denies: Iterable[str]) -> frozenset[str]:
    from alpi.tools._paths import dispatch_tool_denies
    return frozenset(profile_denies) | dispatch_tool_denies()


def _matches(name: str, pattern: str) -> bool:
    return name == pattern or ("*" in pattern and fnmatchcase(name, pattern))


def is_denied(name: str, deny: Iterable[str] | None) -> bool:
    if not deny:
        return False
    return any(_matches(name, entry) for entry in deny)


def denied_actions(name: str, deny: Iterable[str] | None) -> frozenset[str]:
    """Actions a ``tool:action`` deny entry removes from ``name``; ``tool:*`` denies every action."""
    out: set[str] = set()
    for entry in deny or ():
        tool, sep, action = str(entry).partition(":")
        if sep and action and _matches(name, tool):
            out.add(action)
    return frozenset(out)


def denied_schema(
    schema: dict, deny: Iterable[str] | None,
    action_parameters: dict[str, frozenset[str]] | None = None,
) -> dict | None:
    """The schema with denied actions removed from its ``action`` enum (and the parameters only they read); None when nothing of the tool is left."""
    name = str((schema.get("function") or {}).get("name") or "")
    denied = denied_actions(name, deny)
    if not denied:
        return schema
    prop = _action_property(schema)
    enum = prop.get("enum") if prop is not None else None
    if not isinstance(enum, list):
        return None if "*" in denied else schema
    keep = frozenset() if "*" in denied else frozenset(a for a in enum if a not in denied)
    if not keep:
        return None
    trimmed = _trim_actions(schema, keep)
    if action_parameters:
        needed = {p for action in keep for p in action_parameters.get(action, frozenset())}
        owned = {p for params in action_parameters.values() for p in params}
        properties = trimmed["function"]["parameters"]["properties"]
        for param in list(properties):
            if param in owned and param not in needed:
                properties.pop(param)
        required = trimmed["function"]["parameters"].get("required")
        if isinstance(required, list):
            trimmed["function"]["parameters"]["required"] = [r for r in required if r in properties]
    return trimmed


def action_denied(name: str, arguments: object, deny: Iterable[str] | None, schema: dict | None = None) -> str | None:
    """A refusal for a call whose action a ``tool:action`` entry denies, naming what is still allowed."""
    denied = denied_actions(name, deny)
    if not denied:
        return None
    action = _action(arguments)
    enum = None
    if schema is not None:
        prop = _action_property(schema)
        enum = prop.get("enum") if prop is not None else None
    # Tools normalise their action after this gate, so anything not spelled exactly as an allowed value is refused too.
    allowed = [a for a in (enum or []) if a not in denied] if "*" not in denied else []
    if "*" not in denied and action not in denied and (not isinstance(enum, list) or action in allowed):
        return None
    shown = f"{name}:{action}" if action else name
    tail = f"; allowed: {', '.join(allowed)}" if allowed else ""
    return f"tool action denied for this profile: {shown} (tools.deny in config.yaml){tail}"


def allowed_actions(name: str) -> frozenset[str] | None:
    policy = _allowed.get()
    if name in _withheld.get():
        return frozenset()
    if policy is None:
        return None
    actions: set[str] = set()
    for entry in policy:
        tool, _, action = entry.partition(":")
        if _matches(name, tool):
            if not action:
                return None
            actions.add(action)
    return frozenset(actions)


def _action(arguments: object) -> str:
    action = arguments.get("action") if isinstance(arguments, dict) else None
    return action if isinstance(action, str) else ""


def _action_property(schema: dict) -> dict | None:
    parameters = (schema.get("function") or {}).get("parameters")
    properties = parameters.get("properties") if isinstance(parameters, dict) else None
    prop = properties.get("action") if isinstance(properties, dict) else None
    return prop if isinstance(prop, dict) else None


def _restriction(schema: dict) -> frozenset[str] | None:
    # Shared by schema and execution. None: the whole tool is allowed; an empty set: nothing of it is.
    actions = allowed_actions(str((schema.get("function") or {}).get("name") or ""))
    if actions is None:
        return None
    prop = _action_property(schema)
    if prop is None:
        return frozenset()
    enum = prop.get("enum")
    return frozenset(a for a in actions if a in enum) if isinstance(enum, list) else actions


def permits(schema: dict, arguments: object = None) -> bool:
    actions = _restriction(schema)
    return actions is None or _action(arguments) in actions


def _trim_actions(schema: dict, actions: frozenset[str]) -> dict:
    trimmed = copy.deepcopy(schema)
    parameters = trimmed["function"]["parameters"]
    prop = parameters["properties"]["action"]
    enum = prop.get("enum")
    prop["enum"] = [v for v in enum if v in actions] if isinstance(enum, list) else sorted(actions)
    required = parameters.get("required")
    required = list(required) if isinstance(required, list) else []
    parameters["required"] = required if "action" in required else [*required, "action"]
    return trimmed


def allowed_schema(schema: dict) -> dict | None:
    actions = _restriction(schema)
    if actions is None:
        return schema
    if not actions:
        return None
    return _trim_actions(schema, actions)


def refusal(name: str, arguments: object = None) -> str:
    if name in _withheld.get():
        unless = " unless that peer's tools.allow in peers.yaml names it" if _allowed.get() is None else ", whatever a tool list names"
        return (
            f"{name} is not available to {_label.get() or 'this turn'}: session and workgroup history "
            f"stay out of turns another agent starts{unless}"
        )
    action = _action(arguments)
    shown = f"{name}:{action}" if action and allowed_actions(name) else name
    return f"tool not allowed by the tool policy for {_label.get() or 'this turn'}: {shown} (tools.allow in peers.yaml)"
