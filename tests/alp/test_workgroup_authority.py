from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest

from alpi import authority, service, tools
from alpi.alp import peers as peers_mod
from alpi.alp import server as alp_server
from alpi.alp import subscription as sub_mod
from alpi.alp import workgroup as wg_mod
from alpi.alp import workgroup_client as wc
from alpi.alp.keys import load_or_generate
from alpi.alp.peers import Peer
from alpi.host.connection_context import ConnectionContext
from alpi.host.connection_context import use as use_connection
from alpi.tools import _policy
from alpi.tools._paths import PEER_HISTORY_TOOLS

MEMBER = ConnectionContext(connection_id="c2", device_id="d2", source="remote", role="member")
PEER = ConnectionContext(connection_id="peer:carol", source="peer")
SECRET = "ANOTHER-CONVERSATION"

MEMBER_ORIGIN = {"fence": "member"}
PEER_ORIGIN = {"fence": "peer"}


@pytest.fixture
def short_tmp() -> Path:
    d = Path(tempfile.mkdtemp(prefix="alp-auth-", dir="/tmp"))
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


def _as_peer(allow):
    return _policy.use(allow, "peer 'carol'", PEER_HISTORY_TOOLS, fence_without_policy=True)


def _post(seq: int, origin=None, author: str = "m", **extra) -> dict:
    post = {"seq": seq, "from": author, "text": f"post {seq}", **extra}
    if origin is not None:
        post["origin"] = origin
    return post


def test_the_current_authority_follows_the_caller_class() -> None:
    assert authority.current() is None
    with use_connection(MEMBER):
        assert authority.current() == MEMBER_ORIGIN
    with use_connection(PEER), _as_peer(None):
        assert authority.current() == PEER_ORIGIN
    with use_connection(PEER), _as_peer(frozenset({"read_file", "search"})):
        assert authority.current() == {"fence": "allow", "allow": ["read_file", "search"]}


def test_a_claim_that_is_not_understood_fails_closed_and_cannot_widen() -> None:
    for junk in (None, "admin", {}, {"fence": "admin"}, {"fence": "allow"}, {"fence": "allow", "allow": "all"}, ["member"]):
        assert authority.sanitize(junk) == PEER_ORIGIN
    assert authority.sanitize({"fence": "allow", "allow": [" read_file ", 3, "", "read_file"]}) == {"fence": "allow", "allow": ["read_file"]}
    assert authority.of_post({"seq": 1}) is None
    assert authority.of_post({"seq": 1, "origin": None}) == PEER_ORIGIN


def test_the_weakest_authority_of_the_posts_a_turn_sees_wins() -> None:
    fold = authority.fold
    assert fold([]) is None and fold([None, None]) is None
    assert fold([None, MEMBER_ORIGIN]) == MEMBER_ORIGIN
    assert fold([MEMBER_ORIGIN, MEMBER_ORIGIN]) == MEMBER_ORIGIN
    assert fold([MEMBER_ORIGIN, PEER_ORIGIN]) == PEER_ORIGIN
    allow_a = {"fence": "allow", "allow": ["read_file", "search"]}
    allow_b = {"fence": "allow", "allow": ["search", "web_search"]}
    assert fold([allow_a, None]) == allow_a
    assert fold([allow_a, allow_b]) == {"fence": "allow", "allow": ["search"]}
    assert fold([allow_a, MEMBER_ORIGIN]) == PEER_ORIGIN


def test_what_a_turn_sees_is_the_last_posts_and_the_task_opener() -> None:
    hub = "HUB"
    opener = _post(1, MEMBER_ORIGIN, author=hub, text="@bob #task #x · do it")
    quiet = [_post(n) for n in range(2, 10)]
    assert service._wake_authority([opener, *quiet], hub) == MEMBER_ORIGIN
    stale = _post(1, PEER_ORIGIN, author="m", text="old chatter")
    assert service._wake_authority([stale, *[_post(n) for n in range(2, 10)]], hub) is None
    fresh = [_post(n) for n in range(2, 9)] + [_post(9, MEMBER_ORIGIN)]
    assert service._wake_authority(fresh, hub) == MEMBER_ORIGIN
    assert service._wake_authority([_post(n) for n in range(1, 8)], hub) is None


async def _hub_and_member(short_tmp: Path):
    hub_home = short_tmp / "alice"
    hub_home.mkdir()
    bob_home = short_tmp / "bob"
    bob_home.mkdir()
    alice_kp = load_or_generate(hub_home)
    bob_kp = load_or_generate(bob_home)
    peers_mod.add(hub_home, Peer(id="bob", pubkey=bob_kp.pubkey_b64(), allow=["workgroup.join", "workgroup.post", "workgroup.pull", "workgroup.leave"]))
    peers_mod.add(bob_home, Peer(id="alice", pubkey=alice_kp.pubkey_b64(), allow=["link.ping"]))
    wg = wg_mod.create(hub_home, name="design", hub_kp=alice_kp, member_pubkeys=[bob_kp.pubkey_b64()])
    server = alp_server.Server(home=hub_home, agent_name="alice")
    wg_mod.register(server, hub_home)
    await server.start()
    original = peers_mod.local_socket_path
    peers_mod.local_socket_path = lambda peer: server.socket_path()
    await wc.join(bob_home, "alice", wg.meta.id)
    return hub_home, bob_home, wg, server, original


def _origins(hub_home: Path, wg_id: str) -> list:
    return [entry.get("origin") for entry in wg_mod._read_transcript(wg_mod._wg_dir(hub_home, wg_id))]


@pytest.mark.asyncio
async def test_a_post_carries_the_fence_of_whoever_made_it_to_the_hub_and_back(short_tmp: Path) -> None:
    hub_home, bob_home, wg, server, original = await _hub_and_member(short_tmp)
    try:
        await wc.post(bob_home, wg.meta.id, b"from an admin")
        await wc.post(hub_home, wg.meta.id, b"hub answers 1")
        with use_connection(MEMBER):
            await wc.post(bob_home, wg.meta.id, b"from a member device")
        await wc.post(hub_home, wg.meta.id, b"hub answers 2")
        with use_connection(PEER), _as_peer(None):
            await wc.post(bob_home, wg.meta.id, b"from a fenced peer")
        await wc.post(hub_home, wg.meta.id, b"hub answers 3")
        with use_connection(PEER), _as_peer(frozenset({"read_file"})):
            await wc.post(bob_home, wg.meta.id, b"from a listed peer")
        assert _origins(hub_home, wg.meta.id) == [
            None, None, MEMBER_ORIGIN, None, PEER_ORIGIN, None, {"fence": "allow", "allow": ["read_file"]},
        ]
        await wc.pull(bob_home, wg.meta.id)
        cached = sub_mod.get(bob_home, wg.meta.id).recent_posts
        assert [p.get("origin") for p in cached] == _origins(hub_home, wg.meta.id)
    finally:
        peers_mod.local_socket_path = original
        await server.stop()


@pytest.mark.asyncio
async def test_a_hub_side_post_is_stamped_too(short_tmp: Path) -> None:
    hub_home, bob_home, wg, server, original = await _hub_and_member(short_tmp)
    try:
        await wc.post(hub_home, wg.meta.id, b"hub as admin")
        await wc.post(bob_home, wg.meta.id, b"member answers")
        with use_connection(MEMBER):
            await wc.post(hub_home, wg.meta.id, b"hub driven by a member device")
        assert _origins(hub_home, wg.meta.id) == [None, None, MEMBER_ORIGIN]
    finally:
        peers_mod.local_socket_path = original
        await server.stop()


async def _captured_env(home: Path, monkeypatch, **kwargs) -> dict:
    captured: dict = {}

    async def fake_exec(*argv, env=None, **kw):
        captured["env"] = env or {}
        raise OSError("blocked in test")

    monkeypatch.setattr(service.asyncio, "create_subprocess_exec", fake_exec)
    await service._dispatch_workgroup_turn(home, "mira", "wg1", "proj", "woken", **kwargs)
    return captured["env"]


@pytest.mark.asyncio
async def test_a_dispatched_turn_receives_the_authority_it_was_woken_under(short_tmp: Path, monkeypatch) -> None:
    home = short_tmp / "mira"
    home.mkdir()
    env = await _captured_env(home, monkeypatch, authority=MEMBER_ORIGIN)
    assert authority.from_environ(env) == MEMBER_ORIGIN
    monkeypatch.setenv(authority.ENV, authority.encode(PEER_ORIGIN))
    assert authority.ENV not in await _captured_env(home, monkeypatch)
    assert authority.ENV not in await _captured_env(home, monkeypatch, member_turn=True, pipeline=True)


def test_a_child_that_cannot_read_its_authority_is_fenced_not_promoted() -> None:
    assert authority.from_environ({}) is None
    assert authority.from_environ({authority.ENV: "not json"}) == PEER_ORIGIN
    assert authority.from_environ({authority.ENV: '{"fence": "root"}'}) == PEER_ORIGIN
    assert authority.from_environ({authority.ENV: ""}) == PEER_ORIGIN


@pytest.fixture
def home(tmp_path: Path, monkeypatch) -> Path:
    root = tmp_path / "alpi"
    workspace = tmp_path / "ws"
    (root / "sessions").mkdir(parents=True)
    workspace.mkdir()
    monkeypatch.setenv("ALPI_HOME", str(root))
    monkeypatch.chdir(workspace)
    (root / "config.yaml").write_text(f"workspace: {workspace}\n")
    (root / "sessions" / "s1.md").write_text(SECRET)
    return root


def _read_session(home: Path) -> str:
    result = tools.execute("read_file", {"path": str(home / "sessions" / "s1.md")})
    return f"{result.output}{result.error}"


def test_a_turn_under_a_fenced_authority_cannot_read_another_session(home: Path) -> None:
    assert SECRET in _read_session(home)
    with authority.apply(None):
        assert SECRET in _read_session(home)
    for fenced in (MEMBER_ORIGIN, PEER_ORIGIN, {"fence": "allow", "allow": ["web_search"]}):
        with authority.apply(fenced):
            assert SECRET not in _read_session(home), fenced
    with authority.apply({"fence": "allow", "allow": ["read_file"]}):
        assert SECRET in _read_session(home)


def test_the_fence_keeps_the_member_policy_for_members_and_the_stricter_one_for_peers(home: Path) -> None:
    with authority.apply(MEMBER_ORIGIN):
        ran = tools.execute("skill", {"action": "run", "name": "nothing"})
        assert "cannot use" not in f"{ran.output}{ran.error}"
        refused = tools.execute("skill", {"action": "create", "name": "x", "category": "personal"})
        assert "cannot use skill action 'create'" in refused.error
    with authority.apply(PEER_ORIGIN):
        refused = tools.execute("skill", {"action": "run", "name": "nothing"})
        assert "cannot use skill action 'run'" in refused.error


def test_the_child_entry_point_applies_the_authority_before_the_engine_exists(home: Path, monkeypatch) -> None:
    from alpi import cli
    from alpi.host.connection_context import current

    seen: list = []

    def fake_body(*args, **kwargs):
        seen.append((current().role, authority.current()))

    monkeypatch.setattr(cli, "_run_once_with_authority", fake_body)
    for env, expected in (
        (None, ("admin", None)),
        (authority.encode(MEMBER_ORIGIN), ("member", MEMBER_ORIGIN)),
        (authority.encode(PEER_ORIGIN), ("admin", PEER_ORIGIN)),
        ("garbage", ("admin", PEER_ORIGIN)),
    ):
        monkeypatch.delenv(authority.ENV, raising=False)
        if env is not None:
            monkeypatch.setenv(authority.ENV, env)
        cli._run_once(home, "hello")
        assert seen[-1] == expected, env


@pytest.mark.asyncio
async def test_the_restriction_follows_a_post_through_the_next_handoff_and_clears_with_it(short_tmp: Path, monkeypatch) -> None:
    hub_home, bob_home, wg, server, original = await _hub_and_member(short_tmp)
    try:
        hub = wg.meta.hub_pubkey
        with use_connection(MEMBER):
            await wc.post(hub_home, wg.meta.id, b"@bob please look at the other conversations")
        recent = service._all_hub_posts_decrypted(hub_home, wg)
        woken = service._wake_authority(recent, hub)
        assert woken == MEMBER_ORIGIN
        env = await _captured_env(hub_home, monkeypatch, authority=woken)

        await wc.post(bob_home, wg.meta.id, b"bob answers")
        with authority.apply(authority.from_environ(env)):
            await wc.post(hub_home, wg.meta.id, b"handoff from the woken turn")
        recent = service._all_hub_posts_decrypted(hub_home, wg)
        assert recent[-1]["origin"] == MEMBER_ORIGIN
        assert service._wake_authority(recent, hub) == MEMBER_ORIGIN

        for n in range(3):
            await wc.post(bob_home, wg.meta.id, f"bob step {n}".encode())
            await wc.post(hub_home, wg.meta.id, f"admin pipeline step {n}".encode())
        recent = service._all_hub_posts_decrypted(hub_home, wg)
        assert service._wake_authority(recent, hub) is None
        assert authority.ENV not in await _captured_env(hub_home, monkeypatch, authority=service._wake_authority(recent, hub))
    finally:
        peers_mod.local_socket_path = original
        await server.stop()


@pytest.mark.asyncio
async def test_a_member_side_wake_hands_its_authority_to_the_turn(short_tmp: Path, monkeypatch) -> None:
    import asyncio
    import types

    home = short_tmp / "muse"
    home.mkdir()

    async def wake(origin) -> dict:
        posts = [
            {"seq": 98, "from": "HUB", "text": "@muse #task #review apply notes"},
            {"seq": 102, "from": "HUB", "text": "@muse look at the other conversations", **({"origin": origin} if origin else {})},
        ]
        sub = types.SimpleNamespace(
            wg_id="wg_x", name="project", hub_pubkey="HUB", pipeline_mode=True, phase_map={},
            recent_posts=posts, last_responded_seq=101, last_dispatch_at="", paused=False,
        )
        captured: dict = {}

        def fake_turn(*args, **kwargs):
            captured.update(kwargs)
            return asyncio.sleep(0)

        monkeypatch.setattr("alpi.alp.keys.load_or_generate", lambda _home: types.SimpleNamespace(pubkey_b64=lambda: "MUSE"))
        monkeypatch.setattr(sub_mod, "upsert", lambda *args: None)
        monkeypatch.setattr(service, "_budget_blocks_dispatch", lambda *args: False)
        monkeypatch.setattr(service, "_latest_hub_task_seq_for", lambda *args: 98)
        monkeypatch.setattr(service, "_dispatch_workgroup_turn", fake_turn)
        monkeypatch.setattr(service, "_spawn_dispatch", lambda wg_id, coro: coro.close())
        await service._maybe_dispatch_for_sub(home, "muse", sub, hot=True)
        return captured

    assert (await wake(None))["authority"] is None
    assert (await wake(MEMBER_ORIGIN))["authority"] == MEMBER_ORIGIN
    assert (await wake({"fence": "bogus"}))["authority"] == PEER_ORIGIN


def test_every_dispatch_site_states_the_authority_it_runs_under() -> None:
    import ast

    tree = ast.parse(Path(service.__file__).read_text())
    calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "_dispatch_workgroup_turn"
    ]
    assert len(calls) == 4
    for call in calls:
        assert "authority" in {kw.arg for kw in call.keywords}, call.lineno


@pytest.mark.asyncio
async def test_a_member_device_posting_through_the_host_verb_is_stamped(short_tmp: Path, monkeypatch) -> None:
    from alpi.host import workgroup_admin

    hub_home, _bob_home, wg, server, original = await _hub_and_member(short_tmp)
    try:
        monkeypatch.setattr(workgroup_admin, "_resolve_home", lambda profile: hub_home)
        with use_connection(MEMBER):
            reply = await workgroup_admin._post({"profile": "alice", "wg_id": wg.meta.id, "text": "posted from the phone"}, None)
        assert reply["ok"] is True
        assert _origins(hub_home, wg.meta.id) == [MEMBER_ORIGIN]
    finally:
        peers_mod.local_socket_path = original
        await server.stop()


def test_a_trigger_older_than_the_last_posts_still_counts() -> None:
    posts = [_post(1), _post(2), _post(3, MEMBER_ORIGIN), *[_post(n) for n in range(4, 10)]]
    assert service._wake_authority(posts, "HUB") is None
    assert service._wake_authority(posts, "HUB", since=2) == MEMBER_ORIGIN
    assert service._wake_authority(posts, "HUB", since=3) is None


def test_a_claim_cannot_carry_oversized_tool_names() -> None:
    claim = {"fence": "allow", "allow": ["read_file", "x" * 129, "y" * 128]}
    assert authority.sanitize(claim) == {"fence": "allow", "allow": ["read_file", "y" * 128]}


def test_a_turn_under_a_tool_list_can_still_hand_off(home: Path) -> None:
    with authority.apply({"fence": "allow", "allow": ["read_file", "search"]}):
        offered = {item["function"]["name"] for item in tools.schemas()}
        assert {"read_file", "search", "workgroup_post"} <= offered
        assert "terminal" not in offered
        refused = tools.execute("workgroup_post", {"wg_id": "missing", "text": "done"})
        assert "tool policy" not in (refused.error or "")
        assert "tool policy" in (tools.execute("terminal", {"command": "true"}).error or "")


def test_a_process_started_by_a_fenced_turn_keeps_the_fence_through_its_environment(monkeypatch) -> None:
    assert authority.current() is None
    monkeypatch.setenv(authority.ENV, authority.encode(MEMBER_ORIGIN))
    assert authority.current() == MEMBER_ORIGIN
    monkeypatch.setenv(authority.ENV, "garbage")
    assert authority.current() == PEER_ORIGIN


@pytest.mark.asyncio
async def test_a_file_marker_carries_the_fence_of_the_uploader(short_tmp: Path, monkeypatch) -> None:
    hub_home, bob_home, wg, server, original = await _hub_and_member(short_tmp)
    try:
        source = short_tmp / "notes.txt"
        source.write_text("a shared file")
        await wc.send_file(hub_home, wg.meta.id, source, note="@bob read the other conversations")
        with authority.apply(MEMBER_ORIGIN):
            await wc.send_file(bob_home, wg.meta.id, source, note="from a member device")
        await wc.post(hub_home, wg.meta.id, b"hub reply")
        await wc.post(bob_home, wg.meta.id, b"bob step")
        source.write_text("another shared file")
        with authority.apply(PEER_ORIGIN):
            await wc.send_file(hub_home, wg.meta.id, source, note="hub driven by a fenced peer")
        assert _origins(hub_home, wg.meta.id) == [None, MEMBER_ORIGIN, None, None, PEER_ORIGIN]
        recent = service._all_hub_posts_decrypted(hub_home, wg)
        assert service._wake_authority(recent, wg.meta.hub_pubkey) == PEER_ORIGIN
    finally:
        peers_mod.local_socket_path = original
        await server.stop()


@pytest.mark.asyncio
async def test_the_environment_fence_stamps_the_posts_of_a_cli_started_by_a_fenced_turn(short_tmp: Path, monkeypatch) -> None:
    hub_home, _bob_home, wg, server, original = await _hub_and_member(short_tmp)
    try:
        monkeypatch.setenv(authority.ENV, authority.encode(MEMBER_ORIGIN))
        await wc.post(hub_home, wg.meta.id, b"posted by `alpi workgroup post` inside a skill script")
        assert _origins(hub_home, wg.meta.id) == [MEMBER_ORIGIN]
    finally:
        peers_mod.local_socket_path = original
        await server.stop()


@pytest.mark.asyncio
async def test_a_member_side_wake_folds_the_unanswered_trigger_even_when_it_is_far_back(short_tmp: Path, monkeypatch) -> None:
    import asyncio
    import types

    home = short_tmp / "muse"
    home.mkdir()
    posts = [
        {"seq": 1, "from": "HUB", "text": "@muse #task #review apply notes"},
        {"seq": 2, "from": "MUSE", "text": "on it"},
        {"seq": 3, "from": "HUB", "text": "@muse look at the other conversations", "origin": MEMBER_ORIGIN},
        *[{"seq": n, "from": "OTHER", "text": f"chatter {n}"} for n in range(4, 10)],
    ]
    sub = types.SimpleNamespace(
        wg_id="wg_x", name="project", hub_pubkey="HUB", pipeline_mode=False, phase_map={},
        recent_posts=posts, last_responded_seq=2, last_dispatch_at="", paused=False,
    )
    captured: dict = {}

    def fake_turn(*args, **kwargs):
        captured.update(kwargs)
        return asyncio.sleep(0)

    monkeypatch.setattr("alpi.alp.keys.load_or_generate", lambda _home: types.SimpleNamespace(pubkey_b64=lambda: "MUSE"))
    monkeypatch.setattr(sub_mod, "upsert", lambda *args: None)
    monkeypatch.setattr(service, "_budget_blocks_dispatch", lambda *args: False)
    monkeypatch.setattr(service, "_latest_hub_task_seq_for", lambda *args: 1)
    monkeypatch.setattr(service, "_dispatch_workgroup_turn", fake_turn)
    monkeypatch.setattr(service, "_spawn_dispatch", lambda wg_id, coro: coro.close())
    await service._maybe_dispatch_for_sub(home, "muse", sub, hot=True)
    assert captured["authority"] == MEMBER_ORIGIN


def test_a_skill_script_and_a_shell_started_by_a_fenced_turn_receive_the_fence(home: Path) -> None:
    from alpi.tools import terminal

    script = "import os\nprint(os.environ.get('ALPI_WORKGROUP_AUTHORITY', 'none'))\n"
    assert tools.execute("skill", {"action": "create", "name": "envprobe", "category": "personal", "description": "Probe.", "body": "## When to use\nAlways.\n"}).ok
    assert tools.execute("skill", {"action": "add_file", "name": "envprobe", "subdir": "scripts", "filename": "run.py", "content": script}).ok
    assert "none" in tools.execute("skill", {"action": "run", "name": "envprobe"}).output
    with authority.apply(MEMBER_ORIGIN):
        assert '"fence":"member"' in tools.execute("skill", {"action": "run", "name": "envprobe"}).output
    assert authority.ENV not in terminal._build_subprocess_env()
    with authority.apply({"fence": "allow", "allow": ["terminal"]}):
        assert authority.from_environ(terminal._build_subprocess_env()) == {"fence": "allow", "allow": ["terminal", "workgroup_post"]}


def test_every_cursor_aware_dispatch_site_hands_the_cursor_to_the_fold() -> None:
    import ast

    tree = ast.parse(Path(service.__file__).read_text())
    folds = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "_wake_authority"
    ]
    assert sorted(len(call.args) for call in folds) == [2, 2, 3, 3]
