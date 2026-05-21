"""TL.1 — tool availability probe layer.

Each `Tool` subclass can override `check() -> (available, reason)`. The
registry filters unavailable tools out of `schemas()` (so the LLM never
sees them) and exposes `availability_report()` for `alpi doctor`."""

from __future__ import annotations

import importlib

import pytest

from alpi import tools
from alpi.tools._availability import (
    invalidate,
    is_available,
)
from alpi.tools.base import Tool, ToolResult


@pytest.fixture(autouse=True)
def _clear_cache_each_test():
    invalidate()
    yield
    invalidate()


class _Dummy(Tool):
    name = "dummy_tool"
    description = "test fixture"
    parameters = {"type": "object", "properties": {}}

    def run(self, **_kwargs) -> ToolResult:  # noqa: D401
        return ToolResult(ok=True, output="ran")


def test_default_check_reports_available() -> None:
    ok, reason = _Dummy.check()
    assert ok is True
    assert reason == ""


def test_override_reporting_unavailable_propagates() -> None:
    class _NotInstalled(_Dummy):
        name = "missing"

        @classmethod
        def check(cls):
            return False, "fake-dep not installed"

    ok, reason = is_available(_NotInstalled)
    assert ok is False
    assert reason == "fake-dep not installed"


def test_is_available_caches_within_ttl(monkeypatch) -> None:
    calls = {"n": 0}

    class _Probed(_Dummy):
        name = "probed"

        @classmethod
        def check(cls):
            calls["n"] += 1
            return True, ""

    is_available(_Probed)
    is_available(_Probed)
    is_available(_Probed)
    assert calls["n"] == 1


def test_invalidate_forces_refresh() -> None:
    calls = {"n": 0}

    class _Refresh(_Dummy):
        name = "refresh"

        @classmethod
        def check(cls):
            calls["n"] += 1
            return True, ""

    is_available(_Refresh)
    invalidate()
    is_available(_Refresh)
    assert calls["n"] == 2


def test_check_raising_yields_unavailable_with_reason() -> None:
    class _Bad(_Dummy):
        name = "bad"

        @classmethod
        def check(cls):
            raise RuntimeError("boom")

    ok, reason = is_available(_Bad)
    assert ok is False
    assert "boom" in reason


def test_schemas_filters_unavailable_tools(monkeypatch) -> None:
    """schemas() is what the LLM sees — a tool reporting unavailable must
    NOT appear there. Patch one real tool's check to flip False, confirm it
    drops out of the schema list, then restore."""
    from alpi.tools import browser as browser_mod

    original = browser_mod.Browser.check
    try:
        browser_mod.Browser.check = classmethod(
            lambda _cls: (False, "fake: playwright missing")
        )
        invalidate()
        names = [s["function"]["name"] for s in tools.schemas()]
        assert "browser" not in names
    finally:
        browser_mod.Browser.check = original
        invalidate()


def test_schemas_includes_available_tools() -> None:
    names = [s["function"]["name"] for s in tools.schemas()]
    assert "memory" in names
    assert "read_file" in names


def test_availability_report_lists_every_registered_tool() -> None:
    """`alpi doctor` calls this — it must enumerate ALL registered tools,
    available or not, with their reasons. The cache is bypassed so the
    operator always sees fresh state."""
    report = tools.availability_report()
    names = [name for name, _ok, _reason in report]
    assert "memory" in names
    assert "browser" in names
    assert "stt" in names
    assert "tts" in names
    assert len(names) == len(set(names))


def test_availability_report_shape() -> None:
    """Every row is `(str, bool, str)` — that's the contract doctor and any
    future status surface relies on."""
    for entry in tools.availability_report():
        assert isinstance(entry, tuple) and len(entry) == 3
        name, ok, reason = entry
        assert isinstance(name, str) and name
        assert isinstance(ok, bool)
        assert isinstance(reason, str)


@pytest.mark.parametrize("tool_name, pkg", [
    ("browser", "playwright"),
    ("stt",     "faster_whisper"),
    ("tts",     "edge_tts"),
])
def test_heavy_dep_tools_report_missing_when_package_unimportable(
    monkeypatch, tool_name: str, pkg: str,
) -> None:
    """If the underlying package is missing, the tool's check() must report
    that — and use the package's display name in the reason so `alpi doctor`
    text is actionable."""
    cls = tools.get(tool_name)
    assert cls is not None
    real_find_spec = importlib.util.find_spec

    def _stub_find_spec(name, *a, **kw):
        if name == pkg:
            return None
        return real_find_spec(name, *a, **kw)

    monkeypatch.setattr(importlib.util, "find_spec", _stub_find_spec)
    ok, reason = cls.check()
    assert ok is False
    assert pkg.replace("_", "-") in reason


def test_execute_refuses_unavailable_tool(monkeypatch) -> None:
    """`execute()` is the runtime side of the same gate as `schemas()`. Stale
    sessions or sub-agents may try to call a tool whose check() now says
    unavailable; execute() must refuse cleanly instead of calling .run()."""
    from alpi.tools import browser as browser_mod

    original = browser_mod.Browser.check
    try:
        browser_mod.Browser.check = classmethod(
            lambda _cls: (False, "fake: playwright missing"),
        )
        invalidate()
        result = tools.execute("browser", {"action": "snapshot"})
        assert result.ok is False
        assert "unavailable" in (result.error or "")
        assert "playwright missing" in (result.error or "")
    finally:
        browser_mod.Browser.check = original
        invalidate()


@pytest.mark.parametrize("tool_name", ["browser", "stt", "tts"])
def test_heavy_dep_tools_report_available_on_full_install(tool_name: str) -> None:
    """All three are declared in `pyproject.toml` `dependencies`, so a
    normal install must report them available."""
    cls = tools.get(tool_name)
    assert cls is not None
    ok, _ = cls.check()
    assert ok is True
