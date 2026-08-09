from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from alpi import cli
from alpi.host import admin_audit
from alpi.host.connection_context import ConnectionContext


def _seed(home: Path) -> None:
    admin_audit._record(
        home,
        "host.connections.revoke_device",
        {"connection_id": "conn_service", "device_id": "dev_node"},
        {"result": {"ok": True}},
        context=ConnectionContext(
            connection_id="conn_owner",
            device_id="dev_mac",
            source="remote",
            role="admin",
        ),
    )


def test_audit_log_renders_local_trail(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ALPI_HOME", str(tmp_path))
    _seed(tmp_path)

    result = CliRunner().invoke(cli.main, ["audit-log"])

    assert result.exit_code == 0
    assert "dev_mac" in result.output
    assert "host.connect" in result.output
    assert "dev_node" in result.output
    assert "success" in result.output
    assert "remote/admin" in result.output


def test_audit_log_filters_and_emits_json(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ALPI_HOME", str(tmp_path))
    _seed(tmp_path)

    missing = CliRunner().invoke(
        cli.main, ["audit-log", "--connection", "other", "--json"],
    )
    matched = CliRunner().invoke(
        cli.main, ["audit-log", "--connection", "conn_service", "--json"],
    )

    assert json.loads(missing.output) == []
    assert json.loads(matched.output)[0]["device_id"] == "dev_mac"


def test_audit_log_empty_state(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ALPI_HOME", str(tmp_path))
    result = CliRunner().invoke(cli.main, ["audit-log"])
    assert result.exit_code == 0
    assert "no administrative activity yet" in result.output


def test_audit_log_reserves_local_host_for_the_real_local_actor(
    tmp_path: Path, monkeypatch,
) -> None:
    monkeypatch.setenv("ALPI_HOME", str(tmp_path))
    admin_audit._append(tmp_path, {
        "id": "audit_spoof",
        "timestamp": "2026-08-08T10:00:00.000Z",
        "connection_id": "conn_remote",
        "connection_label": "Local host",
        "device_id": "dev_remote",
        "device_name": "Local host",
        "source": "remote",
        "role": "member",
        "method": "host.connections.register_device",
        "target": {},
        "target_connection_label": "",
        "target_device_name": "",
        "result": "success",
    })

    result = CliRunner().invoke(cli.main, ["audit-log"])

    assert result.exit_code == 0
    assert "dev_remote" in result.output
    assert "remote/member" in result.output
    assert "Local host" not in result.output
