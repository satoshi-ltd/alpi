import { describe, it, expect, beforeEach, vi } from "vitest";

const memory = new Map();
vi.mock("expo-secure-store", () => ({
  getItemAsync: vi.fn(async (k) => (memory.has(k) ? memory.get(k) : null)),
  setItemAsync: vi.fn(async (k, v) => { memory.set(k, v); }),
  deleteItemAsync: vi.fn(async (k) => { memory.delete(k); }),
}));

beforeEach(() => {
  memory.clear();
  vi.resetModules();
});

const KEY = "alpi.connections";

function validConn(over = {}) {
  return {
    id: "c-1",
    name: "umbrel",
    ip: "100.0.0.1",
    port: 49200,
    token: "tok",
    kind: "remote",
    added_at: 1700000000000,
    deviceId: "mac-uuid",
    ...over,
  };
}

describe("store.loadConnections", () => {
  it("returns the empty shape when nothing is persisted", async () => {
    const { loadConnections } = await import("./store.js");
    const state = await loadConnections();
    expect(state).toEqual({ v: 1, active_id: null, connections: [] });
  });

  it("falls back to empty when persisted JSON is invalid", async () => {
    memory.set(KEY, "{not json");
    const { loadConnections } = await import("./store.js");
    const state = await loadConnections();
    expect(state).toEqual({ v: 1, active_id: null, connections: [] });
  });

  it("drops connections that fail validation (missing token/port)", async () => {
    memory.set(KEY, JSON.stringify({
      v: 1, active_id: "c-1",
      connections: [
        validConn(),
        { id: "broken", ip: "1.1.1.1", port: 1, token: 42, name: "wrong-type-token", deviceId: "x" },
        { id: "no-ip", port: 1, token: "t", name: "x", kind: "remote", deviceId: "y" },
      ],
    }));
    const { loadConnections } = await import("./store.js");
    const state = await loadConnections();
    expect(state.connections.map((c) => c.id)).toEqual(["c-1"]);
  });

  it("drops connections that lack deviceId — daemon identity is mandatory, no legacy fallback", async () => {
    memory.set(KEY, JSON.stringify({
      v: 1, active_id: "no-device",
      connections: [
        validConn(),
        { id: "no-device", ip: "1.1.1.1", port: 1, token: "t", name: "n", kind: "remote" },
        { id: "blank-device", ip: "1.1.1.1", port: 1, token: "t", name: "n", kind: "remote", deviceId: "" },
      ],
    }));
    const { loadConnections } = await import("./store.js");
    const state = await loadConnections();
    expect(state.connections.map((c) => c.id)).toEqual(["c-1"]);
    expect(state.active_id).toBe("c-1");
  });

  it("rewrites active_id to the first connection when it no longer exists", async () => {
    memory.set(KEY, JSON.stringify({
      v: 1, active_id: "ghost",
      connections: [validConn({ id: "alpha" }), validConn({ id: "beta" })],
    }));
    const { loadConnections } = await import("./store.js");
    const state = await loadConnections();
    expect(state.active_id).toBe("alpha");
  });

  it("clears active_id when no valid connections remain", async () => {
    memory.set(KEY, JSON.stringify({ v: 1, active_id: "ghost", connections: [] }));
    const { loadConnections } = await import("./store.js");
    const state = await loadConnections();
    expect(state.active_id).toBeNull();
  });
});

describe("store.saveConnection", () => {
  it("appends a new connection and marks it active", async () => {
    const { saveConnection } = await import("./store.js");
    const state = await saveConnection({ id: "c-1", name: "n", ip: "1.1.1.1", port: 49200, token: "t", deviceId: "mac" });
    expect(state.connections).toHaveLength(1);
    expect(state.active_id).toBe("c-1");
    expect(state.connections[0].deviceId).toBe("mac");
  });

  it("replaces by id without duplicating", async () => {
    const { saveConnection } = await import("./store.js");
    await saveConnection({ id: "c-1", name: "n", ip: "1.1.1.1", port: 49200, token: "t", deviceId: "mac" });
    const state = await saveConnection({ id: "c-1", name: "renamed", ip: "1.1.1.1", port: 49200, token: "t2", deviceId: "mac" });
    expect(state.connections).toHaveLength(1);
    expect(state.connections[0].name).toBe("renamed");
    expect(state.connections[0].token).toBe("t2");
  });

  it("refuses to save without a deviceId — pairing must capture daemon identity", async () => {
    const { saveConnection } = await import("./store.js");
    await expect(
      saveConnection({ id: "c-1", name: "n", ip: "1.1.1.1", port: 49200, token: "t" }),
    ).rejects.toThrow(/deviceId/);
  });
});

describe("store role persistence", () => {
  it("rolesFromConnections maps id→role and skips roleless connections", async () => {
    const { rolesFromConnections } = await import("./store.js");
    const map = rolesFromConnections([
      { id: "a", role: "admin" },
      { id: "b", role: "member" },
      { id: "c" },
    ]);
    expect([...map.entries()]).toEqual([["a", "admin"], ["b", "member"]]);
  });

  it("setRoles persists the role of matching connections only", async () => {
    const { saveConnection, setRoles, loadConnections } = await import("./store.js");
    await saveConnection({ id: "c-1", name: "n", ip: "1.1.1.1", port: 49200, token: "t", deviceId: "mac" });
    await setRoles(new Map([["c-1", "member"], ["ghost", "admin"]]));
    const state = await loadConnections();
    expect(state.connections[0].role).toBe("member");
  });

  it("saveConnection persists a provided role and preserves it on a role-less re-save", async () => {
    const { saveConnection, loadConnections } = await import("./store.js");
    await saveConnection({ id: "c-1", name: "n", ip: "1.1.1.1", port: 49200, token: "t", deviceId: "mac", role: "admin" });
    expect((await loadConnections()).connections[0].role).toBe("admin");
    await saveConnection({ id: "c-1", name: "n2", ip: "1.1.1.1", port: 49200, token: "t2", deviceId: "mac" });
    expect((await loadConnections()).connections[0].role).toBe("admin");
  });

  it("loadConnections keeps a persisted role through validation", async () => {
    memory.set(KEY, JSON.stringify({
      v: 1, active_id: "c-1",
      connections: [validConn({ role: "member" })],
    }));
    const { loadConnections } = await import("./store.js");
    expect((await loadConnections()).connections[0].role).toBe("member");
  });
});

describe("store.removeConnection", () => {
  it("removes and falls back active_id to the next survivor", async () => {
    memory.set(KEY, JSON.stringify({
      v: 1, active_id: "alpha",
      connections: [validConn({ id: "alpha" }), validConn({ id: "beta" })],
    }));
    const { removeConnection } = await import("./store.js");
    const state = await removeConnection("alpha");
    expect(state.connections.map((c) => c.id)).toEqual(["beta"]);
    expect(state.active_id).toBe("beta");
  });

  it("removes the last connection and nulls active_id", async () => {
    memory.set(KEY, JSON.stringify({
      v: 1, active_id: "alpha",
      connections: [validConn({ id: "alpha" })],
    }));
    const { removeConnection } = await import("./store.js");
    const state = await removeConnection("alpha");
    expect(state.connections).toHaveLength(0);
    expect(state.active_id).toBeNull();
  });
});

describe("store.setActiveConnection", () => {
  it("activates a known connection", async () => {
    memory.set(KEY, JSON.stringify({
      v: 1, active_id: "alpha",
      connections: [validConn({ id: "alpha" }), validConn({ id: "beta" })],
    }));
    const { setActiveConnection } = await import("./store.js");
    const state = await setActiveConnection("beta");
    expect(state.active_id).toBe("beta");
  });

  it("is a no-op when the id is unknown (active_id stays put)", async () => {
    memory.set(KEY, JSON.stringify({
      v: 1, active_id: "alpha",
      connections: [validConn({ id: "alpha" })],
    }));
    const { setActiveConnection } = await import("./store.js");
    const state = await setActiveConnection("ghost");
    expect(state.active_id).toBe("alpha");
  });

  it("stamps last_connected on the activated connection", async () => {
    memory.set(KEY, JSON.stringify({
      v: 1, active_id: "alpha",
      connections: [validConn({ id: "alpha" }), validConn({ id: "beta" })],
    }));
    const { setActiveConnection } = await import("./store.js");
    const before = Date.now();
    const state = await setActiveConnection("beta");
    const beta = state.connections.find((c) => c.id === "beta");
    expect(beta.last_connected).toBeGreaterThanOrEqual(before);
    expect(state.connections.find((c) => c.id === "alpha").last_connected).toBeUndefined();
  });
});

describe("store.sortConnectionsByRecency", () => {
  it("orders by last_connected desc, falling back to added_at, never-seen last", async () => {
    const { sortConnectionsByRecency } = await import("./store.js");
    const conns = [
      validConn({ id: "old", last_connected: 100 }),
      validConn({ id: "added-only", last_connected: undefined, added_at: 400 }),
      validConn({ id: "new", last_connected: 900 }),
      validConn({ id: "never", last_connected: undefined, added_at: undefined }),
    ];
    expect(sortConnectionsByRecency(conns).map((c) => c.id)).toEqual([
      "new", "added-only", "old", "never",
    ]);
  });

  it("does not mutate the input array", async () => {
    const { sortConnectionsByRecency } = await import("./store.js");
    const conns = [validConn({ id: "a", last_connected: 1 }), validConn({ id: "b", last_connected: 2 })];
    sortConnectionsByRecency(conns);
    expect(conns.map((c) => c.id)).toEqual(["a", "b"]);
  });
});

describe("store.clearAll", () => {
  it("wipes the connections key and the legacy single-endpoint key (privacy hygiene: unpair() must not leave a stale token from an old build)", async () => {
    memory.set(KEY, JSON.stringify({ v: 1, active_id: null, connections: [] }));
    memory.set("alpi.endpoint", JSON.stringify({ ip: "1", port: 1, token: "stale" }));
    const { clearAll } = await import("./store.js");
    await clearAll();
    expect(memory.has(KEY)).toBe(false);
    expect(memory.has("alpi.endpoint")).toBe(false);
  });
});

describe("store.setDeviceIds", () => {
  it("updates deviceId for matching connections and persists the change", async () => {
    memory.set(KEY, JSON.stringify({
      v: 1, active_id: "alpha",
      connections: [validConn({ id: "alpha", deviceId: "old" }), validConn({ id: "beta", deviceId: "stable" })],
    }));
    const { setDeviceIds } = await import("./store.js");
    const state = await setDeviceIds(new Map([["alpha", "new-uuid"]]));
    expect(state.connections.find((c) => c.id === "alpha").deviceId).toBe("new-uuid");
    expect(state.connections.find((c) => c.id === "beta").deviceId).toBe("stable");
  });

  it("does not rewrite storage when nothing changed", async () => {
    memory.set(KEY, JSON.stringify({
      v: 1, active_id: "alpha",
      connections: [validConn({ id: "alpha", deviceId: "same" })],
    }));
    const { setDeviceIds } = await import("./store.js");
    const before = memory.get(KEY);
    await setDeviceIds(new Map([["alpha", "same"]]));
    expect(memory.get(KEY)).toBe(before);
  });
});
