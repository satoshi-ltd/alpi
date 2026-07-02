import { beforeEach, describe, expect, it, vi } from "vitest";

let busHandlers;
vi.mock("./daemon-bus.js", () => ({
  subscribeDaemonEvent: (fn) => {
    busHandlers.add(fn);
    return () => busHandlers.delete(fn);
  },
}));

import { createSwrCache, invalidateConnectionCaches, _clearAllSwrCaches } from "./swr-cache.js";

function emit(payload) {
  for (const fn of Array.from(busHandlers)) fn({ payload });
}

beforeEach(() => {
  busHandlers = new Set();
  _clearAllSwrCaches();
  vi.useRealTimers();
});

describe("createSwrCache", () => {
  it("load stores the fetched value and get serves it synchronously afterwards", async () => {
    const cache = createSwrCache({ fetcher: async ({ n }) => n * 2 });
    await cache.load("c1|a", { n: 21 });
    expect(cache.get("c1|a")).toBe(42);
  });

  it("dedupes concurrent loads for the same key", async () => {
    const fetcher = vi.fn(async () => "v");
    const cache = createSwrCache({ fetcher });
    const p1 = cache.load("c1|a", {});
    const p2 = cache.load("c1|a", {});
    expect(p1).toBe(p2);
    await p1;
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("a slow stale response never clobbers a newer forced value", async () => {
    let resolveSlow;
    const fetcher = vi
      .fn()
      .mockImplementationOnce(() => new Promise((r) => { resolveSlow = r; }))
      .mockResolvedValueOnce("fresh");
    const cache = createSwrCache({ fetcher });
    cache.load("c1|a", {});
    await cache.load("c1|a", {}, { force: true });
    expect(cache.get("c1|a")).toBe("fresh");
    resolveSlow("stale");
    await Promise.resolve();
    expect(cache.get("c1|a")).toBe("fresh");
  });

  it("keeps the last good value on transient errors and exposes the error", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce("good")
      .mockRejectedValueOnce(new Error("read timeout"));
    const cache = createSwrCache({ fetcher });
    await cache.load("c1|a", {});
    await cache.load("c1|a", {}, { force: true });
    expect(cache.get("c1|a")).toBe("good");
    expect(String(cache.errorOf("c1|a"))).toContain("read timeout");
  });

  it("drops the value on auth-failed", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce("good")
      .mockRejectedValueOnce(new Error("alp -32000: auth-failed"));
    const cache = createSwrCache({ fetcher });
    await cache.load("c1|a", {});
    await cache.load("c1|a", {}, { force: true });
    expect(cache.get("c1|a")).toBeUndefined();
  });

  it("a matching daemon event refetches a WATCHED key (coalesced)", async () => {
    const fetcher = vi.fn().mockResolvedValueOnce("v1").mockResolvedValue("v2");
    const cache = createSwrCache({
      fetcher,
      coalesceMs: 10,
      events: {
        kinds: new Set(["email_changed"]),
        match: (key, frame) => key.endsWith(`|${frame?.data?.profile}`),
      },
    });
    const unsub = cache.subscribe("c1|doc", () => {});
    await cache.load("c1|doc", {});
    for (let i = 0; i < 20; i += 1) {
      emit({ connection_id: "c1", frame: { event: "email_changed", data: { profile: "doc" } } });
    }
    await new Promise((r) => setTimeout(r, 30));
    expect(fetcher).toHaveBeenCalledTimes(2);
    expect(cache.get("c1|doc")).toBe("v2");
    unsub();
  });

  it("a matching daemon event DROPS an unwatched key instead of refetching it", async () => {
    const fetcher = vi.fn().mockResolvedValue("v1");
    const cache = createSwrCache({
      fetcher,
      coalesceMs: 10,
      events: {
        kinds: new Set(["email_changed"]),
        match: (key, frame) => key.endsWith(`|${frame?.data?.profile}`),
      },
    });
    const unsub = cache.subscribe("c1|doc", () => {});
    await cache.load("c1|doc", {});
    unsub();
    emit({ connection_id: "c1", frame: { event: "email_changed", data: { profile: "doc" } } });
    await new Promise((r) => setTimeout(r, 30));
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(cache.get("c1|doc")).toBeUndefined();
  });

  it("seed stores a value without fetching and wins over an inflight load", async () => {
    let resolveSlow;
    const fetcher = vi.fn(() => new Promise((r) => { resolveSlow = r; }));
    const cache = createSwrCache({ fetcher });
    cache.load("c1|a", {});
    cache.seed("c1|a", "seeded");
    resolveSlow("from-fetch");
    await Promise.resolve();
    expect(cache.get("c1|a")).toBe("seeded");
  });

  it("invalidateConnection drops only that connection's keys", async () => {
    const cache = createSwrCache({ fetcher: async ({ v }) => v });
    await cache.load("c1|a", { v: 1 });
    await cache.load("c2|a", { v: 2 });
    cache.invalidateConnection("c1");
    expect(cache.get("c1|a")).toBeUndefined();
    expect(cache.get("c2|a")).toBe(2);
  });

  it("invalidateConnectionCaches sweeps every registered cache", async () => {
    const a = createSwrCache({ fetcher: async () => "a" });
    const b = createSwrCache({ fetcher: async () => "b" });
    await a.load("gone|x", {});
    await b.load("gone|y", {});
    await b.load("kept|y", {});
    invalidateConnectionCaches("gone");
    expect(a.get("gone|x")).toBeUndefined();
    expect(b.get("gone|y")).toBeUndefined();
    expect(b.get("kept|y")).toBe("b");
  });
});
