from __future__ import annotations

import dataclasses
import os
from pathlib import Path

from alpi import config as cfg_mod
from alpi.doctor import _GLYPH, Check, exit_code

__all__ = ["run_all", "render", "exit_code"]


def run_all(root: Path, *, offline: bool = False) -> list[Check]:
    from alpi import home as home_mod

    out: list[Check] = []
    out.extend(_audit_dependencies(offline))
    for profile in home_mod.list_profiles(root):
        home = root if profile == "default" else root / "profiles" / profile
        cfg = cfg_mod.load(home)
        per_profile = (
            _audit_permissions(home)
            + _audit_network(cfg)
            + _audit_hardening(cfg)
        )
        for c in per_profile:
            out.append(dataclasses.replace(c, group=f"@{profile} · {c.group}"))
    return out


def _installed_packages() -> list[tuple[str, str]]:
    from importlib.metadata import distributions

    seen: dict[str, str] = {}
    for dist in distributions():
        name = (dist.metadata.get("Name") or "").strip()
        version = (dist.version or "").strip()
        if name and version:
            seen.setdefault(name.lower(), version)
    return sorted(seen.items())


def _audit_dependencies(offline: bool) -> list[Check]:
    if offline:
        return [Check("Dependencies", "CVEs", "info",
                      "skipped — offline mode (drop --offline to query OSV)")]
    from alpi.tools import _osv

    packages = _installed_packages()
    hits = _osv.check_versions("PyPI", packages)
    if hits is None:
        return [Check("Dependencies", "CVEs", "info",
                      "skipped — OSV unreachable (no network?)")]
    if not hits:
        return [Check("Dependencies", "CVEs", "ok",
                      f"{len(packages)} packages, no known advisories")]
    out: list[Check] = []
    for name, ids in sorted(hits.items()):
        shown = ", ".join(ids[:3]) + ("…" if len(ids) > 3 else "")
        out.append(Check("Dependencies", name, "warn",
                         f"{shown} — osv.dev"))
    return out


def _audit_permissions(home: Path) -> list[Check]:
    if os.name != "posix":
        return [Check("Permissions", "mode bits", "info",
                      "skipped — no POSIX file modes on this platform")]
    from alpi.alp import keys as keys_mod
    from alpi.alp import peers as peers_mod

    secrets_dir = keys_mod.private_path(home).parent
    targets = [
        (home / ".env", ".env", "fail"),
        (keys_mod.private_path(home), "ALP private key", "fail"),
        (secrets_dir, "secrets/", "fail"),
        (home / "config.yaml", "config.yaml", "warn"),
        (peers_mod.path(home), "peers.yaml", "warn"),
    ]
    out: list[Check] = []
    for path, label, severity in targets:
        try:
            if not path.exists():
                continue
            loose = os.stat(path).st_mode & 0o077
        except OSError:
            continue
        if loose:
            want = "700" if path.is_dir() else "600"
            out.append(Check("Permissions", label, severity,
                             f"group/other bits {oct(loose)[2:]} set — chmod {want}"))
    if not out:
        out.append(Check("Permissions", "secrets", "ok",
                         "no group/other access to secret files"))
    return out


def _audit_network(cfg: cfg_mod.Config) -> list[Check]:
    from alpi.doctor import _check_network_exposure

    checks = _check_network_exposure(cfg)
    if not checks:
        return [Check("Network", "bind", "ok", "no public TCP bind")]
    return [dataclasses.replace(c, group="Network") for c in checks]


def _audit_hardening(cfg: cfg_mod.Config) -> list[Check]:
    out: list[Check] = []

    if cfg.tools.terminal.sandbox:
        out.append(Check("Hardening", "terminal sandbox", "ok", "on"))
    else:
        out.append(Check("Hardening", "terminal sandbox", "warn",
                         "off — shell commands run unconfined on this host"))

    if cfg.runtime.first_byte_timeout_s == 0 or cfg.runtime.stream_idle_timeout_s == 0:
        out.append(Check("Hardening", "LLM watchdog", "warn",
                         "stale-call timeout disabled (0) — a hung provider can stall a turn"))
    else:
        out.append(Check("Hardening", "LLM watchdog", "ok",
                         f"first-byte {cfg.runtime.first_byte_timeout_s:g}s · "
                         f"idle {cfg.runtime.stream_idle_timeout_s:g}s"))

    cap = (cfg.budget or {}).get("daily_usd")
    if cap:
        out.append(Check("Hardening", "budget", "ok", f"daily cap ${cap}"))
    else:
        out.append(Check("Hardening", "budget", "info",
                         "no daily USD cap — unattended runs spend without bound"))

    return out


def render(console, checks: list[Check], version: str) -> None:
    from rich.text import Text

    console.print(f"[b]alpi[/b] {version} · security audit")
    console.print("")
    current_group = ""
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
        console.print(f"[yellow]{warns} warning{'s' if warns != 1 else ''}[/yellow]")
    else:
        console.print("[green]no issues found[/green]")
