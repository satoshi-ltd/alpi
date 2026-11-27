from __future__ import annotations

import json
import time
import urllib.parse
from pathlib import Path

import pytest

from alpi import config as cfg_mod
from alpi.host import config as host_config
from alpi.host import device_state as host_device_state
from alpi.host import events as host_events
from alpi.host import handlers as host_handlers
from alpi.host import server as host_server
from alpi.host.connection_context import ConnectionContext, use
from alpi.providers import chatgpt

ADMIN = ConnectionContext(connection_id="c1", device_id="d1", source="remote", role="admin")


@pytest.fixture
def srv(tmp_path: Path, monkeypatch):
    home = tmp_path / "h"
    home.mkdir()
    monkeypatch.setenv("ALPI_HOME", str(home))
    cfg_mod.save(cfg_mod.Config(home=home, model="chatgpt-plan/gpt-6.2-sol"))
    monkeypatch.setattr(host_handlers, "_resolve_home", lambda p: home)
    monkeypatch.setattr(host_config, "_resolve_home", lambda p: home)
    monkeypatch.setattr(chatgpt, "_PENDING", {})
    server = host_server.Server(home=home)
    host_config.register(server)
    server.home_path = home
    return server


async def _call(server, method: str, **params):
    with use(ADMIN):
        return await server._dispatch({"id": "1", "method": method, "params": {"profile": "default", **params}})


def _signed_record(home: Path) -> None:
    chatgpt.record_path(home).parent.mkdir(parents=True, exist_ok=True)
    chatgpt.record_path(home).write_text(json.dumps({
        "client_id": "oaiapp_1", "subject": "u1", "email": "a@example.com", "id_token": "h.b.s",
        "access_token": "at", "refresh_token": "rt", "saved_at": time.time(), "expires_in": 3600,
        "scopes": [chatgpt.PLAN_SCOPE], "models": [{"slug": "gpt-6.2-sol", "display_name": "GPT-6.2 Sol"}],
    }))


@pytest.mark.asyncio
async def test_begin_hands_the_client_an_address_without_tokens_and_keeps_the_secret(srv) -> None:
    _signed_record(srv.home_path)

    resp = await _call(srv, "host.providers.chatgpt_begin", port=51234)

    out = resp["result"]
    sent = {k: v[0] for k, v in urllib.parse.parse_qs(urllib.parse.urlsplit(out["url"]).query).items()}
    assert out["redirect_uri"] == "http://127.0.0.1:51234/auth/callback" and sent["redirect_uri"] == out["redirect_uri"]
    assert sent["client_id"] == "oaiapp_1" and "id_token_hint" not in sent and "code_verifier" not in json.dumps(out)
    assert set(out) == {"url", "redirect_uri", "expires_in"}


@pytest.mark.asyncio
@pytest.mark.parametrize("port", [80, 70000, "x", -1])
async def test_begin_refuses_a_port_no_client_could_listen_on(srv, port) -> None:
    resp = await _call(srv, "host.providers.chatgpt_begin", port=port)

    assert resp["error"]["message"] == "chatgpt-sign-in" and chatgpt._PENDING == {}
    default = (await _call(srv, "host.providers.chatgpt_begin"))["result"]
    assert default["redirect_uri"] == "http://127.0.0.1:1455/auth/callback"


@pytest.mark.asyncio
async def test_finish_exchanges_only_the_answer_of_the_pending_attempt(srv, monkeypatch) -> None:
    home = srv.home_path
    finished: list[dict] = []

    def fake_finish(h, attempt, query, **kw):
        finished.append(query)
        _signed_record(h)
        return {"first_sign_in": True}

    monkeypatch.setattr(chatgpt, "finish", fake_finish)
    events: list[tuple[str, dict]] = []
    monkeypatch.setattr(host_events, "emit", lambda kind, data=None: events.append((kind, data or {})))

    nothing = await _call(srv, "host.providers.chatgpt_finish", callback="http://127.0.0.1:1455/auth/callback?code=c&state=s")
    assert nothing["error"]["data"]["code"] == "no_attempt"

    begun = (await _call(srv, "host.providers.chatgpt_begin", port=1455))["result"]
    state = urllib.parse.parse_qs(urllib.parse.urlsplit(begun["url"]).query)["state"][0]
    forged = await _call(srv, "host.providers.chatgpt_finish", callback="http://127.0.0.1:1455/auth/callback?code=evil&state=forged")
    elsewhere = await _call(srv, "host.providers.chatgpt_finish", callback=f"https://evil.example/x?code=c&state={state}")
    assert (forged["error"]["data"]["code"], elsewhere["error"]["data"]["code"]) == ("state_mismatch", "not_a_callback")
    assert finished == [] and chatgpt._PENDING

    done = await _call(srv, "host.providers.chatgpt_finish", callback=f"http://127.0.0.1:1455/auth/callback?code=c&state={state}&client_id=oaiapp_1")

    assert done["result"] == {
        "signed_in": True, "email": "a@example.com", "plan_declined": False, "registered": True,
        "models": ["chatgpt-plan/gpt-6.2-sol"], "usage_url": chatgpt.USAGE_URL, "first_sign_in": True, "model_set": "",
    }
    assert finished == [{"code": "c", "state": state, "client_id": "oaiapp_1"}] and chatgpt._PENDING == {}
    assert ("config_changed", {"profile": "default", "scope": "env"}) in events
    again = await _call(srv, "host.providers.chatgpt_finish", callback=f"?code=c&state={state}")
    assert again["error"]["data"]["code"] == "no_attempt"


@pytest.mark.asyncio
async def test_an_attempt_expires(srv, monkeypatch) -> None:
    begun = (await _call(srv, "host.providers.chatgpt_begin", port=1455))["result"]
    state = urllib.parse.parse_qs(urllib.parse.urlsplit(begun["url"]).query)["state"][0]
    real = time.monotonic()
    monkeypatch.setattr(chatgpt.time, "monotonic", lambda: real + chatgpt.PENDING_S + 1)

    resp = await _call(srv, "host.providers.chatgpt_finish", callback=f"?code=c&state={state}")

    assert resp["error"]["data"]["code"] == "no_attempt" and chatgpt._PENDING == {}


@pytest.mark.asyncio
async def test_status_and_the_profile_detail_say_who_is_signed_in_without_tokens(srv) -> None:
    home = srv.home_path
    before = (await _call(srv, "host.providers.chatgpt_status"))["result"]
    assert before == {"signed_in": False, "email": "", "plan_declined": False, "registered": False, "models": [], "usage_url": chatgpt.USAGE_URL}

    _signed_record(home)
    after = (await _call(srv, "host.providers.chatgpt_status"))["result"]
    detail = host_device_state._profile_detail_payload(home)

    assert after["signed_in"] and after["email"] == "a@example.com" and after["models"] == ["chatgpt-plan/gpt-6.2-sol"]
    assert detail["provider_chatgpt"] == {"signed_in": True, "email": "a@example.com", "plan_declined": False, "registered": True, "models": 1}
    assert "at" not in json.dumps(after).split('"') and "rt" not in json.dumps(detail["provider_chatgpt"]).split('"')


@pytest.mark.asyncio
async def test_logout_ends_the_session_and_clears_a_model_that_needed_it(srv, monkeypatch) -> None:
    home = srv.home_path
    _signed_record(home)
    monkeypatch.setattr(chatgpt, "logout", lambda h, forget=False: chatgpt.record_path(h).unlink() or True)

    resp = await _call(srv, "host.providers.chatgpt_logout")

    assert resp["result"] == {"ok": True, "revoked": True, "model_cleared": True}
    assert cfg_mod.load(home).model == "" and not chatgpt.signed_in(home)


def test_the_sign_in_verbs_are_admin_only_and_the_changing_ones_are_audited() -> None:
    from alpi.host import admin_audit

    verbs = {f"host.providers.chatgpt_{name}" for name in ("status", "begin", "finish", "logout")}
    assert verbs <= host_server._ADMIN_METHODS
    assert verbs - {"host.providers.chatgpt_status"} <= admin_audit.AUDITED_METHODS


@pytest.mark.asyncio
async def test_signing_in_gives_a_profile_without_a_model_its_first_plan_model(srv, monkeypatch) -> None:
    home = srv.home_path
    cfg = cfg_mod.load(home)
    cfg.model = ""
    cfg_mod.save(cfg)
    monkeypatch.setattr(chatgpt, "finish", lambda h, attempt, query, **kw: _signed_record(h) or {"first_sign_in": True})
    begun = (await _call(srv, "host.providers.chatgpt_begin", port=1455))["result"]
    state = urllib.parse.parse_qs(urllib.parse.urlsplit(begun["url"]).query)["state"][0]

    done = await _call(srv, "host.providers.chatgpt_finish", callback=f"?code=c&state={state}")

    assert done["result"]["model_set"] == "chatgpt-plan/gpt-6.2-sol" and cfg_mod.load(home).model == "chatgpt-plan/gpt-6.2-sol"
    cfg = cfg_mod.load(home)
    cfg.model = "openrouter/deepseek/deepseek-v4.1-flash"
    cfg_mod.save(cfg)
    assert chatgpt.give_a_model(home) == "" and cfg_mod.load(home).model == "openrouter/deepseek/deepseek-v4.1-flash"


@pytest.mark.asyncio
@pytest.mark.parametrize("callback", ["http://[::1", "\ud800", "", "127.0.0.1:1455/auth/callback?code=c", "http://127.0.0.1:1455/other?state=s"])
async def test_a_malformed_answer_is_refused_without_spending_the_attempt(srv, callback) -> None:
    await _call(srv, "host.providers.chatgpt_begin", port=1455)

    resp = await _call(srv, "host.providers.chatgpt_finish", callback=callback)

    assert resp["error"]["message"] == "chatgpt-sign-in" and resp["error"]["data"]["code"] in ("not_a_callback", "state_mismatch")
    assert chatgpt._PENDING


@pytest.mark.asyncio
@pytest.mark.parametrize("port", [float("inf"), float("nan"), [1455], {"a": 1}])
async def test_a_port_that_is_not_a_number_is_refused(srv, port) -> None:
    resp = await _call(srv, "host.providers.chatgpt_begin", port=port)

    assert resp["error"]["data"]["code"] == "bad_port"


@pytest.mark.asyncio
async def test_signing_out_of_a_profile_that_never_signed_in_leaves_no_files(srv) -> None:
    resp = await _call(srv, "host.providers.chatgpt_logout")

    assert resp["result"]["revoked"] is True and not (srv.home_path / "secrets").exists()


@pytest.mark.asyncio
async def test_sign_out_keeps_the_registration_unless_asked_to_forget(srv, monkeypatch) -> None:
    home = srv.home_path
    monkeypatch.setattr(chatgpt.httpx.Client, "send", lambda self, request, **kw: (_ for _ in ()).throw(chatgpt.httpx.ConnectError("down")))
    _signed_record(home)

    kept = await _call(srv, "host.providers.chatgpt_logout")
    saved = chatgpt.load(home)
    assert kept["result"]["revoked"] is False and saved["client_id"] == "oaiapp_1" and "refresh_token" not in saved
    status = (await _call(srv, "host.providers.chatgpt_status"))["result"]
    assert (status["signed_in"], status["registered"], status["email"]) == (False, True, "a@example.com")

    _signed_record(home)
    await _call(srv, "host.providers.chatgpt_logout", forget=True)
    assert not chatgpt.record_path(home).exists()
    assert (await _call(srv, "host.providers.chatgpt_status"))["result"]["registered"] is False


@pytest.mark.asyncio
async def test_signing_out_drops_a_sign_in_that_was_still_waiting(srv) -> None:
    begun = (await _call(srv, "host.providers.chatgpt_begin", port=1455))["result"]
    state = urllib.parse.parse_qs(urllib.parse.urlsplit(begun["url"]).query)["state"][0]

    await _call(srv, "host.providers.chatgpt_logout", forget=True)
    late = await _call(srv, "host.providers.chatgpt_finish", callback=f"?code=c&state={state}")

    assert chatgpt._PENDING == {} and late["error"]["data"]["code"] == "no_attempt"
