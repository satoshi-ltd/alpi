import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { readSidebarPref, useSidebarPref } from "./sidebar.js";

beforeEach(() => {
  localStorage.clear();
});

describe("sidebar preference", () => {
  it("starts open and remembers a hide across launches", () => {
    expect(readSidebarPref()).toBe(true);
    const { result } = renderHook(() => useSidebarPref());
    expect(result.current.open).toBe(true);
    act(() => result.current.toggle());
    expect(result.current.open).toBe(false);
    expect(localStorage.getItem("alpi.sidebarOpen")).toBe("0");
    expect(readSidebarPref()).toBe(false);
    act(() => result.current.toggle());
    expect(localStorage.getItem("alpi.sidebarOpen")).toBe("1");
  });
});
