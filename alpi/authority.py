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
    if connection().role != "admin":
        return {"fence": "member"}
    if _policy.fences_private_areas():
        return {"fence": "peer"}
    allowed = _policy.allowed()
    if allowed is not None:
        return {"fence": "allow", "allow": sorted(allowed)}
    return from_environ()


def sanitize(raw: object) -> dict[str, Any]:
    if not isinstance(raw, dict) or raw.get("fence") not in _FENCES:
        return dict(_FAIL_CLOSED)
    fence = raw["fence"]
    if fence != "allow":
        return {"fence": fence}
    allow = raw.get("allow")
    if not isinstance(allow, list):
        return dict(_FAIL_CLOSED)
    names = sorted({a.strip() for a in allow if isinstance(a, str) and 0 < len(a.strip()) <= _MAX_NAME})
    return {"fence": "allow", "allow": names[:_MAX_ALLOW]}


def of_post(post: Mapping[str, Any]) -> dict[str, Any] | None:
    return sanitize(post["origin"]) if "origin" in post else None


def fold(origins: Iterable[Mapping[str, Any] | None]) -> dict[str, Any] | None:
    kinds: set[str] = set()
    lists: list[set[str]] = []
    for origin in origins:
        if origin is None:
            continue
        kinds.add(origin["fence"])
        if origin["fence"] == "allow":
            lists.append(set(origin["allow"]))
    if not kinds:
        return None
    if kinds == {"allow"}:
        return {"fence": "allow", "allow": sorted(set.intersection(*lists))}
    if kinds == {"member"}:
        return {"fence": "member"}
    return dict(_FAIL_CLOSED)


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
    with ExitStack() as stack:
        if authority["fence"] == "member":
            stack.enter_context(use_connection(ConnectionContext(source="workgroup", role="member")))
        else:
            allow = {*authority["allow"], "workgroup_post"} if authority["fence"] == "allow" else None
            stack.enter_context(
                _policy.use(allow, "a workgroup turn woken by a fenced post", PEER_HISTORY_TOOLS, fence_without_policy=True),
            )
        yield
