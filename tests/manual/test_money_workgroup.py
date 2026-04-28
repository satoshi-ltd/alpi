"""Oneshot end-to-end test of a 3-peer ALP.3 autonomous workgroup.

Run::

    uv run python tests/manual/test_money_workgroup.py

This script owns the three profiles (alice, bob, carol) end-to-end:
nukes them, recreates them, copies only OPENAI_API_KEY from
~/.alpi/.env, pins openai/gpt-5.4-nano as the model, writes role bios,
installs the launchd services, cross-pins all three pairs, then drives
a workgroup task: scope the next feature for the Money app
(https://satoshi-ltd.com/case-studies/money).

  carol — user researcher: web_fetches the page, extracts facts.
  alice — product manager: turns research into feature candidates.
  bob   — marketer: pushes back on positioning, picks the GTM winner.

WARNING: this WIPES ~/.alpi/profiles/{alice,bob,carol} every run. Do
not point this at profiles you actually use day-to-day.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

_DONE_MARKER = re.compile(r"^\s*(?:@\S+\s+)*#done(?:\s|$)")

ROOT = Path.home() / ".alpi"
PROFILES = ("alice", "bob", "carol")
HUB = "alice"
HOMES = {p: ROOT / "profiles" / p for p in PROFILES}
MODEL = "openai/gpt-5.4-nano"
WORKSPACE = str(Path.home())

BIOS = {
    "alice": (
        "Product manager — turns research into 2-3 feature candidates "
        "scored on user value, build cost, and roadmap fit."
    ),
    "bob": (
        "Marketer — pushes positioning and GTM; picks the candidate "
        "with the strongest audience narrative and 2024-2026 signals."
    ),
    "carol": (
        "User researcher — extracts pain points, audience signals, "
        "and feature gaps from product pages and case studies."
    ),
}
ACCENTS = {
    "alice": "#c8a24e",
    "bob":   "#5fafd7",
    "carol": "#d75f87",
}

WG_NAME = "money-2026"
URL = "https://satoshi-ltd.com/case-studies/money"
BRIEFING = (
    "Money (a privacy-first personal-finance app by Satoshi Ltd, "
    f"case study at {URL}) is at a strategic bifurcation for 2026. "
    "Two paths on the table, both viable, both with real costs:\n"
    "\n"
    "  PATH A — DOUBLE DOWN ON PRIVACY-PURIST NICHE. Stay 100% "
    "on-device, no cloud anything, deepen the iOS-only experience "
    "with on-device LLM-driven categorization + insights, launch "
    "a paid premium tier ($3/mo) for power users. Trade-off: TAM "
    "stays small but defensibility and narrative are sharp.\n"
    "\n"
    "  PATH B — BROADEN TO MAINSTREAM WITH OPTIONAL E2E-ENCRYPTED "
    "SYNC. Add multi-device sync (iCloud/CloudKit or self-hosted) "
    "with end-to-end encryption so the privacy promise survives, "
    "ship Android, run mainstream paid acquisition. Trade-off: "
    "TAM expands ~5x but the narrative softens (\"E2E encrypted "
    "is not the same as zero-bytes-sent\") and dev complexity "
    "balloons.\n"
    "\n"
    "Pick ONE path. The right answer requires both a PM lens "
    "(feasibility, cost, roadmap, retention) AND a GTM lens "
    "(narrative, positioning, audience signal) to land on the "
    "same path with explicit defenses, not assertions.\n"
    "\n"
    "Per-role contributions:\n"
    "\n"
    "@carol — user researcher. BOOTSTRAP ONLY: you post ONCE, then "
    "stay silent for the rest of the session. Before posting you "
    "MUST (a) call web_fetch on the case-study URL, AND (b) call "
    "web_search for at least one 2024-2026 signal about the "
    "privacy-finance category (DAU trends, competitor launches, "
    "App Store review themes about bank-linking apps, paid-sync "
    "service adoption). Your single post is a bullet summary of "
    "what the page promises + what the market is actually doing, "
    "in a way that gives BOTH paths real evidence. Do NOT take a "
    "side. If you have not invoked web_fetch + web_search this "
    "turn, stay silent.\n"
    "\n"
    "@alice — product manager (also the workgroup hub). After "
    "carol's research lands, post your PM read: which path has "
    "better feasibility / build cost / 12-month roadmap fit / "
    "retention math? Default lean: B (TAM math + retention from "
    "multi-device usually wins on PM lens). EXPECT BOB TO PUSH "
    "BACK on narrative grounds. When he does, you MUST respond — "
    "defend B with concrete PM arguments OR concede to A if his "
    "counter on dev complexity / niche defensibility is stronger. "
    "Iterate. Your goal is not to win but to find the path where "
    "both lenses align with explicit defenses in the transcript. "
    "As the hub, you close the task with #done once that's real.\n"
    "\n"
    "@bob — marketer. After carol's research AND alice's PM read, "
    "post your GTM read on both paths. Default lean: A (privacy "
    "purist has the sharper 2024-2026 narrative — every "
    "bank-linking competitor breach is free marketing). If alice "
    "advocated B, push back hard with audience evidence: cite the "
    "real signal carol surfaced or one of your own. Do NOT "
    "capitulate just because she's the hub or PM — narrative "
    "trumps TAM if the broader audience never trusts you. You "
    "may concede only after alice gives a concrete defense you "
    "can't break."
)
KICKOFF = (
    "#task Money is at a strategic bifurcation for 2026: pick "
    "PATH A (privacy-purist niche, on-device only, paid premium) "
    "vs PATH B (mainstream broadening with E2E-encrypted sync + "
    "Android). Each path has real tradeoffs — defend the choice "
    "with both PM and GTM lenses, not just assertions."
)
BUDGET_USD = 5.0
TIMEOUT_SECONDS = 30 * 60
POLL_SECONDS = 20

GREY, BLUE, GREEN, YELLOW, RED, MAGENTA, RESET = (
    "\033[2m", "\033[36m", "\033[32m", "\033[33m", "\033[31m", "\033[35m", "\033[0m",
)
PEER_COLOR = {"alice": BLUE, "bob": GREEN, "carol": MAGENTA}


def step(msg: str) -> None:
    print(f"{BLUE}→{RESET} {msg}")


def ok(msg: str) -> None:
    print(f"{GREEN}✓{RESET} {msg}")


def warn(msg: str) -> None:
    print(f"{YELLOW}!{RESET} {msg}")


def fail(msg: str) -> None:
    print(f"{RED}✗{RESET} {msg}")
    sys.exit(1)


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, check=False, **kw)


# Step 1 — nuke


def nuke_profiles() -> None:
    step("nuking profiles (uninstall launchd + stop + remove dir)")
    for p in PROFILES:
        run(["alpi", "-p", p, "service", "stop"])
        uninstall_code = (
            "from alpi import service as svc\n"
            "from pathlib import Path\n"
            f"home = Path.home() / '.alpi' / 'profiles' / '{p}'\n"
            "try:\n"
            f"    svc.uninstall(home, '{p}')\n"
            "except Exception:\n"
            "    pass\n"
        )
        run(["uv", "run", "python", "-c", uninstall_code],
            cwd=str(Path(__file__).parent.parent))
        if HOMES[p].exists():
            shutil.rmtree(HOMES[p])
            ok(f"removed {HOMES[p]}")
    time.sleep(1)


# Step 2 — read default OPENAI_API_KEY


def read_openai_key() -> str:
    default_env = ROOT / ".env"
    if not default_env.exists():
        fail(f"{default_env} missing — can't bootstrap profiles")
    for line in default_env.read_text().splitlines():
        s = line.strip()
        if s.startswith("OPENAI_API_KEY="):
            val = s.split("=", 1)[1].strip().strip('"').strip("'")
            if val:
                return val
    fail("OPENAI_API_KEY missing or empty in ~/.alpi/.env")
    return ""  # unreachable


# Step 3 — bootstrap profiles


def bootstrap_profiles(api_key: str) -> None:
    step("creating fresh profiles + writing config + installing services")
    import yaml

    for p in PROFILES:
        res = run(["alpi", "profile", "create", p])
        if res.returncode != 0:
            fail(f"profile create {p} failed: {res.stderr}")

        (HOMES[p] / ".env").write_text(f"OPENAI_API_KEY={api_key}\n")

        cfg_path = HOMES[p] / "config.yaml"
        cfg = yaml.safe_load(cfg_path.read_text()) or {}
        cfg["model"] = MODEL
        cfg["workspace"] = WORKSPACE
        cfg["public_bio"] = BIOS[p]
        cfg.setdefault("tui", {})["accent"] = ACCENTS[p]
        cfg_path.write_text(yaml.safe_dump(cfg, sort_keys=False))

        install_code = (
            "from alpi import service as svc\n"
            "from pathlib import Path\n"
            f"home = Path.home() / '.alpi' / 'profiles' / '{p}'\n"
            f"svc.install(home, '{p}')\n"
            "print('installed')\n"
        )
        res = run(["uv", "run", "python", "-c", install_code],
                  cwd=str(Path(__file__).parent.parent))
        if res.returncode != 0:
            fail(f"service install {p} failed: {res.stderr}")
        ok(f"{p}: profile + config + .env + launchd")

    step("waiting for ALP keypairs to be generated")
    deadline = time.time() + 30
    pending = set(PROFILES)
    while time.time() < deadline and pending:
        for p in list(pending):
            if (HOMES[p] / "alp" / "secrets" / "alp_key.pub").exists():
                pending.discard(p)
        if pending:
            time.sleep(1)
    if pending:
        fail(f"ALP keys not generated for {sorted(pending)} after 30s")
    ok("all 3 ALP keypairs generated")


# Step 4 — cross-pin


def cross_pin() -> None:
    step("cross-pinning all 3 pairs")
    pubkeys: dict[str, str] = {}
    for p in PROFILES:
        res = run(["alpi", "-p", p, "peers", "key"])
        if res.returncode != 0 or not res.stdout.strip():
            fail(f"couldn't read {p}'s pubkey: {res.stderr}")
        pubkeys[p] = res.stdout.strip()
    pairs = [(a, b) for i, a in enumerate(PROFILES) for b in PROFILES[i + 1:]]
    for a, b in pairs:
        for hub, peer in ((a, b), (b, a)):
            res = run(["alpi", "-p", hub, "peers", "add", peer, pubkeys[peer]])
            if res.returncode != 0:
                fail(f"{hub} peers add {peer} failed: {res.stderr}")
    ok(f"6 directional pins written")


# Step 5 — create workgroup


def create_workgroup() -> str:
    step(f"creating workgroup as {HUB}")
    members_args: list[str] = []
    for m in PROFILES:
        if m == HUB:
            continue
        members_args += ["--member", m]
    res = run([
        "alpi", "-p", HUB, "workgroup", "create", WG_NAME,
        *members_args, "--budget-usd", str(BUDGET_USD),
    ])
    if res.returncode != 0:
        fail(f"workgroup create failed: {res.stderr}")
    wg_dirs = list((HOMES[HUB] / "alp" / "workgroups").iterdir())
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


# Step 6 — members join


def members_join(wg_id: str) -> None:
    for member in PROFILES:
        if member == HUB:
            continue
        step(f"{member} joining as remote member")
        res = run(["alpi", "-p", member, "workgroup", "join", HUB, wg_id])
        if res.returncode != 0:
            fail(f"{member} join failed: {res.stderr}")
        ok(f"{member} received sealed group key + briefing")


# Step 7 — reset poller state


def reset_poller_state() -> None:
    step("resetting poller state on all profiles")
    profiles_repr = ", ".join(repr(p) for p in PROFILES)
    code = (
        "from alpi import service as svc\n"
        "from alpi.alp import subscription as sub_mod\n"
        "from pathlib import Path\n"
        f"for p in [{profiles_repr}]:\n"
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


# Step 8 — restart services so they reload peers + subscriptions


def restart_services() -> None:
    step("restarting services to load fresh peers + subscriptions")
    for p in PROFILES:
        res = run(["alpi", "-p", p, "service", "restart"])
        if res.returncode != 0:
            fail(f"{p} service restart failed: {res.stderr}")

    deadline = time.time() + 30
    pending = {p for p in PROFILES if p != HUB}
    started = time.time()
    while time.time() < deadline and pending:
        for p in list(pending):
            probe = run(["alpi", "-p", p, "peers", "ping", HUB])
            if probe.returncode == 0:
                pending.discard(p)
        if pending:
            time.sleep(1)
    if pending:
        fail(
            f"{HUB}'s ALP listener didn't answer ping from {sorted(pending)} "
            f"within 30s — check `alpi -p {HUB} service status`"
        )
    ok(f"all services up — pings answered in {int(time.time() - started)}s")


# Step 9 — kickoff


def post_kickoff(wg_id: str) -> None:
    step(f"posting kickoff via {HUB} (the only 'human' message)")
    res = run(["alpi", "-p", HUB, "workgroup", "post", wg_id, KICKOFF])
    if res.returncode != 0:
        fail(f"kickoff post failed: {res.stderr}")
    ok(f"kickoff posted: {KICKOFF[:120]}…")


# Step 10 — watch


def _load_pubkeys() -> dict[str, str]:
    """Map base64 pubkey → handle, by reading each profile's pubkey from
    another profile's peers.yaml (where it's stored in base64 form)."""
    import yaml
    handle_by_pubkey: dict[str, str] = {}
    for target in PROFILES:
        for other in PROFILES:
            if other == target:
                continue
            peers_file = HOMES[other] / "alp" / "peers.yaml"
            if not peers_file.exists():
                continue
            data = yaml.safe_load(peers_file.read_text()) or []
            for entry in data:
                if entry.get("id") == target and entry.get("pubkey"):
                    handle_by_pubkey[entry["pubkey"]] = target
                    break
            if target in handle_by_pubkey.values():
                break
    return handle_by_pubkey


def watch(wg_id: str) -> None:
    print()
    print(f"{BLUE}=== watching transcript (poll every {POLL_SECONDS}s, "
          f"timeout {TIMEOUT_SECONDS // 60} min) ==={RESET}")
    print(f"{GREY}expect: carol researches → alice/bob debate path A "
          f"vs B with defenses → converge → alice (hub) closes{RESET}")
    print()

    pubkey_to_handle = _load_pubkeys()
    seen_seq = 0
    closed = False
    deadline = time.time() + TIMEOUT_SECONDS
    last_status_at = 0.0
    started = time.time()

    while time.time() < deadline:
        posts, ledger = read_state(wg_id)
        if posts:
            for p in posts:
                if int(p["seq"]) <= seen_seq:
                    continue
                seen_seq = int(p["seq"])
                _print_post(p, pubkey_to_handle)
                if any(_DONE_MARKER.match(line) for line in p.get("text", "").splitlines()):
                    closed = True

            if closed:
                print()
                ok(f"task CLOSED with #done — final ledger: "
                   f"${ledger.get('usd', 0):.4f} / "
                   f"{ledger.get('tokens', 0):,} tokens / "
                   f"{ledger.get('posts', 0)} posts")
                return

        if ledger.get("usd", 0) >= BUDGET_USD * 0.95:
            warn(f"workgroup budget at 95%+ (${ledger['usd']:.2f}/${BUDGET_USD}) — "
                 f"hub will start refusing posts soon")

        if time.time() - last_status_at > 60:
            last_status_at = time.time()
            elapsed = int(time.time() - started)
            print(
                f"{GREY}  · {elapsed}s elapsed · {len(posts)} posts · "
                f"${ledger.get('usd', 0):.4f} spent{RESET}"
            )
            _print_turn_panel()

        time.sleep(POLL_SECONDS)

    warn(f"timed out after {TIMEOUT_SECONDS}s — task still open. "
         "investigate prompt or guardrails.")


def _print_turn_panel() -> None:
    """Render a per-profile snapshot of dispatcher activity, reading
    ``turns.jsonl`` from each profile's home plus a live PID check.
    Lets the operator distinguish "agent thinking" from "agent stuck"
    without ssh-ing into log files."""
    import datetime as _dt

    # 1) Live PIDs of any in-flight `chat --once` per profile.
    res = run(["sh", "-c", "ps -eo pid,command | grep 'alpi.*chat --once' | grep -v grep || true"])
    live_pids: dict[str, tuple[int, float]] = {}
    now = time.time()
    for line in res.stdout.splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) != 2:
            continue
        try:
            pid = int(parts[0])
        except ValueError:
            continue
        cmd = parts[1]
        for p in PROFILES:
            if f"-p {p} " in cmd or f"-p {p}\n" in cmd:
                # PID start time via ps -o lstart= would be nicer but
                # parsing varies by OS. Use elapsed seconds instead.
                ts = run(["ps", "-p", str(pid), "-o", "etimes="])
                try:
                    elapsed = float(ts.stdout.strip())
                except ValueError:
                    elapsed = 0.0
                live_pids[p] = (pid, now - elapsed)
                break

    # 2) Last turn event per profile (from turns.jsonl).
    last_event: dict[str, dict] = {}
    for p in PROFILES:
        log_path = HOMES[p] / "alp" / "turns.jsonl"
        if not log_path.exists():
            continue
        last_line = ""
        for line in log_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                last_line = line
        if last_line:
            try:
                last_event[p] = json.loads(last_line)
            except json.JSONDecodeError:
                pass

    # 3) Render compact panel.
    print(f"{GREY}    turns:{RESET}")
    for p in PROFILES:
        col = PEER_COLOR.get(p, GREY)
        if p in live_pids:
            pid, started_at = live_pids[p]
            secs = int(now - started_at)
            print(
                f"{GREY}      · {col}{p}{RESET} "
                f"running {_fmt_dur(secs)} (pid {pid})"
            )
            continue
        if p not in last_event:
            print(f"{GREY}      · {col}{p}{RESET} idle (no turns yet){RESET}")
            continue
        ev = last_event[p]
        kind = ev.get("event", "?")
        ts_iso = ev.get("ts", "")
        try:
            ts_dt = _dt.datetime.strptime(ts_iso, "%Y-%m-%dT%H:%M:%SZ")
            ts_dt = ts_dt.replace(tzinfo=_dt.timezone.utc)
            ago = int((_dt.datetime.now(tz=_dt.timezone.utc) - ts_dt).total_seconds())
        except Exception:
            ago = -1
        ago_s = _fmt_dur(ago) + " ago" if ago >= 0 else "?"
        if kind == "end":
            posts = ev.get("posts_added", 0)
            dur = ev.get("duration_s", 0)
            posted_s = f"+{posts} post" + ("s" if posts != 1 else "")
            print(
                f"{GREY}      · {col}{p}{RESET} idle, last turn "
                f"{ago_s} ({dur}s, {posted_s})"
            )
        elif kind == "timeout":
            print(
                f"{GREY}      · {col}{p}{RESET} {RED}TIMED OUT{RESET} "
                f"{ago_s} ({ev.get('duration_s')}s, killed)"
            )
        elif kind == "spawn-failed":
            print(
                f"{GREY}      · {col}{p}{RESET} {RED}spawn-failed{RESET} "
                f"{ago_s}: {ev.get('error', '')[:80]}"
            )
        else:
            print(f"{GREY}      · {col}{p}{RESET} {kind} {ago_s}")


def _fmt_dur(secs: int) -> str:
    if secs < 60:
        return f"{secs}s"
    return f"{secs // 60}m{secs % 60:02d}s"


def read_state(wg_id: str) -> tuple[list[dict], dict]:
    code = (
        "import json, sys\n"
        "from pathlib import Path\n"
        "from alpi import service as svc\n"
        "from alpi.alp import workgroup as wg_mod\n"
        f"home = Path.home() / '.alpi' / 'profiles' / '{HUB}'\n"
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


def _print_post(p: dict, pubkey_to_handle: dict[str, str]) -> None:
    pubkey = p.get("from", "")
    handle = pubkey_to_handle.get(pubkey)
    color = PEER_COLOR.get(handle, GREY) if handle else GREY
    who = handle if handle else pubkey[:10]
    cost = p.get("cost") or {}
    cost_str = (
        f"  {GREY}${cost.get('usd', 0):.4f} · "
        f"{cost.get('tokens', 0):,}tok{RESET}"
        if cost else ""
    )
    text = p.get("text", "").strip()
    if len(text) > 800:
        text = text[:797] + "…"
    bar = f"{color}┃{RESET}"
    print()
    print(f"{bar} {color}#{p['seq']:>2}  {who}{RESET}{cost_str}")
    print(bar)
    for line in text.splitlines():
        print(f"{bar} {line}")
    print()


def main() -> int:
    print(f"{BLUE}=== ALP.3 oneshot 3-peer Money workgroup test ==={RESET}")
    print(f"{GREY}wipes & rebuilds {', '.join(PROFILES)} from scratch{RESET}")
    print()
    api_key = read_openai_key()
    nuke_profiles()
    bootstrap_profiles(api_key)
    cross_pin()
    wg_id = create_workgroup()
    members_join(wg_id)
    reset_poller_state()
    restart_services()
    post_kickoff(wg_id)
    watch(wg_id)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
