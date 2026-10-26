import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

let resolveCopy;
vi.mock("../lib/clipboard.js", () => ({
  copyText: () => new Promise((resolve) => { resolveCopy = resolve; }),
}));

import { COPIED_MS, useCopyFeedback } from "./useCopyFeedback.js";

describe("useCopyFeedback", () => {
  it("marks the key copied, then clears it", async () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => useCopyFeedback());
    let pending;
    act(() => { pending = result.current[1]("k", "t"); });
    await act(async () => { resolveCopy(true); await pending; });
    expect(result.current[0]).toBe("k");
    act(() => { vi.advanceTimersByTime(COPIED_MS + 10); });
    expect(result.current[0]).toBeNull();
    vi.useRealTimers();
  });

  it("starts no timer and reports no failure when unmounted before the copy settles", async () => {
    vi.useFakeTimers();
    const onFail = vi.fn();
    const { result, unmount } = renderHook(() => useCopyFeedback(onFail));
    let pending;
    act(() => { pending = result.current[1]("k", "t"); });
    unmount();
    await act(async () => { resolveCopy(true); await pending; });
    expect(vi.getTimerCount()).toBe(0);
    vi.useRealTimers();
    const second = renderHook(() => useCopyFeedback(onFail));
    let p2;
    act(() => { p2 = second.result.current[1]("k", "t"); });
    second.unmount();
    await act(async () => { resolveCopy(false); await p2; });
    expect(onFail).not.toHaveBeenCalled();
  });
});
