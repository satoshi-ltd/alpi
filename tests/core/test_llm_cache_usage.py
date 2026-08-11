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


def test_a_malformed_report_is_treated_as_unreported() -> None:
    assert llm._cached_tokens(types.SimpleNamespace(
        prompt_tokens=1000,
        prompt_tokens_details=types.SimpleNamespace(cached_tokens="abc"),
    )) is None
    assert llm._cached_tokens(types.SimpleNamespace(
        prompt_tokens="abc",
        prompt_tokens_details=types.SimpleNamespace(cached_tokens=50),
    )) is None, "an unusable denominator is unreported, not a fabricated miss"


def test_deepseek_top_level_hit_field_normalizes_through_litellm() -> None:
    """DeepSeek sends prompt_cache_hit_tokens at the usage top level; LiteLLM's Usage.__init__ maps it into cached_tokens — pin that the mapping alpi relies on exists."""
    usage = Usage(
        prompt_tokens=10000, completion_tokens=100, total_tokens=10100,
        prompt_cache_hit_tokens=8000, prompt_cache_miss_tokens=2000,
    )
    assert llm._cached_tokens(usage) == 8000


def test_the_share_reaches_the_nonstreaming_completion(monkeypatch) -> None:
    import litellm

    usage = Usage(
        prompt_tokens=12000, completion_tokens=300, cache_read_input_tokens=9000,
        cache_creation_input_tokens=250,
    )
    usage.cost = 0.0021
    response = types.SimpleNamespace(
        choices=[types.SimpleNamespace(
            message=types.SimpleNamespace(content="ok", tool_calls=None),
            finish_reason="stop",
        )],
        usage=usage,
        _hidden_params={"response_cost": 0.0021},
    )
    monkeypatch.setattr(litellm, "completion", lambda **kw: response)
    out = llm.complete(model="openrouter/x/y", messages=[{"role": "user", "content": "q"}])
    assert out.cached_tokens == 9000
    assert out.cache_write_tokens == 250
    assert out.cost_source == "provider"
    assert out.cost_usd == 0.0021


def test_writes_are_read_from_any_field_providers_use() -> None:
    assert llm._cache_write_tokens(types.SimpleNamespace(
        prompt_tokens=1000,
        prompt_tokens_details=types.SimpleNamespace(cache_write_tokens=120),
    )) == 120
    assert llm._cache_write_tokens(
        Usage(prompt_tokens=1000, completion_tokens=1, cache_creation_input_tokens=80),
    ) == 80
    assert llm._cache_write_tokens(
        Usage(prompt_tokens=1000, completion_tokens=1),
    ) is None
    assert llm._cache_write_tokens(types.SimpleNamespace(
        prompt_tokens=1000,
        prompt_tokens_details=types.SimpleNamespace(cache_write_tokens="abc"),
    )) is None


def test_the_discount_is_captured_as_provider_usd() -> None:
    assert llm._cache_discount(types.SimpleNamespace(
        prompt_tokens_details=types.SimpleNamespace(cache_discount=0.0123),
    )) == 0.0123
    assert llm._cache_discount(types.SimpleNamespace(
        prompt_tokens_details=None, cache_discount=0.0123,
    )) == 0.0123
    assert llm._cache_discount(types.SimpleNamespace(
        prompt_tokens_details=types.SimpleNamespace(cache_discount=-0.004),
    )) == -0.004, "a negative discount is a real cache-write premium"
    assert llm._cache_discount(Usage(prompt_tokens=10, completion_tokens=1)) is None
    assert llm._cache_discount(types.SimpleNamespace(
        prompt_tokens_details=types.SimpleNamespace(cache_discount="bogus"),
    )) is None


def test_cost_source_names_the_arithmetic_that_produced_the_dollars(monkeypatch) -> None:
    provider = types.SimpleNamespace(
        _hidden_params={"response_cost": 0.002},
        usage=types.SimpleNamespace(cost=0.002),
    )
    assert llm._compute_cost_detail(provider, "openrouter/x/y") == (0.002, "provider")

    # litellm stamps response_cost from its own price map for any mapped model — without usage.cost that is NOT provider evidence.
    stamped = types.SimpleNamespace(_hidden_params={"response_cost": 0.002}, usage=None)
    assert llm._compute_cost_detail(stamped, "anthropic/claude-x") == (0.002, "litellm")

    monkeypatch.setattr(
        llm, "_openrouter_pricing", lambda: {"x/y": (1e-6, 2e-6)},
    )
    import litellm as _ll

    def _raise(**kw):  # completion_cost must fail for the table fallback to fire
        raise ValueError("model not mapped")

    monkeypatch.setattr(_ll, "completion_cost", _raise)
    table = types.SimpleNamespace(
        _hidden_params={}, usage=types.SimpleNamespace(prompt_tokens=100, completion_tokens=10),
    )
    cost, source = llm._compute_cost_detail(table, "openrouter/x/y")
    assert source == "table"
    assert cost == 100 * 1e-6 + 10 * 2e-6

    nothing = types.SimpleNamespace(_hidden_params={}, usage=None)
    assert llm._compute_cost_detail(nothing, "openrouter/unknown/model") == (0.0, "none")


def test_final_chunk_carries_the_reporting_pair_and_source(monkeypatch) -> None:
    monkeypatch.setattr(llm, "_compute_cost_detail", lambda *a: (0.02, "table"))
    usage = types.SimpleNamespace(
        prompt_tokens=1000,
        completion_tokens=10,
        prompt_tokens_details=types.SimpleNamespace(
            cached_tokens=700, cache_write_tokens=120, cache_discount=0.005,
        ),
    )
    final = llm._final_chunk(types.SimpleNamespace(usage=usage), {}, "openrouter/x/y")
    assert final["cached_tokens"] == 700
    assert final["cache_write_tokens"] == 120
    assert final["cache_discount"] == 0.005
    assert final["cost_source"] == "table"


def test_affinity_id_is_stable_hashed_and_scope_distinct() -> None:
    from alpi import prefix_diag

    a = prefix_diag.affinity_id("atlas", workgroup_id="wg_1")
    assert a == prefix_diag.affinity_id("atlas", workgroup_id="wg_1")
    assert a.startswith("alpi-") and len(a) <= 64
    assert "wg_1" not in a and "atlas" not in a
    others = {
        prefix_diag.affinity_id("atlas", peer_id="wg_1"),
        prefix_diag.affinity_id("atlas", session_id="wg_1"),
        prefix_diag.affinity_id("lens", workgroup_id="wg_1"),
        prefix_diag.affinity_id("atlas", workgroup_id="wg_1", purpose="side"),
    }
    assert a not in others and len(others) == 4


def test_prefix_compare_names_the_changed_component() -> None:
    from alpi import prefix_diag

    kw = {"model": "openrouter/x/y", "api_key": "sk-secret", "max_tokens": 100}
    tools = [{"function": {"name": "a"}}]
    msgs = [{"role": "system", "content": "S"}, {"role": "user", "content": "u1"}]
    base = prefix_diag.capture(kw, tools, msgs)

    assert prefix_diag.compare(None, base) == ["first_contact"]
    grown = prefix_diag.capture(kw, tools, msgs + [{"role": "assistant", "content": "a1"}])
    assert prefix_diag.compare(base, grown) == ["none"], "append-only growth is not a rewrite"

    rewritten = prefix_diag.capture(
        kw, tools, [msgs[0], {"role": "user", "content": "EDITED"}],
    )
    assert prefix_diag.compare(base, rewritten) == ["history_rewrite"]
    assert prefix_diag.first_divergence(base, rewritten) == 1

    assert "tools" in prefix_diag.compare(
        base, prefix_diag.capture(kw, [{"function": {"name": "b"}}], msgs),
    )
    assert "system" in prefix_diag.compare(
        base, prefix_diag.capture(kw, tools, [{"role": "system", "content": "S2"}, msgs[1]]),
    )
    assert "model" in prefix_diag.compare(
        base, prefix_diag.capture({**kw, "model": "openrouter/z"}, tools, msgs),
    )
    kw2 = dict(kw); kw2["api_key"] = "other-secret"
    assert prefix_diag.compare(base, prefix_diag.capture(kw2, tools, msgs)) == ["none"], (
        "secrets never enter the shape"
    )


def test_prefix_shape_round_trips_across_processes(tmp_path) -> None:
    from alpi import prefix_diag

    shape = prefix_diag.capture(
        {"model": "openrouter/x/y"}, [], [{"role": "system", "content": "S"}],
    )
    prefix_diag.save_shape(tmp_path, "alpi-abc", shape)
    loaded = prefix_diag.load_shape(tmp_path, "alpi-abc")
    assert loaded == shape
    assert prefix_diag.load_shape(tmp_path, "alpi-missing") is None


def test_prefix_compare_windows_bound_long_transcripts() -> None:
    from alpi import prefix_diag

    kw = {"model": "openrouter/x/y"}
    msgs = [{"role": "system", "content": "S"}] + [
        {"role": "user", "content": f"m{i}"} for i in range(200)
    ]
    base = prefix_diag.capture(kw, [], msgs)
    assert base.msg_count == 200
    assert len(base.msg_hashes) == prefix_diag._MSG_WINDOW

    grown = prefix_diag.capture(kw, [], msgs + [{"role": "assistant", "content": "a"}])
    assert prefix_diag.compare(base, grown) == ["none"]

    edited = [dict(m) for m in msgs]
    edited[180]["content"] = "EDITED"
    rewritten = prefix_diag.capture(kw, [], edited)
    assert "history_rewrite" in prefix_diag.compare(base, rewritten)
    assert prefix_diag.first_divergence(base, rewritten) == 180

    shrunk = prefix_diag.capture(kw, [], msgs[:100])
    assert "history_rewrite" in prefix_diag.compare(base, shrunk)


def test_prefix_shape_store_evicts_lru_not_hot_keys(tmp_path) -> None:
    from alpi import prefix_diag

    shape = prefix_diag.capture({"model": "m"}, [], [{"role": "system", "content": "S"}])
    prefix_diag.save_shape(tmp_path, "hot", shape)
    for i in range(prefix_diag._MAX_AFFINITIES - 1):
        prefix_diag.save_shape(tmp_path, f"cold-{i}", shape)
    prefix_diag.save_shape(tmp_path, "hot", shape)
    prefix_diag.save_shape(tmp_path, "newcomer", shape)
    assert prefix_diag.load_shape(tmp_path, "hot") is not None, (
        "re-saving must refresh recency; eviction is LRU-by-write, not FIFO"
    )
    assert prefix_diag.load_shape(tmp_path, "cold-0") is None


def test_concurrent_shape_saves_lose_no_keys(tmp_path) -> None:
    import threading

    from alpi import prefix_diag

    shape = prefix_diag.capture({"model": "m"}, [], [{"role": "system", "content": "S"}])

    def _writer(key: str) -> None:
        for _ in range(50):
            prefix_diag.save_shape(tmp_path, key, shape)

    threads = [threading.Thread(target=_writer, args=(k,)) for k in ("a", "b", "c", "d")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    for k in ("a", "b", "c", "d"):
        assert prefix_diag.load_shape(tmp_path, k) is not None, (
            "an unlocked read-modify-write drops concurrent writers' keys"
        )
    import json
    json.loads((tmp_path / "logs" / "prefix_shapes.json").read_text())
