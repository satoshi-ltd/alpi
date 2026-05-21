"""Health checks with live primitives stubbed out in tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from alpi import cli, doctor


@pytest.fixture(autouse=True)
def _no_live_network(monkeypatch):
    """Default stubs; tests override them when needed."""
    monkeypatch.setattr(doctor, "_check_telegram_live", lambda env: [])
    monkeypatch.setattr(doctor, "_check_imap_live", lambda env: [])
    monkeypatch.setattr(doctor, "_check_gmail_live", lambda home, env: [])
    monkeypatch.setattr(doctor, "_check_mcps_live", lambda cfg: [])


def _write_cfg(home: Path, model: str = "openrouter/foo/bar", workspace: str | None = None) -> None:
    text = f"model: {model}\n"
    if workspace:
        text += f"workspace: {workspace}\n"
    (home / "config.yaml").write_text(text)


def _write_env(home: Path, **vars: str) -> None:
    (home / ".env").write_text("\n".join(f"{k}={v}" for k, v in vars.items()))


def test_all_green_on_clean_profile(tmp_path: Path, monkeypatch) -> None:
    _write_cfg(tmp_path, workspace=str(tmp_path))
    _write_env(tmp_path, OPENROUTER_API_KEY="sk-fake")
    # Services absent should not fail the check.
    from alpi import service
    monkeypatch.setattr(service, "daemon_installed", lambda: False)
    monkeypatch.setattr(service, "daemon_running_pid", lambda root: None)

    checks = doctor.run_all(tmp_path, "default")
    statuses = {(c.group, c.name): c.status for c in checks}

    assert statuses[("Model", "configured")] == "ok"
    assert statuses[("Model", "API key")] == "ok"
    assert statuses[("Workspace", "ready")] == "ok"
    # Absent schedule remains a warning.
    assert doctor.exit_code(checks) == 0


def test_missing_model_fails(tmp_path: Path) -> None:
    (tmp_path / "config.yaml").write_text("model: \n")
    checks = doctor.run_all(tmp_path, "default")
    model_status = next(c for c in checks if c.name == "configured" and c.group == "Model")
    assert model_status.status == "fail"
    assert doctor.exit_code(checks) == 1


def test_missing_api_key_fails(tmp_path: Path) -> None:
    _write_cfg(tmp_path)
    _write_env(tmp_path)  # no key set
    # Clear real env vars that would otherwise rescue the check.
    import os
    for v in ("OPENROUTER_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        os.environ.pop(v, None)
    checks = doctor.run_all(tmp_path, "default")
    key_check = next(c for c in checks if c.name == "API key" and c.group == "Model")
    assert key_check.status == "fail"


def test_workspace_missing_dir_fails(tmp_path: Path) -> None:
    _write_cfg(tmp_path, workspace=str(tmp_path / "does-not-exist"))
    _write_env(tmp_path, OPENROUTER_API_KEY="sk-fake")
    checks = doctor.run_all(tmp_path, "default")
    ws = next(c for c in checks if c.group == "Workspace")
    assert ws.status == "fail"
    assert "missing" in ws.detail


def test_live_failure_surfaces_in_output(tmp_path: Path, monkeypatch) -> None:
    """A broken Telegram token should surface as a fail check."""
    _write_cfg(tmp_path, workspace=str(tmp_path))
    _write_env(tmp_path, OPENROUTER_API_KEY="x")
    monkeypatch.setattr(
        doctor, "_check_telegram_live",
        lambda env: [doctor.Check("Gateways", "Telegram", "fail", "getMe: 401 Unauthorized")],
    )
    checks = doctor.run_all(tmp_path, "default")
    tg = next(c for c in checks if c.name == "Telegram")
    assert tg.status == "fail"
    assert "401" in tg.detail
    assert doctor.exit_code(checks) == 1


def test_live_ok_keeps_exit_zero(tmp_path: Path, monkeypatch) -> None:
    _write_cfg(tmp_path, workspace=str(tmp_path))
    _write_env(tmp_path, OPENROUTER_API_KEY="x")
    monkeypatch.setattr(
        doctor, "_check_mcps_live",
        lambda cfg: [doctor.Check("MCPs", "github", "ok", "47 tools")],
    )
    from alpi import service
    monkeypatch.setattr(service, "daemon_installed", lambda: False)
    monkeypatch.setattr(service, "daemon_running_pid", lambda root: None)
    checks = doctor.run_all(tmp_path, "default")
    assert doctor.exit_code(checks) == 0


def test_sandbox_enabled_without_backend_fails(tmp_path: Path, monkeypatch) -> None:
    _write_cfg(tmp_path, workspace=str(tmp_path))
    _write_env(tmp_path, OPENROUTER_API_KEY="x")
    (tmp_path / "config.yaml").write_text(
        "model: openrouter/foo/bar\n"
        f"workspace: {tmp_path}\n"
        "tools:\n  terminal:\n    sandbox: true\n"
    )
    # Pretend no backend is on PATH.
    import shutil as sh
    monkeypatch.setattr(sh, "which", lambda x: None)
    checks = doctor.run_all(tmp_path, "default")
    sb = next(c for c in checks if c.name == "Sandbox")
    assert sb.status == "fail"


def test_cli_doctor_command_exits_nonzero_on_fail(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ALPI_HOME", str(tmp_path))
    (tmp_path / "config.yaml").write_text("model: \n")
    result = CliRunner().invoke(cli.main, ["doctor"])
    assert result.exit_code == 1
    assert "failure" in result.output or "fail" in result.output.lower()


def test_cli_doctor_command_exits_zero_when_healthy(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ALPI_HOME", str(tmp_path))
    _write_cfg(tmp_path, workspace=str(tmp_path))
    _write_env(tmp_path, OPENROUTER_API_KEY="x")
    from alpi import service
    monkeypatch.setattr(service, "daemon_installed", lambda: False)
    monkeypatch.setattr(service, "daemon_running_pid", lambda root: None)
    result = CliRunner().invoke(cli.main, ["doctor"])
    assert result.exit_code == 0


def test_doctor_reports_umbrel_managed_daemon(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ALPI_PLATFORM", "umbrel")
    _write_cfg(tmp_path, workspace=str(tmp_path))
    _write_env(tmp_path, OPENROUTER_API_KEY="x")
    from alpi import service
    monkeypatch.setattr(service, "daemon_installed", lambda: False)
    monkeypatch.setattr(service, "daemon_running_pid", lambda root: 4321)

    checks = doctor.run_all(tmp_path, "default")
    daemon = next(c for c in checks if c.group == "Services" and c.name == "Daemon")
    assert daemon.status == "ok"
    assert daemon.detail == "managed by Umbrel (pid 4321)"


def test_doctor_tools_group_summary_when_all_available(
    tmp_path: Path, monkeypatch,
) -> None:
    """TL.1 — when every tool reports available, doctor emits a single
    summary row under Tools (one row, status ok). Doctor stays scannable
    instead of listing 25+ tools individually."""
    _write_cfg(tmp_path, workspace=str(tmp_path))
    _write_env(tmp_path, OPENROUTER_API_KEY="x")
    from alpi import service, tools as tools_mod
    monkeypatch.setattr(service, "daemon_installed", lambda: False)
    monkeypatch.setattr(service, "daemon_running_pid", lambda root: None)
    monkeypatch.setattr(
        tools_mod, "availability_report",
        lambda: [("read_file", True, ""), ("memory", True, "")],
    )

    checks = doctor.run_all(tmp_path, "default")
    tools_checks = [c for c in checks if c.group == "Tools"]
    assert len(tools_checks) == 1
    assert tools_checks[0].name == "registry"
    assert tools_checks[0].status == "ok"
    assert "2 tools available" in tools_checks[0].detail


def test_doctor_tools_group_warns_on_unavailable(
    tmp_path: Path, monkeypatch,
) -> None:
    """When a tool is unavailable, doctor emits one warn row per unavailable
    tool plus an info row summarising the rest. exit_code stays 0 (warns are
    not fails) so cron and CI don't break on a partial install."""
    _write_cfg(tmp_path, workspace=str(tmp_path))
    _write_env(tmp_path, OPENROUTER_API_KEY="x")
    from alpi import service, tools as tools_mod
    monkeypatch.setattr(service, "daemon_installed", lambda: False)
    monkeypatch.setattr(service, "daemon_running_pid", lambda root: None)
    monkeypatch.setattr(
        tools_mod, "availability_report",
        lambda: [
            ("read_file", True, ""),
            ("browser",   False, "playwright not installed"),
            ("stt",       False, "faster-whisper not installed"),
        ],
    )

    checks = doctor.run_all(tmp_path, "default")
    tools_checks = [c for c in checks if c.group == "Tools"]
    statuses = {(c.name, c.status, c.detail) for c in tools_checks}
    assert ("browser", "warn", "playwright not installed") in statuses
    assert ("stt", "warn", "faster-whisper not installed") in statuses
    assert any(
        c.name == "registry" and c.status == "info" and "1 other" in c.detail
        for c in tools_checks
    )
    assert doctor.exit_code(checks) == 0


def test_doctor_skills_info_when_no_telemetry(tmp_path: Path, monkeypatch) -> None:
    """Fresh profile with no recorded skill usage gets an info row, not a
    fail — the absence of data is normal for a just-installed alpi."""
    _write_cfg(tmp_path, workspace=str(tmp_path))
    _write_env(tmp_path, OPENROUTER_API_KEY="x")
    from alpi import service
    monkeypatch.setattr(service, "daemon_installed", lambda: False)
    monkeypatch.setattr(service, "daemon_running_pid", lambda root: None)

    checks = doctor.run_all(tmp_path, "default")
    skills_checks = [c for c in checks if c.group == "Skills"]
    assert len(skills_checks) == 1
    assert skills_checks[0].status == "info"
    assert "no usage recorded" in skills_checks[0].detail


def test_doctor_skills_summary_when_telemetry_present(
    tmp_path: Path, monkeypatch,
) -> None:
    """A profile with mixed-state skills gets one ok summary line with the
    by-state counts. ``time.time`` is pinned so the active/stale/archived
    cutoffs land predictably regardless of when CI runs the suite."""
    _write_cfg(tmp_path, workspace=str(tmp_path))
    _write_env(tmp_path, OPENROUTER_API_KEY="x")
    from alpi import service, skills_usage as su
    monkeypatch.setattr(service, "daemon_installed", lambda: False)
    monkeypatch.setattr(service, "daemon_running_pid", lambda root: None)

    now = 1_700_000_000.0
    day = 86400.0
    monkeypatch.setattr(su.time, "time", lambda: now)
    su.record_usage(tmp_path, "fresh", "view", now=now - 1 * day)
    su.record_usage(tmp_path, "ageing", "view", now=now - 45 * day)
    su.record_usage(tmp_path, "ancient", "view", now=now - 200 * day)

    checks = doctor.run_all(tmp_path, "default")
    skills_checks = [c for c in checks if c.group == "Skills"]
    summary = next((c for c in skills_checks if c.name == "telemetry"), None)
    assert summary is not None
    assert summary.status == "ok"
    assert "3 tracked" in summary.detail
    assert "1 active" in summary.detail
    assert "1 stale" in summary.detail
    assert "1 archived" in summary.detail


def test_doctor_skills_warns_on_pinned_but_cold(tmp_path: Path, monkeypatch) -> None:
    """The interesting curation signal: a skill the user explicitly pinned
    but hasn't touched in months. Surfaces as a per-skill warn so the
    operator sees it without scanning every entry by hand."""
    _write_cfg(tmp_path, workspace=str(tmp_path))
    _write_env(tmp_path, OPENROUTER_API_KEY="x")
    from alpi import service, skills_usage as su
    monkeypatch.setattr(service, "daemon_installed", lambda: False)
    monkeypatch.setattr(service, "daemon_running_pid", lambda root: None)

    now = 1_700_000_000.0
    monkeypatch.setattr(su.time, "time", lambda: now)
    su.record_usage(tmp_path, "cold-pinned", "view",
                    pinned=True, now=now - 120 * 86400.0)

    checks = doctor.run_all(tmp_path, "default")
    skills_checks = [c for c in checks if c.group == "Skills"]
    warn = next((c for c in skills_checks if c.status == "warn"), None)
    assert warn is not None
    assert warn.name == "cold-pinned"
    assert "pinned but" in warn.detail


def test_doctor_silent_when_all_gateways_healthy(tmp_path: Path, monkeypatch) -> None:
    """No breaker file → no platform has ever failed → no rows under
    Gateways from the breaker section. Doctor stays scannable on the
    happy path."""
    _write_cfg(tmp_path, workspace=str(tmp_path))
    _write_env(tmp_path, OPENROUTER_API_KEY="x")
    from alpi import service
    monkeypatch.setattr(service, "daemon_installed", lambda: False)
    monkeypatch.setattr(service, "daemon_running_pid", lambda root: None)

    checks = doctor.run_all(tmp_path, "default")
    gw_breaker_rows = [
        c for c in checks
        if c.group == "Gateways" and c.name in ("telegram", "imap", "gmail", "matrix")
    ]
    assert gw_breaker_rows == []


def test_doctor_warns_on_disabled_gateway(tmp_path: Path, monkeypatch) -> None:
    """A platform locked out by the breaker shows up as a warn row with
    cooldown + last error. exit_code stays 0 (warn != fail) so a broken
    upstream doesn't break operator scripts."""
    _write_cfg(tmp_path, workspace=str(tmp_path))
    _write_env(tmp_path, OPENROUTER_API_KEY="x")
    from alpi import service
    from alpi.gateway import breaker as br
    monkeypatch.setattr(service, "daemon_installed", lambda: False)
    monkeypatch.setattr(service, "daemon_running_pid", lambda root: None)

    store = br.BreakerStore(tmp_path)
    for _ in range(br.FAILURE_THRESHOLD):
        store.record_failure("telegram", "401 Unauthorized", now=1000.0)
    br._singletons.clear()

    checks = doctor.run_all(tmp_path, "default")
    tg = next(
        (c for c in checks if c.group == "Gateways" and c.name == "telegram"),
        None,
    )
    assert tg is not None
    assert tg.status == "warn"
    assert "disabled" in tg.detail
    assert "401" in tg.detail
    assert doctor.exit_code(checks) == 0


def test_doctor_warns_on_degraded_gateway(tmp_path: Path, monkeypatch) -> None:
    _write_cfg(tmp_path, workspace=str(tmp_path))
    _write_env(tmp_path, OPENROUTER_API_KEY="x")
    from alpi import service
    from alpi.gateway import breaker as br
    monkeypatch.setattr(service, "daemon_installed", lambda: False)
    monkeypatch.setattr(service, "daemon_running_pid", lambda root: None)

    store = br.BreakerStore(tmp_path)
    store.record_failure("imap", "timeout", now=1000.0)
    store.record_failure("imap", "timeout", now=1001.0)
    br._singletons.clear()

    checks = doctor.run_all(tmp_path, "default")
    row = next(
        (c for c in checks if c.group == "Gateways" and c.name == "imap"),
        None,
    )
    assert row is not None
    assert row.status == "warn"
    assert "2 consecutive failures" in row.detail
    assert "timeout" in row.detail
