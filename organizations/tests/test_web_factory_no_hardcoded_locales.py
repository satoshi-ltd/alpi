import json
import re
from pathlib import Path

import pytest

ORGS_ROOT = Path(__file__).resolve().parents[1]
WEB_FACTORY = ORGS_ROOT / "web-factory"
SPEC = WEB_FACTORY / "factory" / "template-spec.json"

pytestmark = pytest.mark.skipif(
    not WEB_FACTORY.exists(),
    reason="organizations/web-factory/ is not in this checkout (subtree imported once acceptance fixtures pass)",
)


def _supported_locales() -> list[str]:
    return list(json.loads(SPEC.read_text())["i18n"]["supportedLocales"])


def _locale_sequence_pattern(locales: list[str]) -> re.Pattern:
    loc_alt = "|".join(sorted((re.escape(l) for l in locales), key=len, reverse=True))
    sep = r"\s*[,/|]\s*"
    return re.compile(
        rf"(?<![A-Za-z0-9-])(?:{loc_alt})(?:{sep}(?:{loc_alt})){{2,}}(?![A-Za-z0-9-])",
        re.IGNORECASE,
    )


def test_no_locale_list_hardcoded_in_web_factory_skills():
    supported = _supported_locales()
    pat = _locale_sequence_pattern(supported)

    leak: list[tuple[str, str, str]] = []
    for md in (WEB_FACTORY / "agents").rglob("*.md"):
        text = md.read_text()
        for m in pat.finditer(text):
            seq = m.group(0)
            start = max(0, m.start() - 60)
            end = min(len(text), m.end() + 60)
            snippet = text[start:end].replace("\n", " ")
            leak.append((str(md.relative_to(WEB_FACTORY)), seq, snippet))
    assert not leak, (
        "Hardcoded locale list (partial or full) found in web-factory skill / "
        "agent files. The single source of truth is "
        "factory/template-spec.json → i18n.supportedLocales; reference it "
        "by name, do not inline the list (drift breaks the moment a locale "
        "is added or removed):\n  "
        + "\n  ".join(f"{p}: matched {seq!r} in …{snip}…" for p, seq, snip in leak[:6])
    )
