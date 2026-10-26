import { readFileSync } from "node:fs";
import { join } from "node:path";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import UsageSkeleton, { DAY_BARS } from "./UsageSkeleton.jsx";
import { Reveal } from "./Skeleton.jsx";

const read = (f) => readFileSync(join(import.meta.dirname, f), "utf8");
const feature = (f) => readFileSync(join(import.meta.dirname, "..", "features", "settings", f), "utf8");

describe("UsageSkeleton silhouette", () => {
  it("draws four tiles, fourteen varied bars and a two-line legend", () => {
    const { container } = render(<UsageSkeleton />);
    expect(screen.getByRole("img", { name: "Loading usage" })).toBeInTheDocument();
    expect(container.querySelectorAll("[data-tile]")).toHaveLength(4);
    expect(container.querySelectorAll("[data-bar]")).toHaveLength(14);
    expect(new Set(DAY_BARS).size).toBeGreaterThan(8);
    const tiles = [...container.querySelectorAll("[data-tile]")];
    expect(tiles.every((t) => t.querySelectorAll("span").length === 2)).toBe(true);
    expect(tiles[0].querySelectorAll("span")[1].style.width).toBe("96px");
    expect(tiles[0].querySelectorAll("span")[1].style.height).toBe("28px");
    expect(container.querySelector("[class*=foot]").querySelectorAll("span")).toHaveLength(2);
  });

  it("derives every slot height, track height, padding and gap from the loaded widget's values", () => {
    const sk = read("UsageSkeleton.module.css");
    const real = read("../features/settings/Usage.module.css");
    const rule = (css, sel) => css.match(new RegExp(`(?:^|\\n)\\.${sel}\\s*\\{([^}]*)\\}`))?.[1] ?? "";
    const prop = (css, sel, p) => rule(css, sel).match(new RegExp(`(?:^|[\\s;])${p}:\\s*([^;]+);`))?.[1].trim();
    const lh = (css, sel) => prop(css, sel, "line-height") ?? "var(--lh-normal)";
    const slot = (css, sel) => `calc(${prop(css, sel, "font-size")} * ${lh(css, sel)})`;
    const norm = (v) => v.replace(/\s+/g, " ");

    expect(norm(prop(sk, "labelSlot", "height"))).toBe(norm(slot(real, "statLabel")));
    expect(prop(sk, "labelSlot", "margin-bottom")).toBe(prop(real, "statLabel", "margin-bottom"));
    expect(norm(prop(sk, "leadSlot", "height"))).toBe(norm(slot(real, "today")));
    expect(norm(prop(sk, "valueSlot", "height"))).toBe(norm(slot(real, "statValue")));
    expect(norm(prop(sk, "footSlot", "height"))).toBe(norm(slot(real, "legend")));
    expect(norm(prop(sk, "footSlot", "height"))).toBe(norm(slot(real, "totals")));
    expect(norm(prop(sk, "labels", "height"))).toBe(norm(slot(real, "dayLabel")));
    expect(prop(sk, "labels", "margin-top")).toBe(prop(real, "labels", "margin-top"));
    expect(prop(sk, "track", "height")).toBe(prop(real, "track", "height"));
    expect(prop(sk, "track", "gap")).toBe(prop(real, "track", "gap"));
    expect(prop(sk, "track", "margin-top")).toBe(prop(real, "chart", "margin-top"));
    expect(prop(sk, "stats", "padding-bottom")).toBe(prop(real, "stats", "padding-bottom"));
    expect(prop(sk, "stats", "border-bottom")).toBe(prop(real, "stats", "border-bottom"));
    expect(prop(sk, "foot", "margin-top")).toBe(prop(real, "foot", "margin-top"));
    expect(prop(sk, "foot", "gap")).toBe(prop(real, "foot", "gap"));
    expect(prop(sk, "wrap", "--u-bar-w")).toBe(prop(real, "wrap", "--u-bar-w"));
  });

  it("centres the bones inside fixed slots, one per line", () => {
    const { container } = render(<UsageSkeleton />);
    const slots = container.querySelectorAll("[class*=labelSlot], [class*=footSlot]");
    expect(slots).toHaveLength(6);
    slots.forEach((s) => expect(s.querySelectorAll("span")).toHaveLength(1));
  });

  it("wraps loaded content in a crossfade class unless told not to animate", () => {
    const on = render(<Reveal><p>x</p></Reveal>);
    expect(on.container.firstElementChild.className).toMatch(/reveal/);
    const off = render(<Reveal animate={false}><p>x</p></Reveal>);
    expect(off.container.firstElementChild.className).not.toMatch(/reveal/);
  });
});

describe("skeleton consumers", () => {
  it("usage loads as the silhouette, never the 104 px slab", () => {
    const src = feature("ProfileDetail.jsx");
    expect(src).toMatch(/<UsageSkeleton/);
    expect(src).toMatch(/useSkeletonPhase\(/);
    expect(src).toMatch(/<Reveal animate=\{usageRevealed\}>/);
    expect(src).not.toMatch(/height="104px"/);
  });

  it("field loaders use the hook and a value-sized pill", () => {
    for (const f of ["fields/WorkgroupsField.jsx", "fields/maintenance.jsx", "fields/devices.jsx", "fields/EmailCell.jsx"]) {
      const src = feature(f);
      expect(src).toMatch(/useSkeleton\(/);
      expect(src).toMatch(/width="112px" height="22px" radius="var\(--r-tag\)"/);
      expect(src).toMatch(/delay=\{0\}/);
    }
  });

  it("network pills and workgroup members hold the bones through the hook", () => {
    const net = feature("fields/network.jsx");
    expect(net.match(/useSkeleton\(!status\)/g)).toHaveLength(3);
    expect(net.match(/<Skeleton[^>]*delay=\{0\}/g)).toHaveLength(3);
    const wg = feature("WorkgroupDetail.jsx");
    expect(wg).toMatch(/useSkeleton\(members === null && !membersFailed\)/);
    expect(wg.match(/<Skeleton[^>]*delay=\{0\}/g)).toHaveLength(2);
  });
});
