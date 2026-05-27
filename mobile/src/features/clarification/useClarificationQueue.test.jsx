import { describe, it, expect, beforeEach, vi } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";

let mockEndpoint;
let mockCall;
let mockCallStream;
let streamHandlers;

vi.mock("../../lib/EndpointContext", () => ({
  useEndpoint: () => ({ endpoint: mockEndpoint, call: mockCall, callStream: mockCallStream }),
}));

const { EventsProvider } = await import("../../hooks/useEvents.jsx");
const { useClarificationQueue } = await import("./useClarificationQueue.js");

beforeEach(() => {
  mockEndpoint = { id: "alpha", ip: "10.0.0.1", port: 49200 };
  streamHandlers = null;
  mockCall = vi.fn(async () => ({ ok: true }));
  mockCallStream = vi.fn((_m, _p, h) => {
    streamHandlers = h;
    return { cancel: vi.fn() };
  });
});

function wrapper({ children }) {
  return <EventsProvider>{children}</EventsProvider>;
}

function frame(event, data) {
  streamHandlers.onFrame({ event, data, at: Date.now() / 1000, seq: Math.floor(Math.random() * 1e6) });
}

const SAMPLE = {
  request_id: "r1",
  question: "Which source?",
  choices: [
    { label: "WHOOP", description: "recovery" },
    { label: "COROS" },
  ],
  allow_other: true,
  profile: "doc",
  timeout_s: 300,
};

describe("useClarificationQueue", () => {
  it("clarification.request enqueues with normalized choices", async () => {
    const { result } = renderHook(() => useClarificationQueue(), { wrapper });
    await waitFor(() => expect(streamHandlers).not.toBeNull());

    await act(async () => {
      streamHandlers.onFrame({ event: "subscribed", next_seq: 0 });
      frame("clarification.request", SAMPLE);
    });

    expect(result.current.current).toMatchObject({
      request_id: "r1",
      question: "Which source?",
      profile: "doc",
      allow_other: true,
    });
    expect(result.current.current.choices.map((c) => c.label)).toEqual(["WHOOP", "COROS"]);
  });

  it("rejects requests with fewer than 2 valid choices", async () => {
    const { result } = renderHook(() => useClarificationQueue(), { wrapper });
    await waitFor(() => expect(streamHandlers).not.toBeNull());

    await act(async () => {
      streamHandlers.onFrame({ event: "subscribed", next_seq: 0 });
      frame("clarification.request", {
        request_id: "r1",
        question: "?",
        choices: [{ label: "Solo" }],
        timeout_s: 60,
      });
    });

    expect(result.current.queue).toEqual([]);
  });

  it("dedupes by request_id", async () => {
    const { result } = renderHook(() => useClarificationQueue(), { wrapper });
    await waitFor(() => expect(streamHandlers).not.toBeNull());

    await act(async () => {
      streamHandlers.onFrame({ event: "subscribed", next_seq: 0 });
      frame("clarification.request", SAMPLE);
      frame("clarification.request", SAMPLE);
    });

    expect(result.current.queue.length).toBe(1);
  });

  it("respond sends the chosen label and pops", async () => {
    const { result } = renderHook(() => useClarificationQueue(), { wrapper });
    await waitFor(() => expect(streamHandlers).not.toBeNull());

    await act(async () => {
      streamHandlers.onFrame({ event: "subscribed", next_seq: 0 });
      frame("clarification.request", SAMPLE);
    });

    await act(async () => {
      await result.current.respond("WHOOP");
    });

    expect(mockCall).toHaveBeenCalledWith("host.clarification.respond", {
      request_id: "r1", choice: "WHOOP",
    });
    expect(result.current.current).toBeNull();
  });

  it("cancel sends a cancellation marker", async () => {
    const { result } = renderHook(() => useClarificationQueue(), { wrapper });
    await waitFor(() => expect(streamHandlers).not.toBeNull());

    await act(async () => {
      streamHandlers.onFrame({ event: "subscribed", next_seq: 0 });
      frame("clarification.request", SAMPLE);
    });

    await act(async () => {
      await result.current.cancel();
    });

    expect(mockCall).toHaveBeenCalledWith("host.clarification.respond", {
      request_id: "r1", choice: "User cancelled clarification.",
    });
    expect(result.current.current).toBeNull();
  });

  it("clarification.resolved pops without an RPC", async () => {
    const { result } = renderHook(() => useClarificationQueue(), { wrapper });
    await waitFor(() => expect(streamHandlers).not.toBeNull());

    await act(async () => {
      streamHandlers.onFrame({ event: "subscribed", next_seq: 0 });
      frame("clarification.request", SAMPLE);
    });
    expect(result.current.current?.request_id).toBe("r1");

    mockCall.mockClear();
    await act(async () => {
      frame("clarification.resolved", { request_id: "r1", choice: "WHOOP", timed_out: false });
    });

    expect(result.current.current).toBeNull();
    expect(mockCall).not.toHaveBeenCalledWith("host.clarification.respond", expect.anything());
  });

  it("queues multiple requests in FIFO order", async () => {
    const { result } = renderHook(() => useClarificationQueue(), { wrapper });
    await waitFor(() => expect(streamHandlers).not.toBeNull());

    await act(async () => {
      streamHandlers.onFrame({ event: "subscribed", next_seq: 0 });
      frame("clarification.request", { ...SAMPLE, request_id: "r1" });
      frame("clarification.request", { ...SAMPLE, request_id: "r2" });
    });

    expect(result.current.current?.request_id).toBe("r1");

    await act(async () => {
      await result.current.respond("WHOOP");
    });

    expect(result.current.current?.request_id).toBe("r2");
  });

  it("cold-start recovery: host.clarification.pending populates queue on mount", async () => {
    mockCall = vi.fn(async (method) => {
      if (method === "host.clarification.pending") {
        return {
          requests: [{ ...SAMPLE, request_id: "stale-1" }],
        };
      }
      return { ok: true };
    });
    const { result } = renderHook(() => useClarificationQueue(), { wrapper });

    await waitFor(() => expect(result.current.current?.request_id).toBe("stale-1"));
    expect(mockCall).toHaveBeenCalledWith("host.clarification.pending", {});
  });

  it("clears the queue when the endpoint changes", async () => {
    const { result, rerender } = renderHook(() => useClarificationQueue(), { wrapper });
    await waitFor(() => expect(streamHandlers).not.toBeNull());
    await act(async () => {
      streamHandlers.onFrame({ event: "subscribed", next_seq: 0 });
      frame("clarification.request", { ...SAMPLE, request_id: "from-alpha" });
    });
    expect(result.current.current?.request_id).toBe("from-alpha");

    mockEndpoint = { id: "beta", ip: "10.0.0.2", port: 49200 };
    mockCall = vi.fn(async () => ({ requests: [] }));
    await act(async () => rerender());

    expect(result.current.current).toBeNull();
  });

  it("empty answer is rejected without an RPC", async () => {
    const { result } = renderHook(() => useClarificationQueue(), { wrapper });
    await waitFor(() => expect(streamHandlers).not.toBeNull());

    await act(async () => {
      streamHandlers.onFrame({ event: "subscribed", next_seq: 0 });
      frame("clarification.request", SAMPLE);
    });

    await act(async () => {
      await result.current.respond("   ");
    });

    expect(result.current.error).toContain("empty");
    expect(mockCall).not.toHaveBeenCalledWith("host.clarification.respond", expect.anything());
    expect(result.current.current?.request_id).toBe("r1");
  });

  it("multi flag is propagated through the queue entry", async () => {
    const { result } = renderHook(() => useClarificationQueue(), { wrapper });
    await waitFor(() => expect(streamHandlers).not.toBeNull());

    await act(async () => {
      streamHandlers.onFrame({ event: "subscribed", next_seq: 0 });
      frame("clarification.request", {
        ...SAMPLE,
        multi: true,
        allow_other: true,
        choices: [{ label: "A" }, { label: "B" }, { label: "C" }],
      });
    });

    expect(result.current.current?.multi).toBe(true);
    // Backend force-drops allow_other when multi is true; mirror in queue.
    expect(result.current.current?.allow_other).toBe(false);
    expect(result.current.current?.choices.map((c) => c.label)).toEqual(["A", "B", "C"]);
  });

  it("multi response is forwarded verbatim as a JSON array string", async () => {
    const { result } = renderHook(() => useClarificationQueue(), { wrapper });
    await waitFor(() => expect(streamHandlers).not.toBeNull());

    await act(async () => {
      streamHandlers.onFrame({ event: "subscribed", next_seq: 0 });
      frame("clarification.request", {
        ...SAMPLE,
        multi: true,
        choices: [{ label: "Sleep summary" }, { label: "Training load" }],
      });
    });

    const wire = JSON.stringify(["Sleep summary", "Training load"]);
    await act(async () => {
      await result.current.respond(wire);
    });

    expect(mockCall).toHaveBeenCalledWith("host.clarification.respond", {
      request_id: "r1",
      choice: wire,
    });
    expect(result.current.current).toBeNull();
  });

  it("server rejection keeps the request in the queue and surfaces the reason", async () => {
    mockCall = vi.fn(async () => ({ ok: false, reason: "unknown label(s): Z" }));
    const { result } = renderHook(() => useClarificationQueue(), { wrapper });
    await waitFor(() => expect(streamHandlers).not.toBeNull());

    await act(async () => {
      streamHandlers.onFrame({ event: "subscribed", next_seq: 0 });
      frame("clarification.request", SAMPLE);
    });

    await act(async () => {
      await result.current.respond("Z");
    });

    expect(result.current.current?.request_id).toBe("r1");
    expect(result.current.error).toBe("unknown label(s): Z");
    expect(result.current.busy).toBe(false);
  });
});
