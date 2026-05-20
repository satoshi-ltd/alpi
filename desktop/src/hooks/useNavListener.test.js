import { describe, it, expect, beforeEach, vi } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { listen } from "@tauri-apps/api/event";
import { useNavListener } from "./useNavListener.js";

let registered;
let unlisten;

beforeEach(() => {
  registered = null;
  unlisten = vi.fn();
  listen.mockImplementation(async (eventName, cb) => {
    if (eventName === "nav") registered = cb;
    return unlisten;
  });
});

describe("useNavListener", () => {
  it("registers a listener for the `nav` event on mount", async () => {
    const setView = vi.fn();
    renderHook(() => useNavListener(setView));
    await Promise.resolve();
    expect(listen).toHaveBeenCalledWith("nav", expect.any(Function));
  });

  it('payload "settings" sets view to settings', async () => {
    const setView = vi.fn();
    renderHook(() => useNavListener(setView));
    await Promise.resolve();
    act(() => registered({ payload: "settings" }));
    expect(setView).toHaveBeenCalledWith({ kind: "settings" });
  });

  it('payload "home" leaves view alone when not in settings', async () => {
    const setView = vi.fn();
    renderHook(() => useNavListener(setView));
    await Promise.resolve();
    act(() => registered({ payload: "home" }));
    expect(setView).toHaveBeenCalledTimes(1);
    const updater = setView.mock.calls[0][0];
    expect(updater({ kind: "chat" })).toEqual({ kind: "chat" });
    expect(updater({ kind: "settings" })).toEqual({ kind: "empty" });
  });

  it("ignores unknown payloads (forward-compat)", async () => {
    const setView = vi.fn();
    renderHook(() => useNavListener(setView));
    await Promise.resolve();
    act(() => registered({ payload: "unknown" }));
    expect(setView).not.toHaveBeenCalled();
  });

  it("unsubscribes on unmount", async () => {
    const setView = vi.fn();
    const { unmount } = renderHook(() => useNavListener(setView));
    await Promise.resolve();  // listen() resolves
    unmount();
    await Promise.resolve();  // the unlisten chain awaits
    expect(unlisten).toHaveBeenCalled();
  });
});
