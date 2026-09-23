"""web_search — keyless search through the public engines ddgs scrapes."""

from __future__ import annotations

import logging
import threading
import time
from urllib.parse import urlparse

from alpi.tools.base import Tool, ToolResult


log = logging.getLogger("alpi.tools.web_search")

_MAX_PER_DOMAIN = 2
_MAX_PER_TURN_DEFAULT = 25
_MIN_INTERVAL_S = 1.5
_ENGINE_TIMEOUT_S = 5
_CALL_BUDGET_S = 25.0
_JOIN_GRACE_S = 1.0
_MAX_LIVE_REQUESTS = 2
_COOLDOWN_S = 900.0
# Provisional, from the one measurement available (a residential IP); not a claim the other engines are broken. Hosts override.
DEFAULT_BACKENDS = ("duckduckgo", "yahoo", "brave")

# Overlapping searches from one IP are what trip its ~17-minute rate limit: a parallel_safe batch must queue, not burst.
_one_at_a_time = threading.Lock()
_last_started = 0.0
# Engine requests abandoned at a deadline keep running; both touched only under ``_one_at_a_time``.
_live: dict[str, threading.Thread] = {}
_cooldowns: dict[str, float] = {}


class WebSearch(Tool):
    name = "web_search"
    parallel_safe = True
    description = (
        "Search the web. Returns {title, URL, snippet} per hit. Use when "
        "the user wants to FIND something and you don't have a URL yet.\n"
        "\n"
        "Query in English by default — the English index has broader "
        "coverage for nearly every topic. Keep the user's language only "
        "when the query is inherently tied to a place or language "
        "(local restaurant, regional product, country-specific regulation).\n"
        "\n"
        "Not for: known URL → use `web_fetch` or `web_extract`. Never "
        "`terminal curl/wget` for HTTP.\n"
        "\n"
        "Cap at 3 searches per user question."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search terms."},
            "max_results": {"type": "integer", "default": 5},
        },
        "required": ["query"],
    }

    def run(self, query: str, max_results: int = 5) -> ToolResult:
        from alpi.tools._sandbox import require_network
        blocked = require_network("web_search")
        if blocked is not None:
            return blocked
        from alpi.tools._state import emit_state

        max_results = max(1, min(int(max_results or 5), 15))

        cap = _max_per_turn()
        if _spend_turn_budget(cap) is None:
            return ToolResult(
                ok=False, output="",
                error=(
                    f"web_search budget for this turn is spent ({cap} searches). "
                    "Answer from what you already have, or read a known URL with "
                    "web_fetch / web_extract."
                ),
            )

        try:
            from ddgs import DDGS
        except ImportError:
            return ToolResult(
                ok=False, output="",
                error="web search is unavailable: the ddgs package is not installed.",
            )

        emit_state("searching the web…")
        with _one_at_a_time:
            engine, results, asked, skipped = _run_query(DDGS, query, max_results)
        if not results and asked and all(outcome == "empty" for _, outcome in asked):
            return ToolResult(
                ok=True,
                output=(
                    f"(no results for {query!r} — every engine asked came back empty; "
                    f"{_describe(asked, skipped)}. If the query is narrow — quotes, site:, "
                    "rare terms — broaden it once; otherwise read a known URL with "
                    "web_fetch / web_extract rather than searching again.)"
                ),
            )
        if not results and not asked:
            return ToolResult(
                ok=False, output="",
                error=(
                    f"web search could not ask any engine right now ({_describe(asked, skipped)}). "
                    "Read a known URL with web_fetch / web_extract, use the browser tool, "
                    "or tell the user web search is unavailable right now."
                ),
            )
        if not results:
            return ToolResult(
                ok=False, output="",
                error=(
                    f"search failed — no engine returned results ({_describe(asked, skipped)}). "
                    "Repeating or rewording the search right away rarely gets past "
                    "timeouts and errors: read a known URL with web_fetch / web_extract, "
                    "use the browser tool, or tell the user web search is unavailable "
                    "right now."
                ),
            )

        results = _dedup_by_domain(results, _MAX_PER_DOMAIN)

        lines: list[str] = [f"# Results for: {query} (via {engine})\n"]
        for i, r in enumerate(results, start=1):
            title = (r.get("title") or "").strip()
            url = (r.get("href") or r.get("url") or "").strip()
            body = (r.get("body") or "").strip()
            lines.append(f"{i}. **[{title}]({url})**\n   {body}\n")

        return ToolResult(ok=True, output="\n".join(lines))


def _raw_settings() -> dict:
    from alpi import config as cfg_mod
    from alpi.home import get_home
    raw = (cfg_mod.load(get_home()).raw.get("tools") or {}).get("web_search") or {}
    return raw if isinstance(raw, dict) else {}


def _max_per_turn() -> int:
    try:
        return max(1, int(_raw_settings().get("max_per_turn", _MAX_PER_TURN_DEFAULT)))
    except Exception:  # noqa: BLE001
        return _MAX_PER_TURN_DEFAULT


def _spend_turn_budget(cap: int) -> int | None:
    from alpi.tools._state import spend_turn_counter

    return spend_turn_counter("web_search", cap)


def _installed_engines() -> set[str] | None:
    try:
        from ddgs.engines import ENGINES
        return set(ENGINES["text"])
    except Exception:  # noqa: BLE001
        return None


def _backends() -> list[str]:
    try:
        configured = _raw_settings().get("backends")
    except Exception:  # noqa: BLE001
        configured = None
    names = (
        [str(n).strip().lower() for n in configured if str(n).strip()]
        if isinstance(configured, list) else []
    )
    installed = _installed_engines()
    # ddgs silently widens an unknown backend name to `auto`, the full fan-out.
    known = [n for n in dict.fromkeys(names) if installed is None or n in installed]
    if known:
        return known
    return [n for n in DEFAULT_BACKENDS if installed is None or n in installed]


# Callers hold ``_one_at_a_time``, which is what makes the module-level clock safe.
def _space_out_calls() -> None:
    global _last_started
    gap = _MIN_INTERVAL_S - (time.monotonic() - _last_started)
    if gap > 0:
        time.sleep(gap)
    _last_started = time.monotonic()


def _outcome(exc: Exception, elapsed: float) -> str:
    name = type(exc).__name__
    text = str(exc)
    if name == "TimeoutException" or "timed out" in text.lower():
        return "timeout"
    if name == "RatelimitException":
        return "rate-limited"
    if "No results found" in text or name == "NoResultsException":
        # ddgs reports an engine still running at its own deadline as "No results found."
        return "timeout" if elapsed >= _ENGINE_TIMEOUT_S * 0.9 else "empty"
    return f"error ({name}: {text[:80]})" if text else f"error ({name})"


def _busy() -> set[str]:
    for name in [n for n, worker in _live.items() if not worker.is_alive()]:
        del _live[name]
    return set(_live)


def _ask(ddgs_cls, engine: str, query: str, max_results: int, wait_s: float) -> tuple[list, str]:
    box: dict = {}

    def work() -> None:
        started = time.monotonic()
        try:
            with ddgs_cls(timeout=_ENGINE_TIMEOUT_S) as ddgs:
                box["rows"] = list(ddgs.text(
                    query,
                    max_results=max_results,
                    safesearch="moderate",
                    backend=engine,
                ))
        except Exception as e:  # noqa: BLE001
            box["outcome"] = _outcome(e, time.monotonic() - started)

    # ddgs joins its own worker threads on exit, so only abandoning ours bounds the wait.
    worker = threading.Thread(target=work, name=f"web_search:{engine}", daemon=True)
    _live[engine] = worker
    worker.start()
    worker.join(min(wait_s, _ENGINE_TIMEOUT_S + _JOIN_GRACE_S))
    if worker.is_alive():
        return [], "timeout"
    del _live[engine]
    if "outcome" in box:
        return [], box["outcome"]
    rows = box.get("rows") or []
    return rows, "results" if rows else "empty"


def _run_query(ddgs_cls, query: str, max_results: int) -> tuple[str, list, list[tuple[str, str]], list[tuple[str, str]]]:
    _space_out_calls()
    now = time.monotonic()
    order = _backends()
    for name in [n for n, until in _cooldowns.items() if until <= now]:
        del _cooldowns[name]
    busy = _busy()

    def skip_reason(name: str) -> str | None:
        if name in busy:
            return "still busy with an earlier search"
        if name in _cooldowns:
            return "cooling down"
        return None

    ready = [n for n in order if skip_reason(n) is None]
    idle_cooling = [n for n in order if n in _cooldowns and n not in busy]
    if not ready and idle_cooling:
        # An outage costs one request per search this way, and a recovered engine still gets found.
        ready = [min(idle_cooling, key=lambda n: _cooldowns[n])]
    skipped = [(n, skip_reason(n) or "") for n in order if n not in ready]
    asked: list[tuple[str, str]] = []
    deadline = time.monotonic() + _CALL_BUDGET_S
    for engine in ready:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            skipped.append((engine, "out of time"))
            continue
        if len(_busy()) >= _MAX_LIVE_REQUESTS:
            skipped.append((engine, "earlier requests still running"))
            continue
        started = time.monotonic()
        rows, outcome = _ask(ddgs_cls, engine, query, max_results, remaining)
        log.info("web_search %s: %s in %.1fs", engine, outcome, time.monotonic() - started)
        if rows:
            _cooldowns.pop(engine, None)
            return engine, rows, asked, skipped
        if outcome != "empty":
            _cooldowns[engine] = now + _COOLDOWN_S
        asked.append((engine, outcome))
    return "", [], asked, skipped


def _describe(asked: list[tuple[str, str]], skipped: list[tuple[str, str]]) -> str:
    parts = []
    if asked:
        parts.append("asked " + ", ".join(f"{name}: {outcome}" for name, outcome in asked))
    if skipped:
        parts.append("not asked " + ", ".join(f"{name} ({reason})" for name, reason in skipped))
    return "; ".join(parts) or "no engine configured"


def _dedup_by_domain(results: list, cap: int) -> list:
    seen: dict[str, int] = {}
    out: list = []
    for r in results:
        url = (r.get("href") or r.get("url") or "").strip()
        try:
            host = urlparse(url).netloc.lower()
        except Exception:  # noqa: BLE001
            host = ""
        if host.startswith("www."):
            host = host[4:]
        count = seen.get(host, 0)
        if host and count >= cap:
            continue
        seen[host] = count + 1
        out.append(r)
    return out


TOOL = WebSearch
