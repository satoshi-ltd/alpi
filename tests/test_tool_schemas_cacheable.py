"""Tool definitions must be byte-stable across LLM calls.

Anthropic's prompt cache key spans system + tool defs up to and including
the marker, so a single tool with ``datetime.now()`` in its description
flips ``tools_hash`` every turn and the second call serves zero cache
reads. Caught once already in v0.6.15 (``Schedule.schema`` was injecting
``Current time: ...``); this test pins the invariant so it can't regress.
"""

from __future__ import annotations

import json
import time

import pytest

from alpi import tools as tools_mod


def _schemas_hash() -> str:
    import hashlib
    schemas = tools_mod.schemas()
    return hashlib.sha256(
        json.dumps(schemas, sort_keys=True).encode("utf-8"),
    ).hexdigest()


def test_schemas_are_byte_stable_across_calls() -> None:
    """Two consecutive ``schemas()`` calls — even with a small sleep — must produce identical JSON. Any tool that embeds wall-clock state breaks Anthropic prompt caching."""
    h1 = _schemas_hash()
    time.sleep(0.01)
    h2 = _schemas_hash()
    assert h1 == h2


def test_schedule_schema_contains_no_timestamp() -> None:
    """Regression — ``Schedule.schema()`` used to prefix the description with ``datetime.now()`` to ground relative phrases; the # NOW system block covers that and the timestamp poisoned the tool-defs cache key."""
    from alpi.tools.schedule import Schedule
    desc = Schedule.schema()["function"]["description"]
    assert "Current time:" not in desc
    assert "Now:" not in desc


def test_wire_order_is_sorted_and_stable_across_mcp_map_order() -> None:
    """The outer list IS the provider cache prefix — sort_keys in the hash above cannot see reordering, so pin the wire order itself."""
    from alpi.tools.base import Tool

    class _ZTool(Tool):
        name = "zzz_fake"
        description = "fake"
        parameters = {"type": "object", "properties": {}}

        def run(self, **kw):  # noqa: ANN003
            raise NotImplementedError

    class _ATool(Tool):
        name = "aaa_fake"
        description = "fake"
        parameters = {"type": "object", "properties": {}}

        def run(self, **kw):  # noqa: ANN003
            raise NotImplementedError

    def _names(mapping):
        with tools_mod.use_mcp_tools(mapping):
            return [s["function"]["name"] for s in tools_mod.schemas()]

    forward = _names({"zzz_fake": _ZTool, "aaa_fake": _ATool})
    backward = _names({"aaa_fake": _ATool, "zzz_fake": _ZTool})
    assert forward == backward, "MCP insertion order must never reach the wire"
    assert forward == sorted(forward)
    assert "aaa_fake" in forward and "zzz_fake" in forward
