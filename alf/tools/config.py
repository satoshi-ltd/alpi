"""config tool — read/write editable keys in config.yaml."""

from __future__ import annotations

import yaml
from pathlib import Path
from typing import Any

from alf import config as cfg_mod
from alf.home import get_home
from alf.tools.base import Tool, ToolResult

_NEXT_SESSION = "next alf session"
_NEXT_GATEWAY = "next `alf gateway restart`"
_NEXT_TURN = "next turn"

_EDITABLE: dict[str, dict] = {
    "model":                           {"type": "str",      "effect": _NEXT_SESSION},
    "workspace":                       {"type": "str",      "effect": _NEXT_SESSION},
    "fallback_models":                 {"type": "list[str]","effect": _NEXT_TURN},
    "tools.max_steps_per_turn":        {"type": "int",      "effect": _NEXT_TURN},
    "tools.web_extract.model":         {"type": "str",      "effect": _NEXT_TURN},
    "tui.show_cost":                   {"type": "bool",     "effect": _NEXT_SESSION},
    "tui.show_tokens":                 {"type": "bool",     "effect": _NEXT_SESSION},
    "tui.accent":                      {"type": "str",      "effect": _NEXT_SESSION},
    "gateway.telegram.show_tool_trace":{"type": "bool",     "effect": _NEXT_GATEWAY},
    "gateway.telegram.typing_indicator":{"type": "bool",    "effect": _NEXT_GATEWAY},
    "gateway.email.poll_interval":     {"type": "int",      "effect": _NEXT_GATEWAY},
    "gateway.email.mark_as_read":      {"type": "bool",     "effect": _NEXT_GATEWAY},
    "gateway.email.show_tool_trace":   {"type": "bool",     "effect": _NEXT_GATEWAY},
    "gateway.email.typing_indicator":  {"type": "bool",     "effect": _NEXT_GATEWAY},
}


class Config(Tool):
    name = "config"
    description = (
        "Read or change alf's settings in ~/.alf/config.yaml.\n"
        "\n"
        "  action=get    return the current value at `key`\n"
        "  action=set    write `value` at `key`\n"
        "  action=reset  drop `key` so the default applies\n"
        "  action=list   show every editable key + current value\n"
        "\n"
        "`providers.custom` and `mcp.servers` are NOT editable here — "
        "they have multi-field wizards in `alf setup`. Every set/reset "
        "returns a note about when the change takes effect; relay that "
        "to the user verbatim."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["get", "set", "reset", "list"]},
            "key": {"type": "string", "description": "Dot-path key (see list action)."},
            "value": {"type": "string", "description": "New value for set — booleans accept true/false/yes/no/1/0."},
        },
        "required": ["action"],
    }

    def run(self, action: str, key: str = "", value: str = "") -> ToolResult:
        home = get_home()

        if action == "list":
            return _list(home)

        if not key:
            return ToolResult(ok=False, output="", error="'key' is required")
        if key not in _EDITABLE:
            known = ", ".join(sorted(_EDITABLE))
            return ToolResult(ok=False, output="",
                              error=f"key {key!r} is not editable. Known keys: {known}")

        if action == "get":
            return _get(home, key)
        if action == "set":
            if not value:
                return ToolResult(ok=False, output="", error="'value' is required for set")
            return _set(home, key, value)
        if action == "reset":
            return _reset(home, key)
        return ToolResult(ok=False, output="", error=f"unknown action: {action}")


def _list(home: Path) -> ToolResult:
    cfg = cfg_mod.load(home)
    lines = []
    for key, meta in _EDITABLE.items():
        val = _read_value(cfg, key)
        lines.append(f"{key} = {val!r}  ({meta['type']})")
    return ToolResult(ok=True, output="\n".join(lines))


def _get(home: Path, key: str) -> ToolResult:
    cfg = cfg_mod.load(home)
    val = _read_value(cfg, key)
    return ToolResult(ok=True, output=f"{key} = {val!r}")


def _set(home: Path, key: str, raw_value: str) -> ToolResult:
    meta = _EDITABLE[key]
    try:
        coerced = _coerce(raw_value, meta["type"])
    except ValueError as e:
        return ToolResult(ok=False, output="", error=str(e))
    _mutate_file(home, key, coerced)
    return ToolResult(
        ok=True,
        output=f"Set {key} = {coerced!r}. Takes effect: {meta['effect']}.",
    )


def _reset(home: Path, key: str) -> ToolResult:
    meta = _EDITABLE[key]
    removed = _mutate_file(home, key, _SENTINEL_DELETE)
    if removed:
        return ToolResult(ok=True, output=f"Reset {key} to default. Takes effect: {meta['effect']}.")
    return ToolResult(ok=True, output=f"{key} was already default.")


_SENTINEL_DELETE = object()


def _mutate_file(home: Path, key: str, value: Any) -> bool:
    cfg_path = home / "config.yaml"
    data: dict[str, Any] = {}
    if cfg_path.exists():
        data = yaml.safe_load(cfg_path.read_text()) or {}

    parts = key.split(".")
    cur = data
    for p in parts[:-1]:
        if not isinstance(cur.get(p), dict):
            if value is _SENTINEL_DELETE:
                return False
            cur[p] = {}
        cur = cur[p]

    leaf = parts[-1]
    changed = False
    if value is _SENTINEL_DELETE:
        if isinstance(cur, dict) and leaf in cur:
            del cur[leaf]
            changed = True
    else:
        cur[leaf] = value
        changed = True

    if changed:
        cfg_path.write_text(yaml.safe_dump(data, sort_keys=False))
    return changed


def _read_value(cfg, dotted: str) -> Any:
    parts = dotted.split(".")
    head = parts[0]

    if head == "tools":
        if len(parts) == 2 and parts[1] == "max_steps_per_turn":
            return cfg.tools.max_steps_per_turn
        if len(parts) == 3 and parts[1] == "web_extract" and parts[2] == "model":
            return cfg.tools.web_extract.model

    if hasattr(cfg, head):
        val = getattr(cfg, head)
    else:
        val = None

    for p in parts[1:]:
        if isinstance(val, dict):
            val = val.get(p)
        else:
            return None
    return val


def _coerce(raw: str, type_str: str) -> Any:
    s = str(raw).strip()
    if type_str == "str":
        return s
    if type_str == "int":
        try:
            return int(s)
        except ValueError as e:
            raise ValueError(f"expected int, got {raw!r}") from e
    if type_str == "bool":
        low = s.lower()
        if low in ("true", "yes", "1", "on"):
            return True
        if low in ("false", "no", "0", "off"):
            return False
        raise ValueError(f"expected bool, got {raw!r}")
    if type_str == "list[str]":
        return [x.strip() for x in s.split(",") if x.strip()]
    raise ValueError(f"unknown type: {type_str}")


TOOL = Config
