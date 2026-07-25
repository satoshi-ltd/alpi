from __future__ import annotations

from typing import Any

import yaml

# yaml.safe_load never uses libyaml on its own — do not "simplify" back to it (10x slower).
_LOADER = getattr(yaml, "CSafeLoader", yaml.SafeLoader)
_DUMPER = getattr(yaml, "CSafeDumper", yaml.SafeDumper)


def safe_load(text: str) -> Any:
    return yaml.load(text, Loader=_LOADER)


def safe_dump(data: Any, **kwargs: Any) -> str:
    return yaml.dump(data, Dumper=_DUMPER, **kwargs)
