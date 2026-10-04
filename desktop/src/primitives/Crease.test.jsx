import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { render, screen } from "@testing-library/react";
import { CREASE_MIN_CONTRAST, contrastRatio, creaseGradient } from "../../../common/crease.mjs";
import Crease, { creaseVars } from "./Crease.jsx";

const LIGHT_GROUND = "#ffffff";
const DARK_GROUND = "#151515";
const HEX = /^#[0-9a-f]{6}$/;

const ladder = (el, prefix) => [1, 2, 3].map((i) => el.style.getPropertyValue(`--crease-${prefix}${i}`));

describe("Crease", () => {
  it("keeps the text real and selectable", () => {
    render(<Crease text="doc" accent="#3899e2" />);
    const el = screen.getByText("doc");
    expect(el.tagName).toBe("SPAN");
    expect(el.className).toMatch(/crease/);
  });

  it("renders as the requested element and merges the class and size", () => {
    render(<Crease text="doc" accent="#3899e2" as="strong" className="extra" size="40px" />);
    const el = screen.getByText("doc");
    expect(el.tagName).toBe("STRONG");
    expect(el.classList.contains("extra")).toBe(true);
    expect(el.style.fontSize).toBe("40px");
  });

  it("sets six tone vars that read on both panes", () => {
    render(<Crease text="doc" accent="#3899e2" />);
    const el = screen.getByText("doc");
    const light = ladder(el, "l");
    const dark = ladder(el, "d");
    for (const hex of [...light, ...dark]) expect(hex).toMatch(HEX);
    for (const hex of light) expect(contrastRatio(hex, LIGHT_GROUND)).toBeGreaterThanOrEqual(CREASE_MIN_CONTRAST);
    for (const hex of dark) expect(contrastRatio(hex, DARK_GROUND)).toBeGreaterThanOrEqual(CREASE_MIN_CONTRAST);
  });

  it.each(["red", undefined, "", "#abc"])("falls back to readable neutral tones for %j", (accent) => {
    render(<Crease text="doc" accent={accent} />);
    const el = screen.getByText("doc");
    for (const hex of ladder(el, "l")) {
      expect(hex).toMatch(HEX);
      expect(contrastRatio(hex, LIGHT_GROUND)).toBeGreaterThanOrEqual(CREASE_MIN_CONTRAST);
    }
    for (const hex of ladder(el, "d")) {
      expect(hex).toMatch(HEX);
      expect(contrastRatio(hex, DARK_GROUND)).toBeGreaterThanOrEqual(CREASE_MIN_CONTRAST);
    }
  });

  it("injects the gradients built from the same tones", () => {
    const vars = creaseVars("#3899e2");
    expect(vars["--crease-light"]).toBe(creaseGradient([vars["--crease-l1"], vars["--crease-l2"], vars["--crease-l3"]]));
    expect(vars["--crease-dark"]).toBe(creaseGradient([vars["--crease-d1"], vars["--crease-d2"], vars["--crease-d3"]]));
  });

  it("picks the dark ladder under the dark theme and falls back to canvas text in forced colours", () => {
    const css = readFileSync(join(import.meta.dirname, "Crease.module.css"), "utf8");
    expect(css).toMatch(/\[data-mode="dark"\]\)?\s*\.crease\s*\{[^}]*--crease-dark/);
    expect(css).toMatch(/prefers-color-scheme: dark[\s\S]*--crease-dark/);
    expect(css).toMatch(/forced-colors: active[\s\S]*CanvasText/);
    expect(css).toMatch(/background-clip: text/);
  });
});
