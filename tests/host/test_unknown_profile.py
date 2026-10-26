from __future__ import annotations

from pathlib import Path

import pytest

from alpi import home
from alpi.host import device_state, handlers, schedule, usage
from alpi.host.server import HandlerError, Server
from alpi.scheduler import jobs_store


@pytest.fixture
def root(monkeypatch, tmp_path: Path) -> Path:
    monkeypatch.setattr(home, "_ROOT", tmp_path)
    (tmp_path / "profiles" / "real").mkdir(parents=True)
    return tmp_path


READS = [
    ("schedule.list", schedule._schedule_list),
    ("profile.attention", device_state._profile_attention),
    ("skills.list", device_state._skills_list),
    ("sessions.list", handlers._sessions_list),
    ("usage.daily", usage._usage_daily),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("name,handler", READS, ids=[n for n, _ in READS])
async def test_reading_an_unknown_profile_is_not_found_and_creates_nothing(root: Path, name, handler) -> None:
    before = sorted(p.name for p in (root / "profiles").iterdir())
    with pytest.raises(HandlerError) as exc:
        await handler({"profile": "ghost"}, Server(root))
    assert exc.value.code == -32004
    assert sorted(p.name for p in (root / "profiles").iterdir()) == before
    assert not (root / "profiles" / "ghost").exists()


@pytest.mark.asyncio
async def test_a_known_profile_still_reads(root: Path) -> None:
    result = await schedule._schedule_list({"profile": "real"}, Server(root))
    assert result == {"jobs": []}


@pytest.mark.asyncio
async def test_the_default_profile_still_reads(root: Path) -> None:
    result = await schedule._schedule_list({"profile": "default"}, Server(root))
    assert result == {"jobs": []}


def test_reading_jobs_never_creates_the_schedule_directory(tmp_path: Path) -> None:
    ghost = tmp_path / "profiles" / "ghost"
    assert jobs_store.read(ghost) == []
    assert not ghost.exists()


def test_writing_jobs_still_creates_the_schedule_directory(tmp_path: Path) -> None:
    jobs_store.update(tmp_path, lambda jobs: [*jobs, {"id": "j1"}])
    assert [j["id"] for j in jobs_store.read(tmp_path)] == ["j1"]
