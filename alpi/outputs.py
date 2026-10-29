"""JSONL store at ``<home>/outputs/outputs.jsonl``, capped at MAX_OUTPUTS.

Row schema (one JSON object per line):
    id           12 hex chars
    profile      ``default`` or ``<name>``
    created_at   epoch seconds (float)
    title        optional short headline (omitted when not set)
    summary      the caller's one or two plain sentences (omitted when none was given; readers derive one from the body)
    body         message body
    type         ``info`` | ``warning`` | ``error``
    status       ``unread`` | ``read``
    session_id   originating chat session, or ``""``
    job_id       scheduled job that produced it (omitted when not set)
    run_id       run journal of that job execution (omitted when not set)
    delivered_to channels the matching notification went out on
"""

from __future__ import annotations

import json
import os
import re
import secrets
import threading
import time
from pathlib import Path
from typing import Any, Iterable

from alpi._redact import redact, scrub_surrogates
from alpi.secrets_io import open_private

MAX_OUTPUTS = 500

VALID_TYPE = frozenset({"info", "warning", "error"})
VALID_STATUS = frozenset({"unread", "read"})

_ALLOWED_EMOJI = frozenset("\U0001F534\U0001F7E1\U0001F7E2")
_EMOJI_RANGES = (
    (0x1F300, 0x1FAFF),
    (0x1F1E6, 0x1F1FF),
    (0x2600, 0x27BF),
    (0x2B00, 0x2BFF),
    (0xFE00, 0xFE0F),
)
_EMOJI_SINGLES = frozenset({0x200D, 0x20E3})


def _is_disallowed_emoji(ch: str) -> bool:
    if ch in _ALLOWED_EMOJI:
        return False
    cp = ord(ch)
    if cp in _EMOJI_SINGLES:
        return True
    return any(lo <= cp <= hi for lo, hi in _EMOJI_RANGES)


def sanitize_emoji(text: str) -> str:
    if not text:
        return text or ""
    kept = "".join("" if _is_disallowed_emoji(ch) else ch for ch in text)
    kept = re.sub(r"[^\S\n]{2,}", " ", kept)
    kept = re.sub(r"[^\S\n]+(?=\n)", "", kept)
    return kept.strip()


_HEADING_RE = re.compile(r"^\s*(#{1,6})\s+(.*?)\s*$")
_HR_RE = re.compile(r"^\s*([-*_])\1{2,}\s*$")
_QUOTE_RE = re.compile(r"^\s*>\s?(.*)$")
_LIST_RE = re.compile(r"^\s*([-*•]|[0-9]+[.)])\s+(.*)$")
_LINK_RE = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
_HTML_RE = re.compile(r"</?[A-Za-z][^>]*>")


def _normalize_inline(s: str) -> str:
    s = _HTML_RE.sub("", s)
    s = _LINK_RE.sub(lambda m: m.group(1), s)
    return s


_CODE_SPAN_RE = re.compile(r"`[^`]*`")
_URL_RE = re.compile(r"https?://[^\s<>]*[^\s<>*_~.,;:!?'\")\]]")
_SLOT_RE = re.compile("\x00([0-9]+)\x00")
_STRONG_RE = re.compile(r"\*\*(.+?)\*\*")
_EM_STAR_RE = re.compile(r"(^|[^A-Za-z0-9_*])\*([^\s*](?:[^*]*[^\s*])?)\*(?![A-Za-z0-9_*])")
_EM_UNDERSCORE_RE = re.compile(r"(^|[^A-Za-z0-9_])_([^\s_](?:[^_]*[^\s_])?)_(?![A-Za-z0-9_])")
_STRIKE_RE = re.compile(r"~~(.+?)~~")
_LINE_BREAK_RE = re.compile("\r\n?|[\u2028\u2029\x85]")
_SEPARATOR_CHAR_RE = re.compile("[\x1c-\x1f]")


def canonical_text(text: str) -> str:
    return _SEPARATOR_CHAR_RE.sub(" ", _LINE_BREAK_RE.sub("\n", text or "")).replace("\ufeff", "")


def text_arg(value: Any, joiner: str = " ") -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)) and all(isinstance(item, str) for item in value):
        return joiner.join(value)
    return ""


def plain_inline(text: str) -> str:
    held: list[str] = []

    def hold(m: re.Match) -> str:
        token = m.group(0)
        held.append(token[1:-1] if token.startswith("`") else token)
        return f"\x00{len(held) - 1}\x00"

    s = _CODE_SPAN_RE.sub(hold, (text or "").replace("\x00", ""))
    s = _URL_RE.sub(hold, _normalize_inline(s))
    s = _STRONG_RE.sub(r"\1", s)
    s = _EM_STAR_RE.sub(r"\1\2", s)
    s = _EM_UNDERSCORE_RE.sub(r"\1\2", s)
    s = _STRIKE_RE.sub(r"\1", s)
    return _SLOT_RE.sub(lambda m: held[int(m.group(1))], s)


def normalize_notification_title(text: str) -> str:
    if not text:
        return text or ""
    text = canonical_text(text)
    heading = _HEADING_RE.match(text)
    if heading:
        text = heading.group(2)
    return re.sub(r"\s+", " ", sanitize_emoji(plain_inline(text))).strip()


def stored_title(text: Any) -> str:
    if not isinstance(text, str) or not text:
        return ""
    return re.sub(r"\s+", " ", sanitize_emoji(_normalize_inline(canonical_text(text)))).strip()


# Mirrored by common/notificationSummary.mjs; common/notificationSummary.fixtures.mjs holds the corpus both test against.
SUMMARY_MAX = 200
LABEL_MAX_CHARS = 32
LABEL_MAX_WORDS = 5
_SUMMARY_FLOOR = 60
_OPEN_ENDS = (":", "：")
_LABEL_ONLY_RE = re.compile(r"^\*\*\s*([^*]+?)\s*\*\*\s*:?$")
_LABEL_LINE_RE = re.compile(r"^\*\*[^*]+\*\*:?\s+\S")
_STATUS_LINE_RE = re.compile(r"^[\U0001F534\U0001F7E1\U0001F7E2]\s+\S")
_SEPARATOR_CELL_RE = re.compile(r":?-+:?")
_SENTENCE_END_RE = re.compile(r"[.!?](?=\s)")


def _is_label(line: str) -> bool:
    m = _LABEL_ONLY_RE.match(line)
    if not m:
        return False
    label = m.group(1).rstrip(":").strip()
    return len(label) <= LABEL_MAX_CHARS and len(label.split()) <= LABEL_MAX_WORDS


def _is_table_separator(line: str) -> bool:
    if "|" not in line:
        return False
    s = line.strip()
    s = s[1:] if s.startswith("|") else s
    s = s[:-1] if s.endswith("|") else s
    cells = [cell.strip() for cell in s.split("|")]
    return all(_SEPARATOR_CELL_RE.fullmatch(cell) for cell in cells)


def _fence_of(line: str) -> str:
    return line[:3] if line.startswith(("```", "~~~")) else ""


def _prose_units(body: str) -> Iterable[str]:
    lines = body.split("\n")
    para: list[str] = []
    fence = ""
    table = False
    for i, raw in enumerate(lines):
        line = sanitize_emoji(raw)
        marker = _fence_of(line)
        if fence:
            if marker == fence:
                fence = ""
            continue
        if table and line and "|" in line:
            continue
        table = False
        if marker or not line or _HR_RE.match(line) or _HEADING_RE.match(line) or _is_label(line):
            fence = marker
        elif "|" in line and i + 1 < len(lines) and _is_table_separator(lines[i + 1]):
            table = True
        elif not line.startswith("|"):
            quote = _QUOTE_RE.match(line)
            content = quote.group(1).strip() if quote else line
            item = _LIST_RE.match(content)
            if not (item or _LABEL_LINE_RE.match(content) or _STATUS_LINE_RE.match(content)):
                text = plain_inline(content).strip()
                if text:
                    para.append(text)
                continue
            if para:
                yield " ".join(para)
                para = []
            text = plain_inline(item.group(2) if item else content).strip()
            if text:
                yield text
            continue
        if para:
            yield " ".join(para)
            para = []
    if para:
        yield " ".join(para)


def _clip_summary(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > SUMMARY_MAX:
        head = text[: SUMMARY_MAX + 1]
        ends = [m.end() for m in _SENTENCE_END_RE.finditer(head) if _SUMMARY_FLOOR <= m.end() <= SUMMARY_MAX]
        if ends:
            text = text[: ends[-1]]
        else:
            cut = text[: SUMMARY_MAX - 1]
            space = cut.rfind(" ")
            text = (cut[:space] if space >= _SUMMARY_FLOOR else cut).rstrip(" ,;:：") + "…"
    if text.endswith(_OPEN_ENDS):
        text = text[:-1].rstrip() + "…"
    return text


def normalize_summary(text: str) -> str:
    parts: list[str] = []
    fence = ""
    for raw in canonical_text(text_arg(text)).split("\n"):
        line = sanitize_emoji(raw)
        marker = _fence_of(line)
        if fence or marker:
            fence = "" if marker == fence else (fence or marker)
            continue
        if not line or _HR_RE.match(line) or _is_table_separator(line):
            continue
        marked = _HEADING_RE.match(line) or _QUOTE_RE.match(line)
        if marked:
            line = marked.group(marked.lastindex).strip()
        item = _LIST_RE.match(line)
        if item:
            line = item.group(2)
        parts.append(plain_inline(line).strip())
    return _clip_summary(" ".join(part for part in parts if part))


def derive_summary(body: str) -> str:
    text = ""
    for unit in _prose_units(canonical_text(text_arg(body))):
        text = f"{text} {unit}" if text else unit
        if not text.endswith(_OPEN_ENDS) or len(text) >= SUMMARY_MAX:
            break
    return _clip_summary(text) if text else ""


def message_summary(output: dict[str, Any]) -> str:
    return output.get("summary") or derive_summary(output.get("body") or "")


def given_summary(output: dict[str, Any]) -> str:
    summary = output.get("summary") or ""
    return summary if summary != derive_summary(output.get("body") or "") else ""


def normalize_notification_body(text: str) -> str:
    if not text:
        return text or ""
    blocks: list[str] = []
    prose: list[str] = []
    fence: list[str] | None = None
    for raw in text.split("\n"):
        if fence is None and raw.lstrip().startswith("```"):
            if prose:
                blocks.append(_normalize_prose(prose))
                prose = []
            fence = [raw.rstrip()]
        elif fence is not None:
            fence.append(raw.rstrip())
            if raw.strip().startswith("```"):
                blocks.append("\n".join(fence))
                fence = None
        else:
            prose.append(raw)
    if fence is not None:
        blocks.append("\n".join(fence))
    if prose:
        blocks.append(_normalize_prose(prose))
    return "\n".join(block for block in blocks if block).strip("\n")


def _normalize_prose(lines: list[str]) -> str:
    out: list[str] = []
    for raw in lines:
        line = raw.rstrip()
        if _HR_RE.match(line):
            continue
        heading = _HEADING_RE.match(line)
        if heading:
            label = sanitize_emoji(_normalize_inline(heading.group(2))).rstrip(":").strip()
            if label:
                marker = "##" if len(heading.group(1)) <= 2 else "###"
                out.append(f"{marker} {label}")
            continue
        quote = _QUOTE_RE.match(line)
        if quote:
            out.append(f"> {_normalize_inline(quote.group(1)).strip()}")
            continue
        item = _LIST_RE.match(line)
        if item:
            out.append(f"{item.group(1)} {_normalize_inline(item.group(2)).strip()}")
        else:
            out.append(_normalize_inline(line))
    return sanitize_emoji("\n".join(out))


_lock = threading.Lock()


def _store_path(home: Path) -> Path:
    return home / "outputs" / "outputs.jsonl"


def _new_id() -> str:
    return secrets.token_hex(6)


def _read_all(home: Path) -> list[dict[str, Any]]:
    path = _store_path(home)
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8").split("\n")
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and isinstance(obj.get("id"), str) and obj["id"]:
            obj["body"] = normalize_notification_body(obj.get("body") or "")
            title = stored_title(obj.get("title") or "")
            if title:
                obj["title"] = title
            elif "title" in obj:
                del obj["title"]
            stored = obj.get("summary")
            if not (isinstance(stored, str) and stored.strip()) and "summary" in obj:
                del obj["summary"]
            out.append(obj)
    return out


def _atomic_rewrite(path: Path, items: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            for it in items:
                f.write(scrub_surrogates(json.dumps(it, ensure_ascii=False)) + "\n")
            f.flush()
            os.fsync(f.fileno())
    except Exception:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise
    os.replace(str(tmp), str(path))


def append(
    home: Path,
    *,
    profile: str,
    body: str,
    type: str = "info",
    session_id: str = "",
    delivered_to: list[str] | None = None,
    title: str = "",
    job_id: str = "",
    run_id: str = "",
    summary: str = "",
) -> dict[str, Any]:
    if type not in VALID_TYPE:
        type = "info"
    body = normalize_notification_body(body or "")
    title = normalize_notification_title(title or "")
    summary = normalize_summary(summary)

    output = {
        "id": _new_id(),
        "profile": profile or "default",
        "created_at": time.time(),
        "body": body,
        "type": type,
        "status": "unread",
        "session_id": session_id or "",
        "delivered_to": list(delivered_to or []),
    }
    if title:
        output["title"] = title
    if summary:
        output["summary"] = summary
    if job_id:
        output["job_id"] = job_id
    if run_id:
        output["run_id"] = run_id

    stored = redact(output)
    path = _store_path(home)
    with _lock:
        existing = _read_all(home)
        existing.append(stored)
        if len(existing) > MAX_OUTPUTS:
            existing = existing[-MAX_OUTPUTS:]
            _atomic_rewrite(path, existing)
        else:
            with open_private(path) as f:
                f.write(scrub_surrogates(json.dumps(stored, ensure_ascii=False)) + "\n")
    return output


def list_outputs(
    home: Path,
    *,
    status: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    items = _read_all(home)
    if status is not None:
        if status not in VALID_STATUS:
            return []
        items = [it for it in items if it.get("status") == status]
    items.sort(key=lambda it: float(it.get("created_at") or 0.0), reverse=True)
    if limit > 0:
        items = items[:limit]
    return items


def read(home: Path, output_id: str) -> dict[str, Any] | None:
    for it in _read_all(home):
        if it.get("id") == output_id:
            return it
    return None


def _mutate(home: Path, output_id: str, mutate) -> dict[str, Any] | None:
    with _lock:
        items = _read_all(home)
        target: dict[str, Any] | None = None
        for it in items:
            if it.get("id") == output_id:
                target = it
                break
        if target is None:
            return None
        mutate(target)
        _atomic_rewrite(_store_path(home), items)
        return target


def mark_read(home: Path, output_id: str) -> dict[str, Any] | None:
    def _apply(it: dict[str, Any]) -> None:
        if it.get("status") == "unread":
            it["status"] = "read"
    return _mutate(home, output_id, _apply)


def mark_unread(home: Path, output_id: str) -> dict[str, Any] | None:
    def _apply(it: dict[str, Any]) -> None:
        it["status"] = "unread"
    return _mutate(home, output_id, _apply)


def delete(home: Path, output_id: str) -> bool:
    """Remove one output by id. Returns True iff a row was actually dropped."""
    with _lock:
        items = _read_all(home)
        kept = [it for it in items if it.get("id") != output_id]
        if len(kept) == len(items):
            return False
        _atomic_rewrite(_store_path(home), kept)
        return True


def mark_all_read(home: Path) -> int:
    with _lock:
        items = _read_all(home)
        touched = 0
        for it in items:
            if it.get("status") == "unread":
                it["status"] = "read"
                touched += 1
        if touched:
            _atomic_rewrite(_store_path(home), items)
        return touched


def normalize_native_notification_args(args: dict) -> dict | None:
    """Returns None when the call wasn't user-facing (empty text) so callers skip it."""
    text = text_arg(args.get("text"), "\n").strip()
    if not text:
        return None
    type = str(args.get("type") or "info").strip().lower()
    if type not in VALID_TYPE:
        type = "info"
    return {
        "notification_title": text_arg(args.get("title")).strip(),
        "summary": text_arg(args.get("summary")).strip(),
        "body": text,
        "type": type,
        "delivered_to": ["alpi"],
    }


def record_child_native_message(home: Path, args: dict, *, job_id: str = "", run_id: str = "") -> str:
    """Files a child agent's native notification and emits output.created + agent.message so the parent's client wakes."""
    record = normalize_native_notification_args(args)
    if record is None:
        return ""

    try:
        from alpi.home import profile_name
        from alpi.host import events as host_events
    except Exception:  # noqa: BLE001
        return ""

    profile = profile_name(home)
    type = record["type"]

    try:
        output = append(
            home,
            profile=profile,
            body=record["body"],
            type=type,
            delivered_to=["alpi"],
            title=record["notification_title"],
            job_id=job_id,
            run_id=run_id,
            summary=record["summary"],
        )
    except Exception:  # noqa: BLE001
        return ""

    output_id = output["id"]
    try:
        host_events.emit("output.created", {
            "profile": profile,
            "id": output_id,
            "type": type,
        })
    except Exception:  # noqa: BLE001
        pass

    payload = {
        "profile": profile,
        "title": output.get("title") or profile or "alpi",
        "summary": message_summary(output),
        "body": output["body"],
        "type": type,
        "output_id": output_id,
        "deep_link": f"/outputs/{profile}/{output_id}",
    }
    try:
        host_events.emit("agent.message", payload)
    except Exception:  # noqa: BLE001
        pass

    return output_id


def _suppress_native_emit() -> bool:
    return (
        os.environ.get("ALPI_SCHEDULE_CHILD") == "1"
        or os.environ.get("ALPI_PARENT_EMITS_AGENT_MESSAGE") == "1"
    )


def create_output(
    *, text: str, type: str,
    delivered_to: list[str],
    title: str = "",
    summary: str = "",
) -> dict | None:
    # Persistence is opportunistic — failures never block delivery.
    try:
        from alpi.home import get_active_session, get_home, profile_name
    except Exception:  # noqa: BLE001
        return None
    try:
        home = get_home()
        prof = profile_name(home)
    except Exception:  # noqa: BLE001
        return None
    try:
        session_id = get_active_session() or ""
    except Exception:  # noqa: BLE001
        session_id = ""
    try:
        return append(
            home, profile=prof,
            body=text, type=type, session_id=session_id,
            delivered_to=delivered_to, title=title, summary=summary,
        )
    except Exception:  # noqa: BLE001
        return None


def create_output_and_emit_message(
    *, text: str, title: str, type: str,
    delivered_to: list[str],
    summary: str = "",
) -> str:
    """Callers must guard with _suppress_native_emit() — schedule children defer to the parent."""
    output = create_output(
        text=text, type=type,
        delivered_to=delivered_to, title=title, summary=summary,
    )
    if output is None:
        return ""
    payload: dict = {
        "profile": output["profile"],
        "title": output.get("title") or output["profile"] or "alpi",
        "summary": message_summary(output),
        "body": output["body"],
        "type": output["type"],
        "output_id": output["id"],
        "deep_link": f"/outputs/{output['profile']}/{output['id']}",
    }
    if output.get("session_id"):
        payload["session_id"] = output["session_id"]
    try:
        from alpi.host import events as host_events
        host_events.emit("agent.message", payload)
        host_events.emit("output.created", {
            "profile": output["profile"],
            "id": output["id"],
            "type": output["type"],
        })
    except Exception:  # noqa: BLE001
        pass
    return output["id"]


__all__ = [
    "MAX_OUTPUTS",
    "VALID_TYPE",
    "VALID_STATUS",
    "append",
    "derive_summary",
    "message_summary",
    "given_summary",
    "mark_unread",
    "list_outputs",
    "read",
    "mark_read",
    "mark_all_read",
    "delete",
    "normalize_native_notification_args",
    "record_child_native_message",
    "create_output",
    "create_output_and_emit_message",
]
