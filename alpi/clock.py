"""Date/time grounding for the LLM: cache-stable timezone in the system prompt, fresh `# NOW` block riding each user turn's host-context suffix (CL.4)."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

_FALLBACK_TZ = "UTC"


def user_timezone() -> str:
    """Resolve IANA timezone name. ``$TZ`` wins; else system tzname; else UTC."""
    candidates: list[str] = []
    env_tz = (os.environ.get("TZ") or "").strip()
    if env_tz:
        candidates.append(env_tz)
    try:
        # /etc/localtime symlink resolution — most accurate on macOS/Linux.
        from pathlib import Path
        link = Path("/etc/localtime")
        if link.is_symlink():
            target = os.readlink(link)
            marker = "/zoneinfo/"
            if marker in target:
                candidates.append(target.split(marker, 1)[1])
    except OSError:
        pass
    try:
        from time import tzname
        candidates.extend(t for t in (tzname or ()) if t)
    except Exception:  # noqa: BLE001
        pass
    for name in candidates:
        try:
            ZoneInfo(name)
            return name
        except (ZoneInfoNotFoundError, ValueError):
            continue
    return _FALLBACK_TZ


def _resolve_zone(tz_name: Optional[str]) -> tuple[ZoneInfo, str]:
    name = tz_name or user_timezone()
    try:
        return ZoneInfo(name), name
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo(_FALLBACK_TZ), _FALLBACK_TZ


def now_block(
    tz_name: Optional[str] = None,
    *,
    now: Optional[datetime] = None,
) -> str:
    """Fresh weekday/date/time/UTC block; the engine appends it to the user turn's host-context suffix so history stays append-only and prompt caches stay valid."""
    zi, tz = _resolve_zone(tz_name)
    if now is None:
        local = datetime.now(zi)
    else:
        # Caller passed an aware datetime: re-anchor to the user TZ for display.
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        local = now.astimezone(zi)
    utc = local.astimezone(timezone.utc)
    return (
        "# NOW\n"
        f"- Local: {local.strftime('%A, %Y-%m-%d %H:%M')} ({tz})\n"
        f"- UTC:   {utc.strftime('%Y-%m-%dT%H:%MZ')}"
    )


def system_time_section(tz_name: Optional[str] = None) -> str:
    """Cache-stable section for the system prompt — only timezone + rule."""
    _, tz = _resolve_zone(tz_name)
    return (
        "# DATE & TIME\n"
        f"- Timezone: {tz}\n"
        "- For the current date, time, or day of week, read the `# NOW` "
        "system block that is injected before every user turn. Do NOT "
        "guess from training data."
    )
