from __future__ import annotations

import contextvars
import sys
import threading
import time
from types import SimpleNamespace

import pytest

from alpi.tools import web_search as ws

HIT = {"title": "T", "href": "https://example.com", "body": "B"}
SHIPPED_ORDER = ws.DEFAULT_BACKENDS
ORDER = ("brave", "yahoo", "startpage", "mojeek", "duckduckgo", "google", "wikipedia", "grokipedia")
WEB_ENGINES = list(ORDER[:6])


@pytest.fixture(autouse=True)
def _quiet_state(monkeypatch):
    monkeypatch.setattr("alpi.tools._state.emit_state", lambda *_a, **_kw: None)


@pytest.fixture(autouse=True)
def _isolated(monkeypatch):
    from alpi.tools import _state

    monkeypatch.setattr(ws, "_MIN_INTERVAL_S", 0.0)
    monkeypatch.setattr(ws, "_last_started", 0.0)
    monkeypatch.setattr(ws, "_raw_settings", lambda: {})
    monkeypatch.setattr(ws, "_live", {})
    monkeypatch.setattr(ws, "_cooldowns", {})
    monkeypatch.setattr(ws, "DEFAULT_BACKENDS", ORDER)
    _state.reset_turn_usage()


class _Timeout(Exception):
    pass


_Timeout.__name__ = "TimeoutException"


def _install(monkeypatch, behaviour=None, default=None):
    """Fake ``ddgs``: per backend, rows, an exception, a callable, or None for its "No results found."."""
    calls: list[dict] = []
    constructed: list[dict] = []
    behaviour = behaviour or {}

    class _FakeDDGS:
        def __init__(self, **kwargs):
            constructed.append(kwargs)

        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

        def text(self, query, **kwargs):
            calls.append({"query": query, **kwargs})
            answer = behaviour.get(kwargs.get("backend"), default)
            if callable(answer) and not isinstance(answer, type):
                answer = answer()
            if isinstance(answer, BaseException):
                raise answer
            if answer is None:
                raise Exception("No results found.")
            return list(answer)

    monkeypatch.setitem(sys.modules, "ddgs", SimpleNamespace(DDGS=_FakeDDGS))
    monkeypatch.setattr(ws, "_installed_engines", lambda: set(ws.DEFAULT_BACKENDS))
    return calls, constructed


def _backends(calls):
    return [c["backend"] for c in calls]


def test_the_shipped_default_is_the_provisional_three():
    assert SHIPPED_ORDER == ("duckduckgo", "yahoo", "brave")


def test_by_default_only_the_first_engine_is_asked_when_it_answers(monkeypatch):
    monkeypatch.setattr(ws, "DEFAULT_BACKENDS", SHIPPED_ORDER)
    calls, _ = _install(monkeypatch, {"duckduckgo": [HIT]})

    assert ws.WebSearch().run(query="hotel").ok
    assert _backends(calls) == ["duckduckgo"]


def test_by_default_a_hanging_first_engine_is_skipped_after_one_timeout(monkeypatch):
    monkeypatch.setattr(ws, "DEFAULT_BACKENDS", SHIPPED_ORDER)
    calls, _ = _install(monkeypatch, {"duckduckgo": _Timeout("operation timed out"), "yahoo": [HIT]})

    assert ws.WebSearch().run(query="first").ok
    assert ws.WebSearch().run(query="second").ok

    assert _backends(calls) == ["duckduckgo", "yahoo", "yahoo"]


def test_every_call_pins_engine_timeout_and_safesearch(monkeypatch):
    calls, constructed = _install(monkeypatch, default=[HIT])

    result = ws.WebSearch().run(query="anything")

    assert result.ok
    assert _backends(calls) == ["brave"]
    assert calls[0]["safesearch"] == "moderate"
    assert constructed == [{"timeout": ws._ENGINE_TIMEOUT_S}]
    assert "auto" not in _backends(calls)


def test_engines_are_asked_in_order_until_one_answers(monkeypatch):
    calls, _ = _install(monkeypatch, {"mojeek": [HIT]})

    result = ws.WebSearch().run(query="hotel booking")

    assert result.ok
    assert _backends(calls) == ["brave", "yahoo", "startpage", "mojeek"]
    assert "(via mojeek)" in result.output
    assert "example.com" in result.output


def test_encyclopedias_are_only_asked_after_every_web_engine(monkeypatch):
    calls, _ = _install(monkeypatch, {"wikipedia": [HIT]})

    result = ws.WebSearch().run(query="anything")

    assert result.ok
    assert _backends(calls) == WEB_ENGINES + ["wikipedia"]


def test_a_failure_names_every_engine_and_what_it_did(monkeypatch):
    _install(monkeypatch, {"yahoo": _Timeout("operation timed out"), "mojeek": RuntimeError("403 Forbidden")})

    result = ws.WebSearch().run(query="anything")

    assert not result.ok
    assert "search failed" in result.error
    assert "brave: empty" in result.error
    assert "yahoo: timeout" in result.error
    assert "mojeek: error (RuntimeError: 403 Forbidden)" in result.error
    assert "grokipedia: empty" in result.error
    assert "rarely gets past" in result.error


@pytest.mark.parametrize("failure", [_Timeout("timed out"), OSError("Name or service not known"), ValueError("bad html")])
def test_a_failure_reports_what_happened_without_inventing_a_cause(monkeypatch, failure):
    _install(monkeypatch, default=failure)

    error = ws.WebSearch().run(query="anything").error

    for claim in ("IP", "rate limit", "limited", "refus", "block"):
        assert claim not in error


def test_each_engine_is_asked_at_most_once_per_search(monkeypatch):
    calls, _ = _install(monkeypatch, default=RuntimeError("down"))

    assert not ws.WebSearch().run(query="anything").ok
    assert sorted(_backends(calls)) == sorted(ws.DEFAULT_BACKENDS)


def test_a_timed_out_engine_cools_down_across_searches(monkeypatch):
    calls, _ = _install(monkeypatch, {"brave": _Timeout("timed out"), "yahoo": [HIT]})

    assert ws.WebSearch().run(query="first").ok
    assert set(ws._cooldowns) == {"brave"}

    calls.clear()
    assert ws.WebSearch().run(query="second").ok
    assert _backends(calls) == ["yahoo"]


def test_an_empty_answer_never_sidelines_an_engine_for_other_queries(monkeypatch):
    only_brave_knows = {"title": "B", "href": "https://b.example", "body": "b"}
    calls, _ = _install(monkeypatch, {"yahoo": [HIT]})
    assert ws.WebSearch().run(query="a").ok

    calls.clear()
    _install(monkeypatch, {"brave": [only_brave_knows]})
    result = ws.WebSearch().run(query="b")

    assert result.ok
    assert "(via brave)" in result.output
    assert ws._cooldowns == {}


def test_every_engine_empty_is_no_results_not_a_blocked_machine(monkeypatch):
    _install(monkeypatch)

    result = ws.WebSearch().run(query="zzxyq nonsense")

    assert result.ok
    assert "no results for 'zzxyq nonsense'" in result.output
    assert "brave: empty" in result.output and "grokipedia: empty" in result.output
    assert "broaden it once" in result.output
    assert "do NOT" not in result.output
    assert ws._cooldowns == {}


def test_skipped_engines_never_turn_no_results_into_a_failure(monkeypatch):
    _install(monkeypatch, {"brave": _Timeout("timed out")})

    assert not ws.WebSearch().run(query="first").ok
    result = ws.WebSearch().run(query="second")

    assert result.ok
    assert "no results for 'second'" in result.output
    assert "not asked brave (cooling down)" in result.output


def _all_cooling(soonest, second=None):
    now = time.monotonic()
    ws._cooldowns.update({name: now + 600 for name in ws.DEFAULT_BACKENDS})
    ws._cooldowns[soonest] = now + 60
    if second:
        ws._cooldowns[second] = now + 120


def test_when_every_engine_is_cooling_only_the_one_due_first_is_asked(monkeypatch):
    _all_cooling("mojeek")
    calls, _ = _install(monkeypatch, default=_Timeout("timed out"))

    result = ws.WebSearch().run(query="anything")

    assert not result.ok
    assert _backends(calls) == ["mojeek"]
    assert "asked mojeek: timeout" in result.error
    assert "brave (cooling down)" in result.error


def _running(stop: threading.Event) -> threading.Thread:
    worker = threading.Thread(target=stop.wait, daemon=True)
    worker.start()
    return worker


def test_the_probe_never_picks_an_engine_still_busy(monkeypatch):
    _all_cooling("mojeek", second="yahoo")
    stop = threading.Event()
    monkeypatch.setattr(ws, "_live", {"mojeek": _running(stop)})
    calls, _ = _install(monkeypatch, {"yahoo": [HIT]})

    try:
        result = ws.WebSearch().run(query="anything")
    finally:
        stop.set()

    assert result.ok
    assert _backends(calls) == ["yahoo"]


def test_an_engine_with_a_request_still_running_is_not_asked_again(monkeypatch):
    stop = threading.Event()
    monkeypatch.setattr(ws, "_live", {"brave": _running(stop)})
    calls, _ = _install(monkeypatch, {"yahoo": [HIT]})

    try:
        result = ws.WebSearch().run(query="anything")
    finally:
        stop.set()

    assert result.ok
    assert _backends(calls) == ["yahoo"]


def test_no_new_request_starts_while_the_cap_is_running(monkeypatch):
    stop = threading.Event()
    monkeypatch.setattr(ws, "_live", {"brave": _running(stop), "yahoo": _running(stop)})
    calls, _ = _install(monkeypatch, default=[HIT])

    try:
        result = ws.WebSearch().run(query="anything")
    finally:
        stop.set()

    assert calls == []
    assert not result.ok
    assert "could not ask any engine" in result.error
    assert "brave (still busy with an earlier search)" in result.error
    assert "startpage (earlier requests still running)" in result.error


def test_the_engine_due_first_that_answers_ends_the_outage(monkeypatch):
    _all_cooling("mojeek")
    calls, _ = _install(monkeypatch, {"mojeek": [HIT]})

    assert ws.WebSearch().run(query="anything").ok
    assert _backends(calls) == ["mojeek"]
    assert "mojeek" not in ws._cooldowns


def test_a_cooldown_expires(monkeypatch):
    ws._cooldowns["brave"] = time.monotonic() - 1
    calls, _ = _install(monkeypatch, {"brave": [HIT]})

    assert ws.WebSearch().run(query="anything").ok
    assert _backends(calls) == ["brave"]
    assert ws._cooldowns == {}


def test_the_search_stops_asking_once_its_time_is_spent(monkeypatch):
    monkeypatch.setattr(ws, "_CALL_BUDGET_S", 0.15)

    def slow():
        time.sleep(0.1)
        return []

    calls, _ = _install(monkeypatch, default=slow)
    result = ws.WebSearch().run(query="anything")

    assert not result.ok
    assert len(calls) == 2
    assert "grokipedia (out of time)" in result.error


def test_configured_backends_set_the_order_and_drop_unknown_names(monkeypatch):
    monkeypatch.setattr(ws, "_raw_settings", lambda: {"backends": ["Mojeek", "bogus", "brave", "mojeek"]})
    calls, _ = _install(monkeypatch)

    ws.WebSearch().run(query="anything")

    assert _backends(calls) == ["mojeek", "brave"]


@pytest.mark.parametrize("configured", [["bogus"], "brave,yahoo", [], None, 7])
def test_unusable_backends_fall_back_to_the_default_order(monkeypatch, configured):
    monkeypatch.setattr(ws, "_raw_settings", lambda: {"backends": configured})
    calls, _ = _install(monkeypatch)

    ws.WebSearch().run(query="anything")

    assert _backends(calls) == list(ws.DEFAULT_BACKENDS)


def test_defaults_skip_engines_this_ddgs_does_not_ship(monkeypatch):
    calls, _ = _install(monkeypatch)
    monkeypatch.setattr(ws, "_installed_engines", lambda: {"brave", "mojeek", "wikipedia"})

    ws.WebSearch().run(query="anything")

    assert _backends(calls) == ["brave", "mojeek", "wikipedia"]


@pytest.mark.parametrize(("exc", "elapsed", "expected"), [
    (_Timeout("error sending request > operation timed out"), 0.1, "timeout"),
    (Exception("No results found."), 0.1, "empty"),
    (Exception("No results found."), ws._ENGINE_TIMEOUT_S, "timeout"),
    (type("RatelimitException", (Exception,), {})("429"), 0.1, "rate-limited"),
    (type("NoResultsException", (Exception,), {})(""), 0.1, "empty"),
    (RuntimeError("connection reset"), 0.1, "error (RuntimeError: connection reset)"),
])
def test_outcomes_are_classified(exc, elapsed, expected):
    assert ws._outcome(exc, elapsed) == expected


def test_missing_ddgs_is_reported_as_missing_not_as_a_blocked_ip(monkeypatch):
    monkeypatch.setitem(sys.modules, "ddgs", None)

    result = ws.WebSearch().run(query="anything")

    assert not result.ok
    assert "ddgs package is not installed" in result.error
    assert "limited" not in result.error


def test_dedup_caps_per_domain(monkeypatch):
    rows = [
        {"title": "r1", "href": "https://reddit.com/a", "body": "b1"},
        {"title": "r2", "href": "https://reddit.com/b", "body": "b2"},
        {"title": "r3", "href": "https://www.reddit.com/c", "body": "b3"},
        {"title": "r4", "href": "https://reddit.com/d", "body": "b4"},
        {"title": "so", "href": "https://stackoverflow.com/q/1", "body": "b"},
        {"title": "wiki", "href": "https://en.wikipedia.org/wiki/X", "body": "b"},
    ]
    _install(monkeypatch, default=rows)

    out = ws.WebSearch().run(query="anything", max_results=10).output

    assert "r1" in out and "r2" in out
    assert "r3" not in out and "r4" not in out
    assert "so" in out and "wiki" in out


def test_turn_budget_stops_calling_the_backend(monkeypatch):
    calls, _ = _install(monkeypatch, default=[HIT])
    monkeypatch.setattr(ws, "_max_per_turn", lambda: 3)

    outcomes = [ws.WebSearch().run(query=f"q{i}") for i in range(5)]

    assert len(calls) == 3
    assert all(r.ok for r in outcomes[:3])
    assert all(not r.ok for r in outcomes[3:])
    assert "budget for this turn is spent" in outcomes[4].error
    assert "web_fetch" in outcomes[4].error


def test_budget_is_per_turn_not_per_process(monkeypatch):
    _install(monkeypatch, default=[HIT])
    monkeypatch.setattr(ws, "_max_per_turn", lambda: 1)
    from alpi.tools import _state

    _state._turn_id.set("turn-one")
    assert ws.WebSearch().run(query="a").ok
    assert not ws.WebSearch().run(query="b").ok

    _state.reset_turn_usage()
    _state._turn_id.set("turn-two")
    assert ws.WebSearch().run(query="c").ok


def test_interleaved_turns_do_not_reset_each_others_budget(monkeypatch):
    monkeypatch.setattr(ws, "_max_per_turn", lambda: 2)
    from alpi.tools import _state

    def new_turn(turn_id: str) -> contextvars.Context:
        context = contextvars.copy_context()

        def initialize() -> None:
            _state.reset_turn_usage()
            _state._turn_id.set(turn_id)

        context.run(initialize)
        return context

    turn_a = new_turn("turn-a")
    turn_b = new_turn("turn-b")

    assert turn_a.run(ws._spend_turn_budget, 2) == 1
    assert turn_b.run(ws._spend_turn_budget, 2) == 1
    assert turn_a.run(ws._spend_turn_budget, 2) == 2
    assert turn_b.run(ws._spend_turn_budget, 2) == 2
    assert turn_a.run(ws._spend_turn_budget, 2) is None
    assert turn_b.run(ws._spend_turn_budget, 2) is None


def test_parallel_calls_in_one_turn_share_the_budget() -> None:
    from alpi.tools import _state

    _state.reset_turn_usage()
    contexts = [contextvars.copy_context() for _ in range(4)]
    results: list[int | None] = []
    result_lock = threading.Lock()

    def spend(context: contextvars.Context) -> None:
        result = context.run(ws._spend_turn_budget, 2)
        with result_lock:
            results.append(result)

    threads = [threading.Thread(target=spend, args=(context,)) for context in contexts]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sorted(result for result in results if result is not None) == [1, 2]
    assert results.count(None) == 2


def test_searches_never_overlap(monkeypatch):
    live = {"now": 0, "max": 0}
    seen = threading.Lock()

    def slow():
        with seen:
            live["now"] += 1
            live["max"] = max(live["max"], live["now"])
        time.sleep(0.02)
        with seen:
            live["now"] -= 1
        return [HIT]

    _install(monkeypatch, default=slow)

    threads = [
        threading.Thread(target=lambda i=i: ws.WebSearch().run(query=f"q{i}"))
        for i in range(4)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert live["max"] == 1


def test_searches_are_spaced_but_engines_within_one_are_not(monkeypatch):
    _install(monkeypatch, {"startpage": [HIT]})
    monkeypatch.setattr(ws, "_MIN_INTERVAL_S", 0.2)

    started = time.monotonic()
    assert ws.WebSearch().run(query="first").ok
    first = time.monotonic() - started
    assert ws.WebSearch().run(query="second").ok

    assert first < 0.2
    assert time.monotonic() - started >= 0.2


class TestAgainstTheRealDdgs:
    @pytest.fixture(autouse=True)
    def _real(self, monkeypatch):
        import ddgs
        from ddgs.engines import ENGINES
        from ddgs.results import TextResult

        monkeypatch.setitem(sys.modules, "ddgs", ddgs)
        monkeypatch.setattr(ws, "_ENGINE_TIMEOUT_S", 1)
        asked: list[str] = []

        def stub(name, answer):
            def search(self, query, **_kwargs):
                asked.append(name)
                if isinstance(answer, float):
                    time.sleep(answer)
                    return None
                if isinstance(answer, BaseException):
                    raise answer
                return [TextResult(title=f"{query} {name}", href=f"https://{name}.example/r", body="b")] if answer else None
            return search

        for name, cls in ENGINES["text"].items():
            monkeypatch.setattr(cls, "search", stub(name, False))
        self.engines = ENGINES["text"]
        self.stub = stub
        self.asked = asked
        self.monkeypatch = monkeypatch

    def answer(self, name, value):
        self.monkeypatch.setattr(self.engines[name], "search", self.stub(name, value))

    def test_ships_every_default_engine(self):
        assert set(SHIPPED_ORDER) <= set(self.engines)

    def test_one_engine_per_ddgs_call_and_the_first_answer_wins(self):
        self.answer("yahoo", True)

        result = ws.WebSearch().run(query="hotel")

        assert result.ok
        assert "(via yahoo)" in result.output
        assert "yahoo.example" in result.output
        assert self.asked == ["brave", "yahoo"]

    def test_an_empty_page_and_a_raised_timeout_are_told_apart(self):
        from ddgs.exceptions import TimeoutException

        self.answer("yahoo", TimeoutException("operation timed out"))
        self.answer("mojeek", True)

        result = ws.WebSearch().run(query="hotel")

        assert result.ok
        assert self.asked == ["brave", "yahoo", "startpage", "mojeek"]
        assert set(ws._cooldowns) == {"yahoo"}

    def test_an_engine_that_outlives_the_deadline_counts_as_a_timeout(self):
        self.answer("brave", 1.3)
        self.answer("yahoo", True)

        result = ws.WebSearch().run(query="hotel")

        assert result.ok
        assert set(ws._cooldowns) == {"brave"}

    def test_the_search_budget_holds_even_though_ddgs_joins_its_threads(self):
        self.monkeypatch.setattr(ws, "_CALL_BUDGET_S", 0.3)
        for name in self.engines:
            self.answer(name, 3.0)

        started = time.monotonic()
        result = ws.WebSearch().run(query="hotel")

        assert time.monotonic() - started < 1.0
        assert "asked brave: timeout" in result.error
        assert "yahoo (out of time)" in result.error

    def test_abandoned_requests_stay_bounded_across_searches(self):
        self.monkeypatch.setattr(ws, "_CALL_BUDGET_S", 0.3)
        self.monkeypatch.setattr(ws, "_raw_settings", lambda: {"backends": ["brave", "yahoo", "mojeek"]})
        live = {"now": 0, "max": 0, "per_engine": {}}
        guard = threading.Lock()
        release = threading.Event()

        def hanging(name):
            def search(_self, query, **_kwargs):
                with guard:
                    live["now"] += 1
                    live["max"] = max(live["max"], live["now"])
                    live["per_engine"][name] = live["per_engine"].get(name, 0) + 1
                release.wait(5)
                with guard:
                    live["now"] -= 1
                return None
            return search

        for name in ("brave", "yahoo", "mojeek"):
            self.monkeypatch.setattr(self.engines[name], "search", hanging(name))
        try:
            outcomes = [ws.WebSearch().run(query=f"q{i}") for i in range(4)]
        finally:
            release.set()

        assert live["max"] <= ws._MAX_LIVE_REQUESTS
        assert all(n == 1 for n in live["per_engine"].values())
        assert not any(r.ok for r in outcomes)
        assert "could not ask any engine" in outcomes[-1].error

    def test_a_failure_lists_the_real_outcomes(self):
        result = ws.WebSearch().run(query="hotel")

        assert result.ok
        assert "brave: empty" in result.output
        assert "wikipedia: empty" in result.output
