"""Command approval — classify terminal calls by severity, gate caution ones."""

from __future__ import annotations

import fnmatch
import re
import threading
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable, Optional


class Severity(str, Enum):
    SAFE = "safe"
    CAUTION = "caution"
    DANGEROUS = "dangerous"


@dataclass
class Pattern:
    desc: str
    regex: re.Pattern
    severity: Severity


@dataclass
class Decision:
    allowed: bool
    severity: Severity = Severity.SAFE
    pattern: str = ""
    reason: str = ""


_PATTERNS: list[Pattern] = [
    Pattern(
        "recursive rm on sensitive path",
        re.compile(r"\brm\s+-[a-zA-Z]*[rR][a-zA-Z]*\s+(?:/\s*$|/[^ /]|~|\$HOME)", re.I),
        Severity.DANGEROUS,
    ),
    Pattern(
        "recursive rm",
        re.compile(r"\brm\s+-[a-zA-Z]*[rR][a-zA-Z]*\b", re.I),
        Severity.CAUTION,
    ),
    Pattern(
        "chmod 777 / a+w",
        re.compile(r"\bchmod\b.*\b(?:777|a\+w)", re.I),
        Severity.CAUTION,
    ),
    Pattern(
        "recursive chown outside workspace",
        re.compile(r"\bchown\s+-R\s+[^ ]+\s+(?:/|~|\$HOME)", re.I),
        Severity.DANGEROUS,
    ),
    Pattern(
        "mkfs",
        re.compile(r"\bmkfs(?:\.\w+)?\b", re.I),
        Severity.DANGEROUS,
    ),
    Pattern(
        "dd to block device",
        re.compile(r"\bdd\b[^|;&]*\bof=/dev/", re.I),
        Severity.DANGEROUS,
    ),
    Pattern(
        "pipe-to-interpreter",
        re.compile(
            r"\b(?:curl|wget|fetch)\b[^|]*\|\s*(?:sh|bash|zsh|python|python3|perl|ruby|node)\b",
            re.I,
        ),
        Severity.DANGEROUS,
    ),
    Pattern(
        "fork bomb",
        re.compile(r":\s*\(\s*\)\s*\{\s*:\s*\|\s*:&\s*}\s*;\s*:", re.I),
        Severity.DANGEROUS,
    ),
    Pattern(
        "write to system directory",
        re.compile(r"(?:>+|tee)\s+/(?:etc|var|usr|boot|sys|proc)/", re.I),
        Severity.DANGEROUS,
    ),
    Pattern(
        "read ssh private key",
        re.compile(
            r"(?:cat|head|tail|less|more|cp|mv|scp|rsync)\s+[^ ]*(?:\.ssh/id_|\.pem\b|id_rsa\b|id_ed25519\b)",
            re.I,
        ),
        Severity.DANGEROUS,
    ),
    Pattern(
        "sql drop / truncate",
        re.compile(r"\b(?:DROP|TRUNCATE)\s+(?:TABLE|DATABASE|SCHEMA)\b", re.I),
        Severity.CAUTION,
    ),
    Pattern(
        "git force-push",
        re.compile(r"\bgit\s+push\b.*--force\b", re.I),
        Severity.CAUTION,
    ),
    Pattern(
        "git hard reset",
        re.compile(r"\bgit\s+reset\s+--hard\b", re.I),
        Severity.CAUTION,
    ),
    Pattern(
        "sudo",
        re.compile(r"\bsudo\b", re.I),
        Severity.CAUTION,
    ),
    Pattern(
        "process kill -9",
        re.compile(r"\bkill(?:all)?\s+-9\b", re.I),
        Severity.CAUTION,
    ),
]


_session_allowlist: set[str] = set()
_lock = threading.Lock()

PromptChoice = str  # "once" | "session" | "always" | "deny"
# ``cwd`` is the *effective* working directory the command will run in (already resolved through ``terminal._default_cwd()``). Callbacks that want to display it to the user can collapse ``$HOME`` to ``~`` themselves.
PromptFn = Callable[[str, str, Severity, Optional[str]], PromptChoice]

_prompt_callback: Optional[PromptFn] = None


def set_prompt_callback(fn: Optional[PromptFn]) -> None:
    global _prompt_callback
    _prompt_callback = fn


def clear_session_allowlist() -> None:
    with _lock:
        _session_allowlist.clear()


def _persistent_allowlist() -> list[str]:
    import yaml
    from alpi.home import get_home
    try:
        p = get_home() / "config.yaml"
        if not p.exists():
            return []
        data = yaml.safe_load(p.read_text()) or {}
        term = ((data.get("tools") or {}).get("terminal") or {})
        approval = (term.get("approval") or {})
        return list(approval.get("allowlist") or [])
    except Exception:  # noqa: BLE001
        return []


def _persist_always(pattern_desc: str) -> None:
    import yaml
    from alpi.home import get_home
    p = get_home() / "config.yaml"
    try:
        data = yaml.safe_load(p.read_text()) if p.exists() else {}
    except Exception:  # noqa: BLE001
        data = {}
    if not isinstance(data, dict):
        data = {}
    tools = data.setdefault("tools", {}) if isinstance(data.get("tools", {}), dict) else data.setdefault("tools", {})
    terminal = tools.setdefault("terminal", {}) if isinstance(tools.get("terminal", {}), dict) else tools.setdefault("terminal", {})
    approval = terminal.setdefault("approval", {}) if isinstance(terminal.get("approval", {}), dict) else terminal.setdefault("approval", {})
    allow = approval.setdefault("allowlist", []) if isinstance(approval.get("allowlist", []), list) else approval.setdefault("allowlist", [])
    if pattern_desc not in allow:
        allow.append(pattern_desc)
    p.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True))


def classify(cmd: str) -> tuple[Severity, str]:
    """Return ``(worst_severity, desc_of_that_match)``.

    Scans every pattern: if any matches with ``DANGEROUS``, that one wins
    immediately (the dangerous desc is what the gate must surface). Else
    the first ``CAUTION`` match wins. This matters for compound commands
    like ``rm -rf build && mkfs.ext4 /dev/sda`` where an earlier caution
    pattern could otherwise hide a later dangerous one and let an
    ``allowlist`` desc-bypass approve the whole line.
    """
    if not cmd:
        return Severity.SAFE, ""
    caution_match: tuple[Severity, str] | None = None
    for p in _PATTERNS:
        if not p.regex.search(cmd):
            continue
        if p.severity == Severity.DANGEROUS:
            return p.severity, p.desc
        if caution_match is None:
            caution_match = (p.severity, p.desc)
    return caution_match if caution_match else (Severity.SAFE, "")


_PATTERN_DESCS = frozenset(p.desc for p in _PATTERNS)

# A command that chains via &&, ||, ;, |, newline, backtick, or $( subshell
# is considered "compound" and is not eligible for glob bypass — the glob
# would match the head while a later segment hides destructive operations.
# Pattern-desc (category) bypass still applies, because the regex
# classifier already picked the worst-severity segment.
_COMPOUND_OP_RE = re.compile(
    r"&&|\|\||;|\n|`|\$\(|(?<!\|)\|(?!\|)"
)


def _is_compound(cmd: str) -> bool:
    return bool(_COMPOUND_OP_RE.search(cmd))


def _allowlist_match(cmd: str, allowlist: list[str], desc: str) -> tuple[str, str] | None:
    """Return ``(entry, kind)`` if ``cmd`` is allowed by any entry; else ``None``.

    Two entry shapes share one config key:
      - **Pattern-desc** (legacy): exact match against a known pattern's
        ``desc`` (e.g. ``"recursive rm"``) — allows every command of that
        severity-category. Kind = ``"category"``.
      - **Command glob** (CH.2): any other string is treated as an
        ``fnmatch`` pattern matched against the literal command
        (whitespace-trimmed). Kind = ``"glob"``. Examples:
        ``"sudo apt update"`` (exact), ``"sudo apt *"`` (wildcard),
        ``"git push --force origin my-branch"`` (exact per-branch).
        Globs never override ``DANGEROUS`` (caller short-circuits) and
        never apply to **compound** commands (``&&``, ``||``, ``;``, ``|``,
        newline, backtick, ``$( … )``) — otherwise ``"sudo apt *"`` would
        also approve ``sudo apt update && rm -rf build``.
    """
    needle = cmd.strip()
    compound = _is_compound(needle)
    for entry in allowlist:
        if not entry:
            continue
        if entry in _PATTERN_DESCS:
            if entry == desc:
                return entry, "category"
            continue
        if compound:
            continue
        if fnmatch.fnmatchcase(needle, entry):
            return entry, "glob"
    return None


def _log_decision(cmd: str, decision: Decision) -> None:
    """Append one line per non-SAFE decision to the approval audit log."""
    try:
        from alpi._log import get_subsystem_logger
        from alpi.home import get_home
        logger = get_subsystem_logger(get_home(), "approval")
        verdict = "ALLOW" if decision.allowed else "DENY"
        # Truncate the command — audit, not forensics; full text lives in the session.
        preview = cmd if len(cmd) <= 160 else cmd[:157] + "..."
        logger.info(
            "%s severity=%s pattern=%r reason=%r cmd=%r",
            verdict, decision.severity.value, decision.pattern,
            decision.reason, preview,
        )
    except Exception:  # noqa: BLE001
        pass


def check(cmd: str, cwd: str | None = None) -> Decision:
    decision = _check_inner(cmd, cwd=cwd)
    if decision.severity != Severity.SAFE:
        _log_decision(cmd, decision)
    return decision


def _check_inner(cmd: str, cwd: str | None = None) -> Decision:
    severity, desc = classify(cmd)
    if severity == Severity.SAFE:
        return Decision(allowed=True, severity=severity)

    if severity == Severity.DANGEROUS:
        return Decision(
            allowed=False, severity=severity, pattern=desc,
            reason=f"dangerous pattern: {desc}",
        )

    with _lock:
        if desc in _session_allowlist:
            return Decision(
                allowed=True, severity=severity, pattern=desc,
                reason="session allowlist",
            )
    match = _allowlist_match(cmd, _persistent_allowlist(), desc)
    if match is not None:
        entry, kind = match
        reason = (
            "config allowlist"
            if kind == "category"
            else f"config allowlist (glob: {entry!r})"
        )
        return Decision(
            allowed=True, severity=severity, pattern=desc,
            reason=reason,
        )

    fn = _prompt_callback
    if fn is None:
        return Decision(
            allowed=False, severity=severity, pattern=desc,
            reason=(
                f"caution pattern: {desc} — no interactive approver in "
                f"this surface. Rerun from TUI to approve, or add {desc!r} "
                f"to tools.terminal.approval.allowlist in config.yaml."
            ),
        )

    try:
        choice = (fn(cmd, desc, severity, cwd) or "deny").lower()
    except Exception as e:  # noqa: BLE001
        return Decision(
            allowed=False, severity=severity, pattern=desc,
            reason=f"approval prompt crashed: {e}",
        )

    if choice == "deny":
        return Decision(
            allowed=False, severity=severity, pattern=desc,
            reason=(
                "user rejected this command. Do not retry, do not "
                "prompt them to reconfirm — just move on or tell them "
                "it was denied."
            ),
        )
    if choice == "session":
        with _lock:
            _session_allowlist.add(desc)
    elif choice == "always":
        try:
            _persist_always(desc)
        except Exception as e:  # noqa: BLE001
            return Decision(
                allowed=False, severity=severity, pattern=desc,
                reason=f"could not persist allowlist: {e}",
            )
    return Decision(
        allowed=True, severity=severity, pattern=desc,
        reason=f"user approved ({choice})",
    )
