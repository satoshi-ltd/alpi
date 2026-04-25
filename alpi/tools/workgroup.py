"""workgroup_post — post a message to an ALP workgroup.

Minimal hook so the agent can drop a message into a multi-party
shared transcript. The tool only handles the *post* leg —
auto-pulling new posts as turn context, surfacing notifications, or
routing @mentions inside workgroups are deferred (ALP.6 / ALP.7
in v0.5).

The workgroup must already be subscribed to (``alpi workgroup join``
or wizard) — otherwise we have no group key. Encryption + the
optional cost declaration happen client-side via
``alpi.alp.workgroup_client``.
"""

from __future__ import annotations

import asyncio
from typing import Any

from alpi.alp import client as alp_client
from alpi.alp import workgroup_client as wc
from alpi.home import get_home
from alpi.tools.base import Tool, ToolResult


class WorkgroupPostTool(Tool):
    name = "workgroup_post"
    description = (
        "Post a message into a shared ALP workgroup transcript. Use this "
        "when (a) the user asks you to broadcast something to a workgroup, "
        "or (b) the workgroup-poller woke this turn because you were "
        "@-mentioned or a collective `#task` opened — see the "
        "`Workgroup engagement rules` block in your system prompt for the "
        "full posture. Default posture is OBSERVER; only post when you "
        "have substantive content. The `wg_id` is the `wg_*` string in "
        "your workgroup context block. Cost is auto-declared from this "
        "turn's accumulated USD/tokens; the hub gates against the "
        "workgroup's lifetime budget. Returns the assigned sequence number."
    )
    parameters = {
        "type": "object",
        "properties": {
            "wg_id": {
                "type": "string",
                "description": "Workgroup id (e.g. wg_jqa3pux6gz3tbo5a).",
            },
            "text": {
                "type": "string",
                "description": "Message body (plaintext; encrypted client-side).",
            },
        },
        "required": ["wg_id", "text"],
    }

    def run(self, **kwargs: Any) -> ToolResult:
        wg_id = kwargs.get("wg_id")
        text = kwargs.get("text")
        if not wg_id or not text:
            return ToolResult(ok=False, output="", error="wg_id and text required")

        # Auto-declare cost from the current turn's accumulated spend.
        # Workgroup hubs gate against this declaration; reporting truthfully
        # keeps the workgroup ledger meaningful and the lifetime cap real.
        from alpi.tools import _state as _wg_state
        tally = _wg_state.get_turn_usage()
        cost = None
        if tally:
            cost = {
                "usd": float(tally.get("usd", 0.0)),
                "tokens": int(tally.get("tokens_in", 0)) + int(tally.get("tokens_out", 0)),
            }

        try:
            result = asyncio.run(
                wc.post(get_home(), wg_id, text.encode("utf-8"), cost=cost),
            )
        except alp_client.RemoteError as e:
            return ToolResult(
                ok=False, output="",
                error=f"hub rejected: {e.code} {e.message}",
            )
        except (ValueError, alp_client.ClientError) as e:
            return ToolResult(ok=False, output="", error=str(e))
        cost_hint = ""
        if cost:
            cost_hint = (
                f" · declared ${cost['usd']:.4f} / {cost['tokens']} tokens"
            )
        return ToolResult(
            ok=True,
            output=f"posted seq {result.get('seq')} at {result.get('ts')}{cost_hint}",
        )


TOOL = WorkgroupPostTool
