import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const invoke = vi.hoisted(() => vi.fn());
vi.mock("@tauri-apps/api/core", () => ({ invoke }));
vi.mock("../lib/daemon-bus.js", () => ({ subscribeDaemonEvent: () => () => {} }));
vi.mock("../primitives/Notification.jsx", () => ({ useNotify: () => () => {} }));

import ProfilePanels from "./ProfilePanels.jsx";

globalThis.ResizeObserver ??= class { observe() {} unobserve() {} disconnect() {} };

const OWNER = { name: "lingua", fold: "plane", accent: "#bb2299" };

beforeEach(() => {
  invoke.mockReset();
  invoke.mockImplementation(async (cmd) => {
    if (cmd === "profile_memory") return { "AGENT.md": "who I am", "MEMORY.md": "", "USER.md": "" };
    if (cmd === "memory_read") return { text: "who I am", rev: "r1" };
    return [];
  });
});

function Harness({ initial = "schedule", onClose = () => {} }) {
  const [section, setSection] = useState(initial);
  return <ProfilePanels section={section} onSection={setSection} onClose={onClose} owner={OWNER} profile="lingua" connectionId={null} canEdit />;
}

describe("ProfilePanels", () => {
  it("swaps the panel inside one window instead of closing and reopening it", async () => {
    render(<Harness />);
    const dialog = await screen.findByRole("dialog");
    await waitFor(() => expect(screen.getByRole("tab", { name: /Schedules/ }).getAttribute("aria-selected")).toBe("true"));
    fireEvent.click(screen.getByRole("tab", { name: "Skills" }));
    await waitFor(() => expect(screen.getByRole("tab", { name: /Skills/ }).getAttribute("aria-selected")).toBe("true"));
    expect(screen.getByRole("dialog")).toBe(dialog);
    expect(screen.getAllByRole("dialog")).toHaveLength(1);
    fireEvent.click(screen.getByRole("tab", { name: "Tools" }));
    await waitFor(() => expect(screen.getByLabelText("Search tools")).toBeTruthy());
    expect(screen.getByRole("dialog")).toBe(dialog);
    fireEvent.click(screen.getByRole("tab", { name: "Memories" }));
    await waitFor(() => expect(screen.getByLabelText("Search memory")).toBeTruthy());
    expect(screen.getByRole("dialog")).toBe(dialog);
  });

  it("asks before leaving a dirty memory edit, by tab, close button or Escape", async () => {
    const onClose = vi.fn();
    render(<Harness initial="memory" onClose={onClose} />);
    await waitFor(() => expect(screen.getByRole("button", { name: "Edit" })).toBeTruthy());
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Edit" })); });
    fireEvent.change(await screen.findByLabelText("Edit AGENT.md"), { target: { value: "draft" } });

    const confirm = vi.spyOn(globalThis, "confirm").mockReturnValue(false);
    fireEvent.click(screen.getByRole("tab", { name: "Skills" }));
    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    fireEvent.keyDown(document, { key: "Escape" });
    expect(confirm).toHaveBeenCalledTimes(3);
    expect(onClose).not.toHaveBeenCalled();
    expect(screen.getByLabelText("Edit AGENT.md")).toBeTruthy();

    confirm.mockReturnValue(true);
    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(onClose).toHaveBeenCalledTimes(1);
    confirm.mockRestore();
  });

  it("lets the app ask the open panel before it switches from outside the window", async () => {
    const guardRef = { current: null };
    render(<ProfilePanels section="memory" onSection={() => {}} onClose={() => {}} owner={OWNER} profile="lingua" connectionId={null} canEdit guardRef={guardRef} />);
    await waitFor(() => expect(screen.getByRole("button", { name: "Edit" })).toBeTruthy());
    expect(guardRef.current()).toBe(true);
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Edit" })); });
    fireEvent.change(await screen.findByLabelText("Edit AGENT.md"), { target: { value: "draft" } });
    const confirm = vi.spyOn(globalThis, "confirm").mockReturnValue(false);
    expect(guardRef.current()).toBe(false);
    confirm.mockReturnValue(true);
    expect(guardRef.current()).toBe(true);
    confirm.mockRestore();
  });
});
