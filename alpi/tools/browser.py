"""Headless browser tool — Playwright-backed, per-profile context."""

from __future__ import annotations

import atexit
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

from alpi.home import get_home
from alpi.tools._guards import check_url
from alpi.tools.base import Tool, ToolResult

_MAX_SNAPSHOT_CHARS = 8000
_DEFAULT_TIMEOUT_MS = 30_000

_executor: ThreadPoolExecutor | None = None
_state: dict[str, Any] = {
    "playwright": None,
    "browser": None,
    "context": None,
    "page": None,
}


def _storage_dir():
    d = get_home() / "browser"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _on_browser_thread(fn: Callable[[], Any]) -> Any:
    """Run ``fn`` on the dedicated Playwright thread and return its result.

    Playwright's sync API is greenlet-based and pinned to the thread that
    started it. alpi's TUI spawns a fresh worker thread per turn, so we
    funnel every browser call through a single-worker executor.
    """
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="alpi-browser",
        )
        atexit.register(_shutdown)
    return _executor.submit(fn).result()


def _ensure_page_blocking():
    if _state["page"] is not None:
        return _state["page"], None
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
    pw = sync_playwright().start()
    try:
        browser = _launch_chromium(pw)
    except Exception as e:  # noqa: BLE001
        pw.stop()
        return None, f"failed to launch chromium: {e}"
    storage_file = _storage_dir() / "state.json"
    context_args: dict[str, Any] = {}
    if storage_file.exists():
        context_args["storage_state"] = str(storage_file)
    context = browser.new_context(**context_args)
    _apply_stealth(context)

    def _route_guard(route, request):  # noqa: ANN001
        ok, reason = check_url(request.url)
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
    page = context.new_page()
    page.set_default_timeout(_DEFAULT_TIMEOUT_MS)
    _state.update(playwright=pw, browser=browser, context=context, page=page)
    return page, None


def _apply_stealth(context) -> None:
    try:
        from playwright_stealth import Stealth
    except ImportError:
        return
    try:
        Stealth().apply_stealth_sync(context)
    except Exception:  # noqa: BLE001
        pass


def _launch_chromium(pw):
    try:
        return pw.chromium.launch(headless=True)
    except Exception as e:  # noqa: BLE001
        if "Executable doesn't exist" not in str(e):
            raise
    import subprocess
    import sys
    # stderr, not stdout — the agent's response goes to stdout in
    # ``chat --once`` and via the engine elsewhere; we don't want a
    # one-line install banner to be parsed as model output.
    print(
        "downloading Chromium for the browser tool (one-time, ~200MB)…",
        file=sys.stderr, flush=True,
    )
    subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        check=True,
    )
    return pw.chromium.launch(headless=True)


def _close_blocking() -> None:
    try:
        if _state["context"] is not None:
            _state["context"].storage_state(path=str(_storage_dir() / "state.json"))
    except Exception:  # noqa: BLE001
        pass
    for key in ("page", "context", "browser"):
        obj = _state.get(key)
        if obj is not None:
            try:
                obj.close()
            except Exception:  # noqa: BLE001
                pass
        _state[key] = None
    pw = _state.get("playwright")
    if pw is not None:
        try:
            pw.stop()
        except Exception:  # noqa: BLE001
            pass
        _state["playwright"] = None


def _shutdown() -> None:
    global _executor
    if _executor is None:
        return
    try:
        _executor.submit(_close_blocking).result(timeout=5)
    except Exception:  # noqa: BLE001
        pass
    _executor.shutdown(wait=False, cancel_futures=True)
    _executor = None


def _snapshot(page) -> str:
    try:
        text = page.locator("body").aria_snapshot()
    except Exception:  # noqa: BLE001
        try:
            text = page.inner_text("body")
        except Exception as e:  # noqa: BLE001
            return f"(snapshot failed: {e})"
    text = (text or "").strip() or "(empty page)"
    url = ""
    try:
        url = page.url
    except Exception:  # noqa: BLE001
        pass
    header = f"url: {url}\n\n" if url else ""
    return _truncate(header + text)


def _truncate(s: str) -> str:
    if len(s) <= _MAX_SNAPSHOT_CHARS:
        return s
    return s[: _MAX_SNAPSHOT_CHARS - 80].rstrip() + (
        f"\n… [truncated, +{len(s) - _MAX_SNAPSHOT_CHARS} chars]"
    )


def _locator(page, role: str, name: str, text: str):
    if role:
        return page.get_by_role(role, name=name) if name else page.get_by_role(role)
    if text:
        return page.get_by_text(text, exact=False)
    return None


def _do_navigate(url: str) -> ToolResult:
    page, err = _ensure_page_blocking()
    if err is not None:
        return ToolResult(ok=False, output="", error=err)
    page.goto(url, wait_until="domcontentloaded")
    return ToolResult(ok=True, output=_snapshot(page))


def _do_snapshot() -> ToolResult:
    page, err = _ensure_page_blocking()
    if err is not None:
        return ToolResult(ok=False, output="", error=err)
    return ToolResult(ok=True, output=_snapshot(page))


def _do_click(role: str, name: str, text: str) -> ToolResult:
    page, err = _ensure_page_blocking()
    if err is not None:
        return ToolResult(ok=False, output="", error=err)
    loc = _locator(page, role, name, text)
    if loc is None:
        return ToolResult(
            ok=False, output="",
            error="click needs `role` (+ optional `name`) or `text`",
        )
    loc.first.click()
    page.wait_for_load_state("domcontentloaded")
    return ToolResult(ok=True, output=_snapshot(page))


def _do_type(role: str, name: str, text: str) -> ToolResult:
    page, err = _ensure_page_blocking()
    if err is not None:
        return ToolResult(ok=False, output="", error=err)
    loc = _locator(page, role, name, "")
    if loc is None:
        return ToolResult(
            ok=False, output="",
            error="type needs `role` (+ optional `name`)",
        )
    target = loc.first
    human, delay_range = _browser_typing_cfg()
    if human and delay_range not in ([0], [0, 0], []):
        import random
        lo, hi = _sanitize_delay_range(delay_range)
        target.clear()
        target.press_sequentially(text, delay=random.randint(lo, hi))
    else:
        target.fill(text)
    return ToolResult(ok=True, output=_snapshot(page))


def _browser_typing_cfg() -> tuple[bool, list]:
    import yaml
    try:
        cfg_path = get_home() / "config.yaml"
        if not cfg_path.exists():
            return True, [30, 80]
        data = yaml.safe_load(cfg_path.read_text()) or {}
        b = ((data.get("tools") or {}).get("browser") or {})
    except Exception:  # noqa: BLE001
        return True, [30, 80]
    return bool(b.get("human_typing", True)), list(b.get("typing_delay_ms", [30, 80]))


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
    page, err = _ensure_page_blocking()
    if err is not None:
        return ToolResult(ok=False, output="", error=err)
    dy = 800 if direction != "up" else -800
    page.mouse.wheel(0, dy)
    page.wait_for_timeout(200)
    return ToolResult(ok=True, output=_snapshot(page))


def _do_press(key: str) -> ToolResult:
    page, err = _ensure_page_blocking()
    if err is not None:
        return ToolResult(ok=False, output="", error=err)
    human, _ = _browser_typing_cfg()
    if human:
        import random
        page.wait_for_timeout(random.randint(150, 400))
    page.keyboard.press(key)
    page.wait_for_load_state("domcontentloaded")
    return ToolResult(ok=True, output=_snapshot(page))


def _do_screenshot() -> ToolResult:
    page, err = _ensure_page_blocking()
    if err is not None:
        return ToolResult(ok=False, output="", error=err)
    import time
    path = _storage_dir() / f"screenshot-{int(time.time())}.png"
    page.screenshot(path=str(path), full_page=False)
    return ToolResult(ok=True, output=str(path))


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
        "Interactive headless browser (Playwright + Chromium) for sites that "
        "need clicks, form fills, or JS. Cookies persist across turns under "
        "~/.alpi/<profile>/browser/.\n"
        "\n"
        "Actions:\n"
        "  navigate    — load a URL, return the page snapshot\n"
        "  snapshot    — return the current page's accessibility tree\n"
        "  click       — click an element (by `role` + `name`, or by `text`)\n"
        "  type        — focus an input and type `text` into it\n"
        "  scroll      — scroll the page (`direction` = down | up). Use for infinite-scroll pages.\n"
        "  press       — press a keyboard key (`key` = Enter, Escape, Tab, …). Use to submit forms without finding the button.\n"
        "  screenshot  — save a PNG of the current view. Returns the file path. "
        "If `question` is also provided AND `tools.browser.vision=true` in the "
        "profile's config, the screenshot is auto-analyzed by the vision model "
        "and the answer is returned instead of the path. Otherwise, chain with "
        "`read_image` manually when you need visual analysis.\n"
        "  close       — tear down Chromium, keep cookies on disk\n"
        "  logout      — tear down Chromium AND delete saved cookies\n"
        "\n"
        "After every action a fresh snapshot is returned so you see the new "
        "page state. Identify elements by role + accessible name whenever "
        "possible — it's more robust than free text. Use `web_fetch` for "
        "read-only static pages; this tool is for interactive flows.\n"
        "\n"
        "If a click/type fails because no element matches, the accessibility "
        "tree probably labels the element differently than the visible text "
        "— re-check the latest snapshot for the real role + name and retry. "
        "Don't guess selectors blindly."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "navigate", "snapshot", "click", "type",
                    "scroll", "press", "screenshot",
                    "close", "logout",
                ],
            },
            "url": {"type": "string", "description": "URL for navigate."},
            "role": {
                "type": "string",
                "description": "ARIA role of the target element (button, textbox, link, …).",
            },
            "name": {
                "type": "string",
                "description": "Accessible name of the target element.",
            },
            "text": {
                "type": "string",
                "description": "For click: visible text to match. For type: the text to enter.",
            },
            "direction": {
                "type": "string",
                "enum": ["down", "up"],
                "description": "Scroll direction. Default: down.",
            },
            "key": {
                "type": "string",
                "description": "Key name for press (Enter, Escape, Tab, ArrowDown, …).",
            },
            "question": {
                "type": "string",
                "description": "For screenshot: optional question to auto-analyze the PNG (requires tools.browser.vision=true).",
            },
        },
        "required": ["action"],
    }

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
    ) -> ToolResult:
        from alpi.tools._sandbox import require_network
        blocked = require_network("browser")
        if blocked is not None:
            return blocked
        if action == "close":
            _on_browser_thread(_close_blocking)
            return ToolResult(ok=True, output="browser context closed")

        if action == "logout":
            _on_browser_thread(_close_blocking)
            state_file = _storage_dir() / "state.json"
            try:
                state_file.unlink()
            except FileNotFoundError:
                pass
            return ToolResult(ok=True, output="browser closed and saved cookies deleted")

        if action == "navigate":
            if not url:
                return ToolResult(ok=False, output="", error="'url' required")
            safe, reason = check_url(url)
            if not safe:
                return ToolResult(ok=False, output="", error=f"blocked: {reason}")
            return _run(_do_navigate, url)

        if action == "snapshot":
            return _run(_do_snapshot)

        if action == "click":
            if not role and not text:
                return ToolResult(
                    ok=False, output="",
                    error="click needs `role` (+ optional `name`) or `text`",
                )
            return _run(_do_click, role, name, text)

        if action == "type":
            if not text:
                return ToolResult(ok=False, output="", error="'text' required for type")
            if not role:
                return ToolResult(
                    ok=False, output="",
                    error="type needs `role` (+ optional `name`)",
                )
            return _run(_do_type, role, name, text)

        if action == "scroll":
            return _run(_do_scroll, direction)

        if action == "press":
            if not key:
                return ToolResult(ok=False, output="", error="'key' required for press")
            return _run(_do_press, key)

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


def _run(fn: Callable[..., ToolResult], *args: Any) -> ToolResult:
    try:
        return _on_browser_thread(lambda: fn(*args))
    except Exception as e:  # noqa: BLE001
        return ToolResult(ok=False, output="", error=f"{type(e).__name__}: {e}")


TOOL = Browser
