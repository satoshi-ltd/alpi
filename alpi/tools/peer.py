"""peer — send a prompt to another alpi profile over ALP.

Tool-level glue for the ``link.ask`` verb. The caller supplies a
pinned ``peer_id`` (from ``peers.yaml``) and a prompt; we route
through ``alpi.alp.mention.execute`` so this tool, the TUI's
``@peer`` gesture, and the gateway mention interception all share
one implementation.

Inter-machine (TCP/Noise) lands in ALP.2 — for now, intra-machine
Unix sockets only. Peers with ``address:`` set are rejected.
"""

from __future__ import annotations

import asyncio
from typing import Any

from alpi.alp import mention as alp_mention
from alpi.home import get_home
from alpi.tools.base import Tool, ToolResult


class PeerTool(Tool):
    name = "peer"
    description = (
        "Ask another alpi profile on this machine a question and return "
        "its reply. Use for cross-profile handoffs (e.g. work profile "
        "asking personal profile for its timezone). The peer must be "
        "pinned in peers.yaml and have link.ask in its allow list. "
        "Returns the remote reply text plus token/cost usage."
    )
    parameters = {
        "type": "object",
        "properties": {
            "peer_id": {
                "type": "string",
                "description": "Pinned peer id from peers.yaml (e.g. 'personal').",
            },
            "prompt": {
                "type": "string",
                "description": "The prompt to send. Single-shot — no session resume.",
            },
        },
        "required": ["peer_id", "prompt"],
    }

    def run(self, **kwargs: Any) -> ToolResult:
        peer_id = kwargs.get("peer_id")
        prompt = kwargs.get("prompt")
        if not peer_id or not prompt:
            return ToolResult(ok=False, output="", error="peer_id and prompt required")

        result = asyncio.run(alp_mention.execute(get_home(), peer_id, prompt))
        if not result.ok:
            return ToolResult(ok=False, output="", error=result.error)

        usage = (
            f"\n\n---\ntokens: in={result.tokens_in} out={result.tokens_out} · "
            f"cost=${result.cost:.4f}"
        )
        return ToolResult(ok=True, output=result.reply + usage)


TOOL = PeerTool
