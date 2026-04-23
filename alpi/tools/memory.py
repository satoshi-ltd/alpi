"""Memory tool — read/add/replace/remove entries in USER.md and MEMORY.md."""

from __future__ import annotations

from alpi.home import get_home
from alpi.memory import ENTRY_DELIMITER, MemoryStore, fuzzy_contains, fuzzy_find_unique_entry
from alpi.tools.base import Tool, ToolResult


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
        "  USER.md         — stable facts about the user (name, location, "
        "role, long-term preferences). True regardless of assistant.\n"
        "  MEMORY.md       — your notes about env/tools (paths, commands, "
        "API quirks, workarounds).\n"
        "  PERSONALITY.md  — how YOU behave (tone, style, length, language, "
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
        "Skip: session progress, restatements of the current turn, facts "
        "stale within a week, duplicates (`read` first if unsure).\n"
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
                "enum": ["USER.md", "MEMORY.md", "PERSONALITY.md"],
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

        # PERSONALITY.md is a free-form file — handle separately.
        if target.upper() == "PERSONALITY.MD":
            return _handle_personality(h, action, content, match)

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
                store.add(target, content)
                return ToolResult(ok=True, output=self._state_snapshot(store, target))

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
        hint = " — run the consolidate-memory skill" if pct >= 80 else ""
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


def _personality_state(text: str) -> str:
    body = text.strip() or "(empty)"
    return f"PERSONALITY.md: {len(text):,} chars\n\nCurrent contents:\n{body}"


def _handle_personality(home, action: str, content: str, match: str) -> ToolResult:
    from alpi.home import personality_path
    path = personality_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = path.read_text() if path.exists() else ""

    if action == "read":
        return ToolResult(ok=True, output=f"[PERSONALITY.md]\n{text or '(empty)'}")

    if action == "add":
        if not content.strip():
            return ToolResult(ok=False, output="", error="'content' required for add")
        if content.strip() in text:
            return ToolResult(ok=False, output="", error="instruction already present")
        new = (text.rstrip() + "\n\n" + content.strip() + "\n") if text.strip() else content.strip() + "\n"
        path.write_text(new)
        return ToolResult(ok=True, output=_personality_state(new))

    if action == "replace":
        if not match or not content:
            return ToolResult(ok=False, output="", error="'match' and 'content' required for replace")
        literal = _locate_literal(text, match)
        if literal is None:
            return ToolResult(ok=False, output="", error=f"no match for {match!r}")
        new = text.replace(literal, content, 1)
        path.write_text(new)
        return ToolResult(ok=True, output=_personality_state(new))

    if action == "remove":
        if not match:
            return ToolResult(ok=False, output="", error="'match' required for remove")
        literal = _locate_literal(text, match)
        if literal is None:
            return ToolResult(ok=False, output="", error=f"no match for {match!r}")
        new = text.replace(literal, "", 1)
        path.write_text(new)
        return ToolResult(ok=True, output=_personality_state(new))

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
