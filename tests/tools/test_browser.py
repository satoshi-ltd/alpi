"""Unit tests for the `browser` tool. Playwright itself is mocked;
we only exercise dispatch, arg plumbing, and error paths."""

from __future__ import annotations

import re
from unittest.mock import MagicMock

import pytest

from alpi.tools import browser as browser_mod
from alpi.tools.browser import Browser


@pytest.fixture(autouse=True)
def _no_session_left_over(monkeypatch):
    for key, value in browser_mod._fresh().items():
        monkeypatch.setitem(browser_mod._state, key, value)
    monkeypatch.setattr(browser_mod, "_parked", {})
    monkeypatch.setattr(browser_mod, "_lost", {})
    monkeypatch.setitem(browser_mod._state, "dead", False)


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
        browser_mod._on_dialog(browser_mod._state["home"], dialog)
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


def test_logout_that_cannot_delete_the_saved_session_says_it_is_still_there(monkeypatch, tmp_path) -> None:
    from pathlib import Path

    state_file = tmp_path / "state.json"
    state_file.write_text('{"per_profile": true, "cookies": [], "origins": []}')
    (tmp_path / "state.json.shared").write_text("older")
    monkeypatch.setattr(browser_mod, "_storage_dir", lambda: tmp_path)
    monkeypatch.setattr(browser_mod, "_on_browser_thread", lambda fn: fn())
    monkeypatch.setattr(browser_mod, "_close_blocking", lambda: None)
    unlink = Path.unlink

    def refuse(self, *args, **kwargs):
        if self.name == "state.json":
            raise PermissionError(13, "Permission denied")
        return unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", refuse)

    r = Browser().run(action="logout")

    assert not r.ok
    assert "could not be deleted: browser/state.json (Permission denied)" in r.error and "still on disk" in r.error
    assert "state.json.shared" not in r.error
    assert state_file.exists() and not (tmp_path / "state.json.shared").exists()


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


def _open_session(monkeypatch, home) -> MagicMock:
    context = MagicMock()
    browser_mod._activate(home)
    monkeypatch.setitem(browser_mod._state, "context", context)
    monkeypatch.setitem(browser_mod._state, "page", MagicMock())
    return context


def test_each_home_gets_its_own_session_and_finds_it_again(monkeypatch, tmp_path) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    monkeypatch.setitem(browser_mod._state, "browser", MagicMock())
    context_one = _open_session(monkeypatch, first)
    page_one = browser_mod._state["page"]
    browser_mod._state["events"].append("note of the first profile")

    browser_mod._activate(second)

    assert browser_mod._state["home"] == second
    assert browser_mod._state["context"] is None and browser_mod._state["page"] is None
    assert browser_mod._state["events"] == []
    assert browser_mod._state["browser"] is not None
    assert browser_mod._session(first)["context"] is context_one

    browser_mod._activate(first)

    assert browser_mod._state["page"] is page_one
    assert browser_mod._state["events"] == ["note of the first profile"]
    assert browser_mod._parked == {}


def test_a_page_event_of_a_profile_that_is_not_being_served_stays_with_that_profile(monkeypatch, tmp_path) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    monkeypatch.setitem(browser_mod._state, "browser", MagicMock())
    _open_session(monkeypatch, first)
    browser_mod._activate(second)
    served_page = MagicMock()
    monkeypatch.setitem(browser_mod._state, "context", MagicMock())
    monkeypatch.setitem(browser_mod._state, "page", served_page)
    monkeypatch.setitem(browser_mod._state, "dialog", "accept")
    popup, download, request, dialog = MagicMock(), MagicMock(), MagicMock(), MagicMock()
    request.resource_type = "fetch"
    dialog.type, dialog.message = "confirm", "Pay now?"

    browser_mod._on_page(first, popup)
    browser_mod._on_download(first, download)
    browser_mod._on_request(first, request)
    browser_mod._on_dialog(first, dialog)

    assert browser_mod._state["page"] is served_page
    assert browser_mod._state["downloads"] == [] and browser_mod._state["inflight"] == set()
    assert browser_mod._state["events"] == []
    dialog.dismiss.assert_called_once()
    dialog.accept.assert_not_called()
    parked = browser_mod._session(first)
    assert parked["page"] is popup and parked["downloads"] == [download] and parked["inflight"] == {request}


def test_an_event_for_a_profile_whose_session_is_gone_is_dropped(monkeypatch, tmp_path) -> None:
    browser_mod._activate(tmp_path / "served")
    download, dialog = MagicMock(), MagicMock()
    dialog.type, dialog.message = "alert", "hello"

    browser_mod._on_download(tmp_path / "gone", download)
    browser_mod._on_dialog(tmp_path / "gone", dialog)
    browser_mod._on_page(tmp_path / "gone", MagicMock())
    browser_mod._on_request(tmp_path / "gone", MagicMock())

    download.cancel.assert_called_once()
    dialog.dismiss.assert_called_once()
    assert browser_mod._state["downloads"] == [] and browser_mod._state["events"] == []


def test_closing_one_profile_keeps_the_browser_while_another_still_uses_it(monkeypatch, tmp_path) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    shared = MagicMock()
    monkeypatch.setitem(browser_mod._state, "browser", shared)
    monkeypatch.setitem(browser_mod._state, "playwright", MagicMock())
    context_one = _open_session(monkeypatch, first)
    browser_mod._activate(second)
    context_two = MagicMock()
    monkeypatch.setitem(browser_mod._state, "context", context_two)

    browser_mod._close_blocking()

    context_two.close.assert_called_once()
    context_one.close.assert_not_called()
    shared.close.assert_not_called()
    assert browser_mod._state["browser"] is shared

    browser_mod._activate(first)
    browser_mod._close_blocking()

    context_one.close.assert_called_once()
    shared.close.assert_called_once()
    assert browser_mod._state["browser"] is None and browser_mod._state["playwright"] is None


def test_the_error_of_an_action_carries_the_notes_of_its_own_profile(monkeypatch, tmp_path) -> None:
    page = _page(BUTTONS)
    _install_fake_page(monkeypatch, page)

    def fail(*args, **kwargs):
        browser_mod._state["events"].append("confirm dialog \"Leave?\" was dismissed")
        raise RuntimeError("page crashed")

    page.get_by_ref.return_value.click.side_effect = fail
    r = Browser().run(action="click", ref="e2")

    assert not r.ok and r.error == "RuntimeError: page crashed"
    assert r.output == 'confirm dialog "Leave?" was dismissed'


def test_cookies_are_written_when_they_change_and_the_rest_of_the_storage_on_close(monkeypatch, tmp_path) -> None:
    import json

    context = MagicMock()
    context.cookies.return_value = [{"name": "sid", "value": "1"}]
    context.storage_state.return_value = {"cookies": [{"name": "sid", "value": "3"}], "origins": [{"origin": "https://b.test"}]}
    monkeypatch.setitem(browser_mod._state, "home", tmp_path)
    monkeypatch.setitem(browser_mod._state, "context", context)
    monkeypatch.setitem(browser_mod._state, "cookies", "[]")
    monkeypatch.setitem(browser_mod._state, "origins", [{"origin": "https://a.test"}])
    state_file = tmp_path / "browser" / "state.json"

    browser_mod._save_state()

    assert json.loads(state_file.read_text()) == {
        "per_profile": True, "cookies": [{"name": "sid", "value": "1"}], "origins": [{"origin": "https://a.test"}],
    }
    assert state_file.stat().st_mode & 0o777 == 0o600
    written = state_file.stat().st_mtime_ns

    browser_mod._save_state()
    assert state_file.stat().st_mtime_ns == written

    context.cookies.return_value = [{"name": "sid", "value": "2"}]
    browser_mod._save_state()
    assert json.loads(state_file.read_text())["cookies"] == [{"name": "sid", "value": "2"}]
    context.storage_state.assert_not_called()

    browser_mod._save_state(full=True)
    assert json.loads(state_file.read_text()) == {
        "per_profile": True, "cookies": [{"name": "sid", "value": "3"}], "origins": [{"origin": "https://b.test"}],
    }
    assert context.storage_state.call_count == 1


def test_a_browser_that_died_is_started_again_for_every_profile(monkeypatch, tmp_path) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    dead = MagicMock()
    dead.is_connected.return_value = False
    monkeypatch.setitem(browser_mod._state, "browser", dead)
    monkeypatch.setitem(browser_mod._state, "playwright", MagicMock())
    _open_session(monkeypatch, first)
    recording = MagicMock()
    monkeypatch.setitem(browser_mod._state, "trace", recording)
    browser_mod._activate(second)
    monkeypatch.setitem(browser_mod._state, "context", MagicMock())
    monkeypatch.setitem(browser_mod._state, "page", MagicMock())

    browser_mod._forget_dead_browser()

    assert browser_mod._parked == {}
    assert browser_mod._state["home"] == second
    assert browser_mod._state["browser"] is None and browser_mod._state["context"] is None and browser_mod._state["page"] is None
    assert "started again" in browser_mod._state["events"][0]
    recording.close.assert_called_once()


def test_a_live_browser_is_left_alone(monkeypatch, tmp_path) -> None:
    alive = MagicMock()
    alive.is_connected.return_value = True
    page = MagicMock()
    monkeypatch.setitem(browser_mod._state, "browser", alive)
    monkeypatch.setitem(browser_mod._state, "page", page)

    browser_mod._forget_dead_browser()

    assert browser_mod._state["browser"] is alive and browser_mod._state["page"] is page
    assert browser_mod._state["events"] == []


def test_a_note_recorded_while_the_profile_was_not_served_reaches_its_next_result(monkeypatch) -> None:
    page = _page(BUTTONS)
    _install_fake_page(monkeypatch, page)
    browser_mod._state["events"].append('confirm dialog "Pay now?" was dismissed')

    first = Browser().run(action="snapshot")
    second = Browser().run(action="snapshot")

    assert 'confirm dialog "Pay now?" was dismissed' in first.output
    assert "Pay now" not in second.output


def test_a_refused_call_does_not_wait_for_the_browser_when_nothing_is_recorded(monkeypatch) -> None:
    reached = []
    monkeypatch.setattr(browser_mod, "_on_browser_thread", lambda fn: reached.append(fn) or fn())

    result = Browser().run(action="navigate")

    assert not result.ok and reached == []


def test_a_browser_that_cannot_report_its_state_does_not_fail_the_action(monkeypatch, tmp_path) -> None:
    context = MagicMock()
    context.cookies.side_effect = RuntimeError("target closed")
    monkeypatch.setitem(browser_mod._state, "home", tmp_path)
    monkeypatch.setitem(browser_mod._state, "context", context)

    browser_mod._save_state()

    assert not (tmp_path / "browser" / "state.json").exists()


def test_every_profile_that_lost_its_pages_is_told_on_its_next_use(monkeypatch, tmp_path) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    dead = MagicMock()
    dead.is_connected.return_value = False
    monkeypatch.setitem(browser_mod._state, "browser", dead)
    _open_session(monkeypatch, first)
    monkeypatch.setitem(browser_mod._state, "trace", MagicMock())
    browser_mod._activate(second)
    monkeypatch.setitem(browser_mod._state, "context", MagicMock())

    browser_mod._forget_dead_browser()

    assert browser_mod._state["events"] == [browser_mod._GONE]
    assert browser_mod._lost == {first: browser_mod._GONE + "; the trace that was recording was saved incomplete"}


def test_a_driver_that_died_is_noticed_although_the_browser_still_looks_connected(monkeypatch) -> None:
    class TargetClosedError(Exception):
        pass

    page = _page(BUTTONS)
    _install_fake_page(monkeypatch, page)
    looks_alive = MagicMock()
    looks_alive.is_connected.return_value = True
    looks_alive.new_context.side_effect = TargetClosedError("Playwright connection closed")
    monkeypatch.setitem(browser_mod._state, "browser", looks_alive)
    page.aria_snapshot.side_effect = TargetClosedError("Playwright connection closed")

    r = Browser().run(action="snapshot")

    assert not r.ok and "the browser stopped; repeat the action" in r.error
    assert browser_mod._state["dead"] is True
    browser_mod._forget_dead_browser()
    assert browser_mod._state["browser"] is None and browser_mod._state["dead"] is False


def test_a_page_that_closed_under_an_action_does_not_condemn_a_working_browser(monkeypatch) -> None:
    class TargetClosedError(Exception):
        pass

    page = _page(BUTTONS)
    _install_fake_page(monkeypatch, page)
    monkeypatch.setitem(browser_mod._state, "browser", MagicMock())
    page.aria_snapshot.side_effect = TargetClosedError("Target page, context or browser has been closed")

    r = Browser().run(action="snapshot")

    assert not r.ok and "the browser stopped" not in r.error
    assert browser_mod._state["dead"] is False


def test_a_failed_action_does_not_read_the_cookies_of_a_browser_that_may_be_frozen(monkeypatch) -> None:
    page = _page(BUTTONS)
    _install_fake_page(monkeypatch, page)
    context = MagicMock()
    monkeypatch.setitem(browser_mod._state, "context", context)
    page.get_by_ref.return_value.click.side_effect = TimeoutError("Timeout 10000ms exceeded")

    assert not Browser().run(action="click", ref="e2").ok
    context.cookies.assert_not_called()

    page.get_by_ref.return_value.click.side_effect = None
    assert Browser().run(action="click", ref="e2").ok
    context.cookies.assert_called()


def test_a_note_waits_for_a_result_that_prints_it(monkeypatch, tmp_path) -> None:
    page = _page(BUTTONS)
    _install_fake_page(monkeypatch, page)
    monkeypatch.setattr(browser_mod, "_storage_dir", lambda: tmp_path)
    browser_mod._state["events"].append('confirm dialog "Pay now?" was dismissed')

    shot = Browser().run(action="screenshot")
    view = Browser().run(action="snapshot")

    assert shot.ok and "Pay now" not in shot.output
    assert 'confirm dialog "Pay now?" was dismissed' in view.output
    assert browser_mod._state["events"] == []


def test_notes_are_capped_and_a_repeated_one_is_said_once() -> None:
    for _ in range(5):
        browser_mod._note("alert dialog \"again\" was dismissed")
    assert browser_mod._state["events"] == ['alert dialog "again" was dismissed']
    for index in range(60):
        browser_mod._note(f"note {index}")
    assert browser_mod._state["events"] == [f"note {index}" for index in range(40, 60)]


def test_an_action_that_answers_with_a_failure_does_not_read_the_cookies_either(monkeypatch) -> None:
    page = _page(BUTTONS)
    _install_fake_page(monkeypatch, page)
    monkeypatch.setattr(browser_mod, "_WAIT_MAX_MS", 0)
    context = MagicMock()
    monkeypatch.setitem(browser_mod._state, "context", context)

    r = Browser().run(action="wait", text="Never there")

    assert not r.ok and "did not appear" in r.error
    context.cookies.assert_not_called()


def test_the_first_error_after_the_driver_dies_is_recognised_too(monkeypatch) -> None:
    page = _page(BUTTONS)
    _install_fake_page(monkeypatch, page)
    looks_alive = MagicMock()
    looks_alive.is_connected.return_value = True
    looks_alive.new_context.side_effect = Exception("Connection closed while reading from the driver")
    monkeypatch.setitem(browser_mod._state, "browser", looks_alive)
    monkeypatch.setitem(browser_mod._state, "context", MagicMock())
    page.main_frame = "main"
    monkeypatch.setitem(browser_mod._state, "stalled", {"main"})
    page.aria_snapshot.side_effect = Exception("Page.aria_snapshot: Connection closed while reading from the driver")

    r = Browser().run(action="snapshot")

    assert not r.ok and "the browser stopped; repeat the action" in r.error
    assert browser_mod._state["dead"] is True


def test_a_profile_that_had_no_pages_is_not_told_it_lost_them(monkeypatch, tmp_path) -> None:
    dead = MagicMock()
    dead.is_connected.return_value = False
    monkeypatch.setitem(browser_mod._state, "browser", dead)
    _open_session(monkeypatch, tmp_path / "first")
    browser_mod._activate(tmp_path / "newcomer")

    browser_mod._forget_dead_browser()

    assert browser_mod._state["events"] == []
    assert list(browser_mod._lost) == [tmp_path / "first"]


def test_a_session_saved_before_profiles_were_separated_is_told_apart(tmp_path) -> None:
    import json

    cookies = [{"name": "sid", "value": "1"}]
    old, new = tmp_path / "old.json", tmp_path / "new.json"
    old.write_text(json.dumps({"cookies": cookies, "origins": []}))
    new.write_text(json.dumps({"per_profile": True, "cookies": cookies, "origins": []}))

    assert browser_mod._saved_session(old) == {"cookies": cookies, "origins": [], "per_profile": False}
    assert browser_mod._saved_session(new) == {"cookies": cookies, "origins": [], "per_profile": True}
    old.write_text(json.dumps({"per_profile": "yes", "cookies": cookies}))
    assert browser_mod._saved_session(old)["per_profile"] is False


def test_two_profiles_that_use_the_browser_first_at_the_same_moment_share_one_thread(monkeypatch) -> None:
    import queue
    import threading
    import time

    monkeypatch.setattr(browser_mod, "_jobs", None)
    made = []
    real_queue = queue.SimpleQueue
    callers = []

    def slow_queue():
        if threading.current_thread() not in callers:
            return real_queue()
        time.sleep(0.2)
        made.append(real_queue())
        return made[-1]

    monkeypatch.setattr(browser_mod.queue, "SimpleQueue", slow_queue)
    go = threading.Barrier(2)
    ran_on = []

    def first_use():
        go.wait(5)
        ran_on.append(browser_mod._on_browser_thread(threading.get_ident))

    callers.extend(threading.Thread(target=first_use) for _ in range(2))
    for caller in callers:
        caller.start()
    for caller in callers:
        caller.join(10)
    for jobs in made:
        jobs.put(None)

    assert len(made) == 1
    assert len(ran_on) == 2 and ran_on[0] == ran_on[1] != threading.get_ident()


def test_a_browser_thread_that_could_not_start_is_started_by_the_next_call(monkeypatch) -> None:
    import threading

    monkeypatch.setattr(browser_mod, "_jobs", None)
    real_thread = threading.Thread
    refused = []

    def no_thread_once(*args, **kwargs):
        if not refused and kwargs.get("name") == "alpi-browser":
            refused.append(True)
            raise RuntimeError("can't start new thread")
        return real_thread(*args, **kwargs)

    monkeypatch.setattr(browser_mod.threading, "Thread", no_thread_once)

    with pytest.raises(RuntimeError, match="can't start new thread"):
        browser_mod._on_browser_thread(lambda: None)
    assert browser_mod._jobs is None

    asked = browser_mod._submit(lambda: "served")
    try:
        assert asked.result(timeout=5) == "served"
    finally:
        browser_mod._jobs.put(None)


def test_the_browser_is_still_closed_properly_when_the_process_exits(tmp_path) -> None:
    import subprocess
    import sys

    proof = tmp_path / "closed"
    script = (
        "import atexit, sys\n"
        "from pathlib import Path\n"
        "from alpi.tools import browser\n"
        "browser._close_all = lambda: Path(sys.argv[1]).write_text('closed on the browser thread')\n"
        "browser._on_browser_thread(lambda: None)\n"
        "atexit.register(browser._shutdown)\n"
    )

    done = subprocess.run([sys.executable, "-c", script, str(proof)], capture_output=True, text=True, timeout=60)

    assert done.returncode == 0, done.stderr
    assert proof.read_text() == "closed on the browser thread"
