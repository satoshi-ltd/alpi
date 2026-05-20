import { describe, it, expect, beforeEach, vi } from "vitest";
import { invoke } from "@tauri-apps/api/core";
import {
  mergeByseq,
  fetchWorkgroupTranscript,
  invalidateTranscriptCache,
  _resetTranscriptCachesForTests,
} from "./workgroup-fetch.js";

beforeEach(() => {
  _resetTranscriptCachesForTests();
  vi.resetAllMocks();
});

describe("mergeByseq", () => {
  it("returns next when prev is empty", () => {
    expect(mergeByseq([], [{ seq: 1 }])).toEqual([{ seq: 1 }]);
    expect(mergeByseq(null, [{ seq: 1 }])).toEqual([{ seq: 1 }]);
  });

  it("returns prev when next is empty", () => {
    expect(mergeByseq([{ seq: 1 }], [])).toEqual([{ seq: 1 }]);
    expect(mergeByseq([{ seq: 1 }], null)).toEqual([{ seq: 1 }]);
  });

  it("appends only the new seqs, sorted", () => {
    const prev = [{ seq: 1 }, { seq: 3 }];
    const next = [{ seq: 2 }, { seq: 3 }, { seq: 4 }];
    expect(mergeByseq(prev, next).map((p) => p.seq)).toEqual([1, 2, 3, 4]);
  });

  it("keeps prev untouched when there is nothing new (referential identity)", () => {
    // Cheap signal that consumers can rely on `===` to detect no-change renders.
    const prev = [{ seq: 1 }, { seq: 2 }];
    const next = [{ seq: 1 }, { seq: 2 }];
    expect(mergeByseq(prev, next)).toBe(prev);
  });
});

describe("fetchWorkgroupTranscript", () => {
  it("first call uses tail=true, limit=200", async () => {
    invoke.mockResolvedValueOnce({ posts: [], next_seq: 0 });
    await fetchWorkgroupTranscript("conn-a", "doc", "wg-1");
    expect(invoke).toHaveBeenCalledWith("workgroup_transcript", {
      profile: "doc",
      wgId: "wg-1",
      tail: true,
      limit: 200,
    });
  });

  it("subsequent call uses the cached cursor as after_seq", async () => {
    invoke.mockResolvedValueOnce({ posts: [{ seq: 5 }], next_seq: 5 });
    await fetchWorkgroupTranscript("conn-a", "doc", "wg-1");
    invoke.mockResolvedValueOnce({ posts: [], next_seq: 5 });
    await fetchWorkgroupTranscript("conn-a", "doc", "wg-1");
    expect(invoke).toHaveBeenLastCalledWith("workgroup_transcript", {
      profile: "doc",
      wgId: "wg-1",
      afterSeq: 5,
      limit: 200,
    });
  });

  it("dedupe in-flight: two concurrent callers share one round trip", async () => {
    let resolveFn;
    invoke.mockImplementationOnce(
      () => new Promise((r) => { resolveFn = r; }),
    );
    const p1 = fetchWorkgroupTranscript("conn-a", "doc", "wg-1");
    const p2 = fetchWorkgroupTranscript("conn-a", "doc", "wg-1");
    expect(invoke).toHaveBeenCalledTimes(1);
    resolveFn({ posts: [{ seq: 1 }], next_seq: 1 });
    const [a, b] = await Promise.all([p1, p2]);
    expect(a).toBe(b);
    expect(a.map((p) => p.seq)).toEqual([1]);
  });

  it("merges incremental posts into the cached transcript", async () => {
    invoke.mockResolvedValueOnce({ posts: [{ seq: 1 }, { seq: 2 }], next_seq: 2 });
    await fetchWorkgroupTranscript("conn-a", "doc", "wg-1");
    invoke.mockResolvedValueOnce({ posts: [{ seq: 3 }], next_seq: 3 });
    const merged = await fetchWorkgroupTranscript("conn-a", "doc", "wg-1");
    expect(merged.map((p) => p.seq)).toEqual([1, 2, 3]);
  });

  it("falls back to bare-array response (older daemons)", async () => {
    invoke.mockResolvedValueOnce([{ seq: 1 }, { seq: 2 }]);
    const out = await fetchWorkgroupTranscript("conn-a", "doc", "wg-1");
    expect(out.map((p) => p.seq)).toEqual([1, 2]);
  });

  it("explicit afterSeq option overrides cached cursor", async () => {
    invoke.mockResolvedValueOnce({ posts: [{ seq: 10 }], next_seq: 10 });
    await fetchWorkgroupTranscript("conn-a", "doc", "wg-1");
    invoke.mockResolvedValueOnce({ posts: [], next_seq: 10 });
    await fetchWorkgroupTranscript("conn-a", "doc", "wg-1", { afterSeq: 5 });
    expect(invoke).toHaveBeenLastCalledWith("workgroup_transcript", {
      profile: "doc",
      wgId: "wg-1",
      afterSeq: 5,
      limit: 200,
    });
  });
});

describe("invalidateTranscriptCache", () => {
  it("clears only the given connection prefix", async () => {
    invoke.mockResolvedValue({ posts: [{ seq: 1 }], next_seq: 1 });
    await fetchWorkgroupTranscript("conn-a", "doc", "wg-1");
    await fetchWorkgroupTranscript("conn-b", "doc", "wg-1");

    invalidateTranscriptCache("conn-a");

    // conn-a's cursor reset → next fetch goes back to tail=true.
    invoke.mockResolvedValueOnce({ posts: [], next_seq: 0 });
    await fetchWorkgroupTranscript("conn-a", "doc", "wg-1");
    expect(invoke).toHaveBeenLastCalledWith("workgroup_transcript", {
      profile: "doc",
      wgId: "wg-1",
      tail: true,
      limit: 200,
    });

    // conn-b still has its cursor → uses after_seq.
    invoke.mockResolvedValueOnce({ posts: [], next_seq: 1 });
    await fetchWorkgroupTranscript("conn-b", "doc", "wg-1");
    expect(invoke).toHaveBeenLastCalledWith("workgroup_transcript", {
      profile: "doc",
      wgId: "wg-1",
      afterSeq: 1,
      limit: 200,
    });
  });
});
