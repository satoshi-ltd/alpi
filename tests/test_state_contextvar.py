"""Tests for ContextVar-based tool state.

The old module-global design broke under parallel sub-agents because two
threads writing to the same `_emit` would interleave progress messages.
These tests confirm each thread has its own isolated view.
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

from alpi.tools import _state as S


def test_set_and_get_roundtrip() -> None:
    seen: list[tuple[str, bool]] = []
    S.set_emit(lambda label, err: seen.append((label, err)))
    try:
        S.emit_state("hello")
        S.emit_state("oops", error=True)
    finally:
        S.set_emit(None)
    assert seen == [("hello", False), ("oops", True)]


def test_parallel_threads_isolated() -> None:
    """Each thread's set_emit should not clobber any other thread's."""
    collected: dict[str, list[str]] = {"A": [], "B": [], "C": []}

    def _worker(name: str):
        S.set_emit(lambda label, err, _n=name: collected[_n].append(label))
        for i in range(5):
            S.emit_state(f"{name}-{i}")

    with ThreadPoolExecutor(max_workers=3) as ex:
        list(ex.map(_worker, ["A", "B", "C"]))

    for name in ("A", "B", "C"):
        assert collected[name] == [f"{name}-0", f"{name}-1", f"{name}-2",
                                   f"{name}-3", f"{name}-4"]


def test_parent_emit_unchanged_by_child() -> None:
    """Parent sets emit, child sets its own emit — parent's stays intact."""
    parent_log: list[str] = []
    S.set_emit(lambda label, err: parent_log.append(label))
    try:
        def _child():
            child_log: list[str] = []
            S.set_emit(lambda label, err: child_log.append(label))
            S.emit_state("in-child")
            return child_log

        t = threading.Thread(target=_child)
        t.start()
        t.join()

        S.emit_state("in-parent-after")
    finally:
        S.set_emit(None)

    assert parent_log == ["in-parent-after"]


def test_is_interrupted_inherits_from_parent() -> None:
    """A ContextVar-set interrupt_getter in parent is NOT auto-inherited by
    a new thread — workers must explicitly re-set it (as the batch dispatch
    in research/delegate does). This documents the expected contract."""
    S.set_interrupt_getter(lambda: True)
    try:
        assert S.is_interrupted() is True

        result_in_worker: list[bool] = []

        def _worker():
            result_in_worker.append(S.is_interrupted())

        t = threading.Thread(target=_worker)
        t.start()
        t.join()

        assert result_in_worker == [False]
    finally:
        S.set_interrupt_getter(None)


def test_record_usage_fans_out_to_sink() -> None:
    total = {"input": 0, "output": 0, "cost": 0.0}

    def _sink(i: int, o: int, c: float) -> None:
        total["input"] += i
        total["output"] += o
        total["cost"] += c

    S.set_usage_sink(_sink)
    try:
        S.record_usage(10, 20, 0.5)
        S.record_usage(5, 2, 0.1)
    finally:
        S.set_usage_sink(None)
    assert total == {"input": 15, "output": 22, "cost": 0.6}
