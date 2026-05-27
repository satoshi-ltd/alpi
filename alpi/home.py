"""HOME_DIR resolution for alpi."""

from __future__ import annotations

import os
from contextvars import ContextVar
from pathlib import Path
from typing import Optional

_ROOT = Path.home() / ".alpi"


# Active-home context for concurrent daemon turns.
_HOME_CTX: ContextVar[Optional[Path]] = ContextVar(
    "alpi_active_home", default=None,
)

# Active-session context — Engine.run_turn binds it so tools like send_message attach session_id without plumbing it through every callsite.
_SESSION_CTX: ContextVar[Optional[str]] = ContextVar(
    "alpi_active_session", default=None,
)


def set_active_home(home: Optional[Path]) -> object:
    """Bind ``home`` to the current context and return the reset token."""
    return _HOME_CTX.set(home)


def reset_active_home(token: object) -> None:
    _HOME_CTX.reset(token)


def set_active_session(session_id: Optional[str]) -> object:
    return _SESSION_CTX.set(session_id)


def reset_active_session(token: object) -> None:
    _SESSION_CTX.reset(token)


def get_active_session() -> Optional[str]:
    return _SESSION_CTX.get()


def get_home(profile: Optional[str] = None) -> Path:
    # Context binding wins; env fallback is for one-shot commands.
    active = _HOME_CTX.get()
    if active is not None:
        return active

    override = os.environ.get("ALPI_HOME")
    if override:
        return Path(override).expanduser()

    name = profile or os.environ.get("ALPI_PROFILE")
    if name and name != "default":
        return _ROOT / "profiles" / name
    return _ROOT


def home_for(name: str) -> Path:
    """Resolve a profile literally; never honour ``ALPI_HOME``."""
    if not name or name == "default":
        return _ROOT
    return _ROOT / "profiles" / name


def alpi_root() -> Path:
    """Return the alpi home root, honoring ``ALPI_HOME`` — ignores any profile selection."""
    override = os.environ.get("ALPI_HOME")
    if override:
        return Path(override).expanduser()
    return _ROOT


def read_profile_env(home: Path) -> dict[str, str]:
    """Parse ``<home>/.env`` → dict. Strips surrounding quotes. Single source for per-profile env snapshots — no global ``os.environ`` mutation."""
    out: dict[str, str] = {}
    env_path = home / ".env"
    if not env_path.exists():
        return out
    try:
        text = env_path.read_text()
    except OSError:
        return out
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k = k.strip()
        if not k:
            continue
        v = v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in ('"', "'"):
            v = v[1:-1]
        out[k] = v
    return out


def effective_profile_env(
    home: Path,
    *,
    base: dict[str, str] | None = None,
    extra: dict[str, str] | None = None,
) -> dict[str, str]:
    """Effective env map for a profile call: ``base`` ∪ profile ``.env`` ∪ ``extra`` (last wins). Use this everywhere a profile-scoped subprocess/library lookup would otherwise reach into ``os.environ`` — the daemon supervises many profiles in one process, so global env would leak secrets across them. ``base`` defaults to ``os.environ`` so process-level vars (PATH, HOME, TZ, ALPI_PLATFORM) still propagate; per-profile keys (provider API keys, gateway tokens) overlay from the profile's .env."""
    out: dict[str, str] = dict(base if base is not None else os.environ)
    out.update(read_profile_env(home))
    if extra:
        out.update(extra)
    return out


def telegram_token_owner(
    token: str,
    *,
    exclude: Path | None = None,
    root: Path | None = None,
) -> str | None:
    """Profile name that already owns this Telegram bot token, or ``None``. One-profile-per-bot is hard-required by Telegram long-polling (409 on second poller)."""
    if not token:
        return None
    base = root or alpi_root()
    candidates: list[Path] = [base]
    profiles_dir = base / "profiles"
    if profiles_dir.is_dir():
        candidates.extend(sorted(p for p in profiles_dir.iterdir() if p.is_dir()))
    target = token.strip()
    for home in candidates:
        if exclude is not None and home.resolve() == exclude.resolve():
            continue
        if read_profile_env(home).get("TELEGRAM_BOT_TOKEN", "").strip() == target:
            return profile_name(home)
    return None


def profile_name(home: Path) -> str:
    """Inverse of ``home_for``: ``~/.alpi`` → ``default``; ``~/.alpi/profiles/<n>`` → ``<n>``."""
    parts = home.parts
    if "profiles" in parts:
        i = parts.index("profiles")
        if i + 1 < len(parts):
            return parts[i + 1]
    return "default"


def find_home_by_pubkey(pubkey: str, root: Path | None = None) -> Path | None:
    if not pubkey:
        return None
    from alpi.alp import keys as keys_mod
    base = root or _ROOT
    candidates: list[Path] = [base]
    sub = base / "profiles"
    if sub.is_dir():
        candidates.extend(sorted(p for p in sub.iterdir() if p.is_dir()))
    for home in candidates:
        if not keys_mod.exists(home):
            continue
        try:
            kp = keys_mod.load(home)
        except Exception:  # noqa: BLE001
            continue
        if kp.pubkey_b64() == pubkey:
            return home
    return None


def list_profiles(root: Path | None = None) -> list[str]:
    """Return ``default`` plus each profile directory under ``<root>``."""
    base = root or _ROOT
    out = ["default"]
    sub = base / "profiles"
    if sub.exists():
        for p in sorted(sub.iterdir(), key=lambda x: x.name):
            if p.is_dir() and not p.name.startswith("."):
                out.append(p.name)
    return out


def ensure_home(home: Path) -> None:
    """Bootstrap the home directory tree on first run."""
    for sub in (
        "memories",
        "secrets",
        "sessions",
        "skills",
        "schedule/output",
        "logs",
    ):
        (home / sub).mkdir(parents=True, exist_ok=True)
    gi = home / ".gitignore"
    if not gi.exists():
        gi.write_text(
            ".env\n"
            "secrets/\n"
            "sessions/\n"
            "mentions/\n"
            "gateway/sessions/\n"
            "schedule/output/\n"
            "logs/\n"
            "cache/\n"
            "skills/**/secrets/\n"
        )


def agent_path(home: Path) -> Path:
    return home / "memories" / "AGENT.md"


def format_bytes(n: int) -> str:
    if n < 1024:
        return f"{n}B"
    if n < 1024 ** 2:
        return f"{n / 1024:.0f}KB"
    if n < 1024 ** 3:
        return f"{n / 1024 ** 2:.1f}MB"
    return f"{n / 1024 ** 3:.2f}GB"


_SIZE_CACHE: dict[Path, tuple[float, str]] = {}
_SIZE_TTL = 30.0


def profile_size_label(home_dir: Path) -> str:
    import time
    now = time.time()
    cached = _SIZE_CACHE.get(home_dir)
    if cached and (now - cached[0]) < _SIZE_TTL:
        return cached[1]
    excluded = home_dir / "profiles"
    total = 0
    try:
        for p in home_dir.rglob("*"):
            if excluded in p.parents or p == excluded:
                continue
            if p.is_file():
                try:
                    total += p.stat().st_size
                except OSError:
                    pass
    except OSError:
        return ""
    label = format_bytes(total)
    _SIZE_CACHE[home_dir] = (now, label)
    return label


def shorten_home(path: Path | str) -> str:
    s = str(path)
    home = str(Path.home())
    if s == home:
        return "~"
    if s.startswith(home + "/") or s.startswith(home + "\\"):
        return "~" + s[len(home):]
    return s
