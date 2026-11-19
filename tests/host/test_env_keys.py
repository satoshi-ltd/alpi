from __future__ import annotations

from pathlib import Path

import pytest

from alpi import config as cfg_mod
from alpi.host import config as host_config
from alpi.host import handlers as host_handlers
from alpi.host import server as host_server
from alpi.host.connection_context import ConnectionContext, use
from alpi.model_selector import _append_env

REMOTE_ADMIN = ConnectionContext(connection_id="c1", device_id="d1", source="remote", role="admin")
LOCAL_SOCKET = ConnectionContext(connection_id="host", source="local", role="admin")
BOOTSTRAP = ConnectionContext(connection_id="host", source="bootstrap", role="admin")

DAEMON_WIDE = [
    "ALPI_NETWORK_HOST",
    "ALPI_HOST_TCP_PORT",
    "ALPI_ALP_TCP_PORT",
    "ALPI_HOST_WS_TRUSTED_PROXIES",
    "ALPI_ANYTHING",
    "PYTHONSTARTUP",
    "PYTHONHOME",
    "LD_PRELOAD",
    "LD_LIBRARY_PATH",
    "DYLD_INSERT_LIBRARIES",
]


@pytest.fixture
def srv(tmp_path: Path, monkeypatch):
    home = tmp_path / "h"
    home.mkdir()
    cfg_mod.save(cfg_mod.Config(home=home, model="x"))
    monkeypatch.setattr(host_handlers, "_resolve_home", lambda p: home)
    server = host_server.Server(home=home)
    host_config.register(server)
    server.home_path = home
    return server


async def _call(srv, method: str, **params):
    return await srv._dispatch({"id": "1", "method": method, "params": {"profile": "default", **params}})


def _env(srv) -> str:
    path = srv.home_path / ".env"
    return path.read_text() if path.exists() else ""


@pytest.mark.asyncio
@pytest.mark.parametrize("name", DAEMON_WIDE)
@pytest.mark.parametrize("method", ["host.providers.set_key", "host.providers.unset_key"])
async def test_nobody_sets_a_daemon_wide_variable_through_the_provider_verbs(srv, name: str, method: str) -> None:
    for context in (None, LOCAL_SOCKET, REMOTE_ADMIN, BOOTSTRAP):
        extra = {"value": "0.0.0.0"} if method.endswith("set_key") else {}
        if context is None:
            resp = await _call(srv, method, key=name, **extra)
        else:
            with use(context):
                resp = await _call(srv, method, key=name, **extra)
        assert resp["error"]["message"] == "forbidden", (name, context)
    assert name not in _env(srv)


@pytest.mark.asyncio
@pytest.mark.parametrize("name", ["MY_KEY", "SOMETHING_ELSE", "PATH_EXTRA", "AWS_SECRET_ACCESS_KEY", "GITHUB_TOKEN"])
async def test_a_remote_admin_sets_only_names_a_client_needs(srv, name: str) -> None:
    with use(REMOTE_ADMIN):
        resp = await _call(srv, "host.providers.set_key", key=name, value="x")
    assert resp["error"]["message"] == "forbidden"
    assert name not in _env(srv)


@pytest.mark.asyncio
@pytest.mark.parametrize("name", [
    "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY", "GEMINI_API_KEY", "GROQ_API_KEY",
    "GMAIL_CLIENT_ID", "GMAIL_CLIENT_SECRET", "EMAIL__WORK__PASSWORD",
])
async def test_a_remote_admin_still_sets_provider_gmail_and_email_keys(srv, name: str) -> None:
    with use(REMOTE_ADMIN):
        resp = await _call(srv, "host.providers.set_key", key=name, value="abc")
        assert resp["result"]["ok"] is True, name
        assert f"{name}=abc" in _env(srv)
        resp = await _call(srv, "host.providers.unset_key", key=name)
        assert resp["result"]["ok"] is True, name
    assert name not in _env(srv)


@pytest.mark.asyncio
@pytest.mark.parametrize("context", [None, LOCAL_SOCKET])
async def test_the_local_socket_keeps_setting_any_ordinary_name(srv, context) -> None:
    if context is None:
        resp = await _call(srv, "host.providers.set_key", key="MY_KEY", value="abc")
    else:
        with use(context):
            resp = await _call(srv, "host.providers.set_key", key="MY_KEY", value="abc")
    assert resp["result"]["ok"] is True
    assert "MY_KEY=abc" in _env(srv)


@pytest.mark.asyncio
async def test_a_bootstrap_caller_is_held_to_the_remote_names(srv) -> None:
    with use(BOOTSTRAP):
        resp = await _call(srv, "host.providers.set_key", key="MY_KEY", value="abc")
    assert resp["error"]["message"] == "forbidden"


@pytest.mark.asyncio
async def test_an_email_password_with_a_line_break_leaves_no_account_behind(srv) -> None:
    with use(REMOTE_ADMIN):
        resp = await _call(srv, "host.email.add", address="a@b.co", password="x\ny", imap_host="imap.b.co", smtp_host="smtp.b.co")
    assert resp["error"]["message"] == "invalid-params"
    assert "a@b.co" not in (srv.home_path / "config.yaml").read_text()
    assert "PASSWORD" not in _env(srv)


@pytest.mark.asyncio
@pytest.mark.parametrize("value", ["a\nPYTHONPATH=/tmp/e", "a\rb", "a\x00b"])
@pytest.mark.parametrize("remote", [False, True])
async def test_a_value_with_a_line_break_or_nul_is_refused(srv, value: str, remote: bool) -> None:
    if remote:
        with use(REMOTE_ADMIN):
            resp = await _call(srv, "host.providers.set_key", key="OPENAI_API_KEY", value=value)
    else:
        resp = await _call(srv, "host.providers.set_key", key="OPENAI_API_KEY", value=value)
    assert resp["error"]["message"] == "invalid-params"
    assert _env(srv) == ""


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["client_id", "client_secret"])
async def test_a_gmail_credential_with_a_line_break_writes_nothing(srv, field: str) -> None:
    params = {"client_id": "id", "client_secret": "secret", "redirect_uri": "http://127.0.0.1:8123/cb"}
    params[field] = "x\nPYTHONPATH=/tmp/e"
    with use(REMOTE_ADMIN):
        resp = await _call(srv, "host.email.gmail.begin", **params)
    assert resp["error"]["message"] == "invalid-params"
    assert "PYTHONPATH" not in _env(srv)


@pytest.mark.parametrize("key,value", [("K", "a\nB=c"), ("K", "a\rb"), ("K", "a\x00b"), ("K\nB", "v"), ("K=B", "v")])
def test_the_env_writer_itself_refuses_line_breaks_and_nul(tmp_path: Path, key: str, value: str) -> None:
    path = tmp_path / ".env"
    with pytest.raises(ValueError):
        _append_env(path, key, value)
    assert not path.exists()


@pytest.mark.asyncio
@pytest.mark.parametrize("change", [{"imap_host": "imap.evil.example"}, {"smtp_host": "smtp.evil.example"}, {"imap_port": 1993}, {"smtp_port": 2525}])
async def test_changing_an_email_accounts_servers_needs_its_password_again(srv, change) -> None:
    base = {"address": "a@b.co", "imap_host": "imap.b.co", "smtp_host": "smtp.b.co"}
    resp = await _call(srv, "host.email.add", password="secret", **base)
    assert resp["result"]["ok"] is True
    with use(REMOTE_ADMIN):
        resp = await _call(srv, "host.email.add", password="", **{**base, **change})
    assert resp["error"]["message"] == "invalid-params"
    assert "password again" in resp["error"]["data"]["detail"]
    assert "imap.b.co" in (srv.home_path / "config.yaml").read_text()


@pytest.mark.asyncio
async def test_an_email_edit_that_keeps_the_servers_keeps_the_stored_password(srv) -> None:
    base = {"address": "a@b.co", "imap_host": "imap.b.co", "smtp_host": "smtp.b.co"}
    await _call(srv, "host.email.add", password="secret", **base)
    resp = await _call(srv, "host.email.add", password="", **base)
    assert resp["result"]["ok"] is True
    assert "secret" in _env(srv)
    resp = await _call(srv, "host.email.add", password="new-secret", **{**base, "imap_host": "imap2.b.co"})
    assert resp["result"]["ok"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize("key", ["email.accounts.a_b_co.imap_host", "email", "email.accounts"])
@pytest.mark.parametrize("method", ["host.config.set_field", "host.config.unset_field"])
async def test_email_accounts_are_not_written_through_the_generic_config_verbs(srv, key, method) -> None:
    base = {"address": "a@b.co", "imap_host": "imap.b.co", "smtp_host": "smtp.b.co"}
    await _call(srv, "host.email.add", password="secret", **base)
    host_config_mod = __import__("alpi.host.device_state", fromlist=["register"])
    host_config_mod.register(srv)
    extra = {"value": "imap.evil.example"} if method.endswith("set_field") else {}
    with use(REMOTE_ADMIN):
        resp = await _call(srv, method, key=key, **extra)
    assert resp["error"]["message"] == "invalid-params"
    assert "host.email.add" in resp["error"]["data"]["detail"]
    assert "imap.evil.example" not in (srv.home_path / "config.yaml").read_text()
