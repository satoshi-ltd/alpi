"""`@peer` mention parser."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from alpi.alp import peers as peers_mod
from alpi.alp.mention import execute, parse
from alpi.alp.peers import Peer


def test_basic_mention_at_start_parses() -> None:
    m = parse("@mirai what time is it?")
    assert m is not None
    assert m.peer_id == "mirai"
    assert m.prompt == "what time is it?"


def test_mention_in_middle_of_text_parses() -> None:
    """Humans can write '@mirai' mid-sentence."""
    m = parse("hey @mirai can you check this?")
    assert m is not None
    assert m.peer_id == "mirai"
    assert m.prompt == "hey can you check this?"


def test_mention_at_end_of_text_parses() -> None:
    """Trailing mention with content before is still routable."""
    m = parse("thanks @mirai")
    assert m is not None
    assert m.peer_id == "mirai"
    assert m.prompt == "thanks"


def test_email_inside_message_does_not_match() -> None:
    """No whitespace before `@` means no match."""
    assert parse("oye alpi manda email a hello@soyjavi.com") is None


def test_missing_prompt_around_handle() -> None:
    """A bare ``@<peer>`` with no surrounding text has no prompt."""
    assert parse("@mirai") is None
    assert parse("@mirai   ") is None
    assert parse("   @mirai   ") is None


def test_just_the_at_sign() -> None:
    assert parse("@") is None
    assert parse("") is None


def test_internal_whitespace_preserved_in_prompt() -> None:
    """Boundary whitespace around the ``@`` token is stripped, but
    internal whitespace inside the user's prompt stays untouched."""
    m = parse("@mirai   hello   world")
    assert m is not None
    assert m.prompt == "hello   world"


def test_mention_in_middle_preserves_internal_whitespace() -> None:
    m = parse("look at  this:\n@mirai\n   what gives?")
    assert m is not None
    assert m.peer_id == "mirai"
    # The seam between the two halves gets exactly one space.
    assert m.prompt == "look at  this: what gives?"


def test_handle_with_hyphens_and_digits() -> None:
    m = parse("@home-server-01 status?")
    assert m is not None
    assert m.peer_id == "home-server-01"


def test_punctuation_after_handle_does_not_eat_into_id() -> None:
    """``@alice,`` should detect id ``alice`` (the comma is just
    punctuation in the prompt, not part of the peer id)."""
    m = parse("hey @alice, please review")
    assert m is not None
    assert m.peer_id == "alice"
    assert m.prompt == "hey , please review"


def test_first_mention_wins() -> None:
    """When two mentions appear, route to the first; the rest stays
    in the prompt for the routed peer to do as they please."""
    m = parse("@alice tell @bob hello")
    assert m is not None
    assert m.peer_id == "alice"
    assert "@bob" in m.prompt


# Roster validation (when ``home`` is provided)


@pytest.fixture
def home_with_pinned_alice(tmp_path: Path) -> Path:
    home = tmp_path / "me"
    home.mkdir()
    peers_mod.add(home, Peer(id="alice", pubkey="ALICE_PK", allow=["link.ping"]))
    return home


def test_pinned_peer_resolves(home_with_pinned_alice: Path) -> None:
    m = parse("hey @alice ping", home=home_with_pinned_alice)
    assert m is not None
    assert m.peer_id == "alice"


def test_unpinned_id_falls_through_to_none(home_with_pinned_alice: Path) -> None:
    """`@property` in code should stay plain text."""
    assert parse("use the @property decorator", home=home_with_pinned_alice) is None


def test_no_home_skips_roster_validation() -> None:
    """Without `home`, the parser only checks structure."""
    m = parse("use @property here")
    assert m is not None
    assert m.peer_id == "property"


# execute() routing


def test_execute_routes_remote_peer_over_tcp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A pinned peer with ``address`` must go through ``call_peer``
    (TCP/Noise), not be rejected as ALP.2 pending."""
    home = tmp_path / "me"
    home.mkdir()
    peers_mod.add(
        home,
        Peer(id="bob", pubkey="BOB_PK", address="100.1.2.3:7425", allow=["link.ask"]),
    )

    captured: dict = {}

    async def fake_call_tcp_stream(**kwargs):
        captured.update(kwargs)
        yield {"event": "started", "session_id": "remote-turn"}, "chunk"
        yield {
            "text": "pong from tcp", "tokens_in": 1, "tokens_out": 2, "cost": 0.0,
        }, "final"

    monkeypatch.setattr(
        "alpi.alp.mention.alp_client.call_tcp_stream", fake_call_tcp_stream,
    )

    result = asyncio.run(execute(home, "bob", "ping"))

    assert result.ok is True
    assert result.reply == "pong from tcp"
    assert captured["host"] == "100.1.2.3"
    assert captured["port"] == 7425
    assert captured["method"] == "link.ask"
    assert captured["params"] == {"prompt": "ping", "stream": True}
    assert captured["timeout"] == 60


def test_execute_local_peer_resolves_socket_by_pubkey(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Without pubkey resolution probe says online but link.ask 404s under arbitrary alias.
    from alpi import home as home_mod
    from alpi.alp import keys as keys_mod

    root = tmp_path / ".alpi"
    root.mkdir()
    monkeypatch.setattr(home_mod, "_ROOT", root)

    me = root / "profiles" / "me"
    me.mkdir(parents=True)
    target = root / "profiles" / "real_name"
    target.mkdir(parents=True)
    keys_mod.generate(me)
    target_kp = keys_mod.generate(target)

    peers_mod.add(
        me,
        Peer(id="arbitrary", pubkey=target_kp.pubkey_b64(), allow=["link.ask"]),
    )

    sock = target / "alp" / "alp.sock"
    sock.parent.mkdir(parents=True, exist_ok=True)
    sock.touch()

    captured: dict = {}

    async def fake_call_stream(**kwargs):
        captured.update(kwargs)
        yield {"event": "started", "session_id": "local-turn"}, "chunk"
        yield {
            "text": "pong unix", "tokens_in": 0, "tokens_out": 0, "cost": 0.0,
        }, "final"

    monkeypatch.setattr(
        "alpi.alp.mention.alp_client.call_stream", fake_call_stream,
    )

    result = asyncio.run(execute(me, "arbitrary", "hi"))
    assert result.ok is True
    assert str(captured["socket_path"]) == str(sock)


def test_execute_uses_configured_idle_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "me"
    home.mkdir()
    peers_mod.add(home, Peer(id="bob", pubkey="BOB_PK", allow=["link.ask"]))
    (home / "config.yaml").write_text(
        "alp:\n  link_idle_timeout_s: 12\n  link_max_duration_s: 0\n",
    )
    socket_path = tmp_path / "bob.sock"
    socket_path.touch()
    monkeypatch.setattr(peers_mod, "local_socket_path", lambda _peer: socket_path)
    captured: dict = {}

    async def fake_call_stream(**kwargs):
        captured.update(kwargs)
        yield {"event": "started", "session_id": "turn"}, "chunk"
        yield {"text": "done"}, "final"

    monkeypatch.setattr(
        "alpi.alp.mention.alp_client.call_stream", fake_call_stream,
    )

    result = asyncio.run(execute(home, "bob", "ping"))

    assert result.ok is True
    assert captured["timeout"] == 12


def test_execute_reports_idle_timeout_and_requests_cancel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "me"
    home.mkdir()
    peers_mod.add(home, Peer(id="bob", pubkey="BOB_PK", allow=["link.ask"]))
    socket_path = tmp_path / "bob.sock"
    socket_path.touch()
    monkeypatch.setattr(peers_mod, "local_socket_path", lambda _peer: socket_path)
    cancelled: dict = {}

    async def fake_call_stream(**_kwargs):
        yield {"event": "started", "session_id": "turn-1"}, "chunk"
        raise asyncio.TimeoutError

    async def fake_cancel(_home, _peer, _sender, session_id):
        cancelled["session_id"] = session_id
        return True

    monkeypatch.setattr(
        "alpi.alp.mention.alp_client.call_stream", fake_call_stream,
    )
    monkeypatch.setattr("alpi.alp.mention._cancel", fake_cancel)

    result = asyncio.run(execute(home, "bob", "ping", timeout=0.01))

    assert result.ok is False
    assert result.error == (
        "link.ask timed out after 0.01s without remote activity; "
        "remote turn cancelled"
    )
    assert cancelled["session_id"] == "turn-1"


def test_execute_enforces_optional_maximum_duration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "me"
    home.mkdir()
    peers_mod.add(home, Peer(id="bob", pubkey="BOB_PK", allow=["link.ask"]))
    socket_path = tmp_path / "bob.sock"
    socket_path.touch()
    monkeypatch.setattr(peers_mod, "local_socket_path", lambda _peer: socket_path)

    async def fake_call_stream(**_kwargs):
        yield {"event": "started", "session_id": "turn-2"}, "chunk"
        await asyncio.sleep(1)
        yield {"text": "too late"}, "final"

    async def fake_cancel(*_args):
        return True

    monkeypatch.setattr(
        "alpi.alp.mention.alp_client.call_stream", fake_call_stream,
    )
    monkeypatch.setattr("alpi.alp.mention._cancel", fake_cancel)

    result = asyncio.run(execute(
        home, "bob", "ping", timeout=0, max_duration=0.01,
    ))

    assert result.ok is False
    assert result.error == (
        "link.ask exceeded its 0.01s maximum duration; remote turn cancelled"
    )
