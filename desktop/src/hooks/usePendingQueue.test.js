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
