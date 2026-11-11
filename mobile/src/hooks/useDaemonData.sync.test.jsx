import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";

const h = vi.hoisted(() => ({ appListeners: new Set(), state: "active" }));

vi.mock("react-native", () => ({
  AppState: {
    get currentState() { return h.state; },
    addEventListener: (_name, fn) => {
      h.appListeners.add(fn);
      return { remove: () => h.appListeners.delete(fn) };
    },
  },
}));
vi.mock("../theme/ThemeContext", () => ({ useTheme: () => ({ colors: { accent: "#14110c" } }) }));

import { EndpointContext } from "../lib/EndpointContext";
import {
  _resetDaemonDataCache, RECONCILE_MS, RETRY_BASE_MS, useWorkgroupTasks,
} from "./useDaemonData";

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((res, rej) => { resolve = res; reject = rej; });
  return { promise, resolve, reject };
}

function mount(call) {
  const wrapper = ({ children }) => (
    <EndpointContext.Provider value={{ endpoint: { id: "ep", name: "ep" }, call }}>{children}</EndpointContext.Provider>
  );
  return renderHook(() => useWorkgroupTasks("doc", "wg1"), { wrapper });
}

async function flush() {
  for (let i = 0; i < 5; i++) await act(async () => { await Promise.resolve(); });
}

function setAppState(state) {
  h.state = state;
  for (const fn of [...h.appListeners]) act(() => fn(state));
}

beforeEach(() => {
  _resetDaemonDataCache();
  h.appListeners.clear();
  h.state = "active";
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

const timeout = () => Object.assign(new Error("request timed out"), { code: -32000, transport: true });

describe("workgroup state stays current", () => {
  it("joins the read in flight on a plain refresh, so a mount plus a focus refresh is one call", async () => {
    const first = deferred();
    const call = vi.fn(() => first.promise);
    const { result } = mount(call);
    act(() => { result.current.refresh(); });
    first.resolve({ tasks: [] });
    await flush();
    expect(call).toHaveBeenCalledTimes(1);
  });

  it("stops retrying and reconciling after an answer the daemon will keep giving", async () => {
    const call = vi.fn()
      .mockImplementationOnce(async () => ({ tasks: [1] }))
      .mockImplementation(async () => { throw Object.assign(new Error("unknown workgroup"), { code: -32602 }); });
    const { result } = mount(call);
    await flush();
    act(() => { result.current.refresh(); });
    await flush();
    await act(async () => { vi.advanceTimersByTime(RECONCILE_MS * 4); });
    await flush();
    expect(call).toHaveBeenCalledTimes(2);
    expect(result.current.stale).toBe(true);
  });

  it("never shows the loading state for a reconcile nobody asked for", async () => {
    const call = vi.fn(async () => ({ tasks: [] }));
    const { result } = mount(call);
    await flush();
    const seen = [];
    call.mockImplementation(() => { seen.push(result.current.loading); return Promise.resolve({ tasks: [] }); });
    await act(async () => { vi.advanceTimersByTime(RECONCILE_MS); });
    await flush();
    expect(call).toHaveBeenCalledTimes(2);
    expect(result.current.loading).toBe(false);
  });

  it("does not re-read on an inactive blip, only on a return from the background", async () => {
    const call = vi.fn(async () => ({ tasks: [] }));
    mount(call);
    await flush();
    setAppState("inactive");
    setAppState("active");
    await flush();
    expect(call).toHaveBeenCalledTimes(1);
    setAppState("background");
    setAppState("active");
    await flush();
    expect(call).toHaveBeenCalledTimes(2);
  });

  it("reads again after an invalidation that arrived while a read was in flight", async () => {
    const first = deferred();
    const call = vi.fn()
      .mockImplementationOnce(() => first.promise)
      .mockImplementationOnce(async () => ({ pipeline_run: { current_phase: "qa" } }));
    const { result } = mount(call);
    await flush();
    let refreshed;
    act(() => { refreshed = result.current.invalidate(); });
    act(() => { result.current.invalidate(); });
    first.resolve({ pipeline_run: { current_phase: "build" } });
    await act(async () => { await refreshed; });
    await flush();
    expect(call).toHaveBeenCalledTimes(2);
    expect(result.current.data.pipeline_run.current_phase).toBe("qa");
  });

  it("recovers after several timeouts with a growing backoff and marks the cached rows stale meanwhile", async () => {
    const call = vi.fn()
      .mockImplementationOnce(async () => ({ tasks: [1] }))
      .mockImplementationOnce(async () => { throw timeout(); })
      .mockImplementationOnce(async () => { throw timeout(); })
      .mockImplementationOnce(async () => ({ tasks: [1, 2] }));
    const { result } = mount(call);
    await flush();
    act(() => { result.current.refresh(); });
    await flush();
    expect(result.current.stale).toBe(true);
    expect(result.current.data.tasks).toEqual([1]);

    await act(async () => { vi.advanceTimersByTime(RETRY_BASE_MS); });
    await flush();
    expect(call).toHaveBeenCalledTimes(3);
    await act(async () => { vi.advanceTimersByTime(RETRY_BASE_MS); });
    await flush();
    expect(call).toHaveBeenCalledTimes(3);
    await act(async () => { vi.advanceTimersByTime(RETRY_BASE_MS); });
    await flush();
    expect(call).toHaveBeenCalledTimes(4);
    expect(result.current.data.tasks).toEqual([1, 2]);
    expect(result.current.stale).toBe(false);
  });

  it("never retries an auth failure and clears what the caller may no longer see", async () => {
    const call = vi.fn()
      .mockImplementationOnce(async () => ({ tasks: [1] }))
      .mockImplementation(async () => { throw Object.assign(new Error("auth-failed"), { code: -32000 }); });
    const { result } = mount(call);
    await flush();
    act(() => { result.current.refresh(); });
    await flush();
    await act(async () => { vi.advanceTimersByTime(RETRY_BASE_MS * 40); });
    await flush();
    expect(call).toHaveBeenCalledTimes(2);
    expect(result.current.data).toBe(null);
  });

  it("reconciles on a timer in the foreground, stops in the background and reads at once on resume", async () => {
    const call = vi.fn(async () => ({ tasks: [] }));
    mount(call);
    await flush();
    expect(call).toHaveBeenCalledTimes(1);

    await act(async () => { vi.advanceTimersByTime(RECONCILE_MS); });
    await flush();
    expect(call).toHaveBeenCalledTimes(2);

    setAppState("background");
    await act(async () => { vi.advanceTimersByTime(RECONCILE_MS * 3); });
    await flush();
    expect(call).toHaveBeenCalledTimes(2);

    setAppState("active");
    await flush();
    expect(call).toHaveBeenCalledTimes(3);
  });

  it("stops every timer when the screen goes away", async () => {
    const call = vi.fn(async () => ({ tasks: [] }));
    const view = mount(call);
    await flush();
    view.unmount();
    await act(async () => { vi.advanceTimersByTime(RECONCILE_MS * 3); });
    expect(call).toHaveBeenCalledTimes(1);
    expect(h.appListeners.size).toBe(0);
  });
});
