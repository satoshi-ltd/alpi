import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

globalThis.ResizeObserver ??= class { observe() {} unobserve() {} disconnect() {} };
globalThis.Element.prototype.scrollTo ??= () => {};

const h = vi.hoisted(() => ({ invoke: vi.fn() }));
vi.mock("@tauri-apps/api/core", () => ({ invoke: h.invoke }));

import ToolsModal from "./ToolsModal.jsx";

const TOOLS = [
  { name: "edit_file", category: "Filesystem", description: "Targeted edit", tag: 3, parameters: { properties: {}, required: [] } },
  { name: "browser", category: "Web", description: "Headless browser", tag: 0, denied: true, parameters: {} },
];

beforeEach(() => {
  h.invoke.mockReset();
  h.invoke.mockImplementation((cmd, args) =>
    cmd === "profile_tools" && args.connectionId === "c2" ? Promise.resolve(TOOLS) : new Promise(() => {}),
  );
});

describe("ToolsModal (mounted)", () => {
  it("shows a loading state before tools resolve", () => {
    h.invoke.mockImplementation(() => new Promise(() => {}));
    render(<ToolsModal open onClose={() => {}} profile="muse" connectionId="c2" />);
    expect(screen.getByRole("progressbar", { name: "Loading tools" })).toBeTruthy();
    expect(screen.getAllByText("Loading tools…").length).toBeGreaterThan(0);
    expect(screen.queryByText("No tools registered")).toBeNull();
  });

  it("loads tools pinned to the active connection", async () => {
    render(<ToolsModal open onClose={() => {}} profile="muse" connectionId="c2" />);
    await waitFor(() => expect(h.invoke).toHaveBeenCalledWith("profile_tools", { profile: "muse", connectionId: "c2" }));
    expect((await screen.findAllByText("edit_file")).length).toBeGreaterThan(0);
  });

  it("drops the previous daemon's tools when the connection changes", async () => {
    const Harness = ({ cid }) => (
      <ToolsModal key={`${cid}:muse`} open onClose={() => {}} profile="muse" connectionId={cid} />
    );
    const { rerender } = render(<Harness cid="c2" />);
    expect((await screen.findAllByText("edit_file")).length).toBeGreaterThan(0);
    rerender(<Harness cid="c9" />);
    await waitFor(() => expect(screen.queryByText("edit_file")).toBeNull());
  });
});
