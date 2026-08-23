from __future__ import annotations

import threading
from pathlib import Path

from alpi.core.run_context import RunContext, current, use


def _context(tmp_path: Path, source: str = "user") -> RunContext:
    return RunContext.create(
        home=tmp_path,
        workspace=tmp_path / "workspace",
        profile="default",
        source=source,
        session_id="session-1",
        connection_id="host",
    )


def test_run_context_is_bound_and_restored(tmp_path: Path) -> None:
    context = _context(tmp_path)

    assert current() is None
    with use(context):
        assert current() is context
    assert current() is None


def test_run_context_does_not_leak_to_new_thread(tmp_path: Path) -> None:
    context = _context(tmp_path)
    seen = []

    with use(context):
        thread = threading.Thread(target=lambda: seen.append(current()))
        thread.start()
        thread.join()

    assert seen == [None]
    assert len(context.run_id) == 32
