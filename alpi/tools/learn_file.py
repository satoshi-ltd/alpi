from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from alpi import attachments as att
from alpi.home import get_home
from alpi.tools import _state
from alpi.tools._paths import resolve_path
from alpi.tools.base import Tool, ToolResult

_DOCUMENTS_REL = (".alpi", "documents")


def _safe_name(name: str) -> str:
    base = Path(str(name or "")).name
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", base).strip("._")
    return cleaned[:128] or "file"


def _safe_folder(folder: str) -> str:
    if not folder:
        return ""
    if folder.startswith("/") or folder.startswith("~") or "\\" in folder:
        raise ValueError("folder must be a relative path inside the workspace")
    parts: list[str] = []
    for seg in folder.split("/"):
        if seg in ("", "."):
            continue
        if seg == "..":
            raise ValueError("folder must not contain '..'")
        safe = re.sub(r"[^A-Za-z0-9._-]+", "_", seg).strip("._")
        if not safe:
            raise ValueError(f"invalid folder segment: {seg!r}")
        parts.append(safe)
    return "/".join(parts)


def _within(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def _unique_path(directory: Path, filename: str) -> Path:
    target = directory / filename
    if not target.exists():
        return target
    stem, suffix = Path(filename).stem, Path(filename).suffix
    n = 2
    while True:
        cand = directory / f"{stem}-{n}{suffix}"
        if not cand.exists():
            return cand
        n += 1


def _resolve_source(name: str, source_path: str) -> tuple[Path, str]:
    if source_path:
        src = resolve_path(source_path)
        if not src.is_file():
            raise ValueError(f"file not found: {source_path}")
        return src, src.name
    atts = _state.get_turn_attachments()
    if name:
        matches = [a for a in atts if a.get("name") == name]
        if not matches:
            raise ValueError(f"no attachment named {name!r} in this turn; attach it or pass source_path")
        if len(matches) > 1:
            raise ValueError(f"multiple attachments named {name!r}; pass source_path to disambiguate")
        chosen = matches[0]
        return Path(chosen["path"]), chosen.get("name") or Path(chosen["path"]).name
    if len(atts) == 1:
        chosen = atts[0]
        return Path(chosen["path"]), chosen.get("name") or Path(chosen["path"]).name
    if not atts:
        raise ValueError("no file to learn: attach a file, or pass source_path")
    names = ", ".join(a.get("name", "?") for a in atts)
    raise ValueError(f"multiple files attached ({names}); specify which with name= or source_path=")


def _append_manifest(docs_root: Path, entry: dict) -> None:
    docs_root.mkdir(parents=True, exist_ok=True)
    with open(docs_root / "manifest.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")


class LearnFile(Tool):
    name = "learn_file"
    description = (
        "Save an attached (or named) file into the user's workspace as a durable "
        "document and index it so `search_workspace` can retrieve it in future "
        "turns. Use ONLY when the user explicitly asks to learn / remember / save "
        "/ index a file — attachments are otherwise one-turn context.\n"
        "\n"
        "Resolution: if `source_path` is given it's used; else `name` must match a "
        "file attached this turn; else the single attached file is used; else it "
        "errors asking which file. The file is copied under "
        "`<workspace>/.alpi/documents/YYYY/MM/` (or a `folder` you pass), never "
        "overwriting. Supported: text/source files and PDFs; images only with "
        "`ocr=true`. Returns `{ok, path, indexed}`."
    )
    parameters = {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Filename of a file attached this turn (e.g. 'plan.md'). Omit if there's exactly one attachment or you pass source_path.",
            },
            "source_path": {
                "type": "string",
                "description": "Path to an existing file (workspace-relative or absolute) to learn instead of an attachment.",
            },
            "folder": {
                "type": "string",
                "description": "Optional sub-folder under .alpi/documents/ (e.g. 'contracts'). Default is YYYY/MM. No '..' or absolute paths.",
            },
            "ocr": {
                "type": "boolean",
                "description": "OCR scanned PDFs / images so their text is indexed. Required to learn image files. Default false.",
                "default": False,
            },
        },
    }

    def run(
        self,
        name: str = "",
        source_path: str = "",
        folder: str = "",
        ocr: bool = False,
    ) -> ToolResult:
        from alpi import config as cfg_mod
        from alpi.tools import workspace as ws_tool

        home = get_home().resolve()
        ws = cfg_mod.load(home).workspace_path
        if ws is None:
            return ToolResult(
                ok=False, output="",
                error="no workspace configured — set `workspace` in config.yaml before learning files",
            )
        ws = ws.resolve()
        if not ws.exists() or not ws.is_dir():
            return ToolResult(
                ok=False, output="",
                error=f"configured workspace does not exist: {ws}",
            )

        try:
            src, original_name = _resolve_source(name, source_path)
        except ValueError as e:
            return ToolResult(ok=False, output="", error=str(e))

        try:
            validated = att.validate([{"path": str(src), "name": original_name}])
        except att.AttachmentError as e:
            return ToolResult(ok=False, output="", error=str(e))
        meta = validated[0]
        if att.is_image(meta.mime) and not ocr:
            return ToolResult(
                ok=False, output="",
                error=f"{meta.name}: images are only learnable with ocr=true (RAG.2 indexes their OCR text)",
            )

        try:
            safe_folder = _safe_folder(folder)
        except ValueError as e:
            return ToolResult(ok=False, output="", error=str(e))

        now = datetime.now(timezone.utc)
        docs_root = ws.joinpath(*_DOCUMENTS_REL)
        subdir = safe_folder or now.strftime("%Y/%m")
        dest_dir = docs_root.joinpath(*subdir.split("/")).resolve()
        if not _within(dest_dir, docs_root.resolve()):
            return ToolResult(ok=False, output="", error="resolved destination escapes the documents directory")
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = _unique_path(dest_dir, f"{now.strftime('%Y-%m-%d')}-{_safe_name(original_name)}")

        try:
            shutil.copy2(src, dest)
        except OSError as e:
            return ToolResult(ok=False, output="", error=f"could not copy file: {e}")

        rel_path = dest.relative_to(ws).as_posix()
        # Manifest is metadata only (not authoritative) — surface a failure, don't abort.
        manifest_warning = None
        try:
            _append_manifest(docs_root, {
                "path": rel_path,
                "original_name": meta.name,
                "mime": meta.mime,
                "size": meta.size,
                "learned_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "source": "path" if source_path else "attachment",
            })
        except OSError as e:
            manifest_warning = f"manifest not written: {e}"

        def _result(body: dict) -> ToolResult:
            if manifest_warning:
                body["manifest_written"] = False
                body["warning"] = manifest_warning
            return ToolResult(ok=True, output=json.dumps(body))

        try:
            summary = ws_tool.index_files(home, [dest], ocr=ocr)
        except Exception as e:  # noqa: BLE001
            return _result({"ok": False, "path": rel_path, "indexed": False, "error": str(e)[:200]})
        indexed = summary.get("indexed_files", 0) >= 1 and summary.get("added_chunks", 0) >= 1
        if not indexed:
            failed = summary.get("failed_files") or []
            reason = failed[0]["reason"] if failed else "no content indexed"
            return _result({"ok": False, "path": rel_path, "indexed": False, "error": reason})
        return _result({"ok": True, "path": rel_path, "indexed": True})


TOOL = LearnFile
