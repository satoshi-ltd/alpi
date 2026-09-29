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
  view: { kind: "empty" },
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

  it("stays quiet while syncing or offline, when an empty roster means nothing yet", () => {
    const { rerender } = render(<Sidebar {...BASE} connectionSyncing />);
    expect(screen.queryByText(/No profiles yet/)).toBeNull();
    rerender(<Sidebar {...BASE} daemonOffline />);
    expect(screen.queryByText(/No profiles yet/)).toBeNull();
  });
});
