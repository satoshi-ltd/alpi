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
    assert _actions(schema, "skill") == {"list", "view", "validate", "run", "invoke"}
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


def _scripted_skill(tmp_home):
    made = execute("skill", {"action": "create", "name": "echo-skill", "category": "personal", "description": "Echo.", "body": "## When to use\nTest.\n"})
    assert made.ok, made.error
    added = execute("skill", {"action": "add_file", "name": "echo-skill", "subdir": "scripts", "filename": "run.py", "content": "print('hello from the skill')\n"})
    assert added.ok, added.error


def test_a_member_runs_and_invokes_existing_skills_but_never_tests_or_changes_them(tmp_home):
    _scripted_skill(tmp_home)
    with use(MEMBER):
        ran = execute("skill", {"action": "run", "name": "echo-skill"})
        assert ran.ok and "hello from the skill" in ran.output, (ran.output, ran.error)
        invoked = execute("skill", {"action": "invoke", "name": "echo-skill"})
        assert "cannot use" not in f"{invoked.output}{invoked.error}"
        assert "structured contract" in (invoked.error or "")
        for action in ("test", "create", "edit", "patch", "add_file", "remove_file", "delete", "set_meta", "reset_state"):
            result = execute("skill", {"action": action, "name": "echo-skill", "category": "personal"})
            assert not result.ok and "cannot use" in (result.error or ""), action
        refusal = execute("skill", {"action": "test", "name": "echo-skill"}).error
        assert "developer action" in refusal and "outside the sandbox" not in refusal


def test_a_member_under_a_tool_list_runs_skills_and_still_changes_none(tmp_home):
    from alpi.tools import _policy

    _scripted_skill(tmp_home)
    with use(MEMBER), _policy.use(frozenset({"skill"}), "listed"):
        assert execute("skill", {"action": "run", "name": "echo-skill"}).ok
        for action in ("test", "patch", "delete"):
            result = execute("skill", {"action": action, "name": "echo-skill"})
            assert not result.ok and "cannot use" in (result.error or ""), action


def test_a_member_cannot_reach_a_skill_script_through_a_workflow_or_a_nested_call(tmp_home):
    with use(MEMBER):
        result = execute("workflow", {"steps": [{"id": "a", "tool": "skill", "arguments": {"action": "test", "name": "x"}}]})
    assert "cannot use" in f"{result.output}{result.error}"


def test_a_fenced_peer_never_runs_skill_scripts_or_changes_skills_and_jobs(tmp_home):
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
