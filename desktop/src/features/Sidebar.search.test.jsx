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
  applyPendingUpdate: vi.fn(),
  checkForUpdates: vi.fn(),
  subscribeUpdater: vi.fn(() => () => {}),
}));

import Sidebar from "./Sidebar.jsx";

const BASE = {
  profiles: [{ name: "doc", model: "a/b" }, { name: "mind", model: "a/b" }],
  workgroups: [{ profile: "doc", id: "webfactory", name: "webfactory" }],
  view: { kind: "empty" },
  hostConnections: { active_id: "remote", connections: [] },
};

const filterInput = () => screen.getByPlaceholderText(/Filter alpis/);

describe("Sidebar filter", () => {
  it("swaps New chat for the filter input when search is open", () => {
    const { rerender } = render(<Sidebar {...BASE} onNewChat={() => {}} />);
    expect(screen.getByText("New chat")).toBeInTheDocument();

    rerender(<Sidebar {...BASE} onNewChat={() => {}} searchOpen />);
    expect(screen.queryByText("New chat")).not.toBeInTheDocument();
    expect(filterInput()).toBeInTheDocument();
  });

  it("narrows the list to matches as you type", () => {
    render(<Sidebar {...BASE} searchOpen />);
    expect(screen.getByText("doc")).toBeInTheDocument();
    expect(screen.getByText("mind")).toBeInTheDocument();

    fireEvent.change(filterInput(), { target: { value: "min" } });
    expect(screen.getByText("mind")).toBeInTheDocument();
    expect(screen.queryByText("doc")).not.toBeInTheDocument();
    expect(screen.queryByText("webfactory")).not.toBeInTheDocument();
  });

  it("shows an empty state when nothing matches", () => {
    render(<Sidebar {...BASE} searchOpen />);
    fireEvent.change(filterInput(), { target: { value: "zzz" } });
    expect(screen.getByText("No alpis or workgroups match")).toBeInTheDocument();
  });

  it("closes via the clear button", () => {
    const onCloseSearch = vi.fn();
    render(<Sidebar {...BASE} searchOpen onCloseSearch={onCloseSearch} />);
    fireEvent.click(screen.getByRole("button", { name: "Close filter" }));
    expect(onCloseSearch).toHaveBeenCalledTimes(1);
  });

  it("closes on Escape in the input", () => {
    const onCloseSearch = vi.fn();
    render(<Sidebar {...BASE} searchOpen onCloseSearch={onCloseSearch} />);
    fireEvent.keyDown(filterInput(), { key: "Escape" });
    expect(onCloseSearch).toHaveBeenCalledTimes(1);
  });

  it("shows workgroup names in plain type without a # prefix", () => {
    render(<Sidebar {...BASE} searchOpen />);
    expect(screen.getByText("webfactory")).toBeInTheDocument();
    expect(screen.queryByText("#webfactory")).not.toBeInTheDocument();
  });

  it("restores the full list when the filter closes", () => {
    const { rerender } = render(<Sidebar {...BASE} searchOpen />);
    fireEvent.change(filterInput(), { target: { value: "mind" } });
    expect(screen.queryByText("doc")).not.toBeInTheDocument();

    rerender(<Sidebar {...BASE} onNewChat={() => {}} />);
    expect(screen.getByText("doc")).toBeInTheDocument();
    expect(screen.getByText("mind")).toBeInTheDocument();
    expect(screen.getByText("webfactory")).toBeInTheDocument();
  });
});
