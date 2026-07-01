#!/usr/bin/env python
# Product acceptance for workspace knowledge recall. No LLM, no workgroup, no ALP.
#   uv run python organizations/lab/test-knowledge-recall.py
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

GREEN, RED, GREY, BOLD, RESET = "\033[32m", "\033[31m", "\033[90m", "\033[1m", "\033[0m"

UNIQUE = "The project codename is BLUE HERON and the renewal threshold is 42 seats."


def _check(label: str, cond: bool) -> bool:
    mark = f"{GREEN}✓{RESET}" if cond else f"{RED}✗{RESET}"
    print(f"  {mark} {label}")
    return cond


def _page(title: str, body: str, page_type: str = "concept") -> str:
    return (
        "---\n"
        f"type: {page_type}\n"
        f"title: {title}\n"
        "tags: []\n"
        "updated_at: \"2026-07-01T00:00:00Z\"\n"
        "sources: []\n"
        "---\n\n"
        f"{body.strip()}\n"
    )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="alpi-knowledge-") as tmp:
        tmp = Path(tmp)
        home = tmp / "mind"
        workspace = tmp / "workspace"
        home.mkdir()
        workspace.mkdir()
        os.environ["ALPI_HOME"] = str(home)
        (home / "config.yaml").write_text(f"workspace: {workspace}\n")

        from alpi.core.store import store_path
        from alpi.tools.knowledge_base import Knowledge

        print(f"\n{BOLD}Knowledge recall - index now, recall later{RESET}")
        print(f"{GREY}profile=mind  home={home}  workspace={workspace}{RESET}\n")

        root = workspace / "knowledge"
        (root / "concepts").mkdir(parents=True)
        (root / "index.md").write_text(
            _page("Knowledge Index", "# Knowledge Index\n\n- [Deal Memo](concepts/deal-memo.md)", "note")
        )
        (root / "log.md").write_text(_page("Knowledge Log", "# Knowledge Log", "note"))
        (root / "concepts" / "deal-memo.md").write_text(
            _page("Deal Memo", f"# Deal Memo\n\n{UNIQUE}\n\nReview before the board call.")
        )

        indexed = Knowledge().run(action="index")
        if not indexed.ok:
            print(f"{RED}knowledge index failed: {indexed.error}{RESET}")
            return 1
        print(f"{GREY}knowledge index -> {indexed.output}{RESET}\n")

        result = Knowledge().run(action="search", query="what is the renewal threshold", k=5)
        results = json.loads(result.output).get("results", []) if result.ok else []

        ok = True
        ok &= _check("knowledge page lives in the workspace",
                     (workspace / "knowledge" / "concepts" / "deal-memo.md").is_file())
        ok &= _check("derived index lives in the profile (knowledge.sqlite)",
                     store_path(home).is_file())
        ok &= _check("knowledge search finds the page by meaning", bool(results))
        ok &= _check("snippet carries the real content (42 seats / BLUE HERON)",
                     any("42 seats" in r["snippet"] or "BLUE HERON" in r["snippet"] for r in results))

        if results:
            top = results[0]
            print(f"\n{GREY}recalled: {top['path']}{RESET}")
            print(f"{GREY}  \"{top['snippet'].strip().splitlines()[-1][:80]}\"{RESET}")

        print()
        if ok:
            print(f"{GREEN}{BOLD}PASS{RESET} - indexed knowledge and recalled it later by meaning.\n")
            return 0
        print(f"{RED}{BOLD}FAIL{RESET}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
