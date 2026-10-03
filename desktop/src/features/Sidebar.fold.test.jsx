import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";

globalThis.ResizeObserver ??= class { observe() {} unobserve() {} disconnect() {} };
window.matchMedia ??= () => ({
  matches: false,
  addEventListener() {},
  removeEventListener() {},
  addListener() {},
  removeListener() {},
});

vi.mock("../lib/updater.js", () => ({
  describeUpdaterError: () => "",
  quitForUpdate: vi.fn(),
  applyPendingUpdate: vi.fn(),
  checkForUpdates: vi.fn(),
  subscribeUpdater: vi.fn(() => () => {}),
}));

import Sidebar from "./Sidebar.jsx";

const BASE = {
  workgroups: [],
  view: { kind: "landing" },
  hostConnections: { active_id: "remote", connections: [] },
};

const glyph = (name) => screen.getByText(name).closest("button").firstElementChild;

describe("Sidebar profile folds", () => {
  it("draws the profile's fold in its colour and the kite-base diamond for a profile without one", () => {
    render(
      <Sidebar
        {...BASE}
        profiles={[
          { name: "doc", model: "a/b", accent: "#3899e2", fold: "shield" },
          { name: "mind", model: "a/b", accent: "#3899e2" },
        ]}
      />,
    );
    const doc = glyph("doc");
    expect(doc.dataset.fold).toBe("shield");
    expect(doc.querySelector(".ds-diamond")).toBeNull();
    const fills = [...doc.querySelectorAll("polygon")].map((p) => p.getAttribute("fill"));
    expect(fills).toContain("#3899e2");
    expect(glyph("mind").dataset.fold).toBe("diamond");
    expect(glyph("mind").querySelector(".ds-diamond")).toBeNull();
    expect(glyph("mind").querySelectorAll("polygon").length).toBeGreaterThan(1);
  });

  it("keeps the slot 16px wide for both glyphs", () => {
    render(
      <Sidebar
        {...BASE}
        profiles={[
          { name: "doc", model: "a/b", accent: "#3899e2", fold: "heart" },
          { name: "mind", model: "a/b", accent: "#3899e2" },
        ]}
      />,
    );
    expect(glyph("doc").style.width).toBe("16px");
    expect(glyph("mind").style.width).toBe("16px");
  });

  it("outlines the fold of a profile that still needs a model", () => {
    render(<Sidebar {...BASE} profiles={[{ name: "doc", accent: "#3899e2", fold: "rocket" }]} />);
    const polygons = [...glyph("doc").querySelectorAll("polygon")];
    expect(polygons.length).toBeGreaterThan(0);
    expect(polygons.every((p) => p.getAttribute("fill-opacity") === "0.22")).toBe(true);
  });
});
