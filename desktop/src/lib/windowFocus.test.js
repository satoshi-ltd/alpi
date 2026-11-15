import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, renderHook } from "@testing-library/react";
import { _resetWindowFocus, useWindowFocus } from "./windowFocus.js";

let visibility;
let hasFocus;

beforeEach(() => {
  _resetWindowFocus();
  visibility = "visible";
  hasFocus = false;
  vi.spyOn(document, "visibilityState", "get").mockImplementation(() => visibility);
  vi.spyOn(document, "hasFocus").mockImplementation(() => hasFocus);
});

afterEach(() => vi.restoreAllMocks());

describe("useWindowFocus", () => {
  it("reads a visible window as focused at startup even when hasFocus() says no until a refocus", () => {
    const { result } = renderHook(() => useWindowFocus());
    expect(result.current).toBe(true);
  });

  it("trusts hasFocus() once a blur has been seen", () => {
    const { result } = renderHook(() => useWindowFocus());
    act(() => window.dispatchEvent(new Event("blur")));
    expect(result.current).toBe(false);
    act(() => document.dispatchEvent(new Event("visibilitychange")));
    expect(result.current).toBe(false);
    hasFocus = true;
    act(() => window.dispatchEvent(new Event("focus")));
    expect(result.current).toBe(true);
  });

  it("is never focused while hidden", () => {
    visibility = "hidden";
    const { result } = renderHook(() => useWindowFocus());
    expect(result.current).toBe(false);
  });
});
