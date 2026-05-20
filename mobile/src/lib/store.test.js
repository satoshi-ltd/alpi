import { describe, it, expect, beforeEach, vi } from "vitest";

// Pairing/storage is the only mutable state we keep on-device. A bad migration
// or corrupt JSON could brick first-run for any user upgrading from a single-
// endpoint build; the tests below pin every recovery path.

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
const LEGACY_KEY = "alpi.endpoint";

function validConn(over = {}) {
  return {
    id: "c-1",
    name: "umbrel",
    ip: "100.0.0.1",
    port: 49200,
    token: "tok",
    kind: "remote",
    added_at: 1700000000000,
    ...over,
  };
}

describe("store.loadConnections", () => {
  it("returns the empty shape when nothing is persisted", async () => {
    const { loadConnections } = await import("./store.js");
    const state = await loadConnections();
    expect(state).toEqual({ v: 1, active_id: null, connections: [] });
  });

  it("migrates the legacy single-endpoint key and deletes it", async () => {
    memory.set(LEGACY_KEY, JSON.stringify({
      name: "macbook",
      ip: "100.0.0.5",
      port: 49200,
      token: "old-tok",
    }));
    const { loadConnections } = await import("./store.js");
    const state = await loadConnections();
    expect(state.connections).toHaveLength(1);
    expect(state.connections[0]).toMatchObject({
      id: "paired", name: "macbook", ip: "100.0.0.5", port: 49200, token: "old-tok", kind: "remote",
    });
    expect(state.active_id).toBe("paired");
    // legacy key is wiped after promotion so we don't re-migrate.
    expect(memory.has(LEGACY_KEY)).toBe(false);
    // promoted state is now persisted under the new key.
    expect(memory.has(KEY)).toBe(true);
  });

  it("discards a malformed legacy endpoint (no ip/token)", async () => {
    memory.set(LEGACY_KEY, JSON.stringify({ name: "broken" }));
    const { loadConnections } = await import("./store.js");
    const state = await loadConnections();
    expect(state.connections).toHaveLength(0);
    expect(state.active_id).toBeNull();
    expect(memory.has(LEGACY_KEY)).toBe(false);
  });

  it("falls back to empty when the new key has invalid JSON", async () => {
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
        { id: "broken", ip: "1.1.1.1", port: 1, token: 42, name: "wrong-type-token" },
        { id: "no-ip", port: 1, token: "t", name: "x", kind: "remote" },
      ],
    }));
    const { loadConnections } = await import("./store.js");
    const state = await loadConnections();
    expect(state.connections.map((c) => c.id)).toEqual(["c-1"]);
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
    const state = await saveConnection({ id: "c-1", name: "n", ip: "1.1.1.1", port: 49200, token: "t" });
    expect(state.connections).toHaveLength(1);
    expect(state.active_id).toBe("c-1");
  });

  it("replaces by id without duplicating", async () => {
    const { saveConnection } = await import("./store.js");
    await saveConnection({ id: "c-1", name: "n", ip: "1.1.1.1", port: 49200, token: "t" });
    const state = await saveConnection({ id: "c-1", name: "renamed", ip: "1.1.1.1", port: 49200, token: "t2" });
    expect(state.connections).toHaveLength(1);
    expect(state.connections[0].name).toBe("renamed");
    expect(state.connections[0].token).toBe("t2");
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
});

describe("store.clearAll", () => {
  it("wipes both the new key and the legacy migration key", async () => {
    memory.set(KEY, JSON.stringify({ v: 1, active_id: null, connections: [] }));
    memory.set(LEGACY_KEY, JSON.stringify({ ip: "1", port: 1, token: "t" }));
    const { clearAll } = await import("./store.js");
    await clearAll();
    expect(memory.has(KEY)).toBe(false);
    expect(memory.has(LEGACY_KEY)).toBe(false);
  });
});
