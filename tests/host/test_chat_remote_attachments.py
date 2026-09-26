from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from alpi.host import chat
from alpi.host.attachments_rpc import _stage_root
from alpi.host.connection_context import ConnectionContext, use
from alpi.host.server import Server

MEMBER = ConnectionContext("conn", "dev", "remote", "member")
REMOTE_ADMIN = ConnectionContext("conn", "dev", "remote", "admin")


class _RecordingEngine:
    seen: list = []

    def __init__(self, *, home: Path, cfg) -> None:  # noqa: ANN001
        self.home = home
        self.session = SimpleNamespace(id="s1", subdir="sessions")

    def run_turn(self, text, emit, **kwargs) -> None:  # noqa: ANN001
        from alpi.engine import AgentEvent
        _RecordingEngine.seen.append(kwargs.get("attachments"))
        emit(AgentEvent(kind="assistant_done", text="ok", final=True))

    def request_interrupt(self, reason: str = "unknown") -> None:
        return None

    def save_session(self) -> None:
        return None


@pytest.fixture
def home(monkeypatch, tmp_path: Path) -> Path:
    from alpi import config as cfg_mod, home as home_mod
    import alpi.engine
    monkeypatch.setattr(home_mod, "_ROOT", tmp_path)
    monkeypatch.setattr(chat, "_resolve_home", lambda profile: tmp_path)
    monkeypatch.setattr(cfg_mod, "load", lambda h: SimpleNamespace(model="x"))
    monkeypatch.setattr(alpi.engine, "Engine", _RecordingEngine)
    _RecordingEngine.seen = []
    (tmp_path / ".env").write_text("OPENROUTER_API_KEY=sk-secret\n")
    return tmp_path


def _staged(home: Path, name: str = "notes.md") -> Path:
    p = _stage_root(home) / "0123456789abcdef" / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("# Notes\n")
    return p


async def _send(home: Path, attachments) -> list[dict]:  # noqa: ANN001
    frames: list[dict] = []

    async def send_frame(frame: dict) -> None:
        frames.append(frame)

    await chat._data_chat_send(
        {"profile": "default", "text": "read this", "request_id": "r1", "attachments": attachments},
        Server(home), send_frame,
    )
    return frames


def _refused(frames: list[dict]) -> bool:
    return any(f.get("event") == "error" and "host.attachments.stage" in f.get("text", "") for f in frames)


@pytest.mark.asyncio
@pytest.mark.parametrize("ctx", (MEMBER, REMOTE_ADMIN))
async def test_a_remote_device_cannot_attach_a_file_it_did_not_upload(home: Path, ctx) -> None:
    with use(ctx):
        frames = await _send(home, [{"path": str(home / ".env"), "mime": "text/plain"}])
    assert _refused(frames)
    assert _RecordingEngine.seen == []


@pytest.mark.asyncio
async def test_a_remote_device_attaches_what_it_staged(home: Path) -> None:
    staged = _staged(home)
    with use(MEMBER):
        frames = await _send(home, [{"path": str(staged), "mime": "text/markdown"}])
    assert not _refused(frames)
    assert _RecordingEngine.seen == [[{"path": str(staged), "mime": "text/markdown"}]]


@pytest.mark.asyncio
async def test_a_symlink_in_the_staging_area_does_not_reach_outside_it(home: Path) -> None:
    link = _stage_root(home) / "0123456789abcdef" / "notes.md"
    link.parent.mkdir(parents=True)
    link.symlink_to(home / ".env")
    with use(MEMBER):
        frames = await _send(home, [{"path": str(link), "mime": "text/plain"}])
    assert _refused(frames)
    assert _RecordingEngine.seen == []


@pytest.mark.asyncio
@pytest.mark.parametrize("attachments", (
    {"path": "x"},
    [{"name": "no-path"}],
    ["not-a-dict"],
    "staging-dir",
    "dotdot",
    "nul",
))
async def test_a_malformed_remote_attachment_is_refused(home: Path, attachments) -> None:
    staged = _staged(home)
    if attachments == "staging-dir":
        attachments = [{"path": str(staged.parent)}]
    elif attachments == "dotdot":
        attachments = [{"path": str(staged.parent / ".." / ".." / ".." / ".." / ".env")}]
    elif attachments == "nul":
        attachments = [{"path": f"{staged}\x00"}]
    with use(MEMBER):
        frames = await _send(home, attachments)
    assert _refused(frames)
    assert _RecordingEngine.seen == []


@pytest.mark.asyncio
@pytest.mark.parametrize("source", ("local", "local-delegate"))
async def test_the_local_desktop_and_delegate_still_attach_a_path_from_the_disk(home: Path, tmp_path_factory, source) -> None:
    local = tmp_path_factory.mktemp("desktop") / "photo-notes.md"
    local.write_text("# Local\n")
    with use(ConnectionContext("conn", "dev", source, "member")):
        frames = await _send(home, [{"path": str(local), "mime": "text/markdown"}])
    assert not _refused(frames)
    assert _RecordingEngine.seen == [[{"path": str(local), "mime": "text/markdown"}]]
