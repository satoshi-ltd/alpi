"""Unit tests for the `browser` tool. Playwright itself is mocked;
we only exercise dispatch, arg plumbing, and error paths."""

from __future__ import annotations

import re
from unittest.mock import MagicMock

from alpi.tools import browser as browser_mod
from alpi.tools.browser import Browser


def _page(snapshot: str) -> MagicMock:
    page = MagicMock()
    page.aria_snapshot.return_value = snapshot
    page.evaluate.return_value = {"y": 0, "h": 720, "w": 1280, "total": 720}
    page.url = "https://x.test/"
    page.title.return_value = "Test page"
    return page


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
        "navigate", "snapshot", "find", "click", "hover", "type", "select", "upload",
        "press", "scroll", "back", "wait", "tab", "screenshot",
        "close", "logout", "trace_start", "trace_stop",
    }


def test_the_description_the_model_reads_every_turn_stays_small() -> None:
    assert len(Browser.description) < 2500


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
    page = _page('- heading "Hello" [level=1] [ref=e1] [box=0,0,100,20]')
    page.url = "https://example.com/"
    _install_fake_page(monkeypatch, page)

    r = Browser().run(action="navigate", url="https://example.com")
    assert r.ok
    page.goto.assert_called_once_with("https://example.com", wait_until="domcontentloaded")
    page.aria_snapshot.assert_called_with(mode="ai", boxes=True, timeout=5000)
    assert r.output == 'url: https://example.com/\ntitle: Test page\n\n- heading "Hello" [level=1]'


def test_click_needs_role_or_text(monkeypatch) -> None:
    _install_fake_page(monkeypatch, MagicMock())
    r = Browser().run(action="click")
    assert not r.ok
    assert "ref" in r.error and "role" in r.error and "text" in r.error


BUTTONS = (
    '- button "Submit" [ref=e2] [box=0,0,80,20]\n'
    '- button "Delete" [ref=e3] [box=0,30,80,20]\n'
    '- button "Delete" [ref=e4] [box=0,60,80,20]'
)


def test_click_by_role_name(monkeypatch) -> None:
    page = _page(BUTTONS)
    _install_fake_page(monkeypatch, page)

    r = Browser().run(action="click", role="button", name="Submit")
    assert r.ok
    page.get_by_ref.assert_called_once_with("e2")
    page.get_by_ref.return_value.click.assert_called_once()


def test_click_by_ref(monkeypatch) -> None:
    page = _page(BUTTONS)
    _install_fake_page(monkeypatch, page)

    assert Browser().run(action="click", ref="e4").ok
    page.get_by_ref.assert_called_once_with("e4")
    page.get_by_ref.return_value.click.assert_called_once()


def test_a_ref_that_is_not_in_the_page_is_refused_without_touching_it(monkeypatch) -> None:
    page = _page(BUTTONS)
    _install_fake_page(monkeypatch, page)

    r = Browser().run(action="click", ref="e9")
    assert not r.ok and "e9" in r.error
    assert 'button "Submit" [ref=e2]' in r.output
    page.get_by_ref.assert_not_called()


def test_several_elements_with_the_asked_role_and_name_are_listed_not_clicked(monkeypatch) -> None:
    page = _page(BUTTONS)
    _install_fake_page(monkeypatch, page)

    r = Browser().run(action="click", role="button", name="Delete")
    assert not r.ok and "2 elements match" in r.error
    assert r.output == '- button "Delete" [ref=e3]\n- button "Delete" [ref=e4]'
    page.get_by_ref.assert_not_called()
    page.get_by_role.assert_not_called()


def test_a_ref_is_refused_when_the_active_tab_is_not_the_one_last_shown(monkeypatch) -> None:
    shown, active = _page(BUTTONS), _page(BUTTONS)
    _install_fake_page(monkeypatch, active)
    monkeypatch.setitem(browser_mod._state, "context", MagicMock())
    monkeypatch.setitem(browser_mod._state, "viewed", shown)

    r = Browser().run(action="click", ref="e3")
    assert not r.ok and "active tab changed" in r.error
    active.get_by_ref.assert_not_called()
    assert browser_mod._state["viewed"] is active
    assert Browser().run(action="click", ref="e3").ok


def test_scroll_numbers_a_page_supplies_are_never_trusted_blindly(monkeypatch) -> None:
    page = _page(BUTTONS)
    page.viewport_size = {"width": 1280, "height": 720}
    for bad in ({"y": float("nan"), "total": 900.0}, {"y": -1.0, "total": 900.0}, {"y": 0.0, "total": float("inf")}, {"y": "x", "total": 1}, None):
        page.evaluate.return_value = bad
        assert browser_mod._metrics(page) is None
    page.evaluate.return_value = {"y": 10.0, "total": 5000.0, "h": -5, "w": 0}
    assert browser_mod._metrics(page) == {"y": 10.0, "total": 5000.0, "h": 720.0, "w": 1280.0}


def test_a_tab_title_cannot_forge_the_tabs_line(monkeypatch) -> None:
    tab = MagicMock()
    tab.title.return_value = 'x" | 2* "Bank'
    assert browser_mod._tab_title(tab) == "x' / 2* 'Bank"


def test_what_the_page_did_is_reported_even_when_the_action_fails(monkeypatch) -> None:
    page = _page(BUTTONS)
    _install_fake_page(monkeypatch, page)

    def goto(*args, **kwargs):
        browser_mod._state["events"].append('beforeunload dialog "" was dismissed')
        raise RuntimeError("net::ERR_ABORTED")

    page.goto.side_effect = goto
    r = Browser().run(action="navigate", url="https://example.com")
    assert not r.ok and "ERR_ABORTED" in r.error and "beforeunload dialog" in r.output


def test_a_dialog_is_dismissed_unless_the_action_accepts_it(monkeypatch) -> None:
    for policy, called in (("dismiss", "dismiss"), ("accept", "accept")):
        dialog = MagicMock()
        dialog.type, dialog.message = "confirm", 'Delete [ref=e1] "order"?'
        noted_before_answering = []
        getattr(dialog, called).side_effect = lambda: noted_before_answering.append(list(browser_mod._state["events"]))
        monkeypatch.setitem(browser_mod._state, "dialog", policy)
        monkeypatch.setitem(browser_mod._state, "events", [])
        browser_mod._on_dialog(dialog)
        getattr(dialog, called).assert_called_once()
        assert noted_before_answering[0][0].startswith("confirm dialog \"Delete [ref:e1] 'order'?\" was " + called[:6])


def test_press_and_scroll_refuse_a_tab_the_model_has_not_seen(monkeypatch) -> None:
    shown, active = _page(BUTTONS), _page(BUTTONS)
    _install_fake_page(monkeypatch, active)
    for action in ({"action": "press", "key": "Enter"}, {"action": "scroll"}):
        monkeypatch.setitem(browser_mod._state, "context", MagicMock())
        monkeypatch.setitem(browser_mod._state, "viewed", shown)
        r = Browser().run(**action)
        assert not r.ok and "active tab changed" in r.error
    active.keyboard.press.assert_not_called()
    active.mouse.wheel.assert_not_called()


def test_a_download_is_refused_when_the_turn_may_not_write_files(tmp_path, monkeypatch) -> None:
    from alpi.tools import _policy

    monkeypatch.setattr(browser_mod, "get_home", lambda: tmp_path)
    (tmp_path / "config.yaml").write_text("tools:\n  deny: []\n")
    assert browser_mod._write_file_denied() is False
    with _policy.use(["browser", "read_file"], "member"):
        assert browser_mod._write_file_denied() is True
    with _policy.use(["browser", "write_file"], "member"):
        assert browser_mod._write_file_denied() is False
    (tmp_path / "config.yaml").write_text("tools:\n  deny: [write_file]\n")
    assert browser_mod._write_file_denied() is True


def test_a_download_name_cannot_leave_the_folder_or_hide() -> None:
    assert browser_mod._safe_name("../../.env") == "env"
    assert browser_mod._safe_name("..\\..\\boot.ini") == "boot.ini"
    assert browser_mod._safe_name("inv oice (1).pdf") == "inv oice _1_.pdf"
    assert browser_mod._safe_name("") == browser_mod._safe_name(None) == browser_mod._safe_name("...") == "download"
    assert len(browser_mod._safe_name("a" * 400 + ".pdf")) == 120


def test_type_needs_text(monkeypatch) -> None:
    _install_fake_page(monkeypatch, MagicMock())
    r = Browser().run(action="type", role="textbox", name="Email")
    assert not r.ok
    assert "text" in r.error.lower()


def test_type_fills_input(monkeypatch) -> None:
    page = _page('- textbox "Email" [ref=e5] [box=0,0,200,20]')
    _install_fake_page(monkeypatch, page)

    r = Browser().run(action="type", role="textbox", name="Email", text="a@b.com")
    assert r.ok
    page.get_by_ref.assert_called_once_with("e5")
    target = page.get_by_ref.return_value
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


def test_scroll_moves_less_than_a_screen_so_views_overlap(monkeypatch) -> None:
    page = _page('- heading "Hi" [ref=e1]')
    _install_fake_page(monkeypatch, page)

    assert Browser().run(action="scroll", direction="down").ok
    assert 0 < page.mouse.wheel.call_args.args[1] < 720
    Browser().run(action="scroll", direction="up")
    assert -720 < page.mouse.wheel.call_args.args[1] < 0


def test_press_needs_key(monkeypatch) -> None:
    _install_fake_page(monkeypatch, MagicMock())
    r = Browser().run(action="press")
    assert not r.ok
    assert "key" in r.error.lower()


def test_press_dispatches(monkeypatch) -> None:
    page = _page('- heading "Hi" [ref=e1]')
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


def test_check_reports_missing_chromium_libs(monkeypatch) -> None:
    monkeypatch.setattr(
        browser_mod, "missing_chromium_libs",
        lambda: ["libgbm.so.1", "libnss3.so"],
    )
    ok, reason = Browser.check()
    assert ok is False
    assert "libgbm.so.1" in reason
    assert "install-deps chromium" in reason


def test_check_available_when_libs_resolve(monkeypatch) -> None:
    monkeypatch.setattr(browser_mod, "missing_chromium_libs", lambda: [])
    assert Browser.check() == (True, "")


def test_check_reports_missing_playwright_before_probing_libs(monkeypatch) -> None:
    import importlib.util
    monkeypatch.setattr(importlib.util, "find_spec", lambda _name: None)

    def _boom() -> list[str]:
        raise AssertionError("libs must not be probed without playwright")

    monkeypatch.setattr(browser_mod, "missing_chromium_libs", _boom)
    ok, reason = Browser.check()
    assert ok is False
    assert reason == "playwright not installed"


def test_missing_chromium_libs_is_linux_only(monkeypatch) -> None:
    import ctypes
    monkeypatch.setattr("sys.platform", "darwin")

    def _boom(_name):
        raise AssertionError("dlopen must not run off Linux")

    monkeypatch.setattr(ctypes, "CDLL", _boom)
    assert browser_mod.missing_chromium_libs() == []


def test_missing_chromium_libs_collects_unloadable_sonames(monkeypatch) -> None:
    import ctypes
    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.setattr(
        ctypes, "CDLL",
        lambda name: (_ for _ in ()).throw(OSError(name))
        if name == "libgbm.so.1" else object(),
    )
    assert browser_mod.missing_chromium_libs() == ["libgbm.so.1"]


# The bug this guards: the image shipped Chromium's downloader but never its libraries, so `browser` was advertised and could never launch. Assert the mechanism, not a copy of the package list — a second hand-written list would only prove it matches itself, and `pip install .` ignores uv.lock so the image's playwright can outrun the suite's.
def test_docker_image_derives_chromium_deps_from_playwright() -> None:
    from pathlib import Path

    dockerfile = (
        Path(__file__).resolve().parents[2] / "docker" / "Dockerfile"
    ).read_text(encoding="utf-8")

    assert "playwright install-deps chromium-headless-shell" in dockerfile
    hand_rolled = [
        line for line in dockerfile.splitlines()
        if re.search(r"^\s+lib\S+\s*\\?$", line)
    ]
    assert not hand_rolled, f"hand-written chromium libs reintroduced: {hand_rolled}"


def test_repair_command_is_reachable_from_a_uv_tool_install(monkeypatch) -> None:
    monkeypatch.setattr(browser_mod, "missing_chromium_libs", lambda: ["libgbm.so.1"])
    _ok, reason = Browser.check()
    # uv tool installs only link alpi-agent's own entry points, so a bare `playwright ...` is command-not-found for the documented install path.
    assert "uvx --from playwright" in reason
    assert not re.search(r"run: playwright\b", reason)
