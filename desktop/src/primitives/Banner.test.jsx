import { readFileSync } from "node:fs";
import { join } from "node:path";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import Banner from "./Banner.jsx";
import { palettes } from "../../../common/tokens.mjs";
import { contrastRatio } from "../../../common/name.mjs";

afterEach(cleanup);

const read = (rel) => readFileSync(join(import.meta.dirname, "..", rel), "utf8");
const DS = read("styles/design-system.css");
const TOKENS = read("styles/tokens.css");
const rule = (sheet, selector) => {
  const at = sheet.search(new RegExp(`(^|\\n)${selector.replace(/\./g, "\\.")}\\s+\\{`));
  return at < 0 ? "" : sheet.slice(at, sheet.indexOf("}", at) + 1);
};
const KINDS = ["info", "success", "warning", "danger"];
const HUE = { info: "ink", success: "success", warning: "warning", danger: "danger" };
const TEXT = { info: "ink2", success: "successText", warning: "warningText", danger: "dangerText" };

const tint = (theme, name) => {
  const light = Number(TOKENS.match(new RegExp(`:root \\{[^}]*--${name}: (\\d+)%`))[1]);
  const dark = Number(TOKENS.match(new RegExp(`\\[data-mode="dark"\\] \\{[^}]*--${name}: (\\d+)%`))[1]);
  return (theme === "light" ? light : dark) / 100;
};
const blend = (hex, base, amount) =>
  "#" + [1, 3, 5].map((i) => Math.round(parseInt(hex.slice(i, i + 2), 16) * amount + parseInt(base.slice(i, i + 2), 16) * (1 - amount)).toString(16).padStart(2, "0")).join("");
const bannerSurface = (kind, theme) => {
  const p = palettes[theme];
  return blend(p[HUE[kind]], p.bgPane, tint(theme, kind === "info" ? "banner-tint-quiet" : "banner-tint"));
};

describe("status banner surface", () => {
  it("is flat and square: no border, outline, shadow or radius", () => {
    for (const selector of [".banner", ...KINDS.map((k) => `.banner.is-${k}`)]) {
      const body = rule(DS, selector);
      expect(body, selector).not.toBe("");
      expect(body, selector).not.toMatch(/border|outline|box-shadow|radius/);
    }
  });

  it("mixes the kind's hue into the pane, 10 % / 14 % for status kinds and a 5 % / 6 % ink for info", () => {
    expect(tint("light", "banner-tint")).toBe(0.1);
    expect(tint("dark", "banner-tint")).toBe(0.14);
    expect(tint("light", "banner-tint-quiet")).toBe(0.05);
    expect(tint("dark", "banner-tint-quiet")).toBe(0.06);
    expect(TOKENS.match(/:root:not\(\[data-mode="light"\]\) \{[^}]*--banner-tint: 14%;[^}]*--banner-tint-quiet: 6%;/)).not.toBeNull();
    for (const kind of ["success", "warning", "danger"]) {
      expect(rule(DS, `.banner.is-${kind}`)).toMatch(new RegExp(`background: color-mix\\(in srgb, var\\(--c-${kind}\\)\\s+var\\(--banner-tint\\), var\\(--bg-pane\\)\\)`));
      expect(rule(DS, `.banner.is-${kind}`)).toMatch(new RegExp(`--banner-text: var\\(--c-${kind}-text\\)`));
    }
    expect(rule(DS, ".banner.is-info")).toMatch(/background: color-mix\(in srgb, var\(--ink\)\s+var\(--banner-tint-quiet\), var\(--bg-pane\)\)/);
    expect(rule(DS, ".banner.is-info")).toMatch(/--banner-text: var\(--ink-2\)/);
  });

  it("sets the action as text in the kind's text colour", () => {
    const action = rule(read("primitives/Banner.module.css"), ".action");
    expect(action).toMatch(/color: var\(--banner-text, var\(--ink-2\)\)/);
    expect(action).not.toMatch(/background|border/);
  });

  it("keeps every text at 4.5:1 on its surface in light and dark", () => {
    for (const theme of ["light", "dark"]) {
      const p = palettes[theme];
      for (const kind of KINDS) {
        const surface = bannerSurface(kind, theme);
        for (const ink of ["ink", "ink2", TEXT[kind]]) {
          expect(contrastRatio(p[ink], surface), `${theme} ${kind} ${ink}`).toBeGreaterThanOrEqual(4.5);
        }
      }
    }
  });
});

describe("Banner", () => {
  it("leads warning and danger with the alert glyph in the kind's text colour", () => {
    for (const kind of ["warning", "danger"]) {
      const { container, unmount } = render(<Banner kind={kind}>x</Banner>);
      const glyph = container.querySelector('[data-icon="triangle-alert"]');
      expect(glyph, kind).not.toBeNull();
      expect(glyph.style.color).toBe(`var(--c-${kind}-text)`);
      expect(container.querySelector(".ds-dot")).toBeNull();
      unmount();
    }
  });

  it("leads info with the ink-3 dot and success with its text-colour dot, no glyph and no disc", () => {
    const expected = { info: "var(--ink-3)", success: "var(--c-success-text)" };
    for (const [kind, color] of Object.entries(expected)) {
      const { container, unmount } = render(<Banner kind={kind}>x</Banner>);
      expect(container.querySelector("[data-icon]")).toBeNull();
      const dot = container.querySelector(".ds-dot");
      expect(dot.style.getPropertyValue("--c")).toBe(color);
      expect(container.firstChild.children).toHaveLength(2);
      unmount();
    }
  });

  it("carries its kind on the surface, announces danger as an alert and falls back to info", () => {
    const { container, rerender } = render(<Banner kind="danger">x</Banner>);
    expect(container.firstChild.className).toBe("banner is-danger");
    expect(screen.getByRole("alert")).toBeTruthy();
    rerender(<Banner kind="bogus">x</Banner>);
    expect(container.firstChild.className).toBe("banner is-info");
    expect(screen.getByRole("status")).toBeTruthy();
  });

  it("pulses the glyph or the dot when asked", () => {
    const { container, rerender } = render(<Banner kind="danger" pulsing>x</Banner>);
    expect(container.querySelector('[data-icon="triangle-alert"]').getAttribute("class")).toMatch(/pulse-glyph/);
    rerender(<Banner kind="info" pulsing>x</Banner>);
    expect(container.querySelector(".ds-dot").className).toMatch(/pulse-dot/);
  });

  it("renders the action as a plain text button", () => {
    const onAction = vi.fn();
    render(<Banner kind="warning" action="Resume" onAction={onAction}>paused</Banner>);
    const button = screen.getByRole("button", { name: "Resume" });
    expect(button.className).toMatch(/alink/);
    fireEvent.click(button);
    expect(onAction).toHaveBeenCalledTimes(1);
  });
});
