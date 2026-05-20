import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { act, render, waitFor } from "@testing-library/react";

// Mutable handles wired through the mocked EndpointContext so each test can
// drive the simulated daemon.
let mockEndpoint;
let mockCall;
let mockCallStream;
let lastStreamHandlers;
let lastStreamHandle;
let streamCallCount;

vi.mock("../lib/EndpointContext", () => ({
  useEndpoint: () => ({ endpoint: mockEndpoint, call: mockCall, callStream: mockCallStream }),
}));

const { EventsProvider, useEventEffect } = await import("./useEvents.jsx");

function Recorder({ kinds, sink }) {
  useEventEffect(kinds, (ev) => sink.push(ev));
  return null;
}

function mount(kinds, sink) {
  return render(
    <EventsProvider>
      <Recorder kinds={kinds} sink={sink} />
    </EventsProvider>,
  );
}

function freshStream() {
  lastStreamHandle = { cancel: vi.fn() };
  return lastStreamHandle;
}

beforeEach(() => {
  mockEndpoint = { id: "alpha", ip: "10.0.0.1", port: 49200 };
  streamCallCount = 0;
  lastStreamHandlers = null;
  mockCall = vi.fn(async () => ({ events: [] }));
  mockCallStream = vi.fn((_method, _params, handlers) => {
    streamCallCount += 1;
    lastStreamHandlers = handlers;
    return freshStream();
  });
});

afterEach(() => {
  vi.useRealTimers();
});

describe("useEvents handshake + anchor", () => {
  it("first connect anchors at next_seq and does NOT backfill", async () => {
    mount("noise", []);
    await waitFor(() => expect(mockCallStream).toHaveBeenCalled());
    await act(async () => {
      lastStreamHandlers.onFrame({ event: "subscribed", next_seq: 42 });
    });
    expect(mockCall).not.toHaveBeenCalled();
  });

  it("subsequent reconnect backfills via host.events.history", async () => {
    vi.useFakeTimers();
    const sink = [];
    mount("wg.post", sink);
    await vi.waitFor(() => expect(mockCallStream).toHaveBeenCalled());

    await act(async () => {
      lastStreamHandlers.onFrame({ event: "subscribed", next_seq: 10 });
      lastStreamHandlers.onFrame({ event: "wg.post", seq: 11, data: { wg_id: "a" } });
    });
    expect(sink).toHaveLength(1);

    mockCall.mockResolvedValueOnce({
      events: [{ event: "wg.post", seq: 12, data: { wg_id: "a" } }],
      next_seq: 13,
    });

    await act(async () => {
      lastStreamHandlers.onDone();
      await vi.advanceTimersByTimeAsync(1100);
    });
    expect(streamCallCount).toBe(2);

    await act(async () => {
      lastStreamHandlers.onFrame({ event: "subscribed", next_seq: 13 });
      await Promise.resolve();
    });
    await vi.waitFor(() => expect(mockCall).toHaveBeenCalledWith(
      "host.events.history",
      expect.objectContaining({ after_seq: 11 }),
    ));
    await vi.waitFor(() => expect(sink).toHaveLength(2));
    expect(sink[1].seq).toBe(12);
  });
});

describe("useEvents dedupe", () => {
  it("ignores a seq seen via live and replayed via backfill", async () => {
    vi.useFakeTimers();
    const sink = [];
    mount("wg.post", sink);
    await vi.waitFor(() => expect(mockCallStream).toHaveBeenCalled());

    await act(async () => {
      lastStreamHandlers.onFrame({ event: "subscribed", next_seq: 5 });
      lastStreamHandlers.onFrame({ event: "wg.post", seq: 6, data: { wg_id: "a" } });
    });
    expect(sink).toHaveLength(1);

    mockCall.mockResolvedValueOnce({
      events: [
        { event: "wg.post", seq: 6, data: { wg_id: "a" } },
        { event: "wg.post", seq: 7, data: { wg_id: "a" } },
      ],
      next_seq: 8,
    });

    await act(async () => {
      lastStreamHandlers.onDone();
      await vi.advanceTimersByTimeAsync(1100);
    });

    await act(async () => {
      lastStreamHandlers.onFrame({ event: "subscribed", next_seq: 8 });
      await Promise.resolve();
    });
    await vi.waitFor(() => expect(sink).toHaveLength(2));
    expect(sink.map((e) => e.seq)).toEqual([6, 7]);
  });
});

describe("useEvents reconnect backoff", () => {
  it("re-subscribes after onError using exponential backoff", async () => {
    vi.useFakeTimers();
    mount("noise", []);
    await vi.waitFor(() => expect(streamCallCount).toBe(1));

    await act(async () => {
      lastStreamHandlers.onError(new Error("ws closed"));
      await vi.advanceTimersByTimeAsync(1100);
    });
    expect(streamCallCount).toBe(2);
  });
});

describe("useEvents endpoint swap", () => {
  // Harness assigns mockEndpoint synchronously in the render body BEFORE
  // returning the provider. That way useEndpoint() sees the right value on
  // the same render that mounts EventsProvider — no useEffect race.
  function Harness({ endpoint, sink = [] }) {
    mockEndpoint = endpoint;
    return (
      <EventsProvider>
        <Recorder kinds="wg.post" sink={sink} />
      </EventsProvider>
    );
  }

  it("resets the seq cursor when the active daemon changes", async () => {
    const { rerender } = render(<Harness endpoint={{ id: "alpha" }} />);
    await waitFor(() => expect(streamCallCount).toBe(1));

    await act(async () => {
      lastStreamHandlers.onFrame({ event: "subscribed", next_seq: 10 });
      lastStreamHandlers.onFrame({ event: "wg.post", seq: 11, data: {} });
    });

    rerender(<Harness endpoint={{ id: "beta" }} />);
    await waitFor(() => expect(streamCallCount).toBe(2));
    mockCall.mockClear();

    await act(async () => {
      lastStreamHandlers.onFrame({ event: "subscribed", next_seq: 50 });
    });
    // Anchor-only: a fresh daemon has no shared seqs to backfill.
    expect(mockCall).not.toHaveBeenCalled();
  });

  // A `host.events.history` in flight when the endpoint swaps must NOT fan
  // out — its events belong to a different daemon's sequence space. Without
  // the post-await `cancelled` check inside backfill(), those events leak
  // through into listeners of the new endpoint.
  it("a stale backfill resolving AFTER endpoint swap does not fanOut", async () => {
    vi.useFakeTimers();
    const sink = [];
    const { rerender } = render(<Harness endpoint={{ id: "alpha" }} sink={sink} />);
    await vi.waitFor(() => expect(streamCallCount).toBe(1));

    // Bring the cursor off zero so the next `subscribed` triggers backfill.
    await act(async () => {
      lastStreamHandlers.onFrame({ event: "subscribed", next_seq: 10 });
      lastStreamHandlers.onFrame({ event: "wg.post", seq: 11, data: {} });
    });
    expect(sink).toHaveLength(1);

    // Make the upcoming history call hang until we resolve it manually.
    let resolveBackfill;
    mockCall.mockImplementationOnce(
      () => new Promise((r) => { resolveBackfill = r; }),
    );

    // Drop stream → reconnect → subscribed triggers backfill (now hanging).
    await act(async () => {
      lastStreamHandlers.onDone();
      await vi.advanceTimersByTimeAsync(1100);
    });
    expect(streamCallCount).toBe(2);
    await act(async () => {
      lastStreamHandlers.onFrame({ event: "subscribed", next_seq: 13 });
    });

    // Swap to a different daemon WHILE backfill is still in flight.
    rerender(<Harness endpoint={{ id: "beta" }} sink={sink} />);
    await vi.waitFor(() => expect(streamCallCount).toBe(3));

    // Now the old daemon's response finally lands.
    await act(async () => {
      resolveBackfill({
        events: [{ event: "wg.post", seq: 12, data: { wg_id: "x" } }],
        next_seq: 13,
      });
      // Let the awaited microtask + state set flush.
      await Promise.resolve();
      await Promise.resolve();
    });

    // Stale backfill must not leak into the new endpoint's listener.
    expect(sink).toHaveLength(1);
    expect(sink[0].seq).toBe(11);
  });
});
