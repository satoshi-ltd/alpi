"""web_fetch — fetch a URL and return Markdown."""

from __future__ import annotations

from alf.tools._guards import check_url, scan_injection
from alf.tools.base import Tool, ToolResult

JINA_BASE = "https://r.jina.ai/"


class WebFetch(Tool):
    name = "web_fetch"
    description = (
        "Fetch a URL as clean Markdown. Use when you need to SEE the full "
        "page content (the user asked \"show me the page\", \"give me the "
        "full markdown\").\n"
        "\n"
        "DO NOT use for:\n"
        "  • answering a specific question about the page → use "
        "`web_extract` (way cheaper, LLM-summarizes)\n"
        "  • HTTP via shell → never `terminal curl/wget`\n"
        "\n"
        "Proxy via Jina Reader for anti-bot resilience, falls back to "
        "direct httpx + html2text. `raw=True` for raw HTML."
    )
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string"},
            "max_bytes": {"type": "integer", "default": 250_000,
                          "description": "Byte cap on the response."},
            "strip_links": {"type": "boolean", "default": False,
                            "description": "Drop link URLs (keep link text). Saves tokens."},
            "raw": {"type": "boolean", "default": False,
                    "description": "Bypass Jina; return raw HTML from direct fetch."},
        },
        "required": ["url"],
    }

    def run(
        self,
        url: str,
        max_bytes: int = 250_000,
        strip_links: bool = False,
        raw: bool = False,
    ) -> ToolResult:
        from alf.tools._state import emit_state
        safe, reason = check_url(url)
        if not safe:
            return ToolResult(ok=False, output="", error=f"refused: {reason}")

        if raw:
            emit_state("reading raw HTML…")
            result = _direct_fetch(url, max_bytes, raw=True, strip_links=strip_links)
        else:
            emit_state("reading page…")
            jina = _jina_fetch(url, max_bytes)
            if jina is not None:
                result = ToolResult(ok=True, output=jina)
            else:
                emit_state("reader unreachable — trying direct", error=True)
                result = _direct_fetch(url, max_bytes, raw=False, strip_links=strip_links)

        if result.ok:
            warning = scan_injection(result.output)
            if warning:
                result = ToolResult(ok=True, output=f"{warning}\n\n{result.output}")
        return result


def _jina_fetch(url: str, max_bytes: int) -> str | None:
    import httpx
    proxy_url = JINA_BASE + url
    try:
        with httpx.Client(follow_redirects=True, timeout=30) as client:
            r = client.get(proxy_url, headers={
                "User-Agent": "alf/0.0.1",
                "Accept": "text/plain",
            })
        if r.status_code != 200:
            return None
        body = r.text.strip()
        if not body:
            return None
        return body[:max_bytes]
    except httpx.HTTPError:
        return None


def _direct_fetch(url: str, max_bytes: int, raw: bool, strip_links: bool) -> ToolResult:
    import httpx
    try:
        with httpx.Client(follow_redirects=True, timeout=30) as client:
            r = client.get(url, headers={"User-Agent": "alf/0.0.1"})
        r.raise_for_status()
    except httpx.HTTPError as e:
        return ToolResult(ok=False, output="", error=str(e))

    body = r.text[:max_bytes]
    if raw:
        return ToolResult(ok=True, output=body)

    try:
        markdown = _html_to_markdown(body, strip_links=strip_links)
    except Exception as e:  # noqa: BLE001
        return ToolResult(ok=True, output=body, error=f"(markdown conversion failed: {e})")

    return ToolResult(ok=True, output=markdown)


def _html_to_markdown(html: str, strip_links: bool = False) -> str:
    import re
    import html2text

    h = html2text.HTML2Text()
    h.ignore_links = strip_links
    h.ignore_images = True
    h.body_width = 0
    h.skip_internal_links = True
    h.protect_links = True
    h.single_line_break = True
    md = h.handle(html)
    md = re.sub(r"\n{3,}", "\n\n", md).strip()
    return md


TOOL = WebFetch
