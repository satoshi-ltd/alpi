from __future__ import annotations

from pathlib import Path

from alf.tools._paths import resolve_path, suggest_similar_paths
from alf.tools.base import Tool, ToolResult


class ReadFile(Tool):
    name = "read_file"
    description = (
        "Read a file from disk. Use this instead of `terminal cat/head/tail`.\n"
        "\n"
        "Relative paths root at the workspace; absolute paths work anywhere "
        "except sensitive system locations (/etc, SSH keys, .aws/credentials, "
        "docker sockets, etc.). Binary files are refused early (null byte or "
        ">30% non-text bytes in the first 8KB). For very large files use "
        "`offset` + `limit` to read a slice.\n"
        "\n"
        "DO NOT use read_file for:\n"
        "  • USER.md / MEMORY.md / PERSONALITY.md → use `memory(action='read')`\n"
        "  • SKILL.md of a skill you want to inspect → read via /skills"
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Absolute file path."},
            "offset": {"type": "integer", "description": "Line to start from (0-indexed).", "default": 0},
            "limit": {"type": "integer", "description": "Max lines to read.", "default": 2000},
        },
        "required": ["path"],
    }

    def run(self, path: str, offset: int = 0, limit: int = 2000) -> ToolResult:
        try:
            p = resolve_path(path)
        except ValueError as e:
            return ToolResult(ok=False, output="", error=str(e))
        if not p.exists():
            hints = suggest_similar_paths(p)
            msg = f"File not found: {p}"
            if hints:
                msg += ". Similar: " + ", ".join(hints)
            return ToolResult(ok=False, output="", error=msg)
        # Sniff the first few KB to refuse binaries early (PNG, ZIP, PDF,
        # compiled binaries, etc.) — otherwise we'd dump garbage into the
        # LLM context.
        try:
            head = p.open("rb").read(8192)
        except OSError as e:
            return ToolResult(ok=False, output="", error=f"Read failed: {e}")
        if _looks_binary(head):
            size = p.stat().st_size
            return ToolResult(ok=False, output="",
                              error=f"Binary file ({size:,} bytes): {p}")
        try:
            lines = p.read_text().splitlines()
        except UnicodeDecodeError:
            return ToolResult(ok=False, output="", error=f"Binary file: {p}")
        chunk = lines[offset : offset + limit]
        numbered = "\n".join(f"{i+offset+1:>6}\t{line}" for i, line in enumerate(chunk))
        return ToolResult(ok=True, output=numbered)


def _looks_binary(blob: bytes) -> bool:
    if not blob:
        return False
    if b"\x00" in blob:
        return True
    # Text bytes: tab, LF, CR, form-feed + printable ASCII + high bytes
    # (UTF-8 continuation) — control chars in the C0 range count against.
    text_chars = bytes(range(0x20, 0x7F)) + b"\t\n\r\f\b"
    non_text = sum(1 for b in blob if b not in text_chars and b < 0x80)
    return non_text / len(blob) > 0.30


TOOL = ReadFile
