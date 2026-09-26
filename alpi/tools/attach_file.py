from __future__ import annotations

import json

from alpi.attachments import _PRODUCED_EXT_MIME, IMAGE_MIMES, servable_roots
from alpi.tools._paths import _configured_workspace, resolve_path
from alpi.tools.base import Tool, ToolResult


class AttachFile(Tool):
    name = "attach_file"
    description = (
        "Attach a file you produced to your reply so the user can open and "
        "download it in the chat. Use this ONLY for a deliverable the user "
        "should keep or download — a document, report, or export — NOT for "
        "normal project files you create or edit (those stay in the workspace "
        "via `write_file` / `edit_file`). A file you write but do not attach "
        "isn't downloadable: mobile, desktop, and remote members can't browse "
        "the workspace. "
        "Write the file first with `write_file`, then call `attach_file(path)`. "
        "A new document for the user goes in the profile's `out/` folder "
        "(generated files, kept about 30 days) or the workspace: the app "
        "downloads documents only from there, never from /tmp or other "
        "folders, and a refused path names the `out/` folder to use. "
        "Supported: .md, .txt, .csv, .json, .html, "
        ".pdf, images, and Office docs. The file rides on your final reply as "
        "a downloadable chip — when you attach a document, do NOT also paste "
        "its full contents into the message; a one-line note is enough."
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file to attach (relative paths root at the workspace).",
            },
        },
        "required": ["path"],
    }

    def run(self, path: str) -> ToolResult:
        try:
            p = resolve_path(path)
        except ValueError as e:
            return ToolResult(ok=False, output="", error=str(e))
        if not p.is_file():
            return ToolResult(ok=False, output="", error=f"no such file: {p}")
        if p.suffix.lower() not in _PRODUCED_EXT_MIME:
            return ToolResult(
                ok=False, output="",
                error=(
                    f"unsupported file type {p.suffix or '(none)'!r} — supported: "
                    + ", ".join(sorted(_PRODUCED_EXT_MIME))
                ),
            )
        if _PRODUCED_EXT_MIME[p.suffix.lower()] not in IMAGE_MIMES:
            from alpi.home import get_home
            home = get_home()
            try:
                workspace = _configured_workspace()
            except ValueError:
                workspace = None
            real = p.resolve()
            if not any(
                real == r.resolve() or real.is_relative_to(r.resolve())
                for r in servable_roots(home, workspace, image=False)
            ):
                served = f"{home / 'out'}/" + (f" and the workspace ({workspace})" if workspace else "")
                return ToolResult(
                    ok=False, output="",
                    error=(
                        f"{p} cannot be downloaded from the chat: the app serves documents "
                        f"only from {served}. Write it under {home / 'out'}/ and attach that path."
                    ),
                )
        return ToolResult(ok=True, output=json.dumps({"out": str(p)}))


TOOL = AttachFile
