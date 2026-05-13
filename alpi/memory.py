"""Persistent memory — USER.md and MEMORY.md with char limits."""

from __future__ import annotations

import contextlib
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterator

try:
    import fcntl  # type: ignore
except ImportError:
    fcntl = None  # Windows — locking is a best-effort no-op

ENTRY_DELIMITER = "\n§\n"

USER_CHAR_LIMIT = 3000
MEMORY_CHAR_LIMIT = 5000

SEED_USER = ""
SEED_MEMORY = ""

CONFIDENCE_LEVELS = ("low", "normal", "high")
DEFAULT_CONFIDENCE = "normal"

LOW_CONFIDENCE_MAX_AGE_DAYS = 30  # AI(1.c) v0.6 calibration target, not a user knob

_META_RE = re.compile(
    r"\n?<!--\s*alpi-meta\s+(?P<kv>[^>]*?)\s*-->", re.IGNORECASE
)
_META_TOKEN = re.compile(r"(\w+)=([^\s]+)")


@dataclass
class MemoryStore:
    home: Path

    @property
    def user_path(self) -> Path:
        return self.home / "memories" / "USER.md"

    @property
    def memory_path(self) -> Path:
        return self.home / "memories" / "MEMORY.md"

    def seed_defaults(self) -> None:
        (self.home / "memories").mkdir(parents=True, exist_ok=True)
        if not self.user_path.exists():
            self.user_path.write_text(SEED_USER)
        if not self.memory_path.exists():
            self.memory_path.write_text(SEED_MEMORY)

    def snapshot(self) -> dict[str, str]:
        """Return current memories with metadata comments stripped.

        Used to inject memory into the system prompt — the LLM never
        sees ``<!-- alpi-meta … -->`` markers.
        """
        return {
            "USER.md": strip_meta(_read(self.user_path)),
            "MEMORY.md": strip_meta(_read(self.memory_path)),
        }

    def usage(self) -> dict[str, tuple[int, int]]:
        """Return (used_chars, limit) per file. Counts what the LLM
        actually sees: metadata comments are stripped first so the
        budget reflects system-prompt impact, not on-disk bytes."""
        return {
            "USER.md": (len(strip_meta(_read(self.user_path))), USER_CHAR_LIMIT),
            "MEMORY.md": (len(strip_meta(_read(self.memory_path))), MEMORY_CHAR_LIMIT),
        }

    def add(
        self,
        target: str,
        content: str,
        confidence: str = DEFAULT_CONFIDENCE,
    ) -> str:
        """Append a new entry and return its action: 'added' or 'reinforced'.

        Near-duplicates reinforce the matching existing entry (bumping
        its counter and upgrading low→normal) instead of raising.
        Raises ValueError only for empty content, over-limit writes, or
        unknown target.
        """
        cleaned = _clean_entry(content)
        if not cleaned:
            raise ValueError("empty entry after cleanup")
        if confidence not in CONFIDENCE_LEVELS:
            raise ValueError(
                f"confidence must be one of {CONFIDENCE_LEVELS}, got {confidence!r}"
            )

        path, limit = self._resolve(target)
        with _locked(path, "a+") as f:
            f.seek(0)
            current = f.read()
            dup_idx = _find_duplicate_index(current, cleaned)
            if dup_idx is not None:
                rewritten = _reinforce_at(current, dup_idx)
                if rewritten != current:
                    backup_file(path)
                    f.seek(0)
                    f.truncate()
                    f.write(rewritten)
                return "reinforced"
            meta = _build_meta(confidence=confidence, captured=_today(), reinforced=0)
            entry_block = cleaned + meta
            new_content = (
                current.rstrip() + ENTRY_DELIMITER + entry_block + "\n"
                if current.strip()
                else entry_block + "\n"
            )
            visible = len(strip_meta(new_content))
            if visible > limit:
                raise ValueError(
                    f"Memory {target} would be {visible:,}/{limit:,} chars. "
                    "Consolidate existing entries before adding."
                )
            backup_file(path)
            f.seek(0)
            f.truncate()
            f.write(new_content)
            return "added"

    def prune_low_confidence(self, max_age_days: int, today: date | None = None) -> int:
        """Drop low-confidence entries older than ``max_age_days`` with zero
        reinforcements. Returns the number of entries removed across
        USER.md + MEMORY.md. ``max_age_days <= 0`` disables the prune.
        """
        if max_age_days <= 0:
            return 0
        today = today or _today()
        removed = 0
        for path in (self.user_path, self.memory_path):
            if not path.exists():
                continue
            with _locked(path, "r+") as f:
                content = f.read()
                if not content.strip():
                    continue
                kept_entries: list[str] = []
                dropped = 0
                for entry in content.split(ENTRY_DELIMITER):
                    if _should_prune(entry, today, max_age_days):
                        dropped += 1
                        continue
                    kept_entries.append(entry)
                if dropped == 0:
                    continue
                backup_file(path)
                new_text = ENTRY_DELIMITER.join(kept_entries).strip()
                if new_text:
                    new_text += "\n"
                f.seek(0)
                f.truncate()
                f.write(new_text)
                removed += dropped
        return removed

    def _resolve(self, target: str) -> tuple[Path, int]:
        key = target.upper()  # accept variants; the canonical form is uppercase
        if key == "USER.MD":
            return self.user_path, USER_CHAR_LIMIT
        if key == "MEMORY.MD":
            return self.memory_path, MEMORY_CHAR_LIMIT
        raise ValueError(f"Unknown memory target: {target!r}")


def _read(path: Path) -> str:
    return path.read_text() if path.exists() else ""


def _clean_entry(content: str) -> str:
    lines = []
    for raw in (content or "").splitlines():
        stripped = raw.strip()
        if not stripped:
            continue
        # Skip pure markdown headers and seed template lines.
        if stripped.startswith("#"):
            continue
        if stripped.startswith("(alpi will"):
            continue
        if stripped == "§":
            continue
        lines.append(stripped)
    return "\n".join(lines).strip()


def is_duplicate_stanza(existing_text: str, new_stanza: str) -> bool:
    """Same fold + Jaccard dedup as ``_is_duplicate`` but splitting the
    existing text on blank lines instead of the ``§`` delimiter. Used for
    AGENT.md, which is free-form markdown (paragraphs / sections) rather
    than a delimited entry list."""
    stanzas = [s for s in existing_text.split("\n\n") if s.strip()]
    joined = ENTRY_DELIMITER.join(stanzas)
    return _is_duplicate(joined, new_stanza)


def _is_duplicate(existing: str, new_entry: str) -> bool:
    return _find_duplicate_index(existing, new_entry) is not None


def _find_duplicate_index(existing: str, new_entry: str) -> int | None:
    needle_norm = _normalize_for_dedup(strip_meta(new_entry))
    if not needle_norm:
        return 0
    needle_tokens = _content_tokens(strip_meta(new_entry))
    for i, entry in enumerate(existing.split(ENTRY_DELIMITER)):
        body = strip_meta(entry)
        existing_norm = _normalize_for_dedup(body)
        if not existing_norm:
            continue
        if (needle_norm == existing_norm
                or needle_norm in existing_norm
                or existing_norm in needle_norm):
            return i
        if needle_tokens:
            existing_tokens = _content_tokens(body)
            if existing_tokens:
                overlap = len(needle_tokens & existing_tokens)
                smaller = min(len(needle_tokens), len(existing_tokens))
                if smaller >= 2 and overlap / smaller >= 0.7:
                    return i
    return None


# Minimal stopword set — Spanish + English function words. Kept deliberately
# small so we only filter noise, not legitimate content words.
_STOPWORDS = frozenset({
    "a", "al", "an", "and", "de", "del", "e", "el", "en", "es", "i", "in",
    "is", "la", "las", "lo", "los", "me", "mi", "my", "o", "of", "on", "or",
    "que", "se", "si", "su", "te", "the", "to", "un", "una", "unas", "unos",
    "y", "yo",
})


def _content_tokens(s: str) -> set[str]:
    import re
    folded = _fold(s)
    words = re.findall(r"[a-z0-9]+", folded)
    return {w for w in words if len(w) >= 2 and w not in _STOPWORDS}


def _normalize_for_dedup(s: str) -> str:
    return _fold(s.strip().rstrip(".!?,;: "))


def _fold(s: str) -> str:
    import unicodedata
    normalized = unicodedata.normalize("NFD", s)
    return "".join(c for c in normalized if unicodedata.category(c) != "Mn").casefold()


def fuzzy_contains(haystack: str, needle: str) -> bool:
    """Case + accent insensitive substring match."""
    return _fold(needle) in _fold(haystack)


def fuzzy_find_unique_entry(entries: list[str], match: str) -> int:
    """Return the single index in `entries` that contains `match` (fuzzy), or raise."""
    hits = [i for i, e in enumerate(entries) if fuzzy_contains(e, match)]
    if not hits:
        hint = ""
        if "§" in match:
            hint = (
                " — note: `§` is the entry delimiter, not content. "
                "Strip it from your match string."
            )
        raise ValueError(f"no entry matches {match!r}{hint}")
    if len(hits) > 1:
        raise ValueError(f"{len(hits)} entries match {match!r}; use a more unique substring")
    return hits[0]


def backup_file(path: Path) -> Path | None:
    """Snapshot ``path`` to ``path.bak`` before a mutating write."""
    if not path.exists():
        return None
    bak = path.with_suffix(path.suffix + ".bak")
    bak.write_bytes(path.read_bytes())
    return bak


@contextlib.contextmanager
def _locked(path: Path, mode: str) -> Iterator:
    path.parent.mkdir(parents=True, exist_ok=True)
    f = open(path, mode)
    try:
        if fcntl is not None:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        yield f
    finally:
        if fcntl is not None:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        f.close()


def strip_meta(text: str) -> str:
    """Remove every ``<!-- alpi-meta … -->`` marker from ``text``.

    Used in two paths: snapshot() before injecting into the system
    prompt, and dedup comparisons (so meta on one side doesn't fake
    a content difference).
    """
    return _META_RE.sub("", text)


def parse_meta(entry: str) -> dict[str, str]:
    """Return the parsed key/value pairs from the last alpi-meta marker
    in ``entry``. Empty dict when none is present."""
    matches = list(_META_RE.finditer(entry))
    if not matches:
        return {}
    return dict(_META_TOKEN.findall(matches[-1].group("kv")))


def _build_meta(*, confidence: str, captured: date, reinforced: int) -> str:
    return (
        f"\n<!-- alpi-meta conf={confidence} "
        f"captured={captured.isoformat()} reinforced={reinforced} -->"
    )


def _reinforce_at(text: str, idx: int) -> str:
    """Return ``text`` with the entry at index ``idx`` bumped: reinforced+1,
    and confidence upgraded low→normal once reinforced ≥ 2."""
    entries = text.split(ENTRY_DELIMITER)
    if idx < 0 or idx >= len(entries):
        return text
    entries[idx] = _bump_entry(entries[idx])
    return ENTRY_DELIMITER.join(entries)


def _bump_entry(entry: str) -> str:
    meta = parse_meta(entry)
    body = strip_meta(entry).rstrip("\n")
    reinforced = int(meta.get("reinforced", "0")) + 1
    conf = meta.get("conf", DEFAULT_CONFIDENCE)
    if conf == "low" and reinforced >= 2:
        conf = "normal"
    captured_raw = meta.get("captured")
    captured = _parse_date(captured_raw) if captured_raw else _today()
    return body + _build_meta(
        confidence=conf, captured=captured, reinforced=reinforced
    )


def _should_prune(entry: str, today: date, max_age_days: int) -> bool:
    meta = parse_meta(entry)
    if not meta:
        return False  # legacy entries without meta never auto-expire
    if meta.get("conf") != "low":
        return False
    if int(meta.get("reinforced", "0")) > 0:
        return False
    captured_raw = meta.get("captured")
    if not captured_raw:
        return False
    captured = _parse_date(captured_raw)
    if captured is None:
        return False
    return (today - captured).days >= max_age_days


def _today() -> date:
    return datetime.now(timezone.utc).date()


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None
