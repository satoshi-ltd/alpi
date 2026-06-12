from __future__ import annotations

import os

import pytest

from alpi import audit
from alpi import config as cfg_mod

posix_only = pytest.mark.skipif(os.name != "posix", reason="POSIX mode bits only")


@posix_only
def test_permissions_flag_world_readable_env(tmp_path):
    env = tmp_path / ".env"
    env.write_text("KEY=secret")
    env.chmod(0o644)
    checks = audit._audit_permissions(tmp_path)
    hit = [c for c in checks if c.name == ".env"]
    assert hit and hit[0].status == "fail"


@posix_only
def test_permissions_ok_when_tight(tmp_path):
    env = tmp_path / ".env"
    env.write_text("KEY=secret")
    env.chmod(0o600)
    checks = audit._audit_permissions(tmp_path)
    assert [c.status for c in checks] == ["ok"]


@posix_only
def test_permissions_config_yaml_is_warn_not_fail(tmp_path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text("model: x")
    cfg.chmod(0o644)
    checks = audit._audit_permissions(tmp_path)
    hit = [c for c in checks if c.name == "config.yaml"]
    assert hit and hit[0].status == "warn"


def test_hardening_flags_sandbox_off_and_uncapped_budget(tmp_path):
    cfg = cfg_mod.load(tmp_path)
    cfg.tools.terminal.sandbox = False
    cfg.budget = {}
    checks = audit._audit_hardening(cfg)
    by = {c.name: c for c in checks}
    assert by["terminal sandbox"].status == "warn"
    assert by["budget"].status == "info"


def test_hardening_clean_config(tmp_path):
    cfg = cfg_mod.load(tmp_path)
    cfg.tools.terminal.sandbox = True
    cfg.budget = {"daily_usd": 5}
    checks = audit._audit_hardening(cfg)
    by = {c.name: c for c in checks}
    assert by["terminal sandbox"].status == "ok"
    assert by["budget"].status == "ok"


def test_hardening_flags_disabled_watchdog(tmp_path):
    cfg = cfg_mod.load(tmp_path)
    cfg.runtime.first_byte_timeout_s = 0
    checks = audit._audit_hardening(cfg)
    hit = [c for c in checks if c.name == "LLM watchdog"]
    assert hit and hit[0].status == "warn"


def test_network_ok_without_public_bind(tmp_path):
    cfg = cfg_mod.load(tmp_path)
    checks = audit._audit_network(cfg)
    assert checks and all(c.group == "Network" for c in checks)
    assert checks[0].status == "ok"


@posix_only
def test_run_all_sweeps_every_profile(tmp_path):
    root = tmp_path
    default_env = root / ".env"
    default_env.write_text("K=1")
    default_env.chmod(0o644)
    work = root / "profiles" / "work"
    work.mkdir(parents=True)
    work_env = work / ".env"
    work_env.write_text("K=2")
    work_env.chmod(0o600)

    checks = audit.run_all(root, offline=True)
    groups = {c.group for c in checks}
    assert any(g.startswith("@default ·") for g in groups)
    assert any(g.startswith("@work ·") for g in groups)
    default_env_hits = [
        c for c in checks if c.group == "@default · Permissions" and c.name == ".env"
    ]
    assert default_env_hits and default_env_hits[0].status == "fail"


def test_dependencies_offline_is_skipped(tmp_path):
    checks = audit._audit_dependencies(offline=True)
    assert len(checks) == 1 and checks[0].status == "info"
    assert "offline" in checks[0].detail


def test_dependencies_network_failure_is_skipped(monkeypatch):
    from alpi.tools import _osv
    monkeypatch.setattr(_osv, "check_versions", lambda *a, **k: None)
    checks = audit._audit_dependencies(offline=False)
    assert checks[0].status == "info" and "unreachable" in checks[0].detail


def test_dependencies_clean(monkeypatch):
    from alpi.tools import _osv
    monkeypatch.setattr(_osv, "check_versions", lambda *a, **k: {})
    checks = audit._audit_dependencies(offline=False)
    assert checks[0].status == "ok"


def test_dependencies_report_advisories(monkeypatch):
    from alpi.tools import _osv
    monkeypatch.setattr(_osv, "check_versions",
                        lambda *a, **k: {"litellm": ["GHSA-aaaa", "GHSA-bbbb"]})
    checks = audit._audit_dependencies(offline=False)
    hit = [c for c in checks if c.name == "litellm"]
    assert hit and hit[0].status == "warn"
    assert "GHSA-aaaa" in hit[0].detail


def test_osv_check_versions_empty_is_clean_without_network():
    from alpi.tools import _osv
    assert _osv.check_versions("PyPI", []) == {}


def test_exit_code_nonzero_on_failure(tmp_path):
    env = tmp_path / ".env"
    env.write_text("KEY=secret")
    if os.name == "posix":
        env.chmod(0o644)
        checks = audit._audit_permissions(tmp_path)
        assert audit.exit_code(checks) == 1
