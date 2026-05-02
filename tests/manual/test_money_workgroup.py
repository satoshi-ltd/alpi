"""Oneshot end-to-end test of TWO concurrent ALP.3 workgroups.

Run::

    uv run python tests/manual/test_money_workgroup.py

This script owns the three profiles (alice, bob, carol) end-to-end:
nukes them, recreates them, copies only OPENAI_API_KEY from
~/.alpi/.env, pins openai/gpt-5.4-nano as the model, writes role bios,
installs the launchd services, cross-pins all three pairs, then runs
TWO workgroups in parallel:

  ▸ money-2026 (hub=alice, members=[alice, bob, carol])
    Pick PATH A vs B for the Money app's 2026 strategy.

  ▸ alpi-v05-roadmap (hub=carol, members=[carol, alice])
    Read https://alpi-agent.com/docs/ROADMAP and decide whether the
    proposed v0.5 scope is the right next step. Bob is intentionally
    excluded — this is a focused PM + researcher pairing.

Roles (per profile, both workgroups):

  carol — user researcher: web_fetches & extracts facts.
  alice — product manager: synthesises into options + roadmap fit.
  bob   — marketer: GTM lens (only money-2026).

Running both in parallel exercises the per-profile poller's ability
to dispatch into multiple wgs without bleeding state, and the
cross-machine transport (alice + carol intra unix socket; bob over
TCP/Noise_XK on a Tailscale hostname).

Transport topology (mirrors a real cross-machine setup as much as a
single laptop allows):

  alice — unix socket (intra-machine).
  carol — unix socket (intra-machine).
  bob   — TCP (Noise_XK) on a Tailscale hostname. Alice and carol pin
          bob with the explicit host:port so their dispatcher uses
          ``call_tcp`` instead of unix-socket dial. Bob's listener
          binds the same hostname so the path matches what an actual
          remote peer would observe.

Conversation language is forced to English in every briefing — gpt-5.4
otherwise drifts to the user's locale and tanks downstream parsing.

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
HOMES = {p: ROOT / "profiles" / p for p in PROFILES}
MODEL = "openai/gpt-5.4-nano"
WORKSPACE = str(Path.home())

# Per-profile transport. Anyone with TCP info gets the listener bound
# to that host:port and is pinned by peers with the same address —
# exercising the Noise_XK path. Profiles without TCP entry stay on
# unix sockets (intra-machine only).
TCP = {
    "bob": {"host": "macbook-pro-m4.tail3442b7.ts.net", "port": 9101},
}

BIOS = {
    "alice": (
        "Product manager - turns research into 2-3 feature candidates "
        "scored on user value, build cost, and roadmap fit."
    ),
    "bob": (
        "Marketer - pushes positioning and GTM; picks the candidate "
        "with the strongest audience narrative and 2024-2026 signals."
    ),
    "carol": (
        "User researcher - extracts pain points, audience signals, "
        "and feature gaps from product pages and case studies."
    ),
}
ACCENTS = {
    "alice": "#c8a24e",
    "bob":   "#5fafd7",
    "carol": "#d75f87",
}

URL_MONEY = "https://satoshi-ltd.com/case-studies/money"
URL_ROADMAP = "https://alpi-agent.com/docs/ROADMAP"

# Briefings are TOPIC + ROLE only. Meta-rules about transcript
# language and #done timing live in WORKGROUP_GUARDRAILS (the agent's
# system prompt).

MONEY_BRIEFING = (
    "Money is a privacy-first personal-finance app by Satoshi Ltd. "
    f"Public case study: {URL_MONEY}. The decision: pick the 2026 "
    "strategic path. PATH A is privacy-purist niche - stay 100% "
    "on-device, iOS-only, deepen the experience with on-device LLM "
    "categorization plus insights, launch a paid premium tier "
    "($3/mo); trade-off: TAM stays small but defensibility and "
    "narrative stay sharp. PATH B is mainstream broadening with "
    "E2E-encrypted sync - add multi-device sync (CloudKit or "
    "self-hosted) with end-to-end encryption, ship Android, run "
    "paid acquisition; trade-off: TAM grows ~5x but narrative "
    "softens and dev complexity grows. Pick ONE path in one line. "
    "Defend with a PM lens (feasibility, cost, retention) and a "
    "GTM lens (narrative, positioning, audience). Cite the case "
    "study at most once if useful, then commit."
)
MONEY_KICKOFF = (
    "#task Money 2026 strategy: pick PATH A (privacy-purist "
    "iOS-only paid premium) vs PATH B (mainstream broadening with "
    "E2E sync + Android). Defend the choice with PM + GTM lenses."
)

ROADMAP_BRIEFING = (
    "alpi (open, local-first agent runtime - github.com/soyjavi/alpi) "
    "is approaching v0.5. The maintainer wants a focused review: is "
    "the proposed v0.5 scope right, or are we missing something? "
    f"Source of truth: {URL_ROADMAP} — sections to ground the "
    "discussion are \"Open release gates\", \"ALP launch work\", "
    "\"Long-term bets\", and \"Discarded decisions\". Converge on "
    "one explicit recommendation by name: \"ship as planned\", "
    "\"ship subset X / defer Y\", or \"add Z first\"."
)
ROADMAP_KICKOFF = (
    f"#task Read {URL_ROADMAP} and decide together: is the "
    "proposed v0.5 scope the right next step? Converge on one "
    "explicit recommendation."
)

WORKGROUPS = [
    {
        "name": "money-2026",
        "hub": "alice",
        "members": ("alice", "bob", "carol"),
        "briefing": MONEY_BRIEFING,
        "kickoff": MONEY_KICKOFF,
        "budget": 5.0,
    },
    {
        "name": "alpi-v05-roadmap",
        "hub": "carol",
        "members": ("carol", "alice"),
        "briefing": ROADMAP_BRIEFING,
        "kickoff": ROADMAP_KICKOFF,
        "budget": 3.0,
    },
]

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


def _hard_remove(p: str) -> None:
    """Best-effort uninstall + rmtree. Does NOT fail — anything
    persistent is handled by the bootstrap retry loop, which is the
    only place that has the full create-after-remove atomicity needed
    to win against a desktop watcher that may re-shell `alpi -p p`
    (which itself re-bootstraps the dir) at any moment."""
    if HOMES[p].exists():
        run(["alpi", "profile", "remove", p, "--yes", "--force"])
    if HOMES[p].exists():
        shutil.rmtree(HOMES[p], ignore_errors=True)


def nuke_profiles() -> None:
    step("nuking profiles (uninstall launchd + remove dir)")
    for p in PROFILES:
        if HOMES[p].exists():
            _hard_remove(p)
            ok(f"removed {HOMES[p]}")
    time.sleep(0.5)


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


def _force_create(p: str, max_attempts: int = 6) -> None:
    """Create the profile, retrying through the race where another
    alpi invocation (e.g. a desktop poll) re-creates the home dir
    between our rmtree and ``profile create``. Each attempt does:
    rmtree (idempotent), then create. If create still says "already
    exists", we lost the race — sleep a moment and retry."""
    for attempt in range(1, max_attempts + 1):
        _hard_remove(p)
        res = run(["alpi", "profile", "create", p])
        if res.returncode == 0:
            return
        # Ignore other shell side-effects; re-arm and retry.
        msg = (res.stderr or res.stdout or "").strip()
        if "already exists" not in msg.lower():
            fail(f"profile create {p} failed: {msg}")
        warn(f"{p}: race lost on attempt {attempt}/{max_attempts} ({msg}); retrying")
        time.sleep(0.5 * attempt)
    fail(
        f"profile create {p} could not win the race after {max_attempts} "
        "attempts — close the desktop app (or pause its workgroup polling) "
        "and rerun the script"
    )


def bootstrap_profiles(api_key: str) -> None:
    step("creating fresh profiles + writing config")
    import yaml

    for p in PROFILES:
        _force_create(p)

        (HOMES[p] / ".env").write_text(f"OPENAI_API_KEY={api_key}\n")

        cfg_path = HOMES[p] / "config.yaml"
        cfg = yaml.safe_load(cfg_path.read_text()) or {}
        cfg["model"] = MODEL
        cfg["workspace"] = WORKSPACE
        cfg["public_bio"] = BIOS[p]
        cfg.setdefault("tui", {})["accent"] = ACCENTS[p]
        if p in TCP:
            tcp = TCP[p]
            alp = cfg.setdefault("alp", {})
            alp["tcp_host"] = tcp["host"]
            alp["tcp_port"] = int(tcp["port"])
        cfg_path.write_text(
            yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True),
        )
        ok(f"{p}: profile + config + .env")

    # Single daemon for the machine; idempotent. Restart picks up the
    # newly-created profile homes that were just bootstrapped above.
    install_code = (
        "from alpi import service as svc\n"
        "from alpi import home as home_mod\n"
        "svc.install_daemon(home_mod._ROOT)\n"
        "print('installed')\n"
    )
    res = run(["uv", "run", "python", "-c", install_code],
              cwd=str(Path(__file__).parent.parent))
    if res.returncode != 0:
        fail(f"daemon install failed: {res.stderr}")
    ok("daemon installed (one launchd plist / systemd unit, all profiles)")

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
            cmd = ["alpi", "-p", hub, "peers", "add", peer, pubkeys[peer]]
            # If the peer is reachable over TCP, pin its host:port so
            # the dispatcher uses ``call_tcp`` instead of unix.
            if peer in TCP:
                tcp = TCP[peer]
                cmd += ["--address", f"{tcp['host']}:{tcp['port']}"]
            res = run(cmd)
            if res.returncode != 0:
                fail(f"{hub} peers add {peer} failed: {res.stderr}")
    ok(f"6 directional pins written ({len(TCP)} via TCP)")


# Step 5 — create workgroup


def create_workgroup(spec: dict) -> str:
    name = spec["name"]
    hub = spec["hub"]
    members = spec["members"]
    step(f"creating workgroup '{name}' as {hub}")
    members_args: list[str] = []
    for m in members:
        if m == hub:
            continue
        members_args += ["--member", m]
    res = run([
        "alpi", "-p", hub, "workgroup", "create", name,
        *members_args, "--budget-usd", str(spec["budget"]),
    ])
    if res.returncode != 0:
        fail(f"workgroup create '{name}' failed: {res.stderr}")
    # New workgroup is the youngest dir under hub's workgroups/.
    wg_dirs = sorted(
        (
            d
            for d in (HOMES[hub] / "alp" / "workgroups").iterdir()
            if d.is_dir() and not d.name.startswith(".")
        ),
        key=lambda d: d.stat().st_mtime,
        reverse=True,
    )
    if not wg_dirs:
        fail(f"workgroup '{name}' directory not created")
    wg_dir = wg_dirs[0]
    wg_id = wg_dir.name

    import yaml
    meta_path = wg_dir / "meta.yaml"
    meta = yaml.safe_load(meta_path.read_text())
    meta["briefing"] = spec["briefing"]
    meta_path.write_text(yaml.safe_dump(meta, sort_keys=False, allow_unicode=True))
    ok(f"created {wg_id} ({name}) with briefing + ${spec['budget']} budget")
    return wg_id


# Step 6 — members join


def members_join(spec: dict, wg_id: str) -> None:
    hub = spec["hub"]
    for member in spec["members"]:
        if member == hub:
            continue
        step(f"{member} joining '{spec['name']}' as remote member")
        res = run(["alpi", "-p", member, "workgroup", "join", hub, wg_id])
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


# Step 8 — restart the daemon so it reloads peers + subscriptions


def restart_services() -> None:
    step("restarting daemon to load fresh peers + subscriptions")
    res = run(["alpi", "daemon", "restart"])
    if res.returncode != 0:
        fail(f"daemon restart failed: {res.stderr}")

    # Wait until every hub responds to a ping from each of its
    # non-hub members. That covers all transports we exercise (unix
    # + TCP) and all hubs across both workgroups.
    pending: set[tuple[str, str]] = set()
    for spec in WORKGROUPS:
        for m in spec["members"]:
            if m != spec["hub"]:
                pending.add((m, spec["hub"]))
    deadline = time.time() + 45
    started = time.time()
    while time.time() < deadline and pending:
        for (caller, target) in list(pending):
            probe = run(["alpi", "-p", caller, "peers", "ping", target])
            if probe.returncode == 0:
                pending.discard((caller, target))
        if pending:
            time.sleep(1)
    if pending:
        details = ", ".join(f"{a}→{b}" for (a, b) in sorted(pending))
        fail(f"ALP listeners didn't answer pings within 45s: {details}")
    ok(f"daemon up — every hub answered pings in {int(time.time() - started)}s")


# Step 9 — kickoff


def post_kickoff(spec: dict, wg_id: str) -> None:
    hub = spec["hub"]
    step(f"posting kickoff for '{spec['name']}' via {hub}")
    res = run(["alpi", "-p", hub, "workgroup", "post", wg_id, spec["kickoff"]])
    if res.returncode != 0:
        fail(f"kickoff post '{spec['name']}' failed: {res.stderr}")
    ok(f"kickoff posted to {spec['name']}: {spec['kickoff'][:100]}…")


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


def watch(specs: list[dict], wg_ids: dict[str, str]) -> None:
    """Poll all workgroups in parallel until every one closes with
    ``#done``, any workgroup hits 95% of its budget, or we time out."""
    print()
    print(
        f"{BLUE}=== watching {len(specs)} workgroup(s) (poll every "
        f"{POLL_SECONDS}s, timeout {TIMEOUT_SECONDS // 60} min) ==={RESET}"
    )
    for spec in specs:
        print(
            f"{GREY}  · {spec['name']} · hub={spec['hub']} · "
            f"members={list(spec['members'])} · ${spec['budget']:.2f} cap{RESET}"
        )
    print()

    pubkey_to_handle = _load_pubkeys()
    seen_seq: dict[str, int] = {spec["name"]: 0 for spec in specs}
    closed: dict[str, bool] = {spec["name"]: False for spec in specs}
    deadline = time.time() + TIMEOUT_SECONDS
    last_status_at = 0.0
    started = time.time()

    while time.time() < deadline:
        all_done = True
        for spec in specs:
            name = spec["name"]
            if closed[name]:
                continue
            all_done = False
            posts, ledger = read_state(spec["hub"], wg_ids[name])
            for p in posts:
                if int(p["seq"]) <= seen_seq[name]:
                    continue
                seen_seq[name] = int(p["seq"])
                _print_post(p, pubkey_to_handle, wg_label=name)
                if any(
                    _DONE_MARKER.match(line)
                    for line in p.get("text", "").splitlines()
                ):
                    closed[name] = True
                    print()
                    ok(
                        f"[{name}] CLOSED with #done — "
                        f"${ledger.get('usd', 0):.4f} / "
                        f"{ledger.get('tokens', 0):,} tokens / "
                        f"{ledger.get('posts', 0)} posts"
                    )

            if ledger.get("usd", 0) >= spec["budget"] * 0.95 and not closed[name]:
                warn(
                    f"[{name}] budget at 95%+ "
                    f"(${ledger['usd']:.2f}/${spec['budget']}) — "
                    f"hub will start refusing posts"
                )

        if all_done:
            print()
            ok("all workgroups closed.")
            return

        if time.time() - last_status_at > 60:
            last_status_at = time.time()
            elapsed = int(time.time() - started)
            running = [s["name"] for s in specs if not closed[s["name"]]]
            print(
                f"{GREY}  · {elapsed}s elapsed · still running: "
                f"{', '.join(running)}{RESET}"
            )
            _print_turn_panel()

        time.sleep(POLL_SECONDS)

    pending = [s["name"] for s in specs if not closed[s["name"]]]
    warn(
        f"timed out after {TIMEOUT_SECONDS}s — still open: {pending}. "
        f"investigate prompt or guardrails."
    )


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


def read_state(hub: str, wg_id: str) -> tuple[list[dict], dict]:
    code = (
        "import json, sys\n"
        "from pathlib import Path\n"
        "from alpi import service as svc\n"
        "from alpi.alp import workgroup as wg_mod\n"
        f"home = Path.home() / '.alpi' / 'profiles' / '{hub}'\n"
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


def _print_post(p: dict, pubkey_to_handle: dict[str, str], wg_label: str = "") -> None:
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
    label = f"  {GREY}[{wg_label}]{RESET}" if wg_label else ""
    text = p.get("text", "").strip()
    if len(text) > 800:
        text = text[:797] + "…"
    bar = f"{color}┃{RESET}"
    print()
    print(f"{bar} {color}#{p['seq']:>2}  {who}{RESET}{cost_str}{label}")
    print(bar)
    for line in text.splitlines():
        print(f"{bar} {line}")
    print()


def main() -> int:
    print(f"{BLUE}=== ALP.3 oneshot multi-workgroup test ==={RESET}")
    print(f"{GREY}wipes & rebuilds {', '.join(PROFILES)} from scratch · "
          f"runs {len(WORKGROUPS)} workgroup(s) in parallel{RESET}")
    print()
    api_key = read_openai_key()
    nuke_profiles()
    bootstrap_profiles(api_key)
    cross_pin()

    wg_ids: dict[str, str] = {}
    for spec in WORKGROUPS:
        wg_id = create_workgroup(spec)
        members_join(spec, wg_id)
        wg_ids[spec["name"]] = wg_id

    reset_poller_state()
    restart_services()

    for spec in WORKGROUPS:
        post_kickoff(spec, wg_ids[spec["name"]])

    watch(WORKGROUPS, wg_ids)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
