from pathlib import Path

import pytest

from alpi.alp.mention import Result
from alpi.tools import peer


@pytest.mark.parametrize(
    "result",
    [
        Result(ok=False, error="-32007 target-busy", transient=True),
        Result(ok=True, reply="[error] provider unavailable", transient=True),
    ],
)
def test_peer_tool_preserves_transient_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, result: Result,
) -> None:
    async def fake_execute(*args, **kwargs):
        return result

    monkeypatch.setattr(peer, "get_home", lambda: tmp_path)
    monkeypatch.setattr(peer.alp_mention, "execute", fake_execute)

    output = peer.PeerTool().run(peer_id="bob", prompt="ping")

    assert output.ok is result.ok
    assert output.transient is True


@pytest.mark.parametrize("shared", [True, False])
def test_peer_tool_says_when_the_peer_shares_history_across_conversations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, shared: bool,
) -> None:
    async def fake_execute(*args, **kwargs):
        return Result(ok=True, reply="pong", history_shared=shared)

    monkeypatch.setattr(peer, "get_home", lambda: tmp_path)
    monkeypatch.setattr(peer.alp_mention, "execute", fake_execute)

    output = peer.PeerTool().run(peer_id="bob", prompt="ping")

    assert output.ok is True
    assert ("runs an older alpi" in output.output) is shared
