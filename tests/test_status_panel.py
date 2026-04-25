"""TUI /status panel — same data as the Telegram /status shortcut."""

from __future__ import annotations

from alpi.session import Session, Turn
from alpi.tui.screens import StatusPanel, _status_rows


def _fake_session(**overrides):
    s = Session(home="/tmp", model="openai/gpt-5.4-mini")
    s.id = "abc123def456"
    s.turns = []
    s.input_tokens = 0
    s.output_tokens = 0
    s.cost_usd = 0.0
    for k, v in overrides.items():
        setattr(s, k, v)
    return s


def test_status_panel_uses_status_title() -> None:
    # Sanity that the rename from /cost to /status stuck.
    assert StatusPanel.panel_title == "/status"


def test_status_rows_cover_every_field() -> None:
    s = _fake_session(
        turns=[Turn(at=0, user="hi", assistant="ok", tools=[])] * 3,
        input_tokens=1234, output_tokens=567, cost_usd=0.0042,
    )
    rows = dict(_status_rows(s))
    assert rows["model"] == "openai/gpt-5.4-mini"
    assert rows["turns"] == "3"
    assert "in=1,234" in rows["tokens"]
    assert "out=567" in rows["tokens"]
    assert rows["session cost"] == "$0.0042"


def test_status_rows_order_matches_telegram_shortcut() -> None:
    """Order of rows should mirror the Telegram ``/status`` shortcut output
    so both surfaces look identical at a glance."""
    s = _fake_session()
    labels = [label for label, _ in _status_rows(s)]
    assert labels == ["model", "turns", "elapsed", "tokens", "session cost"]


def test_status_rows_appends_budget_when_home_provided(tmp_path) -> None:
    """Passing ``home`` adds a ``daily budget`` row sourced from the ledger."""
    s = _fake_session()
    rows = dict(_status_rows(s, home=tmp_path, cfg_budget={"daily_usd": 5.0}))
    assert "daily budget" in rows
    assert rows["daily budget"] == "$0.0000 / $5.00"


def test_status_rows_handle_session_without_turns_attr() -> None:
    """`getattr(..., "turns", [])` fallback survives legacy or stubbed
    session objects that don't ship the attribute."""
    class _MinimalSession:
        id = "x"
        model = "m"
        elapsed = 0
        input_tokens = 0
        output_tokens = 0
        cost_usd = 0.0
    rows = dict(_status_rows(_MinimalSession()))
    assert rows["turns"] == "0"
