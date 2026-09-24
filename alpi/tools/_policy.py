from __future__ import annotations

import contextvars
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from fnmatch import fnmatchcase


_denies: contextvars.ContextVar[frozenset[str]] = contextvars.ContextVar(
    "alpi_tool_policy_denies", default=frozenset(),
)
_label: contextvars.ContextVar[str] = contextvars.ContextVar("alpi_tool_policy_label", default="")


@contextmanager
def use(denies: Iterable[str], label: str) -> Iterator[None]:
    denies_token = _denies.set(frozenset(str(d).strip() for d in denies if str(d).strip()))
    label_token = _label.set(label)
    try:
        yield
    finally:
        _label.reset(label_token)
        _denies.reset(denies_token)


def denies() -> frozenset[str]:
    return _denies.get()


def effective_denies(profile_denies: Iterable[str]) -> frozenset[str]:
    from alpi.tools._paths import dispatch_tool_denies
    return frozenset(profile_denies) | dispatch_tool_denies() | denies()


def is_denied(name: str, deny: Iterable[str] | None) -> bool:
    if not deny:
        return False
    return any(name == entry or ("*" in entry and fnmatchcase(name, entry)) for entry in deny)


def reason_for(name: str) -> str:
    label = _label.get()
    if not label or not is_denied(name, _denies.get()):
        return ""
    return f"tool denied by the tool policy for {label}: {name} (tools.deny in peers.yaml)"
