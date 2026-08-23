from __future__ import annotations

from alpi.alp import subscription as sub_mod
from alpi.alp import tasks
from alpi.alp.agent_context import _format_subscription_block

HUB_PK = "H" * 44
MEMBER_PK = "M" * 44


def _sub() -> sub_mod.Subscription:
    return sub_mod.Subscription(
        wg_id="wg_a", name="site", hub_id="hub", hub_pubkey=HUB_PK, last_seq=0,
    )


def _opener(seq: int = 1) -> dict:
    return {
        "seq": seq, "from": HUB_PK,
        "text": "@quill #task #build ship the landing page",
    }


def _chatter(first: int, count: int) -> list[dict]:
    return [
        {"seq": first + i, "from": MEMBER_PK, "text": f"note {i}"}
        for i in range(count)
    ]


def test_a_burst_wider_than_the_cache_keeps_the_opener() -> None:
    sub = _sub()
    sub.append_recent([_opener(), *_chatter(2, 25)])
    seqs = [int(p["seq"]) for p in sub.recent_posts]
    assert 1 in seqs
    assert len(sub.recent_posts) == sub_mod.RECENT_POSTS_CACHE + 1


def test_the_child_still_sees_the_task_it_was_dispatched_for() -> None:
    sub = _sub()
    sub.append_recent([_opener(), *_chatter(2, 25)])
    active = tasks.active_task(sub.recent_posts, hub_pubkey=sub.hub_pubkey)
    assert active is not None
    assert active.opened_seq == 1
    assert "ship the landing page" in active.description
    block = _format_subscription_block(sub, "quill", {})
    assert "ship the landing page" in block


def test_a_closed_task_is_not_pinned_forever() -> None:
    sub = _sub()
    sub.append_recent([
        _opener(),
        {"seq": 2, "from": HUB_PK, "text": "#done shipped"},
        *_chatter(3, 25),
    ])
    seqs = [int(p["seq"]) for p in sub.recent_posts]
    assert 1 not in seqs
    assert len(sub.recent_posts) == sub_mod.RECENT_POSTS_CACHE


def test_a_burst_inside_the_cache_is_untouched() -> None:
    sub = _sub()
    sub.append_recent([_opener(), *_chatter(2, 5)])
    assert len(sub.recent_posts) == 6
    assert int(sub.recent_posts[0]["seq"]) == 1


def test_a_member_authored_task_never_pins_the_window() -> None:
    sub = _sub()
    sub.append_recent([
        {"seq": 1, "from": MEMBER_PK, "text": "@quill #task not from the hub"},
        *_chatter(2, 25),
    ])
    assert 1 not in [int(p["seq"]) for p in sub.recent_posts]
