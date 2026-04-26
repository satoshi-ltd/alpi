"""``@peer ...`` mention parser. ``@`` matches anywhere as long as
it sits on a whitespace boundary, so ``hello@gmail.com`` never
triggers but ``hey @mirai ¿qué tal?`` does. ``home`` is optional;
when given, the parser also requires the matched id to be a pinned
peer."""

from __future__ import annotations

from pathlib import Path

import pytest

from alpi.alp import peers as peers_mod
from alpi.alp.mention import parse
from alpi.alp.peers import Peer


def test_basic_mention_at_start_parses() -> None:
    m = parse("@mirai what time is it?")
    assert m is not None
    assert m.peer_id == "mirai"
    assert m.prompt == "what time is it?"


def test_mention_in_middle_of_text_parses() -> None:
    """The whole point of ALP.3.1: humans write '@mirai' mid-sentence."""
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
    """``hello@gmail.com`` has no whitespace before ``@`` — never matches."""
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
    """``@property`` in a code snippet shouldn't trigger a peer call —
    no pinned peer named ``property`` → ``parse`` returns ``None`` and
    the caller hands the text to the LLM as plain prose."""
    assert parse("use the @property decorator", home=home_with_pinned_alice) is None


def test_no_home_skips_roster_validation() -> None:
    """Without ``home``, the parser detects structurally-valid
    mentions without checking pinning — used by tests and any
    caller that wants raw detection."""
    m = parse("use @property here")
    assert m is not None
    assert m.peer_id == "property"
