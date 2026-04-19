"""web_search — DuckDuckGo search (no API key required).

Uses the ``ddgs`` library (the maintained successor of ``duckduckgo-search``).
Returns a compact Markdown list of results (title + URL + snippet). Ideal
precursor to ``web_extract`` — search first, then extract the most relevant
result.
"""

from __future__ import annotations

from alf.tools.base import Tool, ToolResult


class WebSearch(Tool):
    name = "web_search"
    description = (
        "Search the web. Returns a list of {title, URL, snippet}. Use when "
        "the user asks to FIND something online and you don't have a URL "
        "yet (\"busca X\", \"where can I read about Y\").\n"
        "\n"
        "DO NOT use for:\n"
        "  • known URL you want to read → use `web_fetch` or `web_extract`\n"
        "  • HTTP via shell → never `terminal curl/wget`\n"
        "\n"
        "Max 3 loops per user question; if results are thin after 3 tries, "
        "stop reformulating — tell the user and switch strategy."
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
        from alf.tools._state import emit_state
        try:
            from ddgs import DDGS
        except ImportError:
            return ToolResult(ok=False, output="",
                              error="ddgs not installed (pip install ddgs)")

        max_results = max(1, min(int(max_results or 5), 15))
        emit_state("searching the web…")
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))
        except Exception as e:  # noqa: BLE001
            return ToolResult(ok=False, output="", error=f"search failed: {e}")

        if not results:
            return ToolResult(ok=True, output=f"(no results for {query!r})")

        lines: list[str] = [f"# Results for: {query}\n"]
        for i, r in enumerate(results, start=1):
            title = (r.get("title") or "").strip()
            url = (r.get("href") or r.get("url") or "").strip()
            body = (r.get("body") or "").strip()
            lines.append(f"{i}. **[{title}]({url})**\n   {body}\n")

        return ToolResult(ok=True, output="\n".join(lines))


TOOL = WebSearch
