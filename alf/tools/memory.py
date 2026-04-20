"""Memory tool — read/add/replace/remove entries in USER.md and MEMORY.md.

Writes go to ~/.alf/memories/*.md immediately. They do NOT refresh the current
session's system prompt — the snapshot there is frozen on purpose (prefix
cache). The next session will see the new memory.

Entries are delimited by the § section sign and can be multiline.
"""

from __future__ import annotations

from alf.home import get_home
from alf.memory import ENTRY_DELIMITER, MemoryStore, fuzzy_contains, fuzzy_find_unique_entry
from alf.tools.base import Tool, ToolResult


class Memory(Tool):
    name = "memory"
    description = (
        "Persist things that reduce future user steering. Three targets, "
        "pick exactly ONE per fact (never duplicate across targets):\n"
        "\n"
        "  USER.md         — stable facts about the user: name, location, "
        "role, family, hardware, long-term preferences. Would still be "
        "true with any other assistant.\n"
        "  MEMORY.md       — environment/tool notes: commands, paths, API "
        "quirks, workarounds. Would still be useful next session.\n"
        "  PERSONALITY.md  — how YOU (alf) should behave: tone, style, "
        "response length, language, identity.\n"
        "\n"
        "Actions: read | add | replace | remove.\n"
        "\n"
        "When the user gives an instruction or fact that applies beyond "
        "this turn, CALL this tool — an acknowledgement in the reply "
        "does not persist anything and is LOST at end of turn.\n"
        "\n"
        "DO NOT save:\n"
        "  • task progress, session outcomes, or diary-style logs of what "
        "was done in this turn. Use session_search for prior sessions.\n"
        "  • rephrasings of what the user just said this turn.\n"
        "  • facts that will be stale in a week.\n"
        "  • duplicates — call read first if unsure.\n"
        "\n"
        "Concrete bad calls to avoid:\n"
        "  ❌ add USER.md \"User asked for direct links\"\n"
        "  ❌ add USER.md \"Usuario pide enlaces directos\"\n"
        "  ❌ add USER.md \"User wants short answers\"  ← that's PERSONALITY\n"
        "  ❌ add USER.md + add PERSONALITY.md with the same fact (pick one)\n"
        "\n"
        "Good calls:\n"
        "  ✓ add USER.md \"Javi lives in Hua Hin.\"\n"
        "  ✓ add PERSONALITY.md \"Prefer short answers, max 2 lines.\"\n"
        "  ✓ add MEMORY.md \"The prod backend runs at 192.168.1.45.\"\n"
        "\n"
        "`replace` match must be verbatim text from a prior `read` or the "
        "frozen snapshot — never invent a match string. If unsure, use add.\n"
        "\n"
        "When in doubt, skip. Junk in memory pollutes every future prompt."
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
                "description": (
                    "USER.md → who the user is (facts that outlive this "
                    "assistant). MEMORY.md → your own notes about env/tools. "
                    "PERSONALITY.md → how YOU should reply (tone, length, "
                    "language, identity). Pick ONE, never save the same "
                    "thing in two targets."
                ),
            },
            "content": {
                "type": "string",
                "description": (
                    "Entry content (for add/replace). One fact per call, "
                    "declarative, short. No paragraphs. No headers."
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
        """Return usage + the full current contents of the file.

        Giving the agent the full current state after every mutation means it
        sees reality in its next turn — no reliance on the frozen snapshot in
        the system prompt (which went stale when we wrote to disk).
        """
        used, limit = store.usage()[target]
        pct = int(used / limit * 100) if limit else 0
        hint = " — run the consolidate-memory skill" if pct >= 80 else ""
        current = store.snapshot()[target].strip() or "(empty)"
        return (
            f"{target}: {pct}% ({used:,}/{limit:,} chars){hint}\n\n"
            f"Current contents:\n{current}"
        )


def _locate_literal(text: str, match: str) -> str | None:
    """Find a substring in `text` that fuzzy-matches `match` and return its
    exact literal slice. None if no match. Case + accent insensitive.
    """
    import unicodedata
    from alf.memory import _fold

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
    """PERSONALITY.md is free-form markdown, not § entries. Simpler ops."""
    from alf.home import personality_path
    path = personality_path(home)
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
    from alf.memory import USER_CHAR_LIMIT, MEMORY_CHAR_LIMIT, backup_file
    limit = USER_CHAR_LIMIT if target == "USER.md" else MEMORY_CHAR_LIMIT
    if len(content) > limit:
        raise ValueError(f"{target} would be {len(content):,}/{limit:,} chars — consolidate first")
    backup_file(path)
    path.write_text(content)


TOOL = Memory
