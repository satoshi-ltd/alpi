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
const { useApprovalQueue } = await import("./useApprovalQueue.js");

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

describe("useApprovalQueue", () => {
  it("approval.request enqueues a pending entry with the command + pattern", async () => {
    const { result } = renderHook(() => useApprovalQueue(), { wrapper });
    await waitFor(() => expect(streamHandlers).not.toBeNull());

    await act(async () => {
      streamHandlers.onFrame({ event: "subscribed", next_seq: 0 });
      frame("approval.request", {
        request_id: "r1",
        command: "rm -rf build",
        severity: "caution",
        pattern: "recursive rm",
        profile: "doc",
        timeout_s: 60,
      });
    });

    expect(result.current.current).toMatchObject({
      request_id: "r1",
      command: "rm -rf build",
      pattern: "recursive rm",
      severity: "caution",
      profile: "doc",
    });
  });

  it("ignores a duplicate approval.request for the same request_id (re-delivered via backfill)", async () => {
    const { result } = renderHook(() => useApprovalQueue(), { wrapper });
    await waitFor(() => expect(streamHandlers).not.toBeNull());

    await act(async () => {
      streamHandlers.onFrame({ event: "subscribed", next_seq: 0 });
      frame("approval.request", { request_id: "r1", command: "rm -rf build", pattern: "recursive rm", severity: "caution", timeout_s: 60 });
      frame("approval.request", { request_id: "r1", command: "rm -rf build", pattern: "recursive rm", severity: "caution", timeout_s: 60 });
    });

    expect(result.current.queue.length).toBe(1);
  });

  it("respond('once') calls host.approval.respond and pops the current entry", async () => {
    const { result } = renderHook(() => useApprovalQueue(), { wrapper });
    await waitFor(() => expect(streamHandlers).not.toBeNull());

    await act(async () => {
      streamHandlers.onFrame({ event: "subscribed", next_seq: 0 });
      frame("approval.request", { request_id: "r1", command: "rm -rf build", pattern: "recursive rm", severity: "caution", timeout_s: 60 });
    });

    await act(async () => {
      await result.current.respond("once");
    });

    expect(mockCall).toHaveBeenCalledWith("host.approval.respond", { request_id: "r1", choice: "once" });
    expect(result.current.current).toBeNull();
  });

  it("approval.resolved (from another client) pops the matching pending request without RPC", async () => {
    const { result } = renderHook(() => useApprovalQueue(), { wrapper });
    await waitFor(() => expect(streamHandlers).not.toBeNull());

    await act(async () => {
      streamHandlers.onFrame({ event: "subscribed", next_seq: 0 });
      frame("approval.request", { request_id: "r1", command: "rm -rf build", pattern: "recursive rm", severity: "caution", timeout_s: 60 });
    });
    expect(result.current.current?.request_id).toBe("r1");

    mockCall.mockClear();
    await act(async () => {
      frame("approval.resolved", { request_id: "r1", choice: "once" });
    });

    expect(result.current.current).toBeNull();
    // After mockClear, only an unwanted host.approval.respond would show up.
    expect(mockCall).not.toHaveBeenCalledWith("host.approval.respond", expect.anything());
  });

  it("queues multiple requests in FIFO order", async () => {
    const { result } = renderHook(() => useApprovalQueue(), { wrapper });
    await waitFor(() => expect(streamHandlers).not.toBeNull());

    await act(async () => {
      streamHandlers.onFrame({ event: "subscribed", next_seq: 0 });
      frame("approval.request", { request_id: "r1", pattern: "recursive rm", severity: "caution", timeout_s: 60 });
      frame("approval.request", { request_id: "r2", pattern: "sudo", severity: "caution", timeout_s: 60 });
    });

    expect(result.current.current?.request_id).toBe("r1");

    await act(async () => {
      await result.current.respond("deny");
    });

    expect(result.current.current?.request_id).toBe("r2");
  });

  it("fetches host.approval.pending on mount so a cold-start client sees in-flight approvals it missed via the live stream", async () => {
    mockCall = vi.fn(async (method) => {
      if (method === "host.approval.pending") {
        return {
          requests: [
            { request_id: "stale-1", command: "rm -rf old", severity: "caution", pattern: "recursive rm", timeout_s: 60 },
          ],
        };
      }
      return { ok: true };
    });
    const { result } = renderHook(() => useApprovalQueue(), { wrapper });

    await waitFor(() => expect(result.current.current?.request_id).toBe("stale-1"));
    expect(mockCall).toHaveBeenCalledWith("host.approval.pending", {});
  });

  it("derives `deadline` from the daemon's `ts` so a cold-start client shows remaining time, not the full window", async () => {
    const tsFortySecondsAgo = Date.now() / 1000 - 40;
    mockCall = vi.fn(async (method) => {
      if (method === "host.approval.pending") {
        return {
          requests: [{
            request_id: "stale", command: "rm -rf x", pattern: "recursive rm", severity: "caution",
            ts: tsFortySecondsAgo, timeout_s: 60,
          }],
        };
      }
      return { ok: true };
    });
    const { result } = renderHook(() => useApprovalQueue(), { wrapper });
    await waitFor(() => expect(result.current.current?.request_id).toBe("stale"));

    const remainingMs = result.current.current.deadline - Date.now();
    // ~20s remain, not ~60s — would be ~60_000 if we'd ignored `ts`.
    expect(remainingMs).toBeLessThan(25_000);
    expect(remainingMs).toBeGreaterThan(15_000);
  });

  it("clears the queue when the endpoint changes so a stale entry can't be responded against the new daemon", async () => {
    const { result, rerender } = renderHook(() => useApprovalQueue(), { wrapper });
    await waitFor(() => expect(streamHandlers).not.toBeNull());
    await act(async () => {
      streamHandlers.onFrame({ event: "subscribed", next_seq: 0 });
      frame("approval.request", { request_id: "from-alpha", command: "rm -rf old", pattern: "recursive rm", severity: "caution", timeout_s: 60 });
    });
    expect(result.current.current?.request_id).toBe("from-alpha");

    // Swap endpoint — the useEffect dep flips, the queue must be dumped before the pending fetch runs.
    mockEndpoint = { id: "beta", ip: "10.0.0.2", port: 49200 };
    mockCall = vi.fn(async () => ({ requests: [] }));
    await act(async () => rerender());

    expect(result.current.current).toBeNull();
  });

  it("surfaces a 'no longer pending' reason when daemon responds ok:false (race with timeout)", async () => {
    mockCall = vi.fn(async () => ({ ok: false, reason: "unknown or already resolved" }));
    const { result } = renderHook(() => useApprovalQueue(), { wrapper });
    await waitFor(() => expect(streamHandlers).not.toBeNull());

    await act(async () => {
      streamHandlers.onFrame({ event: "subscribed", next_seq: 0 });
      frame("approval.request", { request_id: "r1", pattern: "recursive rm", severity: "caution", timeout_s: 60 });
    });

    await act(async () => {
      await result.current.respond("once");
    });

    expect(result.current.error).toContain("already resolved");
    // request still popped locally so the sheet doesn't get stuck
    expect(result.current.current).toBeNull();
  });
});
