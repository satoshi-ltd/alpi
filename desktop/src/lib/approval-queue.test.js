import { describe, it, expect } from "vitest";
import { deadlineFor, enqueueRequest, normalizeRequest } from "./approval-queue.js";

describe("deadlineFor", () => {
  it("returns null when timeout_s missing", () => {
    expect(deadlineFor({})).toBeNull();
    expect(deadlineFor(null)).toBeNull();
  });

  it("uses daemon `ts` when present so cold-start fetches show remaining time, not the full window", () => {
    const tsFortySecondsAgo = Date.now() / 1000 - 40;
    const deadline = deadlineFor({ ts: tsFortySecondsAgo, timeout_s: 60 });
    const remainingMs = deadline - Date.now();
    expect(remainingMs).toBeLessThan(25_000);
    expect(remainingMs).toBeGreaterThan(15_000);
  });

  it("falls back to now + timeout when `ts` missing", () => {
    const deadline = deadlineFor({ timeout_s: 60 });
    const diff = Math.abs(deadline - (Date.now() + 60_000));
    expect(diff).toBeLessThan(1000);
  });
});

describe("normalizeRequest", () => {
  it("fills defaults for command / severity / pattern / profile", () => {
    expect(normalizeRequest({ request_id: "r1", timeout_s: 60 })).toMatchObject({
      request_id: "r1",
      command: "",
      severity: "caution",
      pattern: "",
      profile: null,
    });
  });

  it("returns null when request_id missing", () => {
    expect(normalizeRequest({})).toBeNull();
    expect(normalizeRequest(null)).toBeNull();
  });
});

describe("enqueueRequest", () => {
  it("appends a new request to the queue", () => {
    const q = enqueueRequest([], {
      request_id: "r1", command: "rm -rf build", pattern: "recursive rm", severity: "caution", timeout_s: 60,
    });
    expect(q).toHaveLength(1);
    expect(q[0].command).toBe("rm -rf build");
  });

  it("dedupes by request_id (re-delivery via backfill / pending refetch)", () => {
    const start = enqueueRequest([], { request_id: "r1", timeout_s: 60 });
    const after = enqueueRequest(start, { request_id: "r1", timeout_s: 60 });
    expect(after).toBe(start);
  });

  it("preserves FIFO order across distinct request_ids", () => {
    let q = enqueueRequest([], { request_id: "a", timeout_s: 60 });
    q = enqueueRequest(q, { request_id: "b", timeout_s: 60 });
    q = enqueueRequest(q, { request_id: "c", timeout_s: 60 });
    expect(q.map((r) => r.request_id)).toEqual(["a", "b", "c"]);
  });

  it("drops invalid requests silently", () => {
    expect(enqueueRequest([], null)).toEqual([]);
    expect(enqueueRequest([], {})).toEqual([]);
  });
});
