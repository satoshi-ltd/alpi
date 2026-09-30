from __future__ import annotations

import json
import time
from datetime import datetime
from typing import Any

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import OptionList, Static

from alpi.tui import host_client
from alpi.tui.screens import _LIST_PANEL_CSS, ApprovalPanel, ClarificationPanel, FloatingPanel, fmt_remaining

NOT_RUNNING = "daemon not running — start it with `alpi daemon start` to see background work"
TOO_OLD = "the running daemon predates activity — update alpi and restart the daemon"


def _ago(value: Any) -> str:
    ts = _epoch(value)
    if ts is None:
        return ""
    delta = max(0, int(time.time() - ts))
    if delta < 60:
        return f"{delta}s"
    if delta < 3600:
        return f"{delta // 60}m"
    return f"{delta // 3600}h"


def _epoch(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return None
    return None


def _when(value: Any) -> str:
    ts = _epoch(value)
    if ts is None:
        return "—"
    return datetime.fromtimestamp(ts).strftime("%a %H:%M")


def needs_row(item: dict) -> tuple[str, str]:
    kind = "approval" if item.get("kind") == "approval" else "question"
    title = " ".join(str(item.get("title") or "").split()) or "(untitled)"
    meta = [kind, str(item.get("profile") or "")]
    if item.get("severity"):
        meta.append(str(item["severity"]))
    remaining = expires_in(item)
    if remaining is not None:
        meta.append(f"expires in {fmt_remaining(remaining)}")
    return title, " · ".join(m for m in meta if m)


def expires_in(item: dict) -> float | None:
    ts = _epoch(item.get("ts"))
    timeout = item.get("timeout_s")
    if ts is None or not isinstance(timeout, (int, float)):
        return None
    return max(0.0, ts + float(timeout) - time.time())


def running_line(item: dict) -> str:
    profile = str(item.get("profile") or "")
    if item.get("kind") == "workgroup":
        done, total = item.get("phases_done"), item.get("phases_total")
        progress = f" ({done}/{total})" if isinstance(done, int) and isinstance(total, int) and total else ""
        phase = f" · {item['phase']}" if item.get("phase") else ""
        return f"{profile} · workgroup {item.get('name') or item.get('workgroup_id') or ''}{phase}{progress}"
    title = item.get("title") or item.get("session_id") or "turn"
    source = item.get("source") or "chat"
    ago = _ago(item.get("started_at"))
    return f"{profile} · {title} · {source}" + (f" · {ago}" if ago else "")


def scheduled_line(item: dict) -> str:
    line = f"{item.get('profile') or ''} · {item.get('title') or item.get('job_id') or 'job'} · next {_when(item.get('next_fire'))}"
    if item.get("last_run_status") == "error":
        line += " · last run failed"
    return line


class ActivityPanel(FloatingPanel):
    panel_title = "/activity"
    DEFAULT_CSS = _LIST_PANEL_CSS

    def __init__(self) -> None:
        super().__init__()
        self.data: dict | None = None
        self.message = ""
        self._needs: dict[str, dict] = {}

    def compose_body(self) -> ComposeResult:
        yield Static("loading…", id="activity-status", classes="entry-desc")
        yield VerticalScroll(id="activity-body")

    def on_mount(self) -> None:
        self.run_worker(self.load(), exclusive=True, group="activity")

    async def load(self) -> None:
        try:
            data = await host_client.acall("host.activity.list", timeout=3.0)
        except host_client.HostUnavailable:
            self._show_message(NOT_RUNNING)
            return
        except host_client.HostError as e:
            self._show_message(TOO_OLD if e.missing_verb else e.message)
            return
        if not isinstance(data, dict):
            self._show_message(host_client.INVALID_RESPONSE)
            return
        await self.render_data(data)

    def _show_message(self, text: str) -> None:
        self.message = text
        try:
            self.query_one("#activity-status", Static).update(text)
        except Exception:  # noqa: BLE001
            pass

    async def render_data(self, data: dict) -> None:
        from alpi.tui.list_row import build_options

        self.data = data
        needs = [n for n in data.get("needs_you") or [] if isinstance(n, dict)]
        running = [r for r in data.get("running") or [] if isinstance(r, dict)]
        scheduled = [s for s in data.get("scheduled") or [] if isinstance(s, dict)]
        self._show_message(
            f"{len(needs)} need you · {len(running)} running · {len(scheduled)} scheduled"
        )
        body = self.query_one("#activity-body", VerticalScroll)
        await body.remove_children()
        widgets: list = [Static("needs you", classes="help-section")]
        if needs:
            self._needs = {}
            items = []
            for i, item in enumerate(needs):
                key = f"need-{i}"
                self._needs[key] = item
                title, meta = needs_row(item)
                items.append((key, title, meta))
            widgets.append(OptionList(*build_options(items, accent=self.app.theme_variables.get("accent")),
                                      id="activity-needs", compact=True))
        else:
            widgets.append(Static("nothing waits on you", classes="entry-desc"))
        widgets.append(Static("running", classes="help-section"))
        widgets.extend(Static(running_line(r), classes="list-row") for r in running)
        if not running:
            widgets.append(Static("nothing running", classes="entry-desc"))
        widgets.append(Static("scheduled", classes="help-section"))
        widgets.extend(Static(scheduled_line(s), classes="list-row") for s in scheduled)
        if not scheduled:
            widgets.append(Static("nothing scheduled", classes="entry-desc"))
        await body.mount(*widgets)
        if needs:
            self.query_one("#activity-needs", OptionList).focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        event.stop()
        item = self._needs.get(event.option.id or "")
        if item is None:
            return
        opener = getattr(self.app, "_review_remote", None)
        if opener is not None:
            opener(item)


async def open_review(app, item: dict) -> FloatingPanel | str:
    profile = str(item.get("profile") or "")
    request_id = str(item.get("request_id") or "")
    remaining = expires_in(item)

    def responder(method: str, encode=lambda c: c):
        def on_choice(choice: str) -> None:
            if not choice:
                return
            params = {"request_id": request_id, "choice": encode(choice)}
            if profile:
                params["profile"] = profile
            app.run_worker(_respond(app, method, params), group="activity-respond")
        return on_choice

    if item.get("kind") == "approval":
        return ApprovalPanel(
            str(item.get("title") or ""), "", str(item.get("severity") or ""),
            responder("host.approval.respond"), profile=profile,
            timeout_s=remaining, blocking=False,
        )
    try:
        pending = await host_client.acall("host.clarification.pending", {"profile": profile} if profile else {}, timeout=3.0)
    except host_client.HostUnavailable:
        return NOT_RUNNING
    except host_client.HostError as e:
        return f"could not load the question: {e.message}"
    rows = (pending or {}).get("requests") or []
    meta = next((r for r in rows if isinstance(r, dict) and r.get("request_id") == request_id), None)
    if meta is None:
        return "that question was already answered"
    return ClarificationPanel(
        str(meta.get("question") or item.get("title") or ""),
        [c for c in meta.get("choices") or [] if isinstance(c, dict) and c.get("label")],
        bool(meta.get("allow_other")), bool(meta.get("multi")),
        responder("host.clarification.respond"),
        timeout_s=remaining, blocking=False, profile=profile,
        encode_multi=lambda picks: json.dumps(picks),
    )


async def _respond(app, method: str, params: dict) -> None:
    try:
        result = await host_client.acall(method, params, timeout=5.0)
    except host_client.HostUnavailable:
        app._activity_note(NOT_RUNNING)
        return
    except host_client.HostError as e:
        app._activity_note(f"answer failed: {e.message}")
        return
    if isinstance(result, dict) and result.get("ok") is False:
        app._activity_note(f"not delivered: {result.get('reason') or 'already resolved'}")
        return
    app._activity_note("answer sent")
