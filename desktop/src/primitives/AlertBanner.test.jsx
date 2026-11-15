import { readFileSync } from "node:fs";
import { join } from "node:path";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import AlertBanner from "./AlertBanner.jsx";
import { palettes } from "../../../common/tokens.mjs";
import { contrastRatio } from "../../../common/name.mjs";

afterEach(cleanup);

const CSS = readFileSync(join(import.meta.dirname, "AlertBanner.module.css"), "utf8");
const TOKENS = readFileSync(join(import.meta.dirname, "..", "styles", "tokens.css"), "utf8");
const TINT = {
  light: Number(TOKENS.match(/:root \{[^}]*--banner-tint: (\d+)%/)[1]) / 100,
  dark: Number(TOKENS.match(/\[data-mode="dark"\] \{[^}]*--banner-tint: (\d+)%/)[1]) / 100,
};
const blend = (hex, base, amount) =>
  "#" + [1, 3, 5].map((i) => Math.round(parseInt(hex.slice(i, i + 2), 16) * amount + parseInt(base.slice(i, i + 2), 16) * (1 - amount)).toString(16).padStart(2, "0")).join("");
const rule = (selector) => {
  const at = CSS.indexOf(`${selector} {`);
  return CSS.slice(at, CSS.indexOf("}", at) + 1);
};

describe("AlertBanner", () => {
  it("is one flat square danger tint: no border, outline, shadow or radius", () => {
    const plain = CSS.replace(/@media \(forced-colors: active\) \{[^{}]*\{[^{}]*\}\s*\}/g, "");
    expect(plain).not.toMatch(/border|outline|box-shadow|radius|ring/);
    expect(rule(".banner")).toMatch(/background: color-mix\(in srgb, var\(--c-danger\) var\(--banner-tint\), var\(--bg-pane\)\)/);
  });

  it("leads with the alert glyph in the danger text colour, a bold ink lead and an ink-2 detail", () => {
    const { container } = render(<AlertBanner lead="Nearly full" detail="4,800 / 5,000" />);
    expect(container.querySelector('[data-icon="triangle-alert"]').style.color).toBe("var(--c-danger-text)");
    expect(rule(".lead")).toMatch(/color: var\(--ink\);/);
    expect(rule(".lead")).toMatch(/font-weight: var\(--fw-semibold\)/);
    expect(rule(".detail")).toMatch(/color: var\(--ink-2\);/);
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("offers its action as plain text in the danger text colour", () => {
    const onAction = vi.fn();
    render(<AlertBanner lead="Last run failed" action="Run now" onAction={onAction} />);
    const button = screen.getByRole("button", { name: "Run now" });
    expect(button.className).toMatch(/alink/);
    expect(rule(".action")).toMatch(/color: var\(--c-danger-text\)/);
    expect(rule(".action")).not.toMatch(/background/);
    fireEvent.click(button);
    expect(onAction).toHaveBeenCalledTimes(1);
  });

  it("disables the action while busy", () => {
    render(<AlertBanner lead="x" action="Run now" onAction={() => {}} disabled />);
    expect(screen.getByRole("button", { name: "Run now" }).disabled).toBe(true);
  });

  it("keeps the lead, detail and action at 4.5:1 on the tint in light and dark", () => {
    for (const theme of ["light", "dark"]) {
      const p = palettes[theme];
      const surface = blend(p.danger, p.bgPane, TINT[theme]);
      for (const ink of ["ink", "ink2", "dangerText"]) {
        expect(contrastRatio(p[ink], surface), `${theme} ${ink}`).toBeGreaterThanOrEqual(4.5);
      }
    }
  });
});
