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


def test_update_splits_state_into_runs_json(tmp_path: Path):
    jobs_store.update(tmp_path, lambda _old: [
        {"id": "a", "kind": "cron", "expression": "* * * * *",
         "last_run_at": "2026-07-13T10:00:00Z", "last_run_status": "ok"},
    ])
    raw = json.loads(jobs_store.jobs_path(tmp_path).read_text())
    assert raw == [{"id": "a", "kind": "cron", "expression": "* * * * *"}]
    runs = json.loads(jobs_store.runs_path(tmp_path).read_text())
    assert runs == {"a": {"last_run_at": "2026-07-13T10:00:00Z", "last_run_status": "ok"}}


def test_read_merges_runs_state_onto_definitions(tmp_path: Path):
    jp = jobs_store.jobs_path(tmp_path)
    jp.parent.mkdir(parents=True, exist_ok=True)
    jp.write_text(json.dumps([{"id": "a", "kind": "cron"}]))
    jobs_store.runs_path(tmp_path).write_text(
        json.dumps({"a": {"last_run_at": "2026-01-01T00:00:00Z", "last_run_status": "error"}}))
    merged = jobs_store.read(tmp_path)
    assert merged[0]["last_run_at"] == "2026-01-01T00:00:00Z"
    assert merged[0]["last_run_status"] == "error"


def test_legacy_embedded_state_survives_read_and_migrates_on_first_write(tmp_path: Path):
    jp = jobs_store.jobs_path(tmp_path)
    jp.parent.mkdir(parents=True, exist_ok=True)
    jp.write_text(json.dumps([
        {"id": "a", "kind": "cron", "last_run_at": "2026-02-02T00:00:00Z", "last_run_status": "ok"},
    ]))
    assert jobs_store.read(tmp_path)[0]["last_run_at"] == "2026-02-02T00:00:00Z"
    jobs_store.update(tmp_path, lambda jobs: jobs)
    assert "last_run_at" not in json.loads(jp.read_text())[0]
    runs = json.loads(jobs_store.runs_path(tmp_path).read_text())
    assert runs["a"]["last_run_at"] == "2026-02-02T00:00:00Z"


def test_legacy_embedded_state_wins_over_runs_entry(tmp_path: Path):
    jp = jobs_store.jobs_path(tmp_path)
    jp.parent.mkdir(parents=True, exist_ok=True)
    jp.write_text(json.dumps([{"id": "a", "kind": "cron", "last_run_at": "EMBEDDED"}]))
    jobs_store.runs_path(tmp_path).write_text(json.dumps({"a": {"last_run_at": "RUNS"}}))
    assert jobs_store.read(tmp_path)[0]["last_run_at"] == "EMBEDDED"


def test_state_only_stamp_does_not_rewrite_definitions_file(tmp_path: Path):
    jobs_store.update(tmp_path, lambda _old: [{"id": "a", "kind": "cron"}])
    jp = jobs_store.jobs_path(tmp_path)
    before = jp.read_text()
    before_stat = jp.stat().st_mtime_ns

    def _stamp(jobs):
        jobs[0]["last_run_at"] = "2026-07-13T11:00:00Z"
        return jobs

    jobs_store.update(tmp_path, _stamp)
    assert jp.read_text() == before
    assert jp.stat().st_mtime_ns == before_stat
    assert json.loads(jobs_store.runs_path(tmp_path).read_text())["a"]["last_run_at"] == "2026-07-13T11:00:00Z"


def test_deleting_a_job_drops_its_runs_entry(tmp_path: Path):
    jobs_store.update(tmp_path, lambda _old: [
        {"id": "a", "last_run_at": "X"}, {"id": "b", "last_run_at": "Y"},
    ])
    jobs_store.update(tmp_path, lambda jobs: [j for j in jobs if j["id"] == "b"])
    runs = json.loads(jobs_store.runs_path(tmp_path).read_text())
    assert runs == {"b": {"last_run_at": "Y"}}


def test_corrupt_runs_json_raises(tmp_path: Path):
    jp = jobs_store.jobs_path(tmp_path)
    jp.parent.mkdir(parents=True, exist_ok=True)
    jp.write_text(json.dumps([{"id": "a"}]))
    jobs_store.runs_path(tmp_path).write_text("{broken")
    with pytest.raises(jobs_store.CorruptJobsFile):
        jobs_store.read(tmp_path)


class _WriteCrash(Exception):
    pass


def _crash_on(monkeypatch, target_path: Path, skip: int = 0):
    real = jobs_store._write_inside_lock
    seen = {"n": 0}

    def _maybe_crash(p: Path, payload):
        if p == target_path:
            if seen["n"] >= skip:
                raise _WriteCrash
            seen["n"] += 1
        return real(p, payload)

    return _maybe_crash


def test_crash_before_definitions_write_leaves_no_phantom_job(tmp_path: Path, monkeypatch):
    jobs_store.update(tmp_path, lambda _old: [{"id": "old", "kind": "cron", "last_run_at": "X"}])
    monkeypatch.setattr(
        jobs_store, "_write_inside_lock",
        _crash_on(monkeypatch, jobs_store.runs_path(tmp_path)),
    )

    def _create(jobs):
        jobs.append({"id": "new", "kind": "cron", "last_run_at": "Y"})
        return jobs

    with pytest.raises(_WriteCrash):
        jobs_store.update(tmp_path, _create)
    merged = jobs_store.read(tmp_path)
    assert [j["id"] for j in merged] == ["old"]
    assert merged[0]["last_run_at"] == "X"


def test_crash_between_state_and_definitions_never_exposes_stateless_job(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        jobs_store, "_write_inside_lock",
        _crash_on(monkeypatch, jobs_store.jobs_path(tmp_path)),
    )
    with pytest.raises(_WriteCrash):
        jobs_store.update(tmp_path, lambda _old: [{"id": "a", "kind": "cron", "last_run_at": "STAMPED"}])
    assert not jobs_store.jobs_path(tmp_path).exists()
    runs = json.loads(jobs_store.runs_path(tmp_path).read_text())
    assert runs["a"]["last_run_at"] == "STAMPED"
    assert jobs_store.read(tmp_path) == []


def test_crash_mid_legacy_migration_keeps_embedded_state_authoritative(tmp_path: Path, monkeypatch):
    jp = jobs_store.jobs_path(tmp_path)
    jp.parent.mkdir(parents=True, exist_ok=True)
    jp.write_text(json.dumps([{"id": "a", "kind": "cron", "last_run_at": "LEGACY"}]))
    monkeypatch.setattr(
        jobs_store, "_write_inside_lock",
        _crash_on(monkeypatch, jobs_store.jobs_path(tmp_path)),
    )
    with pytest.raises(_WriteCrash):
        jobs_store.update(tmp_path, lambda jobs: jobs)
    assert jobs_store.read(tmp_path)[0]["last_run_at"] == "LEGACY"


def test_crash_before_orphan_prune_recovers_on_next_write(tmp_path: Path, monkeypatch):
    jobs_store.update(tmp_path, lambda _old: [
        {"id": "a", "last_run_at": "X"}, {"id": "b", "last_run_at": "Y"},
    ])
    # deletion skips the union write (union == old state), so the prune is the first runs write
    monkeypatch.setattr(
        jobs_store, "_write_inside_lock",
        _crash_on(monkeypatch, jobs_store.runs_path(tmp_path)),
    )
    with pytest.raises(_WriteCrash):
        jobs_store.update(tmp_path, lambda jobs: [j for j in jobs if j["id"] == "b"])
    runs = json.loads(jobs_store.runs_path(tmp_path).read_text())
    assert "a" in runs
    monkeypatch.undo()
    jobs_store.update(tmp_path, lambda jobs: jobs)
    runs = json.loads(jobs_store.runs_path(tmp_path).read_text())
    assert runs == {"b": {"last_run_at": "Y"}}
