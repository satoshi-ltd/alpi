import json
import multiprocessing as mp
from pathlib import Path

import pytest

from alpi.scheduler import jobs_store


def _mp_append_worker(home_str: str, i: int) -> None:
    from alpi.scheduler import jobs_store as js

    def _append(jobs):
        jobs.append({"id": f"job-{i:02d}"})
        return jobs

    js.update(Path(home_str), _append)


def _mp_bump_worker(home_str: str) -> None:
    from alpi.scheduler import jobs_store as js

    def _bump(jobs):
        for j in jobs:
            if j.get("id") == "shared":
                j["count"] = int(j.get("count", 0)) + 1
                return jobs
        return None

    js.update(Path(home_str), _bump)


def test_read_returns_empty_when_no_file(tmp_path: Path):
    assert jobs_store.read(tmp_path) == []


def test_read_raises_on_corrupt_json(tmp_path: Path):
    p = jobs_store.jobs_path(tmp_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{not valid json")
    with pytest.raises(jobs_store.CorruptJobsFile):
        jobs_store.read(tmp_path)


def test_read_raises_when_top_level_is_not_list(tmp_path: Path):
    p = jobs_store.jobs_path(tmp_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text('{"id": "this is a dict, not a list"}')
    with pytest.raises(jobs_store.CorruptJobsFile):
        jobs_store.read(tmp_path)


def test_read_treats_empty_file_as_empty_list(tmp_path: Path):
    p = jobs_store.jobs_path(tmp_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("")
    assert jobs_store.read(tmp_path) == []


def test_update_on_corrupt_file_raises_and_preserves_bytes(tmp_path: Path):
    p = jobs_store.jobs_path(tmp_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    original = "{this is corrupt — DO NOT OVERWRITE"
    p.write_text(original)

    def _mutator(jobs):
        jobs.append({"id": "should-never-be-written"})
        return jobs

    with pytest.raises(jobs_store.CorruptJobsFile):
        jobs_store.update(tmp_path, _mutator)
    assert p.read_text() == original
    tmp_sibling = p.with_suffix(p.suffix + ".tmp")
    assert not tmp_sibling.exists()


def test_update_writes_under_lock(tmp_path: Path):
    jobs_store.update(tmp_path, lambda _old: [{"id": "a"}, {"id": "b"}])
    assert jobs_store.read(tmp_path) == [{"id": "a"}, {"id": "b"}]


def test_update_skips_write_when_mutator_returns_none(tmp_path: Path):
    jobs_store.update(tmp_path, lambda _old: [{"id": "seed"}])
    jobs_store.update(tmp_path, lambda _old: None)
    assert jobs_store.read(tmp_path) == [{"id": "seed"}]


def test_update_atomic_no_tmp_left_behind(tmp_path: Path):
    jobs_store.update(tmp_path, lambda _old: [{"id": "x"}])
    p = jobs_store.jobs_path(tmp_path)
    tmp_sibling = p.with_suffix(p.suffix + ".tmp")
    assert p.exists()
    assert not tmp_sibling.exists()
    assert json.loads(p.read_text()) == [{"id": "x"}]


def test_update_propagates_mutator_exception_without_writing(tmp_path: Path):
    jobs_store.update(tmp_path, lambda _old: [{"id": "seed"}])

    class _Boom(Exception):
        pass

    def _explode(_jobs):
        raise _Boom

    with pytest.raises(_Boom):
        jobs_store.update(tmp_path, _explode)
    assert jobs_store.read(tmp_path) == [{"id": "seed"}]


def test_concurrent_appends_across_processes_do_not_lose_updates(tmp_path: Path):
    N = 20
    jobs_store.update(tmp_path, lambda _old: [])

    ctx = mp.get_context("spawn")
    procs = [
        ctx.Process(target=_mp_append_worker, args=(str(tmp_path), i))
        for i in range(N)
    ]
    for p in procs:
        p.start()
    for p in procs:
        p.join(timeout=60)
    for p in procs:
        assert p.exitcode == 0, f"worker pid={p.pid} exitcode={p.exitcode}"

    final = jobs_store.read(tmp_path)
    ids = sorted(j["id"] for j in final)
    expected = sorted(f"job-{i:02d}" for i in range(N))
    assert ids == expected


def test_concurrent_counter_bumps_across_processes_do_not_lose_updates(tmp_path: Path):
    N = 20
    jobs_store.update(tmp_path, lambda _old: [{"id": "shared", "count": 0}])

    ctx = mp.get_context("spawn")
    procs = [
        ctx.Process(target=_mp_bump_worker, args=(str(tmp_path),))
        for _ in range(N)
    ]
    for p in procs:
        p.start()
    for p in procs:
        p.join(timeout=60)
    for p in procs:
        assert p.exitcode == 0, f"worker pid={p.pid} exitcode={p.exitcode}"

    final = jobs_store.read(tmp_path)
    assert len(final) == 1
    assert final[0]["count"] == N
