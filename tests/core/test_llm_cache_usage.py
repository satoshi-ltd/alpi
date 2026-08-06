"""Prefix-cache accounting reads real provider Usage objects, never a stand-in."""

from __future__ import annotations

import types

from litellm.types.utils import Usage

from alpi import llm


def test_a_provider_that_reports_nothing_is_not_a_miss() -> None:
    assert llm._cached_tokens(Usage(prompt_tokens=1000, completion_tokens=1)) is None
    assert llm._cached_tokens(None) is None


def test_a_reported_zero_is_a_measured_miss() -> None:
    assert llm._cached_tokens(
        Usage(prompt_tokens=1000, completion_tokens=1, cache_read_input_tokens=0),
    ) == 0
    assert llm._cached_tokens(types.SimpleNamespace(
        prompt_tokens=1000,
        prompt_tokens_details=types.SimpleNamespace(cached_tokens=0),
    )) == 0


def test_a_hit_is_read_from_either_field_providers_use() -> None:
    assert llm._cached_tokens(
        Usage(prompt_tokens=1000, completion_tokens=1, cache_read_input_tokens=70),
    ) == 70
    assert llm._cached_tokens(types.SimpleNamespace(
        prompt_tokens=12000,
        prompt_tokens_details=types.SimpleNamespace(cached_tokens=9000),
    )) == 9000


def test_a_zero_prompt_does_not_skip_the_clamp() -> None:
    assert llm._cached_tokens(
        Usage(prompt_tokens=0, completion_tokens=1, cache_read_input_tokens=70),
    ) == 0


def test_a_share_cannot_exceed_the_prompt_it_came_from() -> None:
    assert llm._cached_tokens(types.SimpleNamespace(
        prompt_tokens=700,
        prompt_tokens_details=types.SimpleNamespace(cached_tokens=9000),
    )) == 700
    assert llm._cached_tokens(types.SimpleNamespace(
        prompt_tokens=700,
        prompt_tokens_details=types.SimpleNamespace(cached_tokens=-5),
    )) == 0


def test_the_share_survives_save_and_hydrate(tmp_path) -> None:
    from alpi.cli import _hydrate_from_path
    from alpi.session import Session

    s = Session(home=tmp_path, model="m")
    final = llm._final_chunk(
        types.SimpleNamespace(usage=Usage(
            prompt_tokens=12000, completion_tokens=300, cache_read_input_tokens=9000,
        )),
        {}, "openrouter/deepseek/deepseek-v4-flash-0731",
    )
    s.record(
        input_tokens=final["input_tokens"], output_tokens=final["output_tokens"],
        cost=final["cost_usd"], cached_input_tokens=final["cached_tokens"],
    )
    s.record(input_tokens=5000, output_tokens=10, cost=0.0, cached_input_tokens=None)
    s.log_turn(user="q", assistant="a", tools=[])
    path = s.save()
    assert path is not None

    fresh = types.SimpleNamespace(session=Session(home=tmp_path, model="m"))
    assert _hydrate_from_path(fresh, path) is True
    assert fresh.session.cached_input_tokens == 9000
    assert fresh.session.cache_measured_input_tokens == 12000, (
        "the unreported turn must stay out of the denominator"
    )


def test_an_unmeasured_turn_omits_cached_in_from_the_declared_cost() -> None:
    from alpi.tools.workgroup import _declared_cost

    unmeasured = _declared_cost(
        {"tokens_in": 900, "tokens_out": 40, "usd": 0.01, "cached_in": 0, "measured_in": 0},
    )
    assert "cached_in" not in unmeasured and "measured_in" not in unmeasured

    measured_miss = _declared_cost(
        {"tokens_in": 900, "tokens_out": 40, "usd": 0.01, "cached_in": 0, "measured_in": 900},
    )
    assert measured_miss["cached_in"] == 0
    assert measured_miss["measured_in"] == 900


def test_bucket_workgroup_aggregates_the_cache_share() -> None:
    from datetime import date

    from alpi.host.usage import bucket_workgroup

    entries = [
        {"ts": "2026-08-06T10:00:00Z", "cost": {
            "usd": 0.1, "tokens_in": 1000, "tokens_out": 50,
            "cached_in": 800, "measured_in": 1000,
        }},
        {"ts": "2026-08-06T11:00:00Z", "cost": {
            "usd": 0.1, "tokens_in": 500, "tokens_out": 20, "cached_in": 300,
        }},
        {"ts": "2026-08-06T12:00:00Z", "cost": {
            "usd": 0.1, "tokens_in": 700, "tokens_out": 30,
        }},
    ]
    days = bucket_workgroup(entries, date(2026, 8, 6))
    day = next(d for d in days if d.get("cachedIn"))
    assert day["cachedIn"] == 1100
    assert day["measuredIn"] == 1500, (
        "the legacy entry counts its tokens_in as denominator; the unmeasured one counts nothing"
    )


def test_the_share_reaches_the_final_chunk() -> None:
    usage = Usage(
        prompt_tokens=12000, completion_tokens=300, cache_read_input_tokens=9000,
    )
    final = llm._final_chunk(
        types.SimpleNamespace(usage=usage), {},
        "openrouter/deepseek/deepseek-v4-flash-0731",
    )
    assert final["cached_tokens"] == 9000
