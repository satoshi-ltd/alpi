"""Default-profile constraints for the host subsystem."""

from __future__ import annotations

from pathlib import Path

import pytest

from alpi import service


@pytest.mark.asyncio
async def test_run_host_refuses_non_default_profile(tmp_path: Path) -> None:
    """Non-default profiles must not bind the host socket."""
    home = tmp_path / "h"
    home.mkdir()
    await service._run_host(home, "alice")
    assert not (home / "host" / "host.sock").exists()


@pytest.mark.asyncio
async def test_profile_delete_ignores_alpi_home_env(
    tmp_path: Path, monkeypatch,
) -> None:
    """Profile deletion must ignore ``ALPI_HOME`` and resolve literally."""
    from alpi import home as home_mod
    from alpi.host import config as host_config
    from alpi.host import server as host_server

    root = tmp_path / "home" / ".alpi"
    (root / "profiles" / "gus").mkdir(parents=True)
    (root / "profiles" / "gus" / "marker.txt").write_text("gus-only")
    (root / "memories").mkdir()
    (root / "memories" / "USER.md").write_text("default's user memory")
    (root / "config.yaml").write_text("model: x\n")

    monkeypatch.setattr(home_mod, "_ROOT", root)
    monkeypatch.setenv("ALPI_HOME", str(root))

    srv = host_server.Server(home=root)
    host_config.register(srv)

    body = {
        "id": "r",
        "method": "host.profile.delete",
        "params": {"name": "gus"},
    }
    response = await srv._dispatch(body)
    assert response["result"]["ok"] is True

    assert not (root / "profiles" / "gus").exists()
    assert (root / "memories" / "USER.md").read_text() == "default's user memory"
    assert (root / "config.yaml").exists()
    archived = list((root / ".trash").glob("gus-*"))
    assert len(archived) == 1
    assert (archived[0] / "marker.txt").read_text() == "gus-only"


@pytest.mark.parametrize(
    "verb, params",
    [
        ("host.session.read", {"profile": "default", "id": "../../etc/passwd"}),
        ("host.session.read", {"profile": "default", "id": "foo/bar"}),
        ("host.session.read", {"profile": "default", "id": "."}),
        ("host.workgroup.transcript", {"profile": "default", "wg_id": "../etc"}),
        ("host.workgroup.transcript", {"profile": "default", "wg_id": "x/y"}),
    ],
)
@pytest.mark.asyncio
async def test_read_verbs_reject_path_traversal(
    tmp_path: Path, monkeypatch, verb: str, params: dict,
) -> None:
    """Path-like ids must be rejected by read verbs."""
    from alpi import home as home_mod
    from alpi.host import handlers as host_handlers
    from alpi.host import server as host_server

    root = tmp_path / "home" / ".alpi"
    root.mkdir(parents=True)
    monkeypatch.setattr(home_mod, "_ROOT", root)

    srv = host_server.Server(home=root)
    host_handlers.register(srv)

    response = await srv._dispatch({"id": "r", "method": verb, "params": params})
    assert response["error"]["code"] == -32602


@pytest.mark.parametrize(
    "params, expected_code",
    [
        ({"profile": "default", "key": "FOO\nBAR=evil", "value": "x"}, -32602),
        ({"profile": "default", "key": "lowercase", "value": "x"}, -32602),
        ({"profile": "default", "key": "9STARTS_WITH_DIGIT", "value": "x"}, -32602),
        ({"profile": "default", "key": "HOME", "value": "/tmp/evil"}, -32001),
        ({"profile": "default", "key": "ALPI_HOME", "value": "/tmp/evil"}, -32001),
        ({"profile": "default", "key": "PATH", "value": "/tmp/evil"}, -32001),
        ({"profile": "default", "key": "OK_NAME", "value": "good\nEVIL=x"}, -32602),
    ],
)
@pytest.mark.asyncio
async def test_providers_set_key_rejects_dangerous_input(
    tmp_path: Path, monkeypatch, params: dict, expected_code: int,
) -> None:
    """Reject malformed or protected env keys and multiline values."""
    from alpi import home as home_mod
    from alpi.host import config as host_config
    from alpi.host import server as host_server

    root = tmp_path / "home" / ".alpi"
    root.mkdir(parents=True)
    (root / "config.yaml").write_text("model: x\n")
    monkeypatch.setattr(home_mod, "_ROOT", root)

    srv = host_server.Server(home=root)
    host_config.register(srv)
    response = await srv._dispatch({
        "id": "r", "method": "host.providers.set_key", "params": params,
    })
    assert response["error"]["code"] == expected_code


def test_default_profile_has_host_on_by_default(tmp_path: Path) -> None:
    """The default profile enables host by default."""
    home = tmp_path / "h"
    home.mkdir()
    (home / "config.yaml").write_text("model: x\n")
    on = service.enabled_subsystems(home)
    assert on["host"] is True


def test_host_can_be_disabled_explicitly(tmp_path: Path) -> None:
    home = tmp_path / "h"
    home.mkdir()
    (home / "config.yaml").write_text("model: x\nservice:\n  host: false\n")
    on = service.enabled_subsystems(home)
    assert on["host"] is False
