"""Post a message to an ALP workgroup."""

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
        "when the user asks for a workgroup broadcast or when the poller "
        "wakes this turn. Post only with substantive content. The `wg_id` "
        "is the `wg_*` string in your workgroup context. Cost is declared "
        "from this turn's accumulated USD/tokens. Returns the sequence number."
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

        # Auto-declare the current turn's spend for the hub ledger.
        from alpi.tools import _state as _wg_state
        tally = _wg_state.get_turn_usage()
        cost = None
        if tally:
            cost = {
                "usd": float(tally.get("usd", 0.0)),
                "tokens": int(tally.get("tokens_in", 0)) + int(tally.get("tokens_out", 0)),
                "tokens_in": int(tally.get("tokens_in", 0)),
                "tokens_out": int(tally.get("tokens_out", 0)),
            }

        try:
            result = asyncio.run(
                wc.post(get_home(), wg_id, text.encode("utf-8"), cost=cost),
            )
        except alp_client.RemoteError as e:
            err = f"hub rejected: {e.code} {e.message}"
            _record_post_failure(wg_id, err, text)
            return ToolResult(ok=False, output="", error=err)
        except (ValueError, alp_client.ClientError) as e:
            err = str(e)
            _record_post_failure(wg_id, err, text)
            return ToolResult(ok=False, output="", error=err)
        cost_hint = ""
        if cost:
            cost_hint = (
                f" · declared ${cost['usd']:.4f} / {cost['tokens']} tokens"
            )
        return ToolResult(
            ok=True,
            output=f"posted seq {result.get('seq')} at {result.get('ts')}{cost_hint}",
        )


def _record_post_failure(wg_id: str, error: str, attempted_text: str) -> None:
    """Record a rejected post in ``turns.jsonl``."""
    import os
    try:
        from alpi import service
        home = get_home()
        # Truncate the attempted body so the log stays bounded.
        preview = attempted_text[:240] + ("…" if len(attempted_text) > 240 else "")
        service._append_turn_event(home, {
            "ts": service._utcnow_iso(),
            "event": "post-rejected",
            "wg_id": wg_id,
            "error": error,
            "attempted_preview": preview,
            "pid": os.getpid(),
        })
    except Exception:  # noqa: BLE001
        pass


TOOL = WorkgroupPostTool
