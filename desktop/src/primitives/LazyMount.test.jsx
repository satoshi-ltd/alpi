import React from "react";
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup, act } from "@testing-library/react";

import LazyMount from "./LazyMount.jsx";

afterEach(() => {
  cleanup();
  delete global.IntersectionObserver;
});

describe("LazyMount", () => {
  it("renders children immediately when IntersectionObserver is unavailable (jsdom/tests)", () => {
    render(<LazyMount><span>heavy</span></LazyMount>);
    expect(screen.getByText("heavy")).toBeTruthy();
  });

  it("defers children until the block intersects, then mounts once", () => {
    let observerCb = null;
    const disconnect = vi.fn();
    global.IntersectionObserver = class {
      constructor(cb) { observerCb = cb; }
      observe() {}
      disconnect() { disconnect(); }
    };
    render(<LazyMount placeholder={<i>hold</i>}><span>heavy</span></LazyMount>);
    expect(screen.queryByText("heavy")).toBeNull();
    expect(screen.getByText("hold")).toBeTruthy();
    act(() => observerCb([{ isIntersecting: true }]));
    expect(screen.getByText("heavy")).toBeTruthy();
    expect(disconnect).toHaveBeenCalled();
  });
});
