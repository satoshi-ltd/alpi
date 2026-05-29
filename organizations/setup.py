"""Org bootstrap — wipes and rebuilds every profile + persistent workgroup for a single org, then scaffolds its workspace. Org-specific data lives in `organizations/<org>/org.yaml`; everything else is mechanical."""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

# Make `alpi` importable when invoked as `python organizations/setup.py` (without `uv run` from the repo root).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml

from alpi.providers.reasoning import supports_reasoning

ROOT = Path.home() / ".alpi"
PROFILES_DIR = ROOT / "profiles"
ORGANIZATION_DIR = Path(__file__).resolve().parent
REPO_ROOT = ORGANIZATION_DIR.parent

# Populated by init_org() from <org>/org.yaml before any other function runs.
ORG_NAME: str = ""
ORG_DIR: Path = Path()
AGENTS_DIR: Path = Path()
WORKGROUPS_DIR: Path = Path()
COMMON_SKILLS_DIR: Path = Path()
USER_MEMORY_TEMPLATE: Path = Path()
WORKSPACE: str = ""
WORKSPACE_PATH: Path = Path()
WORKSPACE_SCAFFOLD: list[str] = []
SYNC_ITEMS: list[dict] = []
MODEL_DEFAULT: str = ""
MODEL_STRONG: str = ""
BUDGET_DAILY_DEFAULT: float = 0.0
BUDGET_DAILY_STRONG: float = 0.0
BUDGET_WG: float = 0.0
AGENT_VOICES: dict[str, str] = {}
COMMON_SKILLS: dict[str, list[str]] = {}
ORG_DISPLAY_NAME: str = ""


def discover_orgs() -> list[str]:
    return sorted(
        p.name for p in ORGANIZATION_DIR.iterdir()
        if p.is_dir() and (p / "org.yaml").is_file() and not p.name.startswith(("_", "."))
    )


def init_org(name: str) -> None:
    global ORG_NAME, ORG_DIR, AGENTS_DIR, WORKGROUPS_DIR, COMMON_SKILLS_DIR
    global USER_MEMORY_TEMPLATE, WORKSPACE, WORKSPACE_PATH
    global WORKSPACE_SCAFFOLD, SYNC_ITEMS
    global MODEL_DEFAULT, MODEL_STRONG
    global BUDGET_DAILY_DEFAULT, BUDGET_DAILY_STRONG, BUDGET_WG
    global AGENT_VOICES, COMMON_SKILLS, ORG_DISPLAY_NAME

    org_dir = ORGANIZATION_DIR / name
    cfg_path = org_dir / "org.yaml"
    if not cfg_path.exists():
        print(f"error: org config not found at {cfg_path}", file=sys.stderr)
        sys.exit(2)

    try:
        cfg = yaml.safe_load(cfg_path.read_text()) or {}
    except yaml.YAMLError as e:
        print(f"error: org config {cfg_path} is not valid YAML: {e}", file=sys.stderr)
        sys.exit(2)
    if not isinstance(cfg, dict):
        print(f"error: org config {cfg_path} must be a YAML mapping (got {type(cfg).__name__})", file=sys.stderr)
        sys.exit(2)

    ORG_NAME = name
    ORG_DIR = org_dir
    ORG_DISPLAY_NAME = str(cfg.get("display_name", name))
    AGENTS_DIR = org_dir / "agents"
    WORKGROUPS_DIR = org_dir / "workgroups"
    COMMON_SKILLS_DIR = org_dir / "common" / "skills"
    USER_MEMORY_TEMPLATE = org_dir / "user-memory.md"

    # Default workspace if the org's YAML doesn't set one: ~/alpi/organizations/<org>/. An explicit "~" keeps the user's home as workspace (current company case). Any other expanduser-compatible string is honoured verbatim. YAML's bare ~ parses to None and triggers the default.
    explicit_ws = cfg.get("workspace")
    workspace_raw = explicit_ws if explicit_ws is not None else f"~/alpi/organizations/{name}"
    try:
        WORKSPACE_PATH = Path(str(workspace_raw)).expanduser().resolve()
    except (RuntimeError, OSError) as e:
        print(f"error: org '{name}' workspace path '{workspace_raw}' invalid: {e}", file=sys.stderr)
        sys.exit(2)
    if WORKSPACE_PATH == Path("/") or str(WORKSPACE_PATH) == "":
        print(f"error: org '{name}' workspace resolves to filesystem root — refusing to scaffold", file=sys.stderr)
        sys.exit(2)
    WORKSPACE = str(WORKSPACE_PATH)

    WORKSPACE_SCAFFOLD = list(cfg.get("workspace_scaffold", []))
    SYNC_ITEMS = list(cfg.get("sync", []))

    models = cfg.get("models", {}) or {}
    MODEL_DEFAULT = str(models.get("default", "openai/gpt-5.4-mini"))
    MODEL_STRONG = str(models.get("strong", "anthropic/claude-sonnet-4-6"))

    budgets = cfg.get("budgets", {}) or {}
    BUDGET_DAILY_DEFAULT = float(budgets.get("daily_default", 2.0))
    BUDGET_DAILY_STRONG = float(budgets.get("daily_strong", 5.0))
    BUDGET_WG = float(budgets.get("workgroup", 50.0))

    AGENT_VOICES = dict(cfg.get("agent_voices") or {})
    COMMON_SKILLS = dict(cfg.get("common_skills") or {})


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


_FRONT_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)

ALPI_TOOLS_DIR = REPO_ROOT / "alpi" / "tools"


def canonical_tools() -> set[str]:
    """Read alpi/tools/*.py and return the set of declared tool names (the `name = "…"` class attr on each Tool subclass)."""
    names: set[str] = set()
    if not ALPI_TOOLS_DIR.exists():
        warn(f"alpi/tools/ not found at {ALPI_TOOLS_DIR} — skipping tool registry checks")
        return names
    for py in ALPI_TOOLS_DIR.glob("*.py"):
        if py.name.startswith("_"):
            continue
        for m in re.finditer(r'^\s+name\s*=\s*"([a-z_]+)"', py.read_text(), re.M):
            names.add(m.group(1))
    return names


def _parse_frontmatter(path: Path) -> tuple[dict, str]:
    text = path.read_text()
    m = _FRONT_RE.match(text)
    if not m:
        return {}, text
    fm = yaml.safe_load(m.group(1)) or {}
    body = text[m.end():]
    return fm, body


def validate_org(agents: list[dict], strict: bool = True) -> tuple[list[str], list[str]]:
    """Validate SKILL.md and agent.md across the org. Returns (hard_errors, warnings). Hard errors block the bootstrap; warnings are advisory."""
    errors: list[str] = []
    warnings: list[str] = []

    tools = canonical_tools()
    have_registry = bool(tools)

    # 1. Per-agent: tools_deny in agent.md must reference real tools — typo here is a SECURITY gap (deny silently misses, tool stays enabled).
    if have_registry:
        for agent in agents:
            unknown = [t for t in agent["tools_deny"] if t not in tools]
            if unknown:
                rel = (AGENTS_DIR / agent["name"] / "agent.md").relative_to(REPO_ROOT)
                errors.append(f"{rel}: tools_deny references unknown tool(s) {unknown} — security risk, deny silently misses")

    # 2. Per-agent: reasoning_effort is REQUIRED in every agent.md. No invisible defaults — reasoning is a property of the agent's identity, not the org's tier policy.
    for agent in agents:
        rel = (AGENTS_DIR / agent["name"] / "agent.md").relative_to(REPO_ROOT)
        eff = agent["reasoning_effort"]
        if eff == "__missing__":
            errors.append(f"{rel}: missing required frontmatter field 'reasoning_effort' (off | low | medium | high)")
            continue
        if eff == "__invalid__":
            errors.append(f"{rel}: reasoning_effort has invalid value — must be one of: off, low, medium, high")
            continue
        if eff in {"low", "medium", "high"} and not supports_reasoning(agent["model"]):
            warnings.append(f"{rel}: reasoning_effort='{eff}' declared but model '{agent['model']}' doesn't support reasoning — value will be ignored")

    # 3. Per-skill: structural integrity + tool-name correctness.
    skill_paths = sorted(AGENTS_DIR.rglob("SKILL.md"))
    for skill_path in skill_paths:
        fm, body = _parse_frontmatter(skill_path)
        rel = skill_path.relative_to(REPO_ROOT)

        if not fm.get("description"):
            errors.append(f"{rel}: missing required frontmatter field 'description'")
        if not fm.get("category"):
            errors.append(f"{rel}: missing required frontmatter field 'category'")

        if have_registry:
            declared = list(fm.get("tools") or [])
            unknown = [t for t in declared if t not in tools]
            if unknown:
                warnings.append(f"{rel}: tools frontmatter references unknown tool(s) {unknown}")

            body_lower = body.lower()
            backticked = set(re.findall(r"`([a-z_]+)`", body_lower))
            referenced = backticked & tools
            missing = sorted(referenced - set(declared) - {"skill"})
            if missing:
                warnings.append(f"{rel}: body references undeclared tool(s) {missing}")

    return errors, warnings


def report_validation(errors: list[str], warnings: list[str]) -> bool:
    """Print findings and return True if bootstrap should proceed."""
    if not errors and not warnings:
        ok(f"validation clean: {len(errors)} errors, {len(warnings)} warnings")
        return True
    if warnings:
        for w in warnings:
            warn(w)
    if errors:
        print(f"{RED}✗ validation failed: {len(errors)} hard error(s){RESET}")
        for e in errors:
            print(f"  {RED}✗{RESET} {e}")
        return False
    ok(f"validation: 0 errors, {len(warnings)} warning(s) (continuing)")
    return True


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

    for agent in agents:
        for peer in agent.get("peers", []):
            _add(agent["name"], peer)

    for wg in workgroups:
        hub = wg["hub"]
        for member in wg["members"]:
            _add(hub, member)

    return edges


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
        briefing = " ".join(briefing.split())
        wgs.append({
            "name":       p.parent.name,
            "hub":        front["hub"],
            "members":    list(front.get("members", [])),
            "budget_usd": float(front.get("budget_usd", BUDGET_WG)),
            "briefing":   briefing,
        })
    return wgs


def _parse_agent_file(path: Path) -> dict:
    raw = path.read_text()
    m = _FRONT_RE.match(raw)
    if not m:
        fail(f"{path}: missing YAML frontmatter block (expected --- ... ---)")
    front = yaml.safe_load(m.group(1)) or {}
    soul = raw[m.end():].strip()

    tier = front.get("tier", "default")
    if "model" in front:
        model = front["model"]
    elif tier == "strong":
        model = MODEL_STRONG
    else:
        model = MODEL_DEFAULT

    daily_usd = float(front.get("daily_usd", BUDGET_DAILY_DEFAULT))

    # Reasoning effort is REQUIRED in every agent.md. validate_org() catches missing or malformed values. Here we just parse and normalise. YAML 1.1 booleanises bare `off` / `no` / `false` to False — handle that. "" means "not declared" (validation will fail later).
    if "reasoning_effort" in front:
        raw_eff = front["reasoning_effort"]
        if raw_eff is False:
            reasoning_effort = "off"
        else:
            raw_str = str(raw_eff or "").strip().lower()
            if raw_str in {"off", "none", "no", "disabled", "false"}:
                reasoning_effort = "off"
            elif raw_str in {"low", "medium", "high"}:
                reasoning_effort = raw_str
            else:
                reasoning_effort = "__invalid__"
    else:
        reasoning_effort = "__missing__"

    return {
        "name":             path.parent.name,
        "bio":              front.get("bio", ""),
        "accent":           front.get("accent", "#888888"),
        "tier":             tier,
        "model":            model,
        "daily_usd":        daily_usd,
        "reasoning_effort": reasoning_effort,
        "soul":             soul,
        "peers":            list(front.get("peers", [])),
        "tools_deny":       list(front.get("tools_deny", [])),
    }


def load_agents() -> list[dict]:
    paths = sorted(AGENTS_DIR.glob("*/agent.md"))
    if not paths:
        fail(f"no agent files found in {AGENTS_DIR}/*/agent.md")
    return [_parse_agent_file(p) for p in paths]


def load_agent_mcps(agent_name: str, env: dict) -> dict:
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
    name = agent["name"].capitalize()

    wg_lines = []
    for wg in workgroups:
        if agent["name"] == wg["hub"]:
            wg_lines.append(f"- **{wg['name'].capitalize()}** (you are the hub — you open tasks and decide #done)")
        elif agent["name"] in wg["members"]:
            wg_lines.append(f"- **{wg['name'].capitalize()}** (fixed peer — hub is {wg['hub'].capitalize()})")
    wg_section = "\n".join(wg_lines) if wg_lines else "- None (invited on demand)"

    peers = ", ".join(p.capitalize() for p in agent.get("peers", []))
    peers_section = peers if peers else "None declared — you are invited on demand"

    if not USER_MEMORY_TEMPLATE.exists():
        fail(f"user-memory template not found at {USER_MEMORY_TEMPLATE}")
    template = USER_MEMORY_TEMPLATE.read_text()
    return template.format(name=name, wg_section=wg_section, peers=peers_section)


def read_env_lines() -> str:
    org_env = ORG_DIR / ".env"
    if org_env.exists():
        return org_env.read_text()
    default_env = ROOT / ".env"
    if default_env.exists():
        return default_env.read_text()
    fail(f"no .env found — add API keys to {org_env} or {default_env}")


def _hard_remove(home: Path, name: str) -> None:
    if home.exists():
        run(["alpi", "profile", "remove", name, "--yes", "--force"])
    if home.exists():
        shutil.rmtree(home, ignore_errors=True)


def nuke_profiles(agents: list[dict]) -> None:
    step(f"nuking {ORG_NAME} profiles")
    for agent in agents:
        home = PROFILES_DIR / agent["name"]
        if home.exists():
            _hard_remove(home, agent["name"])
            ok(f"removed {agent['name']}")
    time.sleep(0.5)


ALP_BIO_LIMIT = 200


def _truncate_bio(bio: str, limit: int = ALP_BIO_LIMIT) -> str:
    encoded = bio.encode("utf-8")
    if len(encoded) <= limit:
        return bio
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


def _sync_children(src: Path, dst: Path) -> int:
    """Replace each child of dst with the corresponding child from src. Returns count."""
    count = 0
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        target = dst / item.name
        if item.is_dir():
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(item, target)
        else:
            shutil.copy2(item, target)
        count += 1
    return count


def scaffold_workspace() -> None:
    is_home = WORKSPACE_PATH == Path.home()

    if is_home and not WORKSPACE_SCAFFOLD and not SYNC_ITEMS:
        # Workspace points at $HOME with nothing to add — assume the user's home is already real.
        return

    if WORKSPACE_PATH.exists() and not WORKSPACE_PATH.is_dir():
        fail(f"workspace path exists but is not a directory: {WORKSPACE_PATH}")

    created = not WORKSPACE_PATH.exists()
    step(f"{'creating' if created else 'scaffolding'} workspace at {WORKSPACE_PATH}")
    try:
        WORKSPACE_PATH.mkdir(parents=True, exist_ok=True)
    except PermissionError as e:
        fail(f"permission denied creating workspace {WORKSPACE_PATH}: {e}")
    except OSError as e:
        fail(f"cannot create workspace {WORKSPACE_PATH}: {e}")
    if created:
        ok(f"workspace dir created")

    for sub in WORKSPACE_SCAFFOLD:
        target = WORKSPACE_PATH / sub
        try:
            target.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            fail(f"cannot create {target}: {e}")

    for item in SYNC_ITEMS:
        if "src" not in item or "dst" not in item:
            warn(f"sync entry missing 'src' or 'dst' — skipping: {item}")
            continue
        src = ORG_DIR / item["src"]
        dst = WORKSPACE_PATH / item["dst"]
        if not src.exists():
            warn(f"sync source not found: {src} — skipping")
            continue
        try:
            n = _sync_children(src, dst)
        except (OSError, shutil.Error) as e:
            fail(f"sync failed {src} → {dst}: {e}")
        ok(f"synced {n} item(s): {item['src']} → {item['dst']}")

    if WORKSPACE_SCAFFOLD:
        ok(f"workspace ready: {len(WORKSPACE_SCAFFOLD)} folder(s)")


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
        cfg["org"] = ORG_NAME
        cfg["public_bio"] = _truncate_bio(agent["bio"])
        cfg.setdefault("tui", {})["accent"] = agent["accent"]
        cfg.setdefault("budget", {})["daily_usd"] = agent["daily_usd"]

        # Apply reasoning only when explicitly declared as low/medium/high AND the model supports it. "off" / missing / unsupported-model all collapse to "no reasoning config" — keeps config.yaml minimal and intent explicit (declarations live in agent.md).
        if agent["reasoning_effort"] in {"low", "medium", "high"} and supports_reasoning(agent["model"]):
            cfg["model_reasoning"] = {"effort": agent["reasoning_effort"]}
        else:
            cfg.pop("model_reasoning", None)

        if agent["tools_deny"]:
            cfg.setdefault("tools", {})["deny"] = agent["tools_deny"]
        else:
            cfg.get("tools", {}).pop("deny", None)
        voice = AGENT_VOICES.get(agent["name"])
        if voice:
            cfg.setdefault("tools", {}).setdefault("tts", {})["voice"] = voice

        mcps = load_agent_mcps(agent["name"], env_dict)
        if mcps:
            cfg.setdefault("mcp", {})["servers"] = mcps

        cfg_path.write_text(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True))

        mem_dir = h / "memories"
        (mem_dir / "AGENT.md").write_text(agent["soul"])
        (mem_dir / "USER.md").write_text(_make_user_md(agent, workgroups))

        mcp_note = f"  mcps={','.join(mcps)}" if mcps else ""
        applied_effort = agent["reasoning_effort"] if (agent["reasoning_effort"] in {"low", "medium", "high"} and supports_reasoning(agent["model"])) else ""
        reasoning_note = f"  reasoning={applied_effort}" if applied_effort else ""
        deny_note = f"  deny={len(agent['tools_deny'])}" if agent["tools_deny"] else ""
        ok(f"{agent['name']:<10}  model={agent['model']}  daily=${agent['daily_usd']:.1f}{reasoning_note}{deny_note}{mcp_note}")

    install_code = (
        "from alpi import service as svc\n"
        "from alpi import home as home_mod\n"
        "svc.install_daemon(home_mod._ROOT)\n"
        "print('ok')\n"
    )
    res = run(
        ["uv", "run", "python", "-c", install_code],
        cwd=str(REPO_ROOT),
    )
    if res.returncode != 0:
        fail(f"daemon install failed: {res.stderr}")
    ok("daemon installed")


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


def restart_and_verify(edges: list[tuple[str, str]]) -> None:
    step("restarting daemon")
    res = run(["alpi", "daemon", "restart"])
    if res.returncode != 0:
        fail(f"daemon restart failed: {res.stderr.strip()}")

    time.sleep(5)

    pending: set[tuple[str, str]] = set()
    for a, b in edges:
        pending.add((a, b))
        pending.add((b, a))

    deadline_s = 180
    step(f"verifying {len(pending)} peer connections (ping, up to {deadline_s}s)")
    deadline = time.time() + deadline_s
    backoff = 1.0
    while time.time() < deadline and pending:
        for pair in list(pending):
            caller, target = pair
            probe = run(["alpi", "-p", caller, "peers", "ping", target])
            if probe.returncode == 0:
                pending.discard(pair)
        if pending:
            time.sleep(backoff)
            backoff = min(backoff * 1.5, 4.0)

    if pending:
        details = ", ".join(f"{a}→{b}" for a, b in sorted(pending))
        fail(f"peers unreachable after {deadline_s}s: {details}")
    ok("all pings answered")


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
    step(f"creating {len(workgroups)} persistent workgroups")
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

    for skill_path, targets in COMMON_SKILLS.items():
        src = COMMON_SKILLS_DIR / skill_path
        if not src.exists():
            warn(f"common skill not found: {src}")
            continue
        for target in targets:
            if target not in agent_names:
                warn(f"common skill target '{target}' not in agents; skipping")
                continue
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


def print_summary(
    agents: list[dict],
    workgroups: list[dict],
    edges: list[tuple[str, str]],
) -> None:
    names = [a["name"] for a in agents]
    print()
    print(f"{BLUE}=== {ORG_DISPLAY_NAME} ready ==={RESET}")
    print(f"  agents      {GREY}{len(names)}{RESET}")
    print(f"  edges       {GREY}{len(edges)}{RESET}")
    print(f"  workspace   {GREY}{WORKSPACE_PATH}{RESET}")
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

    print(f"\n  {GREY}persistent workgroups:{RESET}")
    for spec in workgroups:
        all_m = [spec["hub"]] + spec["members"]
        print(
            f"    {GREEN}{spec['name']:<14}{RESET}  "
            f"hub={YELLOW}{spec['hub']:<8}{RESET}  "
            f"{GREY}{', '.join(all_m)}  ${spec['budget_usd']:.0f}{RESET}"
        )
    print()


def main() -> int:
    available = discover_orgs()
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "org",
        choices=available,
        help=f"Org to bootstrap. Available: {', '.join(available)}",
    )
    parser.add_argument(
        "--skills-only",
        action="store_true",
        help="Re-install skills into existing profiles without nuking them.",
    )
    parser.add_argument(
        "--workspace-only",
        action="store_true",
        help="Re-sync workspace scaffold + templates/library only, without touching profiles or workgroups.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Run validation only (SKILL.md + agent.md against alpi/tools/ registry) and exit. Nothing else runs. Suitable for CI.",
    )
    parser.add_argument(
        "--no-check",
        action="store_true",
        help="Skip the pre-bootstrap validation gate. Use only when iterating on tooling itself.",
    )
    parser.add_argument(
        "--nuke",
        action="store_true",
        help="Destroy all profiles for this org under ~/.alpi/profiles/ (workgroups go with them). No rebuild. Workspace untouched unless --workspace is also passed.",
    )
    parser.add_argument(
        "--workspace",
        action="store_true",
        help="With --nuke, also delete the workspace directory. Refuses if workspace resolves to your home (~). Irreversible.",
    )
    args = parser.parse_args()

    if args.skills_only and args.workspace_only:
        fail("--skills-only and --workspace-only are mutually exclusive")
    if args.check and (args.skills_only or args.workspace_only or args.no_check or args.nuke):
        fail("--check stands alone (incompatible with --skills-only/--workspace-only/--no-check/--nuke)")
    if args.nuke and (args.skills_only or args.workspace_only or args.no_check):
        fail("--nuke is incompatible with --skills-only/--workspace-only/--no-check")
    if args.workspace and not args.nuke:
        fail("--workspace is only valid in combination with --nuke")

    init_org(args.org)

    if args.nuke:
        agents = load_agents()
        names = [a["name"] for a in agents]
        print(f"{RED}=== {ORG_DISPLAY_NAME} · NUKE ==={RESET}")
        print(f"{YELLOW}Will destroy {len(agents)} profile(s) under ~/.alpi/profiles/: {', '.join(names)}{RESET}")
        if args.workspace:
            if WORKSPACE_PATH == Path.home():
                fail(f"refusing to nuke workspace — it resolves to your home directory ({WORKSPACE_PATH})")
            if not WORKSPACE_PATH.exists():
                warn(f"workspace {WORKSPACE_PATH} doesn't exist — skipping")
            else:
                print(f"{YELLOW}Will also delete workspace dir: {WORKSPACE_PATH}{RESET}")
        print()
        nuke_profiles(agents)
        if args.workspace and WORKSPACE_PATH != Path.home() and WORKSPACE_PATH.exists():
            step(f"removing workspace at {WORKSPACE_PATH}")
            try:
                shutil.rmtree(WORKSPACE_PATH)
            except OSError as e:
                fail(f"cannot remove workspace: {e}")
            ok(f"workspace removed")
        print()
        ok(f"{ORG_DISPLAY_NAME} nuked. Re-run `organizations/setup.py {args.org}` to rebuild.")
        return 0

    agents = load_agents()
    workgroups = load_workgroups()
    names = [a["name"] for a in agents]
    name_set = set(names)

    for spec in workgroups:
        for role in [spec["hub"]] + spec["members"]:
            if role not in name_set:
                fail(f"workgroup '{spec['name']}': '{role}' not found in {AGENTS_DIR}")

    unknown_voices = [n for n in AGENT_VOICES if n not in name_set]
    if unknown_voices:
        warn(f"org.yaml agent_voices references unknown agents (no profile): {unknown_voices}")

    for skill_path, targets in COMMON_SKILLS.items():
        unknown = [t for t in targets if t not in name_set]
        if unknown:
            warn(f"common_skills '{skill_path}' targets unknown agents: {unknown}")
        if not (COMMON_SKILLS_DIR / skill_path).exists():
            warn(f"common_skills '{skill_path}' source missing: {COMMON_SKILLS_DIR / skill_path}")

    edges = derive_edges(agents, workgroups)

    if args.check:
        print(f"{BLUE}=== {ORG_DISPLAY_NAME} · validation check ==={RESET}")
        errors, warnings = validate_org(agents)
        proceed = report_validation(errors, warnings)
        return 0 if proceed else 1

    if not args.no_check:
        step("validating skills + agent.md against alpi tool registry")
        errors, warnings = validate_org(agents)
        if not report_validation(errors, warnings):
            print(f"{RED}aborting — fix the hard errors above, or pass --no-check to bypass (not recommended).{RESET}")
            return 1

    if args.skills_only:
        print(f"{BLUE}=== {ORG_DISPLAY_NAME} · skills-only refresh  ·  {len(agents)} agents ==={RESET}")
        print(f"{GREY}re-installs skills/ from {ORG_DIR.relative_to(REPO_ROOT)}/; profiles otherwise untouched{RESET}")
        print()
        install_skills(agents)
        return 0

    if args.workspace_only:
        if not WORKSPACE_SCAFFOLD and not SYNC_ITEMS:
            print(f"{YELLOW}{ORG_DISPLAY_NAME} has no workspace_scaffold or sync items — nothing to do.{RESET}")
            return 0
        print(f"{BLUE}=== {ORG_DISPLAY_NAME} · workspace-only refresh ==={RESET}")
        print(f"{GREY}re-syncs scaffold + templates/library; profiles + workgroups untouched{RESET}")
        print()
        scaffold_workspace()
        return 0

    print(
        f"{BLUE}=== {ORG_DISPLAY_NAME} bootstrap  ·  {len(agents)} agents  ·  "
        f"{len(edges)} edges  ·  {len(workgroups)} persistent workgroups ==={RESET}"
    )
    print(f"{GREY}wipes & rebuilds: {', '.join(names)}{RESET}")
    print(f"{GREY}workspace target: {WORKSPACE_PATH}{RESET}")
    print()

    env_lines = read_env_lines()
    nuke_profiles(agents)
    bootstrap_profiles(agents, workgroups, env_lines)
    scaffold_workspace()
    wait_for_keypairs(agents)
    cross_pin(agents, edges)
    restart_and_verify(edges)
    setup_workgroups(workgroups)
    install_skills(agents)
    print_summary(agents, workgroups, edges)
    return 0


if __name__ == "__main__":
    sys.exit(main())
