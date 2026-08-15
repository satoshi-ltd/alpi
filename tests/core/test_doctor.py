"""Health checks with live primitives stubbed out in tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from alpi import cli, doctor


@pytest.fixture(autouse=True)
def _no_live_network(monkeypatch):
    """Default stubs; tests override them when needed."""
    monkeypatch.setattr(doctor, "_check_email_live", lambda home: [])
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


def test_unknown_tools_deny_name_fails(tmp_path: Path) -> None:
    _write_cfg(tmp_path, workspace=str(tmp_path))
    (tmp_path / "config.yaml").write_text(
        "model: openrouter/foo/bar\n"
        f"workspace: {tmp_path}\n"
        "tools:\n  deny: [termnal]\n"
    )

    checks = doctor.run_all(tmp_path, "default")

    row = next(c for c in checks if c.group == "Tools" and c.name == "denylist")
    assert row.status == "fail"
    assert "termnal" in row.detail


def test_invalid_skill_frontmatter_fails(tmp_path: Path) -> None:
    _write_cfg(tmp_path, workspace=str(tmp_path))
    skill = tmp_path / "skills" / "meta" / "bad-skill"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        "---\nname: bad-skill\ndescription: Bad skill\ncategory: made-up\n"
        "version: 1.0.0\norigin: user\n---\nBody\n"
    )

    checks = doctor.run_all(tmp_path, "default")

    row = next(c for c in checks if c.group == "Skills" and c.name == "meta/bad-skill")
    assert row.status == "fail"
    assert "category" in row.detail


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
    """A broken IMAP login should surface as a fail check."""
    _write_cfg(tmp_path, workspace=str(tmp_path))
    _write_env(tmp_path, OPENROUTER_API_KEY="x")
    monkeypatch.setattr(
        doctor, "_check_email_live",
        lambda home: [doctor.Check("Email", "me@x.com", "fail", "login/SMTP failed: 535 auth")],
    )
    checks = doctor.run_all(tmp_path, "default")
    row = next(c for c in checks if c.name == "me@x.com")
    assert row.status == "fail"
    assert "535" in row.detail
    assert doctor.exit_code(checks) == 1


def test_email_live_emits_one_check_per_account(tmp_path: Path, monkeypatch) -> None:
    _write_cfg(tmp_path, workspace=str(tmp_path))
    _write_env(tmp_path, OPENROUTER_API_KEY="x")
    from alpi.mail import accounts as accounts_mod
    accounts_mod.add_imap(
        tmp_path, address="a@x.com", password="pw",
        imap_host="imap.x.com", smtp_host="smtp.x.com",
    )
    accounts_mod.add_gmail(tmp_path, address="b@gmail.com")

    captured: dict = {}

    def fake_test(self):
        captured["imap_tested"] = True

    monkeypatch.setattr("alpi.mail.imap.ImapClient.test", fake_test)

    rows = [
        doctor._check_account_live(tmp_path, r)
        for r in accounts_mod.list_accounts(tmp_path)
    ]
    by_name = {c.name: c for c in rows}
    assert by_name["a@x.com"].status == "ok"
    assert captured.get("imap_tested") is True
    # Gmail account has no token → not authorized (info, not a failure).
    assert by_name["b@gmail.com"].status == "info"


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


def _cfg_with_network(home: Path, host: str, *, allow_public: bool = False):
    from alpi import config as cfg_mod
    cfg = cfg_mod.Config(home=home, model="")
    cfg.network = {"host": host}
    if allow_public:
        cfg.host = {"allow_public_bind": True}
    return cfg


def test_network_exposure_warns_on_public_with_optin(tmp_path: Path) -> None:
    checks = doctor._check_network_exposure(_cfg_with_network(tmp_path, "8.8.8.8", allow_public=True))
    assert [c.status for c in checks] == ["warn"]
    assert "public" in checks[0].detail


def test_network_exposure_warns_on_hostname(tmp_path: Path) -> None:
    checks = doctor._check_network_exposure(_cfg_with_network(tmp_path, "home-server.internal"))
    assert [c.status for c in checks] == ["warn"]
    assert "all interfaces" in checks[0].detail


def test_network_exposure_silent_on_private_ip(tmp_path: Path) -> None:
    assert doctor._check_network_exposure(_cfg_with_network(tmp_path, "192.168.1.5")) == []


def test_network_exposure_warns_that_docker_publish_state_is_external(
    tmp_path: Path, monkeypatch,
) -> None:
    monkeypatch.setenv("ALPI_PLATFORM", "docker")

    checks = doctor._check_network_exposure(
        _cfg_with_network(tmp_path, "client.example.com"),
    )

    assert [c.status for c in checks] == ["warn"]
    assert "docker compose config" in checks[0].detail


def test_security_warns_about_ignored_legacy_service_switches(
    tmp_path: Path, monkeypatch,
) -> None:
    from alpi import config as cfg_mod

    monkeypatch.delenv("ALPI_PLATFORM", raising=False)
    (tmp_path / "config.yaml").write_text(
        "model: x\nservice:\n  alp: false\n  schedule: false\n"
    )

    checks = doctor._check_security(cfg_mod.load(tmp_path))

    warning = next(c for c in checks if c.name == "Removed service switches")
    assert warning.status == "warn"
    assert "service.alp" in warning.detail
    assert "all daemon capabilities start" in warning.detail


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


def test_doctor_reports_docker_managed_daemon(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ALPI_PLATFORM", "docker")
    _write_cfg(tmp_path, workspace=str(tmp_path))
    _write_env(tmp_path, OPENROUTER_API_KEY="x")
    from alpi import service
    monkeypatch.setattr(service, "daemon_installed", lambda: False)
    monkeypatch.setattr(service, "daemon_running_pid", lambda root: 4321)

    checks = doctor.run_all(tmp_path, "default")
    daemon = next(c for c in checks if c.group == "Services" and c.name == "Daemon")
    assert daemon.status == "ok"
    assert daemon.detail == "managed by Docker (pid 4321)"


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


def test_storage_check_silent_when_under_thresholds(tmp_path: Path, monkeypatch) -> None:
    _write_cfg(tmp_path, workspace=str(tmp_path))
    _write_env(tmp_path, OPENROUTER_API_KEY="x")
    from alpi import service
    monkeypatch.setattr(service, "daemon_installed", lambda: False)
    monkeypatch.setattr(service, "daemon_running_pid", lambda root: None)

    (tmp_path / "cache" / "tts").mkdir(parents=True)
    (tmp_path / "cache" / "tts" / "tiny.mp3").write_bytes(b"x" * 1024)

    checks = doctor.run_all(tmp_path, "default")
    storage_rows = [c for c in checks if c.group == "Storage"]
    assert storage_rows == []


def test_storage_check_warns_when_tts_cache_outsized(
    tmp_path: Path, monkeypatch,
) -> None:
    _write_cfg(tmp_path, workspace=str(tmp_path))
    _write_env(tmp_path, OPENROUTER_API_KEY="x")
    from alpi import service
    monkeypatch.setattr(service, "daemon_installed", lambda: False)
    monkeypatch.setattr(service, "daemon_running_pid", lambda root: None)
    monkeypatch.setattr(
        doctor, "_STORAGE_THRESHOLDS",
        {"tts": ("TTS cache", "cache/tts", 1024)},
    )

    cache = tmp_path / "cache" / "tts"
    cache.mkdir(parents=True)
    (cache / "fat.mp3").write_bytes(b"x" * 4096)

    checks = doctor.run_all(tmp_path, "default")
    row = next(c for c in checks if c.group == "Storage" and c.name == "TTS cache")
    assert row.status == "warn"
    assert "Cleanup" in row.detail


def test_storage_check_points_sessions_at_desktop(
    tmp_path: Path, monkeypatch,
) -> None:
    _write_cfg(tmp_path, workspace=str(tmp_path))
    _write_env(tmp_path, OPENROUTER_API_KEY="x")
    from alpi import service
    monkeypatch.setattr(service, "daemon_installed", lambda: False)
    monkeypatch.setattr(service, "daemon_running_pid", lambda root: None)
    monkeypatch.setattr(
        doctor, "_STORAGE_THRESHOLDS",
        {"sessions": ("Sessions", "sessions", 1024)},
    )

    sess = tmp_path / "sessions"
    sess.mkdir()
    (sess / "huge.json").write_bytes(b"x" * 8192)

    checks = doctor.run_all(tmp_path, "default")
    row = next(c for c in checks if c.group == "Storage" and c.name == "Sessions")
    assert row.status == "warn"
    assert "Manage Sessions" in row.detail


def _alp_checks(home: Path):
    from alpi import config as cfg_mod
    return doctor._check_alp_integrity(home, cfg_mod.load(home))


def _add_peer(home: Path, peer_id: str, pubkey: str, address: str | None = None) -> None:
    from alpi.alp import peers as peers_mod
    peers_mod.add(home, peers_mod.Peer(id=peer_id, pubkey=pubkey, address=address))


def test_alp_integrity_flags_own_pubkey_in_peers(tmp_path: Path) -> None:
    from alpi.alp.keys import load_or_generate
    _write_cfg(tmp_path)
    own = load_or_generate(tmp_path).pubkey_b64()
    _add_peer(tmp_path, "clone", own, "10.0.0.9:7423")
    checks = _alp_checks(tmp_path)
    assert any(c.status == "fail" and "cloned" in c.detail for c in checks)


def test_alp_integrity_flags_duplicate_peer_pubkeys(tmp_path: Path) -> None:
    _write_cfg(tmp_path)
    # peers.add() dedupes by pubkey, so the corrupt state only exists in hand-copied or volume-cloned peers.yaml files — write it raw.
    (tmp_path / "alp").mkdir(parents=True, exist_ok=True)
    (tmp_path / "alp" / "peers.yaml").write_text(
        "- id: machine-a\n  pubkey: PKSAME\n  address: 10.0.0.1:7423\n"
        "- id: machine-b\n  pubkey: PKSAME\n  address: 10.0.0.2:7423\n"
    )
    checks = _alp_checks(tmp_path)
    assert any(
        c.status == "fail" and "machine-a" in c.detail and "machine-b" in c.detail
        for c in checks
    )


def test_alp_integrity_warns_on_shared_address(tmp_path: Path) -> None:
    _write_cfg(tmp_path)
    _add_peer(tmp_path, "a", "PK1", "10.0.0.1:7423")
    _add_peer(tmp_path, "b", "PK2", "10.0.0.1:7423")
    checks = _alp_checks(tmp_path)
    assert any(c.status == "warn" and "10.0.0.1:7423" in c.detail for c in checks)


def test_alp_integrity_warns_when_docker_has_no_advertised_host(
    tmp_path: Path, monkeypatch,
) -> None:
    _write_cfg(tmp_path)
    monkeypatch.setenv("ALPI_PLATFORM", "docker")
    monkeypatch.delenv("ALPI_NETWORK_HOST", raising=False)
    checks = _alp_checks(tmp_path)
    assert any(c.status == "warn" and "ALPI_NETWORK_HOST" in c.detail for c in checks)


def test_alp_integrity_ok_on_distinct_identities(tmp_path: Path, monkeypatch) -> None:
    _write_cfg(tmp_path)
    monkeypatch.delenv("ALPI_PLATFORM", raising=False)
    _add_peer(tmp_path, "a", "PK1", "10.0.0.1:7423")
    _add_peer(tmp_path, "b", "PK2", "10.0.0.2:7423")
    checks = _alp_checks(tmp_path)
    assert checks == [c for c in checks if c.status == "ok"]
    assert any("2 peer(s)" in c.detail for c in checks)


def test_assets_check_reports_missing_chromium_and_stale_builds(
    tmp_path: Path, monkeypatch,
) -> None:
    from alpi.core import _playwright

    _write_cfg(tmp_path)
    monkeypatch.delenv("ALPI_PLATFORM", raising=False)
    cache = tmp_path / "ms-playwright"
    (cache / "chromium-1100").mkdir(parents=True)
    monkeypatch.setattr(_playwright, "_wanted_chromium_dirs", lambda: {"chromium-1217"})
    monkeypatch.setattr(_playwright, "_browsers_cache_dir", lambda: cache)
    checks = doctor._check_assets(tmp_path)
    assert any(c.name == "chromium" and c.status == "info" for c in checks)
    assert any(c.status == "warn" and "chromium-1100" in c.detail for c in checks)
    assert any(c.name == "prefetch" for c in checks)


@pytest.mark.parametrize("payload", ["{broken", "[]"])
def test_services_check_warns_on_runs_json_the_scheduler_rejects(tmp_path: Path, payload: str) -> None:
    sched = tmp_path / "schedule"
    sched.mkdir(parents=True)
    (sched / "jobs.json").write_text('[{"id": "a", "kind": "cron", "expression": "* * * * *", "prompt": "x"}]')
    (sched / "runs.json").write_text(payload)
    checks = doctor._check_services(tmp_path, "default")
    hit = [c for c in checks if c.name == "Job runs"]
    assert hit and hit[0].status == "warn"
    assert "runs.json" in hit[0].detail and "no job fires" in hit[0].detail
