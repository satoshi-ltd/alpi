from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from alpi import updater

FIXTURES = Path(__file__).resolve().parents[1] / "common" / "updateHint.fixtures.mjs"
ROW = re.compile(r'^\s*\[("[^"]*"), ("[^"]*"|null), ("[^"]*")\],$', re.M)


def _cases() -> list[tuple[str, str | None, str]]:
    rows = [tuple(json.loads(part) for part in match) for match in ROW.findall(FIXTURES.read_text())]
    return [row for row in rows if row[0] in {"docker", "source"}]


def test_the_shared_fixtures_are_readable() -> None:
    assert {kind for kind, _version, _text in _cases()} == {"docker", "source"}


@pytest.mark.parametrize(("kind", "version", "sentence"), _cases())
def test_alpi_update_says_what_the_apps_say(kind: str, version: str | None, sentence: str) -> None:
    assert updater.manual_hint(kind, version) == sentence
