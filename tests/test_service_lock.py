"""Single-instance daemon lock — flock beats the pidfile TOCTOU that let two daemons start."""

from __future__ import annotations

from pathlib import Path

from alpi import service


def test_singleton_lock_blocks_a_second_acquire(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()

    first = service._acquire_singleton_lock(root)
    assert first is not None
    try:
        assert service._acquire_singleton_lock(root) is None
    finally:
        first.close()

    # released on close → a fresh daemon can acquire it again
    again = service._acquire_singleton_lock(root)
    assert again is not None
    again.close()
