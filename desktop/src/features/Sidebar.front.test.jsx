import { afterEach, describe, it, expect, vi } from "vitest";
import { cleanup, render, screen, fireEvent, within } from "@testing-library/react";

const NAV_HEIGHT = vi.hoisted(() => ({ value: 0 }));

globalThis.ResizeObserver = class {
  constructor(cb) {
    this.cb = cb;
  }
  observe() {
    this.cb([{ contentRect: { height: NAV_HEIGHT.value } }]);
  }
  unobserve() {}
  disconnect() {}
};
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

afterEach(() => {
  cleanup();
  NAV_HEIGHT.value = 0;
});

const TS = Math.floor(Date.now() / 1000);
const ALPI = { name: "default", is_default: true, model: "a/b", latest_session: { updated_at: TS - 86400 * 9 } };
const ROSTER = [
  { name: "doc", model: "a/b", latest_session: { updated_at: TS - 60 } },
  ALPI,
  { name: "clonara", model: "a/b", latest_session: { updated_at: TS - 7200 } },
];

const BASE = {
  workgroups: [],
  view: { kind: "landing" },
  hostConnections: { active_id: "remote", connections: [] },
};

const rowNames = () =>
  [...document.querySelectorAll("nav .ds-sb-row .sb-name")].map((el) => el.textContent);
const navText = () => document.querySelector("nav").textContent;
const rowOf = (label) => screen.getByText(label).closest("button");

describe("Sidebar front door", () => {
  it("draws the default profile as the unlabelled first row above Pinned", () => {
    render(<Sidebar {...BASE} profiles={ROSTER} pinned={{ profiles: ["clonara"], workgroups: [] }} />);
    expect(rowNames()).toEqual(["alpi", "clonara", "doc"]);
    expect(navText().indexOf("alpi")).toBeLessThan(navText().indexOf("Pinned"));
    expect(rowOf("alpi").closest("[class*='section']").textContent).toBe(rowOf("alpi").textContent);
  });

  it("stays first and dimmed when paused or without a provider", () => {
    const paused = { ...ALPI, paused: true };
    const { rerender } = render(<Sidebar {...BASE} profiles={[ROSTER[0], paused, ROSTER[2]]} />);
    expect(rowNames()[0]).toBe("alpi");
    expect(rowOf("alpi").getAttribute("data-state")).toBe("paused");

    rerender(<Sidebar {...BASE} profiles={[ROSTER[0], { ...ALPI, model: null }, ROSTER[2]]} />);
    expect(rowNames()[0]).toBe("alpi");
    expect(rowOf("alpi").getAttribute("data-state")).toBe("needs-provider");
  });

  it("is never pinnable: no Pin in its menu and no hover pin", () => {
    render(<Sidebar {...BASE} profiles={ROSTER} onOpenSettingsTarget={() => {}} onTogglePin={() => {}} />);
    const wrap = rowOf("alpi").parentElement;
    expect(within(wrap).queryByRole("button", { name: /pin/i })).toBeNull();
    fireEvent.contextMenu(rowOf("alpi"));
    expect(screen.queryByText("Pin to top")).toBeNull();
    expect(screen.queryByText("Delete profile…")).toBeNull();
    expect(screen.getByText("Open settings")).toBeInTheDocument();
  });

  it("still offers Pin on every other profile", () => {
    render(<Sidebar {...BASE} profiles={ROSTER} onOpenSettingsTarget={() => {}} onTogglePin={() => {}} />);
    fireEvent.contextMenu(rowOf("doc"));
    expect(screen.getByText("Pin to top")).toBeInTheDocument();
  });

  it("ignores a stale default pin", () => {
    render(<Sidebar {...BASE} profiles={ROSTER} pinned={{ profiles: ["default"], workgroups: [] }} />);
    expect(rowNames()).toEqual(["alpi", "doc", "clonara"]);
    expect(screen.queryByText("Pinned")).toBeNull();
  });

  it("never falls behind Show N more", () => {
    NAV_HEIGHT.value = 120;
    const many = ["a", "b", "c", "d", "e", "f"].map((name, i) => ({
      name,
      model: "a/b",
      latest_session: { updated_at: TS - i * 60 },
    }));
    render(<Sidebar {...BASE} profiles={[...many, { ...ALPI, paused: true }]} />);
    expect(screen.getByText(/Show \d+ more/)).toBeInTheDocument();
    expect(rowNames()[0]).toBe("alpi");
  });

  it("shows under a filter only when it matches its name or its label", () => {
    render(<Sidebar {...BASE} profiles={ROSTER} searchOpen />);
    const input = screen.getByPlaceholderText(/Filter profiles/);
    fireEvent.change(input, { target: { value: "al" } });
    expect(rowNames()).toEqual(["alpi"]);
    fireEvent.change(input, { target: { value: "defa" } });
    expect(rowNames()).toEqual(["alpi"]);
    fireEvent.change(input, { target: { value: "doc" } });
    expect(rowNames()).toEqual(["doc"]);
    expect(screen.queryByText("No profiles or workgroups match")).toBeNull();
  });

  it("is absent on a connection that does not serve the default profile", () => {
    render(<Sidebar {...BASE} profiles={[ROSTER[0], ROSTER[2]]} />);
    expect(rowNames()).toEqual(["doc", "clonara"]);
    expect(screen.getByText("Profiles")).toBeInTheDocument();
  });

  it("keeps the Profiles heading and its + when the default is the only profile", () => {
    render(<Sidebar {...BASE} profiles={[ALPI]} onNewProfile={() => {}} />);
    expect(rowNames()).toEqual(["alpi"]);
    expect(screen.getByRole("button", { name: "New profile" })).toBeInTheDocument();
  });
});
