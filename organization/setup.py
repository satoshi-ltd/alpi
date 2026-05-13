"""Canonical org bootstrap for the 17-agent agentic company scaffold.

Agent identities live in organization/agents/<name>/agent.md:
  frontmatter  →  bio, accent, tier, daily_usd (optional model override)
  body         →  soul written to memories/AGENT.md

Skills live in organization/agents/<name>/skills/ and
organization/common/skills/ (shared across multiple agents).

MCP servers live in organization/agents/<name>/mcp.yaml (optional).
  Format: servers: {<name>: {command, args, env}} — merged into config.yaml.

Workgroup structure and peer graph are defined in this file.
Run any time to nuke and rebuild the full org from scratch.

Steps:
  1.  Nuke all 17 org profiles (hard remove).
  2.  Create each profile fresh (alpi profile create).
  3.  Copy all API keys from organization/.env (fallback: ~/.alpi/.env).
  4.  Write memories/AGENT.md (soul from organization/agents/<name>/agent.md).
  5.  Write memories/USER.md (org context for this agent's role and relationships).
  6.  Patch config.yaml — model + public_bio + accent + budget.daily_usd + MCP servers.
  7.  Install daemon (idempotent).
  8.  Wait for ALP Ed25519 keypairs to be generated.
  9.  Read pubkeys; cross-pin peer graph.
  10. Restart daemon; verify every edge responds to ping.
  11. Create 4 standing workgroups; members join each.
  12. Install skills into each profile's skills/ directory.

WARNING: wipes ~/.alpi/profiles/{vera,zeta,prism,echo,ledger,forge,sentinel,
         canvas,quill,rex,fern,hub,lumen,flux,lex,atlas,archive} every run.

Usage:
    uv run python organization/setup.py
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import yaml

ROOT = Path.home() / ".alpi"
PROFILES_DIR = ROOT / "profiles"
WORKSPACE = str(Path.home())
AGENTS_DIR = Path(__file__).parent / "agents"
WORKGROUPS_DIR = Path(__file__).parent / "workgroups"
COMMON_SKILLS_DIR = Path(__file__).parent / "common" / "skills"

# ---------------------------------------------------------------------------
# CONFIG — change these to retune the whole org without touching agent files
# ---------------------------------------------------------------------------

MODEL_DEFAULT = "openai/gpt-5.4-mini"           # execution agents (cheap service turns)
MODEL_STRONG  = "anthropic/claude-sonnet-4-6"   # council + on-demand specialists

BUDGET_DAILY_DEFAULT = 2.0    # USD/day  — default tier agents
BUDGET_DAILY_STRONG  = 5.0    # USD/day  — strong tier agents (overridden per-agent below)
BUDGET_WG            = 50.0   # USD lifetime fallback if workgroup.md omits budget_usd

# ---------------------------------------------------------------------------
# Common skills — shared across multiple agents
# ---------------------------------------------------------------------------
# Maps "category/skill-name" (relative to organization/common/skills/) to the
# list of agent names that should receive a copy of that skill.

COMMON_SKILLS: dict[str, list[str]] = {
    "finance/unit-economics": ["echo", "ledger"],
}

# ---------------------------------------------------------------------------
# Peer graph
# ---------------------------------------------------------------------------
# Peer graph — derived dynamically from agent.md + workgroup.md files
# ---------------------------------------------------------------------------
# Each agent declares its peers in agent.md frontmatter (peers: [...]).
# Workgroup hub↔member pairs are added automatically from workgroup.md.
# Edges are filtered to agents that actually exist — removing an agent
# folder silently drops its edges without breaking the bootstrap.


def derive_edges(
    agents: list[dict],
    workgroups: list[dict],
) -> list[tuple[str, str]]:
    existing = {a["name"] for a in agents}
    seen: set[frozenset[str]] = set()
    edges: list[tuple[str, str]] = []

    def _add(a: str, b: str) -> None:
        if a not in existing or b not in existing:
            return
        key = frozenset((a, b))
        if key not in seen:
            seen.add(key)
            edges.append((a, b))

    # declared peer edges from each agent.md
    for agent in agents:
        for peer in agent.get("peers", []):
            _add(agent["name"], peer)

    # workgroup hub↔member edges (required for workgroup.create/join)
    for wg in workgroups:
        hub = wg["hub"]
        for member in wg["members"]:
            _add(hub, member)

    return edges

# ---------------------------------------------------------------------------
# Workgroup loader — reads organization/workgroups/<name>/workgroup.md
# ---------------------------------------------------------------------------
# frontmatter: hub, members (list), budget_usd (optional, falls back to BUDGET_WG)
# body:        briefing text written to meta.yaml on the hub's profile


def load_workgroups() -> list[dict]:
    paths = sorted(WORKGROUPS_DIR.glob("*/workgroup.md"))
    if not paths:
        fail(f"no workgroup files found in {WORKGROUPS_DIR}/*/workgroup.md")
    wgs = []
    for p in paths:
        raw = p.read_text()
        m = _FRONT_RE.match(raw)
        if not m:
            fail(f"{p}: missing YAML frontmatter")
        front = yaml.safe_load(m.group(1)) or {}
        briefing = raw[m.end():].strip()
        # collapse the multi-line briefing to a single space-separated string
        briefing = " ".join(briefing.split())
        wgs.append({
            "name":       p.parent.name,
            "hub":        front["hub"],
            "members":    list(front.get("members", [])),
            "budget_usd": float(front.get("budget_usd", BUDGET_WG)),
            "briefing":   briefing,
        })
    return wgs

# ---------------------------------------------------------------------------
# Terminal colours
# ---------------------------------------------------------------------------

GREY, BLUE, GREEN, YELLOW, RED, RESET = (
    "\033[2m", "\033[36m", "\033[32m", "\033[33m", "\033[31m", "\033[0m",
)


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


# ---------------------------------------------------------------------------
# Agent loader — reads organization/agents/<name>.md
# ---------------------------------------------------------------------------

_FRONT_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _parse_agent_file(path: Path) -> dict:
    raw = path.read_text()
    m = _FRONT_RE.match(raw)
    if not m:
        fail(f"{path}: missing YAML frontmatter block (expected --- ... ---)")
    front = yaml.safe_load(m.group(1)) or {}
    soul = raw[m.end():].strip()

    tier = front.get("tier", "default")
    if "model" in front:
        model = front["model"]             # explicit override beats tier
    elif tier == "strong":
        model = MODEL_STRONG
    else:
        model = MODEL_DEFAULT

    daily_usd = float(front.get("daily_usd", BUDGET_DAILY_DEFAULT))

    return {
        "name":      path.parent.name,    # <name>/agent.md → name is parent dir
        "bio":       front.get("bio", ""),
        "accent":    front.get("accent", "#888888"),
        "tier":      tier,
        "model":     model,
        "daily_usd": daily_usd,
        "soul":      soul,
        "peers":     list(front.get("peers", [])),
    }


def load_agents() -> list[dict]:
    paths = sorted(AGENTS_DIR.glob("*/agent.md"))
    if not paths:
        fail(f"no agent files found in {AGENTS_DIR}/*/agent.md")
    return [_parse_agent_file(p) for p in paths]


def load_agent_mcps(agent_name: str, env: dict) -> dict:
    """Return MCP servers from agents/<name>/mcp.yaml, filtered to those whose
    required env vars are already present. Servers with no env requirements
    (e.g. fetch) are always included."""
    mcp_file = AGENTS_DIR / agent_name / "mcp.yaml"
    if not mcp_file.exists():
        return {}
    data = yaml.safe_load(mcp_file.read_text()) or {}
    servers = data.get("servers", {})
    active = {}
    for name, cfg in servers.items():
        required = [
            v.removeprefix("env:")
            for v in (cfg.get("env") or {}).values()
            if isinstance(v, str) and v.startswith("env:")
        ]
        if all(env.get(k) for k in required):
            active[name] = cfg
        else:
            missing = [k for k in required if not env.get(k)]
            warn(f"{agent_name}: MCP '{name}' skipped — missing env vars: {missing}")
    return active


def _make_user_md(agent: dict, workgroups: list[dict]) -> str:
    """Generate memories/USER.md — org context visible to the agent each session."""
    name = agent["name"].capitalize()

    wg_lines = []
    for wg in workgroups:
        if agent["name"] == wg["hub"]:
            wg_lines.append(f"- **{wg['name'].capitalize()}** (you are the hub — you open tasks and decide #done)")
        elif agent["name"] in wg["members"]:
            wg_lines.append(f"- **{wg['name'].capitalize()}** (fixed peer — hub is {wg['hub'].capitalize()})")
    wg_section = "\n".join(wg_lines) if wg_lines else "- None (invited on demand)"

    peers = ", ".join(p.capitalize() for p in agent.get("peers", []))

    return f"""# Organization context

You are **{name}**, operating within a 17-agent agentic company scaffold built on the ALP protocol.
The org has four persistent workgroups (Roadmap, Architecture, Growth, Customers) where decisions are made.
Tasks open with `#task`, dialogue happens among peers, and the hub decides `#done`.

## Your workgroups
{wg_section}

## Your peers
{peers if peers else "None declared — you are invited on demand"}

## Operating norms
- Decisions happen in workgroups, not in bilateral pings
- Every significant decision produces a written artifact (ADR, decision record, PRD, etc.)
- Vera is the strategic top — escalate cross-domain tradeoffs there
- Archive captures decisions at `#done` time so rationale is never lost
- Public bios are how agents introduce themselves when joining a workgroup — yours is already set
"""


# ---------------------------------------------------------------------------
# Step 1 — read .env from default profile
# ---------------------------------------------------------------------------


def read_env_lines() -> str:
    # organization/.env takes precedence; fall back to ~/.alpi/.env
    org_env = Path(__file__).parent / ".env"
    if org_env.exists():
        return org_env.read_text()
    default_env = ROOT / ".env"
    if default_env.exists():
        return default_env.read_text()
    fail(f"no .env found — add API keys to organization/.env or {default_env}")


# ---------------------------------------------------------------------------
# Step 2 — nuke
# ---------------------------------------------------------------------------


def _hard_remove(home: Path, name: str) -> None:
    if home.exists():
        run(["alpi", "profile", "remove", name, "--yes", "--force"])
    if home.exists():
        shutil.rmtree(home, ignore_errors=True)


def nuke_profiles(agents: list[dict]) -> None:
    step("nuking org profiles")
    for agent in agents:
        home = PROFILES_DIR / agent["name"]
        if home.exists():
            _hard_remove(home, agent["name"])
            ok(f"removed {agent['name']}")
    time.sleep(0.5)


# ---------------------------------------------------------------------------
# Step 3 — create + configure profiles
# ---------------------------------------------------------------------------


ALP_BIO_LIMIT = 200  # ALP wire cap for public_bio in bytes


def _truncate_bio(bio: str, limit: int = ALP_BIO_LIMIT) -> str:
    encoded = bio.encode("utf-8")
    if len(encoded) <= limit:
        return bio
    # cut at last space before the byte limit so we don't break mid-word
    truncated = encoded[: limit - 1].decode("utf-8", errors="ignore")
    last_space = truncated.rfind(" ")
    if last_space > 0:
        truncated = truncated[:last_space]
    return truncated + "…"


def _force_create(home: Path, name: str, max_attempts: int = 6) -> None:
    for attempt in range(1, max_attempts + 1):
        _hard_remove(home, name)
        res = run(["alpi", "profile", "create", name])
        if res.returncode == 0:
            return
        msg = (res.stderr or res.stdout or "").strip()
        if "already exists" not in msg.lower():
            fail(f"profile create {name} failed: {msg}")
        warn(f"{name}: race on attempt {attempt}/{max_attempts}; retrying")
        time.sleep(0.5 * attempt)
    fail(f"profile create {name} failed after {max_attempts} attempts")


def bootstrap_profiles(agents: list[dict], workgroups: list[dict], env_lines: str) -> None:
    step(f"creating {len(agents)} profiles")
    for agent in agents:
        _force_create(PROFILES_DIR / agent["name"], agent["name"])

    env_dict = {
        k: v
        for line in env_lines.splitlines()
        if "=" in line and not line.startswith("#")
        for k, v in [line.split("=", 1)]
    }

    step("writing .env + config.yaml + memories")
    for agent in agents:
        h = PROFILES_DIR / agent["name"]

        (h / ".env").write_text(env_lines)

        cfg_path = h / "config.yaml"
        cfg = yaml.safe_load(cfg_path.read_text()) if cfg_path.exists() else {}
        cfg = cfg or {}
        cfg["model"] = agent["model"]
        cfg["workspace"] = WORKSPACE
        cfg["public_bio"] = _truncate_bio(agent["bio"])
        cfg.setdefault("tui", {})["accent"] = agent["accent"]
        cfg.setdefault("budget", {})["daily_usd"] = agent["daily_usd"]

        mcps = load_agent_mcps(agent["name"], env_dict)
        if mcps:
            cfg.setdefault("mcp", {})["servers"] = mcps

        cfg_path.write_text(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True))

        mem_dir = h / "memories"
        (mem_dir / "AGENT.md").write_text(agent["soul"])
        (mem_dir / "USER.md").write_text(_make_user_md(agent, workgroups))

        mcp_note = f"  mcps={','.join(mcps)}" if mcps else ""
        ok(f"{agent['name']:<10}  model={agent['model']}  daily=${agent['daily_usd']:.1f}{mcp_note}")

    install_code = (
        "from alpi import service as svc\n"
        "from alpi import home as home_mod\n"
        "svc.install_daemon(home_mod._ROOT)\n"
        "print('ok')\n"
    )
    res = run(
        ["uv", "run", "python", "-c", install_code],
        cwd=str(Path(__file__).parent.parent),
    )
    if res.returncode != 0:
        fail(f"daemon install failed: {res.stderr}")
    ok("daemon installed")


# ---------------------------------------------------------------------------
# Step 4 — wait for ALP keypairs
# ---------------------------------------------------------------------------


def wait_for_keypairs(agents: list[dict]) -> None:
    step("waiting for ALP keypairs to be generated")
    names = [a["name"] for a in agents]
    deadline = time.time() + 60
    pending = set(names)
    while time.time() < deadline and pending:
        for name in list(pending):
            if (PROFILES_DIR / name / "alp" / "secrets" / "alp_key.pub").exists():
                pending.discard(name)
        if pending:
            time.sleep(1)
    if pending:
        fail(f"ALP keys not generated for {sorted(pending)} — is the daemon running?")
    ok(f"all {len(names)} ALP keypairs present")


# ---------------------------------------------------------------------------
# Step 5 — cross-pin peers
# ---------------------------------------------------------------------------


def cross_pin(agents: list[dict], edges: list[tuple[str, str]]) -> None:
    step("reading pubkeys")
    pubkeys: dict[str, str] = {}
    for agent in agents:
        name = agent["name"]
        res = run(["alpi", "-p", name, "peers", "key"])
        if res.returncode != 0 or not res.stdout.strip():
            fail(f"couldn't read {name}'s pubkey: {res.stderr.strip()}")
        pubkeys[name] = res.stdout.strip()

    step(f"pinning {len(edges)} edges ({len(edges) * 2} directional pins)")
    for a, b in edges:
        for caller, target in ((a, b), (b, a)):
            res = run(["alpi", "-p", caller, "peers", "add", target, pubkeys[target]])
            if res.returncode != 0:
                fail(f"{caller} peers add {target} failed: {res.stderr.strip()}")
    ok(f"{len(edges) * 2} pins written")


# ---------------------------------------------------------------------------
# Step 6 — restart daemon + verify connectivity
# ---------------------------------------------------------------------------


def restart_and_verify(edges: list[tuple[str, str]]) -> None:
    step("restarting daemon")
    res = run(["alpi", "daemon", "restart"])
    if res.returncode != 0:
        fail(f"daemon restart failed: {res.stderr.strip()}")

    pending: set[tuple[str, str]] = set()
    for a, b in edges:
        pending.add((a, b))
        pending.add((b, a))

    step(f"verifying {len(pending)} peer connections (ping)")
    deadline = time.time() + 60
    while time.time() < deadline and pending:
        for pair in list(pending):
            caller, target = pair
            probe = run(["alpi", "-p", caller, "peers", "ping", target])
            if probe.returncode == 0:
                pending.discard(pair)
        if pending:
            time.sleep(2)

    if pending:
        details = ", ".join(f"{a}→{b}" for a, b in sorted(pending))
        fail(f"peers unreachable after 60s: {details}")
    ok(f"all pings answered")


# ---------------------------------------------------------------------------
# Step 7 — create workgroups + members join
# ---------------------------------------------------------------------------


def _latest_wg_dir(hub_name: str) -> Path | None:
    wg_root = PROFILES_DIR / hub_name / "alp" / "workgroups"
    if not wg_root.exists():
        return None
    dirs = sorted(
        (d for d in wg_root.iterdir() if d.is_dir() and not d.name.startswith(".")),
        key=lambda d: d.stat().st_mtime,
        reverse=True,
    )
    return dirs[0] if dirs else None


def setup_workgroups(workgroups: list[dict]) -> None:
    step(f"creating {len(workgroups)} workgroups")
    for spec in workgroups:
        hub = spec["hub"]
        name = spec["name"]
        members = spec["members"]
        budget = spec["budget_usd"]

        cmd = ["alpi", "-p", hub, "workgroup", "create", name]
        for m in members:
            cmd += ["--member", m]
        cmd += ["--budget-usd", str(budget)]
        res = run(cmd)
        if res.returncode != 0:
            fail(f"workgroup create '{name}' failed: {res.stderr.strip()}")

        wg_dir = _latest_wg_dir(hub)
        if not wg_dir:
            fail(f"workgroup '{name}' dir not found after create")
        wg_id = wg_dir.name

        meta_path = wg_dir / "meta.yaml"
        meta = yaml.safe_load(meta_path.read_text()) or {}
        meta["briefing"] = spec["briefing"]
        meta_path.write_text(yaml.safe_dump(meta, sort_keys=False, allow_unicode=True))

        ok(f"created '{name}' ({wg_id[:12]}…)  hub={hub}")

        for member in members:
            res = run(["alpi", "-p", member, "workgroup", "join", hub, wg_id])
            if res.returncode != 0:
                fail(f"{member} join '{name}' failed: {res.stderr.strip()}")
            ok(f"  {member} joined")

        time.sleep(0.2)


# ---------------------------------------------------------------------------
# Step 8 — install skills into profiles
# ---------------------------------------------------------------------------


def install_skills(agents: list[dict]) -> None:
    step("installing skills into profiles")
    agent_names = {a["name"] for a in agents}

    for agent in agents:
        name = agent["name"]
        src_skills = AGENTS_DIR / name / "skills"
        dst_skills = PROFILES_DIR / name / "skills"
        if src_skills.exists():
            if dst_skills.exists():
                shutil.rmtree(dst_skills)
            shutil.copytree(src_skills, dst_skills)

    # common skills — copy to each listed agent
    for skill_path, targets in COMMON_SKILLS.items():
        src = COMMON_SKILLS_DIR / skill_path
        if not src.exists():
            warn(f"common skill not found: {src}")
            continue
        for target in targets:
            if target not in agent_names:
                warn(f"common skill target '{target}' not in agents; skipping")
                continue
            # preserve category/skill-name structure inside profile's skills/
            dst = PROFILES_DIR / target / "skills" / skill_path
            dst.parent.mkdir(parents=True, exist_ok=True)
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst)

    for agent in agents:
        name = agent["name"]
        dst_skills = PROFILES_DIR / name / "skills"
        if dst_skills.exists():
            skill_count = sum(1 for _ in dst_skills.rglob("SKILL.md"))
            ok(f"{name:<10}  {skill_count} skill(s) installed")


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------


def print_summary(
    agents: list[dict],
    workgroups: list[dict],
    edges: list[tuple[str, str]],
) -> None:
    names = [a["name"] for a in agents]
    print()
    print(f"{BLUE}=== org ready ==={RESET}")
    print(f"  agents      {GREY}{len(names)}{RESET}")
    print(f"  edges       {GREY}{len(edges)}{RESET}")
    print(f"  model       {GREY}strong={MODEL_STRONG}  default={MODEL_DEFAULT}{RESET}")
    print()

    grouped: dict[str, list[str]] = {}
    for a, b in edges:
        grouped.setdefault(a, []).append(b)
        grouped.setdefault(b, []).append(a)

    print(f"  {GREY}peer graph:{RESET}")
    for node in sorted(grouped):
        neighbors = sorted(set(grouped[node]))
        print(f"    {GREEN}{node:<10}{RESET}  {GREY}↔  {', '.join(neighbors)}{RESET}")

    print(f"\n  {GREY}agents (model / daily budget):{RESET}")
    for a in agents:
        model_short = a["model"].split("/")[-1]
        print(
            f"    {GREEN}{a['name']:<10}{RESET}  "
            f"{GREY}{model_short:<25}  ${a['daily_usd']:.1f}/day{RESET}"
        )

    print(f"\n  {GREY}workgroups:{RESET}")
    for spec in workgroups:
        all_m = [spec["hub"]] + spec["members"]
        print(
            f"    {GREEN}{spec['name']:<14}{RESET}  "
            f"hub={YELLOW}{spec['hub']:<8}{RESET}  "
            f"{GREY}{', '.join(all_m)}  ${spec['budget_usd']:.0f}{RESET}"
        )
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--skills-only",
        action="store_true",
        help=(
            "Re-install skills into existing profiles without nuking them. "
            "Safe targeted refresh — only touches each profile's skills/ "
            "subdirectory; sessions, memory, keys, .env are preserved."
        ),
    )
    args = parser.parse_args()

    agents = load_agents()
    workgroups = load_workgroups()
    names = [a["name"] for a in agents]

    # workgroup hub/members must exist — fail early with a clear message
    for spec in workgroups:
        for role in [spec["hub"]] + spec["members"]:
            if role not in names:
                fail(f"workgroup '{spec['name']}': '{role}' not found in agents/")

    edges = derive_edges(agents, workgroups)

    if args.skills_only:
        print(
            f"{BLUE}=== skills-only refresh  ·  {len(agents)} agents ==={RESET}"
        )
        print(f"{GREY}re-installs skills/ from organization/; profiles otherwise untouched{RESET}")
        print()
        install_skills(agents)
        return 0

    print(
        f"{BLUE}=== org bootstrap  ·  {len(agents)} agents  ·  "
        f"{len(edges)} edges  ·  {len(workgroups)} workgroups ==={RESET}"
    )
    print(f"{GREY}wipes & rebuilds: {', '.join(names)}{RESET}")
    print()

    env_lines = read_env_lines()
    nuke_profiles(agents)
    bootstrap_profiles(agents, workgroups, env_lines)
    wait_for_keypairs(agents)
    cross_pin(agents, edges)
    restart_and_verify(edges)
    setup_workgroups(workgroups)
    install_skills(agents)
    print_summary(agents, workgroups, edges)
    return 0


if __name__ == "__main__":
    sys.exit(main())
