"""Health check — verify everything this profile actually works.

Live checks (not just config presence): for Telegram we hit `getMe`, for
IMAP we log in + out, for Gmail we refresh the token, for MCPs we spawn
+ handshake + stop. Network-bound checks run in a thread pool so total
latency ≈ slowest single check, not the sum.

Each live check has a timeout so a hung provider can't stall the whole
report. If you want a pure-config scan (no network) — there isn't one;
the wizard does that at save time. Doctor is the "does it really work
right now?" answer.
"""

from __future__ import annotations

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
        ("gateways", lambda: (
            _check_telegram_live(env)
            + _check_imap_live(env)
            + _check_gmail_live(home, env)
        )),
        ("mcps", lambda: _check_mcps_live(cfg)),
    ]
    live: dict[str, list[Check]] = {}
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(fn): key for key, fn in live_specs}

        # Sync checks run on the main thread while live ones execute.
        sync_checks: dict[str, list[Check]] = {
            "model": _check_model(cfg, env),
            "workspace": _check_workspace(cfg),
            "services": _check_services(home, profile),
            "security": _check_security(cfg),
        }

        for fut in as_completed(futures):
            key = futures[fut]
            try:
                live[key] = fut.result(timeout=15.0)
            except Exception as e:  # noqa: BLE001
                live[key] = [Check("Live", key, "fail", str(e))]

    # Final render order: model → workspace → gateways → services → mcps → security.
    out: list[Check] = []
    out.extend(sync_checks["model"])
    out.extend(sync_checks["workspace"])
    out.extend(live.get("gateways", []))
    out.extend(sync_checks["services"])
    out.extend(live.get("mcps", []))
    out.extend(sync_checks["security"])
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

    _add_sync(_check_model(cfg, env))
    _add_sync(_check_workspace(cfg))

    # Gateways: always show all three rows; pending if configured.
    if env.get("TELEGRAM_BOT_TOKEN"):
        _add_pending("tg", "Gateways", "Telegram")
    else:
        _add_sync([Check("Gateways", "Telegram", "info", "not configured")])
    if env.get("IMAP_ADDRESS"):
        _add_pending("imap", "Gateways", "IMAP")
    else:
        _add_sync([Check("Gateways", "IMAP", "info", "not configured")])
    if env.get("GMAIL_CLIENT_ID"):
        _add_pending("gmail", "Gateways", "Gmail")
    else:
        _add_sync([Check("Gateways", "Gmail", "info", "not configured")])

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
            if any(k == "tg" for k, _, _ in plan):
                f = pool.submit(_check_telegram_live, env)
                f.add_done_callback(lambda fu: _set("tg", fu.result()[0]) or live.update(_render()))
                futures.append(f)
            if any(k == "imap" for k, _, _ in plan):
                f = pool.submit(_check_imap_live, env)
                f.add_done_callback(lambda fu: _set("imap", fu.result()[0]) or live.update(_render()))
                futures.append(f)
            if any(k == "gmail" for k, _, _ in plan):
                f = pool.submit(_check_gmail_live, home, env)
                f.add_done_callback(lambda fu: _set("gmail", fu.result()[0]) or live.update(_render()))
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


def _check_telegram_live(env: dict[str, str]) -> list[Check]:
    import json as _json
    import urllib.request
    token = env.get("TELEGRAM_BOT_TOKEN")
    if not token:
        return [Check("Gateways", "Telegram", "info", "not configured")]

    allow = [c for c in (env.get("TELEGRAM_ALLOWED_CHAT_IDS") or "").split(",") if c.strip()]
    try:
        url = f"https://api.telegram.org/bot{token}/getMe"
        with urllib.request.urlopen(url, timeout=5.0) as resp:
            body = _json.loads(resp.read().decode())
        if not body.get("ok"):
            return [Check("Gateways", "Telegram", "fail",
                          f"getMe: {body.get('description', 'unknown error')}")]
        username = body.get("result", {}).get("username", "?")
        if not allow:
            return [Check("Gateways", "Telegram", "warn",
                          f"@{username} reachable but no chats allowlisted (fail-closed)")]
        return [Check("Gateways", "Telegram", "ok",
                      f"@{username} · {len(allow)} allowlisted")]
    except Exception as e:  # noqa: BLE001
        return [Check("Gateways", "Telegram", "fail", f"unreachable: {e}")]


def _check_imap_live(env: dict[str, str]) -> list[Check]:
    if not env.get("IMAP_ADDRESS"):
        return [Check("Gateways", "IMAP", "info", "not configured")]
    try:
        from alpi.mail.imap import ImapClient, DEFAULT_IMAP_PORT, DEFAULT_SMTP_PORT
        client = ImapClient(
            address=env["IMAP_ADDRESS"],
            password=env.get("IMAP_PASSWORD", ""),
            imap_host=env.get("IMAP_HOST", ""),
            smtp_host=env.get("SMTP_HOST", ""),
            imap_port=int(env.get("IMAP_PORT") or DEFAULT_IMAP_PORT),
            smtp_port=int(env.get("SMTP_PORT") or DEFAULT_SMTP_PORT),
        )
        client.test()
        senders = [s for s in (env.get("IMAP_ALLOWED_SENDERS") or "").split(",") if s.strip()]
        return [Check("Gateways", "IMAP", "ok",
                      f"{env['IMAP_ADDRESS']} · {len(senders)} allowlisted sender(s)")]
    except Exception as e:  # noqa: BLE001
        return [Check("Gateways", "IMAP", "fail", f"login/SMTP failed: {e}")]


def _check_gmail_live(home: Path, env: dict[str, str]) -> list[Check]:
    if not env.get("GMAIL_CLIENT_ID"):
        return [Check("Gateways", "Gmail", "info", "not configured")]
    try:
        from alpi.mail import gmail_auth
        gmail_auth.get_access_token(home)  # refreshes if needed, raises on fail
        email = gmail_auth.get_email(home) or "?"
        return [Check("Gateways", "Gmail", "ok", f"authorized as {email}")]
    except Exception as e:  # noqa: BLE001
        return [Check("Gateways", "Gmail", "fail", f"token refresh failed: {e}")]


def _check_services(home: Path, profile: str) -> list[Check]:
    from alpi import service
    out: list[Check] = []

    for name in ("gateway", "schedule"):
        backend = service.installed(name, profile)
        pid = _live_pid(home, name)
        if backend and pid:
            out.append(Check("Services", name.capitalize(), "ok",
                             f"running via {backend} (pid {pid})"))
        elif backend:
            out.append(Check("Services", name.capitalize(), "warn",
                             f"installed via {backend} but no live pid"))
        else:
            status: Status = "info" if name == "gateway" else "warn"
            detail = ("not installed — `alpi setup → Schedule service` to enable"
                      if name == "schedule" else "not installed")
            out.append(Check("Services", name.capitalize(), status, detail))

    jobs_file = home / "schedule" / "jobs.json"
    if jobs_file.exists():
        import json
        try:
            n = len(json.loads(jobs_file.read_text() or "[]"))
        except Exception:  # noqa: BLE001
            n = -1
        if n >= 0:
            out.append(Check("Services", "Jobs", "info", f"{n} scheduled"))

    return out


def _probe_mcp(name: str, spec: dict) -> Check:
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
    out_by_name: dict[str, Check] = {}
    with ThreadPoolExecutor(max_workers=min(8, len(servers))) as pool:
        futures = {pool.submit(_probe_mcp, n, s): n for n, s in servers.items()}
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
    return out


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


def _live_pid(home: Path, name: str) -> int | None:
    if name == "gateway":
        from alpi.gateway.run import pid_path
        p = pid_path(home)
    else:
        from alpi.scheduler.run import pid_path
        p = pid_path(home)
    if not p.exists():
        return None
    try:
        pid = int(p.read_text().strip())
        os.kill(pid, 0)
        return pid
    except (ValueError, ProcessLookupError):
        return None
    except PermissionError:
        return pid  # exists but owned by another user


def _sandbox_backend() -> str | None:
    if shutil.which("sandbox-exec"):
        return "sandbox-exec"
    if shutil.which("bwrap"):
        return "bwrap"
    return None
