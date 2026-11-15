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
  it("shows a loading state before tools resolve", async () => {
    h.invoke.mockImplementation(() => new Promise(() => {}));
    render(<ToolsModal open onClose={() => {}} profile="muse" connectionId="c2" />);
    expect(screen.getByRole("progressbar", { name: "Loading tools" })).toBeTruthy();
    await waitFor(() => expect(document.querySelectorAll("[role=listbox] li[role=presentation] [class*=listRow]").length).toBeGreaterThan(1));
    await waitFor(() => expect(document.querySelector("[aria-hidden=true][class*=reader]")).not.toBeNull());
    expect(document.body.textContent).not.toMatch(/Loading/);
    expect(screen.queryByText("No tools registered")).toBeNull();
  });

  it("reads each tool's first sentence under its sans name, denied as the meta, and heads the detail with the id to copy", async () => {
    h.invoke.mockImplementation(() => Promise.resolve([
      { ...TOOLS[0], description: "Targeted edit of a file. Use it for small changes." },
      TOOLS[1],
    ]));
    render(<ToolsModal open onClose={() => {}} profile="muse" connectionId="c2" />);
    const options = await screen.findAllByRole("option");
    expect(options[0].querySelector("[class*=rowTitle]").textContent).toBe("edit_file");
    expect(options[0].querySelector("[class*=rowSub]").textContent).toBe("Targeted edit of a file.");
    expect(options[0].querySelector("[class*=rowMeta]")).toBeNull();
    expect(options[1].querySelector("[class*=rowMeta]").textContent).toBe("denied");
    expect(options[1].querySelector("[class*=rowTitle]").className).toMatch(/rowOff/);
    expect(await screen.findByRole("heading", { name: "edit_file" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Copy edit_file" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Copy filesystem/edit_file" })).toBeNull();
    expect(Array.from(document.querySelectorAll("dt")).map((d) => d.textContent)).toEqual(["About", "Category"]);
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
