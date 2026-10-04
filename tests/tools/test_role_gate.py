from alpi.host.connection_context import ConnectionContext, use
from alpi.tools import execute, schemas


MEMBER = ConnectionContext(connection_id="c1", device_id="d1", source="remote", role="member")
ADMIN = ConnectionContext(connection_id="c1", device_id="d1", source="remote", role="admin")


def _actions(schema, name):
    tool = next(item for item in schema if item["function"]["name"] == name)
    return set(tool["function"]["parameters"]["properties"]["action"]["enum"])


def test_member_sees_every_nonrestricted_tool():
    with use(ADMIN):
        admin_names = {item["function"]["name"] for item in schemas()}
    with use(MEMBER):
        member_names = {item["function"]["name"] for item in schemas()}
    assert member_names == admin_names


def test_member_schema_keeps_only_nonmutating_actions():
    with use(MEMBER):
        schema = schemas()
    assert _actions(schema, "skill") == {"list", "view", "validate"}
    assert _actions(schema, "memory") == {"read", "promotion_list"}
    assert _actions(schema, "schedule") == {"list"}


def test_member_cannot_mutate_admin_owned_resources():
    calls = (
        ("skill", {"action": "create", "name": "x", "category": "personal"}),
        ("memory", {"action": "add", "target": "MEMORY.md", "content": "x"}),
        ("schedule", {"action": "add", "prompt": "x"}),
    )
    with use(MEMBER):
        results = [execute(name, args) for name, args in calls]
    assert all(not result.ok for result in results)
    assert all("cannot use" in (result.error or "") for result in results)


def test_member_blocks_new_actions_on_restricted_tools():
    with use(MEMBER):
        result = execute("skill", {"action": "future_action"})
    assert not result.ok
    assert "cannot use" in (result.error or "")


def test_a_fenced_turn_never_runs_skill_scripts_or_changes_skills_and_jobs(tmp_home):
    from alpi.tools import _policy
    from alpi.tools._paths import PEER_HISTORY_TOOLS

    peer = ConnectionContext(connection_id="peer:carol", source="peer")
    calls = (
        ("skill", {"action": "run", "name": "x"}),
        ("skill", {"action": "test", "name": "x"}),
        ("skill", {"action": "invoke", "name": "x"}),
        ("skill", {"action": "create", "name": "x", "category": "personal"}),
        ("schedule", {"action": "add", "prompt": "x"}),
        ("schedule", {"action": "fire", "id": "x"}),
        ("workflow", {"steps": [{"id": "a", "tool": "skill", "arguments": {"action": "run", "name": "x"}}]}),
    )
    for context, policy in (
        (MEMBER, _policy.use(None, "")),
        (peer, _policy.use(None, "peer 'carol'", PEER_HISTORY_TOOLS, fence_without_policy=True)),
    ):
        with use(context), policy:
            for name, args in calls:
                result = execute(name, args)
                assert not result.ok and "cannot use" in f"{result.output}{result.error}", (context.role, name, args)
            assert _actions(schemas(), "skill") == {"list", "view", "validate"}
    granted = _policy.use(frozenset({"skill"}), "peer 'dave'", PEER_HISTORY_TOOLS, fence_without_policy=True)
    with use(peer), granted:
        assert "cannot use" not in (execute("skill", {"action": "run", "name": "x"}).error or "")
        assert "run" in _actions(schemas(), "skill")
