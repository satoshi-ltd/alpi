"""Health check module — live checks with short timeouts.

Tests monkeypatch the live primitives so the suite stays offline and
deterministic. The primitives themselves (``urllib`` call, ``ImapClient.test()``,
``gmail_auth.get_access_token``, ``MCPClient.start``) are tested in
their own modules.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from alpi import cli, doctor


@pytest.fixture(autouse=True)
def _no_live_network(monkeypatch):
    """Default stubs — individual tests override when they want an outcome."""
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
    # Services not installed → info/warn, not fail
    from alpi import service
    monkeypatch.setattr(service, "installed", lambda *a, **kw: None)

    checks = doctor.run_all(tmp_path, "default")
    statuses = {(c.group, c.name): c.status for c in checks}

    assert statuses[("Model", "configured")] == "ok"
    assert statuses[("Model", "API key")] == "ok"
    assert statuses[("Workspace", "ready")] == "ok"
    # Schedule is warned (not installed but expected) — doesn't fail.
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
    # Scrub real env vars that would otherwise rescue the check.
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
    """A broken Telegram token should produce a fail check in the aggregated output."""
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
    monkeypatch.setattr(service, "installed", lambda *a, **kw: None)
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
    # Pretend no backend on PATH.
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
    monkeypatch.setattr(service, "installed", lambda *a, **kw: None)
    result = CliRunner().invoke(cli.main, ["doctor"])
    assert result.exit_code == 0
