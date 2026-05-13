"""Unit tests for the `browser` tool. Playwright itself is mocked;
we only exercise dispatch, arg plumbing, and error paths."""

from __future__ import annotations

from unittest.mock import MagicMock

from alpi.tools import browser as browser_mod
from alpi.tools.browser import Browser


def _install_fake_page(monkeypatch, page: MagicMock) -> None:
    monkeypatch.setattr(browser_mod, "_ensure_page_blocking", lambda: (page, None))
    monkeypatch.setattr(browser_mod, "_on_browser_thread", lambda fn: fn())


def _install_import_error(monkeypatch) -> None:
    monkeypatch.setattr(
        browser_mod, "_ensure_page_blocking",
        lambda: (None, "playwright is not installed. Run: pip install playwright"),
    )
    monkeypatch.setattr(browser_mod, "_on_browser_thread", lambda fn: fn())


def test_schema_lists_all_actions() -> None:
    actions = Browser.parameters["properties"]["action"]["enum"]
    assert set(actions) == {
        "navigate", "snapshot", "click", "type",
        "scroll", "press", "screenshot",
        "close", "logout",
    }


def test_navigate_requires_url(monkeypatch) -> None:
    _install_fake_page(monkeypatch, MagicMock())
    r = Browser().run(action="navigate")
    assert not r.ok
    assert "url" in r.error.lower()


def test_navigate_blocks_ssrf(monkeypatch) -> None:
    _install_fake_page(monkeypatch, MagicMock())
    r = Browser().run(action="navigate", url="http://169.254.169.254/meta")
    assert not r.ok
    assert "blocked" in r.error.lower()


def test_navigate_happy_path(monkeypatch) -> None:
    page = MagicMock()
    page.locator.return_value.aria_snapshot.return_value = "- heading \"Hello\""
    page.url = "https://example.com/"
    _install_fake_page(monkeypatch, page)

    r = Browser().run(action="navigate", url="https://example.com")
    assert r.ok
    page.goto.assert_called_once_with("https://example.com", wait_until="domcontentloaded")
    assert "Hello" in r.output
    assert "https://example.com" in r.output


def test_click_needs_role_or_text(monkeypatch) -> None:
    _install_fake_page(monkeypatch, MagicMock())
    r = Browser().run(action="click")
    assert not r.ok
    assert "role" in r.error or "text" in r.error


def test_click_by_role_name(monkeypatch) -> None:
    page = MagicMock()
    page.locator.return_value.aria_snapshot.return_value = "- heading \"Hi\""
    page.url = "https://x.test/"
    _install_fake_page(monkeypatch, page)

    r = Browser().run(action="click", role="button", name="Submit")
    assert r.ok
    page.get_by_role.assert_called_once_with("button", name="Submit")
    page.get_by_role.return_value.first.click.assert_called_once()


def test_type_needs_text(monkeypatch) -> None:
    _install_fake_page(monkeypatch, MagicMock())
    r = Browser().run(action="type", role="textbox", name="Email")
    assert not r.ok
    assert "text" in r.error.lower()


def test_type_fills_input(monkeypatch) -> None:
    page = MagicMock()
    page.locator.return_value.aria_snapshot.return_value = "- textbox"
    page.url = "https://x.test/"
    _install_fake_page(monkeypatch, page)

    r = Browser().run(action="type", role="textbox", name="Email", text="a@b.com")
    assert r.ok
    target = page.get_by_role.return_value.first
    target.clear.assert_called_once()
    target.press_sequentially.assert_called_once()
    args, kwargs = target.press_sequentially.call_args
    assert args[0] == "a@b.com"
    assert 30 <= kwargs["delay"] <= 80


def test_human_typing_is_a_constant_not_a_config_knob(monkeypatch, tmp_path) -> None:
    """human_typing / typing_delay_ms are module constants; YAML overrides ignored."""
    import alpi.home as home_mod
    monkeypatch.setattr(home_mod, "_ROOT", tmp_path)
    (tmp_path / "config.yaml").write_text(
        "tools:\n  browser:\n    human_typing: false\n"
    )
    from alpi.tools.browser import HUMAN_TYPING, TYPING_DELAY_MS, _browser_typing_cfg
    assert HUMAN_TYPING is True
    assert TYPING_DELAY_MS == (30, 80)
    assert _browser_typing_cfg() == (True, [30, 80])


def test_scroll_calls_mouse_wheel(monkeypatch) -> None:
    page = MagicMock()
    page.locator.return_value.aria_snapshot.return_value = "- body"
    page.url = "https://x.test/"
    _install_fake_page(monkeypatch, page)

    r = Browser().run(action="scroll", direction="down")
    assert r.ok
    page.mouse.wheel.assert_called_once()
    dy = page.mouse.wheel.call_args.args[1]
    assert dy > 0


def test_scroll_up_negative_dy(monkeypatch) -> None:
    page = MagicMock()
    page.locator.return_value.aria_snapshot.return_value = "- body"
    page.url = "https://x.test/"
    _install_fake_page(monkeypatch, page)

    Browser().run(action="scroll", direction="up")
    dy = page.mouse.wheel.call_args.args[1]
    assert dy < 0


def test_press_needs_key(monkeypatch) -> None:
    _install_fake_page(monkeypatch, MagicMock())
    r = Browser().run(action="press")
    assert not r.ok
    assert "key" in r.error.lower()


def test_press_dispatches(monkeypatch) -> None:
    page = MagicMock()
    page.locator.return_value.aria_snapshot.return_value = "- body"
    page.url = "https://x.test/"
    _install_fake_page(monkeypatch, page)

    Browser().run(action="press", key="Enter")
    page.keyboard.press.assert_called_once_with("Enter")


def test_screenshot_returns_path(monkeypatch, tmp_path) -> None:
    page = MagicMock()
    _install_fake_page(monkeypatch, page)
    monkeypatch.setattr(browser_mod, "_storage_dir", lambda: tmp_path)

    r = Browser().run(action="screenshot")
    assert r.ok
    assert r.output.startswith(str(tmp_path))
    assert r.output.endswith(".png")
    page.screenshot.assert_called_once()


def test_screenshot_with_question_vision_disabled(monkeypatch, tmp_path) -> None:
    """When vision is off, question is ignored and a hint is appended."""
    page = MagicMock()
    _install_fake_page(monkeypatch, page)
    monkeypatch.setattr(browser_mod, "_storage_dir", lambda: tmp_path)
    monkeypatch.setattr(browser_mod, "_vision_enabled", lambda: False)

    r = Browser().run(action="screenshot", question="is the button visible?")
    assert r.ok
    assert ".png" in r.output
    assert "vision disabled" in r.output


def test_screenshot_with_question_vision_enabled(monkeypatch, tmp_path) -> None:
    """When vision is on, the screenshot is auto-analyzed."""
    from alpi.tools.base import ToolResult

    page = MagicMock()
    _install_fake_page(monkeypatch, page)
    monkeypatch.setattr(browser_mod, "_storage_dir", lambda: tmp_path)
    monkeypatch.setattr(browser_mod, "_vision_enabled", lambda: True)
    monkeypatch.setattr(
        browser_mod, "_analyze_screenshot",
        lambda path, q: ToolResult(ok=True, output=f"yes — saw '{q}'"),
    )

    r = Browser().run(action="screenshot", question="logged in?")
    assert r.ok
    assert "yes" in r.output
    assert "logged in?" in r.output


def test_logout_deletes_state_file(monkeypatch, tmp_path) -> None:
    state_file = tmp_path / "state.json"
    state_file.write_text("{}")
    monkeypatch.setattr(browser_mod, "_storage_dir", lambda: tmp_path)
    monkeypatch.setattr(browser_mod, "_on_browser_thread", lambda fn: fn())
    monkeypatch.setattr(browser_mod, "_close_blocking", lambda: None)

    r = Browser().run(action="logout")
    assert r.ok
    assert "deleted" in r.output.lower()
    assert not state_file.exists()


def test_logout_missing_state_file_is_ok(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(browser_mod, "_storage_dir", lambda: tmp_path)
    monkeypatch.setattr(browser_mod, "_on_browser_thread", lambda fn: fn())
    monkeypatch.setattr(browser_mod, "_close_blocking", lambda: None)

    r = Browser().run(action="logout")
    assert r.ok


def test_playwright_missing_yields_install_hint(monkeypatch) -> None:
    _install_import_error(monkeypatch)
    r = Browser().run(action="navigate", url="https://example.com")
    assert not r.ok
    assert "playwright" in r.error.lower()


def test_launch_chromium_installs_on_first_run(monkeypatch) -> None:
    """First launch raises ``Executable doesn't exist`` → tool calls
    ``python -m playwright install chromium`` and retries. The user
    never has to run that command manually; alpi handles it the first
    time the agent reaches for the browser."""
    calls = {"launch": 0, "subprocess": 0}

    class _FakeBrowser:
        pass

    fake_browser = _FakeBrowser()

    def fake_launch(*, headless):  # noqa: ARG001 — mirrors playwright signature
        calls["launch"] += 1
        if calls["launch"] == 1:
            raise RuntimeError(
                "Executable doesn't exist at /tmp/missing/chromium"
            )
        return fake_browser

    fake_pw = MagicMock()
    fake_pw.chromium.launch = fake_launch

    fake_run = MagicMock()

    def _fake_run(args, **_kw):
        calls["subprocess"] += 1
        # Sanity-check the command shape so a refactor that drops the
        # ``-m playwright install chromium`` invocation breaks loudly.
        assert "playwright" in args
        assert "install" in args
        assert "chromium" in args
        return fake_run

    # ``subprocess`` is imported lazily inside ``_launch_chromium``;
    # patching it on the canonical module is enough.
    import subprocess as _sub
    monkeypatch.setattr(_sub, "run", _fake_run)

    out = browser_mod._launch_chromium(fake_pw)
    assert out is fake_browser
    assert calls["launch"] == 2  # first raised, second succeeded
    assert calls["subprocess"] == 1


def test_launch_chromium_propagates_unrelated_errors(monkeypatch) -> None:
    """Errors that aren't about the missing executable should bubble
    up unchanged — JIT install is for "binary not present", not for
    swallowing every chromium failure."""
    fake_pw = MagicMock()
    fake_pw.chromium.launch.side_effect = RuntimeError("some other crash")

    import pytest
    with pytest.raises(RuntimeError, match="some other crash"):
        browser_mod._launch_chromium(fake_pw)
