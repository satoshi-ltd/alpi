import { describe, expect, it } from "vitest";
import { act, render } from "@testing-library/react";
import { useRef, useState } from "react";
import { useScrollAnchor } from "./useScrollAnchor.js";

function setup() {
  let scrollEl = null;
  let setState;
  function Harness() {
    const [{ firstIndex, resetKey }, _set] = useState({ firstIndex: 100, resetKey: "a:s1" });
    setState = _set;
    const ref = useRef(null);
    useScrollAnchor(ref, firstIndex, resetKey);
    return (
      <div
        ref={(node) => {
          if (node) scrollEl = node;
          ref.current = node;
        }}
      />
    );
  }
  render(<Harness />);
  const geometry = { scrollHeight: 1000, clientHeight: 300 };
  Object.defineProperty(scrollEl, "scrollHeight", {
    get: () => geometry.scrollHeight,
    configurable: true,
  });
  Object.defineProperty(scrollEl, "clientHeight", {
    get: () => geometry.clientHeight,
    configurable: true,
  });
  return {
    el: scrollEl,
    geometry,
    scrollTo: (top) =>
      act(() => {
        scrollEl.scrollTop = top;
        scrollEl.dispatchEvent(new Event("scroll"));
      }),
    prepend: (newFirstIndex, addedHeight, resetKey) =>
      act(() => {
        geometry.scrollHeight += addedHeight;
        setState((p) => ({ firstIndex: newFirstIndex, resetKey: resetKey ?? p.resetKey }));
      }),
    rerender: (firstIndex) => act(() => setState((p) => ({ ...p, firstIndex }))),
  };
}

describe("useScrollAnchor", () => {
  it("compensates scrollTop when older turns are prepended above a scrolled-up viewport", () => {
    const { el, scrollTo, prepend } = setup();
    scrollTo(100);
    prepend(50, 400);
    expect(el.scrollTop).toBe(500);
  });

  it("leaves bottom-stuck viewports alone (sticky scroll owns them)", () => {
    const { el, scrollTo, prepend } = setup();
    scrollTo(700);
    prepend(50, 400);
    expect(el.scrollTop).toBe(700);
  });

  it("does nothing when firstIndex does not decrease", () => {
    const { el, scrollTo, rerender, geometry } = setup();
    scrollTo(100);
    act(() => {
      geometry.scrollHeight += 200;
    });
    rerender(100);
    expect(el.scrollTop).toBe(100);
  });

  it("treats a session switch as a reset, not a prepend", () => {
    const { el, scrollTo, prepend } = setup();
    scrollTo(100);
    prepend(0, 400, "a:s2");
    expect(el.scrollTop).toBe(100);
  });
});
