from __future__ import annotations

import json
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from alpi.tools import _browser_view, browser

pytestmark = pytest.mark.integration

ORDERS = """<html><head><title>Orders</title></head><body><h1>Orders</h1>
<table>
<tr><td>Order 1001</td><td><button onclick="document.title='deleted 1'">Delete</button></td></tr>
<tr><td>Order 1002</td><td><button onclick="document.title='deleted 2'">Delete</button></td></tr>
<tr><td>Order 1003</td><td><button onclick="document.title='deleted 3'">Delete</button></td></tr>
</table>
<iframe src="/frame" style="width:300px;height:80px"></iframe>
<button onclick="fetch('/api/save').then(r=>r.text()).then(t=>document.body.insertAdjacentHTML('beforeend','<p>'+t+'</p>'))">Save</button>
<button onclick="document.title='confirm='+confirm('Delete order?')">Ask</button>
<button id="vanish">Vanish</button><button onclick="document.getElementById('vanish').remove()">Remove it</button>
<a href="/second" target="_blank">Open second</a>
<a href="/forbidden" target="_blank">Open forbidden</a>
<a href="/slow">Slow page</a>
<a href="/second">Plain second</a>
<select aria-label="Country" onchange="document.title='country='+this.value"><option>Spain</option><option>France</option></select>
<div onmouseover="document.getElementById('menu').hidden=false">Hover me</div><button id="menu" hidden>Secret item</button>
<input type="file" aria-label="Attachment" onchange="document.title='chosen='+this.files[0].name">
<input type="file" id="hidden-input" hidden onchange="document.title='picked='+this.files[0].name">
<button onclick="document.getElementById('hidden-input').click()">Add a document</button>
<a href="/file">Small file</a> <a href="/big">Big file</a> <a href="/dotfile">Dot file</a>
<button onclick="setTimeout(()=>document.body.insertAdjacentHTML('beforeend','<p>Late arrival</p>'),1000)">Start job</button>
<a href="/nothing">No content</a> <a href="/broken">Broken file</a> <a href="/never">Never answers</a>
<button onclick="setTimeout(()=>{location.href='/file'},1200)">Countdown file</button>
<button onclick="confirm('Leave?'); location.href='http://127.0.0.1:1/'">Ask then fail</button>
<button onclick="setTimeout(()=>window.open('/second'),144)">Delayed popup</button>
</body></html>"""

PRICES = """<html><head><title>Prices</title></head><body>
<button onclick="document.title='bought 1'">Price: 10</button>
<button onclick="document.title='bought 2'">Price: 10</button>
<button onclick="history.pushState({}, '', '/prices/two'); document.title='Two'">Go to step: two</button>
</body></html>"""

HOSTILE = """<html><head><title>Hostile</title><script>
scrollY = NaN; innerHeight = -1; innerWidth = 0;
Object.defineProperty(document, 'scrollingElement', {get: () => ({scrollTop: NaN, scrollHeight: -5})});
</script></head><body>""" + "".join(
    f"<p>Row {i} padded with enough words to make this page longer than one view <button onclick=\"document.title='hit {i}'\">Hit {i}</button></p>"
    for i in range(1, 301)
) + "</body></html>"

LONG = "<html><head><title>Long</title></head><body><h1>Catalogue</h1>" + "".join(
    f"<p>Item {i} with a description long enough to fill the line <button onclick=\"document.title='bought {i}'\">Buy {i}</button></p>"
    for i in range(1, 601)
) + "</body></html>"


class Site(BaseHTTPRequestHandler):
    hits: list[str] = []

    def reply(self, body, kind="text/html", headers=()):
        raw = body if isinstance(body, bytes) else body.encode()
        self.send_response(200)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(raw)))
        for key, value in headers:
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        type(self).hits.append(self.path)
        if self.path == "/orders":
            return self.reply(ORDERS)
        if self.path == "/long":
            return self.reply(LONG)
        if self.path.startswith("/prices"):
            return self.reply(PRICES)
        if self.path == "/hostile":
            return self.reply(HOSTILE)
        if self.path == "/driveby":
            return self.reply("<html><head><title>Drive-by</title></head><body><h1>Quiet page</h1><iframe src='/file' hidden></iframe></body></html>")
        if self.path == "/never":
            time.sleep(4)
            return self.reply("<html><head><title>Finally</title></head><body><h1>Finally here</h1></body></html>")
        if self.path == "/selfstart":
            return self.reply("<html><head><title>Self</title></head><body><h1>Self starter</h1><script>setTimeout(()=>{location.href='/file'},1500)</script></body></html>")
        if self.path == "/lateby":
            return self.reply("<html><head><title>Late</title></head><body><h1>Late page</h1><a href='/second'>Read more</a><script>setTimeout(()=>{location.href='/file'},700)</script></body></html>")
        if self.path == "/nothing":
            self.send_response(204)
            self.end_headers()
            return None
        if self.path == "/broken":
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Disposition", 'attachment; filename="broken.bin"')
            self.send_header("Content-Length", "100000")
            self.end_headers()
            self.wfile.write(b"x" * 100)
            self.wfile.flush()
            self.close_connection = True
            return None
        if self.path == "/frame":
            return self.reply("<button onclick=\"parent.document.title='paid'\">Pay now</button><input placeholder='Card number'>")
        if self.path == "/api/save":
            time.sleep(0.4)
            return self.reply("Saved OK", "text/plain")
        if self.path == "/slow":
            time.sleep(0.7)
            return self.reply("<html><head><title>Slow</title></head><body><h1>Arrived late</h1></body></html>")
        if self.path == "/file":
            return self.reply(b"invoice-bytes", "application/octet-stream", [("Content-Disposition", 'attachment; filename="invoice.pdf"')])
        if self.path == "/dotfile":
            return self.reply(b"x", "application/octet-stream", [("Content-Disposition", 'attachment; filename="../../.env"')])
        if self.path == "/big":
            return self.reply(b"x" * 200_000, "application/octet-stream", [("Content-Disposition", 'attachment; filename="big.bin"')])
        self.reply("<html><head><title>Second</title></head><body><h1>Second page</h1><a href='/orders'>Home</a></body></html>")

    def log_message(self, *args):
        pass


@pytest.fixture
def site(tmp_path, monkeypatch):
    Site.hits = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), Site)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    home = tmp_path / "home"
    home.mkdir()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (home / "config.yaml").write_text(f"workspace: {json.dumps(str(workspace))}\ntools:\n  browser:\n    allow_local: true\n")
    monkeypatch.setenv("ALPI_HOME", str(home))
    monkeypatch.setattr(browser, "get_home", lambda: home)
    monkeypatch.setattr(browser, "HUMAN_TYPING", False)
    tool = browser.Browser()

    def call(**arguments):
        if "path_of" in arguments:
            arguments["url"] = f"http://127.0.0.1:{server.server_port}{arguments.pop('path_of')}"
        return tool.run(**arguments)

    call.workspace = workspace
    try:
        yield call
    finally:
        tool.run(action="logout")
        server.shutdown()


def refs(view: str, label: str) -> list[str]:
    return re.findall(re.escape(label) + r'"(?: \[(?!ref=)[^\]]*\])* \[ref=(\w+)\]', view)


def ok(result) -> str:
    assert result.ok, result.error
    assert len(result.output) <= _browser_view.CAP
    return result.output


def test_a_ref_acts_on_the_exact_element_among_same_named_ones(site) -> None:
    view = ok(site(action="navigate", path_of="/orders"))
    deletes = refs(view, 'button "Delete')
    assert len(deletes) == 3
    assert "title: deleted 2" in ok(site(action="click", ref=deletes[1]))


def test_role_and_name_with_several_matches_lists_them_and_clicks_nothing(site) -> None:
    ok(site(action="navigate", path_of="/orders"))
    result = site(action="click", role="button", name="Delete")
    assert not result.ok and "3 elements match" in result.error
    assert len(refs(result.output, 'button "Delete')) == 3
    assert "title: Orders" in ok(site(action="snapshot"))
    assert "title: confirm=false" in ok(site(action="click", role="button", name="Ask"))


def test_a_button_inside_an_iframe_is_listed_and_clicked(site) -> None:
    view = ok(site(action="navigate", path_of="/orders"))
    pay = refs(view, 'button "Pay now')
    assert len(pay) == 1 and 'textbox "Card number"' in view
    assert "title: paid" in ok(site(action="click", ref=pay[0]))


def test_what_a_click_renders_later_is_in_that_click_result(site) -> None:
    view = ok(site(action="navigate", path_of="/orders"))
    assert "Saved OK" in ok(site(action="click", ref=refs(view, 'button "Save')[0]))


def test_a_click_that_navigates_slowly_returns_the_new_page(site) -> None:
    view = ok(site(action="navigate", path_of="/orders"))
    assert "Arrived late" in ok(site(action="click", ref=refs(view, 'link "Slow page')[0]))


def test_the_ref_of_a_removed_element_fails_at_once_with_a_fresh_view(site) -> None:
    view = ok(site(action="navigate", path_of="/orders"))
    gone = refs(view, 'button "Vanish')[0]
    ok(site(action="click", ref=refs(view, 'button "Remove it')[0]))
    started = time.monotonic()
    result = site(action="click", ref=gone)
    assert time.monotonic() - started < 2
    assert not result.ok and gone in result.error
    assert 'button "Remove it"' in result.output and 'button "Vanish"' not in result.output
    assert not site(action="click", ref="e99999").ok


def test_a_confirm_is_reported_dismissed_and_accepted_only_on_request(site) -> None:
    view = ok(site(action="navigate", path_of="/orders"))
    ask = refs(view, 'button "Ask')[0]
    dismissed = ok(site(action="click", ref=ask))
    assert "title: confirm=false" in dismissed
    assert 'confirm dialog "Delete order?" was dismissed' in dismissed
    accepted = ok(site(action="click", ref=ask, dialog="accept"))
    assert "title: confirm=true" in accepted and 'confirm dialog "Delete order?" was accepted' in accepted
    assert "title: confirm=false" in ok(site(action="click", ref=ask))


def test_a_tab_the_page_opens_becomes_active_and_tab_goes_back(site) -> None:
    view = ok(site(action="navigate", path_of="/orders"))
    opened = ok(site(action="click", ref=refs(view, 'link "Open second')[0]))
    assert "Second page" in opened and 'tabs: 1 "Orders" | 2* "Second"' in opened and "a new tab opened" in opened
    first = ok(site(action="tab", index=1))
    assert 'tabs: 1* "Orders" | 2 "Second"' in first and 'heading "Orders"' in first
    assert not site(action="tab", index=7).ok


def test_a_tab_the_page_opens_goes_through_the_url_guard(site, monkeypatch) -> None:
    allowed = browser.check_url
    monkeypatch.setattr(browser, "check_url", lambda url, **kw: (False, "test") if "/forbidden" in url else allowed(url, **kw))
    view = ok(site(action="navigate", path_of="/orders"))
    blocked = site(action="click", ref=refs(view, 'link "Open forbidden')[0])
    assert "/forbidden" not in Site.hits
    assert "Second page" not in blocked.output


def test_select_hover_back_and_wait(site, monkeypatch) -> None:
    view = ok(site(action="navigate", path_of="/orders"))
    assert "title: country=France" in ok(site(action="select", ref=refs(view, 'combobox "Country')[0], text="France"))
    assert 'button "Secret item"' not in view
    assert 'button "Secret item"' in ok(site(action="hover", text="Hover me"))
    ok(site(action="click", ref=refs(view, 'link "Plain second')[0]))
    assert 'heading "Orders"' in ok(site(action="back"))
    view = ok(site(action="snapshot"))
    started = ok(site(action="click", ref=refs(view, 'button "Start job')[0]))
    assert "Late arrival" not in started
    assert "Late arrival" in ok(site(action="wait", text="Late arrival"))
    monkeypatch.setattr(browser, "_WAIT_MAX_MS", 600)
    missing = site(action="wait", text="never shown")
    assert not missing.ok and "did not appear" in missing.error and 'heading "Orders"' in missing.output


def test_upload_goes_through_the_file_guard(site) -> None:
    (site.workspace / "notes.txt").write_text("hello")
    (site.workspace / ".env").write_text("SECRET=1")
    view = ok(site(action="navigate", path_of="/orders"))
    assert "title: chosen=notes.txt" in ok(site(action="upload", ref=refs(view, 'button "Attachment')[0], path="notes.txt"))
    assert "title: picked=notes.txt" in ok(site(action="upload", ref=refs(view, 'button "Add a document')[0], path="notes.txt"))
    denied = site(action="upload", ref=refs(view, 'button "Attachment')[0], path=".env")
    assert not denied.ok and "sensitive" in denied.error
    assert not site(action="upload", ref=refs(view, 'button "Attachment')[0], path="absent.txt").ok


def test_a_download_lands_in_the_workspace_under_a_safe_name(site) -> None:
    view = ok(site(action="navigate", path_of="/orders"))
    folder = site.workspace / ".browser-downloads"
    first = ok(site(action="click", ref=refs(view, 'link "Small file')[0]))
    assert f"downloaded {folder / 'invoice.pdf'}" in first
    assert (folder / "invoice.pdf").read_bytes() == b"invoice-bytes"
    assert f"downloaded {folder / 'invoice-1.pdf'}" in ok(site(action="click", ref=refs(view, 'link "Small file')[0]))
    ok(site(action="click", ref=refs(view, 'link "Dot file')[0]))
    saved = sorted(p.name for p in folder.iterdir())
    assert len(saved) == 3 and {"invoice-1.pdf", "invoice.pdf"} < set(saved)
    assert not any(name.startswith(".") for name in saved)
    assert not (site.workspace / ".env").exists() and not (site.workspace.parent / ".env").exists()
    assert f"downloaded {folder / 'invoice-2.pdf'}" in ok(site(action="navigate", path_of="/file"))


def test_a_download_above_the_cap_is_refused_and_the_next_one_still_works(site, monkeypatch) -> None:
    monkeypatch.setattr(browser, "_DOWNLOAD_MAX_BYTES", 100_000)
    view = ok(site(action="navigate", path_of="/orders"))
    refused = ok(site(action="click", ref=refs(view, 'link "Big file')[0]))
    assert 'download "big.bin" not saved: it is larger than' in refused
    folder = site.workspace / ".browser-downloads"
    assert not folder.exists() or not list(folder.iterdir())
    assert "downloaded" in ok(site(action="click", ref=refs(view, 'link "Small file')[0]))


def test_a_long_page_shows_one_screen_and_find_reaches_the_rest(site) -> None:
    view = ok(site(action="navigate", path_of="/long"))
    assert re.search(r"view: screen 1 of \d+", view)
    assert 'button "Buy 1"' in view and 'button "Buy 600"' not in view
    found = ok(site(action="find", text="Buy 550"))
    assert 'find "Buy 550": 1 match' in found and found.startswith("url: ")
    assert "title: bought 550" in ok(site(action="click", ref=refs(found, 'button "Buy 550')[0]))
    second = ok(site(action="navigate", path_of="/long"))
    scrolled = ok(site(action="scroll", direction="down"))
    assert re.search(r"view: screen 2 of \d+", scrolled)
    last_before = re.findall(r'button "Buy (\d+)"', second)[-1]
    assert f'button "Buy {last_before}"' in scrolled


def test_a_name_with_a_colon_is_still_reached_by_its_ref(site) -> None:
    view = ok(site(action="navigate", path_of="/prices"))
    prices = refs(view, 'button "Price: 10')
    assert len(prices) == 2 and "box=" not in view and "'button" not in view
    assert "title: bought 2" in ok(site(action="click", ref=prices[1]))
    listed = site(action="click", role="button", name="Price: 10")
    assert not listed.ok and len(refs(listed.output, 'button "Price: 10')) == 2


def test_back_over_a_same_document_history_entry_succeeds(site) -> None:
    view = ok(site(action="navigate", path_of="/prices"))
    assert "/prices/two" in ok(site(action="click", ref=refs(view, 'button "Go to step: two')[0])).splitlines()[0]
    returned = ok(site(action="back")).splitlines()[0]
    assert returned.endswith("/prices")


def test_a_page_that_lies_about_its_scroll_position_still_gets_a_view(site) -> None:
    view = ok(site(action="navigate", path_of="/hostile"))
    assert 'button "Hit 1"' in view
    assert "title: hit 2" in ok(site(action="click", ref=refs(view, 'button "Hit 2')[0]))
    assert 'button "Hit' in ok(site(action="scroll"))


def test_a_link_answered_with_no_content_returns_the_view_instead_of_hanging(site) -> None:
    view = ok(site(action="navigate", path_of="/orders"))
    started = time.monotonic()
    after = ok(site(action="click", ref=refs(view, 'link "No content')[0]))
    assert time.monotonic() - started < 5
    assert 'heading "Orders"' in after


def test_a_download_that_breaks_midway_is_reported_at_once(site) -> None:
    view = ok(site(action="navigate", path_of="/orders"))
    started = time.monotonic()
    broken = ok(site(action="click", ref=refs(view, 'link "Broken file')[0]))
    assert time.monotonic() - started < 10
    assert 'download "broken.bin" failed' in broken
    folder = site.workspace / ".browser-downloads"
    assert not folder.exists() or not list(folder.iterdir())
    assert "downloaded" in ok(site(action="click", ref=refs(view, 'link "Small file')[0]))


def test_a_download_the_page_starts_by_itself_is_not_saved(site) -> None:
    quiet = ok(site(action="navigate", path_of="/driveby"))
    later = ok(site(action="snapshot"))
    assert 'download "invoice.pdf" not saved: the page started it on its own' in quiet + later
    assert not (site.workspace / ".browser-downloads").exists()


def test_a_download_the_page_starts_late_is_not_credited_to_the_next_click(site) -> None:
    view = ok(site(action="navigate", path_of="/lateby"))
    time.sleep(1.2)
    clicked = ok(site(action="click", ref=refs(view, 'link "Read more')[0]))
    assert 'download "invoice.pdf" not saved: the page started it on its own' in clicked
    assert "Second page" in clicked
    assert not (site.workspace / ".browser-downloads").exists()


def test_a_download_that_starts_seconds_after_its_click_is_still_saved(site) -> None:
    view = ok(site(action="navigate", path_of="/orders"))
    assert "download" not in ok(site(action="click", ref=refs(view, 'button "Countdown file')[0]))
    time.sleep(1.5)
    assert f"downloaded {site.workspace / '.browser-downloads' / 'invoice.pdf'}" in ok(site(action="snapshot"))


def test_a_page_that_does_not_answer_is_given_up_with_a_note(site, monkeypatch) -> None:
    monkeypatch.setattr(browser, "_NAVIGATION_MAX_MS", 1000)
    view = ok(site(action="navigate", path_of="/orders"))
    started = time.monotonic()
    waiting = ok(site(action="click", ref=refs(view, 'link "Never answers')[0]))
    assert time.monotonic() - started < 3
    assert "has not answered in 1 s" in waiting and waiting.startswith("url: ")
    again = ok(site(action="snapshot"))
    assert "has not answered" in again or "Finally here" in again
    assert "Finally here" in ok(site(action="wait", text="Finally here"))


def test_a_dialog_is_reported_by_the_action_that_raised_it_even_when_the_page_then_fails(site) -> None:
    view = ok(site(action="navigate", path_of="/orders"))
    result = site(action="click", ref=refs(view, 'button "Ask then fail')[0])
    assert 'confirm dialog "Leave?" was dismissed' in result.output


def test_a_profile_that_denies_write_file_saves_no_download(site, monkeypatch) -> None:
    monkeypatch.setattr(browser, "_write_file_denied", lambda: True)
    view = ok(site(action="navigate", path_of="/orders"))
    denied = ok(site(action="click", ref=refs(view, 'link "Small file')[0]))
    assert 'download "invoice.pdf" not saved: this turn may not call write_file' in denied
    assert not (site.workspace / ".browser-downloads").exists()


def test_a_download_lands_in_the_workspace_of_the_turn_that_asked(site, tmp_path) -> None:
    from alpi.home import reset_active_home, set_active_home

    other = tmp_path / "other-home"
    other.mkdir()
    theirs = tmp_path / "other-workspace"
    theirs.mkdir()
    (other / "config.yaml").write_text(f"workspace: {json.dumps(str(theirs))}\ntools:\n  browser:\n    allow_local: true\n")
    view = ok(site(action="navigate", path_of="/orders"))
    token = set_active_home(other)
    try:
        saved = ok(site(action="click", ref=refs(view, 'link "Small file')[0]))
    finally:
        reset_active_home(token)
    assert f"downloaded {theirs / '.browser-downloads' / 'invoice.pdf'}" in saved
    assert not (site.workspace / ".browser-downloads").exists()


def test_a_tab_that_opens_late_never_receives_a_ref_chosen_on_another_tab(site) -> None:
    view = ok(site(action="navigate", path_of="/orders"))
    for _ in range(3):
        shown = ok(site(action="click", ref=refs(view, 'button "Delayed popup')[0]))
        on_second = "Second page" in shown
        assert on_second == bool(re.search(r'\d\* "Second"', shown))
        if on_second:
            home = site(action="click", ref=refs(shown, 'link "Home')[0])
            assert home.ok and 'heading "Orders"' in home.output
        else:
            pressed = site(action="click", ref=refs(shown, 'button "Ask')[0])
            assert (pressed.ok and "title: confirm=false" in pressed.output) or "active tab changed" in pressed.error
        ok(site(action="tab", index=1))
        view = ok(site(action="navigate", path_of="/orders"))


def test_a_click_in_one_tab_does_not_let_another_tab_save_its_own_download(site) -> None:
    first = ok(site(action="navigate", path_of="/selfstart"))
    orders_url = first.splitlines()[0].removeprefix("url: ").replace("/selfstart", "/orders")
    browser._on_browser_thread(lambda: browser._state["context"].new_page().goto(orders_url))
    orders = ok(site(action="tab", index=2))
    ok(site(action="click", ref=refs(orders, 'button "Save')[0]))
    time.sleep(1.8)
    after = ok(site(action="snapshot"))
    assert 'download "invoice.pdf" not saved: the page started it on its own' in after
    assert not (site.workspace / ".browser-downloads").exists()


def test_a_navigate_to_a_file_does_not_leave_the_page_free_to_save_more(site) -> None:
    ok(site(action="navigate", path_of="/selfstart"))
    assert "downloaded" in ok(site(action="navigate", path_of="/big"))
    time.sleep(1.8)
    after = ok(site(action="snapshot"))
    assert 'download "invoice.pdf" not saved: the page started it on its own' in after
    assert sorted(p.name for p in (site.workspace / ".browser-downloads").iterdir()) == ["big.bin"]
