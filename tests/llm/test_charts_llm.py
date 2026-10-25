from __future__ import annotations

import re

import pytest

from alpi import charts

pytestmark = pytest.mark.llm

_BLOCK = re.compile(r"^[ \t]*```chart[^\n]*\n(.*?)\n[ \t]*```", re.M | re.S)


def _blocks(text: str) -> list[str]:
    return _BLOCK.findall(text)


def test_a_series_over_time_comes_back_as_a_valid_chart(llm_engine) -> None:
    _engine, _home, trace, run = llm_engine()
    run(
        "My sleep score for the last ten nights, oldest first: 71, 74, 69, 78, 81, 77, 83, 80, 85, 82. "
        "How is my sleep going?"
    )
    reply = trace.assistant_text()
    blocks = _blocks(reply)
    assert blocks, f"no chart for a ten-point series; reply:\n{reply}"
    assert any(charts.parse_chart(b) is not None for b in blocks), f"chart block does not validate:\n{blocks}"


def test_a_single_number_stays_text(llm_engine) -> None:
    _engine, _home, trace, run = llm_engine()
    run("My sleep score last night was 82. Is that good?")
    reply = trace.assistant_text()
    assert not _blocks(reply), f"charted a single number; reply:\n{reply}"
