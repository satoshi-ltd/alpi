from __future__ import annotations

import re
from typing import Any

import yaml

_SURROGATE_RE = re.compile("[\ud800-\udfff]")

# yaml.safe_load never uses libyaml on its own — do not "simplify" back to it (10x slower).
_LOADER = getattr(yaml, "CSafeLoader", yaml.SafeLoader)
_DUMPER = getattr(yaml, "CSafeDumper", yaml.SafeDumper)
HAS_LIBYAML = _DUMPER is not yaml.SafeDumper


def safe_load(text: str) -> Any:
    return yaml.load(text, Loader=_LOADER)


def _reject_surrogates(data: Any) -> None:
    stack = [data]
    while stack:
        item = stack.pop()
        if isinstance(item, str):
            found = _SURROGATE_RE.search(item)
            if found is not None:
                raise UnicodeEncodeError(
                    "utf-8", item, found.start(), found.end(),
                    "surrogates not allowed",
                )
        elif isinstance(item, dict):
            stack.extend(item.keys())
            stack.extend(item.values())
        elif isinstance(item, (list, tuple)):
            stack.extend(item)


def safe_dump(data: Any, **kwargs: Any) -> str:
    if not HAS_LIBYAML:
        # libyaml raises on a lone surrogate while the pure emitter escapes it into a file CSafeLoader then refuses, so raise the same error by hand rather than write a file only this install can read.
        _reject_surrogates(data)
        # The pure emitter writes U+0085 raw inside a quoted scalar and every loader folds it back to a space; escaping all non-ASCII is its only lossless setting.
        kwargs["allow_unicode"] = False
    return yaml.dump(data, Dumper=_DUMPER, **kwargs)
