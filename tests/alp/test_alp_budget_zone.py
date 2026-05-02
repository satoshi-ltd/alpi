from __future__ import annotations

import json
from pathlib import Path

import pytest

from alpi.alp import agent_context


def _write_cfg(home: Path, daily_usd: float | None = None) -> None:
    home.mkdir(parents=True, exist_ok=True)
    cfg = "model: x\n"
    if daily_usd is not None:
        cfg += f"budget:\n  daily_usd: {daily_usd}\n"
    (home / "config.yaml").write_text(cfg)


def _write_ledger(home: Path, used_usd: float) -> None:
    import datetime as dt
    today = dt.datetime.now(dt.timezone.utc).date().isoformat()
    p = home / "logs" / "ledger.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({
        "day": today,
        "profile": {"usd": used_usd, "tokens": 0},
        "by_peer": {},
    }))


@pytest.mark.parametrize(
    "used, expected",
    [
        (0.0, ""),
        (0.39, ""),
        (0.45, "prefer one paragraph"),
        (0.65, "one sentence if it's enough"),
        (0.85, "only post if it changes the outcome"),
    ],
)
def test_budget_zone_thresholds(tmp_path: Path, used: float, expected: str) -> None:
    home = tmp_path / "h"
    _write_cfg(home, daily_usd=1.0)
    _write_ledger(home, used)
    line = agent_context._budget_zone(home)
    if not expected:
        assert line == ""
    else:
        assert expected in line
        assert line.startswith("BUDGET:")


def test_budget_zone_silent_when_uncapped(tmp_path: Path) -> None:
    home = tmp_path / "h"
    _write_cfg(home, daily_usd=None)
    _write_ledger(home, 999.0)
    assert agent_context._budget_zone(home) == ""
