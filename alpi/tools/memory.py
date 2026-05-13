"""Memory tool — read/add/replace/remove entries in USER.md and MEMORY.md."""

from __future__ import annotations

import re

from alpi.home import get_home
from alpi.memory import (
    ENTRY_DELIMITER,
    MemoryStore,
    _clean_entry,
    _is_duplicate,
    fuzzy_contains,
    fuzzy_find_unique_entry,
    is_duplicate_stanza,
)
from alpi.tools.base import Tool, ToolResult
from alpi.tools.skill import scan_skill_body


# Memory loads into the system prompt every session — same injection vector
# as skill bodies. Reuse the skill scanner's pattern library, plus a check
# for invisible / bidi-override unicode (Trojan-Source style payloads that
# can carry hidden instructions through ``web_extract`` → memory → next-session
# system prompt).
# Zero-width / LTR-RTL marks (200B-200F), bidi overrides (202A-202E,
# the Trojan-Source vector), word joiner (2060), bidi isolates (2066-2069),
# zero-width no-break / BOM (FEFF).
_INVISIBLE_CHARS_RE = re.compile(
    "[\u200B-\u200F\u202A-\u202E\u2060\u2066-\u2069\uFEFF]"
)


def _scan_memory_content(text: str) -> list[str]:
    findings = scan_skill_body(text)
    if _INVISIBLE_CHARS_RE.search(text):
        findings.append("invisible / bidi-override unicode characters")
    return findings


def _safety_error(text: str) -> str | None:
    flags = _scan_memory_content(text)
    if not flags:
        return None
    return f"memory write blocked by safety scan: {', '.join(flags)}"


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
        "targets. The single deciding question is **who is the fact "
        "about**:\n"
        "\n"
        "  USER.md   — the USER. Stable facts about the human you're "
        "    talking to: name, location, role, employer, family, "
        "    long-term preferences and dislikes, languages they speak. "
        "    True regardless of which assistant they're using. Test: "
        "    \"would this still be true if they switched to a different "
        "    AI tool?\" If yes → USER.md.\n"
        "  MEMORY.md — the WORLD the user operates in. Project paths, "
        "    tool quirks, API workarounds, team members, internal "
        "    domain knowledge, environment specifics. NOT about the "
        "    user themselves; about what the user works on or with. "
        "    Test: \"would this make sense to a teammate of the user?\" "
        "    If yes → MEMORY.md.\n"
        "  AGENT.md  — YOU. How the assistant behaves: tone, register, "
        "    response length, output formatting, what to skip, what "
        "    voice to use. NEVER facts about the user or the world. "
        "    Test: \"is this a directive about MY behavior?\" If yes → "
        "    AGENT.md.\n"
        "\n"
        "Disambiguation: \"user prefers concise replies\" → AGENT.md "
        "(it's about the assistant's output style). \"user is Spanish\" "
        "→ USER.md (stable fact about the human). \"the repo uses "
        "pytest with xdist\" → MEMORY.md (world the user operates in).\n"
        "\n"
        "Voice: use neutral third-person \"user\" in MEMORY.md entries, "
        "never the user's name. The name lives in USER.md; hardcoding it "
        "in MEMORY.md duplicates state and breaks if the user changes "
        "names. Write \"user runs standups at 12:10\", not "
        "\"Javi runs standups at 12:10\".\n"
        "\n"
        "Language: write every entry in ENGLISH, regardless of the "
        "chat language. Memory files reload into the system prompt "
        "every turn — non-English entries bias replies forever. "
        "Translate the fact before writing.\n"
        "\n"
        "Phrasing: write facts, not instructions. \"User prefers concise "
        "replies\" ✓ — \"Always reply concisely\" ✗. \"Project uses pytest "
        "with xdist\" ✓ — \"Run tests with pytest -n 4\" ✗. Imperative "
        "memory gets re-read as a directive in later sessions and can "
        "override the user's current request or trigger repeated work. "
        "Procedures and workflows belong in skills, not memory.\n"
        "\n"
        "Actions: read | add | replace | remove | promotion_list | "
        "promotion_discard.\n"
        "\n"
        "Promotion queue (read-only / discard-only from this tool):\n"
        "Auto-compaction emits candidate facts into a queue at "
        "``<home>/memories/promotion_queue.jsonl``. Use "
        "``promotion_list`` to surface them; warnings on each candidate "
        "flag operational state, near-duplicates, and safety-scan hits. "
        "Use ``promotion_discard(id=…)`` to drop clearly-wrong ones "
        "without writing. APPLYING a candidate is a CLI-only operation "
        "(``alpi memory promote``) — the agent has no apply path, by "
        "design. If the user asks you to durably remember a fact, write "
        "it directly via ``add``; the queue is for compaction-produced "
        "candidates, not for routing user requests through.\n"
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
        "`replace` / `remove` match must be verbatim from a prior `read` "
        "or the frozen snapshot — never invent one. Do not include the "
        "`§` entry delimiter in the match; match only content inside an "
        "entry. If unsure, use `add`."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "read", "add", "replace", "remove",
                    "promotion_list", "promotion_discard",
                ],
            },
            "target": {
                "type": "string",
                "enum": ["USER.md", "MEMORY.md", "AGENT.md"],
                "description": (
                    "See tool description for target semantics. Optional for "
                    "``promotion_*`` actions; required otherwise."
                ),
            },
            "id": {
                "type": "string",
                "description": (
                    "Promotion candidate id (``promotion_discard`` only). "
                    "Get it from ``promotion_list``."
                ),
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
            "entries": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Batch ``add`` only. List of entries to append in one "
                    "call to the same target. Use this when the user gives "
                    "you several facts at once — calling ``add`` 5+ times "
                    "in one turn wastes tokens and round-trips. Each entry "
                    "is checked for cross-file duplicates independently."
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
            "confidence": {
                "type": "string",
                "enum": ["low", "normal", "high"],
                "default": "normal",
                "description": (
                    "How sure you are this fact is durable. ``normal`` is "
                    "the default: explicit user statements or things you "
                    "verified this turn. ``high``: invariants the user "
                    "stated more than once or marked as core. ``low``: "
                    "inferences you made that the user did not confirm "
                    "directly. Applies to USER.md and MEMORY.md only — "
                    "AGENT.md is persona/behaviour and never auto-expires. "
                    "Low entries auto-expire after ~30 days unless "
                    "reinforced (a second add of the same fact bumps the "
                    "counter and upgrades low → normal)."
                ),
            },
        },
        "required": ["action"],
    }

    def run(self, action: str, target: str = "", content: str = "",
            match: str = "",
            entries: list[str] | None = None,
            confidence: str = "normal",
            id: str = "") -> ToolResult:
        h = get_home()

        if action.startswith("promotion_"):
            return _handle_promotion(h, action, id)

        if not target:
            return ToolResult(ok=False, output="", error="'target' is required for this action")

        if target.upper() == "AGENT.MD":
            return _handle_agent(h, action, content, match, entries)

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
                batch = [e for e in (entries or []) if e and e.strip()]
                if not content.strip() and not batch:
                    return ToolResult(ok=False, output="", error="'content' or 'entries' required for add")
                if content.strip() and batch:
                    return ToolResult(
                        ok=False, output="",
                        error="pass either 'content' (single entry) or 'entries' (batch), not both",
                    )

                if batch:
                    return _add_memory_batch(self, store, target, batch, confidence)

                items = [content]
                added = 0
                reinforced = 0
                warnings: list[str] = []
                for item in items:
                    item = item.strip()
                    if not item:
                        continue
                    blocked = _safety_error(item)
                    if blocked is not None:
                        return ToolResult(ok=False, output="", error=blocked)
                    other = _cross_file_duplicate(store, target, item)
                    if other is not None:
                        if len(items) == 1:
                            return ToolResult(
                                ok=False, output="",
                                error=(
                                    f"looks like a near-duplicate of an entry "
                                    f"already in {other}. Use `replace` there or "
                                    f"confirm this is a genuinely distinct fact."
                                ),
                            )
                        warnings.append(f"skipped (duplicate of {other}): {item[:60]!r}")
                        continue
                    outcome = store.add(target, item, confidence=confidence)
                    if outcome == "reinforced":
                        reinforced += 1
                    else:
                        added += 1
                    warn = _operational_warning(item)
                    if warn:
                        warnings.append(warn)

                if added == 0 and reinforced == 0:
                    return ToolResult(
                        ok=False, output="",
                        error="no entries added: " + " | ".join(warnings),
                    )

                output = self._state_snapshot(store, target)
                header_parts = []
                if added:
                    header_parts.append(f"Added {added} entr{'ies' if added != 1 else 'y'}")
                if reinforced:
                    header_parts.append(
                        f"reinforced {reinforced} existing entr{'ies' if reinforced != 1 else 'y'} "
                        "(duplicate detected, counter bumped)"
                    )
                if header_parts:
                    output = f"{' · '.join(header_parts)} in {target}.\n\n{output}"
                if warnings:
                    output = f"{output}\n\n" + "\n".join(warnings)
                return ToolResult(ok=True, output=output)

            if action == "replace":
                if not match or not content:
                    return ToolResult(ok=False, output="", error="'match' and 'content' required for replace")
                blocked = _safety_error(content)
                if blocked is not None:
                    return ToolResult(ok=False, output="", error=blocked)
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


def _add_memory_batch(
    tool: Memory,
    store: MemoryStore,
    target: str,
    entries: list[str],
    confidence: str = "normal",
) -> ToolResult:
    added = 0
    reinforced = 0
    warnings: list[str] = []

    for raw in entries:
        item = _clean_entry(raw)
        if not item:
            continue
        blocked = _safety_error(item)
        if blocked is not None:
            warnings.append(f"skipped ({blocked}): {item[:60]!r}")
            continue
        other = _cross_file_duplicate(store, target, item)
        if other is not None:
            warnings.append(f"skipped (duplicate of {other}): {item[:60]!r}")
            continue
        try:
            outcome = store.add(target, item, confidence=confidence)
        except ValueError as e:
            warnings.append(f"skipped ({e}): {item[:60]!r}")
            continue
        if outcome == "reinforced":
            reinforced += 1
        else:
            added += 1
        warn = _operational_warning(item)
        if warn:
            warnings.append(warn)

    if added == 0 and reinforced == 0:
        return ToolResult(
            ok=False, output="",
            error="no entries added: " + " | ".join(warnings),
        )

    header_parts = []
    if added:
        header_parts.append(f"Added {added} entr{'ies' if added != 1 else 'y'}")
    if reinforced:
        header_parts.append(
            f"reinforced {reinforced} existing entr{'ies' if reinforced != 1 else 'y'}"
        )
    out = (
        f"{' · '.join(header_parts)} in {target}.\n\n"
        f"{tool._state_snapshot(store, target)}"
    )
    if warnings:
        out = f"{out}\n\n" + "\n".join(warnings)
    return ToolResult(ok=True, output=out)


def _handle_agent(home, action: str, content: str, match: str,
                  entries: list[str] | None = None) -> ToolResult:
    from alpi.home import agent_path
    path = agent_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = path.read_text() if path.exists() else ""

    if action == "read":
        return ToolResult(ok=True, output=f"[AGENT.md]\n{text or '(empty)'}")

    if action == "add":
        batch = [e for e in (entries or []) if e and e.strip()]
        if not content.strip() and not batch:
            return ToolResult(ok=False, output="", error="'content' or 'entries' required for add")
        if content.strip() and batch:
            return ToolResult(
                ok=False, output="",
                error="pass either 'content' or 'entries', not both",
            )
        items = batch if batch else [content]
        added = 0
        skipped: list[str] = []
        new_text = text
        for item in items:
            item = item.strip()
            if not item:
                continue
            blocked = _safety_error(item)
            if blocked is not None:
                if len(items) == 1:
                    return ToolResult(ok=False, output="", error=blocked)
                skipped.append(f"skipped ({blocked}): {item[:60]!r}")
                continue
            if is_duplicate_stanza(new_text, item):
                if len(items) == 1:
                    return ToolResult(
                        ok=False, output="",
                        error=(
                            "near-duplicate of an existing paragraph in AGENT.md. "
                            "For voice / identity changes, use `replace` with the "
                            "literal line you want to change."
                        ),
                    )
                skipped.append(f"skipped (duplicate): {item[:60]!r}")
                continue
            new_text = (
                new_text.rstrip() + "\n\n" + item + "\n"
            ) if new_text.strip() else item + "\n"
            added += 1
        if added == 0:
            return ToolResult(ok=False, output="",
                              error="no entries added; all duplicates: " + " | ".join(skipped))
        path.write_text(new_text)
        out = _agent_state(new_text)
        if added > 1:
            out = f"Added {added} paragraphs to AGENT.md.\n\n{out}"
        if skipped:
            out = f"{out}\n\n" + "\n".join(skipped)
        return ToolResult(ok=True, output=out)

    if action == "replace":
        if not match or not content:
            return ToolResult(ok=False, output="", error="'match' and 'content' required for replace")
        blocked = _safety_error(content)
        if blocked is not None:
            return ToolResult(ok=False, output="", error=blocked)
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


def _format_candidate(c, *, with_warnings: bool = True) -> str:
    import datetime as _dt
    age = _dt.datetime.fromtimestamp(c.created_at).strftime("%Y-%m-%d %H:%M")
    head = (
        f"  [{c.id}] {c.target}  confidence={c.confidence}  "
        f"source={c.source}  session={c.session_id[:8]}  ({age})"
    )
    body = f"    text: {c.text}"
    if with_warnings and c.warnings:
        body += "\n    warnings: " + "; ".join(c.warnings)
    return f"{head}\n{body}"


def _handle_promotion(home, action: str, candidate_id: str) -> ToolResult:
    """promotion_list / promotion_discard.

    The agent can ``list`` (read-only) or ``discard`` (drops without writing).
    There is **no agent-callable apply**: the human-in-the-loop gate lives at
    the CLI ``alpi memory promote`` so the agent cannot promote facts to
    durable memory on its own, regardless of how the prompt is framed.
    """
    from alpi import promotion

    if action == "promotion_list":
        pending = promotion.list_pending(home)
        if not pending:
            return ToolResult(
                ok=True,
                output=(
                    "(no pending promotion candidates)\n\n"
                    "Compaction emits candidates after it fires. Apply or "
                    "discard them with ``alpi memory promote``."
                ),
            )
        lines = [
            f"{len(pending)} pending promotion candidate(s) "
            f"(cap={promotion.MAX_PENDING}, expire after "
            f"{promotion.MAX_AGE_DAYS}d):",
            "",
        ]
        for c in pending:
            lines.append(_format_candidate(c))
            lines.append("")
        lines.append(
            "Applying a candidate is a CLI-only operation: run "
            "``alpi memory promote`` for an interactive review. From here "
            "you can drop clearly-wrong candidates with "
            "``memory(action='promotion_discard', id=…)``."
        )
        return ToolResult(ok=True, output="\n".join(lines).rstrip())

    if action == "promotion_discard":
        if not candidate_id:
            return ToolResult(ok=False, output="", error="'id' is required for promotion_discard")
        removed = promotion.discard(home, candidate_id)
        if not removed:
            return ToolResult(ok=False, output="", error=f"no pending candidate with id {candidate_id!r}")
        return ToolResult(ok=True, output=f"discarded candidate {candidate_id}")

    if action == "promotion_apply":
        return ToolResult(
            ok=False, output="",
            error=(
                "promotion_apply is not available as a tool action — the "
                "human-in-the-loop gate lives at the CLI. Run "
                "``alpi memory promote`` for interactive review and apply. "
                "From this tool you can ``promotion_list`` (read-only) or "
                "``promotion_discard(id=…)`` (drops without writing)."
            ),
        )
    return ToolResult(ok=False, output="", error=f"unknown promotion action: {action}")


def compute_promotion_warnings(home, target: str, text: str) -> list[str]:
    """Build the preview warnings shown alongside a candidate.

    Reuses the exact checks the ``memory(action="add")`` write path runs:
    operational-state heuristic, cross-file duplicate detection, and the
    safety scanner (Trojan-Source unicode, prompt-injection patterns,
    secret leakage). All non-blocking here — a real apply will re-run them
    via the standard path and reject if anything blocks.
    """
    warnings: list[str] = []
    op = _operational_warning(text)
    if op:
        warnings.append(op)

    if target in ("USER.md", "MEMORY.md"):
        try:
            store = MemoryStore(home=home)
            store.seed_defaults()
            other = _cross_file_duplicate(store, target, text)
            if other is not None:
                warnings.append(f"near-duplicate of an entry already in {other}")
        except Exception:  # noqa: BLE001
            pass

    flags = _scan_memory_content(text)
    if flags:
        warnings.append(f"safety scan: {', '.join(flags)}")

    return warnings


TOOL = Memory
