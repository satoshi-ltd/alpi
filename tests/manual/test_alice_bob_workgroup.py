"""End-to-end manual test of the ALP.3 autonomous workgroup loop.

Run::

    uv run python scripts/test_alice_bob_workgroup.py

What it does, in order:

1. Sanity-checks both profiles (alice + bob) exist with workspace,
   ALP keypair, and the peers pinned in each direction.
2. Wipes any existing workgroup state on alice's hub (so the test
   starts from a clean transcript + ledger).
3. Creates a fresh workgroup ``stack-decision`` on alice as hub,
   inviting bob, with a clear briefing and a $3 lifetime budget.
4. Bob joins and harvests the sealed group key.
5. Resets the workgroup-poller state on both profiles
   (cursors, cooldowns, responded-seq pointers, recent_posts cache).
6. Restarts both services so the new code is loaded and the
   pollers start from zero.
7. Posts the kickoff message via bob (the only "human" message
   in the conversation).
8. Polls the transcript every 20s, printing each new post as it
   arrives, until the active task is closed with `#done`, the
   workgroup budget caps, or a 25-minute timeout.

You should see:
- alice and bob alternating responses every ~60s
- web-search/research evidence in their early posts (numbers,
  sources, framework benchmarks)
- mid-conversation convergence on a recommendation
- one of them posting `#done <result>` to close

If the conversation paraphrases without closing, that's a
prompt-engineering miss in the engagement rules — interrupt and
investigate; the protocol itself is fine.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path.home() / ".alpi"
ALICE = ROOT / "profiles" / "alice"
BOB = ROOT / "profiles" / "bob"
WG_NAME = "stack-decision"
BRIEFING = (
    "Decide stack for a personal task tracker REST API: ~10 endpoints, "
    "single user, run 5+ years on a small VPS. Two complementary angles: "
    "alice (product velocity, ship-now bias) + bob (systems durability, "
    "migration-cost bias). Converge on FastAPI vs Flask AND SQLite vs "
    "Postgres. EVIDENCE EXPECTED: each of you must cite at least one "
    "recent (2024-2026) source — GitHub trends, benchmarks, postmortems, "
    "or production case studies — to back your position. Use web_search "
    "and web_fetch as needed. Final #done must include the recommendation "
    "with 2-3 concrete reasons (with source citations) per choice."
)
KICKOFF = (
    "@alice @bob #task pick stack for our personal task tracker "
    "(FastAPI vs Flask, SQLite vs Postgres). cite real numbers from "
    "2024-2026, react to each other, converge with #done. budget $3."
)
BUDGET_USD = 3.0
TIMEOUT_SECONDS = 25 * 60
POLL_SECONDS = 20

# Pretty-printing colours (match your terminal).
GREY, BLUE, GREEN, YELLOW, RED, RESET = (
    "\033[2m", "\033[36m", "\033[32m", "\033[33m", "\033[31m", "\033[0m",
)


def step(msg: str) -> None:
    print(f"{BLUE}→{RESET} {msg}")


def ok(msg: str) -> None:
    print(f"{GREEN}✓{RESET} {msg}")


def warn(msg: str) -> None:
    print(f"{YELLOW}!{RESET} {msg}")


def fail(msg: str) -> str:
    print(f"{RED}✗{RESET} {msg}")
    sys.exit(1)


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, check=False, **kw)


# Step 1 — sanity


def sanity() -> None:
    step("checking profiles")
    for h in (ALICE, BOB):
        if not h.exists():
            fail(f"{h} missing — create it first via `alpi profile create`")
        if not (h / "alp" / "secrets" / "alp_key.pub").exists():
            fail(f"{h.name} has no ALP keypair — run `alpi -p {h.name} service start` once")
        cfg = (h / "config.yaml").read_text()
        if "workspace:" not in cfg:
            fail(f"{h.name} has no workspace set — `alpi -p {h.name} setup → Workspace`")

    # alice must have bob pinned, bob must have alice pinned
    for hub, peer in ((ALICE, "bob"), (BOB, "alice")):
        peers_file = hub / "alp" / "peers.yaml"
        if not peers_file.exists() or peer not in peers_file.read_text():
            fail(f"{hub.name} has no peer entry for @{peer} — set up peers first")
    ok("profiles look healthy")


# Step 2 — wipe old state


def wipe_old_workgroups() -> None:
    step("wiping old workgroup state on alice (hub)")
    wg_root = ALICE / "alp" / "workgroups"
    if wg_root.exists():
        for d in wg_root.iterdir():
            if d.is_dir():
                shutil.rmtree(d)
        ok(f"removed {wg_root}/*")
    # Drop bob's stale subscription to any old workgroup
    sub_path = BOB / "alp" / "secrets" / "subscriptions.yaml"
    if sub_path.exists():
        sub_path.unlink()
        ok("cleared bob's subscriptions")

    # Public bios live in each profile's config.yaml — the user owns
    # them (set via `alpi setup → ALP → Identity`). The script does not
    # touch them; whatever's there propagates to the workgroup roster
    # via create() (alice as hub) and workgroup.join (bob).
    import yaml as _yaml
    for h in (ALICE, BOB):
        cfg = _yaml.safe_load((h / "config.yaml").read_text()) or {}
        bio = (cfg.get("public_bio") or "").strip()
        if bio:
            ok(f"{h.name} bio: {bio[:70]}")
        else:
            ok(f"{h.name} bio: (not set — peers will see handle only)")


# Step 3 — create + invite


def create_workgroup() -> str:
    step("creating workgroup as alice")
    res = run([
        "alpi", "-p", "alice", "workgroup", "create", WG_NAME,
        "--member", "bob", "--budget-usd", str(BUDGET_USD),
    ])
    if res.returncode != 0:
        fail(f"workgroup create failed: {res.stderr}")
    # The CLI doesn't take a briefing arg yet; patch it into meta.yaml
    wg_dirs = list((ALICE / "alp" / "workgroups").iterdir())
    if not wg_dirs:
        fail("workgroup directory not created")
    wg_dir = wg_dirs[0]
    wg_id = wg_dir.name

    import yaml
    meta_path = wg_dir / "meta.yaml"
    meta = yaml.safe_load(meta_path.read_text())
    meta["briefing"] = BRIEFING
    meta_path.write_text(yaml.safe_dump(meta, sort_keys=False))
    ok(f"created {wg_id} ({WG_NAME}) with briefing + ${BUDGET_USD} budget")
    return wg_id


# Step 4 — bob joins


def bob_joins(wg_id: str) -> None:
    step("bob joining as remote member")
    res = run(["alpi", "-p", "bob", "workgroup", "join", "alice", wg_id])
    if res.returncode != 0:
        fail(f"bob join failed: {res.stderr}")
    ok("bob received sealed group key + briefing")


# Step 5 — reset poller state


def reset_poller_state() -> None:
    step("resetting poller state on both profiles")
    code = (
        "from alpi import service as svc\n"
        "from alpi.alp import subscription as sub_mod\n"
        "from pathlib import Path\n"
        "for p in ['alice', 'bob']:\n"
        "    home = Path.home() / '.alpi' / 'profiles' / p\n"
        "    state = svc._load_poller_state(home)\n"
        "    state.pop('hub_cursors', None)\n"
        "    state.pop('hub_last_dispatch_at', None)\n"
        "    state.pop('hub_last_responded_seq', None)\n"
        "    svc._save_poller_state(home, state)\n"
        "    subs = sub_mod.load(home)\n"
        "    for s in subs:\n"
        "        s.last_dispatch_at = ''\n"
        "        s.last_seq = 0\n"
        "        s.last_responded_seq = 0\n"
        "        s.recent_posts = []\n"
        "    sub_mod.save(home, subs)\n"
    )
    res = run(["uv", "run", "python", "-c", code], cwd=str(Path(__file__).parent.parent))
    if res.returncode != 0:
        fail(f"poller reset failed: {res.stderr}")
    ok("cursors + cooldowns + recent_posts cache cleared")


# Step 6 — restart services + wait for ALP listeners to be reachable


def restart_services() -> None:
    step("restarting services so they pick up the latest binary")
    for p in ("alice", "bob"):
        res = run(["alpi", "-p", p, "service", "restart"])
        if res.returncode != 0:
            fail(f"{p} service restart failed: {res.stderr}")
    # launchd respawns within ~1-2s; the alp listener takes another
    # second to bind. Poll the loopback dial until it answers, up to
    # 20s, instead of guessing with a fixed sleep.
    deadline = time.time() + 20
    while time.time() < deadline:
        # bob → alice over alice's loopback TCP (the path the kickoff
        # post uses). If this responds, both services are up enough.
        probe = run(["alpi", "-p", "bob", "peers", "ping", "alice"])
        if probe.returncode == 0:
            ok(f"both services up — alice answered ping in "
               f"{int(time.time() - (deadline - 20))}s")
            return
        time.sleep(1)
    fail("alice's ALP listener didn't respond to ping within 20s — "
         "check `alpi -p alice service status` and the service.log")


# Step 7 — kickoff


def post_kickoff(wg_id: str) -> None:
    step("posting kickoff via bob (this is the only 'human' message)")
    res = run(["alpi", "-p", "bob", "workgroup", "post", wg_id, KICKOFF])
    if res.returncode != 0:
        fail(f"kickoff post failed: {res.stderr}")
    ok(f"kickoff posted: {KICKOFF[:100]}…")


# Step 8 — watch


def watch(wg_id: str) -> None:
    print()
    print(f"{BLUE}=== watching transcript (poll every {POLL_SECONDS}s, "
          f"timeout {TIMEOUT_SECONDS // 60} min) ==={RESET}")
    print(f"{GREY}you should see alice + bob alternating with web-search "
          f"evidence, then converging with `#done`{RESET}")
    print()

    seen_seq = 0
    deadline = time.time() + TIMEOUT_SECONDS
    last_status_at = 0.0

    while time.time() < deadline:
        posts, ledger = read_state(wg_id)
        if posts:
            for p in posts:
                if int(p["seq"]) <= seen_seq:
                    continue
                seen_seq = int(p["seq"])
                _print_post(p)

            latest_text = posts[-1].get("text", "")
            if any(line.startswith("#done") or line.startswith("@")
                   and "#done" in line.split(None, 1)[1:]
                   for line in latest_text.splitlines()):
                print()
                ok(f"task CLOSED with #done — final ledger: ${ledger.get('usd', 0):.4f} / "
                   f"{ledger.get('tokens', 0):,} tokens / {ledger.get('posts', 0)} posts")
                return

        # Budget exhausted?
        if ledger.get("usd", 0) >= BUDGET_USD * 0.95:
            warn(f"workgroup budget at 95%+ (${ledger['usd']:.2f}/${BUDGET_USD}) — "
                 f"hub will start refusing posts soon")

        # Periodic status to show liveness.
        if time.time() - last_status_at > 60:
            last_status_at = time.time()
            elapsed = int(time.time() - (deadline - TIMEOUT_SECONDS))
            print(f"{GREY}  · {elapsed}s elapsed · {len(posts)} posts · "
                  f"${ledger.get('usd', 0):.4f} spent · waiting…{RESET}")

        time.sleep(POLL_SECONDS)

    warn(f"timed out after {TIMEOUT_SECONDS}s — task still open. "
         "investigate prompt or guardrails.")


def read_state(wg_id: str) -> tuple[list[dict], dict]:
    """Decrypt the transcript via the in-process service helpers."""
    code = (
        "import json, sys\n"
        "from pathlib import Path\n"
        "from alpi import service as svc\n"
        "from alpi.alp import workgroup as wg_mod\n"
        f"home = Path.home() / '.alpi' / 'profiles' / 'alice'\n"
        f"wg = wg_mod.load(home, '{wg_id}')\n"
        "if wg is None:\n"
        "    print(json.dumps({'posts': [], 'ledger': {}})); sys.exit(0)\n"
        "posts = svc._all_hub_posts_decrypted(home, wg)\n"
        f"ledger_path = home / 'alp' / 'workgroups' / '{wg_id}' / 'ledger.json'\n"
        "ledger = json.loads(ledger_path.read_text()) if ledger_path.exists() else {}\n"
        "out = []\n"
        "for p in posts:\n"
        "    out.append({'seq': p['seq'], 'from': p['from'], 'text': p.get('text',''),"
        " 'cost': p.get('cost', {})})\n"
        "print(json.dumps({'posts': out, 'ledger': ledger}))\n"
    )
    res = run(["uv", "run", "python", "-c", code], cwd=str(Path(__file__).parent.parent))
    if res.returncode != 0:
        return [], {}
    try:
        data = json.loads(res.stdout.strip().splitlines()[-1])
        return data.get("posts", []), data.get("ledger", {})
    except (json.JSONDecodeError, IndexError):
        return [], {}


def _print_post(p: dict) -> None:
    pubkey = p.get("from", "")
    if pubkey.startswith("zlS"):
        who = f"{BLUE}alice{RESET}"
    elif pubkey.startswith("+W9"):
        who = f"{GREEN}bob{RESET}"
    else:
        who = f"{GREY}{pubkey[:10]}{RESET}"
    cost = p.get("cost") or {}
    cost_str = (
        f" {GREY}[${cost.get('usd', 0):.4f}/{cost.get('tokens', 0):,}tok]{RESET}"
        if cost else ""
    )
    text = p.get("text", "").strip()
    if len(text) > 600:
        text = text[:597] + "…"
    print(f"{GREY}#{p['seq']:>2}{RESET} {who}{cost_str}:")
    for line in text.splitlines():
        print(f"     {line}")
    print()


def main() -> int:
    print(f"{BLUE}=== ALP.3 alice + bob autonomous workgroup test ==={RESET}")
    print()
    sanity()
    wipe_old_workgroups()
    wg_id = create_workgroup()
    bob_joins(wg_id)
    reset_poller_state()
    restart_services()
    post_kickoff(wg_id)
    watch(wg_id)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
