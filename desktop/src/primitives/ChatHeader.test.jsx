import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import ChatHeader from "./ChatHeader.jsx";

const titleGlyph = (container) => container.querySelector(".title-row").firstElementChild;

describe("ChatHeader", () => {
  it("draws the profile's fold at header size in its colour", () => {
    const { container } = render(<ChatHeader id="doc" accent="#3899e2" fold="plane" />);
    const glyph = titleGlyph(container);
    expect(glyph.dataset.fold).toBe("plane");
    expect(glyph.style.width).toBe("20px");
    expect(container.querySelector(".ds-diamond")).toBeNull();
    expect([...glyph.querySelectorAll("polygon")].map((p) => p.getAttribute("fill"))).toContain("#3899e2");
  });

  it("draws the kite-base origami for a profile that never chose a fold", () => {
    const { container } = render(<ChatHeader id="doc" accent="#3899e2" />);
    expect(container.querySelector(".ds-diamond")).toBeNull();
    expect(container.querySelector("[data-fold='diamond']")).not.toBeNull();
  });

  it("sets a profile's name in crease type in its colour", () => {
    const { container } = render(<ChatHeader id="doc" accent="#3899e2" fold="plane" />);
    const name = container.querySelector("h1 > span");
    expect(name.textContent).toBe("doc");
    expect(name.className).toMatch(/crease/);
    expect(name.style.getPropertyValue("--crease-l1")).toMatch(/^#[0-9a-f]{6}$/);
  });

  it("sets a workgroup's name in crease type too", () => {
    const { container } = render(<ChatHeader kind="workgroup" id="ops" accent="#3899e2" />);
    expect(container.querySelector("h1 > span").className).toMatch(/crease/);
  });

  it("draws a workgroup as the honeycomb at header size in the hub's colour, unfolded in grey when paused", () => {
    const { container, rerender } = render(<ChatHeader kind="workgroup" id="ops" accent="#3899e2" />);
    const glyph = titleGlyph(container);
    expect(glyph.dataset.fold).toBe("honeycomb");
    expect(glyph.style.width).toBe("20px");
    expect(glyph.querySelectorAll("polygon")).toHaveLength(3);
    expect([...glyph.querySelectorAll("polygon")].map((p) => p.getAttribute("fill"))).toContain("#3899e2");
    expect(container.querySelector("polygon").getAttribute("fill-opacity")).toBeNull();
    rerender(<ChatHeader kind="workgroup" id="ops" accent="#3899e2" paused />);
    expect(container.querySelector("polygon").getAttribute("fill")).toBe("none");
  });
});

describe("ChatHeader paused", () => {
  it("unfolds a paused profile in grey and draws its crease name in grey", () => {
    const { container, rerender } = render(<ChatHeader kind="profile" id="doc" accent="#f36a8a" fold="heart" />);
    const live = container.querySelector("h1 span").getAttribute("style");
    rerender(<ChatHeader kind="profile" id="doc" accent="#f36a8a" fold="heart" paused />);
    expect(container.querySelector("[data-fold]").hasAttribute("data-unfolded")).toBe(true);
    expect(container.querySelector("h1 span").getAttribute("style")).not.toBe(live);
  });
});

