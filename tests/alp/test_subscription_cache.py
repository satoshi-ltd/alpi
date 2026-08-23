from __future__ import annotations

import datetime as dt
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from alpi import yamlfast
from alpi.alp import subscription as sub_mod


@pytest.fixture(autouse=True)
def _clear_raw_cache() -> None:
    sub_mod._raw_cache.clear()
    yield
    sub_mod._raw_cache.clear()


@pytest.fixture
def parses(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    seen: list[str] = []
    real = yamlfast.safe_load

    def counting(text: str):
        seen.append(text)
        return real(text)

    monkeypatch.setattr(yamlfast, "safe_load", counting)
    return seen


def _sub(wg_id: str, posts: int = 3) -> sub_mod.Subscription:
    sub = sub_mod.Subscription(
        wg_id=wg_id, name=f"name-{wg_id}", hub_id="hub", hub_pubkey="HUBPK",
        last_seq=posts, joined_at="2026-08-16T10:00:00Z",
    )
    sub.roster = {"alice": "PK_A", "bob": "PK_B"}
    sub.recent_posts = [
        {
            "seq": i,
            "text": f"post {i}",
            "from": "HUBPK",
            "meta": {"tags": ["clean"]},
        }
        for i in range(1, posts + 1)
    ]
    return sub


def test_save_then_load_does_not_reparse_the_file(
    tmp_path: Path, parses: list[str],
) -> None:
    home = tmp_path / "quill"
    sub_mod.save(home, [_sub("wg_a"), _sub("wg_b")])
    assert parses == []

    for _ in range(5):
        assert {s.wg_id for s in sub_mod.load(home)} == {"wg_a", "wg_b"}
        assert sub_mod.get(home, "wg_b") is not None
    assert parses == []


def test_mutating_save_paths_keep_the_cache_warm(
    tmp_path: Path, parses: list[str],
) -> None:
    def _bump(sub: sub_mod.Subscription) -> bool:
        sub.last_seq = 99
        return True

    home = tmp_path / "muse"
    sub_mod.save(home, [_sub("wg_a")])
    sub_mod.upsert(home, _sub("wg_b"))
    sub_mod.mutate(home, "wg_a", _bump)
    assert sub_mod.get(home, "wg_a").last_seq == 99
    assert parses == []


def test_cached_snapshot_equals_a_fresh_parse_of_the_file(tmp_path: Path) -> None:
    home = tmp_path / "lens"
    original = [_sub("wg_a"), _sub("wg_b", posts=5)]
    sub_mod.save(home, original)

    p = sub_mod.path(home)
    cached = sub_mod._raw_cache[str(p)][1]
    assert cached == yamlfast.safe_load(p.read_text())

    warm = sub_mod.load(home)
    sub_mod._raw_cache.clear()
    assert sub_mod.load(home) == warm


def test_external_write_still_invalidates_the_cache(
    tmp_path: Path, parses: list[str],
) -> None:
    home = tmp_path / "scout"
    sub_mod.save(home, [_sub("wg_a")])
    p = sub_mod.path(home)

    p.write_text(yamlfast.safe_dump([
        {
            "wg_id": "wg_foreign", "name": "foreign", "hub_id": "hub",
            "hub_pubkey": "HUBPK", "last_seq": 7, "sealed_keys": [],
        },
    ]))

    assert [s.wg_id for s in sub_mod.load(home)] == ["wg_foreign"]
    assert len(parses) == 1


def test_another_process_write_still_invalidates_the_cache(tmp_path: Path) -> None:
    home = tmp_path / "relay"
    sub_mod.save(home, [_sub("wg_a")])

    script = textwrap.dedent(
        f"""
        from pathlib import Path
        from alpi.alp import subscription as sub_mod
        home = Path({str(home)!r})
        subs = sub_mod.load(home)
        subs.append(sub_mod.Subscription(
            wg_id="wg_other", name="other", hub_id="hub", hub_pubkey="HUBPK",
        ))
        sub_mod.save(home, subs)
        """
    )
    subprocess.run(
        [sys.executable, "-c", script], check=True,
        cwd=str(Path(sub_mod.__file__).parents[2]),
    )

    assert {s.wg_id for s in sub_mod.load(home)} == {"wg_a", "wg_other"}


def test_mtime_change_alone_invalidates_the_cache(
    tmp_path: Path, parses: list[str],
) -> None:
    home = tmp_path / "dial"
    sub_mod.save(home, [_sub("wg_a")])
    p = sub_mod.path(home)

    st = p.stat()
    os.utime(p, ns=(st.st_atime_ns, st.st_mtime_ns - 5_000_000_000))

    assert [s.wg_id for s in sub_mod.load(home)] == ["wg_a"]
    assert len(parses) == 1


def test_a_caller_mutating_load_output_cannot_poison_a_later_load(
    tmp_path: Path,
) -> None:
    home = tmp_path / "vault"
    sub_mod.save(home, [_sub("wg_a")])

    subs = sub_mod.load(home)
    subs[0].recent_posts[0]["meta"]["tags"].append("poison")
    subs[0].recent_posts[0]["text"] = "poison"
    subs[0].recent_posts.clear()
    subs[0].roster["alice"] = "poison"

    fresh = sub_mod.load(home)
    assert fresh[0].roster == {"alice": "PK_A", "bob": "PK_B"}
    assert [p["text"] for p in fresh[0].recent_posts] == ["post 1", "post 2", "post 3"]
    assert fresh[0].recent_posts[0]["meta"] == {"tags": ["clean"]}

    sub_mod._raw_cache.clear()
    assert sub_mod.load(home) == fresh


def test_a_caller_mutating_saved_objects_cannot_poison_the_cache(
    tmp_path: Path,
) -> None:
    home = tmp_path / "forge"
    saved = [_sub("wg_a")]
    sub_mod.save(home, saved)

    saved[0].recent_posts.append({"seq": 99, "text": "poison"})
    saved[0].recent_posts[0]["meta"]["tags"].append("poison")
    saved[0].roster["carol"] = "poison"

    warm = sub_mod.load(home)
    assert [p["seq"] for p in warm[0].recent_posts] == [1, 2, 3]
    assert warm[0].recent_posts[0]["meta"] == {"tags": ["clean"]}
    assert "carol" not in warm[0].roster

    sub_mod._raw_cache.clear()
    assert sub_mod.load(home) == warm


def test_a_value_that_cannot_round_trip_is_never_cached(
    tmp_path: Path, parses: list[str],
) -> None:
    home = tmp_path / "clock"
    p = sub_mod.path(home)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        "- wg_id: wg_a\n"
        "  name: name-wg_a\n"
        "  hub_id: hub\n"
        "  hub_pubkey: HUBPK\n"
        "  last_seq: 1\n"
        "  sealed_keys: []\n"
        "  recent_posts:\n"
        "  - seq: 1\n"
        "    text: post 1\n"
        "    when: 2026-08-16 10:00:00\n"
    )

    subs = sub_mod.load(home)
    assert isinstance(subs[0].recent_posts[0]["when"], dt.datetime)
    sub_mod.save(home, subs)
    assert str(p) not in sub_mod._raw_cache

    before = len(parses)
    reread = sub_mod.load(home)
    assert len(parses) == before + 1
    assert reread[0].recent_posts[0]["when"] == subs[0].recent_posts[0]["when"]
    assert sub_mod._raw_cache[str(p)][1] == yamlfast.safe_load(p.read_text())


def test_cacheable_copy_rejects_types_yaml_would_not_return(tmp_path: Path) -> None:
    assert sub_mod._cacheable_copy([{"a": (1, 2)}]) == [{"a": [1, 2]}]
    assert sub_mod._cacheable_copy({"a": {1: "int-key"}}) is sub_mod._UNCACHEABLE
    assert sub_mod._cacheable_copy([{"a": {"b"}}]) is sub_mod._UNCACHEABLE
    assert sub_mod._cacheable_copy([float("nan")]) is sub_mod._UNCACHEABLE
    assert sub_mod._cacheable_copy([b"raw"]) is sub_mod._UNCACHEABLE

    deep: list = []
    node = deep
    for _ in range(sub_mod._CACHE_MAX_DEPTH + 2):
        child: list = []
        node.append(child)
        node = child
    assert sub_mod._cacheable_copy(deep) is sub_mod._UNCACHEABLE


def test_the_file_holds_post_text_the_pure_emitter_would_corrupt(
    tmp_path: Path,
) -> None:
    home = tmp_path / "nel"
    sub = _sub("wg_a", posts=1)
    sub.recent_posts[0]["text"] = "rollback\x85now"
    sub.briefing = "brief\x85ing"
    sub_mod.save(home, [sub])

    p = sub_mod.path(home)
    on_disk = yamlfast.safe_load(p.read_text())
    assert on_disk[0]["recent_posts"][0]["text"] == "rollback\x85now"
    assert on_disk[0]["briefing"] == "brief\x85ing"

    sub_mod._raw_cache.clear()
    reread = sub_mod.load(home)
    assert reread[0].recent_posts[0]["text"] == "rollback\x85now"
    assert reread[0].briefing == "brief\x85ing"


def test_a_lone_surrogate_fails_the_write_instead_of_poisoning_the_file(
    tmp_path: Path,
) -> None:
    home = tmp_path / "surrogate"
    sub_mod.save(home, [_sub("wg_a")])
    p = sub_mod.path(home)
    before = p.read_text()

    doomed = _sub("wg_b", posts=1)
    doomed.briefing = "anchor \ud800"
    with pytest.raises(UnicodeEncodeError):
        sub_mod.upsert(home, doomed)

    assert p.read_text() == before
    assert [s.wg_id for s in sub_mod.load(home)] == ["wg_a"]
    sub_mod._raw_cache.clear()
    assert [s.wg_id for s in sub_mod.load(home)] == ["wg_a"]


def test_cacheable_copy_rejects_strings_the_pure_emitter_mangles() -> None:
    assert sub_mod._cacheable_copy("plain") == "plain"
    assert sub_mod._cacheable_copy([{"t": "a\x85b"}]) is sub_mod._UNCACHEABLE
    assert sub_mod._cacheable_copy([{"t": "a\ud800b"}]) is sub_mod._UNCACHEABLE
    assert sub_mod._cacheable_copy({"t": "a\udfffb"}) is sub_mod._UNCACHEABLE
    assert sub_mod._cacheable_copy([{"t": "a b"}]) == [{"t": "a b"}]


def test_a_write_landing_mid_parse_is_not_clobbered_by_the_older_parse(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _bump(sub: sub_mod.Subscription) -> bool:
        sub.last_seq = 4242
        return True

    home = tmp_path / "race"
    sub_mod.save(home, [_sub("wg_a")])
    p = sub_mod.path(home)
    sub_mod._invalidate_cache(p)

    real = yamlfast.safe_load
    raced = {"done": False}

    def racing(text: str):
        raw = real(text)
        if not raced["done"]:
            raced["done"] = True
            sub_mod.mutate(home, "wg_a", _bump)
        return raw

    monkeypatch.setattr(yamlfast, "safe_load", racing)
    sub_mod.load(home)
    assert raced["done"]

    stamp, cached = sub_mod._raw_cache[str(p)]
    st = p.stat()
    assert stamp == (st.st_mtime_ns, st.st_size)
    assert cached == real(p.read_text())
    assert sub_mod.get(home, "wg_a").last_seq == 4242


def test_an_uncacheable_post_still_detaches_its_nested_containers(
    tmp_path: Path,
) -> None:
    home = tmp_path / "detach"
    p = sub_mod.path(home)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        "- wg_id: wg_a\n"
        "  name: name-wg_a\n"
        "  hub_id: hub\n"
        "  hub_pubkey: HUBPK\n"
        "  last_seq: 1\n"
        "  sealed_keys: []\n"
        "  recent_posts:\n"
        "  - seq: 1\n"
        "    text: post 1\n"
        "    when: 2026-08-16 10:00:00\n"
        "    meta:\n"
        "      tags:\n"
        "      - clean\n"
    )

    first = sub_mod.load(home)
    assert isinstance(first[0].recent_posts[0]["when"], dt.datetime)
    first[0].recent_posts[0]["meta"]["tags"].append("poison")

    second = sub_mod.load(home)
    assert second[0].recent_posts[0]["meta"]["tags"] == ["clean"]
