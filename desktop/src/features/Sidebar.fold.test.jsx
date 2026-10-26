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

describe("Sidebar roster state", () => {
  const roster = [
    { name: "doc", model: "a/b", accent: "#3899e2" },
    { name: "napper", model: "a/b", accent: "#3899e2", paused: true },
    { name: "fresh", accent: "#3899e2" },
  ];

  it("keeps the glyphs folded for a plain disconnect and unfolds only the paused profile", () => {
    render(<Sidebar {...BASE} profiles={roster} daemonOffline />);
    expect(glyph("doc").dataset.unfolded).toBeUndefined();
    expect(glyph("napper").dataset.unfolded).toBeDefined();
  });

  it("says paused and needs provider in words instead of fading the row", () => {
    render(<Sidebar {...BASE} profiles={roster} />);
    expect(screen.getByText("napper").closest("button")).toHaveTextContent("paused");
    expect(screen.getByText("fresh").closest("button")).toHaveTextContent("needs provider");
    expect(screen.getByText("doc").closest("button")).not.toHaveTextContent("paused");
    expect(screen.getByText("napper").closest("button").style.opacity).toBe("");
  });

  it("draws the selected row's accent bar in that profile's colour", () => {
    render(
      <Sidebar
        {...BASE}
        view={{ kind: "profile", profile: "doc" }}
        profiles={[
          { name: "doc", model: "a/b", accent: "#3899e2", fold: "shield" },
          { name: "abby", model: "a/b", accent: "#e8708a" },
        ]}
      />,
    );
    const selected = screen.getByText("doc").closest("button");
    expect(selected.hasAttribute("data-sel")).toBe(true);
    expect(selected.style.getPropertyValue("--row-accent")).toBe("#3899e2");
    expect(screen.getByText("abby").closest("button").style.getPropertyValue("--row-accent")).toBe("");
  });
});
