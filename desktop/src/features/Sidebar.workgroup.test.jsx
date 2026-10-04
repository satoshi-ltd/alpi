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
import { WORKGROUP_FOLD } from "../../../common/folds.mjs";

const BASE = {
  profiles: [{ name: "alpi", model: "a/b", accent: "#3899e2", fold: "shield" }],
  view: { kind: "landing" },
  hostConnections: { active_id: "remote", connections: [] },
};

const glyph = (name) => screen.getByText(name).closest("button").querySelector("[data-fold]");
const cells = (el) => [...el.querySelectorAll("polygon")];

describe("Sidebar workgroup rows", () => {
  it("draw the honeycomb in the hub's colour, not the two diamonds", () => {
    render(<Sidebar {...BASE} workgroups={[{ profile: "alpi", id: "crew", name: "launch-crew" }]} />);
    const el = glyph("launch-crew");
    expect(el.dataset.fold).toBe(WORKGROUP_FOLD);
    expect(el.style.width).toBe("16px");
    expect(cells(el)).toHaveLength(3);
    expect(cells(el).map((c) => c.getAttribute("fill"))).toContain("#3899e2");
    expect(cells(el).every((c) => c.getAttribute("fill-opacity") === null)).toBe(true);
    expect(el.closest("button").querySelector(".ds-diamond")).toBeNull();
  });

  it("ripple the cells while working", () => {
    render(
      <Sidebar
        {...BASE}
        workgroups={[{ profile: "alpi", id: "crew", name: "launch-crew" }]}
        rosterState={{ profiles: {}, workgroups: { "alpi/crew": { state: "working", phase: "analyze" } } }}
      />,
    );
    const el = glyph("launch-crew");
    expect(cells(el).every((c) => c.style.animationDelay !== "")).toBe(true);
    expect(el.querySelector(".pulse-glyph")).toBeNull();
  });

  it("unfolds the honeycomb in grey when paused", () => {
    render(<Sidebar {...BASE} workgroups={[{ profile: "alpi", id: "crew", name: "launch-crew", paused: true }]} />);
    expect(cells(glyph("launch-crew")).every((c) => c.getAttribute("fill") === "none")).toBe(true);
  });

  it("unfolds a paused workgroup even while a run is still in flight", () => {
    render(
      <Sidebar
        {...BASE}
        workgroups={[{ profile: "alpi", id: "crew", name: "launch-crew", paused: true }]}
        rosterState={{ profiles: {}, workgroups: { "alpi/crew": { state: "working", phase: "analyze" } } }}
      />,
    );
    const el = glyph("launch-crew");
    expect(cells(el).every((c) => c.getAttribute("fill") === "none")).toBe(true);
    expect(cells(el).every((c) => c.style.animationDelay === "")).toBe(true);
  });
});
