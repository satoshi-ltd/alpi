import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { BUSY_DELAY_MS, BUSY_MIN_MARK_PX, BUSY_MIN_MS } from "../../../common/busy.mjs";
import { TWIN } from "../lib/brandMark.js";
import Busy from "./Busy.jsx";

const mark = () => screen.queryByRole("status");

function mockReducedMotion(matches) {
  window.matchMedia = vi.fn((query) => ({
    matches: matches && query === "(prefers-reduced-motion: reduce)",
    media: query,
    addEventListener: () => {},
    removeEventListener: () => {},
  }));
}

beforeEach(() => {
  vi.useFakeTimers();
  delete window.matchMedia;
});

afterEach(() => {
  vi.useRealTimers();
  delete window.matchMedia;
});

describe("Busy", () => {
  it("stays hidden for the delay so a fast wait never flashes", () => {
    const { rerender } = render(<Busy />);
    act(() => vi.advanceTimersByTime(BUSY_DELAY_MS - 1));
    expect(mark()).toBeNull();
    rerender(<Busy active={false} />);
    act(() => vi.advanceTimersByTime(BUSY_DELAY_MS + BUSY_MIN_MS));
    expect(mark()).toBeNull();
  });

  it("appears after the delay and, once shown, stays the minimum time", () => {
    const { rerender } = render(<Busy />);
    act(() => vi.advanceTimersByTime(BUSY_DELAY_MS));
    expect(mark()).not.toBeNull();
    act(() => vi.advanceTimersByTime(50));
    rerender(<Busy active={false} />);
    expect(mark()).not.toBeNull();
    act(() => vi.advanceTimersByTime(BUSY_MIN_MS - 51));
    expect(mark()).not.toBeNull();
    act(() => vi.advanceTimersByTime(1));
    expect(mark()).toBeNull();
  });

  it("is labelled Loading by default and by its words when it shows them", () => {
    const { unmount } = render(<Busy />);
    act(() => vi.advanceTimersByTime(BUSY_DELAY_MS));
    expect(screen.getByRole("status", { name: "Loading" }).textContent).toBe("");
    unmount();
    render(<Busy label="Reaching the daemon" />);
    act(() => vi.advanceTimersByTime(BUSY_DELAY_MS));
    expect(screen.getByRole("status", { name: "Reaching the daemon" })).toHaveTextContent("Reaching the daemon");
  });

  it("draws Twin busy in the brand ink, its eyes morphing", () => {
    render(<Busy size={40} />);
    act(() => vi.advanceTimersByTime(BUSY_DELAY_MS));
    const slot = mark().querySelector("[data-shape]");
    expect(slot.dataset.shape).toBe(TWIN);
    expect(slot.dataset.mark).toBe("alpi-twin");
    expect(slot.dataset.state).toBe("busy");
    expect(slot.querySelector("path[data-body]").getAttribute("fill")).toBe("var(--accent)");
    expect(slot.querySelectorAll("path[data-eye] animate")).toHaveLength(2);
    expect(slot.querySelector("polygon")).toBeNull();
  });

  it("is never painted in a profile colour", () => {
    render(<Busy label="Fetching" color="#ff3366" accent="#ff3366" style={{ "--c": "#ff3366" }} />);
    act(() => vi.advanceTimersByTime(BUSY_DELAY_MS));
    const html = mark().outerHTML;
    expect(html).not.toContain("#ff3366");
    expect(html).not.toMatch(/--c:|var\(--c\b/);
  });

  it("stands still under reduced motion and keeps its words", () => {
    mockReducedMotion(true);
    render(<Busy label="Reaching the daemon" size={40} />);
    act(() => vi.advanceTimersByTime(BUSY_DELAY_MS));
    const status = screen.getByRole("status", { name: "Reaching the daemon" });
    expect(status).toHaveTextContent("Reaching the daemon");
    expect(status.querySelector("animate")).toBeNull();
    expect(status.querySelector("[class*='am-'], [class*='vt-']")).toBeNull();
  });

  it("never draws the mark below its minimum size", () => {
    render(<Busy size={10} />);
    act(() => vi.advanceTimersByTime(BUSY_DELAY_MS));
    expect(mark().querySelector("[data-shape]").style.width).toBe(`${BUSY_MIN_MARK_PX}px`);
  });

  it("leaves all motion to the mark, with no keyframes of its own", () => {
    const css = readFileSync(join(import.meta.dirname, "Busy.module.css"), "utf8");
    expect(css).not.toMatch(/@keyframes|animation/);
    expect(css).not.toMatch(/#[0-9a-f]{3,6}\b/i);
  });
});

describe("every mounted wait goes through the timing hook", () => {
  const walk = (dir, out = []) => {
    for (const name of readdirSync(dir)) {
      const p = join(dir, name);
      if (statSync(p).isDirectory()) walk(p, out);
      else if (/\.jsx?$/.test(name) && !/\.test\./.test(name)) out.push(p);
    }
    return out;
  };

  it("a Busy always says when it is active, and a bare BusyMark lives beside useBusyVisible", () => {
    const offenders = [];
    for (const path of walk(join(import.meta.dirname, ".."))) {
      const source = readFileSync(path, "utf8");
      const rel = relative(join(import.meta.dirname, ".."), path);
      for (const m of source.matchAll(/<Busy\b[^>]*>/g)) if (!/\bactive=/.test(m[0])) offenders.push(`${rel}: ${m[0]}`);
      if (/<BusyMark\b/.test(source) && !rel.endsWith("Busy.jsx") && !/useBusyVisible\(/.test(source)) offenders.push(`${rel}: BusyMark without useBusyVisible`);
    }
    expect(offenders).toEqual([]);
  });
});
