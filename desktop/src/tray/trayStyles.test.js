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
  it("draws on a transparent window without a forced colour scheme or a painted window colour", () => {
    const main = readFileSync(join(import.meta.dirname, "main.jsx"), "utf8");
    const rust = readFileSync(join(import.meta.dirname, "../../src-tauri/src/tray_popover.rs"), "utf8");
    expect(main).not.toMatch(/colorScheme/);
    expect(rust).toMatch(/\.transparent\(true\)/);
    expect(rust).not.toMatch(/background_color/);
    expect(rule(":global(html),\n:global(body),\n:global(#root)")).toMatch(/background:\s*transparent/);
  });

  it("is --pop-md wide inside a one pixel frame so the edge ring is not clipped", () => {
    expect(rule(".pop")).toMatch(/width:\s*var\(--pop-md\)/);
    expect(rule(".frame")).toMatch(/width:\s*calc\(var\(--pop-md\) \+ 2px\)/);
    expect(rule(".frame")).toMatch(/padding:\s*1px/);
  });

  it("draws only an inset edge, never a drop shadow the window would clip, on the elevated surface at the surface radius", () => {
    const pop = rule(".pop");
    expect(pop).toMatch(/border-radius:\s*var\(--r-surface\)/);
    expect(pop).toMatch(/box-shadow:\s*inset 0 0 0 1px var\(--line\)/);
    expect(pop).not.toMatch(/shadow-(edge|float)/);
    expect(pop).toMatch(/background:\s*var\(--bg-elev\)/);
    expect(pop).toMatch(/overflow:\s*hidden/);
  });

  it("keeps the heading subtitle on one line", () => {
    expect(rule(".sub")).toMatch(/white-space:\s*nowrap/);
    expect(rule(".sub")).toMatch(/text-overflow:\s*ellipsis/);
  });

  it("lets the transparent window show through the page", () => {
    expect(css).toMatch(/:global\(html\),\s*:global\(body\),\s*:global\(#root\) \{[^}]*background:\s*transparent/);
  });

  it("sizes rows at 52 on the control radius, the marks at 24 and count lines at 32", () => {
    expect(rule(".row")).toMatch(/min-height:\s*calc\(var\(--ctl-48\) \+ var\(--sp-4\)\)/);
    expect(rule(".row")).toMatch(/border-radius:\s*var\(--r-control\)/);
    expect(rule(".mark")).toMatch(/width:\s*var\(--icon-lg\)/);
    expect(rule(".line,\n.busy")).toMatch(/height:\s*var\(--ctl-32\)/);
  });

  it("pads the heading at 16 and the footer and sections on the board's insets", () => {
    expect(rule(".head")).toMatch(/padding:\s*var\(--sp-16\) var\(--sp-16\) var\(--sp-12\)/);
    expect(rule(".foot")).toMatch(/padding:\s*var\(--sp-8\) var\(--sp-12\) var\(--sp-12\)/);
    expect(rule(".section")).toMatch(/padding:\s*0 var\(--sp-8\) var\(--sp-4\)/);
  });

  it("types the title at 20 semibold, the summary and names at 14, the job at 15 and the meta at 12", () => {
    expect(rule(".title")).toMatch(/font-size:\s*var\(--text-title\)/);
    expect(rule(".title")).toMatch(/font-weight:\s*var\(--fw-semibold\)/);
    expect(rule(".sub")).toMatch(/font-size:\s*var\(--text-small\)/);
    expect(rule(".sectionLabel")).toMatch(/font-size:\s*var\(--text-small\)/);
    expect(rule(".name")).toMatch(/font-size:\s*var\(--text-small\)/);
    expect(rule(".rowTitle")).toMatch(/font-size:\s*var\(--text-ui\)/);
    expect(rule(".meta")).toMatch(/font-size:\s*var\(--text-meta\)/);
  });

  it("sets times in ink-2 at 14 and never lets them truncate", () => {
    const time = rule(".time");
    expect(time).toMatch(/font-size:\s*var\(--text-small\)/);
    expect(time).toMatch(/color:\s*var\(--ink-2\)/);
    expect(time).toMatch(/flex-shrink:\s*0/);
    expect(time).toMatch(/white-space:\s*nowrap/);
  });

  it("tints the failing and update banners like the app's banners, on the control radius", () => {
    expect(rule(".banner")).toMatch(/border-radius:\s*var\(--r-control\)/);
    expect(rule('.banner[data-tone="danger"]')).toMatch(/background:\s*color-mix\(in srgb, var\(--c-danger\) var\(--banner-tint\), var\(--bg-pane\)\)/);
    expect(rule('.banner[data-tone="success"]')).toMatch(/background:\s*color-mix\(in srgb, var\(--c-success\) var\(--banner-tint\), var\(--bg-pane\)\)/);
    expect(rule(".bannerTitle")).toMatch(/color:\s*var\(--c-danger-text\)/);
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
    expect(css).toMatch(/\.pop button:focus-visible \{\s*outline-offset:\s*var\(--focus-inset\)/);
    expect(css).not.toMatch(/button:focus \{|\.line:focus \{/);
  });

  it("keeps focus visible on every line and inherits the app's outline", () => {
    expect(css).toMatch(/\.line:focus-visible \{\s*outline-offset:\s*var\(--focus-inset\)/);
  });
});

describe("tray quiet list pixels", () => {
  it("adds no chip or ask element to the popover", () => {
    expect(css).not.toMatch(/\.ask|\.chip/);
  });
});
