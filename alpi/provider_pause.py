from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

log = logging.getLogger("alpi.provider_pause")

ACCOUNT_CODES = frozenset({"insufficient_credit", "auth", "model_unavailable"})
TRANSPORT_CODES = frozenset({"provider_unavailable", "timeout"})
OPEN_AFTER = 2
ACCOUNT_BASE_S = 15 * 60.0
ACCOUNT_MAX_S = 4 * 3600.0
TRANSPORT_BASE_S = 5 * 60.0
TRANSPORT_MAX_S = 3600.0
# A probe that never reports (killed child, error without a provider code) frees the slot after this long.
PROBE_TTL_S = 900.0


@dataclass
class PauseState:
    code: str = ""
    failures: int = 0
    until: float = 0.0
    window_s: float = 0.0
    opened_at: float = 0.0
    # A lapsed window lets exactly one probe through; the others stay paused until that probe reports.
    probing: bool = False
    probing_since: float = 0.0
    announced: set[str] = field(default_factory=set)

    @property
    def open(self) -> bool:
        return self.until > 0.0


_states: dict[str, PauseState] = {}
_lock = threading.Lock()
# Only the daemon owns scheduler and poller state; a TUI or CLI engine must not file "jobs paused" alerts from its own memory.
_active = False


def activate() -> None:
    global _active
    _active = True


def active() -> bool:
    return _active


def _kind(code: str) -> str:
    if code in ACCOUNT_CODES:
        return "account"
    if code in TRANSPORT_CODES:
        return "transport"
    return ""


def _window(kind: str, previous: float) -> float:
    base, cap = (ACCOUNT_BASE_S, ACCOUNT_MAX_S) if kind == "account" else (TRANSPORT_BASE_S, TRANSPORT_MAX_S)
    return base if previous <= 0 else min(cap, previous * 2)


def record_failure(profile: str, code: str, *, now: float | None = None) -> PauseState | None:
    """Count a provider failure; returns the state when this call opened (or re-opened) the pause."""
    kind = _kind(code)
    if not kind or not _active:
        return None
    now = time.time() if now is None else now
    with _lock:
        state = _states.setdefault(profile, PauseState())
        if state.code and _kind(state.code) != kind and not state.open:
            state.failures = 0
            state.window_s = 0.0
        state.code = code
        state.failures += 1
        state.probing = False
        if state.open and state.until > now:
            return None
        if state.failures < OPEN_AFTER:
            return None
        first_open = not state.open
        state.window_s = _window(kind, state.window_s)
        state.until = now + state.window_s
        if first_open:
            state.opened_at = now
        state.announced = set()
        log.warning(
            "profile %s: provider paused for %ds after %d failures (%s)",
            profile, int(state.window_s), state.failures, code,
        )
        return state if first_open else None


def record_success(profile: str) -> PauseState | None:
    """Clear the pause; returns the state that was open, for the caller to announce the recovery."""
    if not _active:
        return None
    with _lock:
        state = _states.pop(profile, None)
    if state is None or not state.open:
        return None
    log.info("profile %s: provider recovered (%s)", profile, state.code)
    return state


def paused(profile: str, *, now: float | None = None) -> PauseState | None:
    """The open pause, or None when the profile may call the provider; a lapsed window lets one attempt through."""
    now = time.time() if now is None else now
    with _lock:
        state = _states.get(profile)
        if state is None or not state.open:
            return None
        if state.until <= now:
            if state.probing and now - state.probing_since < PROBE_TTL_S:
                return state
            state.probing = True
            state.probing_since = now
            return None
        return state


def release_probe(profile: str) -> None:
    """A probe ended without a provider verdict (timeout, kill, unrelated error): let the next caller probe."""
    with _lock:
        state = _states.get(profile)
        if state is not None:
            state.probing = False


def _peek(profile: str) -> PauseState | None:
    with _lock:
        state = _states.get(profile)
        return state if state is not None and state.open else None


def describe(profile: str, *, now: float | None = None) -> dict[str, Any] | None:
    """Read-only view for status surfaces: never takes the probe slot."""
    state = _peek(profile)
    if state is None:
        return None
    return {
        "code": state.code,
        "since": state.opened_at,
        "until": state.until,
        "failures": state.failures,
        "probing": state.probing,
    }


def announce_once(profile: str, key: str) -> bool:
    """True the first time ``key`` is announced for the current pause; keeps per-tick skips to one log line."""
    with _lock:
        state = _states.get(profile)
        if state is None or not state.open or key in state.announced:
            return False
        state.announced.add(key)
        return True


def reset(profile: str | None = None) -> None:
    global _active
    with _lock:
        if profile is None:
            _states.clear()
            _active = False
        else:
            _states.pop(profile, None)


def notify_opened(home: Path, profile: str, state: PauseState) -> None:
    from alpi import llm_errors
    minutes = max(1, int(round(state.window_s / 60)))
    message = llm_errors.MESSAGES.get(state.code, llm_errors.MESSAGES["unknown"])
    body = (
        f"{message} Scheduled jobs and workgroup turns of this profile are paused for "
        f"{minutes} minutes after {state.failures} failures in a row; the pause doubles while "
        "the provider keeps failing and lifts on the first successful call. Chat is not blocked."
    )
    _file_alert(home, profile, title=f"{profile}: model provider paused", body=body, code=state.code)


def notify_closed(home: Path, profile: str, state: PauseState) -> None:
    minutes = max(1, int(round((time.time() - state.opened_at) / 60)))
    body = f"The model provider answered again after {minutes} minutes; scheduled jobs and workgroup turns resume."
    _file_alert(home, profile, title=f"{profile}: model provider recovered", body=body, code=state.code, type="info")


def _file_alert(home: Path, profile: str, *, title: str, body: str, code: str, type: str = "error") -> None:
    try:
        from alpi import outputs as outputs_mod
        from alpi.host import events as host_events
        host_events.ensure_history_loaded()
        output = outputs_mod.append(
            home, profile=profile, body=body, type=type, title=title, delivered_to=[],
        )
        output_id = str(output["id"])
        payload = {
            "profile": profile,
            "job_id": "",
            "title": title,
            "kind": "provider",
            "message": body,
            "reply": "",
            "delivered_to": "",
            "silent": False,
            "body": body,
            "code": code,
            "output_id": output_id,
            "deep_link": f"/outputs/{profile}/{output_id}",
        }
        host_events.emit("schedule.failed" if type == "error" else "schedule.done", payload)
        host_events.emit("output.created", {"profile": profile, "id": output_id, "type": type})
    except Exception:  # noqa: BLE001
        log.exception("profile %s: cannot file the provider pause alert", profile)


__all__ = [
    "ACCOUNT_CODES",
    "OPEN_AFTER",
    "PauseState",
    "TRANSPORT_CODES",
    "announce_once",
    "describe",
    "notify_closed",
    "notify_opened",
    "paused",
    "record_failure",
    "record_success",
    "release_probe",
    "reset",
]
