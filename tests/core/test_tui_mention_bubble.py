from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from alpi.alp import mention as alp_mention
from alpi.tui.app import AlpiApp, MentionChunk, MentionDone


class _Bubble:
    def __init__(self) -> None:
        self.text = ""
        self.replaced: list[str] = []

    def append(self, delta: str) -> None:
        self.text += delta

    def replace(self, text: str) -> None:
        self.text = text
        self.replaced.append(text)


class _Card:
    def __init__(self) -> None:
        self.finished: tuple[str, bool] | None = None

    def finish(self, output: str, ok: bool) -> None:
        self.finished = (output, ok)


def _drive_mention(monkeypatch, tmp_path: Path, frames: list[dict]) -> tuple[_Bubble, _Card, dict, SimpleNamespace]:
    async def fake_stream(home, peer_id, prompt, **kwargs):
        for frame in frames:
            yield frame

    monkeypatch.setattr(alp_mention, "execute_stream", fake_stream)
    posted: list = []
    logged: dict = {}
    session = SimpleNamespace(id="tui-sess", messages=[], log_turn=lambda **kw: logged.update(kw))
    app = SimpleNamespace(
        home=tmp_path,
        engine=SimpleNamespace(session=session, save_session=lambda: None),
        post_message=posted.append,
    )
    bubble, card = _Bubble(), _Card()

    AlpiApp._run_mention.__wrapped__(app, "bob", "ping", card, bubble)
    for message in posted:
        if isinstance(message, MentionChunk):
            AlpiApp.on_mention_chunk(app, message)
        elif isinstance(message, MentionDone):
            AlpiApp.on_mention_done(app, message)
    return bubble, card, logged, app


def test_tui_bubble_shows_the_full_final_reply_with_the_shared_history_note(monkeypatch, tmp_path: Path) -> None:
    body = "a" * 50 + "b" * 50
    bubble, card, logged, app = _drive_mention(monkeypatch, tmp_path, [
        {"kind": "chunk", "text": "a" * 50},
        {"kind": "chunk", "text": "b" * 50},
        {"kind": "final", "text": body, "history": "peer", "history_shared": True},
    ])

    expected = f"{body}\n\n{alp_mention.shared_history_note('bob')}"
    assert bubble.text == expected
    assert bubble.replaced == [expected]
    assert card.finished == (f"{expected[:60]}…", True)
    assert logged["assistant"] == expected
    assert app.engine.session.messages[-1] == {"role": "assistant", "content": expected}


def test_tui_bubble_keeps_the_plain_reply_when_the_peer_scoped_history(monkeypatch, tmp_path: Path) -> None:
    bubble, card, logged, _ = _drive_mention(monkeypatch, tmp_path, [
        {"kind": "chunk", "text": "po"},
        {"kind": "chunk", "text": "ng"},
        {"kind": "final", "text": "pong", "history": "conversation", "history_shared": False},
    ])

    assert bubble.text == "pong" and bubble.replaced == ["pong"]
    assert card.finished == ("pong", True)
    assert logged["assistant"] == "pong"


def test_tui_error_leaves_the_bubble_untouched_and_marks_the_card(monkeypatch, tmp_path: Path) -> None:
    bubble, card, logged, _ = _drive_mention(monkeypatch, tmp_path, [
        {"kind": "chunk", "text": "par"},
        {"kind": "error", "text": "target-offline"},
    ])

    assert bubble.text == "par" and bubble.replaced == []
    assert card.finished == ("target-offline", False)
    assert logged == {}
