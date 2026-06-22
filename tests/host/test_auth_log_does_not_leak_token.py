import logging

import pytest

from alpi.host import server as host_server


@pytest.fixture
def caplog_warning(caplog):
    caplog.set_level(logging.WARNING, logger="alpi.host.server")
    return caplog


def test_failed_auth_log_does_not_emit_token_suffix(caplog_warning, monkeypatch):
    secret = "verysecrettoken-AAAABBBBCCCCDDDD"
    monkeypatch.setattr(
        "alpi.host.devices.validate_and_lookup",
        lambda token: (False, "", []),
    )
    body = {"method": "host.config.get", "params": {"auth_token": secret}}
    valid, role, scope = host_server._check_token_meta(body)
    assert not valid
    failure_lines = [
        rec.message for rec in caplog_warning.records if "auth-failed" in rec.message
    ]
    assert failure_lines
    for line in failure_lines:
        assert secret not in line
        assert secret[-8:] not in line


def test_failed_auth_log_carries_useful_diagnostics(caplog_warning, monkeypatch):
    secret = "verysecrettoken-AAAABBBBCCCCDDDD"
    monkeypatch.setattr(
        "alpi.host.devices.validate_and_lookup",
        lambda token: (False, "", []),
    )
    body = {"method": "host.config.get", "params": {"auth_token": secret}}
    host_server._check_token_meta(body)
    failure_lines = [
        rec.message for rec in caplog_warning.records if "auth-failed" in rec.message
    ]
    assert any(f"len={len(secret)}" in line for line in failure_lines)
    assert any("host.config.get" in line for line in failure_lines)


def test_missing_token_log_is_distinct(caplog_warning, monkeypatch):
    monkeypatch.setattr(
        "alpi.host.devices.validate_and_lookup",
        lambda token: (False, "", []),
    )
    body = {"method": "host.config.get", "params": {}}
    host_server._check_token_meta(body)
    failure_lines = [
        rec.message for rec in caplog_warning.records if "auth-failed" in rec.message
    ]
    assert any("no token sent" in line for line in failure_lines)


def test_unicode_token_is_rejected_without_raising(caplog_warning, monkeypatch):
    from alpi.host import devices as devices_mod

    ascii_device = {
        "token": "AAAABBBBCCCCDDDD-ascii-only-32chr",
        "role": "member",
        "profile_scope": [],
        "last_seen": 0,
    }
    monkeypatch.setattr(devices_mod, "_load_cached", lambda: [dict(ascii_device)])
    monkeypatch.setattr(devices_mod, "load", lambda: [dict(ascii_device)])

    body = {"method": "host.config.get", "params": {"auth_token": "🔑secret"}}
    valid, role, scope = host_server._check_token_meta(body)
    assert valid is False, (
        "Unicode token must be rejected via _tokens_match without raising; "
        "the previous hmac.compare_digest(str, str) on non-ASCII would TypeError"
    )
    assert role == "" and scope == []
