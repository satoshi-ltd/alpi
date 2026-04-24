"""Persistent memory — USER.md and MEMORY.md with char limits."""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
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
        """Return current content of both memories (for system prompt injection)."""
        return {
            "USER.md": _read(self.user_path),
            "MEMORY.md": _read(self.memory_path),
        }

    def usage(self) -> dict[str, tuple[int, int]]:
        """Return (used_chars, limit) per file."""
        return {
            "USER.md": (len(_read(self.user_path)), USER_CHAR_LIMIT),
            "MEMORY.md": (len(_read(self.memory_path)), MEMORY_CHAR_LIMIT),
        }

    def add(self, target: str, content: str) -> None:
        """Append a new entry. Raises ValueError if over char limit or duplicate."""
        cleaned = _clean_entry(content)
        if not cleaned:
            raise ValueError("empty entry after cleanup")

        path, limit = self._resolve(target)
        with _locked(path, "a+") as f:
            f.seek(0)
            current = f.read()
            if _is_duplicate(current, cleaned):
                raise ValueError("entry already present (or very similar) — skipping duplicate")
            new_content = (current.rstrip() + ENTRY_DELIMITER + cleaned + "\n"
                           if current.strip() else cleaned + "\n")
            if len(new_content) > limit:
                raise ValueError(
                    f"Memory {target} would be {len(new_content):,}/{limit:,} chars. "
                    "Consolidate existing entries before adding."
                )
            backup_file(path)
            f.seek(0)
            f.truncate()
            f.write(new_content)

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
    needle_norm = _normalize_for_dedup(new_entry)
    if not needle_norm:
        return True
    needle_tokens = _content_tokens(new_entry)
    for entry in existing.split(ENTRY_DELIMITER):
        existing_norm = _normalize_for_dedup(entry)
        if not existing_norm:
            continue
        if (needle_norm == existing_norm
                or needle_norm in existing_norm
                or existing_norm in needle_norm):
            return True
        if needle_tokens:
            existing_tokens = _content_tokens(entry)
            if existing_tokens:
                overlap = len(needle_tokens & existing_tokens)
                # Max containment: if ≥70% of the shorter entry's content
                # tokens are in the longer one, it's a paraphrase/superset.
                smaller = min(len(needle_tokens), len(existing_tokens))
                if smaller >= 2 and overlap / smaller >= 0.7:
                    return True
    return False


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
