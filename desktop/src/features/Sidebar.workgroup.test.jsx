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
import { WORKGROUP_SHAPE } from "../../../common/shapes.mjs";
import { nameTone } from "../../../common/name.mjs";
import { palettes } from "../../../common/tokens.mjs";

const BASE = {
  profiles: [{ name: "alpi", model: "a/b", accent: "#3899e2", shape: "bell" }],
  view: { kind: "landing" },
  hostConnections: { active_id: "remote", connections: [] },
};

const glyph = (name) => screen.getByText(name).closest("button").querySelector("[data-shape]");
const cells = (el) => [...el.querySelectorAll("[data-cell]")];
const paint = (cell) => (cell.tagName === "g" ? cell.querySelector("path") : cell);

describe("Sidebar workgroup rows", () => {
  it("draw the soft honeycomb in neutral ink at rest, not the hub's colour, at row size", () => {
    render(<Sidebar {...BASE} workgroups={[{ profile: "alpi", id: "crew", name: "launch-crew" }]} />);
    const el = glyph("launch-crew");
    expect(el.dataset.shape).toBe(WORKGROUP_SHAPE);
    expect(el.dataset.mark).toBe("soft-honeycomb");
    expect(el.dataset.state).toBe("idle");
    expect(el.style.width).toBe("24px");
    expect(cells(el).map((c) => c.getAttribute("fill"))).toEqual(["var(--ink-3)", "var(--ink-3)", "var(--ink-3)"]);
    expect(cells(el).every((c) => c.getAttribute("fill-opacity") === null)).toBe(true);
  });

  it("light only the current phase's cell in the hub's colour while running, never the owner's, and name the owner in the tip", () => {
    render(
      <Sidebar
        {...BASE}
        profiles={[...BASE.profiles, { name: "lingo", model: "a/b", accent: "#f36a8a", shape: "heart" }]}
        workgroups={[{ profile: "alpi", id: "crew", name: "launch-crew", phase_map: { translate: { owner: "lingo" } } }]}
        rosterState={{ profiles: {}, workgroups: { "alpi/crew": { state: "working", phase: "translate", phasesDone: 2, phasesTotal: 3 } } }}
      />,
    );
    const el = glyph("launch-crew");
    expect(el.dataset.state).toBe("running");
    expect(el.dataset.cell).toBe("right");
    const lead = el.querySelector("[data-lead]");
    expect(lead.getAttribute("fill")).toBe("var(--wg-lit)");
    expect(el.style.getPropertyValue("--wg-lit-light")).toBe(nameTone("#3899e2", palettes.light.bgPane));
    expect(lead.getAttribute("class")).toBeNull();
    expect(el.innerHTML).not.toContain("#f36a8a");
    expect(cells(el).slice(0, 2).map((c) => c.getAttribute("fill"))).toEqual(["var(--ink-3)", "var(--ink-3)"]);
    expect(document.body.innerHTML).toContain("Working · translate · @lingo");
  });

  it("count the phases in the hub's name tone on the sidebar ground, never the raw accent", async () => {
    const { readFileSync } = await import("node:fs");
    const { join } = await import("node:path");
    const { contrastRatio } = await import("../../../common/name.mjs");
    render(
      <Sidebar
        {...BASE}
        profiles={[{ ...BASE.profiles[0], accent: "#f0b447" }]}
        workgroups={[{ profile: "alpi", id: "crew", name: "launch-crew" }]}
        rosterState={{ profiles: {}, workgroups: { "alpi/crew": { state: "working", phase: "translate", phasesDone: 2, phasesTotal: 3 } } }}
      />,
    );
    const count = screen.getByLabelText("phase 2 of 3");
    const light = count.style.getPropertyValue("--name-light");
    const dark = count.style.getPropertyValue("--name-dark");
    expect(light).toBe(nameTone("#f0b447", palettes.light.bgSide));
    expect(dark).toBe(nameTone("#f0b447", palettes.dark.bgSide));
    expect(contrastRatio(light, palettes.light.bgSide)).toBeGreaterThanOrEqual(4.5);
    expect(contrastRatio(dark, palettes.dark.bgSide)).toBeGreaterThanOrEqual(4.5);
    expect(count.getAttribute("style")).not.toContain("#f0b447");
    const css = readFileSync(join(import.meta.dirname, "Sidebar.module.css"), "utf8");
    expect(css).toMatch(/\.phaseCount \{[^}]*color: var\(--name-light, var\(--ink-2\)\);/);
    expect(css).toContain(':global([data-mode="dark"]) .phaseCount { color: var(--name-dark, var(--ink-2)); }');
  });

  it("tip a blocked workgroup with the shared status line, naming the phase and who it waits on", () => {
    render(
      <Sidebar
        {...BASE}
        workgroups={[{ profile: "alpi", id: "crew", name: "launch-crew", pipeline_status: "blocked", pipeline_phase: "approval", phase_map: { approval: { owner: "@yuri" } } }]}
      />,
    );
    expect(glyph("launch-crew").dataset.state).toBe("needs");
    expect(document.body.innerHTML).toContain("Needs you · approval · @yuri");
  });

  it("tip nothing for an idle or paused workgroup", () => {
    render(<Sidebar {...BASE} workgroups={[{ profile: "alpi", id: "crew", name: "launch-crew", paused: true, pipeline_status: "blocked", pipeline_phase: "approval" }]} />);
    expect(document.body.innerHTML).not.toContain("Needs you");
  });

  it("set the name in the same row type and ink as a profile row, never the name face or the hub's tone", () => {
    render(<Sidebar {...BASE} workgroups={[{ profile: "alpi", id: "crew", name: "launch-crew" }]} />);
    const wg = screen.getByText("launch-crew");
    const profile = screen.getAllByText("alpi").find((el) => el.classList.contains("sb-name"));
    expect(wg.className).toBe(profile.className);
    expect(wg.classList.contains("ds-name")).toBe(false);
    expect(wg.getAttribute("style")).toBeNull();
    expect(profile.getAttribute("style")).toBeNull();
  });

  it("draw a run without phase counts as running, still at row size", () => {
    render(
      <Sidebar
        {...BASE}
        workgroups={[{ profile: "alpi", id: "crew", name: "launch-crew" }]}
        rosterState={{ profiles: {}, workgroups: { "alpi/crew": { state: "working", phase: "analyze" } } }}
      />,
    );
    const el = glyph("launch-crew");
    expect(el.dataset.state).toBe("running");
    expect(el.querySelector("[class]")).toBeNull();
  });

  it("draw the honeycomb dashed in grey when paused", () => {
    render(<Sidebar {...BASE} workgroups={[{ profile: "alpi", id: "crew", name: "launch-crew", paused: true }]} />);
    const el = glyph("launch-crew");
    expect(el.dataset.state).toBe("paused");
    expect(cells(el).every((c) => paint(c).getAttribute("fill") === "none" && paint(c).getAttribute("stroke-dasharray"))).toBe(true);
  });

  it("draw a paused workgroup dashed even while a run is still in flight", () => {
    render(
      <Sidebar
        {...BASE}
        workgroups={[{ profile: "alpi", id: "crew", name: "launch-crew", paused: true }]}
        rosterState={{ profiles: {}, workgroups: { "alpi/crew": { state: "working", phase: "analyze" } } }}
      />,
    );
    const el = glyph("launch-crew");
    expect(el.dataset.state).toBe("paused");
    expect(cells(el).every((c) => paint(c).getAttribute("fill") === "none")).toBe(true);
    expect(el.querySelector("[class]")).toBeNull();
  });
});
