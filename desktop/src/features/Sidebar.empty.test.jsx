import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

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
  profiles: [],
  workgroups: [],
  view: { kind: "landing" },
  hostConnections: { active_id: "remote", connections: [] },
};

describe("Sidebar with nothing to list", () => {
  it("says so and offers the first profile once the connection has settled", () => {
    const onNewProfile = vi.fn();
    render(<Sidebar {...BASE} onNewProfile={onNewProfile} />);
    expect(screen.getByText(/No profiles yet/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "New profile" }));
    expect(onNewProfile).toHaveBeenCalledTimes(1);
  });

  it("stays quiet until the roster answers or while offline, when an empty roster means nothing yet", () => {
    const { rerender } = render(<Sidebar {...BASE} connectionSyncing rosterAnswered={false} />);
    expect(screen.queryByText(/No profiles yet/)).toBeNull();
    rerender(<Sidebar {...BASE} rosterAnswered={false} />);
    expect(screen.queryByText(/No profiles yet/)).toBeNull();
    rerender(<Sidebar {...BASE} daemonOffline />);
    expect(screen.queryByText(/No profiles yet/)).toBeNull();
  });

  it("keeps saying so through a later reload of an answered roster", () => {
    render(<Sidebar {...BASE} connectionSyncing rosterAnswered />);
    expect(screen.getByText(/No profiles yet/)).toBeInTheDocument();
  });
});

describe("Sidebar while the daemon is away", () => {
  it("keeps the roster and draws every profile and workgroup unfolded", () => {
    const profiles = [{ name: "default", is_default: true, model: "m" }, { name: "doc", fold: "heart", accent: "#f36a8a", model: "m" }];
    const workgroups = [{ profile: "doc", id: "crew", name: "crew" }];
    const { container, rerender } = render(<Sidebar {...BASE} profiles={profiles} workgroups={workgroups} rosterAnswered daemonOffline />);
    const folds = [...container.querySelectorAll("[data-fold]")];
    expect(folds.length).toBeGreaterThanOrEqual(3);
    expect(folds.every((f) => f.hasAttribute("data-unfolded"))).toBe(true);
    rerender(<Sidebar {...BASE} profiles={profiles} workgroups={workgroups} rosterAnswered />);
    expect(container.querySelector("[data-unfolded]")).toBeNull();
  });
});
