#!/usr/bin/env python
# Product acceptance for RAG.2 — "learn now, recall later". No LLM, no workgroup, no ALP.
#   uv run python organizations/lab/test-knowledge-recall.py
from __future__ import annotations

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


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="alpi-rag2-") as tmp:
        tmp = Path(tmp)
        home = tmp / "mind"          # the lab profile's home
        workspace = tmp / "workspace"
        home.mkdir()
        workspace.mkdir()
        os.environ["ALPI_HOME"] = str(home)
        (home / "config.yaml").write_text(f"workspace: {workspace}\n")

        from alpi.core.store import store_path
        from alpi.tools import _state
        from alpi.tools import workspace as ws_mod
        from alpi.tools.learn_file import LearnFile

        print(f"\n{BOLD}RAG.2 — learn now, recall later{RESET}")
        print(f"{GREY}profile=mind  home={home}  workspace={workspace}{RESET}\n")

        incoming = tmp / "downloads" / "deal-memo.md"
        incoming.parent.mkdir(parents=True)
        incoming.write_text(f"# Deal memo\n\n{UNIQUE}\n\nReview before the board call.\n")
        _state.set_turn_attachments([
            {"name": "deal-memo.md", "path": str(incoming), "mime": "text/markdown"},
        ])
        print(f"{GREY}before: attachment is visible only this turn — next session it's gone.{RESET}")

        out = LearnFile().run()
        if not out.ok:
            print(f"{RED}learn_file failed: {out.error}{RESET}")
            return 1
        import json
        body = json.loads(out.output)
        print(f"{GREY}learn_file → {body}{RESET}\n")

        ok = True
        ok &= _check("document copied into the workspace (source of truth)",
                     (workspace / body.get("path", "x")).is_file())
        ok &= _check("stored under .alpi/documents/",
                     body.get("path", "").startswith(".alpi/documents/"))
        ok &= _check("manifest.jsonl written",
                     (workspace / ".alpi" / "documents" / "manifest.jsonl").is_file())
        ok &= _check("RAG index lives in the profile (rag/store.sqlite)",
                     store_path(home).is_file())

        res = ws_mod.SearchWorkspace().run(query="what is the renewal threshold", k=5)
        results = json.loads(res.output).get("results", []) if res.ok else []
        ok &= _check("search_workspace finds the learned doc by meaning", bool(results))
        ok &= _check("hit is the workspace document",
                     any(".alpi/documents/" in r["path"] for r in results))
        ok &= _check("snippet carries the real content (42 seats / BLUE HERON)",
                     any("42 seats" in r["snippet"] or "BLUE HERON" in r["snippet"] for r in results))

        if results:
            top = results[0]
            print(f"\n{GREY}recalled: {top['path']}{RESET}")
            print(f"{GREY}  “{top['snippet'].strip().splitlines()[-1][:80]}”{RESET}")

        print()
        if ok:
            print(f"{GREEN}{BOLD}PASS{RESET} — learned a file, recalled it later by meaning; "
                  f"document in workspace, index in profile.\n")
            return 0
        print(f"{RED}{BOLD}FAIL{RESET}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
