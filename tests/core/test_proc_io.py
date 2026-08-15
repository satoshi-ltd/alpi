"""Async drain_tail: must consume the full stream (no deadlock) but cap memory."""

from __future__ import annotations

import asyncio
import sys

import pytest

from alpi._proc_io import drain_tail


@pytest.mark.asyncio
async def test_drain_tail_keeps_only_last_n_lines() -> None:
    proc = await asyncio.create_subprocess_exec(
        sys.executable, "-c",
        "import sys\n"
        "for i in range(1000):\n"
        "    print(f'line-{i}', file=sys.stderr)\n",
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    tail = await drain_tail(proc.stderr, max_lines=10)
    await proc.wait()
    lines = tail.split("\n")
    assert len(lines) == 10
    assert lines[-1] == "line-999"
    assert lines[0] == "line-990"


@pytest.mark.asyncio
async def test_drain_tail_consumes_full_stream_no_deadlock() -> None:
    # Child writes ~256KB to stderr — well past the typical pipe buffer
    # (~64KB), so without a concurrent drain proc.wait() would deadlock.
    proc = await asyncio.create_subprocess_exec(
        sys.executable, "-c",
        "import sys\n"
        "for _ in range(8192):\n"
        "    sys.stderr.write('x' * 32 + '\\n')\n"
        "sys.exit(0)\n",
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    drain = asyncio.create_task(drain_tail(proc.stderr, max_lines=5))
    rc = await asyncio.wait_for(proc.wait(), timeout=5)
    tail = await drain
    assert rc == 0
    assert tail.count("\n") == 4
    assert all(line == "x" * 32 for line in tail.split("\n"))


@pytest.mark.asyncio
async def test_drain_tail_handles_none_stream() -> None:
    assert await drain_tail(None) == ""


@pytest.mark.asyncio
async def test_drain_tail_observes_every_line() -> None:
    reader = asyncio.StreamReader()
    reader.feed_data(b"one\ntwo\n")
    reader.feed_eof()
    seen: list[str] = []

    assert await drain_tail(reader, on_line=seen.append) == "one\ntwo"
    assert seen == ["one", "two"]


@pytest.mark.asyncio
async def test_drain_tail_finishes_when_child_killed() -> None:
    proc = await asyncio.create_subprocess_exec(
        sys.executable, "-c",
        "import sys, time\n"
        "sys.stderr.write('start\\n'); sys.stderr.flush()\n"
        "time.sleep(60)\n",
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    drain = asyncio.create_task(drain_tail(proc.stderr, max_lines=5))
    await asyncio.sleep(0.2)
    proc.kill()
    rc = await asyncio.wait_for(proc.wait(), timeout=3)
    tail = await asyncio.wait_for(drain, timeout=3)
    assert rc != 0
    assert "start" in tail
