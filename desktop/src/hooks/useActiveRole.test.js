import { describe, it, expect, beforeEach, vi } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";

import { useActiveRole } from "./useActiveRole.js";
import { useHostConnections } from "./useHostConnections.js";
import { _resetDaemonBus } from "../lib/daemon-bus.js";

vi.mock("../lib/workgroup-cache.js", () => ({ pruneCachedMessages: vi.fn() }));

let statusListener;
let rustActive;
let setActive;
let rustSilent;

function connections(active) {
  return {
    active_id: active,
    connections: [
      { id: "local", kind: "local", status: "online", error: null, role: "admin" },
      { id: "remote", kind: "remote", status: "online", error: null, role: "member" },
    ],
  };
}

function mount() {
  const props = {
    setSessionData: vi.fn(),
    clearTurnsForConnection: vi.fn(),
    setRewriteDraft: vi.fn(),
    setActiveTask: vi.fn(),
    setView: vi.fn(),
    notify: vi.fn(),
  };
  return renderHook(() => ({ role: useActiveRole(), host: useHostConnections(props) }));
}

beforeEach(() => {
  vi.resetAllMocks();
  _resetDaemonBus();
  localStorage.clear();
  statusListener = null;
  rustActive = "local";
  setActive = null;
  rustSilent = false;
  listen.mockImplementation(async (name, cb) => {
    if (name === "connection-status") statusListener = cb;
    return () => {};
  });
  invoke.mockImplementation(async (cmd, args) => {
    if (cmd === "host_connections") return rustSilent ? new Promise(() => {}) : connections(rustActive);
    if (cmd === "host_connection_set_active") {
      return new Promise((resolve, reject) => {
        setActive = {
          ok: () => { rustActive = args.id; resolve(null); },
          fail: () => reject(new Error("refused")),
        };
      });
    }
    if (cmd === "host_connection_probe") return "online";
    return [];
  });
});

async function ready(result) {
  await waitFor(() => expect(result.current.role).toBe("admin"));
  await waitFor(() => expect(result.current.host.hostConnections.connections).toHaveLength(2));
}

describe("active role across a connection switch", () => {
  it("is the new connection's role in the same render as the switch", async () => {
    const { result } = mount();
    await ready(result);

    act(() => { result.current.host.onSetHostConnection("remote"); });

    expect(result.current.host.hostConnections.active_id).toBe("remote");
    expect(result.current.role).toBe("member");
  });

  it("ignores an answer that still describes the connection it left", async () => {
    const { result } = mount();
    await ready(result);
    act(() => { result.current.host.onSetHostConnection("remote"); });

    expect(statusListener).toBeTypeOf("function");
    await act(async () => { statusListener({ payload: { id: "local", status: "online" } }); });

    expect(result.current.role).toBe("member");
  });

  it("returns to the previous role when the switch is refused", async () => {
    const { result } = mount();
    await ready(result);
    act(() => { result.current.host.onSetHostConnection("remote"); });
    await waitFor(() => expect(setActive).not.toBeNull());

    rustSilent = true;
    await act(async () => { setActive.fail(); });

    await waitFor(() => expect(result.current.host.hostConnections.active_id).toBe("local"));
    expect(result.current.role).toBe("admin");
  });

  it("follows a role change on the active connection", async () => {
    const { result } = mount();
    await ready(result);
    act(() => { result.current.host.onSetHostConnection("remote"); });
    await waitFor(() => expect(setActive).not.toBeNull());
    await act(async () => { setActive.ok(); });

    invoke.mockImplementation(async (cmd) => {
      if (cmd === "host_connections") {
        const state = connections("remote");
        state.connections[1].role = "admin";
        return state;
      }
      return [];
    });
    await act(async () => { statusListener({ payload: { id: "remote", status: "online", role: "admin" } }); });

    await waitFor(() => expect(result.current.role).toBe("admin"));
  });
});
