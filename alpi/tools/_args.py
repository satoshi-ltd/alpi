from __future__ import annotations

import json
import math
import re
import sys
from typing import Any

_DECODABLE = {"object": dict, "array": list}
MAX_DEPTH = 100
OUT_OF_RANGE = "a number is out of range (NaN, Infinity or beyond ±1.8e308)"
_LONE_SURROGATE = re.compile("[\ud800-\udfff]")


def _kind(value: Any) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    return {list: "array", str: "string"}.get(type(value), type(value).__name__)


class DuplicateKey(ValueError):
    pass


def _unique(pairs: list[tuple[str, Any]]) -> dict:
    out: dict = {}
    for key, value in pairs:
        if key in out and out[key] != value:
            raise DuplicateKey(key)
        out[key] = value
    return out


def _distinct(pairs: list[tuple[str, Any]]) -> dict:
    out = dict(pairs)
    if len(out) != len(pairs):
        raise DuplicateKey("")
    return out


def _loads(raw: str) -> Any:
    try:
        return json.loads(raw, object_pairs_hook=_unique)
    except json.JSONDecodeError:
        return json.loads(raw, strict=False, object_pairs_hook=_unique)


def _unsafe(value: Any, depth: int = 1) -> str | None:
    stack = [(value, depth)]
    while stack:
        item, depth = stack.pop()
        if isinstance(item, str):
            if _LONE_SURROGATE.search(item):
                return "a string holds an unpaired surrogate"
            continue
        if isinstance(item, float) and not math.isfinite(item):
            return OUT_OF_RANGE
        if isinstance(item, int) and abs(item) > sys.float_info.max:
            return OUT_OF_RANGE
        if not isinstance(item, (dict, list)):
            continue
        if depth > MAX_DEPTH:
            return f"nested deeper than {MAX_DEPTH} levels"
        if isinstance(item, dict):
            stack.extend((key, depth) for key in item)
            stack.extend((child, depth + 1) for child in item.values())
        else:
            stack.extend((child, depth + 1) for child in item)
    return None


def decode(raw: Any) -> tuple[dict | None, str | None]:
    if isinstance(raw, dict):
        unsafe = _unsafe(raw)
        return (raw, None) if unsafe is None else (None, f"not valid JSON: {unsafe}")
    if raw is None or isinstance(raw, str) and not raw.strip():
        return {}, None
    if not isinstance(raw, str):
        return None, f"not a JSON object (got {_kind(raw)})"
    try:
        value = _loads(raw)
    except json.JSONDecodeError as e:
        return None, f"not valid JSON: {e.msg} (char {e.pos} of {len(raw)})"
    except DuplicateKey as e:
        return None, f"not valid JSON: key {json.dumps(str(e))} appears twice"
    except (RecursionError, ValueError):
        return None, f"not valid JSON: too deeply nested or too large ({len(raw)} chars)"
    if isinstance(value, str):
        try:
            inner = _loads(value)
        except DuplicateKey as e:
            return None, f"not valid JSON: key {json.dumps(str(e))} appears twice"
        except (RecursionError, ValueError):
            inner = None
        if isinstance(inner, dict):
            value = inner
    if value is None:
        return {}, None
    if not isinstance(value, dict):
        return None, f"not a JSON object (got {_kind(value)})"
    unsafe = _unsafe(value)
    if unsafe is not None:
        return None, f"not valid JSON: {unsafe}"
    return value, None


def prepare(name: str, raw: Any) -> tuple[dict | None, str | None]:
    args, error = decode(raw)
    if args is None:
        return None, error
    from alpi import tools

    cls = tools.get(name)
    parameters = cls.parameters if cls is not None else None
    if not args and not isinstance(raw, dict) and (raw is None or raw.strip() in ("", "null")):
        required = parameters.get("required") if isinstance(parameters, dict) else None
        if isinstance(required, list) and required:
            return None, f"missing (required: {', '.join(map(str, required))})"
    return coerce(args, parameters), None


def wire(raw: Any, args: dict | None) -> str:
    if args is None or _unsafe(args) is not None:
        return "{}"
    if isinstance(raw, str):
        try:
            if json.loads(raw, object_pairs_hook=_distinct) == args:
                return raw
        except (RecursionError, ValueError):
            pass
    try:
        return json.dumps(args, allow_nan=False)
    except (RecursionError, ValueError):
        return "{}"


def refusal(name: str, detail: str, cut: bool = False) -> str:
    message = (
        f"arguments for {name} are {detail}; the call did not run. "
        "Resend it with the complete arguments as one JSON object."
    )
    if cut:
        message += (
            " Your reply hit the output-token limit and cut this call off, "
            "so the same payload will be cut again."
        )
    return message


def _declared(schema: Any) -> set[str] | None:
    if not isinstance(schema, dict):
        return None
    kind = schema.get("type")
    if isinstance(kind, str):
        return {kind}
    if isinstance(kind, list) and all(isinstance(k, str) for k in kind):
        return set(kind)
    branches = schema.get("anyOf") or schema.get("oneOf")
    if kind is None and isinstance(branches, list) and branches:
        found: set[str] = set()
        for branch in branches:
            types = _declared(branch)
            if types is None:
                return None
            found |= types
        return found
    return None


def coerce(arguments: dict, parameters: Any) -> dict:
    properties = parameters.get("properties") if isinstance(parameters, dict) else None
    if not isinstance(properties, dict):
        return arguments
    out = arguments
    for key, value in arguments.items():
        if not isinstance(value, str):
            continue
        try:
            types = _declared(properties.get(key))
        except RecursionError:
            continue
        if not types or "string" in types:
            continue
        wanted = tuple(_DECODABLE[t] for t in types if t in _DECODABLE)
        if not wanted:
            continue
        try:
            decoded = _loads(value)
        except (RecursionError, ValueError):
            continue
        if isinstance(decoded, wanted) and _unsafe(decoded, 2) is None:
            if out is arguments:
                out = dict(arguments)
            out[key] = decoded
    return out
