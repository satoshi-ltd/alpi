"""``@peer ...`` mention parser — the rule is strict-leading-@ so
free-form messages like ``email a hello@soyjavi.com`` never trigger."""

from __future__ import annotations

from alpi.alp.mention import parse


def test_basic_mention_parses() -> None:
    m = parse("@mirai what time is it?")
    assert m is not None
    assert m.peer_id == "mirai"
    assert m.prompt == "what time is it?"


def test_leading_whitespace_disqualifies() -> None:
    # " @mirai hi" is just a regular message — do not route.
    assert parse(" @mirai hi") is None


def test_email_inside_message_does_not_match() -> None:
    assert parse("oye alpi manda email a hello@soyjavi.com") is None


def test_missing_prompt_after_handle() -> None:
    assert parse("@mirai") is None
    assert parse("@mirai   ") is None


def test_just_the_at_sign() -> None:
    assert parse("@") is None
    assert parse("") is None


def test_extra_whitespace_collapsed_into_prompt() -> None:
    m = parse("@mirai   hello   world")
    assert m is not None
    assert m.prompt == "hello   world"


def test_handle_with_hyphens_and_digits() -> None:
    m = parse("@home-server-01 status?")
    assert m is not None
    assert m.peer_id == "home-server-01"
