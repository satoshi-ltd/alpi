import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

globalThis.ResizeObserver ??= class { observe() {} unobserve() {} disconnect() {} };
globalThis.Element.prototype.scrollTo ??= () => {};

const h = vi.hoisted(() => ({ invoke: vi.fn() }));
vi.mock("@tauri-apps/api/core", () => ({ invoke: h.invoke }));

import MemoryModal from "./MemoryModal.jsx";

const MEM = { "AGENT.md": "I am doc", "MEMORY.md": "learned things", "USER.md": "about you" };

beforeEach(() => {
  h.invoke.mockReset();
  h.invoke.mockImplementation((cmd, args) =>
    cmd === "profile_memory" && args.connectionId === "c2" ? Promise.resolve(MEM) : new Promise(() => {}),
  );
});

describe("MemoryModal (mounted)", () => {
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
});
