import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

globalThis.ResizeObserver ??= class { observe() {} unobserve() {} disconnect() {} };
globalThis.Element.prototype.scrollTo ??= () => {};

const h = vi.hoisted(() => ({ invoke: vi.fn() }));
vi.mock("@tauri-apps/api/core", () => ({ invoke: h.invoke }));

import MemoryModal from "./MemoryModal.jsx";

const MEM = { "AGENT.md": "# Title\n\n**bold** note", "MEMORY.md": "learned things", "USER.md": "about you" };

beforeEach(() => {
  h.invoke.mockReset();
  h.invoke.mockImplementation((cmd, args) =>
    cmd === "profile_memory" && args.connectionId === "c2" ? Promise.resolve(MEM) : new Promise(() => {}),
  );
});

describe("MemoryModal (mounted)", () => {
  it("shows a loading state before memory files resolve", () => {
    h.invoke.mockImplementation(() => new Promise(() => {}));
    render(<MemoryModal open onClose={() => {}} profile="muse" connectionId="c2" />);
    expect(screen.getByRole("progressbar", { name: "Loading memory" })).toBeTruthy();
    expect(screen.getAllByText("Loading memory…").length).toBeGreaterThan(0);
    expect(screen.queryByText("No memory files")).toBeNull();
  });

  it("loads memory files pinned to the active connection", async () => {
    render(<MemoryModal open onClose={() => {}} profile="muse" connectionId="c2" />);
    await waitFor(() => expect(h.invoke).toHaveBeenCalledWith("profile_memory", { profile: "muse", connectionId: "c2" }));
    expect((await screen.findAllByText("AGENT.md")).length).toBeGreaterThan(0);
  });

  it("drops the previous daemon's files when the connection changes", async () => {
    const Harness = ({ cid }) => (
      <MemoryModal key={`${cid}:muse`} open onClose={() => {}} profile="muse" connectionId={cid} />
    );
    const { rerender } = render(<Harness cid="c2" />);
    expect((await screen.findAllByText("AGENT.md")).length).toBeGreaterThan(0);
    rerender(<Harness cid="c9" />);
    await waitFor(() => expect(screen.queryByText("AGENT.md")).toBeNull());
  });

  it("renders the active file's content as formatted markdown, not raw source", async () => {
    render(<MemoryModal open onClose={() => {}} profile="muse" connectionId="c2" />);
    await waitFor(() => expect(document.querySelector(".alpi-md")).not.toBeNull());
    const md = document.querySelector(".alpi-md");
    expect(md.querySelector("strong")?.textContent).toBe("bold");
    expect(md.textContent).not.toContain("**");
  });
});
