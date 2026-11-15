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
import { trackedCount } from "../lib/gaze.js";

const BASE = {
  workgroups: [],
  view: { kind: "landing" },
  hostConnections: { active_id: "remote", connections: [] },
};

const glyph = (name) => screen.getByText(name).closest("button").firstElementChild;

describe("Sidebar profile marks", () => {
  it("draws the profile's mark in its colour and the round shape for a profile without a fold", () => {
    render(
      <Sidebar
        {...BASE}
        profiles={[
          { name: "doc", model: "a/b", accent: "#3899e2", shape: "bell" },
          { name: "mind", model: "a/b", accent: "#3899e2" },
        ]}
      />,
    );
    const doc = glyph("doc");
    expect(doc.dataset.shape).toBe("bell");
    expect(doc.dataset.mark).toBe("bell");
    expect(doc.querySelector("path[data-body]").getAttribute("fill")).toBe("#3899e2");
    expect(glyph("mind").dataset.shape).toBe("round");
    expect(glyph("mind").dataset.mark).toBe("round");
    expect(doc.getAttribute("aria-hidden")).toBe("true");
  });

  it("draws the default profile as Twin in the brand ink, on its 48 px tile", () => {
    render(<Sidebar {...BASE} profiles={[{ name: "default", model: "a/b", accent: "#3899e2", shape: "twin", is_default: true }]} />);
    const twin = screen.getByText("alpi").closest("button").querySelector("[data-shape]");
    expect(twin.dataset.mark).toBe("alpi-twin");
    expect(twin.style.width).toBe("48px");
    expect(twin.querySelector("path[data-body]").getAttribute("fill")).toBe("var(--accent)");
  });

  it("never lets a tile or a row follow the pointer, even the selected one", () => {
    const add = vi.spyOn(window, "addEventListener");
    const { container } = render(
      <Sidebar
        {...BASE}
        view={{ kind: "profile", profile: "default", sessionId: null }}
        pinned={{ profiles: ["doc"], workgroups: [] }}
        profiles={[
          { name: "default", model: "a/b", shape: "twin", is_default: true },
          { name: "doc", model: "a/b", accent: "#3899e2", shape: "bell" },
          { name: "mind", model: "a/b", accent: "#3899e2", shape: "drop" },
        ]}
      />,
    );
    expect(container.querySelectorAll("[data-shape]").length).toBeGreaterThanOrEqual(3);
    expect(container.querySelector("[data-watch]")).toBeNull();
    expect(trackedCount()).toBe(0);
    expect(add.mock.calls.filter(([type]) => type === "mousemove")).toHaveLength(0);
    add.mockRestore();
  });

  it("keeps the slot at row size for every mark", () => {
    render(
      <Sidebar
        {...BASE}
        profiles={[
          { name: "doc", model: "a/b", accent: "#3899e2", shape: "heart" },
          { name: "mind", model: "a/b", accent: "#3899e2" },
        ]}
      />,
    );
    expect(glyph("doc").style.width).toBe("24px");
    expect(glyph("mind").style.width).toBe("24px");
  });

  it("draws a profile that still needs a model in its needs state, filled, never dashed", () => {
    render(<Sidebar {...BASE} profiles={[{ name: "doc", accent: "#3899e2", shape: "pill" }]} />);
    const mark = screen.getByText("doc").closest("button").querySelector("[data-shape]");
    expect(mark.dataset.state).toBe("needs");
    expect(mark.querySelector("path[stroke-dasharray]")).toBeNull();
    expect(mark.querySelector("path[data-body]").getAttribute("fill")).toBe("#3899e2");
  });
});

describe("Sidebar roster state", () => {
  const roster = [
    { name: "doc", model: "a/b", accent: "#3899e2" },
    { name: "napper", model: "a/b", accent: "#3899e2", paused: true },
    { name: "fresh", accent: "#3899e2" },
  ];

  it("keeps the marks filled for a plain disconnect and draws only the paused profile dashed", () => {
    render(<Sidebar {...BASE} profiles={roster} daemonOffline />);
    expect(glyph("doc").dataset.state).toBe("idle");
    expect(glyph("doc").querySelector("path[data-body]")).not.toBeNull();
    expect(glyph("napper").dataset.state).toBe("paused");
    expect(glyph("napper").querySelector("path[stroke-dasharray]")).not.toBeNull();
  });

  it("says paused and needs provider in words instead of fading the row", () => {
    render(<Sidebar {...BASE} profiles={roster} />);
    expect(screen.getByText("napper").closest("button")).toHaveTextContent("paused");
    expect(screen.getByText("fresh").closest("button")).toHaveTextContent("needs provider");
    expect(screen.getByText("doc").closest("button")).not.toHaveTextContent("paused");
    expect(screen.getByText("napper").closest("button").style.opacity).toBe("");
  });

  it("marks the chosen row with aria-current and the neutral fill, never the profile's colour", () => {
    render(
      <Sidebar
        {...BASE}
        view={{ kind: "profile", profile: "doc" }}
        profiles={[
          { name: "doc", model: "a/b", accent: "#3899e2", shape: "bell" },
          { name: "abby", model: "a/b", accent: "#e8708a" },
        ]}
      />,
    );
    const selected = screen.getByText("doc").closest("button");
    expect(selected.hasAttribute("data-sel")).toBe(true);
    expect(selected.getAttribute("aria-current")).toBe("page");
    expect(selected.style.getPropertyValue("--row-accent")).toBe("");
    expect(selected.style.background).toBe("");
    const other = screen.getByText("abby").closest("button");
    expect(other.hasAttribute("aria-current")).toBe(false);
    expect(other.hasAttribute("data-sel")).toBe(false);
  });
});
