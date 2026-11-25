from __future__ import annotations

import json
import secrets
import shutil
import threading
from pathlib import Path

import pytest

from alpi import authority, tools
from alpi.config import Config, ToolsConfig
from alpi.engine import Engine
from alpi.host import attachments_rpc, chat
from alpi.host.connection_context import ConnectionContext
from alpi.host.connection_context import use as use_connection
from alpi.tools import _policy, _state, knowledge_base
from alpi.tools._paths import PEER_HISTORY_TOOLS, _member_denied_area, is_read_denied, resolve_path

ADMIN = ConnectionContext(connection_id="c1", device_id="d1", source="remote", role="admin")
MEMBER = ConnectionContext(connection_id="c2", device_id="d2", source="remote", role="member")
OTHER = ConnectionContext(connection_id="c3", device_id="d3", source="remote", role="member")
PEER = ConnectionContext(connection_id="peer:carol", source="peer")

MINE = "MY-OWN-BOOKINGS"
THEIRS = "ANOTHER-CONNECTIONS-BOOKINGS"
FENCE = "cannot read the profile host/ area"


@pytest.fixture
def home(tmp_path: Path, monkeypatch) -> Path:
    root = tmp_path / "alpi"
    workspace = tmp_path / "ws"
    (root / "host").mkdir(parents=True)
    workspace.mkdir()
    monkeypatch.setenv("ALPI_HOME", str(root))
    monkeypatch.chdir(workspace)
    (root / "config.yaml").write_text(f"workspace: {workspace}\n")
    (root / "host" / "connections.yaml").write_text("token: HOST-ADMIN-TOKEN\n")
    _state.reset_turn_attachments()
    yield root
    _state.reset_turn_attachments()


def _stage(home: Path, owner: ConnectionContext, name: str, content: str | bytes, area: Path | None = None) -> Path:
    directory = (area or attachments_rpc._stage_root(home)) / secrets.token_hex(8)
    directory.mkdir(parents=True)
    with use_connection(owner):
        attachments_rpc._record_owner(directory)
    path = directory / name
    path.write_bytes(content if isinstance(content, bytes) else content.encode())
    return path


def _attach(*paths: Path) -> None:
    _state.set_turn_attachments([{"name": p.name, "path": str(p), "mime": "text/csv"} for p in paths])


def _text(result) -> str:
    return f"{result.output}{result.error}"


def test_a_member_reads_and_searches_the_upload_it_attached_to_this_turn(home: Path) -> None:
    upload = _stage(home, MEMBER, "data.csv", f"room,amount\nsuite,{MINE}\n")
    _attach(upload)
    with use_connection(MEMBER):
        assert MINE in tools.execute("read_file", {"path": str(upload)}).output
        assert MINE in tools.execute("search", {"pattern": MINE, "path": str(upload)}).output
        source, meta = knowledge_base._validated_source("", str(upload), ocr=False)
        folder = tools.execute("search", {"pattern": MINE, "path": str(upload.parent)})
    assert source == upload.resolve() and meta.name == "data.csv"
    assert not folder.ok and FENCE in folder.error and MINE not in _text(folder)


def test_a_member_reaches_the_image_it_attached_past_the_fence(home: Path) -> None:
    shot = _stage(home, MEMBER, "shot.png", b"not really a png")
    with use_connection(MEMBER):
        assert FENCE in tools.execute("read_image", {"path": str(shot), "question": "what is it?"}).error
        _attach(shot)
        error = tools.execute("read_image", {"path": str(shot), "question": "what is it?"}).error
    assert FENCE not in error and "supported image format" in error


def test_the_upload_stops_being_readable_when_the_turn_is_over(home: Path) -> None:
    upload = _stage(home, MEMBER, "data.csv", MINE)
    _attach(upload)
    with use_connection(MEMBER):
        assert tools.execute("read_file", {"path": str(upload)}).ok
        _state.reset_turn_attachments()
        refused = tools.execute("read_file", {"path": str(upload)})
        assert MINE not in _text(tools.execute("search", {"pattern": MINE, "path": str(upload)}))
        assert is_read_denied(upload)
    assert not refused.ok and FENCE in refused.error and MINE not in _text(refused)


def test_a_member_cannot_read_another_connections_upload_even_when_its_turn_names_it(home: Path) -> None:
    theirs = _stage(home, OTHER, "data.csv", THEIRS)
    mine = _stage(home, MEMBER, "mine.csv", MINE)
    _attach(mine, theirs)
    with use_connection(MEMBER):
        assert MINE in tools.execute("read_file", {"path": str(mine)}).output
        refused = tools.execute("read_file", {"path": str(theirs)})
        found = _text(tools.execute("search", {"pattern": "BOOKINGS", "path": str(theirs)}))
        swept = _text(tools.execute("search", {"pattern": "BOOKINGS", "path": str(attachments_rpc._stage_root(home))}))
        with pytest.raises(ValueError, match="host/ area"):
            knowledge_base._validated_source("", str(theirs), ocr=False)
    assert not refused.ok and FENCE in refused.error
    assert THEIRS not in found and THEIRS not in swept and FENCE in swept


def test_the_exemption_covers_the_attached_file_and_nothing_beside_it(home: Path) -> None:
    upload = _stage(home, MEMBER, "data.csv", MINE)
    sibling = upload.parent / "notes.txt"
    sibling.write_text("left beside the upload")
    _attach(upload)
    with use_connection(MEMBER):
        for path in (upload.parent / attachments_rpc._OWNER_FILE, sibling, home / "host" / "connections.yaml"):
            refused = tools.execute("read_file", {"path": str(path)})
            assert not refused.ok and FENCE in refused.error, path
        climbed = tools.execute("read_file", {"path": f"{upload.parent}/../../../connections.yaml"})
        folder = tools.execute("search", {"pattern": ".", "path": str(home / "host"), "target": "files"})
    assert not climbed.ok and "HOST-ADMIN-TOKEN" not in _text(climbed)
    assert not folder.ok and FENCE in folder.error


@pytest.mark.parametrize("ripgrep", [True, False])
def test_a_search_from_outside_finds_the_attached_upload_and_nothing_around_it(home: Path, tmp_path: Path, monkeypatch, ripgrep: bool) -> None:
    if ripgrep and shutil.which("rg") is None:
        pytest.skip("ripgrep is not installed; the stdlib case covers the same rule")
    if not ripgrep:
        monkeypatch.setattr("alpi.tools.search.shutil.which", lambda _name: None)
    mine = _stage(home, MEMBER, "mine.csv", MINE)
    (mine.parent / "notes.csv").write_text("LEFT-BESIDE-BOOKINGS")
    _stage(home, OTHER, "theirs.csv", THEIRS)
    _attach(mine)
    with use_connection(MEMBER):
        content = tools.execute("search", {"pattern": "BOOKINGS", "path": str(tmp_path)})
        files = tools.execute("search", {"pattern": "*.csv", "path": str(tmp_path), "target": "files"})
        markers = tools.execute("search", {"pattern": "connection_id", "path": str(tmp_path)})
    assert MINE in content.output and THEIRS not in content.output and "LEFT-BESIDE" not in content.output
    assert "mine.csv" in files.output and "theirs.csv" not in files.output and "notes.csv" not in files.output
    assert "connection_id" not in markers.output


def test_a_member_cannot_change_or_remove_the_upload_it_may_read(home: Path) -> None:
    upload = _stage(home, MEMBER, "data.csv", MINE)
    _attach(upload)
    with use_connection(MEMBER):
        assert not tools.execute("write_file", {"path": str(upload), "content": "rewritten"}).ok
        assert not tools.execute("edit_file", {"path": str(upload), "old_string": MINE, "new_string": "x"}).ok
        assert not tools.execute("delete_file", {"path": str(upload)}).ok
        with pytest.raises(ValueError):
            resolve_path(str(upload), for_write=True)
        assert _member_denied_area(upload, upload.resolve(), for_write=False) is None
        assert _member_denied_area(upload, upload.resolve(), for_write=True) == "host"
    assert upload.read_text() == MINE


def test_an_attachment_outside_the_upload_area_opens_nothing_under_host(home: Path) -> None:
    token = home / "host" / "connections.yaml"
    kept = _stage(home, MEMBER, "data.csv", MINE, area=home / "host" / "attachments" / "keep")
    loose = attachments_rpc._stage_root(home) / "loose.csv"
    loose.parent.mkdir(parents=True, exist_ok=True)
    loose.write_text(MINE)
    _attach(token, kept, loose)
    with use_connection(MEMBER):
        for path in (token, kept, loose):
            refused = tools.execute("read_file", {"path": str(path)})
            assert not refused.ok and FENCE in refused.error, path
            assert "HOST-ADMIN-TOKEN" not in _text(refused) and MINE not in _text(refused)


def test_the_marker_of_an_upload_is_never_an_attachment_a_member_reads(home: Path) -> None:
    upload = _stage(home, MEMBER, "data.csv", MINE)
    marker = upload.parent / attachments_rpc._OWNER_FILE
    shouted = upload.parent / attachments_rpc._OWNER_FILE.upper()
    _attach(upload, marker, shouted)
    with use_connection(MEMBER):
        refused = tools.execute("read_file", {"path": str(marker)})
        by_case = tools.execute("read_file", {"path": str(shouted)})
        assert chat._unstaged_attachment(home, [{"path": str(upload)}]) is None
        assert chat._unstaged_attachment(home, [{"path": str(marker)}]) == str(marker)
        assert chat._unstaged_attachment(home, [{"path": str(shouted)}]) == str(shouted)
    assert not refused.ok and FENCE in refused.error and "connection_id" not in _text(refused)
    assert not by_case.ok and "connection_id" not in _text(by_case)


def test_an_upload_staged_under_another_profile_stays_closed(home: Path) -> None:
    other_profile = home / "profiles" / "b"
    elsewhere = _stage(other_profile, MEMBER, "data.csv", MINE)
    _attach(elsewhere)
    with use_connection(MEMBER):
        refused = tools.execute("read_file", {"path": str(elsewhere)})
    assert not refused.ok and FENCE in refused.error and MINE not in _text(refused)


def test_the_upload_is_recognised_through_a_linked_home(home: Path, tmp_path: Path) -> None:
    upload = _stage(home, MEMBER, "data.csv", MINE)
    link = tmp_path / "linked-home"
    link.symlink_to(home, target_is_directory=True)
    through_link = link / upload.relative_to(home)
    _attach(through_link)
    with use_connection(MEMBER):
        assert MINE in tools.execute("read_file", {"path": str(through_link)}).output
        assert MINE in tools.execute("read_file", {"path": str(upload)}).output
        assert not tools.execute("read_file", {"path": str(link / "host" / "connections.yaml")}).ok


@pytest.mark.parametrize("fence", [{"fence": "member"}, {"fence": "peer"}, {"fence": "peer", "allow": ["read_file"]}])
def test_a_turn_fenced_by_a_workgroup_post_reads_no_upload_the_local_owner_staged(home: Path, fence: dict) -> None:
    upload = _stage(home, ConnectionContext(), "data.csv", MINE)
    _attach(upload)
    with authority.apply(fence):
        refused = tools.execute("read_file", {"path": str(upload)})
    assert not refused.ok and MINE not in _text(refused)


def test_two_turns_at_once_each_read_their_own_upload_only(home: Path) -> None:
    uploads = {MEMBER: _stage(home, MEMBER, "mine.csv", MINE), OTHER: _stage(home, OTHER, "theirs.csv", THEIRS)}
    ready = threading.Barrier(2)
    seen: dict[str, tuple[str, str]] = {}
    failures: list[BaseException] = []

    def turn(ctx: ConnectionContext) -> None:
        try:
            _state.set_turn_attachments([{"name": uploads[ctx].name, "path": str(uploads[ctx]), "mime": "text/csv"}])
            ready.wait(timeout=5)
            with use_connection(ctx):
                seen[ctx.connection_id] = (
                    _text(tools.execute("read_file", {"path": str(uploads[MEMBER])})),
                    _text(tools.execute("read_file", {"path": str(uploads[OTHER])})),
                )
        except BaseException as exc:  # noqa: BLE001
            failures.append(exc)

    threads = [threading.Thread(target=turn, args=(ctx,)) for ctx in uploads]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
    assert not failures and sorted(seen) == ["c2", "c3"]
    assert MINE in seen["c2"][0] and THEIRS not in seen["c2"][1] and FENCE in seen["c2"][1]
    assert THEIRS in seen["c3"][1] and MINE not in seen["c3"][0] and FENCE in seen["c3"][0]


def test_an_upload_reached_through_a_link_is_judged_by_where_it_ends(home: Path, tmp_path: Path) -> None:
    theirs = _stage(home, OTHER, "data.csv", THEIRS)
    mine = _stage(home, MEMBER, "mine.csv", MINE)
    (tmp_path / "ws" / "to-theirs.csv").symlink_to(theirs)
    (tmp_path / "ws" / "to-mine.csv").symlink_to(mine)
    disguised = mine.parent / "alias.csv"
    disguised.symlink_to(home / "host" / "connections.yaml")
    _attach(mine, tmp_path / "ws" / "to-theirs.csv", disguised)
    with use_connection(MEMBER):
        assert MINE in tools.execute("read_file", {"path": "to-mine.csv"}).output
        assert THEIRS not in _text(tools.execute("read_file", {"path": "to-theirs.csv"}))
        assert "HOST-ADMIN-TOKEN" not in _text(tools.execute("read_file", {"path": str(disguised)}))


def test_an_upload_whose_owner_cannot_be_verified_stays_closed(home: Path) -> None:
    unmarked = _stage(home, MEMBER, "data.csv", MINE)
    (unmarked.parent / attachments_rpc._OWNER_FILE).unlink()
    broken = _stage(home, MEMBER, "broken.csv", MINE)
    (broken.parent / attachments_rpc._OWNER_FILE).write_text("{not json")
    _attach(unmarked, broken)
    with use_connection(MEMBER):
        for path in (unmarked, broken):
            refused = tools.execute("read_file", {"path": str(path)})
            assert not refused.ok and MINE not in _text(refused), path


def test_a_device_scoped_member_reads_its_own_upload_and_not_a_sibling_devices(home: Path) -> None:
    scoped = ConnectionContext(connection_id="c2", device_id="d2", source="remote", role="member", session_scope="device")
    sibling = ConnectionContext(connection_id="c2", device_id="d9", source="remote", role="member", session_scope="device")
    mine = _stage(home, scoped, "mine.csv", MINE)
    theirs = _stage(home, sibling, "theirs.csv", THEIRS)
    _attach(mine, theirs)
    with use_connection(scoped):
        assert MINE in tools.execute("read_file", {"path": str(mine)}).output
        assert THEIRS not in _text(tools.execute("read_file", {"path": str(theirs)}))


def test_a_peer_without_a_tool_policy_reads_no_upload_even_one_its_turn_names(home: Path) -> None:
    upload = _stage(home, MEMBER, "data.csv", MINE)
    _attach(upload)
    with use_connection(PEER), _policy.use(None, "peer 'carol'", PEER_HISTORY_TOOLS, fence_without_policy=True):
        refused = tools.execute("read_file", {"path": str(upload)})
    assert not refused.ok and MINE not in _text(refused)


def test_a_turn_the_local_owner_delegates_for_a_connection_gets_no_opening(home: Path) -> None:
    delegated = ConnectionContext(connection_id="c2", device_id="d2", source="local-delegate", role="member")
    upload = _stage(home, MEMBER, "data.csv", MINE)
    _attach(upload)
    with use_connection(delegated):
        refused = tools.execute("read_file", {"path": str(upload)})
    assert not refused.ok and FENCE in refused.error and MINE not in _text(refused)


def test_only_a_path_given_as_text_counts_as_an_attachment_of_the_turn(home: Path) -> None:
    upload = _stage(home, MEMBER, "data.csv", MINE)
    _state.set_turn_attachments([{"path": 123}, {"path": ""}, {"name": "no path"}, "loose", {"path": str(upload)}])
    assert _state.turn_attachment_paths() == {upload.resolve()}


def test_an_admin_still_reads_any_staged_upload(home: Path) -> None:
    upload = _stage(home, MEMBER, "data.csv", MINE)
    with use_connection(ADMIN):
        assert MINE in tools.execute("read_file", {"path": str(upload)}).output


def _final(text: str, tool_calls=None):
    return {"final": True, "text": text, "input_tokens": 10, "output_tokens": 5, "cost_usd": 0.0, "tool_calls": tool_calls or []}


def _stub_stream(monkeypatch, scripted):
    state = {"i": 0, "seen": []}

    def fake_stream(messages, tools, **_kwargs):
        state["seen"].append([dict(m) for m in messages])
        chunk = dict(scripted[state["i"]]) if state["i"] < len(scripted) else _final("")
        state["i"] += 1
        text = chunk.pop("text", "")
        if text:
            yield {"text_delta": text}
        yield chunk

    monkeypatch.setattr("alpi.llm.stream", fake_stream)
    return state


def _last_tool_result(state) -> str:
    return [str(m.get("content", "")) for m in state["seen"][-1] if m.get("role") == "tool"][-1]


def test_a_member_turn_reads_its_upload_with_the_file_tools_and_the_next_turn_does_not(home: Path, monkeypatch) -> None:
    upload = _stage(home, MEMBER, "data.csv", f"room,amount\nsuite,{MINE}\n")
    monkeypatch.setattr("alpi.engine._maybe_load_mcps", lambda _cfg: [])
    monkeypatch.setattr(Engine, "_build_system_prompt", lambda self: "you are alpi")
    monkeypatch.setattr("alpi.ctx_window.resolve", lambda _h, _c, _m: 400_000)
    monkeypatch.setattr("alpi.ledger.check", lambda *a, **kw: None)
    monkeypatch.setattr("alpi.ledger.record", lambda *a, **kw: None)
    monkeypatch.setattr("alpi.attachments.build_content_parts", lambda text, *_a, **_kw: text)
    cfg = Config(home=home, model="gpt-5.4-mini", tools=ToolsConfig(max_steps_per_turn=6), raw={})
    with use_connection(MEMBER):
        engine = Engine(home=home, cfg=cfg)
    read = {"id": "t1", "name": "read_file", "arguments": json.dumps({"path": str(upload)})}

    first = _stub_stream(monkeypatch, [_final("reading", tool_calls=[read]), _final("done")])
    engine.run_turn("check this export", emit=lambda _e: None, attachments=[{"path": str(upload), "name": "data.csv", "mime": "text/csv"}])
    assert MINE in _last_tool_result(first) and FENCE not in _last_tool_result(first)
    assert _state.get_turn_attachments() == []
    with use_connection(MEMBER):
        assert FENCE in tools.execute("read_file", {"path": str(upload)}).error

    second = _stub_stream(monkeypatch, [_final("reading", tool_calls=[{**read, "id": "t2"}]), _final("done")])
    engine.run_turn("and again", emit=lambda _e: None)
    assert MINE not in _last_tool_result(second) and FENCE in _last_tool_result(second)


def test_a_turn_that_breaks_still_leaves_no_attachment_behind(home: Path, monkeypatch) -> None:
    upload = _stage(home, MEMBER, "data.csv", MINE)
    monkeypatch.setattr("alpi.engine._maybe_load_mcps", lambda _cfg: [])
    cfg = Config(home=home, model="gpt-5.4-mini", tools=ToolsConfig(max_steps_per_turn=6), raw={})
    with use_connection(MEMBER):
        engine = Engine(home=home, cfg=cfg)

    def broken(self, *_args, **_kwargs):
        _state.set_turn_attachments([{"name": "data.csv", "path": str(upload), "mime": "text/csv"}])
        raise KeyError("the turn broke")

    monkeypatch.setattr(Engine, "_run_turn_locked", broken)
    with pytest.raises(KeyError):
        engine.run_turn("check this export", emit=lambda _e: None)
    assert _state.get_turn_attachments() == []
