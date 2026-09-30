import { describe, it, expect, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

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

const TS = Math.floor(Date.now() / 1000) - 300;

const BASE = {
  profiles: [
    { name: "alpi", model: "a/b", latest_session: { updated_at: TS } },
    { name: "builder", model: "a/b", latest_session: { updated_at: TS } },
    { name: "doc", model: "a/b", latest_session: { updated_at: TS } },
    { name: "abby", model: "a/b", latest_session: { updated_at: TS } },
  ],
  workgroups: [{ profile: "alpi", id: "crew", name: "launch-crew", mtime: TS }],
  view: { kind: "empty" },
  hostConnections: { active_id: "local", connections: [] },
};

const rosterState = {
  profiles: { alpi: "working", builder: "needs-you", doc: "failed" },
  workgroups: { "alpi/crew": { state: "working", phasesDone: 2, phasesTotal: 4, phase: "analyze" } },
};

describe("Sidebar agent states", () => {
  it("shows needs you, failed and working chips and leaves idle rows alone", () => {
    render(<Sidebar {...BASE} rosterState={rosterState} />);
    expect(screen.getByRole("button", { name: "builder, needs you" })).toHaveTextContent("needs you");
    expect(screen.getByRole("button", { name: "doc, failed" })).toHaveTextContent("failed");
    const alpi = screen.getByRole("button", { name: "alpi, working" });
    expect(alpi.querySelector(".pulse-glyph")).not.toBeNull();
    const abby = screen.getByText("abby").closest("button");
    expect(abby.querySelector("[data-state]")).toBeNull();
    expect(abby.querySelector(".sb-ts")).not.toBeNull();
  });

  it("shows phases done over total on a running workgroup", () => {
    render(<Sidebar {...BASE} rosterState={rosterState} />);
    expect(screen.getByLabelText("phase 2 of 4")).toHaveTextContent("2/4");
  });

  it("renders the old timestamps when the daemon has no activity verb", () => {
    render(<Sidebar {...BASE} rosterState={null} />);
    expect(screen.queryByText("needs you")).toBeNull();
    expect(screen.queryByText("2/4")).toBeNull();
  });

  it("offers the Activity button with a needs-you badge only when wired", () => {
    const onOpenActivity = vi.fn();
    const { rerender } = render(<Sidebar {...BASE} onOpenActivity={onOpenActivity} activityNeedsYou={2} />);
    fireEvent.click(screen.getByRole("button", { name: "Activity · 2 need you · ⌘J" }));
    expect(onOpenActivity).toHaveBeenCalledTimes(1);
    rerender(<Sidebar {...BASE} onOpenActivity={null} />);
    expect(screen.queryByRole("button", { name: /^Activity/ })).toBeNull();
  });
});
