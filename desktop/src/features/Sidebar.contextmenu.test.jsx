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

const TS = Math.floor(Date.now() / 1000) - 300;

const BASE = {
  profiles: [{ name: "doc", model: "a/b", latest_session: { updated_at: TS } }],
  workgroups: [{ profile: "doc", id: "roma", name: "roma", mtime: TS }],
  view: { kind: "empty" },
  hostConnections: { active_id: "remote", connections: [] },
};

describe("Sidebar workgroup context menu", () => {
  it("offers only actions that do something: settings and delete, no archive", () => {
    render(<Sidebar {...BASE} onOpenSettingsTarget={() => {}} />);
    fireEvent.contextMenu(screen.getByText("roma").closest("button"));
    expect(screen.getByRole("menu")).toBeInTheDocument();
    expect(screen.queryByText("Archive workgroup")).not.toBeInTheDocument();
    expect(screen.getByText("Delete workgroup…")).toBeInTheDocument();
  });
});
