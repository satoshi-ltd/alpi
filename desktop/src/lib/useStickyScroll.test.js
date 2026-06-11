import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, act } from "@testing-library/react";
import { useStickyScroll } from "./useStickyScroll.js";

function setup({ stickKey } = {}) {
  let scrollEl = null;
  let setProps;
  function Harness() {
    const [props, _set] = require("react").useState({ d: [0], k: stickKey });
    setProps = _set;
    const ref = useStickyScroll(props.d, props.k);
    return require("react").createElement("div", {
      ref: (node) => {
        if (node) scrollEl = node;
        ref.current = node;
      },
      "data-testid": "scroll",
    });
  }
  render(require("react").createElement(Harness));
  Object.defineProperty(scrollEl, "scrollHeight", { value: 1000, configurable: true });
  Object.defineProperty(scrollEl, "clientHeight", { value: 300, configurable: true });
  return {
    el: scrollEl,
    bump: (extra = {}) => act(() => setProps((p) => ({ d: [p.d[0] + 1], k: p.k, ...extra }))),
    scrollTo: (top) => act(() => { scrollEl.scrollTop = top; scrollEl.dispatchEvent(new Event("scroll")); }),
  };
}

describe("useStickyScroll", () => {
  beforeEach(() => vi.stubGlobal("requestAnimationFrame", (cb) => cb()));
  afterEach(() => vi.unstubAllGlobals());

  it("follows new content while stuck to the bottom", () => {
    const { el, bump } = setup();
    bump();
    expect(el.scrollTop).toBe(el.scrollHeight);
  });

  it("stops following once the user scrolls up", () => {
    const { el, bump, scrollTo } = setup();
    scrollTo(100);
    bump();
    expect(el.scrollTop).toBe(100);
  });

  it("re-engages follow when stickKey changes even after scrolling up", () => {
    const { el, bump, scrollTo } = setup({ stickKey: "r1" });
    scrollTo(100);
    bump({ k: "r2" });
    expect(el.scrollTop).toBe(el.scrollHeight);
  });
});
