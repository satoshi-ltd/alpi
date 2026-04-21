"""Unit tests for ``alf.tools.web_search``.

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

import sys
from types import SimpleNamespace

import pytest

from alpi.tools import web_search as ws


@pytest.fixture(autouse=True)
def _quiet_state(monkeypatch):
    """``emit_state`` writes to the global event bus. Silence it so the
    tests don't need to mount a fake event sink."""
    monkeypatch.setattr("alpi.tools._state.emit_state", lambda *_a, **_kw: None)


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
