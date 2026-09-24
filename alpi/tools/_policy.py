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


@contextmanager
def use(allowed: Iterable[str] | None, label: str) -> Iterator[None]:
    entries = None if allowed is None else frozenset(str(a).strip() for a in allowed if str(a).strip())
    allowed_token = _allowed.set(entries)
    label_token = _label.set(label)
    try:
        yield
    finally:
        _label.reset(label_token)
        _allowed.reset(allowed_token)


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


def allowed_actions(name: str) -> frozenset[str] | None:
    policy = _allowed.get()
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


def allowed_schema(schema: dict) -> dict | None:
    actions = _restriction(schema)
    if actions is None:
        return schema
    if not actions:
        return None
    trimmed = copy.deepcopy(schema)
    parameters = trimmed["function"]["parameters"]
    prop = parameters["properties"]["action"]
    enum = prop.get("enum")
    prop["enum"] = [v for v in enum if v in actions] if isinstance(enum, list) else sorted(actions)
    required = parameters.get("required")
    required = list(required) if isinstance(required, list) else []
    parameters["required"] = required if "action" in required else [*required, "action"]
    return trimmed


def refusal(name: str, arguments: object = None) -> str:
    action = _action(arguments)
    shown = f"{name}:{action}" if action and allowed_actions(name) else name
    return f"tool not allowed by the tool policy for {_label.get() or 'this turn'}: {shown} (tools.allow in peers.yaml)"
