"""Health check — verify everything this profile actually works.

Live checks (not just config presence): for email we log in + out over
IMAP, for Gmail we refresh the token, for MCPs we spawn + handshake +
stop. Network-bound checks run in a thread pool so total latency ≈
slowest single check, not the sum.

Each live check has a timeout so a hung provider can't stall the whole
report. If you want a pure-config scan (no network) — there isn't one;
the wizard does that at save time. Doctor is the "does it really work
right now?" answer.
"""

from __future__ import annotations

import ipaddress
import os
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Literal

from alpi import config as cfg_mod

Status = Literal["ok", "warn", "fail", "info"]


@dataclass
class Check:
    group: str
    name: str
    status: Status
    detail: str


_GLYPH = {
    "ok":   ("[green]✓[/green]",   "ok"),
    "warn": ("[yellow]![/yellow]", "warn"),
    "fail": ("[red]✗[/red]",        "fail"),
    "info": ("[dim]·[/dim]",        "info"),
}


def run_all(home: Path, profile: str) -> list[Check]:
    """Run every check; network-bound ones run in parallel with a timeout."""
    cfg = cfg_mod.load(home)
    env = _read_env(home)

    # Kick off live checks immediately so they run while we do the sync ones.
    live_specs: list[tuple[str, Callable[[], list[Check]]]] = [
        ("email", lambda: _check_email_live(home)),
        ("mcps", lambda: _check_mcps_live(cfg)),
    ]
    live: dict[str, list[Check]] = {}
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(fn): key for key, fn in live_specs}

        # Sync checks run on the main thread while live ones execute.
        sync_checks: dict[str, list[Check]] = {
            "version": _check_version(),
            "model": _check_model(cfg, env),
            "workspace": _check_workspace(cfg),
            "tools": _check_tools(),
            "skills": _check_skills(home),
            "services": _check_services(home, profile),
            "alp": _check_alp_integrity(home, cfg),
            "security": _check_security(cfg),
            "storage": _check_storage(home),
            "assets": _check_assets(home),
        }

        for fut in as_completed(futures):
            key = futures[fut]
            try:
                live[key] = fut.result(timeout=15.0)
            except Exception as e:  # noqa: BLE001
                live[key] = [Check("Live", key, "fail", str(e))]

    # Render order: version → model → workspace → tools → email → services → mcps → security.
    out: list[Check] = []
    out.extend(sync_checks["version"])
    out.extend(sync_checks["model"])
    out.extend(sync_checks["workspace"])
    out.extend(sync_checks["tools"])
    out.extend(sync_checks["skills"])
    out.extend(live.get("email", []))
    out.extend(sync_checks["services"])
    out.extend(sync_checks["alp"])
    out.extend(live.get("mcps", []))
    out.extend(sync_checks["security"])
    out.extend(sync_checks["storage"])
    out.extend(sync_checks["assets"])
    return out


def _check_assets(home: Path) -> list[Check]:
    from alpi import home as home_mod
    from alpi.core._playwright import _browsers_cache_dir, _wanted_chromium_dirs
    from alpi.service import _prefetch_mode

    out: list[Check] = []
    root = home_mod.alpi_root()
    out.append(Check("Assets", "prefetch", "info", f"mode {_prefetch_mode(root)}"))
    try:
        wanted = _wanted_chromium_dirs()
        cache = _browsers_cache_dir()
        present = sorted(w for w in wanted if (cache / w).is_dir())
        if present:
            out.append(Check("Assets", "chromium", "ok", ", ".join(present)))
        else:
            out.append(Check(
                "Assets", "chromium", "info",
                "not installed — fetched on first browser use",
            ))
        stale = sorted(
            e.name for e in cache.glob("chromium*")
            if e.is_dir() and e.name not in wanted
        ) if cache.is_dir() else []
        if stale:
            out.append(Check(
                "Assets", "chromium", "warn",
                f"stale builds wasting disk: {', '.join(stale)} — pruned on next successful install",
            ))
    except Exception:  # noqa: BLE001
        pass
    emb = root / "cache" / "fastembed"
    try:
        cached = emb.is_dir() and any(emb.iterdir())
    except OSError:
        cached = False
    if cached:
        out.append(Check("Assets", "embedder", "ok", "weights cached"))
    else:
        out.append(Check(
            "Assets", "embedder", "info",
            "not cached — fetched on first semantic search",
        ))
    return out


# Fleet-integrity signatures: a /data volume cloned across machines shows up as the local pubkey inside peers.yaml, or one pubkey under several peer ids.
def _check_alp_integrity(home: Path, cfg: cfg_mod.Config) -> list[Check]:
    import os

    from alpi import runtime
    from alpi.alp import keys as keys_mod
    from alpi.alp import peers as peers_mod

    out: list[Check] = []
    rows = peers_mod.load(home)

    own = None
    if keys_mod.exists(home):
        try:
            own = keys_mod.load(home).pubkey_b64()
        except Exception:  # noqa: BLE001
            own = None

    by_pubkey: dict[str, list[str]] = {}
    by_address: dict[str, list[str]] = {}
    for p in rows:
        by_pubkey.setdefault(p.pubkey, []).append(p.id)
        if p.address:
            by_address.setdefault(p.address, []).append(p.id)

    clean = True
    if own and by_pubkey.get(own):
        clean = False
        out.append(Check(
            "ALP", "identity", "fail",
            f"peer(s) {', '.join(by_pubkey[own])} carry THIS agent's pubkey — "
            "cloned /data volume; regenerate keys on one machine",
        ))
    for pubkey, ids in by_pubkey.items():
        if len(ids) > 1 and pubkey != own:
            clean = False
            out.append(Check(
                "ALP", "peers", "fail",
                f"{', '.join(ids)} share one pubkey — same identity under several "
                "entries (volume cloned between machines?)",
            ))
    for addr, ids in by_address.items():
        if len(ids) > 1:
            clean = False
            out.append(Check(
                "ALP", "peers", "warn",
                f"{addr} appears under {', '.join(ids)} — two handles dialing the same endpoint",
            ))
    if runtime.is_docker():
        advertised = (
            str(os.environ.get("ALPI_NETWORK_HOST") or "").strip()
            or str((cfg.network or {}).get("host") or "").strip()
        )
        if not advertised:
            clean = False
            out.append(Check(
                "ALP", "advertised address", "warn",
                "ALPI_NETWORK_HOST / network.host unset — clients and peers "
                "have no address to dial into this container",
            ))
    if clean and rows:
        out.append(Check("ALP", "peers", "ok", f"{len(rows)} peer(s), identities distinct"))
    return out


def _check_skills(home: Path) -> list[Check]:
    """SK.1 — surface skill telemetry. One summary row + warns for pinned skills that have gone cold (most likely curation candidates). Stale/archived counts inform but don't warn — pruning is AC.1's job in v0.7."""
    from alpi import skills_usage as _su

    stats = _su.summary(home)
    total = stats["total"]
    out: list[Check] = []
    if total == 0:
        out.append(Check("Skills", "telemetry", "info", "no usage recorded yet"))
        return out
    by_state = stats["by_state"]
    out.append(Check(
        "Skills", "telemetry", "ok",
        f"{total} tracked · "
        f"{by_state['active']} active / {by_state['stale']} stale / "
        f"{by_state['archived']} archived",
    ))
    for name, state in stats["pinned_cold"]:
        out.append(Check(
            "Skills", name, "warn",
            f"pinned but {state} — review for curation",
        ))
    return out


def _check_tools() -> list[Check]:
    """TL.1 — flag tools whose optional runtime deps are missing. Available tools share a single summary line; only unavailable ones get their own row so doctor stays scannable."""
    from alpi import tools as tools_mod

    report = tools_mod.availability_report()
    unavailable = [(name, reason) for name, ok, reason in report if not ok]
    out: list[Check] = []
    if unavailable:
        for name, reason in unavailable:
            out.append(Check("Tools", name, "warn", reason or "unavailable"))
        ok_count = len(report) - len(unavailable)
        out.append(Check("Tools", "registry", "info", f"{ok_count} other tools available"))
    else:
        out.append(Check("Tools", "registry", "ok", f"{len(report)} tools available"))
    return out


def render(console, checks: list[Check], profile: str, version: str) -> None:
    from rich.text import Text

    console.print(f"[b]alpi[/b] {version} · profile: [b]{profile}[/b]")
    console.print("")

    current_group = ""
    # Pre-compute column widths so each group's names align.
    name_w = max((len(c.name) for c in checks), default=0)

    for c in checks:
        if c.group != current_group:
            if current_group:
                console.print("")
            console.print(f"[dim]{c.group}[/dim]")
            current_group = c.group
        glyph, _ = _GLYPH[c.status]
        t = Text.from_markup(f"  {glyph} ")
        t.append(c.name.ljust(name_w + 2))
        t.append(c.detail, style="dim")
        console.print(t)

    fails = sum(1 for c in checks if c.status == "fail")
    warns = sum(1 for c in checks if c.status == "warn")
    console.print("")
    if fails:
        console.print(f"[red]{fails} failure{'s' if fails != 1 else ''}[/red]"
                      + (f" · {warns} warning{'s' if warns != 1 else ''}" if warns else ""))
    elif warns:
        console.print(f"[yellow]{warns} warning{'s' if warns != 1 else ''}[/yellow] · otherwise healthy")
    else:
        console.print("[green]all checks passed[/green]")


def exit_code(checks: list[Check]) -> int:
    """0 if all ok/warn/info, 1 if any fail. Warns do not break cron."""
    return 1 if any(c.status == "fail" for c in checks) else 0


# Progressive renderer


def run_and_render(console, home: Path, profile: str, version: str) -> list[Check]:
    """Stream results live with spinners — looks alive for the 5-10s it runs.

    Returns the final list of checks so the caller can compute an exit code.
    """
    import threading
    import time
    from rich.console import Group
    from rich.live import Live
    from rich.text import Text

    _FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    cfg = cfg_mod.load(home)
    env = _read_env(home)

    # Plan the full layout upfront. Every row has a stable key; sync rows
    # start resolved, live rows start as None (pending → spinner).
    plan: list[tuple[str, str, str]] = []  # (key, group, name)
    resolved: dict[str, Check] = {}
    lock = threading.Lock()

    def _add_sync(checks: list[Check]) -> None:
        for c in checks:
            key = f"{c.group}:{c.name}"
            plan.append((key, c.group, c.name))
            resolved[key] = c

    def _add_pending(key: str, group: str, name: str) -> None:
        plan.append((key, group, name))

    _add_sync(_check_version())
    _add_sync(_check_model(cfg, env))
    _add_sync(_check_workspace(cfg))

    from alpi.mail import accounts as accounts_mod
    email_rows = accounts_mod.list_accounts(home)
    if not email_rows:
        _add_sync([Check("Email", "accounts", "info", "none configured")])
    for row in email_rows:
        label = row.get("address") or row["id"]
        if row.get("configured"):
            _add_pending(f"email:{row['id']}", "Email", label)
        else:
            _add_sync([Check("Email", label, "info", "not authorized")])

    _add_sync(_check_services(home, profile))

    servers = (cfg.raw.get("mcp") or {}).get("servers") or {}
    if not servers:
        _add_sync([Check("MCPs", "configured", "info", "none")])
    else:
        for n in sorted(servers.keys()):
            _add_pending(f"mcp:{n}", "MCPs", n)

    _add_sync(_check_security(cfg))

    # Pre-compute column width from all known names.
    name_w = max(len(name) for _, _, name in plan)

    def _set(key: str, c: Check) -> None:
        with lock:
            resolved[key] = c

    def _render() -> Group:
        lines = []
        current_group = ""
        frame = _FRAMES[int(time.time() * 10) % len(_FRAMES)]
        for key, group, name in plan:
            if group != current_group:
                if current_group:
                    lines.append(Text(""))
                lines.append(Text.from_markup(f"[dim]{group}[/dim]"))
                current_group = group
            with lock:
                c = resolved.get(key)
            pad = " " * (name_w - len(name) + 2)
            if c is None:
                row = Text("  ")
                row.append(frame, style="cyan")
                row.append(f" {name}{pad}")
                row.append("checking…", style="dim")
            else:
                glyph_markup, _ = _GLYPH[c.status]
                row = Text.from_markup(f"  {glyph_markup} ")
                row.append(f"{name}{pad}")
                row.append(c.detail, style="dim")
            lines.append(row)
        return Group(*lines)

    console.print(f"[b]alpi[/b] {version} · profile: [b]{profile}[/b]")
    console.print("")

    with Live(_render(), console=console, refresh_per_second=12,
              transient=False) as live:
        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = []
            for row in email_rows:
                if not row.get("configured"):
                    continue
                key = f"email:{row['id']}"
                f = pool.submit(_check_account_live, home, row)
                f.add_done_callback(
                    lambda fu, k=key: _set(k, fu.result()) or live.update(_render())
                )
                futures.append(f)
            for n, spec in servers.items():
                key = f"mcp:{n}"
                f = pool.submit(_probe_mcp, n, spec)
                f.add_done_callback(
                    lambda fu, k=key: _set(k, fu.result()) or live.update(_render())
                )
                futures.append(f)

            # Tick the Live during execution so spinner animates even if no
            # callbacks fire for a while.
            import time
            while not all(f.done() for f in futures):
                live.update(_render())
                time.sleep(0.08)
            live.update(_render())

    # Build final ordered list + summary.
    final: list[Check] = []
    for key, group, name in plan:
        c = resolved.get(key)
        if c is None:
            c = Check(group, name, "fail", "check did not complete")
        final.append(c)

    fails = sum(1 for c in final if c.status == "fail")
    warns = sum(1 for c in final if c.status == "warn")
    console.print("")
    if fails:
        console.print(
            f"[red]{fails} failure{'s' if fails != 1 else ''}[/red]"
            + (f" · {warns} warning{'s' if warns != 1 else ''}" if warns else "")
        )
    elif warns:
        console.print(
            f"[yellow]{warns} warning{'s' if warns != 1 else ''}[/yellow] · otherwise healthy"
        )
    else:
        console.print("[green]all checks passed[/green]")
    return final


# Individual checks

def _check_version() -> list[Check]:
    from alpi import __version__, updater
    newer = updater.available_update()
    if newer:
        return [Check(
            "Version", "alpi-agent", "warn",
            f"v{__version__} → v{newer} available — run `alpi update`",
        )]
    cache = updater._load_cache()
    if cache is None:
        # No cache yet — daemon populates it asynchronously; show the
        # version without claiming it's up to date.
        return [Check("Version", "alpi-agent", "info", f"v{__version__}")]
    return [Check(
        "Version", "alpi-agent", "ok",
        f"v{__version__} (latest)",
    )]


def _check_model(cfg: cfg_mod.Config, env: dict[str, str]) -> list[Check]:
    out: list[Check] = []
    if not cfg.model:
        out.append(Check("Model", "configured", "fail",
                         "no model set — run `alpi setup → Model`"))
        return out
    out.append(Check("Model", "configured", "ok", cfg.model))

    key_var = _provider_api_key_var(cfg)
    if key_var is None:
        out.append(Check("Model", "API key", "ok", "ollama (no key required)"))
    elif env.get(key_var) or os.environ.get(key_var):
        out.append(Check("Model", "API key", "ok", f"{key_var} set"))
    else:
        out.append(Check("Model", "API key", "fail",
                         f"{key_var} missing in .env"))
    return out


def _check_workspace(cfg: cfg_mod.Config) -> list[Check]:
    wp = cfg.workspace_path
    if wp is None:
        return [Check("Workspace", "configured", "warn",
                      "no workspace — set one via `alpi setup`")]
    if not wp.exists():
        return [Check("Workspace", "exists", "fail", f"{wp} missing")]
    if not os.access(wp, os.W_OK):
        return [Check("Workspace", "writable", "fail", f"{wp} not writable")]
    return [Check("Workspace", "ready", "ok", str(wp))]


def _check_email_live(home: Path) -> list[Check]:
    from alpi.mail import accounts as accounts_mod

    rows = accounts_mod.list_accounts(home)
    if not rows:
        return [Check("Email", "accounts", "info", "none configured")]
    out: list[Check] = []
    for row in rows:
        out.append(_check_account_live(home, row))
    return out


def _check_account_live(home: Path, row: dict) -> Check:
    address = row.get("address") or row.get("id") or "?"
    if not row.get("configured"):
        return Check("Email", address, "info", "not authorized")
    if row.get("type") == "gmail":
        try:
            from alpi.mail import gmail_auth
            gmail_auth.get_access_token(home, row["id"])
            who = gmail_auth.get_email(home, row["id"]) or address
            return Check("Email", address, "ok", f"authorized as {who}")
        except Exception as e:  # noqa: BLE001
            return Check("Email", address, "fail", f"token refresh failed: {e}")
    try:
        from alpi.mail import accounts as accounts_mod
        client = accounts_mod.client_for(home, row["id"])
        client.test()
        return Check("Email", address, "ok", f"{address} · IMAP+SMTP ok")
    except Exception as e:  # noqa: BLE001
        return Check("Email", address, "fail", f"login/SMTP failed: {e}")


def _check_services(home: Path, profile: str) -> list[Check]:
    from alpi import home as home_mod
    from alpi import service as svc
    out: list[Check] = []

    from alpi import runtime

    installed = svc.daemon_installed()
    pid = svc.daemon_running_pid(home_mod._ROOT)
    bin_mtime = _alpi_binary_mtime()

    if runtime.is_docker():
        if pid:
            out.append(Check(
                "Services", "Daemon", "ok",
                f"managed by Docker (pid {pid})",
            ))
        else:
            out.append(Check(
                "Services", "Daemon", "warn",
                "managed by Docker but no live pid",
            ))
    elif installed and pid:
        if _is_binary_newer_than_process(bin_mtime, pid):
            out.append(Check(
                "Services", "Daemon", "warn",
                "running — stale binary — `alpi daemon restart` to reload",
            ))
        else:
            out.append(Check(
                "Services", "Daemon", "ok",
                f"running (pid {pid})",
            ))
    elif installed:
        out.append(Check("Services", "Daemon", "warn",
                         "installed but no live pid"))
    elif pid:
        out.append(Check("Services", "Daemon", "info",
                         f"running foreground (pid {pid}) — not installed"))
    else:
        out.append(Check("Services", "Daemon", "info",
                         "not installed — `alpi setup → Daemon` to enable"))

    out.extend(_check_alp(home))

    jobs_file = home / "schedule" / "jobs.json"
    if jobs_file.exists():
        import json
        try:
            n = len(json.loads(jobs_file.read_text() or "[]"))
        except Exception:  # noqa: BLE001
            n = -1
        if n >= 0:
            out.append(Check("Services", "Jobs", "info", f"{n} scheduled"))
    runs_file = home / "schedule" / "runs.json"
    if runs_file.exists():
        from alpi.scheduler import jobs_store
        try:
            jobs_store._load_json(runs_file, dict)
        except Exception:  # noqa: BLE001
            out.append(Check(
                "Services", "Job runs", "warn",
                "schedule/runs.json is corrupt — the scheduler skips every tick until it is repaired; no job fires",
            ))

    return out


def _check_alp(home: Path) -> list[Check]:
    """ALP-specific sub-checks beyond service liveness: identity key
    present, socket listening, pinned peers reachable. Granular enough
    that a failure tells the user exactly which piece to fix."""
    import socket as _socket
    out: list[Check] = []

    # Identity key — loadable Ed25519 pair?
    try:
        from alpi.alp.keys import exists as key_exists, load as key_load
        if key_exists(home):
            try:
                key_load(home)
                out.append(Check("ALP", "Identity", "ok", "Ed25519 keypair present"))
            except Exception as e:  # noqa: BLE001
                out.append(Check("ALP", "Identity", "fail",
                                 f"key files exist but failed to load: {e}"))
        else:
            out.append(Check("ALP", "Identity", "info",
                             "no keypair yet — generated on first `alpi daemon start`"))
    except Exception as e:  # noqa: BLE001
        out.append(Check("ALP", "Identity", "fail", f"keys module error: {e}"))

    # Socket — listening?
    sock_path = home / "alp" / "alp.sock"
    if sock_path.exists():
        s = _socket.socket(_socket.AF_UNIX, _socket.SOCK_STREAM)
        s.settimeout(0.5)
        try:
            s.connect(str(sock_path))
            out.append(Check("ALP", "Socket", "ok", f"listening on {sock_path}"))
        except (ConnectionRefusedError, OSError) as e:
            out.append(Check("ALP", "Socket", "warn",
                             f"stale socket at {sock_path}: {e}"))
        finally:
            s.close()
    else:
        out.append(Check("ALP", "Socket", "info",
                         "not listening — `alpi setup → Daemon → Install` or `alpi daemon start`"))

    # Peers — pinned and reachable?
    try:
        from alpi.alp import peers as peers_mod
        pinned = peers_mod.load(home)
    except Exception as e:  # noqa: BLE001
        out.append(Check("ALP", "Peers", "fail", f"peers.yaml error: {e}"))
        return out

    if not pinned:
        out.append(Check("ALP", "Peers", "info", "none pinned"))
        return out

    import asyncio
    from alpi.alp.setup import _probe_all

    try:
        results = asyncio.run(_probe_all(home, pinned, ""))
    except Exception as e:  # noqa: BLE001
        out.append(Check("ALP", "Peers", "fail", f"probe error: {e}"))
        return out

    total = len(pinned)
    reachable = sum(1 for v in results.values() if v[0] == "on")
    unreachable = [pid for pid, v in results.items() if v[0] != "on"]
    detail = f"{reachable}/{total} reachable"
    if unreachable:
        detail += f" · offline: {', '.join(unreachable)}"
    status: Status = "ok" if not unreachable else "warn"
    out.append(Check("ALP", "Peers", status, detail))
    return out


def _alpi_binary_mtime() -> float | None:
    """Modification time of the ``alpi`` executable on PATH, or None."""
    import os as _os
    path = shutil.which("alpi")
    if not path:
        return None
    try:
        return _os.path.getmtime(path)
    except OSError:
        return None


def _is_binary_newer_than_process(bin_mtime: float | None, pid: int) -> bool:
    """True when the ``alpi`` binary on disk is newer than ``pid``'s start
    time — i.e. the user reinstalled alpi but the daemon is still running
    the old code and needs a restart."""
    if bin_mtime is None:
        return False
    elapsed = _process_elapsed_seconds(pid)
    if elapsed is None:
        return False
    import time
    process_start = time.time() - elapsed
    # 30s grace — freshly-restarted processes shouldn't flash warn because
    # clocks and filesystem rounding drift.
    return bin_mtime > process_start + 30


def _process_elapsed_seconds(pid: int) -> int | None:
    """Return how many seconds ``pid`` has been running. ``ps -o etime=``
    format is portable across macOS + Linux (the ``etimes=`` variant is
    Linux-only); we parse the ``[[days-]hh:]mm:ss`` shape ourselves."""
    import subprocess
    try:
        r = subprocess.run(
            ["ps", "-o", "etime=", "-p", str(pid)],
            capture_output=True, text=True, timeout=2,
        )
    except Exception:  # noqa: BLE001
        return None
    if r.returncode != 0:
        return None
    return _parse_etime(r.stdout.strip())


def _parse_etime(raw: str) -> int | None:
    if not raw:
        return None
    days = 0
    if "-" in raw:
        day_part, _, raw = raw.partition("-")
        try:
            days = int(day_part)
        except ValueError:
            return None
    try:
        parts = [int(x) for x in raw.split(":")]
    except ValueError:
        return None
    if len(parts) == 2:
        h, m, s = 0, parts[0], parts[1]
    elif len(parts) == 3:
        h, m, s = parts[0], parts[1], parts[2]
    else:
        return None
    return days * 86400 + h * 3600 + m * 60 + s


def _probe_mcp(
    name: str, spec: dict, env_base: dict[str, str] | None = None,
) -> Check:
    """Spawn one MCP server, list its tools, then stop it."""
    from alpi.mcp.client import MCPClient
    command = str(spec.get("command") or "")
    if not command:
        return Check("MCPs", name, "fail", "no command in config")
    if shutil.which(command) is None:
        return Check("MCPs", name, "fail", f"{command!r} not on PATH")
    client = MCPClient(
        name=name, command=command,
        args=list(spec.get("args") or []),
        env=dict(spec.get("env") or {}),
        env_base=env_base,
    )
    try:
        client.start(timeout=8.0)
        tools = client.list_tools()
        return Check("MCPs", name, "ok",
                     f"{len(tools)} tool{'s' if len(tools) != 1 else ''}")
    except Exception as e:  # noqa: BLE001
        return Check("MCPs", name, "fail", f"handshake failed: {e}")
    finally:
        try:
            client.stop()
        except Exception:  # noqa: BLE001
            pass


def _check_mcps_live(cfg: cfg_mod.Config) -> list[Check]:
    servers = (cfg.raw.get("mcp") or {}).get("servers") or {}
    if not servers:
        return [Check("MCPs", "configured", "info", "none")]
    from alpi.home import effective_profile_env
    env_base = effective_profile_env(cfg.home)
    out_by_name: dict[str, Check] = {}
    with ThreadPoolExecutor(max_workers=min(8, len(servers))) as pool:
        futures = {pool.submit(_probe_mcp, n, s, env_base): n for n, s in servers.items()}
        for fut in as_completed(futures):
            c = fut.result()
            out_by_name[c.name] = c
    return [out_by_name[n] for n in sorted(out_by_name.keys())]


def _check_security(cfg: cfg_mod.Config) -> list[Check]:
    out: list[Check] = []
    term = cfg.tools.terminal
    if term.sandbox:
        backend = _sandbox_backend()
        if backend:
            net = "network allowed" if term.allow_network else "network denied"
            out.append(Check("Security", "Sandbox", "ok", f"{backend} · {net}"))
        else:
            out.append(Check("Security", "Sandbox", "fail",
                             "enabled but no backend (sandbox-exec / bwrap) on PATH"))
    else:
        out.append(Check("Security", "Sandbox", "info", "off"))

    allow = (cfg.raw.get("tools") or {}).get("terminal", {}).get("approval", {}).get("allowlist") or []
    if allow:
        out.append(Check("Security", "Approval allowlist", "info",
                         f"{len(allow)} entry(ies)"))
    else:
        out.append(Check("Security", "Approval allowlist", "info", "empty"))

    legacy_switches = cfg_mod.legacy_service_switches(cfg)
    if legacy_switches:
        names = ", ".join(f"service.{name}" for name in legacy_switches)
        out.append(Check(
            "Security", "Removed service switches", "warn",
            f"ignored: {names} — all daemon capabilities start; remove these keys",
        ))

    out.extend(_check_network_exposure(cfg))
    return out


def _check_network_exposure(cfg: cfg_mod.Config) -> list[Check]:
    # An IP literal only binds 0.0.0.0 (outside docker) via allow_public_bind
    # — a private IP binds itself — so that case is public-internet exposure.
    from alpi import runtime
    from alpi.host.network import resolve_bind_host

    configured = str((cfg.network or {}).get("host") or "").strip() or None
    if runtime.is_docker():
        return [Check(
            "Security", "Docker exposure", "warn",
            "the container bind cannot reveal host port publishing — verify "
            "`docker compose config`, the host firewall, and the security group",
        )]
    if not configured:
        return []
    allow_public = bool((cfg.host or {}).get("allow_public_bind"))
    bind = resolve_bind_host(configured, is_docker=False, allow_public=allow_public)
    if bind != "0.0.0.0":
        return []
    try:
        ipaddress.ip_address(configured)
    except ValueError:
        return [Check("Security", "Network exposure", "warn",
                      f"network.host {configured!r} binds all interfaces (0.0.0.0) — "
                      "configure a wss:// endpoint and verify firewall/NAT")]
    return [Check("Security", "Network exposure", "warn",
                  f"network.host {configured} is public (allow_public_bind on) — "
                  "direct ws:// advertisement is disabled; configure wss:// and "
                  "protect the pairing port and ALP listener")]


# Helpers

def _read_env(home: Path) -> dict[str, str]:
    env_path = home / ".env"
    if not env_path.exists():
        return {}
    out: dict[str, str] = {}
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        out[k.strip()] = v.strip()
    return out


def _provider_api_key_var(cfg: cfg_mod.Config) -> str | None:
    """Best-effort: given a model string, return the env var that holds its key.

    None means "no key required" (ollama). Empty string would mean unknown;
    we return a sensible default instead of confusing the check.
    """
    ollama_eps = {c.get("name") for c in cfg.providers.get("ollama", [])}
    head, _, _ = (cfg.model or "").partition("/")
    if head in ollama_eps:
        return None
    if head == "openrouter":
        return "OPENROUTER_API_KEY"
    if head == "openai" or head.startswith("gpt"):
        return "OPENAI_API_KEY"
    if head == "anthropic" or head.startswith("claude"):
        return "ANTHROPIC_API_KEY"
    if head == "gemini":
        return "GEMINI_API_KEY"
    return "OPENROUTER_API_KEY"  # safe default — most models go through openrouter


def _live_pid(home: Path, name: str = "service") -> int | None:
    """Live PID for the unified service. ``name`` parameter kept for
    legacy callers but ignored — there's only one process per profile."""
    from alpi import service as svc
    return svc.running_pid(home)


def _sandbox_backend() -> str | None:
    if shutil.which("sandbox-exec"):
        return "sandbox-exec"
    if shutil.which("bwrap"):
        return "bwrap"
    return None


# Storage thresholds — per-profile. Doctor only warns; cleanup is a user action via `alpi setup → Cleanup` or desktop Manage Sessions. Tuned for surprise-noise: a profile only ever sees a row when something is genuinely outsized.
_MB = 1024 * 1024
_STORAGE_THRESHOLDS = {
    "sessions":   ("Sessions",            "sessions",          1024 * _MB),
    "tts":        ("TTS cache",           "cache/tts",          500 * _MB),
    "workgroups": ("Workgroup transcripts", "alp/workgroups",   250 * _MB),
}


def _dir_size(d: Path) -> int:
    if not d.exists() or not d.is_dir():
        return 0
    total = 0
    try:
        for p in d.rglob("*"):
            if p.is_file():
                try:
                    total += p.stat().st_size
                except OSError:
                    pass
    except OSError:
        pass
    return total


def _fmt_mb(n: int) -> str:
    mb = n / _MB
    if mb >= 1024:
        return f"{mb / 1024:.1f} GB"
    return f"{mb:.0f} MB"


def _check_storage(home: Path) -> list[Check]:
    """ST.1 — warn when a per-profile store is outsized. Silent on the happy path; doctor never deletes — pointer is ``alpi setup → Cleanup`` (CLI) or desktop Manage Sessions for the sessions store."""
    out: list[Check] = []
    for _key, (label, rel, limit) in _STORAGE_THRESHOLDS.items():
        size = _dir_size(home / rel)
        if size > limit:
            hint = (
                "desktop Manage Sessions or `alpi setup → Cleanup`"
                if rel == "sessions"
                else "`alpi setup → Cleanup`"
            )
            out.append(Check(
                "Storage", label, "warn",
                f"{_fmt_mb(size)} on disk — review via {hint}",
            ))
    return out
