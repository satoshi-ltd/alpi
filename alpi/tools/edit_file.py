from __future__ import annotations

import errno
import os
import re
import sys
from bisect import bisect_left
from contextlib import suppress
from pathlib import Path
from stat import S_IMODE, S_ISREG
from tempfile import NamedTemporaryFile

from alpi.tools._paths import release_unused_claim, resolve_path, suggest_similar_paths
from alpi.tools.base import Tool, ToolResult


class EditFile(Tool):
    name = "edit_file"
    description = (
        "Targeted edit: replace an exact string with a new one in a file. "
        "The match must be unique in the file (single occurrence). Line "
        "endings, permissions and owner are kept.\n"
        "\n"
        "Relative paths root at the workspace; absolute paths work anywhere "
        "except sensitive locations (SSH keys, .env files, etc.). Use this instead of "
        "`terminal sed/awk/perl -i`.\n"
        "\n"
        "If `old_string` matches 0 or >1 times → the call fails. In that "
        "case, widen the context in `old_string` with surrounding lines "
        "until it's unique, then retry.\n"
        "\n"
        "DO NOT use edit_file for:\n"
        "  • memory files → use `memory(replace)`\n"
        "  • skill files (SKILL.md or anything in scripts/references/"
        "assets/secrets/) → use `skill(action='edit'|'add_file')`. Direct "
        "edits skip the security scanner."
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "old_string": {"type": "string"},
            "new_string": {"type": "string"},
        },
        "required": ["path", "old_string", "new_string"],
    }

    def run(self, path: str, old_string: str, new_string: str) -> ToolResult:
        try:
            p = resolve_path(path, for_write=True)
        except ValueError as e:
            return ToolResult(ok=False, output="", error=str(e))
        if _is_skill_path(p):
            return ToolResult(
                ok=False, output="",
                error=(
                    "path is inside a skill directory — use "
                    "`skill(action='edit')` for SKILL.md or "
                    "`skill(action='add_file')` for scripts/references/"
                    "assets/secrets. Direct edits bypass the security scanner."
                ),
            )
        try:
            regular = S_ISREG(p.stat().st_mode)
        except (FileNotFoundError, NotADirectoryError):
            release_unused_claim(p)
            hints = suggest_similar_paths(p)
            msg = f"File not found: {p}"
            if hints:
                msg += ". Similar: " + ", ".join(hints)
            return ToolResult(ok=False, output="", error=msg)
        except OSError as e:
            return ToolResult(ok=False, output="", error=f"Cannot open {p} for a text edit: {e}")
        if not regular:
            return ToolResult(ok=False, output="", error=f"Not a regular file: {p}")
        try:
            with p.open("r+", newline="") as original:
                before = os.fstat(original.fileno())
                encoding = original.encoding
                raw = original.read()
        except (OSError, UnicodeDecodeError) as e:
            return ToolResult(ok=False, output="", error=f"Cannot open {p} for a text edit: {e}")
        text, wide = _plain(raw)
        old = _LINE_ENDING.sub("\n", old_string)
        count = text.count(old)
        if count == 0:
            return ToolResult(ok=False, output="", error="old_string not found")
        if count > 1:
            return ToolResult(ok=False, output="",
                              error=f"old_string matches {count} times; make it unique")
        at = text.find(old)
        start, end = (plain + bisect_left(wide, plain) for plain in (at, at + len(old)))
        wanted = text[:at] + _LINE_ENDING.sub("\n", new_string) + text[at + len(old):]
        for mark in dict.fromkeys((_ending_at(raw, start), "\n", "\r", "\r\n")):
            after = raw[:start] + _WRITTEN_ENDING.sub(lambda _: mark, new_string) + raw[end:]
            if _LINE_ENDING.sub("\n", after) == wanted:
                break
        else:
            return ToolResult(
                ok=False, output="",
                error="refused — the new text would merge with the line ending next to it; include that line in old_string",
            )
        from alpi.tools._lint import lint_content
        lint_err = lint_content(p, wanted)
        if lint_err:
            return ToolResult(
                ok=False, output="",
                error=f"refused — edit would make {p.name} unparseable: {lint_err}",
            )
        try:
            data = after.encode(encoding)
        except UnicodeEncodeError as e:
            return ToolResult(ok=False, output="", error=f"Cannot write {p} in its encoding ({encoding}): {e}")
        try:
            if not _replaced(p, data, before):
                p.write_bytes(data)
                with suppress(OSError):
                    p.chmod(S_IMODE(before.st_mode))
        except OSError as e:
            return ToolResult(ok=False, output="", error=f"Cannot write {p}: {e}")
        from alpi.tools import _mutations
        _mutations.record_mutation(_mutations.build_record(p, raw, after, op_hint="edit"))
        return ToolResult(ok=True, output=f"Edited {p}")


_LINE_ENDING = re.compile(r"\r\n|\r|\n")
_WRITTEN_ENDING = re.compile(r"\r\n|\n")
_NO_NEW_ENTRY = (errno.EACCES, errno.EPERM, errno.EROFS, errno.ENAMETOOLONG)
_NOT_REPLACEABLE = (errno.EBUSY, errno.EXDEV, errno.EPERM, errno.EACCES)


# `wide` lists the offsets in the "\n"-only text whose line ending takes two characters in the file.
def _plain(raw: str) -> tuple[str, list[int]]:
    wide = [found.start() - nth for nth, found in enumerate(re.finditer("\r\n", raw))]
    return _LINE_ENDING.sub("\n", raw), wide


def _ending_at(raw: str, start: int) -> str:
    ahead = _LINE_ENDING.search(raw, start)
    if ahead:
        return ahead.group()
    last = max(raw.rfind("\n", 0, start), raw.rfind("\r", 0, start))
    if last < 0:
        return "\n"
    return "\r\n" if raw[last] == "\n" and raw[last - 1:last] == "\r" else raw[last]


_REMADE_ATTRIBUTES = {"security.selinux", "com.apple.provenance"}


def _carries_attributes(p: Path) -> bool:
    return bool(_attribute_names(p) - _REMADE_ATTRIBUTES)


def _attribute_names(p: Path) -> set[str]:
    try:
        if hasattr(os, "listxattr"):
            return set(os.listxattr(p))
        if sys.platform == "darwin":
            return _darwin_attribute_names(p)
    except OSError:
        return set()
    return set()


def _darwin_attribute_names(p: Path) -> set[str]:
    try:
        import ctypes

        libc = ctypes.CDLL(None)
        libc.listxattr.restype = ctypes.c_ssize_t
        libc.listxattr.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_size_t, ctypes.c_int]
        libc.acl_get_file.restype = ctypes.c_void_p
        libc.acl_get_file.argtypes = [ctypes.c_char_p, ctypes.c_int]
        libc.acl_free.argtypes = [ctypes.c_void_p]
    except (ImportError, AttributeError, OSError):
        return {"unknown"}
    path = os.fsencode(p)
    names: set[str] = set()
    size = libc.listxattr(path, None, 0, 0)
    if size > 0:
        listed = ctypes.create_string_buffer(size)
        got = libc.listxattr(path, listed, size, 0)
        names = {name.decode("utf-8", "replace") for name in listed.raw[:max(got, 0)].split(b"\0") if name} or {"unknown"}
    acl = libc.acl_get_file(path, 0x100)
    if acl:
        libc.acl_free(acl)
        names.add("access control list")
    return names


# False lets the caller truncate in place; raising means the original is untouched.
def _replaced(p: Path, data: bytes, before: os.stat_result) -> bool:
    if before.st_nlink > 1 or getattr(before, "st_flags", 0) or _carries_attributes(p):
        return False
    try:
        staged = NamedTemporaryFile(dir=p.parent, prefix=f".{p.name[:64]}.", suffix=".tmp", delete=False)
    except OSError as e:
        if e.errno in _NO_NEW_ENTRY:
            return False
        raise
    tmp: Path | None = Path(staged.name)
    try:
        with staged:
            staged.write(data)
            staged.flush()
            fd = staged.fileno()
            os.fsync(fd)
            made = os.fstat(fd)
            try:
                if (made.st_uid, made.st_gid) != (before.st_uid, before.st_gid):
                    os.fchown(fd, before.st_uid, before.st_gid)
                os.fchmod(fd, S_IMODE(before.st_mode))
                if S_IMODE(os.fstat(fd).st_mode) != S_IMODE(before.st_mode):
                    return False
            except OSError:
                return False
        try:
            os.replace(tmp, p)
        except OSError as e:
            if e.errno in _NOT_REPLACEABLE:
                return False
            raise
        tmp = None
        return True
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)


def _is_skill_path(p: Path) -> bool:
    from alpi.home import get_home
    skills_root = (get_home() / "skills").resolve()
    try:
        p.resolve().relative_to(skills_root)
        return True
    except ValueError:
        return False


TOOL = EditFile
