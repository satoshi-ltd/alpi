"""web_search — DuckDuckGo search, no API key."""

from __future__ import annotations

import threading
import time
from urllib.parse import urlparse

from alpi.tools.base import Tool, ToolResult


_MAX_PER_DOMAIN = 2
_MAX_PER_TURN_DEFAULT = 25
_MIN_INTERVAL_S = 1.5
_RETRY_BACKOFF_S = 2.0

# One ddgs call fans out to 5+ upstream engines, so two of ours in flight is 10+ requests at once — the fastest way to the shared-IP rate limit, which then locks everyone out for ~17 minutes. Serialize and space them: a parallel_safe batch queues instead of bursting.
_one_at_a_time = threading.Lock()
_last_started = 0.0


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

        emit_state("searching the web…")
        with _one_at_a_time:
            results, failure = _run_query(query, max_results)
        if results is None:
            return ToolResult(
                ok=False, output="",
                error=(
                    f"search failed after one retry — every backend refused or "
                    f"errored ({failure}). This is usually a rate limit on this "
                    "machine's IP that clears in minutes, not a bad query, so do "
                    "NOT reformulate and search again now. Use web_fetch / "
                    "web_extract on a known URL, or the browser tool, or tell the "
                    "user web search is temporarily unavailable."
                ),
            )

        if not results:
            return ToolResult(ok=True, output=f"(no results for {query!r})")

        results = _dedup_by_domain(results, _MAX_PER_DOMAIN)

        lines: list[str] = [f"# Results for: {query}\n"]
        for i, r in enumerate(results, start=1):
            title = (r.get("title") or "").strip()
            url = (r.get("href") or r.get("url") or "").strip()
            body = (r.get("body") or "").strip()
            lines.append(f"{i}. **[{title}]({url})**\n   {body}\n")

        return ToolResult(ok=True, output="\n".join(lines))


def _max_per_turn() -> int:
    try:
        from alpi import config as cfg_mod
        from alpi.home import get_home
        raw = (cfg_mod.load(get_home()).raw.get("tools") or {}).get("web_search") or {}
        return max(1, int(raw.get("max_per_turn", _MAX_PER_TURN_DEFAULT)))
    except Exception:  # noqa: BLE001
        return _MAX_PER_TURN_DEFAULT


def _spend_turn_budget(cap: int) -> int | None:
    from alpi.tools._state import spend_turn_counter

    return spend_turn_counter("web_search", cap)


# Callers hold ``_one_at_a_time``, which is what makes the module-level clock safe.
def _space_out_calls() -> None:
    global _last_started
    gap = _MIN_INTERVAL_S - (time.monotonic() - _last_started)
    if gap > 0:
        time.sleep(gap)
    _last_started = time.monotonic()


def _run_query(query: str, max_results: int) -> tuple[list | None, str]:
    try:
        from ddgs import DDGS
    except ImportError:
        return None, "the ddgs package is not installed"
    failure = ""
    for attempt in range(2):
        if attempt:
            time.sleep(_RETRY_BACKOFF_S)
        _space_out_calls()
        try:
            with DDGS() as ddgs:
                return list(ddgs.text(
                    query,
                    max_results=max_results,
                    safesearch="moderate",
                )), ""
        except Exception as e:  # noqa: BLE001
            failure = f"{type(e).__name__}: {e}".strip() or type(e).__name__
    return None, failure


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
