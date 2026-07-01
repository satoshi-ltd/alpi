#!/usr/bin/env python
# Product acceptance for CM.4 — "talked about it once, find it later by meaning". No LLM, no ALP, no gateway.
#   uv run python organizations/lab/test-session-recall.py
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

GREEN, RED, GREY, BOLD, RESET = "\033[32m", "\033[31m", "\033[90m", "\033[1m", "\033[0m"


def _check(label: str, cond: bool) -> bool:
    print(f"  {(GREEN + '✓' + RESET) if cond else (RED + '✗' + RESET)} {label}")
    return cond


def _session(home: Path, sid: str, turns: list[dict], started_at: float) -> None:
    sdir = home / "sessions"
    sdir.mkdir(parents=True, exist_ok=True)
    (sdir / f"{sid}.json").write_text(json.dumps({"id": sid, "started_at": started_at, "turns": turns}))


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="alpi-cm4-") as tmp:
        home = Path(tmp) / "mind"
        home.mkdir()
        os.environ["ALPI_HOME"] = str(home)

        from alpi.core.store import store_path
        from alpi.tools import recall as rc
        from alpi.host import sessions as host_sessions

        print(f"\n{BOLD}CM.4 — recall a past conversation by meaning{RESET}")
        print(f"{GREY}profile=mind  home={home}{RESET}\n")

        _session(home, "infra-chat", [
            {"user": "where do the database backups go",
             "assistant": "Postgres on RDS, daily snapshots to S3"},
        ], started_at=1700000000.0)
        _session(home, "pricing-chat", [
            {"user": "what did we land on for enterprise renewals",
             "assistant": "the renewal threshold for enterprise seats is 42 seats, billed annually"},
        ], started_at=1700100000.0)
        print(f"{GREY}two past sessions written; the exact words are forgotten — only the gist remains.{RESET}")

        rc.index_sessions(home)
        results = rc.recall(home, "seat threshold for renewals", k=3)

        ok = True
        ok &= _check("recall returns a match", bool(results))
        ok &= _check("top hit is the pricing conversation",
                     bool(results) and results[0]["session_id"] == "pricing-chat")
        ok &= _check("snippet carries the real content (42 seats)",
                     any("42 seats" in r["snippet"] for r in results))
        ok &= _check("index lives in the profile (knowledge.sqlite)", store_path(home).is_file())

        if results:
            top = results[0]
            print(f"\n{GREY}recalled session {top['session_id']} ({top['when']}):{RESET}")
            print(f"{GREY}  “{top['snippet'].strip().splitlines()[-1][:80]}”{RESET}\n")

        host_sessions.delete_session(home, "pricing-chat")
        after = rc.recall(home, "seat threshold for renewals", k=3)
        ok &= _check("forgettable: deleting the session drops it from recall",
                     all(r["session_id"] != "pricing-chat" for r in after))

        print()
        if ok:
            print(f"{GREEN}{BOLD}PASS{RESET} — found a past conversation by meaning, then forgot it on delete.\n")
            return 0
        print(f"{RED}{BOLD}FAIL{RESET}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
