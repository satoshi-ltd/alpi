import { act, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { BUSY_DELAY_MS, BUSY_MIN_MS } from "../../../common/busy.mjs";

import Settings, { canOpenConnections } from "./Settings.jsx";

afterEach(() => vi.useRealTimers());

describe("Settings", () => {
  it("waits with the ink mark and its words while the selected target fetches remote summaries", async () => {
    render(
      <Settings
        profiles={[]}
        workgroups={[]}
        target={{ kind: "profile", id: "doc" }}
        activeConnection={{ id: "remote", accent: "#57a" }}
        connectionSyncing
      />,
    );

    const busy = await screen.findByRole("status", { name: "Fetching latest settings" });
    expect(busy).toHaveTextContent("Fetching latest settings");
    expect(busy.querySelector("[data-fold]").dataset.fold).toBe("alpaca");
    expect(busy.innerHTML).not.toContain("#57a");
    expect(screen.queryByRole("progressbar")).toBeNull();
  });

  it("keeps the mark the minimum time when the sync ends just after it appeared", () => {
    vi.useFakeTimers();
    const view = (syncing) => (
      <Settings profiles={[]} workgroups={[]} target={{ kind: "profile", id: "doc" }} activeConnection={{ id: "remote" }} connectionSyncing={syncing} />
    );
    const { rerender } = render(view(true));
    expect(screen.queryByRole("status")).toBeNull();
    expect(screen.queryByText("No selection")).toBeNull();
    act(() => vi.advanceTimersByTime(BUSY_DELAY_MS));
    expect(screen.getByRole("status", { name: "Fetching latest settings" })).toBeInTheDocument();
    act(() => vi.advanceTimersByTime(350 - BUSY_DELAY_MS));
    rerender(view(false));
    expect(screen.getByRole("status", { name: "Fetching latest settings" })).toBeInTheDocument();
    act(() => vi.advanceTimersByTime(BUSY_DELAY_MS + BUSY_MIN_MS - 350 - 1));
    expect(screen.getByRole("status", { name: "Fetching latest settings" })).toBeInTheDocument();
    act(() => vi.advanceTimersByTime(1));
    expect(screen.queryByRole("status")).toBeNull();
    expect(screen.getByText("No selection")).toBeInTheDocument();
  });

  it("drops the held mark at once when another profile is selected", () => {
    vi.useFakeTimers();
    const view = (id, syncing) => (
      <Settings profiles={[{ name: "atlas" }]} workgroups={[]} target={{ kind: "profile", id }} activeConnection={{ id: "remote" }} connectionSyncing={syncing} />
    );
    const { rerender } = render(view("doc", true));
    act(() => vi.advanceTimersByTime(BUSY_DELAY_MS));
    expect(screen.getByRole("status", { name: "Fetching latest settings" })).toBeInTheDocument();
    rerender(view("atlas", false));
    expect(screen.queryByRole("status", { name: "Fetching latest settings" })).toBeNull();
    expect(screen.getAllByText("atlas").length).toBeGreaterThan(0);
  });

  it("never draws the mark over the connections page", () => {
    vi.useFakeTimers();
    const view = (target) => (
      <Settings profiles={[]} workgroups={[]} target={target} activeConnection={{ id: "remote", kind: "remote", role: "member" }} connectionSyncing />
    );
    const { rerender } = render(view({ kind: "profile", id: "doc" }));
    act(() => vi.advanceTimersByTime(BUSY_DELAY_MS));
    expect(screen.getByRole("status", { name: "Fetching latest settings" })).toBeInTheDocument();
    rerender(view({ kind: "connections", id: "x" }));
    expect(screen.queryByRole("status", { name: "Fetching latest settings" })).toBeNull();
    expect(screen.getByText("Admin access required")).toBeInTheDocument();
  });

  it("does not open connection administration for a member credential", () => {
    render(
      <Settings
        profiles={[]}
        target={{ kind: "connections" }}
        activeConnection={{ id: "remote", kind: "remote", role: "member" }}
      />,
    );

    expect(screen.getByText("Admin access required")).toBeInTheDocument();
  });

  it("offers connection administration only from the default profile", () => {
    const admin = { kind: "remote", role: "admin" };

    expect(canOpenConnections(admin, "default")).toBe(true);
    expect(canOpenConnections(admin, "atlas")).toBe(false);
    expect(canOpenConnections({ kind: "remote", role: "member" }, "default")).toBe(false);
  });
});
