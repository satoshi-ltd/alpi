import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import SettingsHero from "./SettingsHero.jsx";

describe("SettingsHero", () => {
  it("sets a profile's name in crease type", () => {
    const { container } = render(<SettingsHero id="doc" accent="#3899e2" fold="plane" />);
    expect(container.querySelector("h1 > span").className).toMatch(/crease/);
  });

  it("sets a workgroup's name in crease type", () => {
    const { container } = render(<SettingsHero kind="workgroup" id="ops" accent="#3899e2" />);
    expect(container.querySelector("h1 > span").className).toMatch(/crease/);
  });

  it("sets the connections heading in crease type too", () => {
    const { container } = render(<SettingsHero kind="connections" id="alpi" accent="#3899e2" />);
    const h1 = container.querySelector("h1");
    expect(h1.textContent).toBe("alpi");
    expect(h1.querySelector("span").className).toMatch(/crease/);
  });

  it("draws a workgroup as the honeycomb in the hub's colour, unfolded in grey when paused", () => {
    const { container, rerender } = render(<SettingsHero kind="workgroup" id="ops" accent="#3899e2" />);
    const glyph = container.querySelector(".title-row").firstElementChild;
    expect(glyph.dataset.fold).toBe("honeycomb");
    expect(glyph.style.width).toBe("20px");
    expect([...glyph.querySelectorAll("polygon")].map((p) => p.getAttribute("fill"))).toContain("#3899e2");
    expect(glyph.querySelector("polygon").getAttribute("fill-opacity")).toBeNull();
    rerender(<SettingsHero kind="workgroup" id="ops" accent="#3899e2" paused />);
    expect(container.querySelector("polygon").getAttribute("fill")).toBe("none");
  });
});
