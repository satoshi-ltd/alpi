import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { usePinned } from "./usePinned.js";

beforeEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

describe("usePinned", () => {
  it("persists pins within their connection", () => {
    const { result } = renderHook(() => usePinned("local"));

    act(() => result.current.onTogglePin("workgroups", "mira/wg-1"));

    expect(result.current.pinned.workgroups).toEqual(["mira/wg-1"]);
    expect(JSON.parse(localStorage.getItem("alf:pinned:v2:local"))).toEqual({
      profiles: [],
      workgroups: ["mira/wg-1"],
    });
  });

  it("evicts only regenerated caches and retries when storage is full", () => {
    localStorage.setItem("alpi.workgroup.cache.local.mira.wg-1", "cached posts");
    localStorage.setItem("alpi.session.cache.v1.local.mira.s-1", "cached session");
    localStorage.setItem("alpi.drafts.v1", "important draft");
    const nativeSetItem = Storage.prototype.setItem;
    let pinWrites = 0;
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(function setItem(key, value) {
      if (key === "alf:pinned:v2:local" && pinWrites++ === 0) {
        throw new DOMException("The quota has been exceeded.", "QuotaExceededError");
      }
      return nativeSetItem.call(this, key, value);
    });
    const { result } = renderHook(() => usePinned("local"));

    act(() => result.current.onTogglePin("workgroups", "mira/wg-1"));

    expect(result.current.pinned.workgroups).toEqual(["mira/wg-1"]);
    expect(localStorage.getItem("alpi.workgroup.cache.local.mira.wg-1")).toBeNull();
    expect(localStorage.getItem("alpi.session.cache.v1.local.mira.s-1")).toBeNull();
    expect(localStorage.getItem("alpi.drafts.v1")).toBe("important draft");
    expect(JSON.parse(localStorage.getItem("alf:pinned:v2:local")).workgroups).toEqual([
      "mira/wg-1",
    ]);
  });

  it("keeps the interface state when storage remains unavailable", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation((key) => {
      if (key === "alf:pinned:v2:local") {
        throw new DOMException("The quota has been exceeded.", "QuotaExceededError");
      }
    });
    const { result } = renderHook(() => usePinned("local"));

    act(() => result.current.onTogglePin("profiles", "muse"));

    expect(result.current.pinned.profiles).toEqual(["muse"]);
  });
});
