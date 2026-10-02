from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace as NS

import pytest
import yaml

import alpi.llm as llm
import alpi.tools as tools_mod
from alpi.config import Config, ToolsConfig
from alpi.engine import Engine
from alpi.runs import persisted_tool_arguments
from alpi.tools import _args
from alpi.tools.base import Tool, ToolResult

CUT = '{"channelId": "c-1", "baseVersion": 3, "knowledge": {"data": {"general": {"name": "Hotel Example'


@pytest.fixture
def engine(monkeypatch, tmp_path: Path) -> Engine:
    home = tmp_path / "h"
    home.mkdir()
    (home / "sessions").mkdir()
    (home / "config.yaml").write_text(yaml.safe_dump({"model": "gpt-5.4-mini"}))
    monkeypatch.setattr("alpi.engine._maybe_load_mcps", lambda _cfg: [])
    monkeypatch.setattr(Engine, "_build_system_prompt", lambda self: "alpi")
    monkeypatch.setattr("alpi.ctx_window.resolve", lambda _h, _c, _m: 400_000)
    monkeypatch.setattr("alpi.ledger.check", lambda *a, **kw: None)
    monkeypatch.setattr("alpi.ledger.record", lambda *a, **kw: None)
    cfg = Config(home=home, model="gpt-5.4-mini", tools=ToolsConfig(max_steps_per_turn=6), raw={})
    return Engine(home=home, cfg=cfg)


def _streams(steps, finish_reason=None):
    def fake_stream(*_a, **_kw):
        step = steps.pop(0)
        if not step:
            yield {"text_delta": "done"}
        yield {
            "final": True,
            "input_tokens": 1, "output_tokens": 1, "cost_usd": 0.0,
            "tool_calls": step, "finish_reason": finish_reason if step else "stop",
        }
    return fake_stream


@pytest.fixture
def ran(monkeypatch):
    calls: list[tuple[str, dict]] = []

    def spy(name, arguments, deny=None, deny_reasons=None):
        calls.append((name, arguments))
        return ToolResult(ok=True, output="ok")

    monkeypatch.setattr(tools_mod, "_execute_registered", spy)
    return calls


def _tool_messages(engine: Engine) -> list[str]:
    return [m["content"] for m in engine.session.messages if m.get("role") == "tool"]


def _echoed(engine: Engine) -> list[str]:
    return [
        call["function"]["arguments"]
        for m in engine.session.messages if m.get("role") == "assistant"
        for call in m.get("tool_calls") or []
    ]


def _register(monkeypatch, parameters: dict, name: str = "probe_args") -> list[dict]:
    seen: list[dict] = []

    class Probe(Tool):
        description = "probe"

        def run(self, **kwargs):
            seen.append(kwargs)
            return ToolResult(ok=True, output="ok")

    Probe.name = name
    Probe.parameters = parameters
    monkeypatch.setitem(tools_mod._TOOLS, name, Probe)
    return seen


def test_unparseable_arguments_never_run_the_tool(engine: Engine, monkeypatch, ran) -> None:
    monkeypatch.setattr("alpi.llm.stream", _streams([
        [{"id": "c1", "name": "lobby__lobby_update_knowledge", "arguments": CUT}],
        [],
    ]))
    engine.run_turn("write it", emit=lambda _e: None)
    assert ran == []
    body = _tool_messages(engine)[-1]
    assert "arguments for lobby__lobby_update_knowledge are not valid JSON: " in body
    opened = CUT.rindex(chr(34))
    assert f"Unterminated string starting at (char {opened} of {len(CUT)}); the call did not run." in body
    assert "output-token limit" not in body
    assert _echoed(engine) == ["{}"]


def test_a_reply_cut_at_the_output_limit_says_so(engine: Engine, monkeypatch, ran) -> None:
    monkeypatch.setattr("alpi.llm.stream", _streams([
        [{"id": "c1", "name": "lobby__lobby_update_knowledge", "arguments": CUT}],
        [],
    ], finish_reason="length"))
    engine.run_turn("write it", emit=lambda _e: None)
    assert ran == []
    assert "output-token limit and cut this call off" in _tool_messages(engine)[-1]


def test_only_the_last_call_of_a_cut_reply_gets_the_limit_hint(engine: Engine, monkeypatch, ran) -> None:
    monkeypatch.setattr("alpi.llm.stream", _streams([
        [
            {"id": "c1", "name": "read_file", "arguments": '["a.txt"]'},
            {"id": "c2", "name": "read_file", "arguments": '{"path": "b.t'},
        ],
        [],
    ], finish_reason="length"))
    engine.run_turn("read", emit=lambda _e: None)
    first, last = _tool_messages(engine)
    assert "output-token limit" not in first
    assert "output-token limit" in last


def test_a_normal_tool_call_finish_never_adds_the_limit_hint(engine: Engine, monkeypatch, ran) -> None:
    monkeypatch.setattr("alpi.llm.stream", _streams([
        [{"id": "c1", "name": "read_file", "arguments": '{"path": "b.t'}],
        [],
    ], finish_reason="tool_calls"))
    engine.run_turn("read", emit=lambda _e: None)
    assert ran == []
    assert "output-token limit" not in _tool_messages(engine)[-1]


REQUIRED = {"type": "object", "properties": {
    "channelId": {"type": "string"}, "knowledge": {"type": "object"},
}, "required": ["channelId", "knowledge"]}


@pytest.mark.parametrize("raw", ["", "   ", "null"])
def test_empty_arguments_cut_at_the_output_limit_never_run(engine: Engine, monkeypatch, ran, raw) -> None:
    _register(monkeypatch, REQUIRED)
    monkeypatch.setattr("alpi.llm.stream", _streams([
        [{"id": "c1", "name": "probe_args", "arguments": raw}],
        [],
    ], finish_reason="length"))
    engine.run_turn("write it", emit=lambda _e: None)
    assert ran == []
    body = _tool_messages(engine)[-1]
    assert "arguments for probe_args are missing (required: channelId, knowledge); the call did not run." in body
    assert "output-token limit and cut this call off" in body


def test_a_complete_no_argument_call_survives_a_cut_reply(engine: Engine, monkeypatch, ran) -> None:
    _register(monkeypatch, {"type": "object", "properties": {"verbose": {"type": "boolean"}}})
    monkeypatch.setattr("alpi.llm.stream", _streams([
        [{"id": "c1", "name": "probe_args", "arguments": ""}],
        [],
    ], finish_reason="length"))
    engine.run_turn("go", emit=lambda _e: None)
    assert ran == [("probe_args", {})]


def test_an_explicit_empty_object_still_reaches_a_tool_with_required_fields(
    engine: Engine, monkeypatch, ran,
) -> None:
    _register(monkeypatch, REQUIRED)
    monkeypatch.setattr("alpi.llm.stream", _streams([
        [{"id": "c1", "name": "probe_args", "arguments": "{}"}],
        [],
    ]))
    engine.run_turn("go", emit=lambda _e: None)
    assert ran == [("probe_args", {})]


@pytest.mark.parametrize("raw", ["", "null"])
def test_empty_arguments_for_a_tool_with_required_fields_never_run(
    engine: Engine, monkeypatch, ran, raw,
) -> None:
    _register(monkeypatch, REQUIRED)
    monkeypatch.setattr("alpi.llm.stream", _streams([
        [{"id": "c1", "name": "probe_args", "arguments": raw}],
        [],
    ], finish_reason="tool_calls"))
    engine.run_turn("write it", emit=lambda _e: None)
    assert ran == []
    body = _tool_messages(engine)[-1]
    assert "are missing (required: channelId, knowledge); the call did not run." in body
    assert "output-token limit" not in body


def test_empty_arguments_still_run_a_tool_without_required_fields(engine: Engine, monkeypatch, ran) -> None:
    _register(monkeypatch, {"type": "object", "properties": {"verbose": {"type": "boolean"}}})
    monkeypatch.setattr("alpi.llm.stream", _streams([
        [{"id": "c1", "name": "probe_args", "arguments": ""}],
        [],
    ]))
    engine.run_turn("go", emit=lambda _e: None)
    assert ran == [("probe_args", {})]
    assert _echoed(engine) == ["{}"]


def test_raw_control_characters_inside_strings_are_accepted(engine: Engine, monkeypatch, ran) -> None:
    raw = '{"path": "notes.md", "content": "line one\nline two\ttabbed"}'
    monkeypatch.setattr("alpi.llm.stream", _streams([
        [{"id": "c1", "name": "write_file", "arguments": raw}],
        [],
    ]))
    engine.run_turn("save", emit=lambda _e: None)
    sent = {"path": "notes.md", "content": "line one\nline two\ttabbed"}
    assert ran == [("write_file", sent)]
    assert json.loads(_echoed(engine)[0]) == sent


def test_a_strict_call_is_echoed_byte_for_byte(engine: Engine, monkeypatch, ran) -> None:
    raw = '{ "path" :"a.txt"}'
    monkeypatch.setattr("alpi.llm.stream", _streams([
        [{"id": "c1", "name": "read_file", "arguments": raw}],
        [],
    ]))
    engine.run_turn("read", emit=lambda _e: None)
    assert _echoed(engine) == [raw]


def test_a_malformed_call_in_a_parallel_batch_runs_nothing_and_its_sibling_runs(
    engine: Engine, monkeypatch, ran,
) -> None:
    monkeypatch.setattr("alpi.llm.stream", _streams([
        [
            {"id": "c1", "name": "read_file", "arguments": '{"path": "a.txt"}'},
            {"id": "c2", "name": "read_file", "arguments": '{"path": "b.t'},
        ],
        [],
    ]))
    engine.run_turn("read both", emit=lambda _e: None)
    assert ran == [("read_file", {"path": "a.txt"})]
    bodies = _tool_messages(engine)
    assert "did not run" not in bodies[0]
    assert "arguments for read_file are not valid JSON" in bodies[1]


def test_a_non_object_payload_is_refused(engine: Engine, monkeypatch, ran) -> None:
    monkeypatch.setattr("alpi.llm.stream", _streams([
        [{"id": "c1", "name": "read_file", "arguments": '["a.txt"]'}],
        [],
    ]))
    engine.run_turn("read", emit=lambda _e: None)
    assert ran == []
    assert (
        "arguments for read_file are not a JSON object (got array); the call did not run."
        in _tool_messages(engine)[-1]
    )


def test_a_stringified_object_argument_reaches_the_tool_and_the_log_as_an_object(
    engine: Engine, monkeypatch, ran,
) -> None:
    _register(monkeypatch, {"type": "object", "properties": {
        "knowledge": {"type": "object"}, "summary": {"type": "string"},
    }})
    raw = json.dumps({"knowledge": json.dumps({"schemaVersion": 1}), "summary": "{}"})
    monkeypatch.setattr("alpi.llm.stream", _streams([
        [{"id": "c1", "name": "probe_args", "arguments": raw}],
        [],
    ]))
    engine.run_turn("write", emit=lambda _e: None)
    sent = {"knowledge": {"schemaVersion": 1}, "summary": "{}"}
    assert ran == [("probe_args", sent)]
    assert engine.session.turns[-1].tools[0].args == sent
    assert json.loads(_echoed(engine)[0]) == sent


def test_an_interrupt_mid_batch_logs_each_skipped_call_with_its_decoded_arguments(
    engine: Engine, monkeypatch,
) -> None:
    def interrupting(name, arguments, deny=None, deny_reasons=None):
        engine.interrupt_requested = True
        return ToolResult(ok=True, output="ok")

    monkeypatch.setattr(tools_mod, "_execute_registered", interrupting)
    monkeypatch.setattr("alpi.llm.stream", _streams([
        [
            {"id": "c1", "name": "write_file", "arguments": '{"path": "a", "content": "b"}'},
            {"id": "c2", "name": "write_file", "arguments": '{"path": "c", "content": "d"}'},
            {"id": "c3", "name": "write_file", "arguments": '{"path": "b.t'},
        ],
    ]))
    engine.run_turn("write", emit=lambda _e: None)
    bodies = _tool_messages(engine)
    assert len(bodies) == 3
    assert all("skipped" in body for body in bodies[1:])
    assert [tool.args for tool in engine.session.turns[-1].tools[1:]] == [{"path": "c", "content": "d"}, {}]


def test_nesting_a_log_cannot_hold_is_refused_before_the_tool_runs(engine: Engine, monkeypatch, ran) -> None:
    raw = '{"path": "a.txt", "x": ' + "[" * 500 + "]" * 500 + "}"
    monkeypatch.setattr("alpi.llm.stream", _streams([
        [{"id": "c1", "name": "read_file", "arguments": raw}],
        [],
    ]))
    engine.run_turn("read", emit=lambda _e: None)
    assert ran == []
    assert "are not valid JSON: nested deeper than 100 levels; the call did not run." in _tool_messages(engine)[-1]


def test_an_unpaired_surrogate_is_refused_before_the_tool_runs(engine: Engine, monkeypatch, ran) -> None:
    raw = '{"path": "notes.md", "content": "smile \\ud83d\nnext line"}'
    monkeypatch.setattr("alpi.llm.stream", _streams([
        [{"id": "c1", "name": "write_file", "arguments": raw}],
        [],
    ]))
    engine.run_turn("save", emit=lambda _e: None)
    assert ran == []
    assert "a string holds an unpaired surrogate" in _tool_messages(engine)[-1]
    assert _echoed(engine) == ["{}"]


@pytest.mark.parametrize("number", ["NaN", "Infinity", "-Infinity", "1e999"])
def test_a_non_finite_number_never_reaches_the_tool_or_the_history(
    engine: Engine, monkeypatch, ran, number,
) -> None:
    monkeypatch.setattr("alpi.llm.stream", _streams([
        [{"id": "c1", "name": "read_file", "arguments": '{"path": "a.txt", "limit": ' + number + "}"}],
        [],
    ]))
    engine.run_turn("read", emit=lambda _e: None)
    assert ran == []
    assert "a number is out of range (NaN, Infinity or beyond ±1.8e308); the call did not run." in _tool_messages(engine)[-1]
    assert _echoed(engine) == ["{}"]


@pytest.mark.parametrize("number", ["NaN", "Infinity", "-Infinity", "1e999"])
def test_a_stringified_object_with_a_non_finite_number_stays_a_string(
    engine: Engine, monkeypatch, ran, number,
) -> None:
    _register(monkeypatch, {"type": "object", "properties": {"payload": {"type": "object"}}})
    raw = json.dumps({"payload": '{"measurement": ' + number + "}"})
    monkeypatch.setattr("alpi.llm.stream", _streams([
        [{"id": "c1", "name": "probe_args", "arguments": raw}],
        [],
    ]))
    engine.run_turn("send", emit=lambda _e: None)
    assert ran == [("probe_args", {"payload": '{"measurement": ' + number + "}"})]
    echoed = _echoed(engine)[0]
    assert echoed == raw
    json.loads(echoed, parse_constant=lambda c: pytest.fail(f"history carries {c}"))


@pytest.mark.parametrize("hidden", ["NaN", "1e999", '"\\ud83d"', "1" + "0" * 400])
def test_a_duplicate_key_cannot_hide_a_value_from_the_checks(engine: Engine, monkeypatch, ran, hidden) -> None:
    raw = '{"path": "a.txt", "limit": ' + hidden + ', "limit": 5}'
    monkeypatch.setattr("alpi.llm.stream", _streams([
        [{"id": "c1", "name": "read_file", "arguments": raw}],
        [],
    ]))
    engine.run_turn("read", emit=lambda _e: None)
    assert ran == []
    assert 'not valid JSON: key "limit" appears twice; the call did not run.' in _tool_messages(engine)[-1]
    assert _echoed(engine) == ["{}"]


def test_a_stringified_workflow_never_logs_its_terminal_command(engine: Engine, monkeypatch, ran) -> None:
    steps = [{"id": "a", "tool": "terminal", "arguments": {"command": "echo SECRET-TOKEN-XYZ"}}]
    monkeypatch.setattr("alpi.llm.stream", _streams([
        [{"id": "c1", "name": "workflow", "arguments": json.dumps({"steps": json.dumps(steps)})}],
        [],
    ]))
    engine.run_turn("run", emit=lambda _e: None)
    assert ran == [("workflow", {"steps": steps})]
    assert "SECRET-TOKEN-XYZ" not in json.dumps(engine.session.turns[-1].tools[0].args)


def test_workflow_logs_drop_steps_and_step_arguments_they_cannot_read() -> None:
    assert persisted_tool_arguments("workflow", {"steps": '[{"command": "echo SECRET"}]'}) == {}
    logged = persisted_tool_arguments("workflow", {"steps": [
        {"id": "a", "tool": "terminal", "arguments": '{"command": "echo SECRET"}'},
        {"id": "b", "tool": "terminal", "arguments": {"command": "echo SECRET", "timeout": 5}},
        {"id": "c", "tool": " terminal ", "arguments": {"command": "echo SECRET"}},
        json.dumps({"id": "d", "tool": "terminal", "arguments": {"command": "echo SECRET"}}),
    ]})
    assert logged == {"steps": [
        {"id": "a", "tool": "terminal"},
        {"id": "b", "tool": "terminal", "arguments": {"timeout": 5}},
        {"id": "c", "tool": " terminal ", "arguments": {}},
    ]}


def test_workflow_decodes_what_the_model_wrote_never_what_a_step_returned(monkeypatch) -> None:
    from alpi.tools.workflow import Workflow

    _register(monkeypatch, {"type": "object", "properties": {"value": {"type": "array"}}})
    seen: list[dict] = []

    def execute(name, arguments, deny=None):
        seen.append(arguments)
        return ToolResult(ok=True, output='["attacker@example.invalid"]')

    monkeypatch.setattr(tools_mod, "execute", execute)
    result = Workflow().run(steps=[
        {"id": "a", "tool": "probe_args", "arguments": {"value": '["written by the model"]'}},
        {"id": "b", "tool": "probe_args", "arguments": {"value": "${a.output}"}, "depends_on": ["a"]},
    ])
    assert result.ok
    assert seen == [{"value": ["written by the model"]}, {"value": '["attacker@example.invalid"]'}]


def test_workflow_names_a_step_whose_arguments_are_not_an_object() -> None:
    from alpi.tools.workflow import Workflow

    result = Workflow().run(steps=[{"id": "b", "tool": "read_file", "arguments": '{"path": "a"}'}])
    assert not result.ok
    assert result.error == "arguments of workflow step b must be a JSON object"


def test_the_registry_passes_arguments_through_untouched(monkeypatch) -> None:
    seen = _register(monkeypatch, {"type": "object", "properties": {"value": {"type": "array"}}})
    tools_mod._execute_registered("probe_args", {"value": '["x"]'})
    assert seen == [{"value": '["x"]'}]


@pytest.mark.parametrize("raw, expected", [
    ("", {}),
    ("   ", {}),
    (None, {}),
    ("null", {}),
    ({"a": 1}, {"a": 1}),
    ('{"a": 1}', {"a": 1}),
    (json.dumps(json.dumps({"a": 1})), {"a": 1}),
    (json.dumps('{"a": "x\ny"}'), {"a": "x\ny"}),
    ('{"a": "x\ny"}', {"a": "x\ny"}),
    ('{"a": "\\ud83d\\ude00"}', {"a": "\U0001F600"}),
    ('{"a": ' + "[" * 99 + "]" * 99 + "}", {"a": json.loads("[" * 99 + "]" * 99)}),
    ('{"n": 1' + "0" * 300 + ', "z": -0.0}', {"n": 10 ** 300, "z": -0.0}),
    ({"m": int(sys.float_info.max), "t": True}, {"m": int(sys.float_info.max), "t": True}),
    ('{"path": "a.txt", "path": "a.txt"}', {"path": "a.txt"}),
])
def test_decode_accepts(raw, expected) -> None:
    assert _args.decode(raw) == (expected, None)


@pytest.mark.parametrize("raw, detail", [
    ('{"a": 1', "not valid JSON: Expecting ',' delimiter (char 7 of 7)"),
    ('{"a": 1} trailing', "not valid JSON: Extra data (char 9 of 17)"),
    ('{"a": "x', "not valid JSON: Unterminated string starting at (char 6 of 8)"),
    ("[1, 2]", "not a JSON object (got array)"),
    ('"plain"', "not a JSON object (got string)"),
    ('"null"', "not a JSON object (got string)"),
    ("42", "not a JSON object (got number)"),
    ("true", "not a JSON object (got boolean)"),
    ("[" * 100_000 + "]" * 100_000, "not valid JSON: too deeply nested or too large (200000 chars)"),
    ("1" * 5000, "not valid JSON: too deeply nested or too large (5000 chars)"),
    (json.dumps("1" * 5000), "not a JSON object (got string)"),
    (json.dumps("[" * 100_000), "not a JSON object (got string)"),
    ('{"a": ' + "[" * 100 + "]" * 100 + "}", "not valid JSON: nested deeper than 100 levels"),
    ('{"a": "\\ud83d"}', "not valid JSON: a string holds an unpaired surrogate"),
    ('{"\\udfff": 1}', "not valid JSON: a string holds an unpaired surrogate"),
    ([1], "not a JSON object (got array)"),
    (b"{}", "not a JSON object (got bytes)"),
    ('{"m": NaN}', "not valid JSON: a number is out of range (NaN, Infinity or beyond ±1.8e308)"),
    ('{"m": Infinity}', "not valid JSON: a number is out of range (NaN, Infinity or beyond ±1.8e308)"),
    ('{"m": [-Infinity]}', "not valid JSON: a number is out of range (NaN, Infinity or beyond ±1.8e308)"),
    ('{"m": {"n": 1e999}}', "not valid JSON: a number is out of range (NaN, Infinity or beyond ±1.8e308)"),
    ({"m": float("nan")}, "not valid JSON: a number is out of range (NaN, Infinity or beyond ±1.8e308)"),
    ('{"m": 1' + "0" * 400 + "}", "not valid JSON: a number is out of range (NaN, Infinity or beyond ±1.8e308)"),
    ({"m": -(10 ** 400)}, "not valid JSON: a number is out of range (NaN, Infinity or beyond ±1.8e308)"),
    ('{"path": "a.txt", "limit": NaN, "limit": 5}', 'not valid JSON: key "limit" appears twice'),
    ('{"a": {"b": 1, "b": 2}}', 'not valid JSON: key "b" appears twice'),
    ('{"a": "x\ny", "a": "z"}', 'not valid JSON: key "a" appears twice'),
    ('{"m": NaN, "m": NaN}', 'not valid JSON: key "m" appears twice'),
    (json.dumps('{"path": "a.txt", "limit": NaN, "limit": 5}'), 'not valid JSON: key "limit" appears twice'),
    (json.dumps('{"b": 1, "b": 2}'), 'not valid JSON: key "b" appears twice'),
    ({"m": int(sys.float_info.max) + 1}, "not valid JSON: a number is out of range (NaN, Infinity or beyond ±1.8e308)"),
])
def test_decode_refuses(raw, detail) -> None:
    assert _args.decode(raw) == (None, detail)


def test_prepare_takes_an_already_decoded_object_as_is(monkeypatch) -> None:
    _register(monkeypatch, REQUIRED)
    assert _args.prepare("probe_args", {}) == ({}, None)
    assert _args.prepare("probe_args", {"knowledge": '{"a": 1}'}) == ({"knowledge": {"a": 1}}, None)


def test_wire_echoes_strict_calls_and_canonicalises_the_rest() -> None:
    assert _args.wire('{ "a":1}', {"a": 1}) == '{ "a":1}'
    assert _args.wire('{"a": "x\ny"}', {"a": "x\ny"}) == '{"a": "x\\ny"}'
    assert _args.wire('{"a": "{}"}', {"a": {}}) == '{"a": {}}'
    assert _args.wire("", {}) == "{}"
    assert _args.wire('{"a": 1', None) == "{}"
    assert _args.wire('{"a": "\u00e9\n"}', {"a": "\u00e9\n"}) == '{"a": "\\u00e9\\n"}'
    assert _args.wire('{"m": NaN}', {"m": float("nan")}) == "{}"
    assert _args.wire('{"m": 1e999}', {"m": float("inf")}) == "{}"
    assert _args.wire("", {"m": [float("-inf")]}) == "{}"
    assert _args.wire('{"a": 1, "a": 1}', {"a": 1}) == '{"a": 1}'
    assert _args.wire('{"a": {"b": 2, "b": 2}}', {"a": {"b": 2}}) == '{"a": {"b": 2}}'


SCHEMA = {"type": "object", "properties": {
    "knowledge": {"type": "object", "additionalProperties": {}},
    "steps": {"type": "array", "items": {"type": "object"}},
    "summary": {"type": "string"},
    "either": {"oneOf": [{"type": "object"}, {"type": "null"}]},
    "nullable": {"type": ["array", "null"]},
}}


def test_coerce_decodes_strings_for_object_and_array_parameters() -> None:
    assert _args.coerce({
        "knowledge": '{"schemaVersion": 1}',
        "steps": '[{"id": "a"}]',
        "summary": '{"looks": "like json"}',
        "either": '{"k": 1}',
        "nullable": "[1]",
    }, SCHEMA) == {
        "knowledge": {"schemaVersion": 1},
        "steps": [{"id": "a"}],
        "summary": '{"looks": "like json"}',
        "either": {"k": 1},
        "nullable": [1],
    }


def test_coerce_leaves_structured_values_alone() -> None:
    arguments = {"knowledge": {"a": 1}, "steps": [{"id": "a"}], "summary": "s", "either": None}
    assert _args.coerce(arguments, SCHEMA) == arguments


@pytest.mark.parametrize("prop, value", [
    ({"type": "object"}, "not json"),
    ({"type": "object"}, "[1, 2]"),
    ({"type": "array"}, '{"a": 1}'),
    ({"type": "integer"}, "5"),
    ({"type": ["object", "string"]}, '{"a": 1}'),
    ({"anyOf": [{"type": "object"}, {"type": "string"}]}, '{"a": 1}'),
    ({"anyOf": [{"type": "object"}, {"$ref": "#/defs/x"}]}, '{"a": 1}'),
    ({"$ref": "#/defs/x"}, '{"a": 1}'),
    ({}, '{"a": 1}'),
    ({"type": "object"}, "[" * 100_000),
    ({"type": "array"}, "[" * 101 + "]" * 101),
    ({"type": "object"}, '{"a": "\\ud83d"}'),
    ({"type": "object"}, '{"measurement": NaN}'),
    ({"type": "array"}, "[Infinity]"),
    ({"type": "object"}, '{"measurement": 1e999}'),
    ({"type": "object"}, '{"m": 1, "m": 2}'),
    ({"type": "array"}, "[" * 100 + "]" * 100),
])
def test_a_string_stays_a_string_unless_the_schema_rules_strings_out(prop, value) -> None:
    assert _args.coerce({"value": value}, {"type": "object", "properties": {"value": prop}}) == {"value": value}


def test_a_coerced_value_never_breaks_the_depth_limit_of_the_call() -> None:
    raw = json.dumps({"steps": "[" * 99 + "]" * 99})
    args, error = _args.prepare("workflow", raw)
    assert error is None and isinstance(args["steps"], list)
    assert json.loads(_args.wire(raw, args)) == args
    assert _args.prepare("workflow", json.dumps({"steps": "[" * 100 + "]" * 100}))[0] == {"steps": "[" * 100 + "]" * 100}


def test_coerce_survives_a_pathologically_nested_schema() -> None:
    schema: dict = {"type": "object"}
    for _ in range(5000):
        schema = {"anyOf": [schema]}
    assert _args.coerce({"v": "{}"}, {"properties": {"v": schema}}) == {"v": "{}"}


def test_coerce_never_mutates_the_caller_arguments() -> None:
    arguments = {"knowledge": '{"a": 1}'}
    _args.coerce(arguments, SCHEMA)
    assert arguments == {"knowledge": '{"a": 1}'}


def _complete_steps(steps, captured, finish_reason=None):
    def fake_complete(**kw):
        captured.append(kw.get("messages") or [])
        step = steps.pop(0)
        return NS(content="done" if not step else "", tool_calls=step, input_tokens=1,
                  output_tokens=1, cost_usd=0.0, raw=None,
                  finish_reason=finish_reason if step else "stop")
    return fake_complete


def _relayed(captured) -> tuple[str, str]:
    messages = captured[-1]
    body = [m for m in messages if m.get("role") == "tool"][-1]["content"]
    echo = [c["function"]["arguments"] for m in messages if m.get("role") == "assistant"
            for c in m.get("tool_calls") or []][-1]
    return body, echo


def test_delegate_never_runs_a_call_it_cannot_parse(monkeypatch, tmp_home_no_env: Path) -> None:
    from alpi.tools.delegate import Delegate

    captured: list = []
    monkeypatch.setattr("alpi.llm.complete", _complete_steps(
        [[{"id": "c1", "name": "write_file", "arguments": '{"path": "x", "content": "y'}], []],
        captured, finish_reason="length",
    ))
    ran: list = []
    monkeypatch.setattr(tools_mod, "execute", lambda *a, **kw: ran.append(a) or ToolResult(ok=True, output="ok"))
    assert Delegate().run(goal="write x", toolsets=["file"]).ok
    assert ran == []
    body, echo = _relayed(captured)
    assert "arguments for write_file are not valid JSON" in body
    assert "output-token limit" in body
    assert echo == "{}"


def test_research_never_runs_a_call_it_cannot_parse(monkeypatch, tmp_home_no_env: Path) -> None:
    from alpi.tools.research import Research

    captured: list = []
    monkeypatch.setattr("alpi.llm.complete", _complete_steps(
        [[{"id": "c1", "name": "web_fetch", "arguments": '{"url": "https://x'}], []],
        captured, finish_reason="length",
    ))
    ran: list = []
    monkeypatch.setattr(tools_mod, "execute", lambda *a, **kw: ran.append(a) or ToolResult(ok=True, output="ok"))
    assert Research().run(brief="what is X").ok
    assert ran == []
    body, echo = _relayed(captured)
    assert "arguments for web_fetch are not valid JSON" in body
    assert "output-token limit" in body
    assert echo == "{}"


def test_the_memory_reviewer_saves_an_add_with_raw_newlines(monkeypatch) -> None:
    from alpi import review

    saved: list[dict] = []
    monkeypatch.setattr(review, "run_tool", lambda name, args: saved.append(args) or ToolResult(ok=True, output="ok"))
    count = review._apply_calls([
        {"name": "memory", "arguments": '{"action": "add", "content": "first\nsecond"}'},
        {"name": "memory", "arguments": '{"action": "add", "content": "cut'},
    ])
    assert count == 1
    assert saved == [{"action": "add", "content": "first\nsecond"}]


def _tool_chunk(arguments: str, finish_reason=None):
    call = NS(index=0, id="c1", function=NS(name="write_file", arguments=arguments))
    return NS(choices=[NS(delta=NS(content=None, reasoning_content=None, reasoning=None, tool_calls=[call]),
                          finish_reason=finish_reason)], usage=None)


@pytest.mark.parametrize("finish, expected", [("length", "length"), (None, None), ("tool_calls", "tool_calls")])
def test_stream_reports_why_the_reply_ended(monkeypatch, finish, expected) -> None:
    def fake(_kwargs):
        yield _tool_chunk('{"path": "x", ')
        yield _tool_chunk('"content": "y"}', finish_reason=finish)
        yield NS(choices=[NS(delta=NS(content=None, reasoning_content=None, reasoning=None, tool_calls=None),
                             finish_reason=None)], usage=None)
        yield NS(choices=[], usage=NS(prompt_tokens=1, completion_tokens=1))

    monkeypatch.setattr(llm, "_completion_silenced", fake)
    final = list(llm.stream(model="openrouter/x/y", messages=[{"role": "user", "content": "q"}]))[-1]
    assert final["final"] is True
    assert final["finish_reason"] == expected
    assert final["tool_calls"][0]["arguments"] == '{"path": "x", "content": "y"}'


def test_complete_reports_why_the_reply_ended(monkeypatch) -> None:
    import litellm

    message = NS(content="", tool_calls=[NS(id="c1", function=NS(name="write_file", arguments='{"path": "x"'))])
    response = NS(choices=[NS(message=message, finish_reason="length")], usage=None, id=None, provider=None)
    monkeypatch.setattr(litellm, "completion", lambda **_kw: response)
    monkeypatch.setattr(llm, "_compute_cost_detail", lambda *_a: (0.0, ""))
    assert llm.complete(model="openrouter/x/y", messages=[]).finish_reason == "length"
