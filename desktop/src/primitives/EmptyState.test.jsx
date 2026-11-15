import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";

import EmptyState from "./EmptyState.jsx";

const glyphOf = (heading) => screen.getByRole("heading", { name: heading }).parentElement.firstElementChild;

describe("brand glyphs are folds", () => {
  it("EmptyState shows Twin in the theme's brand ink by default", () => {
    render(<EmptyState heading="Nothing here" />);
    const glyph = glyphOf("Nothing here");
    expect(glyph.dataset.mark).toBe("alpi-twin");
    expect(glyph.querySelector("path[data-body]").getAttribute("fill")).toBe("var(--accent)");
    expect(glyph.style.width).toBe("72px");
  });

  it("EmptyState draws the workgroup it is given neutral at rest", () => {
    render(<EmptyState shape="honeycomb" accent="#3388ff" heading="No workgroups" />);
    const glyph = glyphOf("No workgroups");
    expect(glyph.dataset.shape).toBe("honeycomb");
    expect([...glyph.querySelectorAll("[data-cell]")].map((c) => c.getAttribute("fill"))).toEqual(["var(--ink-3)", "var(--ink-3)", "var(--ink-3)"]);
  });
});
