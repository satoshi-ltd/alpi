"""Unit tests for ``alpi.tools.web_search``.

We mock the ``ddgs`` backend so the tests don't hit the network and
don't depend on DDG's current behaviour. The goal is to exercise our
own plumbing:

- safesearch is pinned to ``moderate`` (not left to the backend default)
- dedup collapses multiple hits from the same host
- zero-results returns a clean message instead of an error

The "query in English by default" guidance lives in the tool
description, not in code — it's instructions to the LLM. No unit test
can exercise it without running an actual agent loop; it's covered in
manual smoke tests.
"""

from __future__ import annotations

import contextvars
import sys
import time
import threading
from types import SimpleNamespace

import pytest

from alpi.tools import web_search as ws


@pytest.fixture(autouse=True)
def _quiet_state(monkeypatch):
    """``emit_state`` writes to the global event bus. Silence it so the
    tests don't need to mount a fake event sink."""
    monkeypatch.setattr("alpi.tools._state.emit_state", lambda *_a, **_kw: None)


@pytest.fixture(autouse=True)
def _no_waiting(monkeypatch):
    """Zero the pacing clock and the retry backoff, and drop the per-turn
    tally — otherwise every test pays real seconds."""
    from alpi.tools import _state

    monkeypatch.setattr(ws, "_MIN_INTERVAL_S", 0.0)
    monkeypatch.setattr(ws, "_RETRY_BACKOFF_S", 0.0)
    monkeypatch.setattr(ws, "_last_started", 0.0)
    _state.reset_turn_usage()


def _fake_ddgs(results):
    """Build a context-manager class whose ``.text(...)`` returns ``results``.

    Single call per test is enough now — the regional escalation that
    needed multi-call sequencing is gone.
    """
    class _FakeContext:
        def __init__(self):
            self.calls: list[dict] = []

        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

        def text(self, query, **kwargs):
            self.calls.append({"query": query, **kwargs})
            return list(results)

    return _FakeContext


def test_safesearch_pinned(monkeypatch):
    """Every DDG call must carry ``safesearch="moderate"`` explicitly.

    The backend default has drifted across ``ddgs`` releases; pinning
    it here means a ``pip upgrade`` can't silently change what users
    see.
    """
    fake = _fake_ddgs([{"title": "T", "href": "https://example.com", "body": "B"}])
    instance = fake()
    monkeypatch.setitem(sys.modules, "ddgs", SimpleNamespace(DDGS=lambda: instance))

    tool = ws.WebSearch()
    result = tool.run(query="anything")

    assert result.ok
    assert instance.calls[0]["safesearch"] == "moderate"


def test_zero_results_is_ok_not_error(monkeypatch):
    """An empty result set is a legitimate answer, not a tool error.

    If we returned ``ok=False`` here, the LLM would treat an obscure
    query ("zzxyq") as a transient failure and loop reformulating —
    burning turns for no reason. Empty is a signal, not a crash.
    """
    fake = _fake_ddgs([])
    instance = fake()
    monkeypatch.setitem(sys.modules, "ddgs", SimpleNamespace(DDGS=lambda: instance))

    tool = ws.WebSearch()
    result = tool.run(query="zzxyq nonsense")

    assert result.ok
    assert "no results" in result.output
    assert len(instance.calls) == 1


def test_dedup_caps_per_domain(monkeypatch):
    """Four Reddit hits collapse to two; other domains preserved.

    DDG routinely floods the first page with 3-5 Reddit threads or
    StackOverflow questions when the query matches a popular thread
    pattern. Those later hits rarely add signal and push genuinely
    diverse sources off the list the LLM sees.
    """
    results = [
        {"title": "r1", "href": "https://reddit.com/a", "body": "b1"},
        {"title": "r2", "href": "https://reddit.com/b", "body": "b2"},
        {"title": "r3", "href": "https://www.reddit.com/c", "body": "b3"},
        {"title": "r4", "href": "https://reddit.com/d", "body": "b4"},
        {"title": "so", "href": "https://stackoverflow.com/q/1", "body": "b"},
        {"title": "wiki", "href": "https://en.wikipedia.org/wiki/X", "body": "b"},
    ]
    fake = _fake_ddgs(results)
    instance = fake()
    monkeypatch.setitem(sys.modules, "ddgs", SimpleNamespace(DDGS=lambda: instance))

    tool = ws.WebSearch()
    result = tool.run(query="anything", max_results=10)
    out = result.output

    assert result.ok
    # First two Reddit hits kept, the next two dropped (cap=2). ``www.``
    # normalisation means the third reddit hit counts against the same
    # bucket as the first two.
    assert "r1" in out and "r2" in out
    assert "r3" not in out and "r4" not in out
    # Unrelated domains untouched.
    assert "so" in out and "wiki" in out


def test_backend_exception_becomes_error(monkeypatch):
    """When ``ddgs`` raises (network blip, quota, whatever), the tool
    surfaces an ``ok=False`` so the LLM can react — retry, give up,
    tell the user — instead of getting a silent empty page that looks
    identical to "nothing matches your query"."""
    class _Raising:
        def __enter__(self): return self
        def __exit__(self, *_a): return False
        def text(self, *_a, **_kw):
            raise RuntimeError("ddgs exploded")

    monkeypatch.setitem(sys.modules, "ddgs", SimpleNamespace(DDGS=_Raising))

    tool = ws.WebSearch()
    result = tool.run(query="anything")

    assert not result.ok
    assert "search failed" in result.error


def test_retry_runs_once_then_reports_the_real_exception(monkeypatch):
    """The old code swallowed the exception and said "the ddgs backend
    raised", so the model retried blindly into an IP-wide block and the
    logs carried nothing to diagnose. One retry, then the exception type
    and message reach both."""
    calls = {"n": 0}

    class _Raising:
        def __enter__(self): return self
        def __exit__(self, *_a): return False
        def text(self, *_a, **_kw):
            calls["n"] += 1
            raise RuntimeError("Ratelimit 429")

    monkeypatch.setitem(sys.modules, "ddgs", SimpleNamespace(DDGS=_Raising))

    result = ws.WebSearch().run(query="anything")

    assert not result.ok
    assert calls["n"] == 2
    assert "RuntimeError: Ratelimit 429" in result.error
    assert "do NOT reformulate" in result.error


def test_retry_recovers_when_the_second_attempt_succeeds(monkeypatch):
    calls = {"n": 0}

    class _FlakyOnce:
        def __enter__(self): return self
        def __exit__(self, *_a): return False
        def text(self, *_a, **_kw):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("transient")
            return [{"title": "T", "href": "https://example.com", "body": "B"}]

    monkeypatch.setitem(sys.modules, "ddgs", SimpleNamespace(DDGS=_FlakyOnce))

    result = ws.WebSearch().run(query="anything")

    assert result.ok
    assert calls["n"] == 2
    assert "example.com" in result.output


def test_turn_budget_stops_calling_the_backend(monkeypatch):
    calls = {"n": 0}

    class _Counting:
        def __enter__(self): return self
        def __exit__(self, *_a): return False
        def text(self, *_a, **_kw):
            calls["n"] += 1
            return []

    monkeypatch.setitem(sys.modules, "ddgs", SimpleNamespace(DDGS=_Counting))
    monkeypatch.setattr(ws, "_max_per_turn", lambda: 3)

    outcomes = [ws.WebSearch().run(query=f"q{i}") for i in range(5)]

    assert calls["n"] == 3
    assert all(r.ok for r in outcomes[:3])
    assert all(not r.ok for r in outcomes[3:])
    assert "budget for this turn is spent" in outcomes[4].error
    assert "web_fetch" in outcomes[4].error


def test_budget_is_per_turn_not_per_process(monkeypatch):
    class _Empty:
        def __enter__(self): return self
        def __exit__(self, *_a): return False
        def text(self, *_a, **_kw): return []

    monkeypatch.setitem(sys.modules, "ddgs", SimpleNamespace(DDGS=_Empty))
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
    """ddgs fans one query out to several engines, so overlapping calls
    multiply upstream requests and are what tips the shared IP into a
    rate limit that lasts minutes."""
    import threading

    live = {"now": 0, "max": 0}
    seen = threading.Lock()

    class _Slow:
        def __enter__(self): return self
        def __exit__(self, *_a): return False
        def text(self, *_a, **_kw):
            with seen:
                live["now"] += 1
                live["max"] = max(live["max"], live["now"])
            time.sleep(0.05)
            with seen:
                live["now"] -= 1
            return []

    monkeypatch.setitem(sys.modules, "ddgs", SimpleNamespace(DDGS=_Slow))

    threads = [
        threading.Thread(target=lambda i=i: ws.WebSearch().run(query=f"q{i}"))
        for i in range(4)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert live["max"] == 1


def test_calls_are_spaced_apart(monkeypatch):
    class _Empty:
        def __enter__(self): return self
        def __exit__(self, *_a): return False
        def text(self, *_a, **_kw): return []

    monkeypatch.setitem(sys.modules, "ddgs", SimpleNamespace(DDGS=_Empty))
    monkeypatch.setattr(ws, "_MIN_INTERVAL_S", 0.2)

    started = time.monotonic()
    for i in range(3):
        ws.WebSearch().run(query=f"q{i}")
    assert time.monotonic() - started >= 0.4


def test_retry_and_following_search_are_each_spaced(monkeypatch):
    attempts = {"n": 0}

    class _FailsOnce:
        def __enter__(self): return self
        def __exit__(self, *_a): return False
        def text(self, *_a, **_kw):
            attempts["n"] += 1
            if attempts["n"] == 1:
                raise RuntimeError("transient")
            return []

    monkeypatch.setitem(sys.modules, "ddgs", SimpleNamespace(DDGS=_FailsOnce))
    monkeypatch.setattr(ws, "_MIN_INTERVAL_S", 0.1)

    started = time.monotonic()
    assert ws.WebSearch().run(query="first").ok
    assert ws.WebSearch().run(query="second").ok

    assert attempts["n"] == 3
    assert time.monotonic() - started >= 0.2
