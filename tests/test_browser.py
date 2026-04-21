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
    page.get_by_role.return_value.first.fill.assert_called_once_with("a@b.com")


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
