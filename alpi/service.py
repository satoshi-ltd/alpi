"""Single per-profile service: orchestrator + install.

One process per profile runs every enabled subsystem (gateway,
scheduler, ALP listener) on the same asyncio event loop. The PID,
log, and OS-level service registration (launchd plist on macOS,
systemd-user unit on Linux) all share the single ``service`` name —
no more three-process / three-plist sprawl per profile.

Subsystems are toggled per profile in ``config.yaml``::

    service:
      gateway: true     # Telegram / IMAP / Gmail polling
      schedule: true    # cron jobs
      alp: true         # peer listener (Unix socket + optional TCP)

Default if the section is missing: all three on, since that matches
the previous (split-services) behaviour.

Lifecycle commands live under ``alpi service`` in the CLI:
``start`` (foreground), ``stop`` (signal a running process),
``restart``, ``status`` (PID + uptime + which subsystems are active).
``install`` and ``uninstall`` are reached from the wizard
(``alpi setup → Service``) — they register one plist / unit per
profile that supervises the same ``alpi service start`` command.
"""

from __future__ import annotations

import asyncio
import logging
import os
import platform
import shutil
import signal
import subprocess
import sys
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any


log = logging.getLogger("alpi.service")


# Public — orchestration


def pid_path(home: Path) -> Path:
    return home / "service.pid"


def log_path(home: Path) -> Path:
    return home / "logs" / "service.log"


def running_pid(home: Path) -> int | None:
    """Return the PID of the live service or ``None`` if nothing is
    running. Stale PID files (process gone) are cleaned up on the way."""
    p = pid_path(home)
    if not p.exists():
        return None
    try:
        pid = int(p.read_text().strip())
    except (ValueError, OSError):
        return None
    try:
        os.kill(pid, 0)
    except OSError:
        try:
            p.unlink()
        except OSError:
            pass
        return None
    return pid


def is_running(home: Path) -> bool:
    return running_pid(home) is not None


def enabled_subsystems(home: Path) -> dict[str, bool]:
    """Read which subsystems this profile wants. Missing config →
    everything on (matches pre-refactor default)."""
    from alpi import config as cfg_mod
    cfg = cfg_mod.load(home)
    raw = getattr(cfg, "service", None) or {}
    return {
        "gateway": bool(raw.get("gateway", True)),
        "schedule": bool(raw.get("schedule", True)),
        "alp": bool(raw.get("alp", True)),
    }


def serve(home: Path, profile: str = "default") -> None:
    """Foreground entry point — boots every enabled subsystem on a
    single asyncio loop, writes the PID, sets the process title to
    ``alpi (<profile>)``, and waits until SIGTERM / SIGINT."""
    _configure_logging(home)
    _load_env(home)
    _set_proctitle(profile)
    _write_pid(home)

    subsystems = enabled_subsystems(home)
    log.info(
        "service starting · profile=%s · subsystems=%s",
        profile,
        ",".join(name for name, on in subsystems.items() if on) or "(none)",
    )

    try:
        asyncio.run(_main(home, profile, subsystems))
    except KeyboardInterrupt:
        pass
    finally:
        _clear_pid(home)
        log.info("service stopped · profile=%s", profile)


async def _main(
    home: Path, profile: str, subsystems: dict[str, bool],
) -> None:
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:
            # Windows / restricted env — fall back to KeyboardInterrupt.
            pass

    tasks: list[asyncio.Task] = []
    if subsystems.get("gateway"):
        tasks.append(asyncio.create_task(_run_gateway(home), name="gateway"))
    if subsystems.get("schedule"):
        tasks.append(asyncio.create_task(_run_scheduler(home), name="schedule"))
    if subsystems.get("alp"):
        tasks.append(asyncio.create_task(_run_alp(home, profile), name="alp"))

    if not tasks:
        log.warning("no subsystems enabled — service will idle")
        await stop.wait()
        return

    stop_task = asyncio.create_task(stop.wait(), name="stop-signal")
    done, pending = await asyncio.wait(
        [*tasks, stop_task], return_when=asyncio.FIRST_COMPLETED,
    )
    # If a subsystem crashed we surface it; otherwise the stop signal
    # fired and we tear down everything cleanly.
    for t in tasks:
        if t in done and t.exception() is not None:
            log.exception("subsystem %s crashed", t.get_name(),
                          exc_info=t.exception())
    for t in pending:
        t.cancel()
    await asyncio.gather(*pending, return_exceptions=True)


async def _run_gateway(home: Path) -> None:
    from alpi.gateway.run import serve as gw_serve
    await gw_serve(home)


async def _run_scheduler(home: Path) -> None:
    from alpi.scheduler.run import serve as sch_serve
    await sch_serve(home)


async def _run_alp(home: Path, profile: str) -> None:
    from alpi import config as cfg_mod
    from alpi.alp import handlers as alp_handlers
    from alpi.alp import workgroup as alp_workgroup
    from alpi.alp.server import Server

    cfg = cfg_mod.load(home)
    cfg_alp = cfg.alp or {}
    server = Server(
        home=home,
        agent_name=profile,
        tcp_host=cfg_alp.get("tcp_host"),
        tcp_port=cfg_alp.get("tcp_port"),
    )
    alp_handlers.register_link_ask(server, home)
    alp_workgroup.register(server, home)
    await server.start()
    try:
        await server.serve_forever()
    finally:
        await server.stop()


# Helpers


def _set_proctitle(profile: str) -> None:
    try:
        import setproctitle
        setproctitle.setproctitle(f"alpi ({profile})")
    except Exception:  # noqa: BLE001
        pass


def _configure_logging(home: Path) -> None:
    """Root logger goes to ``service.log``. Add a stderr stream only
    when running interactively (TTY) — under launchd / systemd the
    plist already redirects stderr to the same log file, and a
    second handler would write every line twice."""
    from alpi._log import FORMAT, MAX_BYTES

    p = log_path(home)
    p.parent.mkdir(parents=True, exist_ok=True)
    handlers: list[logging.Handler] = [
        RotatingFileHandler(p, maxBytes=MAX_BYTES, backupCount=0),
    ]
    if sys.stderr.isatty():
        handlers.append(logging.StreamHandler())
    logging.basicConfig(
        level=logging.INFO,
        format=FORMAT,
        handlers=handlers,
        force=True,
    )


def _load_env(home: Path) -> None:
    env_path = home / ".env"
    if env_path.exists():
        from dotenv import load_dotenv
        load_dotenv(env_path, override=False)


def _write_pid(home: Path) -> None:
    p = pid_path(home)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(str(os.getpid()))


def _clear_pid(home: Path) -> None:
    p = pid_path(home)
    if p.exists():
        try:
            p.unlink()
        except OSError:
            pass


# OS-level service install — single per profile


class ServiceError(Exception):
    """Surface install/uninstall failures to the CLI."""


def install(home: Path, profile: str = "default") -> str:
    """Register a per-profile launchd plist (macOS) or systemd-user unit
    (Linux) that supervises ``alpi -p <profile> service start``. Returns
    the backend used."""
    backend = _detect_backend()
    alpi_bin = _locate_alpi()
    if backend == "launchd":
        _launchd_install(home, profile, alpi_bin)
        return "launchd"
    if backend == "systemd":
        _systemd_install(home, profile, alpi_bin)
        return "systemd"
    raise ServiceError(f"unsupported platform: {platform.system()}")


def uninstall(home: Path, profile: str = "default") -> str:
    backend = _detect_backend()
    if backend == "launchd":
        _launchd_uninstall(profile)
        return "launchd"
    if backend == "systemd":
        _systemd_uninstall(profile)
        return "systemd"
    raise ServiceError(f"unsupported platform: {platform.system()}")


def installed(profile: str = "default") -> str | None:
    """Return the backend name if a service unit exists on disk, else None."""
    backend = _detect_backend()
    if backend == "launchd" and _launchd_plist_path(profile).exists():
        return "launchd"
    if backend == "systemd" and _systemd_unit_path(profile).exists():
        return "systemd"
    return None


def label(profile: str) -> str:
    """Public label used in messages + ps output."""
    if _detect_backend() == "launchd":
        return f"com.alpi.service.{profile}"
    return f"alpi-service-{profile}"


def _detect_backend() -> str | None:
    system = platform.system()
    if system == "Darwin":
        return "launchd"
    if system == "Linux":
        return "systemd"
    return None


def _locate_alpi() -> str:
    path = shutil.which("alpi")
    if not path:
        return f"{sys.executable} -m alpi"
    return path


# launchd (macOS)


_PLIST_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>{label}</string>
  <key>ProgramArguments</key>
  <array>
{program_args}
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>ALPI_HOME</key>
    <string>{home}</string>
    <key>PATH</key>
    <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
  </dict>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>{log}</string>
  <key>StandardErrorPath</key>
  <string>{log}</string>
</dict>
</plist>
"""


def _launchd_plist_path(profile: str) -> Path:
    return (
        Path.home() / "Library" / "LaunchAgents"
        / f"com.alpi.service.{profile}.plist"
    )


def _launchd_install(home: Path, profile: str, alpi_bin: str) -> None:
    lbl = f"com.alpi.service.{profile}"
    plist = _launchd_plist_path(profile)
    plist.parent.mkdir(parents=True, exist_ok=True)
    log_p = log_path(home)
    log_p.parent.mkdir(parents=True, exist_ok=True)

    plist.write_text(_PLIST_TEMPLATE.format(
        label=lbl,
        program_args=_program_args_xml(alpi_bin, profile),
        home=str(home),
        log=str(log_p),
    ))

    uid = os.getuid()
    _run(["launchctl", "bootout", f"gui/{uid}", str(plist)], check=False)
    res = _run(["launchctl", "bootstrap", f"gui/{uid}", str(plist)], check=False)
    if res.returncode != 0:
        raise ServiceError(
            f"launchctl bootstrap failed (rc={res.returncode}): "
            f"{(res.stderr or res.stdout).strip()}"
        )


def _launchd_uninstall(profile: str) -> None:
    plist = _launchd_plist_path(profile)
    if not plist.exists():
        raise ServiceError(f"service is not installed (no plist at {plist})")
    uid = os.getuid()
    _run(["launchctl", "bootout", f"gui/{uid}", str(plist)], check=False)
    plist.unlink(missing_ok=True)


# systemd --user (Linux)


_UNIT_TEMPLATE = """[Unit]
Description=alpi service ({profile})
After=network-online.target

[Service]
Type=simple
Environment=ALPI_HOME={home}
ExecStart={exec_start}
Restart=on-failure
RestartSec=5
StandardOutput=append:{log}
StandardError=append:{log}

[Install]
WantedBy=default.target
"""


def _systemd_unit_path(profile: str) -> Path:
    return (
        Path.home() / ".config" / "systemd" / "user"
        / f"alpi-service-{profile}.service"
    )


def _systemd_install(home: Path, profile: str, alpi_bin: str) -> None:
    unit = _systemd_unit_path(profile)
    unit.parent.mkdir(parents=True, exist_ok=True)
    log_p = log_path(home)
    log_p.parent.mkdir(parents=True, exist_ok=True)

    unit.write_text(_UNIT_TEMPLATE.format(
        profile=profile,
        home=str(home),
        exec_start=f"{alpi_bin} -p {profile} service start",
        log=str(log_p),
    ))

    unit_id = f"alpi-service-{profile}.service"
    res = _run(["systemctl", "--user", "daemon-reload"], check=False)
    if res.returncode != 0:
        raise ServiceError(
            f"systemctl daemon-reload failed (rc={res.returncode}): "
            f"{(res.stderr or res.stdout).strip()}{_systemd_hint(res)}"
        )
    res = _run(["systemctl", "--user", "enable", "--now", unit_id], check=False)
    if res.returncode != 0:
        raise ServiceError(
            f"systemctl enable --now failed (rc={res.returncode}): "
            f"{(res.stderr or res.stdout).strip()}{_systemd_hint(res)}"
        )


def _systemd_uninstall(profile: str) -> None:
    unit = _systemd_unit_path(profile)
    if not unit.exists():
        raise ServiceError(f"service is not installed (no unit at {unit})")
    unit_id = f"alpi-service-{profile}.service"
    _run(["systemctl", "--user", "disable", "--now", unit_id], check=False)
    unit.unlink(missing_ok=True)
    _run(["systemctl", "--user", "daemon-reload"], check=False)


def _systemd_hint(result: subprocess.CompletedProcess) -> str:
    combined = (result.stderr or "") + (result.stdout or "")
    if "Failed to connect to bus" in combined or "No such file" in combined:
        return (
            "\nNote: `systemd --user` must be available. On WSL without "
            "`systemd=true` in /etc/wsl.conf, or in minimal containers, "
            "run `alpi service start` in a tmux/screen session instead."
        )
    return ""


def _program_args_xml(alpi_bin: str, profile: str) -> str:
    parts = alpi_bin.split() + ["-p", profile, "service", "start"]
    return "\n".join(f"    <string>{x}</string>" for x in parts)


def _run(cmd: list[str], *, check: bool) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


# Stop / restart helpers used by the CLI


def stop(home: Path, profile: str, *, timeout: float = 5.0) -> bool:
    """Send SIGTERM to the service. Returns True if a process was
    signalled, False if nothing was running."""
    pid = running_pid(home)
    if pid is None:
        return False
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        return False
    deadline = time.time() + timeout
    while time.time() < deadline:
        if running_pid(home) is None:
            return True
        time.sleep(0.1)
    # Last-ditch — SIGKILL if it ignored SIGTERM
    try:
        os.kill(pid, signal.SIGKILL)
    except OSError:
        pass
    return True


def status(home: Path, profile: str) -> dict[str, Any]:
    """Snapshot for ``alpi service status``."""
    pid = running_pid(home)
    info: dict[str, Any] = {
        "profile": profile,
        "pid": pid,
        "running": pid is not None,
        "installed_via": installed(profile),
        "subsystems": enabled_subsystems(home),
    }
    if pid is not None:
        info["uptime_seconds"] = _uptime_seconds(pid)
    return info


def _uptime_seconds(pid: int) -> int | None:
    """Best-effort process uptime via ``ps -o lstart``. Returns None on
    failure — uptime is observability, not load-bearing."""
    try:
        res = subprocess.run(
            ["ps", "-o", "etime=", "-p", str(pid)],
            capture_output=True, text=True, check=False, timeout=2,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    out = res.stdout.strip()
    if not out:
        return None
    return _parse_etime(out)


def _parse_etime(s: str) -> int | None:
    """Parse `ps -o etime` output like ``[[dd-]hh:]mm:ss``."""
    days = 0
    if "-" in s:
        d, _, s = s.partition("-")
        try:
            days = int(d)
        except ValueError:
            return None
    parts = [p for p in s.split(":") if p]
    try:
        nums = [int(p) for p in parts]
    except ValueError:
        return None
    if len(nums) == 2:
        h, m, sec = 0, nums[0], nums[1]
    elif len(nums) == 3:
        h, m, sec = nums
    else:
        return None
    return days * 86400 + h * 3600 + m * 60 + sec
