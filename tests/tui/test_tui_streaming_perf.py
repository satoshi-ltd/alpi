"""Streaming render perf — input responsiveness during heavy stream.

Roadmap BG (v0.4): per-keystroke p99 latency must stay under 50 ms
while AssistantMessage is actively flushing deltas at full rate.

Run locally:

    pytest -m perf tests/test_tui_streaming_perf.py -v

Gated behind the ``perf`` marker because terminal timing is variable
and CI hardware would flake the assertion. Numbers are stable on a
quiet local machine.
"""

from __future__ import annotations

import asyncio
import statistics
import time

import pytest
from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.events import Key
from textual.widgets import Input

from alpi.tui.widgets import AssistantMessage


_TOKENS_PER_SEC = 60
_STREAM_TOTAL_TOKENS = 240
_KEYSTROKES_PER_SEC = 5
_KEYSTROKE_BUDGET_S = 0.050  # 50 ms p99 target

_PARAGRAPH = (
    "The quick brown fox jumps over the lazy dog. " * 3 + "\n\n"
)
_FULL_TEXT = _PARAGRAPH * 4
_TOKENS = _FULL_TEXT.split(" ")


class _StreamApp(App):
    """Minimal app: a scrollable body and an input footer.

    Mirrors the AlpiApp streaming path for AssistantMessage without
    booting profiles, engine, or any I/O.
    """

    def compose(self) -> ComposeResult:
        yield VerticalScroll(id="body")
        yield Input(id="chat-input")

    async def on_mount(self) -> None:
        self.query_one("#chat-input", Input).focus()


async def _drive_stream(msg: AssistantMessage) -> None:
    interval = 1.0 / _TOKENS_PER_SEC
    for tok in _TOKENS[:_STREAM_TOTAL_TOKENS]:
        msg.append(tok + " ")
        await asyncio.sleep(interval)


@pytest.mark.perf
@pytest.mark.asyncio
async def test_input_latency_during_stream() -> None:
    app = _StreamApp()
    async with app.run_test() as pilot:
        body = app.query_one("#body", VerticalScroll)
        input_widget = app.query_one("#chat-input", Input)

        msg = AssistantMessage()
        await body.mount(msg)
        await pilot.pause()

        stream_task = asyncio.create_task(_drive_stream(msg))

        latencies: list[float] = []
        keystroke_interval = 1.0 / _KEYSTROKES_PER_SEC
        char = ord("a")
        try:
            while not stream_task.done():
                expected_len = len(input_widget.value) + 1
                key = chr(char)
                t0 = time.perf_counter()
                input_widget.post_message(Key(key, key))
                while len(input_widget.value) < expected_len:
                    await asyncio.sleep(0)
                latencies.append(time.perf_counter() - t0)
                char = (char - ord("a") + 1) % 26 + ord("a")
                await asyncio.sleep(keystroke_interval)
        finally:
            await stream_task

        assert len(latencies) >= 5, f"too few samples: {len(latencies)}"

        p50 = statistics.median(latencies)
        p95 = statistics.quantiles(latencies, n=20)[18]
        p99 = statistics.quantiles(latencies, n=100)[98]
        peak = max(latencies)

        print(
            f"\nkeystroke latency over {len(latencies)} samples: "
            f"p50={p50*1000:.1f}ms p95={p95*1000:.1f}ms "
            f"p99={p99*1000:.1f}ms peak={peak*1000:.1f}ms"
        )

        assert p99 < _KEYSTROKE_BUDGET_S, (
            f"p99 {p99*1000:.1f}ms exceeds {_KEYSTROKE_BUDGET_S*1000:.0f}ms "
            f"budget (peak {peak*1000:.1f}ms)"
        )
