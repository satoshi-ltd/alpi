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
