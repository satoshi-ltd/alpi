"""web_search — DuckDuckGo search, no API key."""

from __future__ import annotations

from urllib.parse import urlparse

from alpi.tools.base import Tool, ToolResult


_MAX_PER_DOMAIN = 2


class WebSearch(Tool):
    name = "web_search"
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
        from alpi.tools._state import emit_state

        max_results = max(1, min(int(max_results or 5), 15))

        emit_state("searching the web…")
        results = _run_query(query, max_results)
        if results is None:
            return ToolResult(
                ok=False, output="",
                error="search failed: the ddgs backend raised.",
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


def _run_query(query: str, max_results: int) -> list | None:
    try:
        from ddgs import DDGS
    except ImportError:
        return None
    try:
        with DDGS() as ddgs:
            return list(ddgs.text(
                query,
                max_results=max_results,
                safesearch="moderate",
            ))
    except Exception:  # noqa: BLE001
        return None


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
