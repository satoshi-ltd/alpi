"""Engine pre-turn hook — ``alpi.alp.agent_context.build``.

Builds the system-prompt block that injects workgroup state into
every agent turn: briefing, active task, recent posts with alias
resolution, mention awareness, and the engagement guardrails.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest

from alpi.alp import agent_context
from alpi.alp import peers as peers_mod
from alpi.alp import subscription as sub_mod
from alpi.alp import workgroup as wg_mod
from alpi.alp.keys import load_or_generate
from alpi.alp.peers import Peer


@pytest.fixture
def short_tmp() -> Path:
    d = Path(tempfile.mkdtemp(prefix="alpi-ctx-", dir="/tmp"))
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_returns_none_with_no_workgroups(short_tmp: Path) -> None:
    home = short_tmp / "solo"; home.mkdir()
    load_or_generate(home)
    assert agent_context.build(home) is None


def test_subscription_block_has_wg_id_and_briefing(short_tmp: Path) -> None:
    """The block must surface the `wg_id` so the agent calls
    ``workgroup_post`` with the right id, AND the briefing so
    members see the same anchor as the hub."""
    home = short_tmp / "alice"; home.mkdir()
    load_or_generate(home)
    sub = sub_mod.Subscription(
        wg_id="wg_design", name="design", hub_id="bob", hub_pubkey="bobkey",
        briefing="research peptides for protein X. shortlist 5 by friday.",
    )
    sub.append_recent([
        {"seq": 1, "text": "kicking off", "from": "bobkey"},
    ])
    sub_mod.upsert(home, sub)

    block = agent_context.build(home)
    assert block is not None
    assert "wg_id=wg_design" in block
    assert "briefing: research peptides" in block
    assert "design" in block


def test_subscription_briefing_is_injected_beyond_post_preview(short_tmp: Path) -> None:
    home = short_tmp / "alice"
    home.mkdir()
    load_or_generate(home)
    briefing = "first line\n" + "member context " * 30
    sub_mod.upsert(home, sub_mod.Subscription(
        wg_id="wg_design", name="design", hub_id="bob", hub_pubkey="bobkey",
        briefing=briefing,
    ))

    block = agent_context.build(home)

    assert block is not None
    assert briefing.splitlines()[1].strip() in block
    assert "  briefing: first line\n            member context" in block


def test_subscription_briefing_truncation_is_visible(short_tmp: Path) -> None:
    home = short_tmp / "alice"
    home.mkdir()
    load_or_generate(home)
    briefing = "x" * (agent_context._BRIEFING_INJECT_CHARS + 100)
    sub_mod.upsert(home, sub_mod.Subscription(
        wg_id="wg_design", name="design", hub_id="bob", hub_pubkey="bobkey",
        briefing=briefing,
    ))

    block = agent_context.build(home)

    assert block is not None
    assert f"… [briefing truncated at {agent_context._BRIEFING_INJECT_CHARS} chars]" in block
    rendered = block.split("  briefing: ", 1)[1].splitlines()[0]
    assert len(rendered) == agent_context._BRIEFING_INJECT_CHARS


def test_recent_posts_keep_the_short_preview(short_tmp: Path) -> None:
    home = short_tmp / "alice"
    home.mkdir()
    load_or_generate(home)
    post = "p" * 300
    sub = sub_mod.Subscription(
        wg_id="wg_design", name="design", hub_id="bob", hub_pubkey="bobkey",
    )
    sub.append_recent([{"seq": 1, "text": post, "from": "bobkey"}])
    sub_mod.upsert(home, sub)

    block = agent_context.build(home)

    assert block is not None
    assert post not in block
    assert "p" * (agent_context._POST_PREVIEW_CHARS - 1) + "…" in block


def test_active_task_surfaces_in_block(short_tmp: Path) -> None:
    home = short_tmp / "alice"; home.mkdir()
    load_or_generate(home)
    sub = sub_mod.Subscription(
        wg_id="wg_x", name="x", hub_id="h", hub_pubkey="hubkey",
    )
    sub.append_recent([
        {"seq": 1, "text": "#task #peptides research peptides", "from": "hubkey"},
        {"seq": 2, "text": "@alice you take lit angle", "from": "hubkey"},
    ])
    sub_mod.upsert(home, sub)
    block = agent_context.build(home)
    assert block is not None
    assert "active task: research peptides" in block


def test_aliases_resolve_pinned_peers(short_tmp: Path) -> None:
    """Pinned peers in peers.yaml render as ``@<id>`` instead of a
    pubkey fragment. Makes the system prompt readable."""
    home = short_tmp / "alice"; home.mkdir()
    load_or_generate(home)
    bob_pubkey = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
    peers_mod.add(home, Peer(id="bob", pubkey=bob_pubkey, allow=["link.ping"]))
    sub = sub_mod.Subscription(
        wg_id="wg_x", name="x", hub_id="bob", hub_pubkey=bob_pubkey,
    )
    sub.append_recent([
        {"seq": 1, "text": "kicking off", "from": bob_pubkey},
    ])
    sub_mod.upsert(home, sub)
    block = agent_context.build(home)
    assert block is not None
    assert "@bob" in block


def test_self_mention_flagged(short_tmp: Path, monkeypatch) -> None:
    """When a recent post mentions @<own-profile>, the block notes it
    so the agent knows it's expected to engage."""
    fake_root = short_tmp / "alpi-root"
    profiles = fake_root / "profiles"
    home = profiles / "alice"
    home.mkdir(parents=True)
    monkeypatch.setattr("alpi.alp.agent_context._ROOT", fake_root)
    load_or_generate(home)
    sub = sub_mod.Subscription(
        wg_id="wg_x", name="x", hub_id="h", hub_pubkey="hk",
    )
    sub.append_recent([
        {"seq": 1, "text": "hi @alice please help", "from": "hk"},
    ])
    sub_mod.upsert(home, sub)
    block = agent_context.build(home)
    assert block is not None
    assert "mentioned" in block.lower()


def test_hub_workgroup_briefing_and_id_in_block(short_tmp: Path) -> None:
    """Hub-of workgroups surface their plaintext briefing + id so the
    agent has the anchor for its own workgroups too."""
    home = short_tmp / "alice"; home.mkdir()
    kp = load_or_generate(home)
    wg = wg_mod.create(
        home, name="hosted", hub_kp=kp, member_pubkeys=[],
        briefing="ongoing scratchpad for q2 planning",
    )
    block = agent_context.build(home)
    assert block is not None
    assert "hosted" in block
    assert f"wg_id={wg.meta.id}" in block
    assert "scratchpad" in block


def test_hub_workgroup_injects_multiline_briefing(short_tmp: Path) -> None:
    home = short_tmp / "alice"
    home.mkdir()
    kp = load_or_generate(home)
    second = "hub context " * 30
    wg_mod.create(
        home, name="hosted", hub_kp=kp, member_pubkeys=[],
        briefing=f"first line\n{second}",
    )

    block = agent_context.build(home)

    assert block is not None
    assert second.strip() in block
    assert "  briefing: first line\n            hub context" in block


def test_block_contains_engagement_guardrails(short_tmp: Path) -> None:
    """The footer enumerates concrete dos and don'ts so the agent
    doesn't desync into ping-pong loops."""
    home = short_tmp / "alice"; home.mkdir()
    kp = load_or_generate(home)
    wg_mod.create(home, name="x", hub_kp=kp, member_pubkeys=[])
    block = agent_context.build(home)
    assert block is not None
    # Critical anti-noise rules must be present.
    assert "OBSERVER" in block
    assert "DO NOT POST" in block
    # Hub-only marker rule must be present in the current prompt text.
    assert "manager assigning tasks" in block.lower()
    assert "ONLY THE HUB OPENS" in block
    assert "ONLY THE HUB CLOSES" in block


def test_working_guardrail_requires_naming_the_tool(short_tmp: Path) -> None:
    """`#working` must carry a concrete action + tool, not a bare heartbeat —
    the reason is the only signal the hub/human see while a peer works."""
    home = short_tmp / "alice"; home.mkdir()
    kp = load_or_generate(home)
    wg_mod.create(home, name="x", hub_kp=kp, member_pubkeys=[])
    block = agent_context.build(home)
    assert block is not None
    assert "#working <concrete action> (<tool>)" in block
    assert "SAY WHAT YOU'RE DOING" in block
    assert "(web_fetch)" in block


def test_roster_renders_bios_when_present(short_tmp: Path) -> None:
    """Members in the roster with a self-published bio render as
    ``@alice (online, "product engineer — velocity")``; members
    without a bio render with just the status."""
    home = short_tmp / "alice"; home.mkdir()
    kp = load_or_generate(home)
    # Pin two peers so they alias to readable handles in the block.
    peers_mod.add(home, Peer(
        id="bob", pubkey="BOB_PK", allow=["link.ping"], address=None,
    ))
    peers_mod.add(home, Peer(
        id="carla", pubkey="CARLA_PK", allow=["link.ping"], address=None,
    ))
    sub = sub_mod.Subscription(
        wg_id="wg1", name="design", hub_id="bob", hub_pubkey="BOB_PK",
        roster={"BOB_PK": "", "CARLA_PK": ""},
        roster_bios={"BOB_PK": "systems engineer — durability"},
    )
    sub_mod.upsert(home, sub)
    block = agent_context.build(home)
    assert block is not None
    assert '@bob (unknown, "systems engineer — durability")' in block
    # Carla has no bio → renders without the quoted suffix.
    assert "@carla (unknown)" in block
    assert '@carla (unknown, ' not in block


def test_hub_workgroup_renders_own_bio(short_tmp: Path) -> None:
    """When the profile is the hub of a workgroup, its own ``Member.bio``
    (set via ``hub_bio=`` on ``create``) shows up in the rendered roster."""
    home = short_tmp / "alice"; home.mkdir()
    kp = load_or_generate(home)
    wg_mod.create(
        home, name="hosted", hub_kp=kp, member_pubkeys=[],
        hub_bio="product engineer — velocity",
    )
    block = agent_context.build(home)
    assert block is not None
    assert "product engineer — velocity" in block


def test_member_block_renders_the_declared_chains_with_owners(short_tmp: Path) -> None:
    home = short_tmp / "quill"; home.mkdir()
    load_or_generate(home)
    sub = sub_mod.Subscription(
        wg_id="wg_site", name="site", hub_id="mira", hub_pubkey="mirakey",
    )
    sub.absorb_pipeline_state({
        "pipelines": {
            "setup": ["setup", "content", "qa"],
            "media-update": ["media-update", "media-qa"],
        },
        "launch_pipeline": "setup",
        "pipeline_mode": True,
        "phase_map": {
            "setup": {"owner": "pixel", "task": "initialize the clone"},
            "content": {"owner": "quill"},
            "media-update": {"owner": "muse"},
        },
    })
    sub_mod.upsert(home, sub)

    block = agent_context.build(home)
    assert "pipelines:" in block
    assert "- setup: #setup @pixel → #content @quill → #qa (launch)" in block
    assert "- media-update: #media-update @muse → #media-qa" in block


def test_launchless_member_block_says_nothing_starts_on_its_own(short_tmp: Path) -> None:
    home = short_tmp / "muse"; home.mkdir()
    load_or_generate(home)
    sub = sub_mod.Subscription(
        wg_id="wg_idle", name="idle", hub_id="mira", hub_pubkey="mirakey",
    )
    sub.absorb_pipeline_state({
        "pipelines": {"media-update": ["media-update", "media-qa"]},
        "launch_pipeline": None,
        "pipeline_mode": True,
        "phase_map": {"media-update": {"owner": "muse"}},
    })
    sub_mod.upsert(home, sub)

    block = agent_context.build(home)
    assert "no launch pipeline" in block
    assert "(launch)" not in block


def test_hub_block_renders_chains_and_never_the_gate_commands(short_tmp: Path) -> None:
    home = short_tmp / "mira"; home.mkdir(parents=True)
    kp = load_or_generate(home)
    wg_mod.create(
        home, name="site", hub_kp=kp, member_pubkeys=[],
        pipelines={"setup": ["setup", "qa"]},
        launch_pipeline="setup",
        pipeline_steps={
            "setup": {
                "owner": "mira", "task": "initialize the clone",
                "gate": {"argv": ["npm", "run", "check:setup"], "cwd": "projects/x"},
            },
            "qa": {"owner": "mira", "task": "audit it"},
        },
    )

    block = agent_context.build(home)
    assert "- setup: #setup @mira → #qa @mira (launch)" in block
    assert "check:setup" not in block
    assert "projects/x" not in block


def test_block_orders_stable_content_before_volatile(short_tmp: Path) -> None:
    """Provider prefix caching: the static guardrails precede the per-turn churn (roster liveness, recent posts, budget %), which sinks to the tail."""
    home = short_tmp / "cachet"; home.mkdir()
    load_or_generate(home)
    (home / "config.yaml").write_text("budget:\n  daily_usd: 10.0\n")
    from alpi import ledger
    ledger.record(home, usd=9.0, tokens=100, tokens_in=80, tokens_out=20)
    sub = sub_mod.Subscription(
        wg_id="wg_c", name="site", hub_id="mira", hub_pubkey="HUB",
        briefing="stable briefing text",
    )
    sub.append_recent([{"seq": 9, "text": "volatile recent post", "from": "HUB"}])
    sub_mod.upsert(home, sub)

    block = agent_context.build(home)
    guard = block.index("=== Workgroup engagement rules ===")
    wg = block.index("wg_id=wg_c")
    budget = block.index("BUDGET:")
    assert guard < wg < budget
    assert block.rstrip().endswith(block[budget:].rstrip())
