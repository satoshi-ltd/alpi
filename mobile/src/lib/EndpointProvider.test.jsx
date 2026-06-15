import { describe, it, expect, beforeEach, vi } from "vitest";
import { act, render, waitFor } from "@testing-library/react";

// Spy on the pieces we care about. setActive must drop the previous endpoint's
// pooled WS; forget must drop only the target's pool; rpc.call routes to the
// active endpoint.
const drops = [];
const callSpy = vi.fn(async () => ({}));
const callStreamSpy = vi.fn(() => ({ cancel: vi.fn() }));

vi.mock("./rpc", () => ({
  call: (...args) => callSpy(...args),
  callStream: (...args) => callStreamSpy(...args),
  dropEndpointPool: (endpoint) => { drops.push(endpoint?.id ?? null); },
}));

// Mutable store state — each test resets in beforeEach.
let storeState;
const storeMutations = [];

vi.mock("./store", () => ({
  loadConnections: async () => structuredClone(storeState),
  saveConnection: async (conn) => {
    storeMutations.push({ op: "save", conn });
    const existing = storeState.connections.findIndex((c) => c.id === conn.id);
    if (existing >= 0) storeState.connections[existing] = conn;
    else storeState.connections.push(conn);
    if (!storeState.active_id) storeState.active_id = conn.id;
  },
  removeConnection: async (id) => {
    storeMutations.push({ op: "remove", id });
    storeState.connections = storeState.connections.filter((c) => c.id !== id);
    if (storeState.active_id === id) {
      storeState.active_id = storeState.connections[0]?.id ?? null;
    }
  },
  setActiveConnection: async (id) => {
    storeMutations.push({ op: "active", id });
    storeState.active_id = id;
  },
  clearAll: async () => {
    storeMutations.push({ op: "clear" });
    storeState = { v: 1, active_id: null, connections: [] };
  },
  setDeviceIds: async (map) => {
    storeMutations.push({ op: "setDeviceIds", count: map.size });
    for (const conn of storeState.connections) {
      const next = map.get(conn.id);
      if (next) conn.deviceId = next;
    }
    return structuredClone(storeState);
  },
}));

// Probe returns whatever the test sets. Default: every connection is online.
let probeResults = new Map();
vi.mock("./probe", () => ({
  probe: async (endpoint) => probeResults.get(endpoint.id) ?? { status: "online", version: "0.4.54", deviceId: null },
  probeAll: async (connections) => {
    const status = new Map();
    const versions = new Map();
    const updates = new Map();
    const deviceIds = new Map();
    for (const c of connections) {
      const r = probeResults.get(c.id) ?? { status: "online", version: "0.4.54" };
      status.set(c.id, r.status);
      if (r.version) versions.set(c.id, r.version);
      if (r.updateAvailable) updates.set(c.id, r.updateAvailable);
      if (r.deviceId) deviceIds.set(c.id, r.deviceId);
    }
    return { status, versions, updates, deviceIds };
  },
}));

const { EndpointProvider } = await import("./EndpointProvider.jsx");
const { useEndpoint } = await import("./EndpointContext.jsx");

beforeEach(() => {
  drops.length = 0;
  storeMutations.length = 0;
  probeResults = new Map();
  callSpy.mockClear();
  callStreamSpy.mockClear();
  storeState = {
    v: 1,
    active_id: "alpha",
    connections: [
      { id: "alpha", name: "umbrel", ip: "100.0.0.1", port: 49200, token: "a", kind: "remote" },
      { id: "beta", name: "macbook", ip: "100.0.0.2", port: 49200, token: "b", kind: "remote" },
    ],
  };
});

function Harness({ captureRef }) {
  const ctx = useEndpoint();
  captureRef.current = ctx;
  return null;
}

async function mount() {
  const captureRef = { current: null };
  const utils = render(
    <EndpointProvider>
      <Harness captureRef={captureRef} />
    </EndpointProvider>,
  );
  await waitFor(() => expect(captureRef.current?.ready).toBe(true));
  return { ...utils, captureRef };
}

describe("EndpointProvider lifecycle", () => {
  it("loads stored connections and probes ONLY the active endpoint on cold start", async () => {
    const { captureRef } = await mount();
    expect(captureRef.current.connections).toHaveLength(2);
    expect(captureRef.current.activeId).toBe("alpha");
    expect(captureRef.current.endpoint.id).toBe("alpha");
    expect(captureRef.current.probeState.get("alpha")).toBe("online");
    expect(captureRef.current.probeState.has("beta")).toBe(false);
    expect(captureRef.current.versionState.get("alpha")).toBe("0.4.54");
  });

  it("setActive drops the previous endpoint's pool and writes the new active id", async () => {
    const { captureRef } = await mount();
    await act(async () => { await captureRef.current.setActive("beta"); });
    expect(drops).toEqual(["alpha"]);
    expect(storeMutations.some((m) => m.op === "active" && m.id === "beta")).toBe(true);
    expect(captureRef.current.activeId).toBe("beta");
    expect(captureRef.current.endpoint.id).toBe("beta");
  });

  it("forget drops only the targeted endpoint's pool", async () => {
    const { captureRef } = await mount();
    await act(async () => { await captureRef.current.forget("beta"); });
    expect(drops).toEqual(["beta"]);
    expect(captureRef.current.connections.find((c) => c.id === "beta")).toBeUndefined();
    expect(captureRef.current.activeId).toBe("alpha");
  });

  it("forgetting the active endpoint falls back to the next connection", async () => {
    const { captureRef } = await mount();
    await act(async () => { await captureRef.current.forget("alpha"); });
    expect(drops).toEqual(["alpha"]);
    expect(captureRef.current.activeId).toBe("beta");
    expect(captureRef.current.endpoint.id).toBe("beta");
  });

  it("unpair wipes all pools and clears the store", async () => {
    const { captureRef } = await mount();
    await act(async () => { await captureRef.current.unpair(); });
    expect(new Set(drops)).toEqual(new Set(["alpha", "beta"]));
    expect(storeMutations.some((m) => m.op === "clear")).toBe(true);
    expect(captureRef.current.connections).toHaveLength(0);
    expect(captureRef.current.endpoint).toBeNull();
  });

  it("probeOne updates status + version for a single endpoint without touching others", async () => {
    const { captureRef } = await mount();
    probeResults.set("beta", { status: "offline", version: null });
    await act(async () => { await captureRef.current.probeOne("beta"); });
    expect(captureRef.current.probeState.get("beta")).toBe("offline");
    expect(captureRef.current.versionState.has("beta")).toBe(false);
    // alpha untouched.
    expect(captureRef.current.probeState.get("alpha")).toBe("online");
  });

  it("probeOne records update_available so the badge updates without a full reload", async () => {
    const { captureRef } = await mount();
    probeResults.set("beta", { status: "online", version: "0.9.4", updateAvailable: "0.9.5" });
    await act(async () => { await captureRef.current.probeOne("beta"); });
    expect(captureRef.current.updateState.get("beta")).toBe("0.9.5");
  });
});

describe("EndpointProvider call routing", () => {
  it("call() routes through the active endpoint", async () => {
    const { captureRef } = await mount();
    await act(async () => { await captureRef.current.call("host.profile.summaries", {}); });
    const args = callSpy.mock.calls[0];
    expect(args[0].id).toBe("alpha");
    expect(args[1]).toBe("host.profile.summaries");
  });

  it("call() rejects when there's no active endpoint", async () => {
    storeState = { v: 1, active_id: null, connections: [] };
    const { captureRef } = await mount();
    await expect(captureRef.current.call("host.profile.summaries", {})).rejects.toThrow(/No active/);
  });

  it("after setActive, subsequent call() routes through the NEW endpoint", async () => {
    const { captureRef } = await mount();
    await act(async () => { await captureRef.current.setActive("beta"); });
    callSpy.mockClear();
    await act(async () => { await captureRef.current.call("host.workgroups.list", {}); });
    expect(callSpy.mock.calls[0][0].id).toBe("beta");
  });
});


describe("EndpointProvider offline auto-reprobe", () => {
  it("re-probes the active endpoint while offline and recovers when it returns", async () => {
    const { captureRef } = await mount();
    vi.useFakeTimers();
    try {
      probeResults.set("alpha", { status: "offline", version: null });
      await act(async () => { await captureRef.current.probeOne("alpha"); });
      expect(captureRef.current.probeState.get("alpha")).toBe("offline");

      probeResults.set("alpha", { status: "online", version: "0.9.7" });
      await act(async () => {
        vi.advanceTimersByTime(4000);
        await Promise.resolve();
        await Promise.resolve();
      });
      expect(captureRef.current.probeState.get("alpha")).toBe("online");

      probeResults.set("alpha", { status: "offline", version: null });
      await act(async () => {
        vi.advanceTimersByTime(4000 * 2);
        await Promise.resolve();
        await Promise.resolve();
      });
      expect(captureRef.current.probeState.get("alpha")).toBe("online");
    } finally {
      vi.useRealTimers();
    }
  });
});
