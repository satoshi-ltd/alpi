import { readFileSync } from "node:fs";
import { join } from "node:path";
import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { FOLD_IDS, WORKGROUP_FOLD, foldFacets } from "../../../common/folds.mjs";
import Fold from "./Fold.jsx";

afterEach(cleanup);

const draw = (props) => render(<Fold {...props} />).container.firstChild;

describe("Fold", () => {
  it("draws the kite-base origami until a profile names another fold", () => {
    for (const fold of [undefined, null, "", "diamond", "pencil"]) {
      const root = draw({ fold, color: "#3899e2" });
      expect(root.dataset.fold, String(fold)).toBe("diamond");
      expect(root.querySelector(".ds-diamond")).toBeNull();
      expect(root.querySelectorAll("polygon").length).toBeGreaterThan(1);
      cleanup();
    }
  });

  it.each(FOLD_IDS.filter((id) => id !== "diamond"))("draws %s as its own polygons in the profile's colour", (fold) => {
    const root = draw({ fold, color: "#3899e2" });
    const polygons = root.querySelectorAll("polygon");
    expect(polygons).toHaveLength(foldFacets(fold).length);
    expect(root.querySelector(".ds-diamond")).toBeNull();
    expect(new Set([...polygons].map((p) => p.getAttribute("fill"))).has("#3899e2")).toBe(true);
  });

  it("keeps the slot the same size for every glyph, 16 in rows and 20 in headers", () => {
    expect(draw({ fold: "shield", color: "#3899e2" }).style.width).toBe("16px");
    cleanup();
    expect(draw({ fold: "shield", color: "#3899e2", size: "md" }).style.width).toBe("20px");
    cleanup();
    expect(draw({ color: "#3899e2" }).style.width).toBe("16px");
    cleanup();
    expect(draw({ color: "#3899e2", size: "md" }).style.width).toBe("20px");
  });

  it("draws a specimen at the pixel size it is given, the diamond as its kite-base origami", () => {
    const root = draw({ fold: "diamond", color: "#3899e2", size: 28 });
    expect(root.style.width).toBe("28px");
    expect(root.querySelectorAll("polygon").length).toBeGreaterThan(1);
    expect(root.querySelector(".ds-diamond")).toBeNull();
    cleanup();
    expect(draw({ fold: "shield", color: "#3899e2", size: 40 }).style.height).toBe("40px");
  });

  it("ripples facet by facet when working and outlines when paused", () => {
    const pulsing = draw({ fold: "heart", color: "#f36a8a", pulse: true });
    expect(pulsing.querySelector("svg").getAttribute("class")).toBeNull();
    expect([...pulsing.querySelectorAll("polygon")].every((p) => /cell/.test(p.getAttribute("class")))).toBe(true);
    cleanup();
    const outlined = draw({ fold: "heart", color: "#f36a8a", outlined: true });
    expect(outlined.querySelector("polygon").getAttribute("fill-opacity")).toBe("0.22");
    cleanup();
    expect(draw({ color: "#f36a8a", pulse: true }).querySelector(".pulse-glyph")).toBeNull();
  });

  it("draws the alpaca as twelve facets in one flat ink whatever colour it is given", () => {
    for (const color of ["#f0b447", "var(--accent)", undefined]) {
      const root = draw({ fold: "alpaca", color, size: 72 });
      expect(root.querySelectorAll("polygon")).toHaveLength(12);
      expect(new Set([...root.querySelectorAll("polygon")].map((p) => p.getAttribute("fill")))).toEqual(new Set(["var(--alp)"]));
      expect(root.querySelector(".ds-diamond")).toBeNull();
      cleanup();
    }
  });

  it("draws the alpaca larger than its slot in rows and headers so it weighs as much as the other objects", () => {
    const row = draw({ fold: "alpaca" });
    expect(row.style.width).toBe("16px");
    expect(Number(row.querySelector("svg").getAttribute("width"))).toBeCloseTo(16 * 1.3);
    cleanup();
    const header = draw({ fold: "alpaca", size: "md" });
    expect(Number(header.querySelector("svg").getAttribute("width"))).toBeCloseTo(20 * 1.3);
    cleanup();
    expect(draw({ fold: "alpaca", size: 72 }).querySelector("svg").getAttribute("width")).toBe("72");
    cleanup();
    expect(draw({ fold: "shield" }).querySelector("svg").getAttribute("width")).toBe("16");
  });

  it("carries the brand ink of each theme for the alpaca", async () => {
    const { BRAND_INK } = await import("../../../common/folds.mjs");
    const root = draw({ fold: "alpaca", size: 72 });
    expect(root.style.getPropertyValue("--alp-l")).toBe(BRAND_INK.light);
    expect(root.style.getPropertyValue("--alp-d")).toBe(BRAND_INK.dark);
  });

  it("paints the alpaca in the theme accent when no colour is given", () => {
    const root = draw({ fold: "alpaca" });
    expect(root.style.getPropertyValue("--c")).toBe("var(--accent)");
  });

  it("follows the theme for a colour that is not a hex", () => {
    const root = draw({ fold: "tree", color: "var(--accent)" });
    expect(root.style.getPropertyValue("--c")).toBe("var(--accent)");
    expect(root.querySelector("polygon").getAttribute("fill")).toContain("var(--c,");
  });

  it("falls back to the neutral ink when a profile has no colour", () => {
    const root = draw({ fold: "house" });
    const fills = [...root.querySelectorAll("polygon")].map((p) => p.getAttribute("fill"));
    expect(fills.every((f) => f.includes("var(--c, var(--ink-3))"))).toBe(true);
    expect(root.style.getPropertyValue("--c")).toBe("");
  });
  describe("honeycomb", () => {
    const cells = (root) => [...root.querySelectorAll("polygon")];

    it("draws the three cells in the given colour at row, header and hero size", () => {
      const row = draw({ fold: WORKGROUP_FOLD, color: "#3899e2" });
      expect(row.dataset.fold).toBe(WORKGROUP_FOLD);
      expect(cells(row)).toHaveLength(3);
      expect(cells(row).map((c) => c.getAttribute("fill"))).toContain("#3899e2");
      expect(row.style.width).toBe("16px");
      cleanup();
      expect(draw({ fold: WORKGROUP_FOLD, color: "#3899e2", size: "md" }).style.width).toBe("20px");
      cleanup();
      expect(draw({ fold: WORKGROUP_FOLD, color: "#3899e2", size: 72 }).style.width).toBe("72px");
    });

    it("ripples each cell with its own negative delay when working, and leaves the whole glyph steady", () => {
      const root = draw({ fold: WORKGROUP_FOLD, color: "#3899e2", pulse: true });
      expect(root.querySelector("svg").getAttribute("class")).toBeNull();
      const delays = cells(root).map((c) => c.style.animationDelay);
      expect(delays.map(Number.parseFloat)).toEqual([0, -0.47, -0.93]);
      expect(cells(root).every((c) => /cell/.test(c.getAttribute("class")))).toBe(true);
    });

    it("ripples every working object the same way, the alpaca included, and stays still when idle", () => {
      for (const fold of ["heart", "alpaca"]) {
        const working = draw({ fold, color: "#f36a8a", pulse: true });
        expect(working.querySelector("svg").getAttribute("class")).toBeNull();
        expect(cells(working).every((c) => /cell/.test(c.getAttribute("class")) && c.style.animationDelay !== "")).toBe(true);
        cleanup();
      }
      const idle = draw({ fold: WORKGROUP_FOLD, color: "#3899e2" });
      expect(cells(idle).every((c) => c.getAttribute("class") === null)).toBe(true);
    });

    it("outlines the cells when paused", () => {
      const paused = draw({ fold: WORKGROUP_FOLD, color: "#3899e2", outlined: true });
      expect(cells(paused).every((c) => c.getAttribute("fill-opacity") === "0.22" && c.getAttribute("stroke") !== null)).toBe(true);
    });

    it("loops on the shared loop token and stops under the one global prefers-reduced-motion rule", () => {
      const css = readFileSync(join(import.meta.dirname, "Fold.module.css"), "utf8");
      const ds = readFileSync(join(import.meta.dirname, "../styles/design-system.css"), "utf8");
      expect(css).toMatch(/\.cell\s*\{\s*animation:\s*cellRipple var\(--dur-loop\) ease-in-out infinite;/);
      expect(css).not.toMatch(/prefers-reduced-motion/);
      expect(ds).toMatch(/@media \(prefers-reduced-motion: reduce\)\s*\{\s*\*,\s*\*::before,\s*\*::after\s*\{[^}]*animation-duration:\s*0\.01ms\s*!important;[^}]*animation-iteration-count:\s*1\s*!important/);
    });
  });

  it("unfolds into the dashed crease pattern with no fill and no ripple when its daemon is away", () => {
    const root = draw({ fold: "shield", color: "#3899e2", pulse: true, unfolded: true });
    expect(root.hasAttribute("data-unfolded")).toBe(true);
    for (const polygon of root.querySelectorAll("polygon")) {
      expect(polygon.getAttribute("fill")).toBe("none");
      expect(polygon.getAttribute("stroke-dasharray")).toBeTruthy();
      expect(polygon.getAttribute("class") ?? "").toBe("");
    }
  });
});
