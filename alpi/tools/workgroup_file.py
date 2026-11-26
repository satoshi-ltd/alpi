"""Send and receive encrypted workgroup files."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from alpi.alp import client as alp_client
from alpi.alp import workgroup_client as wc
from alpi.home import get_home
from alpi.tools import _state
from alpi.tools._paths import resolve_path, resolve_workspace_path
from alpi.tools.base import Tool, ToolResult


def _source_path(value: str) -> Path:
    try:
        return resolve_path(value)
    except ValueError:
        requested = Path(value).expanduser().resolve()
        if requested not in _state.turn_attachment_paths():
            raise
        return requested


def _available_destination(path: Path) -> Path:
    if not path.exists():
        return path
    for index in range(1, 10_000):
        candidate = path.with_name(f"{path.stem}-{index}{path.suffix}")
        if not candidate.exists():
            return candidate
    raise ValueError(f"cannot find an available destination for {path.name}")


class WorkgroupFileTool(Tool):
    name = "workgroup_file"
    description = (
        "List, send, or fetch encrypted files in an ALP workgroup. Transcript "
        "announcements start with `#file` and include the full sha256; fetch "
        "that sha only when the task needs the file, or use `list` to rediscover "
        "older files. Never paste file contents into a workgroup post. `send` "
        "accepts workspace files and files attached in the current turn. `get` "
        "writes without overwriting an existing file."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["list", "send", "get"]},
            "wg_id": {"type": "string"},
            "path": {"type": "string", "description": "Source path for send."},
            "sha256": {"type": "string", "description": "File digest for get."},
            "dest": {"type": "string", "description": "Optional destination for get."},
            "note": {"type": "string", "description": "Optional marker note for send."},
            "offset": {"type": "integer", "minimum": 0},
            "limit": {"type": "integer", "minimum": 1, "maximum": 200},
        },
        "required": ["action", "wg_id"],
    }

    def run(self, **kwargs: Any) -> ToolResult:
        action = str(kwargs.get("action") or "")
        wg_id = str(kwargs.get("wg_id") or "").strip()
        if not wg_id:
            return ToolResult(ok=False, output="", error="wg_id required")
        try:
            if action == "list":
                result = asyncio.run(
                    wc.list_files(
                        get_home(),
                        wg_id,
                        offset=kwargs.get("offset", 0),
                        limit=kwargs.get("limit", 50),
                    ),
                )
                files = result.get("files") or []
                if not files:
                    return ToolResult(ok=True, output="no workgroup files")
                total = result.get("total", len(files))
                noun = "file" if total == 1 else "files"
                lines = [f"{total} workgroup {noun}:"]
                for item in files:
                    lines.append(
                        f"- {item['name']} · {item['size']} bytes · "
                        f"sha256:{item['sha256']}",
                    )
                    note = " ".join(str(item.get("note") or "").split())
                    if note:
                        lines.append(f"  {note[:220]}")
                if result.get("next_offset") is not None:
                    lines.append(f"next_offset: {result['next_offset']}")
                return ToolResult(ok=True, output="\n".join(lines))
            if action == "send":
                raw_path = str(kwargs.get("path") or "")
                if not raw_path:
                    raise ValueError("path required for send")
                source = _source_path(raw_path)
                if not source.is_file():
                    raise ValueError(f"no such file: {source}")
                result = asyncio.run(
                    wc.send_file(
                        get_home(), wg_id, source,
                        note=str(kwargs.get("note") or ""),
                    ),
                )
                return ToolResult(
                    ok=True,
                    output=(
                        f"sent {result['name']} · {result['size']} bytes · "
                        f"sha256:{result['sha256']}\n{result['marker']}"
                    ),
                )
            if action == "get":
                digest = str(kwargs.get("sha256") or "")
                if not digest:
                    raise ValueError("sha256 required for get")
                metadata, data = asyncio.run(wc.get_file(get_home(), wg_id, digest))
                # The hub names the file: without a dest of the agent's own, it lands inside the workspace or nowhere.
                chosen = str(kwargs.get("dest") or "")
                resolve = resolve_path if chosen else resolve_workspace_path
                requested = resolve(chosen or str(metadata["name"]), for_write=True)
                destination = _available_destination(requested)
                if destination != requested:
                    destination = resolve(str(destination), for_write=True)
                destination.parent.mkdir(parents=True, exist_ok=True)
                with destination.open("xb") as handle:
                    handle.write(data)
                return ToolResult(
                    ok=True,
                    output=f"downloaded {metadata['name']} to {destination}",
                )
            return ToolResult(
                ok=False,
                output="",
                error="action must be list, send, or get",
            )
        except alp_client.RemoteError as e:
            return ToolResult(
                ok=False, output="",
                error=f"hub rejected: {e.code} {e.message}",
            )
        except (OSError, ValueError, alp_client.ClientError) as e:
            return ToolResult(ok=False, output="", error=str(e))


TOOL = WorkgroupFileTool
