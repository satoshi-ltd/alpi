"""Memory tool — read/add/replace/remove entries in USER.md and MEMORY.md."""

from __future__ import annotations

import re

from alpi.home import get_home
from alpi.memory import (
    ENTRY_DELIMITER,
    MemoryStore,
    _is_duplicate,
    fuzzy_contains,
    fuzzy_find_unique_entry,
    is_duplicate_stanza,
)
from alpi.tools.base import Tool, ToolResult


_OPERATIONAL_PATTERNS = (
    (re.compile(r"\bchat(?:_|\s+)id\b", re.I), "chat id"),
    (re.compile(r"\bsession(?:_|\s+)id\b", re.I), "session id"),
    (re.compile(r"\bfirst\s+interaction\b", re.I), "interaction log"),
    (re.compile(r"\binbound\b", re.I), "inbound marker"),
    (re.compile(r"\b\d{4}-\d{2}-\d{2}T\d{2}"), "ISO timestamp"),
)


def _operational_warning(text: str) -> str:
    """Return a non-empty warning if ``text`` looks like operational state
    (session / chat / interaction log), else empty. Non-blocking — the
    caller decides whether to attach it to the response."""
    for pattern, label in _OPERATIONAL_PATTERNS:
        if pattern.search(text):
            return (
                f"⚠ looks like operational state ({label}); consider "
                f"whether USER.md / MEMORY.md is the right home. "
                f"Session transcripts are searchable via session_search."
            )
    # Heuristic: 5+-digit numeric id in the same entry as a date or time.
    has_long_id = re.search(r"\b\d{5,}\b", text) is not None
    has_date = re.search(r"\b\d{4}-\d{2}-\d{2}\b", text) is not None
    if has_long_id and has_date:
        return (
            "⚠ entry carries a long numeric id + a date — looks like "
            "operational state. Consider keeping session/chat history "
            "out of USER.md / MEMORY.md."
        )
    return ""


def _cross_file_duplicate(store: MemoryStore, target: str, content: str) -> str | None:
    """If ``content`` is near-duplicate of an entry in the OTHER memory
    file, return the other file's name. Used to catch facts that land
    twice (e.g. vehicle list in both USER.md and MEMORY.md)."""
    key = target.upper()
    other = "MEMORY.md" if key == "USER.MD" else "USER.md" if key == "MEMORY.MD" else None
    if other is None:
        return None
    other_text = store.snapshot()[other]
    return other if _is_duplicate(other_text, content) else None


class Memory(Tool):
    name = "memory"
    description = (
        "Persist facts that apply beyond this turn. CALL this tool — "
        "saying \"I'll remember that\" without a tool call saves "
        "NOTHING; the fact is lost at end of turn.\n"
        "\n"
        "Three targets, pick exactly one per fact — never duplicate across "
        "targets:\n"
        "\n"
        "  USER.md   — stable facts about the user (name, location, "
        "role, long-term preferences). True regardless of assistant.\n"
        "  MEMORY.md — your notes about env/tools (paths, commands, "
        "API quirks, workarounds).\n"
        "  AGENT.md  — how YOU behave (tone, style, length, language, "
        "identity).\n"
        "\n"
        "Voice: use neutral third-person \"user\" in MEMORY.md entries, "
        "never the user's name. The name lives in USER.md; hardcoding it "
        "in MEMORY.md duplicates state and breaks if the user changes "
        "names. Write \"user runs standups at 12:10\", not "
        "\"Javi runs standups at 12:10\".\n"
        "\n"
        "Phrasing: write facts, not instructions. \"User prefers concise "
        "replies\" ✓ — \"Always reply concisely\" ✗. \"Project uses pytest "
        "with xdist\" ✓ — \"Run tests with pytest -n 4\" ✗. Imperative "
        "memory gets re-read as a directive in later sessions and can "
        "override the user's current request or trigger repeated work. "
        "Procedures and workflows belong in skills, not memory.\n"
        "\n"
        "Actions: read | add | replace | remove.\n"
        "\n"
        "AGENT.md flow (voice / identity / persona):\n"
        "  • `add` appends a NEW paragraph — use only for a genuinely "
        "    new section / rule / topic never seen before in the file.\n"
        "  • `replace` swaps the literal `match` text with `content`. "
        "    To CHANGE a rule: match the old line, content = new line. "
        "    To EXTEND a section with a new bullet: match = existing "
        "    line, content = existing line + newline + new bullet. "
        "    Never replace an unrelated rule to 'make room' — you "
        "    will destroy content the user relies on.\n"
        "  • Repeated `add` with paraphrased content accumulates "
        "    duplicated sections; the dedup check will block it.\n"
        "\n"
        "Skip: session progress, chat / session ids, restatements of "
        "the current turn, facts stale within a week, duplicates "
        "(`read` first if unsure).\n"
        "\n"
        "`replace` match must be verbatim from a prior `read` or the "
        "frozen snapshot — never invent one. If unsure, use `add`."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["read", "add", "replace", "remove"],
            },
            "target": {
                "type": "string",
                "enum": ["USER.md", "MEMORY.md", "AGENT.md"],
                "description": "See tool description for target semantics.",
            },
            "content": {
                "type": "string",
                "description": (
                    "Entry content (for add/replace). One fact per call, "
                    "declarative, short. No paragraphs. No headers. For "
                    "MEMORY.md refer to the user as \"user\", never by "
                    "name (the name lives in USER.md)."
                ),
            },
            "match": {
                "type": "string",
                "description": (
                    "Short unique substring from an EXISTING entry "
                    "(replace/remove only). Must be verbatim from a prior "
                    "read — do not invent."
                ),
            },
        },
        "required": ["action", "target"],
    }

    def run(self, action: str, target: str, content: str = "",
            match: str = "") -> ToolResult:
        h = get_home()

        if target.upper() == "AGENT.MD":
            return _handle_agent(h, action, content, match)

        store = MemoryStore(home=h)
        store.seed_defaults()

        try:
            if action == "read":
                snap = store.snapshot()
                usage = store.usage()
                used, limit = usage[target]
                pct = int(used / limit * 100) if limit else 0
                body = snap[target].strip() or "(empty)"
                return ToolResult(ok=True, output=f"[{target}: {pct}% — {used:,}/{limit:,} chars]\n{body}")

            if action == "add":
                if not content.strip():
                    return ToolResult(ok=False, output="", error="'content' required for add")
                other = _cross_file_duplicate(store, target, content)
                if other is not None:
                    return ToolResult(
                        ok=False, output="",
                        error=(
                            f"looks like a near-duplicate of an entry "
                            f"already in {other}. Use `replace` there or "
                            f"confirm this is a genuinely distinct fact."
                        ),
                    )
                store.add(target, content)
                output = self._state_snapshot(store, target)
                warn = _operational_warning(content)
                if warn:
                    output = f"{output}\n\n{warn}"
                return ToolResult(ok=True, output=output)

            if action == "replace":
                if not match or not content:
                    return ToolResult(ok=False, output="", error="'match' and 'content' required for replace")
                new_entries = _modify(store, target, match, replacement=content)
                _write(store, target, new_entries)
                return ToolResult(ok=True, output=self._state_snapshot(store, target))

            if action == "remove":
                if not match:
                    return ToolResult(ok=False, output="", error="'match' required for remove")
                new_entries = _modify(store, target, match, replacement=None)
                _write(store, target, new_entries)
                return ToolResult(ok=True, output=self._state_snapshot(store, target))

            return ToolResult(ok=False, output="", error=f"unknown action: {action}")
        except ValueError as e:
            return ToolResult(ok=False, output="", error=str(e))

    def _state_snapshot(self, store: MemoryStore, target: str) -> str:
        used, limit = store.usage()[target]
        pct = int(used / limit * 100) if limit else 0
        hint = " — consider consolidating old entries before adding more" if pct >= 80 else ""
        current = store.snapshot()[target].strip() or "(empty)"
        return (
            f"{target}: {pct}% ({used:,}/{limit:,} chars){hint}\n\n"
            f"Current contents:\n{current}"
        )


def _locate_literal(text: str, match: str) -> str | None:
    import unicodedata
    from alpi.memory import _fold

    text_nfc = unicodedata.normalize("NFC", text)
    folded_text = _fold(text_nfc)
    folded_match = _fold(match)
    if not folded_match:
        return None
    pos = folded_text.find(folded_match)
    if pos < 0:
        return None
    # NFC + accent-stripping preserves 1-char-per-char for Latin scripts.
    end = pos + len(folded_match)
    return text_nfc[pos:end] if end <= len(text_nfc) else None


def _agent_state(text: str) -> str:
    body = text.strip() or "(empty)"
    return f"AGENT.md: {len(text):,} chars\n\nCurrent contents:\n{body}"


def _handle_agent(home, action: str, content: str, match: str) -> ToolResult:
    from alpi.home import agent_path
    path = agent_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = path.read_text() if path.exists() else ""

    if action == "read":
        return ToolResult(ok=True, output=f"[AGENT.md]\n{text or '(empty)'}")

    if action == "add":
        if not content.strip():
            return ToolResult(ok=False, output="", error="'content' required for add")
        if is_duplicate_stanza(text, content):
            return ToolResult(
                ok=False, output="",
                error=(
                    "near-duplicate of an existing paragraph in AGENT.md. "
                    "For voice / identity changes, use `replace` with the "
                    "literal line you want to change."
                ),
            )
        new = (text.rstrip() + "\n\n" + content.strip() + "\n") if text.strip() else content.strip() + "\n"
        path.write_text(new)
        return ToolResult(ok=True, output=_agent_state(new))

    if action == "replace":
        if not match or not content:
            return ToolResult(ok=False, output="", error="'match' and 'content' required for replace")
        literal = _locate_literal(text, match)
        if literal is None:
            return ToolResult(ok=False, output="", error=f"no match for {match!r}")
        new = text.replace(literal, content, 1)
        path.write_text(new)
        return ToolResult(ok=True, output=_agent_state(new))

    if action == "remove":
        if not match:
            return ToolResult(ok=False, output="", error="'match' required for remove")
        literal = _locate_literal(text, match)
        if literal is None:
            return ToolResult(ok=False, output="", error=f"no match for {match!r}")
        new = text.replace(literal, "", 1)
        path.write_text(new)
        return ToolResult(ok=True, output=_agent_state(new))

    return ToolResult(ok=False, output="", error=f"unknown action: {action}")


def _entries(store: MemoryStore, target: str) -> list[str]:
    path = store.user_path if target == "USER.md" else store.memory_path
    text = path.read_text() if path.exists() else ""
    return [e for e in text.split(ENTRY_DELIMITER) if e.strip()]


def _modify(store: MemoryStore, target: str, match: str,
            replacement: str | None) -> list[str]:
    entries = _entries(store, target)
    idx = fuzzy_find_unique_entry(entries, match)
    if replacement is None:
        entries.pop(idx)
    else:
        entries[idx] = replacement.strip()
    return entries


def _write(store: MemoryStore, target: str, entries: list[str]) -> None:
    path = store.user_path if target == "USER.md" else store.memory_path
    content = ENTRY_DELIMITER.join(entries) + ("\n" if entries else "")
    from alpi.memory import USER_CHAR_LIMIT, MEMORY_CHAR_LIMIT, backup_file
    limit = USER_CHAR_LIMIT if target == "USER.md" else MEMORY_CHAR_LIMIT
    if len(content) > limit:
        raise ValueError(f"{target} would be {len(content):,}/{limit:,} chars — consolidate first")
    backup_file(path)
    path.write_text(content)


TOOL = Memory
