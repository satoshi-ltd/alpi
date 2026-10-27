import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, renderHook } from "@testing-library/react";
import { invoke } from "@tauri-apps/api/core";

const h = vi.hoisted(() => ({ updater: null }));
vi.mock("../lib/updater.js", () => ({
  subscribeUpdater: (fn) => {
    h.updater = fn;
    fn({ available: false, version: null, installing: false });
    return () => { h.updater = null; };
  },
}));

import { TRAY_ANNOUNCE_DEBOUNCE_MS, reducedSnapshot, useTrayAnnouncer } from "./useTrayAnnouncer.js";

const online = { id: "local", kind: "local", status: "online" };
const EMPTY = { needs_you: [], running: [], scheduled: [] };
const props = (over = {}) => ({ connection: online, daemon: null, activity: EMPTY, activitySupported: true, member: false, unread: 0, foldByProfile: {}, accentByProfile: {}, ...over });
const sent = () => invoke.mock.calls.filter(([name]) => name === "tray_announce_state");
const flush = () => act(async () => { await vi.advanceTimersByTimeAsync(TRAY_ANNOUNCE_DEBOUNCE_MS + 10); });

beforeEach(() => {
  vi.useFakeTimers();
  invoke.mockClear();
  invoke.mockImplementation(async () => null);
});
afterEach(() => vi.useRealTimers());

describe("useTrayAnnouncer", () => {
  it("pushes one snapshot after the debounce", async () => {
    renderHook(() => useTrayAnnouncer(props()));
    expect(sent()).toHaveLength(0);
    await flush();
    expect(sent()).toHaveLength(1);
    expect(sent()[0][1].snapshot).toMatchObject({ v: 1, state: "quiet", unread: 0 });
  });

  it("coalesces a burst of changes into the last snapshot", async () => {
    const { rerender } = renderHook((p) => useTrayAnnouncer(p), { initialProps: props() });
    for (const unread of [1, 2, 3]) {
      rerender(props({ unread }));
      await act(async () => { await vi.advanceTimersByTimeAsync(50); });
    }
    await flush();
    expect(sent()).toHaveLength(1);
    expect(sent()[0][1].snapshot.unread).toBe(3);
  });

  it("sends nothing for a rerender that changes no fact", async () => {
    const { rerender } = renderHook((p) => useTrayAnnouncer(p), { initialProps: props() });
    await flush();
    rerender(props());
    rerender(props({ activity: { needs_you: [], running: [], scheduled: [] } }));
    await flush();
    expect(sent()).toHaveLength(1);
  });

  it("sends again when a fact changes", async () => {
    const { rerender } = renderHook((p) => useTrayAnnouncer(p), { initialProps: props() });
    await flush();
    rerender(props({ activity: { needs_you: [{ request_id: "a", kind: "approval", profile: "abby", ts: 1 }], running: [], scheduled: [] } }));
    await flush();
    expect(sent()).toHaveLength(2);
    expect(sent()[1][1].snapshot).toMatchObject({ state: "needs" });
  });

  it("pushes the update the updater finds and the member rule", async () => {
    const { rerender } = renderHook((p) => useTrayAnnouncer(p), { initialProps: props({ unread: 4 }) });
    await flush();
    act(() => h.updater({ available: true, version: "0.9.3", installing: false }));
    await flush();
    expect(sent().at(-1)[1].snapshot.update).toEqual({ version: "0.9.3", busy: false });
    rerender(props({ unread: 4, member: true }));
    await flush();
    expect(sent().at(-1)[1].snapshot).toMatchObject({ member: true, unread: 0 });
  });

  it("does not resend an update state the updater repeats", async () => {
    renderHook(() => useTrayAnnouncer(props()));
    await flush();
    act(() => h.updater({ available: false, version: null, installing: false }));
    await flush();
    expect(sent()).toHaveLength(1);
  });

  it("falls back to a reduced snapshot when the full one is refused, never leaving a stale state", async () => {
    invoke.mockImplementationOnce(async () => { throw new Error("Tray snapshot too large"); });
    renderHook(() => useTrayAnnouncer(props({ activity: { needs_you: [{ request_id: "a", kind: "approval", profile: "abby", title: "x".repeat(100000), ts: 1 }], running: [], scheduled: [] } })));
    await flush();
    expect(sent()).toHaveLength(2);
    const reduced = sent()[1][1].snapshot;
    expect(Object.keys(reduced).sort()).toEqual(["counts", "state", "v"]);
    expect(reduced).toMatchObject({ state: "needs", counts: { needs: 1 } });
  });

  it("builds the reduced snapshot from state and counts only", () => {
    expect(reducedSnapshot({ v: 1, state: "failing", counts: { failing: 2 }, needs: { rows: [1] }, unread: 4 })).toEqual({ v: 1, state: "failing", counts: { failing: 2 } });
  });

  it("retries on the next change when even the reduced snapshot fails", async () => {
    invoke.mockImplementationOnce(async () => { throw new Error("not ready"); });
    invoke.mockImplementationOnce(async () => { throw new Error("not ready"); });
    const { rerender } = renderHook((p) => useTrayAnnouncer(p), { initialProps: props() });
    await flush();
    rerender(props({ unread: 1 }));
    await flush();
    expect(sent()).toHaveLength(3);
  });

  it("drops a pending push when it unmounts", async () => {
    const { unmount } = renderHook(() => useTrayAnnouncer(props()));
    unmount();
    await flush();
    expect(sent()).toHaveLength(0);
  });
});
