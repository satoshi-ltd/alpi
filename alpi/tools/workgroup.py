"""Post a message to an ALP workgroup."""

from __future__ import annotations

import asyncio
import os
from typing import Any

from alpi.alp import client as alp_client
from alpi.alp import workgroup_client as wc
from alpi.home import get_home
from alpi.tools.base import Tool, ToolResult


def _declared_cost(tally: dict | None) -> dict | None:
    if not tally:
        return None
    cost = {
        "usd": float(tally.get("usd", 0.0)),
        "tokens": int(tally.get("tokens_in", 0)) + int(tally.get("tokens_out", 0)),
        "tokens_in": int(tally.get("tokens_in", 0)),
        "tokens_out": int(tally.get("tokens_out", 0)),
    }
    # Absent = unmeasured; 0 = measured miss. Never write an unmeasured zero.
    if int(tally.get("measured_in", 0)) > 0:
        cost["cached_in"] = int(tally.get("cached_in", 0))
        cost["measured_in"] = int(tally.get("measured_in", 0))
    return cost


def _append_dispatch_recheck(text: str) -> str:
    phase = os.environ.get("ALPI_WORKGROUP_RECHECK_PHASE", "").strip()
    suffix = os.environ.get("ALPI_WORKGROUP_RECHECK_SUFFIX", "")
    if not phase or not suffix:
        return text
    from alpi.alp import tasks as tasks_mod

    lines = text.splitlines(keepends=True)
    for index, line in enumerate(lines):
        events = tasks_mod.parse_post(line, 0, "", hub_pubkey="")
        opened = next(
            (event.slug for event in events if event.kind == "task" and event.slug),
            "",
        )
        if opened != phase and not opened.startswith(f"{phase}-"):
            continue
        if suffix not in line:
            ending = "\r\n" if line.endswith("\r\n") else "\n" if line.endswith("\n") else ""
            body = line[:-len(ending)] if ending else line
            lines[index] = body.rstrip() + suffix + ending
        return "".join(lines)
    return text




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
                "description": "Workgroup id (e.g. wg_jqa3pux6gz3tbo5a); inside a dispatched workgroup turn it defaults to that workgroup.",
            },
            "text": {
                "type": "string",
                "description": "Message body (plaintext; encrypted client-side).",
            },
        },
        "required": ["text"],
    }

    def run(self, **kwargs: Any) -> ToolResult:  # noqa: C901
        wg_id = kwargs.get("wg_id")
        text = kwargs.get("text")
        dispatch_wg = os.environ.get("ALPI_WORKGROUP_DISPATCH") or ""
        corrected = ""
        if dispatch_wg and wg_id != dispatch_wg:
            if wg_id:
                corrected = f" · wg_id {wg_id!r} replaced by this turn's workgroup {dispatch_wg!r}"
            wg_id = dispatch_wg
        if not wg_id or not text:
            return ToolResult(ok=False, output="", error="wg_id and text required")
        from alpi.alp import tasks as tasks_mod
        from alpi.tools import _state as _wg_state
        text = _append_dispatch_recheck(text)
        member_turn = os.environ.get("ALPI_WORKGROUP_MEMBER_TURN") == "1"
        continuation = tasks_mod.is_continuation_working(text)
        if member_turn and tasks_mod.is_working_only(text) and not continuation:
            return ToolResult(
                ok=False, output="",
                error="the daemon tracks this turn's progress; post only your handoff when the deliverable is ready",
            )
        if member_turn and not continuation and _wg_state.get_turn_tools_run() == 0:
            return ToolResult(
                ok=False, output="",
                error="nothing ran this turn: read the briefing, produce and verify the deliverable with your tools, then post the handoff as the last call",
            )
        phase = _wg_state.pipeline_phase() if member_turn else ""
        if phase and not continuation and not tasks_mod.is_skip_only(text) and not tasks_mod.names_phase(text, phase):
            return ToolResult(
                ok=False, output="",
                error=f"a pipeline handoff names its phase: post `#{phase} done — <what changed and where>` once the deliverable is complete, or `#skip <reason>` alone; progress notes are not posted, keep working",
            )
        if member_turn and not continuation and not tasks_mod.is_skip_only(text):
            scope_changed = _wg_state.write_scope_changed()
            scope_error = _wg_state.write_scope_error()
            if scope_error:
                return ToolResult(
                    ok=False, output="",
                    error=f"the phase write scope cannot be verified ({scope_error}); the handoff is refused until the daemon runs this turn with a configured workspace",
                )
            if scope_changed is False:
                return ToolResult(
                    ok=False, output="",
                    error="this phase owns artifacts and none changed since the round opened: write the deliverable first, or post `#skip <reason>` alone when there is nothing to produce",
                )

        pending, snapshot = _wg_state.get_undeclared_turn_usage()
        cost = _declared_cost(pending)
        turn_id = _wg_state.get_turn_id()

        try:
            result = asyncio.run(
                wc.post(
                    get_home(), wg_id, text.encode("utf-8"),
                    cost=cost, turn_id=turn_id,
                ),
            )
        except alp_client.RemoteError as e:
            err = f"hub rejected: {e.code} {e.message}"
            _record_post_failure(wg_id, err, text)
            return ToolResult(
                ok=False,
                output="",
                error=err,
                transient=alp_client.is_transient_link_error(e),
            )
        except (ValueError, alp_client.ClientError, OSError, asyncio.TimeoutError) as e:
            err = str(e)
            _record_post_failure(wg_id, err, text)
            return ToolResult(
                ok=False,
                output="",
                error=err,
                transient=alp_client.is_transient_link_error(e),
            )
        _wg_state.mark_turn_usage_declared(snapshot)
        if member_turn and not continuation:
            _wg_state.clear_write_scope_baseline()
        cost_hint = ""
        if cost:
            cost_hint = (
                f" · declared ${cost['usd']:.4f} / {cost['tokens']} tokens"
            )
        return ToolResult(
            ok=True,
            output=f"posted seq {result.get('seq')} at {result.get('ts')}{cost_hint}{corrected}",
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
