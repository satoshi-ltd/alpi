import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ALPACA_FOLD, BRAND_INK, foldFacets } from "../../../common/folds.mjs";
import { BUSY_DELAY_MS, BUSY_DIM, BUSY_MIN_MARK_PX, BUSY_MIN_MS, BUSY_WAVE_S, busyFacetDelays } from "../../../common/busy.mjs";
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

  it("draws the alpaca in the brand ink, each facet dimming in turn over one loop", () => {
    render(<Busy />);
    act(() => vi.advanceTimersByTime(BUSY_DELAY_MS));
    const slot = mark().querySelector("[data-fold]");
    expect(slot.dataset.fold).toBe(ALPACA_FOLD);
    expect(slot.style.getPropertyValue("--alp-l")).toBe(BRAND_INK.light);
    expect(slot.style.getPropertyValue("--alp-d")).toBe(BRAND_INK.dark);
    expect(slot.style.getPropertyValue("--busy-dim")).toBe(String(BUSY_DIM));
    const polygons = [...slot.querySelectorAll("polygon")];
    expect(polygons).toHaveLength(foldFacets(ALPACA_FOLD).length);
    const delays = busyFacetDelays(polygons.length);
    polygons.forEach((p, i) => {
      expect(p.getAttribute("fill")).toBe("var(--alp)");
      expect(p.getAttribute("class")).toMatch(/facet/);
      expect(p.style.animationDuration).toBe(`${BUSY_WAVE_S}s`);
      expect(p.style.animationDelay).toBe(`${delays[i]}s`);
    });
  });

  it("is never painted in a profile colour", () => {
    render(<Busy label="Fetching" color="#ff3366" accent="#ff3366" style={{ "--c": "#ff3366" }} />);
    act(() => vi.advanceTimersByTime(BUSY_DELAY_MS));
    const html = mark().outerHTML;
    expect(html).not.toContain("#ff3366");
    expect(html).not.toMatch(/--c:|var\(--accent\)|var\(--c\b/);
    expect([...html.matchAll(/#[0-9a-f]{6}/gi)].map((m) => m[0].toLowerCase()).sort()).toEqual([BRAND_INK.dark, BRAND_INK.light].sort());
  });

  it("stands still under reduced motion and keeps its words", () => {
    mockReducedMotion(true);
    render(<Busy label="Reaching the daemon" />);
    act(() => vi.advanceTimersByTime(BUSY_DELAY_MS));
    const status = screen.getByRole("status", { name: "Reaching the daemon" });
    expect(status.hasAttribute("data-still")).toBe(true);
    expect(status).toHaveTextContent("Reaching the daemon");
    for (const p of status.querySelectorAll("polygon")) {
      expect(p.getAttribute("class")).toBeNull();
      expect(p.style.animationDelay).toBe("");
    }
  });

  it("never draws the mark below its minimum size", () => {
    render(<Busy size={10} />);
    act(() => vi.advanceTimersByTime(BUSY_DELAY_MS));
    expect(mark().querySelector("[data-fold]").style.width).toBe(`${BUSY_MIN_MARK_PX}px`);
  });

  it("animates opacity only, from its own dim token, and stops under reduced motion in CSS too", () => {
    const css = readFileSync(join(import.meta.dirname, "Busy.module.css"), "utf8");
    const keyframes = css.match(/@keyframes busyWave\s*\{([\s\S]*?)\n\}/)[1];
    expect(keyframes).not.toMatch(/transform|fill|color|background/);
    expect(keyframes).toMatch(/opacity:\s*var\(--busy-dim\)/);
    expect(css).toMatch(/\.facet\s*\{\s*animation: busyWave var\(--dur-loop\) linear infinite;\s*\}/);
    expect(keyframes).not.toMatch(/timing-function|ease/);
    expect(css).toMatch(/@media \(prefers-reduced-motion: reduce\)\s*\{\s*\.facet\s*\{\s*animation:\s*none;/);
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
