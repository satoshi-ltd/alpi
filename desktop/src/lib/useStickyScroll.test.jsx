import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, act } from "@testing-library/react";
import { useStickyScroll } from "./useStickyScroll.js";

let rafQueue = [];
const flushRaf = () => {
  const q = rafQueue;
  rafQueue = [];
  q.forEach((cb) => cb && cb());
};

beforeEach(() => {
  rafQueue = [];
  vi.stubGlobal("requestAnimationFrame", (cb) => rafQueue.push(cb));
  vi.stubGlobal("cancelAnimationFrame", (id) => { rafQueue[id - 1] = null; });
});
afterEach(() => vi.unstubAllGlobals());

function makeScrollable(node, { scrollHeight, clientHeight }) {
  let top = 0;
  Object.defineProperty(node, "scrollHeight", { configurable: true, get: () => scrollHeight });
  Object.defineProperty(node, "clientHeight", { configurable: true, get: () => clientHeight });
  Object.defineProperty(node, "scrollTop", {
    configurable: true,
    get: () => top,
    set: (v) => { top = v; },
  });
}

function Harness({ tick, stickKey, nodeRef }) {
  const ref = useStickyScroll([tick], stickKey);
  return (
    <div
      ref={(n) => {
        ref.current = n;
        if (n) nodeRef.current = n;
      }}
    />
  );
}

function setup({ stickKey = "k" } = {}) {
  const nodeRef = { current: null };
  const { rerender } = render(<Harness tick={0} stickKey={stickKey} nodeRef={nodeRef} />);
  const node = nodeRef.current;
  makeScrollable(node, { scrollHeight: 1000, clientHeight: 500 });
  node.scrollTop = 500;
  return { node, nodeRef, rerender };
}

const scrollUp = (node, top, scrollHeight) => {
  if (scrollHeight != null) {
    Object.defineProperty(node, "scrollHeight", { configurable: true, get: () => scrollHeight });
  }
  node.scrollTop = top;
  act(() => { node.dispatchEvent(new Event("scroll")); });
};

describe("useStickyScroll", () => {
  it("follows new content while pinned to the bottom", () => {
    const { node, nodeRef, rerender } = setup();
    Object.defineProperty(node, "scrollHeight", { configurable: true, get: () => 1200 });
    act(() => rerender(<Harness tick={1} stickKey="k" nodeRef={nodeRef} />));
    act(() => flushRaf());
    expect(node.scrollTop).toBe(1200);
  });

  it("does NOT yank back to bottom when the user scrolls up between schedule and paint", () => {
    const { node, nodeRef, rerender } = setup();
    act(() => rerender(<Harness tick={1} stickKey="k" nodeRef={nodeRef} />));
    scrollUp(node, 100, 1200);
    act(() => flushRaf());
    expect(node.scrollTop).toBe(100);
  });

  it("stays put on further output once the user has scrolled up", () => {
    const { node, nodeRef, rerender } = setup();
    scrollUp(node, 100, 1200);
    act(() => rerender(<Harness tick={1} stickKey="k" nodeRef={nodeRef} />));
    act(() => flushRaf());
    expect(node.scrollTop).toBe(100);
  });

  it("re-engages following when the stick key changes (new message sent)", () => {
    const { node, nodeRef, rerender } = setup();
    scrollUp(node, 100, 1200);
    act(() => rerender(<Harness tick={1} stickKey="k2" nodeRef={nodeRef} />));
    act(() => flushRaf());
    expect(node.scrollTop).toBe(1200);
  });
});
