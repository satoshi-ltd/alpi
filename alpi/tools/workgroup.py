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
        "Post a message into a shared ALP workgroup transcript. The "
        "workgroup id is the `wg_*` string the user shared with you "
        "(or the value of `wg_id` in `alpi workgroup list`). The "
        "profile must already be subscribed — joins happen via "
        "`alpi workgroup join` or the setup wizard, not via this tool. "
        "Use when the user explicitly asks you to broadcast something "
        "to a workgroup; do NOT post unprompted. Other members read "
        "the post when they pull. Returns the assigned sequence number."
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
        try:
            result = asyncio.run(
                wc.post(get_home(), wg_id, text.encode("utf-8")),
            )
        except alp_client.RemoteError as e:
            return ToolResult(
                ok=False, output="",
                error=f"hub rejected: {e.code} {e.message}",
            )
        except (ValueError, alp_client.ClientError) as e:
            return ToolResult(ok=False, output="", error=str(e))
        return ToolResult(
            ok=True,
            output=f"posted seq {result.get('seq')} at {result.get('ts')}",
        )


TOOL = WorkgroupPostTool
