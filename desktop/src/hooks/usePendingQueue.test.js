import { describe, it, expect, beforeEach, vi } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { invoke } from "@tauri-apps/api/core";
import { usePendingQueue } from "./usePendingQueue.js";

function enqueue(queue, req) {
  if (!req?.request_id) return queue;
  if (queue.some((r) => r.request_id === req.request_id)) return queue;
  return [...queue, req];
}

beforeEach(() => {
  vi.resetAllMocks();
});

describe("usePendingQueue", () => {
  it("cold-start fetch populates the queue and resolve removes entries", async () => {
    invoke.mockResolvedValueOnce({ requests: [{ request_id: "a" }, { request_id: "b" }] });
    const { result } = renderHook(() =>
      usePendingQueue({ command: "approval_pending", connectionId: "local", enqueue }),
    );
    await waitFor(() => expect(result.current.queue).toHaveLength(2));
    act(() => result.current.resolve("a"));
    expect(result.current.queue.map((r) => r.request_id)).toEqual(["b"]);
  });

  it("merge dedupes through the provided enqueue", async () => {
    invoke.mockResolvedValueOnce({ requests: [] });
    const { result } = renderHook(() =>
      usePendingQueue({ command: "approval_pending", connectionId: "local", enqueue }),
    );
    await waitFor(() => expect(invoke).toHaveBeenCalled());
    act(() => {
      result.current.merge({ request_id: "x" });
      result.current.merge({ request_id: "x" });
    });
    expect(result.current.queue).toHaveLength(1);
  });

  it("a connection switch drops the stale queue and refetches", async () => {
    invoke
      .mockResolvedValueOnce({ requests: [{ request_id: "old" }] })
      .mockResolvedValueOnce({ requests: [{ request_id: "new" }] });
    const { result, rerender } = renderHook(
      ({ conn }) => usePendingQueue({ command: "approval_pending", connectionId: conn, enqueue }),
      { initialProps: { conn: "local" } },
    );
    await waitFor(() => expect(result.current.queue.map((r) => r.request_id)).toEqual(["old"]));
    rerender({ conn: "remote" });
    await waitFor(() => expect(result.current.queue.map((r) => r.request_id)).toEqual(["new"]));
  });
});

describe("usePendingQueue reconcile", () => {
  it("refetch drops a request another client resolved while the stream was down and keeps the order", async () => {
    invoke
      .mockResolvedValueOnce({ requests: [{ request_id: "a" }, { request_id: "b" }, { request_id: "c" }] })
      .mockResolvedValueOnce({ requests: [{ request_id: "c" }, { request_id: "b" }, { request_id: "d" }] });
    const { result } = renderHook(() =>
      usePendingQueue({ command: "approval_pending", connectionId: "local", enqueue }),
    );
    await waitFor(() => expect(result.current.queue).toHaveLength(3));
    await act(async () => { await result.current.refetch(); });
    expect(result.current.queue.map((r) => r.request_id)).toEqual(["b", "c", "d"]);
  });

  it("keeps a request that arrived live while the refetch was in flight", async () => {
    let answer;
    invoke
      .mockResolvedValueOnce({ requests: [{ request_id: "a" }] })
      .mockImplementationOnce(() => new Promise((resolve) => { answer = resolve; }));
    const { result } = renderHook(() =>
      usePendingQueue({ command: "approval_pending", connectionId: "local", enqueue }),
    );
    await waitFor(() => expect(result.current.queue).toHaveLength(1));
    let pending;
    act(() => { pending = result.current.refetch(); });
    act(() => result.current.merge({ request_id: "live" }));
    await act(async () => { answer({ requests: [{ request_id: "a" }] }); await pending; });
    expect(result.current.queue.map((r) => r.request_id)).toEqual(["a", "live"]);
  });

  it("ignores the answer of a connection the user has already left", async () => {
    let answer;
    invoke
      .mockResolvedValueOnce({ requests: [{ request_id: "a" }] })
      .mockImplementationOnce(() => new Promise((resolve) => { answer = resolve; }))
      .mockResolvedValueOnce({ requests: [{ request_id: "b" }] });
    const { result, rerender } = renderHook(
      ({ conn }) => usePendingQueue({ command: "approval_pending", connectionId: conn, enqueue }),
      { initialProps: { conn: "one" } },
    );
    await waitFor(() => expect(result.current.queue).toHaveLength(1));
    let pending;
    act(() => { pending = result.current.refetch(); });
    rerender({ conn: "two" });
    await waitFor(() => expect(result.current.queue.map((r) => r.request_id)).toEqual(["b"]));
    await act(async () => { answer({ requests: [{ request_id: "from-one" }] }); await pending; });
    expect(result.current.queue.map((r) => r.request_id)).toEqual(["b"]);
  });

  it("a failed refetch leaves the queue alone", async () => {
    invoke
      .mockResolvedValueOnce({ requests: [{ request_id: "a" }] })
      .mockRejectedValueOnce(new Error("offline"));
    const { result } = renderHook(() =>
      usePendingQueue({ command: "approval_pending", connectionId: "local", enqueue }),
    );
    await waitFor(() => expect(result.current.queue).toHaveLength(1));
    await act(async () => { await result.current.refetch(); });
    expect(result.current.queue.map((r) => r.request_id)).toEqual(["a"]);
  });
});

describe("usePendingQueue review", () => {
  it("refetch pulls a request the event stream missed and promote moves it to the front", async () => {
    invoke
      .mockResolvedValueOnce({ requests: [{ request_id: "a" }] })
      .mockResolvedValueOnce({ requests: [{ request_id: "a" }, { request_id: "b" }] });
    const { result } = renderHook(() =>
      usePendingQueue({ command: "clarification_pending", connectionId: "local", enqueue }),
    );
    await waitFor(() => expect(result.current.queue).toHaveLength(1));
    await act(async () => { await result.current.refetch(); });
    expect(result.current.queue.map((r) => r.request_id)).toEqual(["a", "b"]);
    act(() => result.current.promote("b"));
    expect(result.current.queue.map((r) => r.request_id)).toEqual(["b", "a"]);
    act(() => result.current.promote("missing"));
    expect(result.current.queue.map((r) => r.request_id)).toEqual(["b", "a"]);
  });
});
