"""``alpi.knowledge`` — packaged answer packs about alpi itself."""

from __future__ import annotations

from importlib.resources import files

import pytest

from alpi import knowledge


def test_topics_returns_explicit_enum() -> None:
    assert knowledge.topics() == list(knowledge.TOPICS.keys())


def test_topics_is_stable_and_non_empty() -> None:
    ts = knowledge.topics()
    assert len(ts) >= 8
    for required in ("readme", "install", "quickstart", "alp", "security"):
        assert required in ts


def test_every_topic_has_a_packaged_reference_file() -> None:
    refs = files("alpi.knowledge") / "references"
    for topic, filename in knowledge.TOPICS.items():
        assert (refs / filename).is_file(), f"{topic}: {filename} missing"


def test_read_returns_packaged_markdown() -> None:
    body = knowledge.read("readme")
    assert isinstance(body, str)
    assert body.strip()
    assert "alpi" in body.lower()


def test_read_install_mentions_install_methods() -> None:
    body = knowledge.read("install")
    lowered = body.lower()
    assert "uv tool" in lowered or "pipx" in lowered or "pip install" in lowered


def test_read_unknown_topic_raises_keyerror_with_valid_list() -> None:
    with pytest.raises(KeyError) as exc:
        knowledge.read("does-not-exist")
    msg = str(exc.value)
    assert "does-not-exist" in msg
    # Error includes a valid topic so the agent can recover without a second round-trip.
    assert "readme" in msg
