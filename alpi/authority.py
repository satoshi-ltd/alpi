from __future__ import annotations

import json
import os
from collections.abc import Iterable, Iterator, Mapping
from contextlib import ExitStack, contextmanager
from typing import Any

ENV = "ALPI_WORKGROUP_AUTHORITY"
_FENCES = frozenset({"member", "peer", "allow"})
_MAX_ALLOW = 256
_MAX_NAME = 128
_FAIL_CLOSED: dict[str, Any] = {"fence": "peer"}


def current() -> dict[str, Any] | None:
    from alpi.host.connection_context import current as connection
    from alpi.tools import _policy
    allowed = _policy.allowed()
    if _policy.fences_private_areas():
        fence = "peer"
    elif connection().role != "admin":
        fence = "member"
    elif allowed is not None:
        return {"fence": "allow", "allow": sorted(allowed)}
    else:
        return from_environ()
    return {"fence": fence} if allowed is None else {"fence": fence, "allow": sorted(allowed)}


def _names(raw: object) -> list[str] | None:
    if not isinstance(raw, list):
        return None
    names = sorted({a.strip() for a in raw if isinstance(a, str) and 0 < len(a.strip()) <= _MAX_NAME})
    return names[:_MAX_ALLOW]


def sanitize(raw: object) -> dict[str, Any]:
    if not isinstance(raw, dict) or raw.get("fence") not in _FENCES:
        return dict(_FAIL_CLOSED)
    fence = raw["fence"]
    if fence == "allow" or "allow" in raw:
        names = _names(raw.get("allow"))
        if names is None:
            return {"fence": "peer", "allow": []} if fence != "allow" else dict(_FAIL_CLOSED)
        return {"fence": fence, "allow": names}
    return {"fence": fence}


def of_post(post: Mapping[str, Any]) -> dict[str, Any] | None:
    return sanitize(post["origin"]) if "origin" in post else None


def fold(origins: Iterable[Mapping[str, Any] | None]) -> dict[str, Any] | None:
    fences: set[str] = set()
    lists: list[set[str]] = []
    for origin in origins:
        if origin is None:
            continue
        fences.add(origin["fence"])
        if "allow" in origin:
            lists.append(set(origin["allow"]))
    if not fences:
        return None
    allow = sorted(set.intersection(*lists)) if lists else None
    fence = "peer" if "peer" in fences else "member" if "member" in fences else "allow"
    return {"fence": fence} if allow is None else {"fence": fence, "allow": allow}


def environ() -> dict[str, str]:
    current_authority = current()
    return {} if current_authority is None else {ENV: encode(current_authority)}


def encode(authority: Mapping[str, Any]) -> str:
    return json.dumps(authority, separators=(",", ":"), sort_keys=True)


def from_environ(environ: Mapping[str, str] | None = None) -> dict[str, Any] | None:
    raw = (os.environ if environ is None else environ).get(ENV)
    if raw is None:
        return None
    try:
        return sanitize(json.loads(raw))
    except ValueError:
        return dict(_FAIL_CLOSED)


@contextmanager
def apply(authority: Mapping[str, Any] | None) -> Iterator[None]:
    if authority is None:
        yield
        return
    from alpi.host.connection_context import ConnectionContext
    from alpi.host.connection_context import use as use_connection
    from alpi.tools import _policy
    from alpi.tools._paths import PEER_HISTORY_TOOLS
    fence = authority["fence"]
    allow = {*authority["allow"], "workgroup_post"} if "allow" in authority else None
    with ExitStack() as stack:
        if fence == "member":
            stack.enter_context(use_connection(ConnectionContext(source="workgroup", role="member")))
        if fence != "member" or allow is not None:
            stack.enter_context(
                _policy.use(
                    allow, "a workgroup turn woken by a fenced post", PEER_HISTORY_TOOLS,
                    fence_without_policy=True, fenced=fence == "peer",
                ),
            )
        yield
