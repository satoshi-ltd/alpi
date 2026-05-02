"""Oneshot end-to-end test of an ALP.3 workgroup with 4 complementary
peers — designed to stress turn-rotation under genuinely distinct
roles that do NOT paraphrase each other.

Run::

    uv run python tests/manual/test_tasting_menu_workgroup.py

Owns four profiles end-to-end (dana, emil, freya, gus): nukes them,
recreates them, copies only OPENAI_API_KEY from ~/.alpi/.env, pins
openai/gpt-5.4-nano as the model, writes role bios, installs the
launchd services, cross-pins all six pairs, then runs ONE
workgroup:

  ▸ autumn-tasting-menu (hub=dana, members=[dana, emil, freya, gus])
    Pick the opening + signature courses for Foundry & Field's
    autumn 2026 tasting menu under hard constraints (hyper-local
    sourcing, fermentation thread, 130€ price, 90 min service).

Why this complements `test_money_workgroup.py`: money is a
business-strategy decision (PM + GTM + research) that converges on
PATH A vs PATH B. This one is a creative/operational decision in a
totally different vocabulary (chef + sommelier + pastry + service)
where each role brings non-overlapping concerns. A sommelier can't
paraphrase a service captain — the language is different — so the
SDK's "one post per round" rule has more concrete signal to lean
on.

Topology (one peer over TCP, three intra-machine, mirrors a real
home-server + remote member setup):

  dana  — unix socket (intra-machine, hub).
  emil  — unix socket.
  freya — unix socket.
  gus   — TCP (Noise_XK) on a Tailscale hostname; the other three
          pin gus with that host:port so the dispatcher uses
          ``call_tcp`` instead of unix-socket dial.

Conversation language is forced to English in every briefing — the
WORKGROUP_GUARDRAILS contract already requires English by default.

WARNING: this WIPES ~/.alpi/profiles/{dana,emil,freya,gus} every
run. Do not point this at profiles you actually use day-to-day.
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
PROFILES = ("dana", "emil", "freya", "gus")
HOMES = {p: ROOT / "profiles" / p for p in PROFILES}
MODEL = "openai/gpt-5.4-mini"
WORKSPACE = str(Path.home())

# Per-profile transport. Anyone with TCP info gets the listener bound
# to that host:port and is pinned by peers with the same address —
# exercising the Noise_XK path. Profiles without TCP entry stay on
# unix sockets (intra-machine only). Port 9102 to avoid colliding
# with the money test's bob (9101) when both run back-to-back.
TCP = {
    "gus": {"host": "macbook-pro-m4.tail3442b7.ts.net", "port": 9102},
}

BIOS = {
    "dana": (
        "Head chef - turns a seasonal larder into a coherent tasting "
        "menu; trades novelty for craft and dish-to-dish narrative."
    ),
    "emil": (
        "Sommelier - maps acidity, tannin, and sweetness through a "
        "menu; sources beverages within 80km of the kitchen."
    ),
    "freya": (
        "Pastry chef - bread, transitions, dessert, petit fours; "
        "guards plating feasibility at fixed menu price points."
    ),
    "gus": (
        "Service captain - 90 minute pacing, dietary substitutions, "
        "course-to-course service choreography front of house."
    ),
}
ACCENTS = {
    "dana":  "#d4a017",  # saffron
    "emil":  "#7d3cfc",  # wine purple
    "freya": "#ff6b9d",  # rose
    "gus":   "#3aae5e",  # service green
}

# Briefing is TOPIC + ROLES only. Meta-rules about transcript
# language, hub-only #task/#done, and one-post-per-round live in
# WORKGROUP_GUARDRAILS (the agent's system prompt) and are enforced
# by the SDK on top.

MENU_BRIEFING = (
    "Foundry & Field is a 28-seat farm-to-table restaurant launching "
    "its autumn 2026 tasting menu. The decision: pick the OPENING "
    "course (course 1, sets palate and tone) and the SIGNATURE course "
    "(course 4, the mid-menu table moment). These two anchor the "
    "narrative of the other five courses. "
    "Hard constraints: every ingredient sourced within 80km of the "
    "kitchen; fermentation must touch BOTH anchor dishes (kraut, "
    "miso, koji, vinegar, lacto, kefir, kombucha — chef's call); "
    "menu price point 130 euros; beverage program is 4 wine pairings "
    "plus 1 non-alcoholic alternative across the full menu, with an "
    "explicit non-alcoholic option named for the signature course; "
    "90 minute average service window across the 7 courses; 1 vegan "
    "substitution path and 1 gluten-free substitution path must be "
    "plate-feasible for both anchors. "
    "Deliverable: 2 named dishes (one line each), 1 wine pairing "
    "for each anchor, 1 non-alcoholic alternative named for the "
    "signature, plus the vegan and gluten-free substitution paths "
    "for both anchors."
)

MENU_KICKOFF = (
    "#task Pick the opening course (course 1) and the signature "
    "course (course 4) for Foundry & Field's autumn 2026 tasting "
    "menu under the briefing's constraints. Converge on 2 named "
    "dishes plus pairings."
)

WORKGROUPS = [
    {
        "name": "autumn-tasting-menu",
        "hub": "dana",
        "members": ("dana", "emil", "freya", "gus"),
        "briefing": MENU_BRIEFING,
        "kickoff": MENU_KICKOFF,
        "budget": 4.0,
    },
]

TIMEOUT_SECONDS = 30 * 60
POLL_SECONDS = 20

GREY, BLUE, GREEN, YELLOW, RED, MAGENTA, CYAN, RESET = (
    "\033[2m", "\033[36m", "\033[32m", "\033[33m",
    "\033[31m", "\033[35m", "\033[96m", "\033[0m",
)
PEER_COLOR = {
    "dana":  YELLOW,
    "emil":  MAGENTA,
    "freya": RED,
    "gus":   GREEN,
}


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
    between our rmtree and ``profile create``."""
    for attempt in range(1, max_attempts + 1):
        _hard_remove(p)
        res = run(["alpi", "profile", "create", p])
        if res.returncode == 0:
            return
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
    ok(f"all {len(PROFILES)} ALP keypairs generated")


# Step 4 — cross-pin


def cross_pin() -> None:
    step(f"cross-pinning all {len(PROFILES) * (len(PROFILES) - 1) // 2} pairs")
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
            if peer in TCP:
                tcp = TCP[peer]
                cmd += ["--address", f"{tcp['host']}:{tcp['port']}"]
            res = run(cmd)
            if res.returncode != 0:
                fail(f"{hub} peers add {peer} failed: {res.stderr}")
    ok(f"{len(pairs) * 2} directional pins written ({len(TCP)} via TCP)")


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
        "    state.pop('hub_watchdog_fired_seq', None)\n"
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
                ts = run(["ps", "-p", str(pid), "-o", "etimes="])
                try:
                    elapsed = float(ts.stdout.strip())
                except ValueError:
                    elapsed = 0.0
                live_pids[p] = (pid, now - elapsed)
                break

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
    print(f"{BLUE}=== ALP.3 oneshot 4-peer tasting-menu test ==={RESET}")
    print(f"{GREY}wipes & rebuilds {', '.join(PROFILES)} from scratch · "
          f"runs {len(WORKGROUPS)} workgroup(s){RESET}")
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
