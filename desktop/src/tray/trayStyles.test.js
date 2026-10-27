import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const css = readFileSync(join(import.meta.dirname, "TrayApp.module.css"), "utf8");
const rule = (selector) => {
  const start = css.indexOf(`${selector} {`);
  expect(start, `${selector} rule`).toBeGreaterThanOrEqual(0);
  return css.slice(start, css.indexOf("}", start));
};

describe("tray popover pixels", () => {
  it("is --pop-md wide inside a one pixel frame so the edge ring is not clipped", () => {
    expect(rule(".pop")).toMatch(/width:\s*var\(--pop-md\)/);
    expect(rule(".frame")).toMatch(/width:\s*calc\(var\(--pop-md\) \+ 2px\)/);
    expect(rule(".frame")).toMatch(/padding:\s*1px/);
  });

  it("uses the tiered edge, the elevated surface and a 4 px radius, and stays flat", () => {
    const pop = rule(".pop");
    expect(pop).toMatch(/border-radius:\s*var\(--r-xs\)/);
    expect(pop).toMatch(/box-shadow:\s*var\(--shadow-edge-lg\)/);
    expect(pop).toMatch(/background:\s*var\(--bg-elev\)/);
    expect(pop).toMatch(/overflow:\s*hidden/);
  });

  it("lets the transparent window show through the page", () => {
    expect(css).toMatch(/:global\(html\),\s*:global\(body\),\s*:global\(#root\) \{[^}]*background:\s*transparent/);
  });

  it("sizes needs-you rows at 40, count rows at 32 and the glyph at 16", () => {
    expect(rule(".row")).toMatch(/height:\s*var\(--ctl-40\)/);
    expect(rule(".line,\n.busy")).toMatch(/height:\s*var\(--ctl-32\)/);
    expect(rule(".glyph")).toMatch(/width:\s*var\(--icon-md\)/);
    expect(rule(".update")).toMatch(/min-height:\s*var\(--ctl-40\)/);
  });

  it("pads the heading and the footer on the 12 px inset the board draws", () => {
    expect(rule(".head")).toMatch(/padding:\s*var\(--sp-12\)/);
    expect(rule(".foot")).toMatch(/padding:\s*var\(--sp-8\) var\(--sp-12\)/);
    expect(rule(".section")).toMatch(/padding:\s*0 var\(--sp-8\) var\(--sp-8\)/);
  });

  it("types the title at 15 semibold and the line under it at 13", () => {
    expect(rule(".title")).toMatch(/font-size:\s*var\(--text-chat\)/);
    expect(rule(".title")).toMatch(/font-weight:\s*var\(--fw-semibold\)/);
    expect(rule(".sub")).toMatch(/font-size:\s*var\(--text-ui\)/);
  });

  it("draws the unread dot like the sidebar bell", () => {
    const dot = rule(".bellDot");
    expect(dot).toMatch(/width:\s*var\(--dot-md\)/);
    expect(dot).toMatch(/background:\s*var\(--c-danger\)/);
  });

  it("carries no raw colour and no raw pixel size beyond the frame ring", () => {
    expect(css).not.toMatch(/#[0-9a-fA-F]{3,8}\b|rgb\(|rgba\(/);
    const px = [...css.matchAll(/(\d*\.?\d+)px/g)].map((m) => m[0]);
    expect(px.every((v) => ["1px", "2px", ".5px"].includes(v))).toBe(true);
  });

  it("keeps the root ring-free and lets the buttons show focus only through :focus-visible, inset", () => {
    expect(css).toMatch(/\.frame:focus \{\s*outline: none;\s*\}\s*\.frame:focus-visible \{\s*outline-style: none;/);
    expect(css).toMatch(/\.pop button:focus-visible \{\s*outline-offset:\s*calc\(var\(--focus-outline-offset\) \* -1\)/);
    expect(css).not.toMatch(/button:focus \{|\.line:focus \{/);
  });

  it("keeps focus visible on every line and inherits the app's outline", () => {
    expect(css).toMatch(/\.line:focus-visible \{\s*outline-offset:\s*calc\(var\(--focus-outline-offset\) \* -1\)/);
  });
});

describe("tray Next line pixels", () => {
  it("keeps the time from truncating while the title gives way", () => {
    expect(css).toMatch(/\.nextLead,\s*\.nextWhen \{\s*flex-shrink:\s*0/);
    expect(rule(".nextTitle")).toMatch(/text-overflow:\s*ellipsis/);
    expect(rule(".nextTitle")).toMatch(/min-width:\s*0/);
    expect(rule(".sub[data-next]")).toMatch(/white-space:\s*nowrap/);
  });

  it("adds no row, so the quiet popover keeps its 107 px", () => {
    expect(css).not.toMatch(/\.ask|\.chip/);
  });
});
