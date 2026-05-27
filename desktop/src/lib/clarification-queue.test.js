import { describe, it, expect } from "vitest";
import {
  deadlineFor,
  enqueueRequest,
  normalizeRequest,
} from "./clarification-queue.js";

describe("clarification-queue", () => {
  it("normalizes valid request shape", () => {
    const out = normalizeRequest({
      request_id: "abc",
      profile: "doc",
      question: "Which?",
      choices: [{ label: "A" }, { label: "B", description: "second" }],
      allow_other: true,
      ts: 1_000,
      timeout_s: 60,
    });
    expect(out).toMatchObject({
      request_id: "abc",
      profile: "doc",
      question: "Which?",
      allow_other: true,
    });
    expect(out.choices).toEqual([
      { label: "A", description: "" },
      { label: "B", description: "second" },
    ]);
    expect(out.deadline).toBeGreaterThan(0);
  });

  it("returns null for missing request_id", () => {
    expect(normalizeRequest({})).toBeNull();
    expect(normalizeRequest(null)).toBeNull();
  });

  it("drops choices with empty labels", () => {
    const out = normalizeRequest({
      request_id: "x",
      choices: [{ label: "A" }, { label: "  " }, { label: "B" }],
      timeout_s: 60, ts: 1_000,
    });
    expect(out.choices.map((c) => c.label)).toEqual(["A", "B"]);
  });

  it("computes deadline from ts + timeout_s", () => {
    expect(deadlineFor({ ts: 1, timeout_s: 60 })).toBe(61_000);
    expect(deadlineFor({ timeout_s: 60 })).toBeGreaterThan(Date.now());
    expect(deadlineFor({})).toBeNull();
  });

  it("dedupes by request_id", () => {
    const req = {
      request_id: "x",
      choices: [{ label: "A" }, { label: "B" }],
      timeout_s: 60, ts: 1_000,
    };
    const q1 = enqueueRequest([], req);
    const q2 = enqueueRequest(q1, req);
    expect(q1.length).toBe(1);
    expect(q2.length).toBe(1);
  });

  it("rejects requests with fewer than 2 choices", () => {
    const out = enqueueRequest([], {
      request_id: "x",
      choices: [{ label: "Solo" }],
      timeout_s: 60, ts: 1_000,
    });
    expect(out).toEqual([]);
  });

  it("defaults multi to false when absent", () => {
    const out = normalizeRequest({
      request_id: "x",
      choices: [{ label: "A" }, { label: "B" }],
      timeout_s: 60, ts: 1_000,
    });
    expect(out.multi).toBe(false);
  });

  it("propagates multi=true and forces allow_other=false", () => {
    const out = normalizeRequest({
      request_id: "x",
      choices: [{ label: "A" }, { label: "B" }],
      multi: true,
      allow_other: true,
      timeout_s: 60, ts: 1_000,
    });
    expect(out.multi).toBe(true);
    expect(out.allow_other).toBe(false);
  });

  it("accepts a multi request with 5 choices", () => {
    const out = enqueueRequest([], {
      request_id: "x",
      multi: true,
      allow_other: false,
      choices: [
        { label: "Python" },
        { label: "TypeScript" },
        { label: "Rust" },
        { label: "Go" },
        { label: "Swift" },
      ],
      timeout_s: 60, ts: 1_000,
    });
    expect(out).toHaveLength(1);
    expect(out[0].multi).toBe(true);
    expect(out[0].choices).toHaveLength(5);
  });

  it("preserves order across multiple distinct requests", () => {
    const q1 = enqueueRequest([], {
      request_id: "a",
      choices: [{ label: "1" }, { label: "2" }],
      timeout_s: 60, ts: 1_000,
    });
    const q2 = enqueueRequest(q1, {
      request_id: "b",
      choices: [{ label: "3" }, { label: "4" }],
      timeout_s: 60, ts: 1_000,
    });
    expect(q2.map((r) => r.request_id)).toEqual(["a", "b"]);
  });
});
