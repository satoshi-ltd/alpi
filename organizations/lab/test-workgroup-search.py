#!/usr/bin/env python
# Product acceptance for ALP.6 — "decision made in a workgroup, found later by meaning". Real crypto + fastembed, no daemon, no LLM.
#   uv run python organizations/lab/test-workgroup-search.py
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


def _seed_hub_workgroup(home: Path, bodies: list[bytes]) -> str:
    from alpi.alp import workgroup as wg_mod
    from alpi.alp.keys import load_or_generate

    kp = load_or_generate(home)
    wg = wg_mod.create(home, name="launch-bench", hub_kp=kp, member_pubkeys=[], briefing="")
    me = wg.member(kp.pubkey_b64())
    group_key = wg_mod.open_sealed_group_key(me.sealed_key, kp)
    d = home / "alp" / "workgroups" / wg.meta.id
    lines = []
    for i, body in enumerate(bodies, start=1):
        nonce_b64, ct_b64 = wg_mod.encrypt_post(group_key, body)
        lines.append(json.dumps({
            "seq": i, "ts": "2026-06-04T12:30:00Z", "from": kp.pubkey_b64(),
            "key_version": me.key_version, "nonce": nonce_b64, "ciphertext": ct_b64,
        }, separators=(",", ":")))
    (d / "transcript.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return wg.meta.id


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="alpi-alp6-") as tmp:
        home = Path(tmp) / "mind"
        home.mkdir()
        os.environ["ALPI_HOME"] = str(home)

        from alpi.tools import workgroup_search as wgs

        print(f"\n{BOLD}ALP.6 — recall a workgroup decision by meaning{RESET}")
        print(f"{GREY}profile=mind  home={home}{RESET}\n")

        wg_id = _seed_hub_workgroup(home, [
            b"@mira We decided the launch gate is: no placeholders anywhere.",
            b"@lens QA should block release if a hotel's phone or address is missing.",
            b"@pixel Hero image must be real, not a stock template.",
        ])
        print(f"{GREY}sealed, encrypted transcript written for {wg_id}; the words are now ciphertext on disk.{RESET}")

        summary = wgs.index_workgroups(home)
        results = wgs.workgroup_search(home, wg_id, "what blocks launch quality", k=5)

        ok = True
        ok &= _check("hub transcript indexed", summary["indexed_workgroups"] == 1)
        ok &= _check("search returns a match", bool(results))
        ok &= _check("snippet carries the real decision (no placeholders / phone / address)",
                     any(("placeholders" in r["snippet"]) or ("phone" in r["snippet"]) or ("address" in r["snippet"])
                         for r in results))
        ok &= _check("result names the authors", bool(results) and bool(results[0]["authors"]))

        if results:
            top = results[0]
            print(f"\n{GREY}recalled seq {top['seq_start']}–{top['seq_end']} ({top['when']}) by {', '.join(top['authors'])}:{RESET}")
            print(f"{GREY}  “{top['snippet'].strip().splitlines()[-1][:80]}”{RESET}\n")

        wgs.forget_workgroup(home, wg_id)
        after = wgs.workgroup_search(home, wg_id, "launch gate", k=5)
        ok &= _check("forgettable: removing the workgroup drops it from search", after == [])

        print()
        if ok:
            print(f"{GREEN}{BOLD}PASS{RESET} — decrypted a hub transcript, recalled the decision by meaning, then forgot it.\n")
            return 0
        print(f"{RED}{BOLD}FAIL{RESET}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
