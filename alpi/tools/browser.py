from __future__ import annotations

import atexit
import contextvars
import json
import math
import os
import queue
import re
import shutil
import tempfile
import threading
import time
from concurrent.futures import Future
from functools import partial
from pathlib import Path
from typing import Any, Callable

from alpi.home import get_home
from alpi.tools import _browser_view
from alpi.tools._guards import check_url
from alpi.tools.base import Tool, ToolResult

_DEFAULT_TIMEOUT_MS = 30_000
_ACTION_TIMEOUT_MS = 10_000
_SETTLE_STEP_MS = 150
_SETTLE_MAX_MS = 2_000
_NAVIGATION_MAX_MS = 10_000
_SNAPSHOT_TIMEOUT_MS = 5_000
_WAIT_MAX_MS = 15_000
_DOWNLOAD_MAX_BYTES = 50 * 1024 * 1024
_DOWNLOAD_MAX_S = 60
_DOWNLOAD_GRACE_S = 1.5
_BOX = re.compile(r" \[box=[^\]]*\]")

# uv tool installs expose only alpi-agent's own entry points, so the `playwright` console script is not on PATH — the repair has to go through uvx (see docs/INSTALL.md).
CHROMIUM_DEPS_COMMAND = (
    "uvx --from playwright playwright install-deps chromium-headless-shell"
)

# Chromium's DT_NEEDED set, one soname per Debian package family — playwright downloads the browser but never these, so a slim Linux image resolves the import and still cannot launch.
_CHROMIUM_SONAMES = (
    "libglib-2.0.so.0",
    "libnss3.so",
    "libnspr4.so",
    "libatk-1.0.so.0",
    "libatk-bridge-2.0.so.0",
    "libdbus-1.so.3",
    "libX11.so.6",
    "libXcomposite.so.1",
    "libXdamage.so.1",
    "libXext.so.6",
    "libXfixes.so.3",
    "libXrandr.so.2",
    "libgbm.so.1",
    "libxcb.so.1",
    "libxkbcommon.so.0",
    "libasound.so.2",
    "libatspi.so.0",
)

def _fresh() -> dict[str, Any]:
    return {
        "home": None, "context": None, "page": None, "trace": None, "downloads": [], "watched": [],
        "navigating": set(), "stalled": set(), "inflight": set(), "events": [], "dialog": "dismiss",
        "caller": None, "opening": False, "previous": None, "viewed": None, "save_from": [], "cookies": None,
        "origins": [],
    }


_jobs: queue.SimpleQueue | None = None
_starting = threading.Lock()
# One Chromium, one context per profile home. `_state` holds the shared browser plus the session of the profile being served; `_parked` holds the other profiles' sessions. Both are touched only on the browser thread.
_state: dict[str, Any] = {"playwright": None, "browser": None, "downloads_dir": None, "dead": False, **_fresh()}
_parked: dict[Any, dict[str, Any]] = {}
_lost: dict[Any, str] = {}
_NOTES_MAX = 20
_reached_browser = threading.local()


def _activate(home: Path) -> None:
    if _state["home"] == home:
        return
    incoming = _parked.pop(home, None)
    if _state["home"] is None and incoming is None:
        _state["home"] = home
        return
    if _state["context"] is not None or _state["trace"] is not None:
        _parked[_state["home"]] = {key: _state[key] for key in _fresh()}
    _state.update(incoming or {**_fresh(), "home": home})


# Notes wait for their profile's next view, which a page that raises dialogs in a loop could otherwise fill.
def _note(text: str, session: dict[str, Any] | None = None) -> None:
    notes = (_state if session is None else session)["events"]
    if notes and notes[-1] == text:
        return
    notes.append(text)
    del notes[:-_NOTES_MAX]


# Page events arrive whenever any call pumps Playwright, so a handler may run for a profile that is not the one being served.
def _session(home: Any) -> dict[str, Any] | None:
    return _state if _state["home"] == home else _parked.get(home)


def missing_chromium_libs() -> list[str]:
    import sys
    if not sys.platform.startswith("linux"):
        return []
    import ctypes
    missing = []
    for soname in _CHROMIUM_SONAMES:
        try:
            ctypes.CDLL(soname)
        except OSError:
            missing.append(soname)
    return missing


def _storage_dir():
    d = (_state["home"] or get_home()) / "browser"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _serve(jobs: queue.SimpleQueue) -> None:
    while True:
        job = jobs.get()
        if job is None:
            return
        done, fn = job
        try:
            done.set_result(fn())
        except BaseException as error:  # noqa: BLE001
            done.set_exception(error)


def _submit(fn: Callable[[], Any]) -> Future:
    global _jobs
    done: Future = Future()
    # Playwright's sync API is pinned to the thread that started it. That thread is a daemon one because `_shutdown` runs at exit, when a ThreadPoolExecutor already refuses work.
    with _starting:
        if _jobs is None:
            jobs: queue.SimpleQueue = queue.SimpleQueue()
            threading.Thread(target=_serve, args=(jobs,), name="alpi-browser", daemon=True).start()
            _jobs = jobs
        _jobs.put((done, fn))
    return done


def _on_browser_thread(fn: Callable[[], Any]) -> Any:
    return _submit(fn).result()


_GONE = "the browser had stopped and was started again: its open pages are gone, saved cookies are kept"


# Chromium is shared: when it has died every profile's session died with it, and no single profile's `close` could bring it back while others stay parked. `is_connected` stays true when only the Playwright driver died, hence `dead`.
def _forget_dead_browser() -> None:
    browser = _state["browser"]
    if browser is None or (not _state["dead"] and _call(browser.is_connected)):
        return
    for session in (_state, *_parked.values()):
        recording = session["trace"] is not None
        if recording:
            _call(session["trace"].close)
        if session["context"] is not None or recording:
            _lost[session["home"]] = _GONE + ("; the trace that was recording was saved incomplete" if recording else "")
    _parked.clear()
    _state.update({**_fresh(), "home": _state["home"], "caller": _state["caller"], "dialog": _state["dialog"], "dead": False})
    _stop_browser()
    if _state["home"] in _lost:
        _note(_lost.pop(_state["home"]))


# The first call after the Playwright driver dies raises a bare Exception, later ones TargetClosedError.
def _connection_lost(error: BaseException) -> bool:
    return type(error).__name__ == "TargetClosedError" or "connection closed" in str(error).lower()


def _browser_answers() -> bool:
    try:
        _state["browser"].new_context().close()
        return True
    except Exception:  # noqa: BLE001
        return False


# A saved session that cannot be used is kept beside the live one, which the next cookie change overwrites.
def _set_aside(storage_file: Path, why: str, aside: str = "state.json.unreadable") -> None:
    try:
        os.replace(storage_file, storage_file.with_name(aside))
        kept = f"was set aside as browser/{aside}"
    except OSError:
        kept = "could not be moved away, so nothing this session saves will be kept until browser/state.json is removed"
    _note(f"the saved browser session {why} and {kept}: this one starts signed out")


# A file without `per_profile` was written while every profile shared one session, so whose sign-ins it holds is unknown.
def _saved_session(storage_file: Path) -> dict[str, Any] | None:
    try:
        saved = json.loads(storage_file.read_text(encoding="utf-8"))
        return {
            "cookies": list(saved["cookies"]), "origins": list(saved.get("origins") or []),
            "per_profile": saved.get("per_profile") is True,
        }
    except Exception:  # noqa: BLE001
        return None


def _ensure_page_blocking():
    _forget_dead_browser()
    page = _state["page"]
    if page is not None:
        if not page.is_closed():
            return page, None
        still_open = [p for p in _state["context"].pages if not p.is_closed()]
        before = _state["previous"]
        if before is not None and any(before is p for p in still_open):
            page = before
        else:
            page = still_open[-1] if still_open else _open_page(_state["context"])
        _state["page"] = _watch(page)
        return page, None
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        # playwright is a hard dependency declared in ``pyproject.toml``,
        # so reaching this branch means the alpi install itself is broken
        # (partial wheel, manual edit of site-packages, etc.). The fix is
        # to reinstall through the same tool the user installed with.
        return None, (
            "playwright import failed — your alpi install is incomplete. "
            "Try: uv tool install alpi-agent --reinstall"
        )
    if _state["browser"] is None:
        pw = sync_playwright().start()
        downloads_dir = tempfile.mkdtemp(prefix="alpi-browser-")
        try:
            browser = _launch_chromium(pw, downloads_dir)
        except Exception as e:  # noqa: BLE001
            pw.stop()
            shutil.rmtree(downloads_dir, ignore_errors=True)
            return None, f"failed to launch chromium: {e}"
        _state.update(playwright=pw, browser=browser, downloads_dir=downloads_dir)
        # Exit hooks run last-registered first, and greenlet's own hook (set when Playwright is imported) ends the sync API: ours has to be the later one.
        atexit.unregister(_shutdown)
        atexit.register(_shutdown)
    home = _state["home"]
    if home in _lost:
        _note(_lost.pop(home))
    storage_file = _storage_dir() / "state.json"
    saved = None
    if storage_file.is_symlink():
        _set_aside(storage_file, "is a link")
    elif storage_file.exists():
        _call(lambda: os.chmod(storage_file, 0o600))
        saved = _saved_session(storage_file)
        if saved is None:
            _set_aside(storage_file, "could not be read")
        elif not saved.pop("per_profile"):
            saved = None
            _set_aside(storage_file, "dates from when every profile shared one browser session", "state.json.shared")
    try:
        try:
            context = _state["browser"].new_context(**({"storage_state": saved} if saved else {}))
        except Exception:
            if not saved:
                raise
            saved = None
            context = _state["browser"].new_context()
            _set_aside(storage_file, "was not accepted by the browser")
    except Exception:
        if not _parked:
            _stop_browser()
        raise
    _state["origins"] = saved["origins"] if saved else []
    _apply_stealth(context)

    allow_local = _in_caller(_allow_local)
    def _route_guard(route, request):  # noqa: ANN001
        ok, reason = check_url(request.url, allow_loopback=allow_local)
        if not ok:
            try:
                route.abort("addressunreachable")
            except Exception:  # noqa: BLE001
                pass
            return
        try:
            route.continue_()
        except Exception:  # noqa: BLE001
            pass

    try:
        context.route("**/*", _route_guard)
    except Exception:  # noqa: BLE001
        pass
    context.on("page", partial(_on_page, home))
    context.on("dialog", partial(_on_dialog, home))
    _state["context"] = context
    _state["cookies"] = _call(lambda: json.dumps(context.cookies(), sort_keys=True))
    _state["page"] = page = _open_page(context)
    return page, None


def _open_page(context):
    _state["opening"] = True
    try:
        return _watch(context.new_page())
    finally:
        _state["opening"] = False


def _watch(page, session: dict[str, Any] | None = None):
    session = _state if session is None else session
    if any(page is seen for seen in session["watched"]):
        return page
    session["watched"].append(page)
    home = session["home"]
    page.set_default_timeout(_DEFAULT_TIMEOUT_MS)
    page.on("download", partial(_on_download, home))
    page.on("request", partial(_on_request, home))
    page.on("framenavigated", partial(_on_navigated, home))
    page.on("requestfinished", partial(_on_request_done, home))
    page.on("requestfailed", partial(_on_request_done, home))
    page.on("response", partial(_on_response, home))
    return page


def _on_page(home, page) -> None:
    session = _session(home)
    if session is None or session["opening"] or any(page is seen for seen in session["watched"]):
        return
    session["previous"] = session["page"]
    session["page"] = _watch(page, session)
    if session["save_from"]:
        session["save_from"].append(page)
    _note("a new tab opened and is now the active one", session)


def _on_download(home, download) -> None:
    session = _session(home)
    if session is None:
        _call(download.cancel)
        return
    session["downloads"].append(download)


def _on_request(home, request) -> None:
    session = _session(home)
    if session is None:
        return
    try:
        if request.resource_type in ("xhr", "fetch"):
            session["inflight"].add(request)
        elif request.is_navigation_request() and request.frame.parent_frame is None:
            session["stalled"].discard(request.frame)
            session["navigating"].add(request.frame)
    except Exception:  # noqa: BLE001
        pass


def _on_request_done(home, request) -> None:
    session = _session(home)
    if session is None:
        return
    session["inflight"].discard(request)
    if _call(request.is_navigation_request):
        frame = _call(lambda: request.frame)
        session["navigating"].discard(frame)
        session["stalled"].discard(frame)


def _on_navigated(home, frame) -> None:
    session = _session(home)
    if session is None:
        return
    session["navigating"].discard(frame)
    session["stalled"].discard(frame)
    if _call(lambda: frame.parent_frame) is None:
        session["inflight"].clear()


# A navigation answered 204/205 never commits, so no `framenavigated` would clear it.
def _on_response(home, response) -> None:
    session = _session(home)
    if session is None:
        return
    try:
        if response.status in (204, 205) and response.request.is_navigation_request():
            session["navigating"].discard(response.request.frame)
    except Exception:  # noqa: BLE001
        pass


# The note is recorded before answering: answering lets the page go on, and the action may fail before this handler returns.
def _on_dialog(home, dialog) -> None:
    session = _session(home)
    accept = session is not None and session["dialog"] == "accept"
    message = _one_line(dialog.message, 200).replace('"', "'")
    done = "accepted" if accept else 'dismissed (repeat the action with dialog="accept" to accept it)'
    if session is not None:
        _note(f'{dialog.type} dialog "{message}" was {done}', session)
    try:
        if accept:
            dialog.accept()
        else:
            dialog.dismiss()
    except Exception:  # noqa: BLE001
        pass


def _apply_stealth(context) -> None:
    try:
        from playwright_stealth import Stealth
    except ImportError:
        return
    try:
        Stealth().apply_stealth_sync(context)
    except Exception:  # noqa: BLE001
        pass


def _launch_chromium(pw, downloads_path: str | None = None):
    options: dict[str, Any] = {"headless": True}
    if downloads_path:
        options["downloads_path"] = downloads_path
    try:
        return pw.chromium.launch(**options)
    except Exception as e:  # noqa: BLE001
        if "Executable doesn't exist" not in str(e):
            raise
    import sys

    from alpi.core._playwright import ensure_chromium

    print(
        "downloading the Chromium headless shell for the browser tool "
        "(one-time, ~340MB)…",
        file=sys.stderr, flush=True,
    )
    ensure_chromium()
    return pw.chromium.launch(**options)


# Cookies cost under a millisecond to read; the rest of the storage costs a hidden page per origin ever visited, so it is read on close only and carried over in between.
def _save_state(*, full: bool = False) -> None:
    context = _state["context"]
    if context is None:
        return
    try:
        found = context.cookies()
        cookies = json.dumps(found, sort_keys=True)
        if not full and cookies == _state["cookies"]:
            return
        if full:
            whole = context.storage_state()
            found, _state["origins"] = whole["cookies"], whole["origins"]
            cookies = json.dumps(found, sort_keys=True)
        from alpi.secrets_io import safe_write_secret
        safe_write_secret(_storage_dir() / "state.json", json.dumps({"per_profile": True, "cookies": found, "origins": _state["origins"]}))
        _state["cookies"] = cookies
    except Exception:  # noqa: BLE001
        pass


def _close_blocking() -> None:
    trace = _state.get("trace")
    if trace is not None:
        try:
            trace.close()
        except Exception:
            pass
    _save_state(full=True)
    context = _state["context"]
    if context is not None:
        _call(context.close)
    _lost.pop(_state["home"], None)
    _state.update(_fresh())
    if not _parked:
        _stop_browser()


def _stop_browser() -> None:
    for key, stop in (("browser", "close"), ("playwright", "stop")):
        obj = _state.get(key)
        if obj is not None:
            _call(getattr(obj, stop))
        _state[key] = None
    if _state["downloads_dir"]:
        shutil.rmtree(_state["downloads_dir"], ignore_errors=True)
    _state["downloads_dir"] = None
    _state["dead"] = False


def _close_all() -> None:
    while True:
        _close_blocking()
        if not _parked:
            return
        _activate(next(iter(_parked)))


def _shutdown(wait: float = 5.0) -> None:
    global _jobs
    with _starting:
        jobs, _jobs = _jobs, None
    if jobs is None:
        return
    done: Future = Future()
    jobs.put((done, _close_all))
    try:
        done.result(timeout=wait)
    except Exception:  # noqa: BLE001
        pass
    if _state["downloads_dir"]:
        shutil.rmtree(_state["downloads_dir"], ignore_errors=True)
    jobs.put(None)


def _one_line(value: Any, limit: int) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.replace("[ref=", "[ref:").split())[:limit]


def _call(fn: Callable[[], Any]) -> Any:
    try:
        return fn()
    except Exception:  # noqa: BLE001
        return None


def _loading(page) -> bool:
    frame = page.main_frame
    return frame in _state["navigating"] or frame in _state["stalled"]


# Always page-wide: a locator-scoped `ai` snapshot makes Playwright forget every ref outside that locator. Playwright holds a snapshot while a navigation is pending, hence the short timeout; a page that is merely huge gets the long one.
def _raw(page) -> str:
    try:
        return page.aria_snapshot(mode="ai", boxes=True, timeout=_SNAPSHOT_TIMEOUT_MS)
    except Exception:  # noqa: BLE001
        _call(lambda: page.wait_for_load_state("domcontentloaded", timeout=_SNAPSHOT_TIMEOUT_MS))
        patience = _SNAPSHOT_TIMEOUT_MS if _loading(page) else _DEFAULT_TIMEOUT_MS
        return page.aria_snapshot(mode="ai", boxes=True, timeout=patience)


class _StillLoading(Exception):
    pass


def _pump(page, ms: int) -> None:
    try:
        page.wait_for_timeout(ms)
    except Exception:  # noqa: BLE001
        time.sleep(ms / 1000)


# A page that renders on a bare timer is not waited for (`wait` covers it): only a pending navigation of this tab and the requests the action started are. The first pump lets the action's request events arrive.
def _settled(page) -> str:
    frame = page.main_frame
    page.wait_for_timeout(50)
    deadline = time.monotonic() + _NAVIGATION_MAX_MS / 1000
    while frame in _state["navigating"] and not _state["downloads"]:
        if time.monotonic() > deadline:
            _state["navigating"].discard(frame)
            _state["stalled"].add(frame)
            raise _StillLoading
        page.wait_for_timeout(50)
    _state["navigating"].discard(frame)
    raw = _raw(page)
    deadline = time.monotonic() + _SETTLE_MAX_MS / 1000
    while time.monotonic() < deadline:
        page.wait_for_timeout(_SETTLE_STEP_MS)
        again = _raw(page)
        if not _state["inflight"] and frame not in _state["navigating"] and _BOX.sub("", again) == _BOX.sub("", raw):
            return again
        raw = again
    return raw


# The scroll position comes from the page's own world, so a hostile page can return anything: unusable numbers mean "no metrics", never an exception.
def _metrics(page) -> dict | None:
    try:
        found = page.evaluate(
            "() => { const e = document.scrollingElement || document.documentElement;"
            " return {y: e.scrollTop, total: e.scrollHeight, h: innerHeight, w: innerWidth}; }"
        )
        size = page.viewport_size
        if isinstance(size, dict):
            found = {**found, "h": size["height"], "w": size["width"]}
        metrics = {key: float(found[key]) for key in ("y", "h", "w", "total")}
    except Exception:  # noqa: BLE001
        return None
    if not all(math.isfinite(value) and value >= 0 for value in metrics.values()) or metrics["h"] < 1 or metrics["w"] < 1:
        return None
    return metrics


def _header(page) -> str:
    lines = []
    url = _one_line(_call(lambda: page.url), 300)
    if url:
        lines.append(f"url: {url}")
    title = _one_line(_call(page.title), 120)
    if title:
        lines.append(f"title: {title}")
    context = _state["context"]
    pages = list(context.pages) if context is not None else []
    if len(pages) > 1:
        tabs = [f'{i}{"*" if tab is page else ""} "{_tab_title(tab)}"' for i, tab in enumerate(pages, 1)]
        lines.append("tabs: " + " | ".join(tabs) + " (* active)")
    lines.extend(_state["events"])
    return "\n".join(lines) + "\n" if lines else ""


def _tab_title(tab) -> str:
    return _one_line(_call(tab.title), 40).replace('"', "'").replace("|", "/")


def _view(page, raw: str) -> str:
    _state["viewed"] = page
    return _browser_view.render(_browser_view.parse(raw), _header(page), _metrics(page))


def _result(page, *, settle: bool = True) -> ToolResult:
    try:
        return ToolResult(ok=True, output=_current_view(page, settle))
    except _StillLoading:
        # No title, metrics or snapshot here: Playwright holds every call into the page until the pending navigation ends.
        page = _state["page"] or page
        _state["viewed"] = page
        notes = "".join(f"{note}\n" for note in _state["events"])
        waited = _NAVIGATION_MAX_MS // 1000
        return ToolResult(ok=True, output=(
            f"url: {_one_line(_call(lambda: page.url), 300)}\n{notes}\n"
            f"(the page this action started loading has not answered in {waited} s: no view yet — use `wait` or `snapshot`)"
        ))


# The view must come from the tab that is active when it is returned: a tab opened while the view is being built would otherwise receive the next ref.
def _current_view(page, settle: bool) -> str:
    try:
        raw = _settled(page) if settle else _raw(page)
    except _StillLoading:
        raise
    except Exception as e:  # noqa: BLE001
        if _connection_lost(e) and _state["browser"] is not None and not _browser_answers():
            raise
        if _state["page"] is None or not page.is_closed():
            if _state["context"] is not None and _loading(page):
                raise _StillLoading from None
            raise
        raw = None
    for _ in range(4):
        active = _state["page"]
        if active is not None and (raw is None or active is not page):
            page, _ = _ensure_page_blocking()
            raw = _settled(page)
        _collect_downloads(page)
        output = _view(page, raw)
        if _state["page"] is None or _state["page"] is page:
            break
    return output


def _fail(page, raw: str, error: str) -> ToolResult:
    return ToolResult(ok=False, output=_view(page, raw), error=error)


def _safe_name(suggested: Any) -> str:
    name = suggested if isinstance(suggested, str) else ""
    name = re.sub(r"[^A-Za-z0-9._ -]", "_", name.replace("\\", "/").rsplit("/", 1)[-1]).lstrip(". ")[:120]
    return name or "download"


def _download_target(name: str) -> Path:
    from alpi.tools._paths import resolve_workspace_path

    stem, dot, suffix = name.rpartition(".")
    if not stem:
        stem, dot, suffix = name, "", ""
    for attempt in range(1000):
        candidate = name if attempt == 0 else f"{stem}-{attempt}{dot}{suffix}"
        target = _in_caller(resolve_workspace_path, f".browser-downloads/{candidate}", for_write=True)
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            os.close(os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600))
            return target
        except FileExistsError:
            continue
    raise ValueError("too many files with that name in .browser-downloads/")


def _write_file_denied() -> bool:
    try:
        from alpi import config as cfg_mod
        from alpi.tools import _policy
        denies = _policy.effective_denies(cfg_mod.load(get_home()).tools.deny)
        return _policy.is_denied("write_file", denies) or _policy.allowed_actions("write_file") is not None
    except Exception:  # noqa: BLE001
        return True


def _in_caller(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    caller = _state["caller"]
    return caller.run(fn, *args, **kwargs) if caller is not None else fn(*args, **kwargs)


# The folder is shared by every profile's context, so only this session's own files are watched; the artifact path is not public API, hence the whole-folder fallback.
def _own_files(downloads: list) -> set[str] | None:
    names = set()
    for download in downloads:
        path = _call(lambda: download._impl_obj._artifact.absolute_path)
        if not isinstance(path, str) or not path:
            return None
        names.add(os.path.basename(path))
    return names


# Chromium writes `<guid>.crdownload` and renames it when the file is complete, or removes it when the transfer fails: the only completion signal that does not block, since Download.path() and failure() wait for ever.
def _collect_downloads(page) -> None:
    pending = _state["downloads"]
    folder = _state["downloads_dir"]
    if not pending or not folder:
        return
    batch = list(pending)
    why_not = {}
    denied = None
    for download in batch:
        source = _call(lambda: download.page)
        if not any(source is armed for armed in _state["save_from"]):
            why_not[id(download)] = "the page started it on its own"
        else:
            denied = _in_caller(_write_file_denied) if denied is None else denied
            if denied:
                why_not[id(download)] = "this turn may not call write_file"
    for download in batch:
        if id(download) in why_not:
            _call(download.cancel)
    wanted = [download for download in batch if id(download) not in why_not]
    own = _own_files(wanted)
    refused = ""
    started = time.monotonic()
    seen_partial = False
    while wanted and not refused:
        names = [n for n in os.listdir(folder) if own is None or n.removesuffix(".crdownload") in own]
        partial = [n for n in names if n.endswith(".crdownload")]
        seen_partial = seen_partial or bool(partial)
        elapsed = time.monotonic() - started
        if sum(_call(lambda n=n: os.path.getsize(os.path.join(folder, n))) or 0 for n in names) > _DOWNLOAD_MAX_BYTES:
            refused = f"it is larger than {_DOWNLOAD_MAX_BYTES // (1024 * 1024)} MB"
        elif not partial and (seen_partial or len(names) >= len(wanted) or elapsed > _DOWNLOAD_GRACE_S):
            break
        elif elapsed > _DOWNLOAD_MAX_S:
            refused = f"it did not finish in {_DOWNLOAD_MAX_S} s"
        else:
            _pump(page, 200)
    for download in batch:
        name = _safe_name(_call(lambda: download.suggested_filename))
        reason = why_not.get(id(download)) or refused
        target = None
        try:
            if reason:
                download.cancel()
                note = f'download "{name}" not saved: {reason}'
            elif (failure := download.failure()) is not None:
                note = f'download "{name}" failed: {_one_line(failure, 120)}'
            else:
                source = download.path()
                if os.path.getsize(source) > _DOWNLOAD_MAX_BYTES:
                    raise ValueError(f"it is larger than {_DOWNLOAD_MAX_BYTES // (1024 * 1024)} MB")
                target = _download_target(name)
                shutil.copyfile(source, target)
                note, target = f"downloaded {target}", None
        except Exception as e:  # noqa: BLE001
            note = f'download "{name}" not saved: {_one_line(str(e), 200)}'
        if target is not None:
            _call(target.unlink)
        _call(download.delete)
        _note(note)
        pending.remove(download)


# A download is saved only from the tab that received the last click or key press, or a tab opened since: what is already pending when the next click, key press or navigation begins is settled under the rule in force until then, and only an action that went through arms a tab.
def _settle_downloads(page, *, disarm: bool = False) -> None:
    _pump(page, 50)
    _collect_downloads(page)
    if disarm:
        _state["save_from"] = []


def _target(page, ref: str, role: str, name: str, text: str = ""):
    raw = _raw(page)
    rows = _browser_view.parse(raw)
    changed = _tab_changed(page, raw)
    if changed is not None:
        return None, changed
    if ref:
        ref = ref.strip().strip("[]@").removeprefix("ref=")
        if ref not in _browser_view.refs(rows):
            return None, _fail(page, raw, f"ref {ref} is not on the page any more — take one from this view")
        return page.get_by_ref(ref), None
    found = _browser_view.candidates(rows, role, name, text)
    if len(found) == 1:
        return page.get_by_ref(found[0].ref), None
    if len(found) > 1:
        listing = "\n".join(row.line(0, keep_ref=True) for row in found[:12])
        return None, ToolResult(
            ok=False, output=listing,
            error=f"{len(found)} elements match — repeat with the `ref` of the one you mean",
        )
    if role:
        loose = page.get_by_role(role, name=name) if name else page.get_by_role(role)
    else:
        loose = page.get_by_text(text, exact=False)
    count = loose.count()
    if count == 1:
        return loose, None
    if count == 0:
        return None, _fail(page, raw, "no element matches — read the view for its role and name, or use find")
    return None, _fail(page, raw, f"{count} elements match — use find to get the `ref` of the one you mean")


def _page_or_error():
    page, err = _ensure_page_blocking()
    return page, (ToolResult(ok=False, output="", error=err) if err is not None else None)


def _tab_changed(page, raw: str | None = None) -> ToolResult | None:
    viewed = _state["viewed"]
    if _state["context"] is None or viewed is None or viewed is page:
        return None
    return _fail(page, raw if raw is not None else _raw(page), "the active tab changed since the last view — choose again from this view")


def _do_navigate(url: str) -> ToolResult:
    page, failed = _page_or_error()
    if failed:
        return failed
    _settle_downloads(page, disarm=True)
    try:
        page.goto(url, wait_until="domcontentloaded")
    except Exception as e:  # noqa: BLE001
        if "Download is starting" not in str(e):
            raise
        _state["save_from"] = [page]
        page.wait_for_timeout(_SETTLE_STEP_MS)
    try:
        return _result(page)
    finally:
        _state["save_from"] = []


def _do_snapshot() -> ToolResult:
    page, failed = _page_or_error()
    return failed or _result(page, settle=False)


def _do_find(text: str) -> ToolResult:
    page, failed = _page_or_error()
    if failed:
        return failed
    found = _browser_view.find(_browser_view.parse(_raw(page)), text)
    _state["viewed"] = page
    header = _header(page)
    return ToolResult(ok=True, output=(header + "\n" if header else "") + found)


def _do_trace_start() -> ToolResult:
    from alpi.tools._browser_trace import BrowserTrace
    import json
    if _state.get("trace") is not None:
        return ToolResult(ok=False, output="", error="A trace is already active; stop it first")
    page, err = _ensure_page_blocking()
    if err:
        return ToolResult(ok=False, output="", error=err)
    trace = _in_caller(BrowserTrace, _state["context"])
    _state["trace"] = trace
    return ToolResult(ok=True, output=json.dumps({"path": str(trace.path), "recording": True,
        "next": "Navigate to the start of the workflow; subsequent browser actions use this same session"}))


def _do_trace_stop(role: str, name: str) -> ToolResult:
    import json
    _forget_dead_browser()
    trace = _state.get("trace")
    if trace is None:
        return ToolResult(ok=False, output="", error="No active trace")
    _state["page"].wait_for_timeout(500)
    confirmed = False
    if role and name:
        confirmed = _state["page"].get_by_role(role, name=name, exact=True).first.is_visible()
    result = trace.close(confirmed)
    _state["trace"] = None
    return ToolResult(ok=True, output=json.dumps(result))


def _do_click(ref: str, role: str, name: str, text: str) -> ToolResult:
    page, failed = _page_or_error()
    if failed:
        return failed
    target, failed = _target(page, ref, role, name, text)
    if failed:
        return failed
    _settle_downloads(page)
    # Playwright would otherwise wait inside click for the navigation it starts and fail with no view when the server answers 204 or never; _settled waits for that navigation instead, and gives up with a note.
    target.click(timeout=_ACTION_TIMEOUT_MS, no_wait_after=True)
    _state["save_from"] = [page]
    return _result(page)


def _do_hover(ref: str, role: str, name: str, text: str) -> ToolResult:
    page, failed = _page_or_error()
    if failed:
        return failed
    target, failed = _target(page, ref, role, name, text)
    if failed:
        return failed
    target.hover(timeout=_ACTION_TIMEOUT_MS)
    return _result(page)


def _do_type(ref: str, role: str, name: str, text: str) -> ToolResult:
    page, failed = _page_or_error()
    if failed:
        return failed
    target, failed = _target(page, ref, role, name)
    if failed:
        return failed
    human, delay_range = _browser_typing_cfg()
    if human and delay_range not in ([0], [0, 0], []):
        import random
        lo, hi = _sanitize_delay_range(delay_range)
        target.clear(timeout=_ACTION_TIMEOUT_MS)
        target.press_sequentially(text, delay=random.randint(lo, hi))
    else:
        target.fill(text, timeout=_ACTION_TIMEOUT_MS)
    return _result(page)


def _do_select(ref: str, role: str, name: str, text: str) -> ToolResult:
    page, failed = _page_or_error()
    if failed:
        return failed
    target, failed = _target(page, ref, role, name)
    if failed:
        return failed
    target.select_option(label=text, timeout=_ACTION_TIMEOUT_MS)
    return _result(page)


def _do_upload(ref: str, role: str, name: str, path: str) -> ToolResult:
    page, failed = _page_or_error()
    if failed:
        return failed
    target, failed = _target(page, ref, role, name)
    if failed:
        return failed
    try:
        target.set_input_files(path, timeout=_ACTION_TIMEOUT_MS)
    except Exception as e:  # noqa: BLE001
        if "HTMLInputElement" not in str(e):
            raise
        with page.expect_file_chooser(timeout=_ACTION_TIMEOUT_MS) as chooser:
            target.click(timeout=_ACTION_TIMEOUT_MS)
        chooser.value.set_files(path)
    return _result(page)


HUMAN_TYPING = True
TYPING_DELAY_MS = (30, 80)


def _browser_typing_cfg() -> tuple[bool, list]:
    return HUMAN_TYPING, list(TYPING_DELAY_MS)


def _sanitize_delay_range(raw) -> tuple[int, int]:
    try:
        if isinstance(raw, (list, tuple)) and len(raw) >= 2:
            lo, hi = int(raw[0]), int(raw[1])
        elif isinstance(raw, (list, tuple)) and len(raw) == 1:
            lo = hi = int(raw[0])
        else:
            lo, hi = int(raw), int(raw)
    except (TypeError, ValueError):
        lo, hi = 30, 80
    if lo > hi:
        lo, hi = hi, lo
    return max(0, lo), max(0, hi)


def _do_scroll(direction: str) -> ToolResult:
    page, failed = _page_or_error()
    if failed:
        return failed
    changed = _tab_changed(page)
    if changed is not None:
        return changed
    before = _metrics(page) or {}
    step = max(100, int((before.get("h") or 720) * _browser_view.SCROLL_FRACTION))
    page.mouse.wheel(0, step if direction != "up" else -step)
    last = before.get("y")
    deadline = time.monotonic() + 1
    while time.monotonic() < deadline:
        page.wait_for_timeout(80)
        now = (_metrics(page) or {}).get("y")
        if now == last and (now != before.get("y") or time.monotonic() > deadline - 0.6):
            break
        last = now
    return _result(page)


def _do_press(key: str) -> ToolResult:
    page, failed = _page_or_error()
    if failed:
        return failed
    changed = _tab_changed(page)
    if changed is not None:
        return changed
    _settle_downloads(page)
    human, _ = _browser_typing_cfg()
    if human:
        import random
        page.wait_for_timeout(random.randint(150, 400))
    page.keyboard.press(key)
    _state["save_from"] = [page]
    return _result(page)


def _do_back() -> ToolResult:
    page, failed = _page_or_error()
    if failed:
        return failed
    _settle_downloads(page, disarm=True)
    before = page.url
    if page.go_back(wait_until="domcontentloaded") is None and page.url == before:
        return _fail(page, _raw(page), "this tab has no earlier page")
    return _result(page)


def _do_wait(text: str) -> ToolResult:
    page, failed = _page_or_error()
    if failed:
        return failed
    needle = text.strip().lower()
    deadline = time.monotonic() + _WAIT_MAX_MS / 1000
    while True:
        raw = _call(lambda: _raw(page))
        if raw and any(needle in f"{row.name} {row.tail}".lower() for row in _browser_view.parse(raw)):
            return _result(page, settle=False)
        if time.monotonic() > deadline:
            error = f'"{text}" did not appear in {_WAIT_MAX_MS // 1000} s'
            if raw is None:
                return ToolResult(ok=False, output="", error=error + "; the page is still loading")
            return _fail(page, raw, error)
        page.wait_for_timeout(250)


def _do_tab(index: int) -> ToolResult:
    page, failed = _page_or_error()
    if failed:
        return failed
    pages = list(_state["context"].pages) if _state["context"] is not None else [page]
    if not 1 <= index <= len(pages):
        return _fail(page, _raw(page), f"there is no tab {index}; open tabs are numbered 1 to {len(pages)}")
    _settle_downloads(page, disarm=True)
    page = _watch(pages[index - 1])
    page.bring_to_front()
    _state["page"] = page
    return _result(page, settle=False)


def _do_screenshot() -> ToolResult:
    page, failed = _page_or_error()
    if failed:
        return failed
    path = _storage_dir() / f"screenshot-{int(time.time())}.png"
    page.screenshot(path=str(path), full_page=False)
    return ToolResult(ok=True, output=str(path))


def _allow_local() -> bool:
    try:
        from alpi import config as cfg_mod
        cfg = cfg_mod.load(get_home())
        return cfg.tools.browser.allow_local
    except Exception:  # noqa: BLE001
        return False


def _vision_enabled() -> bool:
    try:
        from alpi import config as cfg_mod
        cfg = cfg_mod.load(get_home())
        return cfg.tools.browser.vision
    except Exception:  # noqa: BLE001
        return False


def _analyze_screenshot(path: str, question: str) -> ToolResult:
    from alpi.tools.read_image import ReadImage
    return ReadImage().run(path=path, question=question)


class Browser(Tool):
    name = "browser"
    description = (
        "Interactive headless browser (Chromium) for sites that need clicks, forms or JS; use `web_fetch` for "
        "static pages. Cookies persist across turns.\n"
        "Every action returns the page view: an accessibility tree where each element you can act on carries "
        "`[ref=e12]`. Pass that `ref` to act on exactly that element; a ref is valid only while it is in the "
        "latest view. A long page shows one screen (`view: screen 2 of 9`): `scroll` moves a screen, `find` "
        "searches the whole page.\n"
        "Actions:\n"
        "  navigate — load `url`\n"
        "  snapshot — the current view again\n"
        "  find — elements matching `text` anywhere on the page, iframes included, with refs and link URLs\n"
        "  click, hover — the element `ref` (or `role` + `name`, or its visible `text`)\n"
        "  type — `text` into the element `ref`\n"
        "  select — the option labelled `text` in the dropdown `ref`\n"
        "  upload — the file at `path` into the file input `ref`\n"
        "  press — keyboard `key` (Enter, Escape, Tab, ArrowDown, …)\n"
        "  scroll — `direction` down | up\n"
        "  back — the previous page of this tab\n"
        "  wait — until `text` appears, 15 s at most\n"
        "  tab — switch to tab `index`; a tab the page opens becomes the active one by itself\n"
        "  screenshot — save a PNG and return its path; with `question` and tools.browser.vision=true the "
        "vision model answers instead (otherwise chain `read_image`)\n"
        "  close — stop the browser, keep cookies; logout — also delete them\n"
        "  trace_start / trace_stop — record sanitised network evidence of a workflow in this session; start "
        "before navigating; stop takes an optional `role` + exact `name` of a visible confirmation. An "
        "incomplete trace does not prove a completed workflow\n"
        "A confirm or prompt dialog is dismissed unless the action carries dialog=\"accept\"; the result says "
        "what happened. A download that follows a click, a key press or a navigate to the file is saved under "
        "the workspace's .browser-downloads/ and its path returned; any other is cancelled and reported."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "navigate", "snapshot", "find", "click", "hover", "type", "select", "upload",
                    "press", "scroll", "back", "wait", "tab", "screenshot",
                    "close", "logout",
                    "trace_start", "trace_stop",
                ],
            },
            "url": {"type": "string", "description": "URL for navigate."},
            "ref": {"type": "string", "description": "Element ref from the latest view, e.g. e12."},
            "role": {
                "type": "string",
                "description": "ARIA role of the target (button, textbox, link, …) when no ref is given.",
            },
            "name": {"type": "string", "description": "Accessible name of the target, with `role`."},
            "text": {
                "type": "string",
                "description": "type: text to enter. select: option label. find, wait: text to look for. click, hover: visible text of the target.",
            },
            "direction": {"type": "string", "enum": ["down", "up"], "description": "Scroll direction. Default: down."},
            "key": {"type": "string", "description": "Key name for press."},
            "path": {"type": "string", "description": "upload: file to send (relative paths root at the workspace)."},
            "index": {"type": "integer", "description": "tab: number of the tab, as listed in the view."},
            "dialog": {
                "type": "string", "enum": ["dismiss", "accept"],
                "description": "What to answer if this action opens a dialog. Default: dismiss.",
            },
            "question": {
                "type": "string",
                "description": "For screenshot: optional question to auto-analyze the PNG (requires tools.browser.vision=true).",
            },
        },
        "required": ["action"],
    }

    @classmethod
    def check(cls) -> tuple[bool, str]:
        import importlib.util
        if importlib.util.find_spec("playwright") is None:
            return False, "playwright not installed"
        missing = missing_chromium_libs()
        if missing:
            return False, (
                f"chromium system libraries missing ({', '.join(missing)}) — run: "
                f"{CHROMIUM_DEPS_COMMAND}"
            )
        return True, ""

    def run(
        self,
        action: str,
        url: str = "",
        role: str = "",
        name: str = "",
        text: str = "",
        direction: str = "down",
        key: str = "",
        question: str = "",
        ref: str = "",
        path: str = "",
        index: int = 0,
        dialog: str = "dismiss",
    ) -> ToolResult:
        _reached_browser.value = False
        result = self._run_action(action, url, role, name, text, direction, key, question, ref, path, index, dialog)
        # A racy read on purpose: a refused call must not queue behind another profile's action when nobody records a trace.
        recording = any(session["trace"] is not None for session in (_state, *list(_parked.values())))
        if not result.ok and not _reached_browser.value and recording:
            _as_profile(lambda: _state["trace"] is not None and _state["trace"].step(action, False))
        return result

    def _run_action(
        self,
        action: str,
        url: str = "",
        role: str = "",
        name: str = "",
        text: str = "",
        direction: str = "down",
        key: str = "",
        question: str = "",
        ref: str = "",
        path: str = "",
        index: int = 0,
        dialog: str = "dismiss",
    ) -> ToolResult:
        from alpi.tools._sandbox import require_network
        blocked = require_network("browser")
        if blocked is not None:
            return blocked
        answer = "accept" if dialog == "accept" else "dismiss"
        if action == "trace_start":
            return _run(_do_trace_start)
        if action == "trace_stop":
            return _run(_do_trace_stop, role, name)
        if action == "close":
            _as_profile(_close_blocking)
            return ToolResult(ok=True, output="browser context closed")

        if action == "logout":
            left = _as_profile(_logout)
            if left:
                return ToolResult(ok=False, output="", error=(
                    f"browser closed, but the saved session could not be deleted: {', '.join(left)}. "
                    "What is listed is still on disk, and a browser/state.json left there is loaded by the next browser use."
                ))
            return ToolResult(ok=True, output="browser closed and saved cookies deleted")

        if action == "navigate":
            if not url:
                return ToolResult(ok=False, output="", error="'url' required")
            safe, reason = check_url(url, allow_loopback=_allow_local())
            if not safe:
                return ToolResult(ok=False, output="", error=f"blocked: {reason}")
            return _run(_do_navigate, url, dialog=answer)

        if action == "snapshot":
            return _run(_do_snapshot, dialog=answer)

        if action in ("find", "wait"):
            if not text.strip():
                return ToolResult(ok=False, output="", error=f"'text' required for {action}")
            return _run(_do_find if action == "find" else _do_wait, text, dialog=answer)

        if action in ("click", "hover"):
            if not ref and not role and not text:
                return ToolResult(
                    ok=False, output="",
                    error=f"{action} needs `ref`, or `role` (+ optional `name`), or `text`",
                )
            return _run(_do_click if action == "click" else _do_hover, ref, role, name, text, dialog=answer)

        if action in ("type", "select"):
            if not text:
                return ToolResult(ok=False, output="", error=f"'text' required for {action}")
            if not ref and not role:
                return ToolResult(ok=False, output="", error=f"{action} needs `ref`, or `role` (+ optional `name`)")
            return _run(_do_type if action == "type" else _do_select, ref, role, name, text, dialog=answer)

        if action == "upload":
            if not path:
                return ToolResult(ok=False, output="", error="'path' required for upload")
            if not ref and not role:
                return ToolResult(ok=False, output="", error="upload needs `ref`, or `role` (+ optional `name`)")
            from alpi.tools._paths import resolve_path
            try:
                source = resolve_path(path)
            except ValueError as e:
                return ToolResult(ok=False, output="", error=str(e))
            if not source.is_file():
                return ToolResult(ok=False, output="", error=f"no such file: {source}")
            return _run(_do_upload, ref, role, name, str(source), dialog=answer)

        if action == "scroll":
            return _run(_do_scroll, direction, dialog=answer)

        if action == "press":
            if not key:
                return ToolResult(ok=False, output="", error="'key' required for press")
            return _run(_do_press, key, dialog=answer)

        if action == "back":
            return _run(_do_back, dialog=answer)

        if action == "tab":
            try:
                number = int(index)
            except (TypeError, ValueError):
                number = 0
            if number < 1:
                return ToolResult(ok=False, output="", error="'index' required for tab: the tab's number in the view")
            return _run(_do_tab, number, dialog=answer)

        if action == "screenshot":
            shot = _run(_do_screenshot)
            if not shot.ok or not question:
                return shot
            if not _vision_enabled():
                hint = (
                    f"{shot.output}\n\n"
                    "[vision disabled — set tools.browser.vision=true in "
                    "config.yaml to auto-analyze, or call read_image "
                    "manually with this path]"
                )
                return ToolResult(ok=True, output=hint)
            return _analyze_screenshot(shot.output, question)

        return ToolResult(ok=False, output="", error=f"unknown action: {action}")


def _logout() -> list[str]:
    state_file = _storage_dir() / "state.json"
    _close_blocking()
    left = []
    for saved in (state_file, state_file.with_name("state.json.unreadable"), state_file.with_name("state.json.shared")):
        try:
            saved.unlink()
        except FileNotFoundError:
            pass
        except OSError as error:
            left.append(f"browser/{saved.name} ({error.strerror or type(error).__name__})")
    return left


def _as_profile(fn: Callable[[], Any]) -> Any:
    home = get_home()
    _reached_browser.value = True

    def serve():
        _activate(home)
        return fn()
    return _on_browser_thread(serve)


def _run(fn: Callable[..., ToolResult], *args: Any, dialog: str = "dismiss") -> ToolResult:
    caller = contextvars.copy_context()

    def execute():
        trace = _state.get("trace")
        _state["inflight"].clear()
        _state["dialog"] = dialog
        _state["caller"] = caller
        try:
            result = fn(*args)
        except Exception as e:  # noqa: BLE001
            error = f"{type(e).__name__}: {e}"
            if _connection_lost(e) and _state["browser"] is not None and not _browser_answers():
                _state["dead"] = True
                error += " — the browser stopped; repeat the action to start it again"
            result = ToolResult(ok=False, output="\n".join(_state["events"]), error=error)
        finally:
            _state["dialog"] = "dismiss"
            _state["caller"] = None
        # A note leaves only with a result that printed it: one recorded while another profile was served, or before a result with no view, waits for the next.
        _state["events"] = [note for note in _state["events"] if note not in result.output]
        if trace is not None and _state["trace"] is trace and fn not in (_do_trace_start, _do_trace_stop):
            trace.step(fn.__name__.removeprefix("_do_"), result.ok)
        # Not after a failure: with Chromium frozen the cookie read has no timeout and would hold the one browser thread.
        if result.ok:
            _save_state()
        return result
    try:
        return _as_profile(execute)
    except Exception as e:  # noqa: BLE001
        return ToolResult(ok=False, output="", error=f"{type(e).__name__}: {e}")


TOOL = Browser
