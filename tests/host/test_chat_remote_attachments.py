from __future__ import annotations

import json
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


def _staged(home: Path, name: str = "notes.md", owner: tuple[str, str] | None = ("conn", "dev")) -> Path:
    p = _stage_root(home) / "0123456789abcdef" / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("# Notes\n")
    if owner is not None:
        (p.parent / ".owner").write_text(json.dumps({"connection_id": owner[0], "device_id": owner[1]}))
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


def _ctx(connection: str, device: str, scope: str, role: str = "member") -> ConnectionContext:
    return ConnectionContext(connection, device, "remote", role, session_scope=scope)


@pytest.mark.asyncio
@pytest.mark.parametrize("scope", ("connection", "device"))
async def test_a_member_cannot_attach_another_connections_upload(home: Path, scope) -> None:
    staged = _staged(home, owner=("conn-a", "dev-a"))
    with use(_ctx("conn-b", "dev-a", scope)):
        frames = await _send(home, [{"path": str(staged), "mime": "text/markdown"}])
    assert _refused(frames)
    assert _RecordingEngine.seen == []


@pytest.mark.asyncio
async def test_a_sibling_device_attaches_a_connection_upload_only_under_connection_scope(home: Path) -> None:
    staged = _staged(home, owner=("conn", "dev-a"))
    attachments = [{"path": str(staged), "mime": "text/markdown"}]
    with use(_ctx("conn", "dev-b", "device")):
        assert _refused(await _send(home, attachments))
    assert _RecordingEngine.seen == []
    with use(_ctx("conn", "dev-b", "connection")):
        assert not _refused(await _send(home, attachments))
    assert _RecordingEngine.seen == [attachments]


@pytest.mark.asyncio
async def test_a_device_scoped_member_attaches_its_own_and_its_connection_shared_uploads(home: Path) -> None:
    own = _staged(home, owner=("conn", "dev-a"))
    with use(_ctx("conn", "dev-a", "device")):
        assert not _refused(await _send(home, [{"path": str(own)}]))
    shared = _stage_root(home) / "fedcba9876543210" / "shared.md"
    shared.parent.mkdir(parents=True)
    shared.write_text("# Shared\n")
    (shared.parent / ".owner").write_text(json.dumps({"connection_id": "conn", "device_id": ""}))
    with use(_ctx("conn", "dev-b", "device")):
        assert not _refused(await _send(home, [{"path": str(shared)}]))


@pytest.mark.asyncio
@pytest.mark.parametrize("marker", (None, "{", "[]", "{}", "null", '{"connection_id": [], "device_id": ""}', "unreadable"))
async def test_a_member_cannot_attach_an_upload_whose_owner_cannot_be_verified(home: Path, monkeypatch, marker) -> None:
    staged = _staged(home, owner=None if marker is None else ("conn", "dev"))
    path = staged.parent / ".owner"
    if marker == "unreadable":
        real = Path.read_text

        def fail_marker(self, *args, **kwargs):
            if self.name == ".owner":
                raise PermissionError("cannot read owner")
            return real(self, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", fail_marker)
    elif marker is not None:
        path.write_text(marker)
    with use(MEMBER):
        frames = await _send(home, [{"path": str(staged), "mime": "text/markdown"}])
    assert _refused(frames)
    assert _RecordingEngine.seen == []


@pytest.mark.asyncio
@pytest.mark.parametrize("owner", (None, ("other", "dev")))
async def test_a_remote_admin_still_attaches_any_upload_in_the_staging_area(home: Path, owner) -> None:
    staged = _staged(home, owner=owner)
    with use(REMOTE_ADMIN):
        frames = await _send(home, [{"path": str(staged), "mime": "text/markdown"}])
    assert not _refused(frames)
    assert _RecordingEngine.seen == [[{"path": str(staged), "mime": "text/markdown"}]]


@pytest.mark.asyncio
async def test_a_remote_caller_with_an_unknown_role_is_treated_as_a_member(home: Path) -> None:
    staged = _staged(home, owner=("other", "dev"))
    with use(ConnectionContext("conn", "dev", "remote", "")):
        frames = await _send(home, [{"path": str(staged), "mime": "text/markdown"}])
    assert _refused(frames)
    assert _RecordingEngine.seen == []


@pytest.mark.asyncio
async def test_a_remote_message_with_more_attachments_than_the_cap_is_refused_before_any_file_is_read(home: Path, monkeypatch) -> None:
    from alpi import attachments as att

    staged = _staged(home)
    reads: list[Path] = []
    real_owner = chat._owns_staged_upload
    monkeypatch.setattr(chat, "_owns_staged_upload", lambda h, r: reads.append(r) or real_owner(h, r))
    with use(MEMBER):
        frames = await _send(home, [{"path": str(staged)}] * (att.MAX_ATTACHMENTS + 1))
    assert _refused(frames)
    assert reads == []
    assert _RecordingEngine.seen == []
