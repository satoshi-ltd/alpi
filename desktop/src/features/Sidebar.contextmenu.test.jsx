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
  view: { kind: "landing" },
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

describe("Sidebar profile context menu", () => {
  const ALPI = { name: "default", is_default: true, model: "a/b", latest_session: { updated_at: TS } };

  it("puts New session with its ⌘N hint at the top, above Pin, Pause and Open settings", () => {
    const onNewSessionWith = vi.fn();
    render(
      <Sidebar
        {...BASE}
        onNewSessionWith={onNewSessionWith}
        onOpenSettingsTarget={() => {}}
        onTogglePauseProfile={() => {}}
      />,
    );
    fireEvent.contextMenu(screen.getByText("doc").closest("button"));
    const items = screen.getAllByRole("menuitem");
    expect(items[0].textContent).toContain("New session");
    expect(items[0].textContent).toContain("⌘N");
    expect(items.map((it) => it.textContent)).toEqual([
      expect.stringContaining("New session"),
      expect.stringContaining("Pin to top"),
      expect.stringContaining("Pause profile"),
      expect.stringContaining("Open settings"),
      expect.stringContaining("Delete profile…"),
    ]);
    fireEvent.click(items[0]);
    expect(onNewSessionWith).toHaveBeenCalledWith(BASE.profiles[0]);
  });

  it("offers New session on alpi's row too", () => {
    const onNewSessionWith = vi.fn();
    render(<Sidebar {...BASE} profiles={[ALPI, ...BASE.profiles]} onNewSessionWith={onNewSessionWith} onOpenSettingsTarget={() => {}} />);
    fireEvent.contextMenu(screen.getByText("alpi").closest("button"));
    fireEvent.click(screen.getAllByRole("menuitem")[0]);
    expect(onNewSessionWith).toHaveBeenCalledWith(ALPI);
  });

  it("still offers New session to a member device without settings", () => {
    const onNewSessionWith = vi.fn();
    render(<Sidebar {...BASE} onNewSessionWith={onNewSessionWith} />);
    fireEvent.contextMenu(screen.getByText("doc").closest("button"));
    expect(screen.getAllByRole("menuitem").map((it) => it.textContent)).toEqual([expect.stringContaining("New session")]);
  });

  it("never offers New session on a workgroup row", () => {
    render(<Sidebar {...BASE} onNewSessionWith={() => {}} onOpenSettingsTarget={() => {}} />);
    fireEvent.contextMenu(screen.getByText("roma").closest("button"));
    expect(screen.queryByText("New session")).not.toBeInTheDocument();
  });
});
