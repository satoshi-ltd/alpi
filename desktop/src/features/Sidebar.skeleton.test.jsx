import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

globalThis.ResizeObserver ??= class { observe() {} unobserve() {} disconnect() {} };
window.matchMedia ??= () => ({
  matches: false,
  addEventListener() {},
  removeEventListener() {},
  addListener() {},
  removeListener() {},
});

vi.mock("../lib/updater.js", () => ({
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

const loadingRows = () =>
  screen.queryByRole("status", { name: "Loading profiles" });

describe("Sidebar connection-switch skeleton", () => {
  it("stays silent at first, then shows loading rows for a slow empty-cache sync", async () => {
    render(<Sidebar {...BASE} connectionSyncing />);
    expect(loadingRows()).not.toBeInTheDocument();
    await waitFor(() => expect(loadingRows()).toBeInTheDocument());
  });

  it("renders no loading rows once profiles are present", async () => {
    render(
      <Sidebar
        {...BASE}
        profiles={[{ name: "doc", model: "a/b" }]}
        connectionSyncing
      />,
    );
    await new Promise((r) => setTimeout(r, 400));
    expect(loadingRows()).not.toBeInTheDocument();
  });

  it("renders no loading rows when idle", async () => {
    render(<Sidebar {...BASE} />);
    await new Promise((r) => setTimeout(r, 400));
    expect(loadingRows()).not.toBeInTheDocument();
  });
});

describe("Sidebar notifications bell (member gating)", () => {
  const bell = () => screen.queryByRole("button", { name: /Notifications/ });

  it("shows the bell when notifications are allowed", () => {
    render(<Sidebar {...BASE} onOpenNotifications={() => {}} />);
    expect(bell()).toBeInTheDocument();
  });

  it("hides the bell when notifications are gated off (member connection)", () => {
    render(<Sidebar {...BASE} onOpenNotifications={null} />);
    expect(bell()).not.toBeInTheDocument();
  });
});
