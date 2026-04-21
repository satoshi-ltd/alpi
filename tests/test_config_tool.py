"""Tests for the `config` tool — get/set/reset/list over config.yaml."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from alpi.tools.config import Config


@pytest.fixture
def home(tmp_home_no_env: Path) -> Path:
    return tmp_home_no_env


def _yaml(home: Path) -> dict:
    p = home / "config.yaml"
    return yaml.safe_load(p.read_text()) if p.exists() else {}


def test_list_returns_every_editable_key(home: Path) -> None:
    r = Config().run(action="list")
    assert r.ok
    for k in (
        "model", "workspace", "tools.max_steps_per_turn", "tui.accent",
        "gateway.telegram.show_tool_trace", "gateway.email.poll_interval",
    ):
        assert k in r.output


def test_get_reflects_default_when_key_not_in_file(home: Path) -> None:
    r = Config().run(action="get", key="tools.max_steps_per_turn")
    assert r.ok
    assert "40" in r.output


def test_set_int_writes_to_yaml_and_returns_takes_effect(home: Path) -> None:
    r = Config().run(action="set", key="tools.max_steps_per_turn", value="60")
    assert r.ok
    assert "60" in r.output and "next turn" in r.output
    data = _yaml(home)
    assert data["tools"]["max_steps_per_turn"] == 60


def test_set_bool_accepts_true_false_yes_no(home: Path) -> None:
    tool = Config()
    for raw, expected in (("false", False), ("no", False), ("true", True),
                          ("yes", True), ("1", True), ("0", False)):
        r = tool.run(action="set", key="gateway.telegram.typing_indicator",
                     value=raw)
        assert r.ok
        data = _yaml(home)
        assert data["gateway"]["telegram"]["typing_indicator"] is expected


def test_set_bool_rejects_garbage(home: Path) -> None:
    r = Config().run(action="set", key="gateway.telegram.typing_indicator",
                     value="maybe")
    assert not r.ok
    assert "bool" in r.error


def test_set_int_rejects_non_number(home: Path) -> None:
    r = Config().run(action="set", key="tools.max_steps_per_turn", value="lots")
    assert not r.ok
    assert "int" in r.error


def test_set_str_writes_accent_for_facebook_blue(home: Path) -> None:
    r = Config().run(action="set", key="tui.accent", value="#1877F2")
    assert r.ok
    assert _yaml(home)["tui"]["accent"] == "#1877F2"


def test_set_list_splits_on_comma(home: Path) -> None:
    r = Config().run(action="set", key="fallback_models",
                     value="anthropic/claude-sonnet-4.6, openai/gpt-5.4")
    assert r.ok
    assert _yaml(home)["fallback_models"] == [
        "anthropic/claude-sonnet-4.6", "openai/gpt-5.4",
    ]


def test_reset_removes_key_and_returns_to_default(home: Path) -> None:
    tool = Config()
    tool.run(action="set", key="tools.max_steps_per_turn", value="99")
    assert _yaml(home)["tools"]["max_steps_per_turn"] == 99

    r = tool.run(action="reset", key="tools.max_steps_per_turn")
    assert r.ok
    data = _yaml(home)
    assert "max_steps_per_turn" not in (data.get("tools") or {})

    back = tool.run(action="get", key="tools.max_steps_per_turn")
    assert "40" in back.output


def test_reset_noop_when_key_was_already_default(home: Path) -> None:
    r = Config().run(action="reset", key="tui.show_cost")
    assert r.ok
    assert "already default" in r.output


def test_unknown_key_is_rejected_with_discoverable_list(home: Path) -> None:
    r = Config().run(action="set", key="tools.mystery_knob", value="42")
    assert not r.ok
    assert "not editable" in r.error
    assert "tools.max_steps_per_turn" in r.error


def test_set_without_value_errors(home: Path) -> None:
    r = Config().run(action="set", key="tui.accent")
    assert not r.ok
    assert "value" in r.error


def test_missing_key_for_get_errors(home: Path) -> None:
    r = Config().run(action="get")
    assert not r.ok
    assert "key" in r.error


def test_gateway_edit_reports_gateway_restart_effect(home: Path) -> None:
    r = Config().run(action="set",
                     key="gateway.email.poll_interval", value="30")
    assert r.ok
    assert "gateway restart" in r.output
