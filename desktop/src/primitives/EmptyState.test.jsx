import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";

import EmptyState from "./EmptyState.jsx";
import BootSplash from "./BootSplash.jsx";

const glyphOf = (heading) => screen.getByRole("heading", { name: heading }).parentElement.firstElementChild;

describe("brand glyphs are folds", () => {
  it("EmptyState shows the alpaca in the theme's brand ink by default", () => {
    render(<EmptyState heading="Nothing here" />);
    const glyph = glyphOf("Nothing here");
    expect(glyph.dataset.fold).toBe("alpaca");
    expect(glyph.style.getPropertyValue("--alp-l")).toBe("#14110c");
    expect(glyph.style.width).toBe("72px");
  });

  it("EmptyState draws the fold it is given in the given colour", () => {
    render(<EmptyState fold="honeycomb" accent="#3388ff" heading="No workgroups" />);
    const glyph = glyphOf("No workgroups");
    expect(glyph.dataset.fold).toBe("honeycomb");
    expect([...glyph.querySelectorAll("polygon")].map((c) => c.getAttribute("fill"))).toContain("#3388ff");
  });

  it("BootSplash pulses the alpaca", () => {
    const { container } = render(<BootSplash />);
    const glyph = container.querySelector("[data-fold]");
    expect(glyph.dataset.fold).toBe("alpaca");
    expect(glyph.className).toMatch(/glyph/);
    expect(container.querySelector("svg[aria-label='alpi']")).toBeNull();
  });
});
