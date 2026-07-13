import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor, fireEvent, act } from "@testing-library/react";

vi.mock("@tauri-apps/api/core", () => ({ invoke: vi.fn() }));
vi.mock("../primitives/Notification.jsx", () => ({ useNotify: () => () => {} }));

import { invoke } from "@tauri-apps/api/core";
import MemoryModal, { humanBytes, stripMemoryDelimiters, matchesFile } from "./MemoryModal.jsx";

globalThis.ResizeObserver ??= class { observe() {} unobserve() {} disconnect() {} };

describe("humanBytes", () => {
  it("formats by magnitude", () => {
    expect(humanBytes(0)).toBe("0b");
    expect(humanBytes(891)).toBe("891b");
    expect(humanBytes(1536)).toBe("1.5kb");
    expect(humanBytes(2 * 1024 * 1024)).toBe("2.0mb");
  });
});

describe("stripMemoryDelimiters", () => {
  it("drops the § entry delimiter and collapses blank runs", () => {
    expect(stripMemoryDelimiters("a\n§\nb")).toBe("a\n\nb");
    expect(stripMemoryDelimiters("a\n\n\n\nb")).toBe("a\n\nb");
  });
});

describe("matchesFile", () => {
  const file = { name: "AGENT.md", label: "Things alpi is", content: "ancestral worldview" };
  it("matches name, label, content; empty query passes", () => {
    expect(matchesFile(file, "")).toBe(true);
    expect(matchesFile(file, "agent")).toBe(true);
    expect(matchesFile(file, "things")).toBe(true);
    expect(matchesFile(file, "worldview")).toBe(true);
    expect(matchesFile(file, "nope")).toBe(false);
  });
});

describe("MemoryModal budget %", () => {
  it("renders each file's percentage from memory_usage", async () => {
    invoke.mockImplementation((cmd) => {
      if (cmd === "profile_memory") {
        return Promise.resolve({ "AGENT.md": "hi", "MEMORY.md": "", "USER.md": "" });
      }
      if (cmd === "memory_usage") {
        return Promise.resolve({
          "AGENT.md": { used: 4000, limit: 8000, pct: 50 },
          "MEMORY.md": { used: 0, limit: 5000, pct: 0 },
          "USER.md": { used: 0, limit: 3000, pct: 0 },
        });
      }
      return Promise.resolve(null);
    });
    render(<MemoryModal open profile="doc" connectionId={null} canEdit />);
    await waitFor(() => expect(screen.getByText("50%")).toBeTruthy());
  });

  it("hides the Edit action for members (no canEdit)", async () => {
    invoke.mockImplementation((cmd) =>
      cmd === "profile_memory"
        ? Promise.resolve({ "AGENT.md": "hi", "MEMORY.md": "", "USER.md": "" })
        : Promise.resolve(null),
    );
    render(<MemoryModal open profile="doc" connectionId={null} />);
    await waitFor(() => expect(screen.getAllByText("AGENT.md").length).toBeGreaterThan(0));
    expect(screen.queryByRole("button", { name: "Edit" })).toBeNull();
  });
});

describe("MemoryModal edit", () => {
  function mockLoad(over = {}) {
    invoke.mockImplementation((cmd) => {
      if (cmd === "profile_memory") return Promise.resolve({ "AGENT.md": "old body", "MEMORY.md": "", "USER.md": "" });
      if (cmd === "memory_usage") return Promise.resolve(null);
      if (cmd === "memory_read") return Promise.resolve({ text: "old body full", rev: "r1" });
      if (cmd === "memory_write") return over.write ? over.write() : Promise.resolve({ ok: true, rev: "r2" });
      return Promise.resolve(null);
    });
  }

  it("reads the full file on edit and saves with the revision", async () => {
    mockLoad();
    render(<MemoryModal open profile="doc" connectionId={null} canEdit />);
    await waitFor(() => expect(screen.getByRole("button", { name: "Edit" })).toBeTruthy());

    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Edit" })); });
    const box = await screen.findByLabelText("Edit AGENT.md");
    expect(box.value).toBe("old body full");
    fireEvent.change(box, { target: { value: "new body" } });
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Save" })); });

    expect(invoke).toHaveBeenCalledWith("memory_write", {
      profile: "doc", name: "AGENT.md", text: "new body", rev: "r1", connectionId: null,
    });
  });

  it("keeps the editor and the draft when the save conflicts", async () => {
    mockLoad({ write: () => Promise.reject(new Error("conflict: memory changed")) });
    render(<MemoryModal open profile="doc" connectionId={null} canEdit />);
    await waitFor(() => expect(screen.getByRole("button", { name: "Edit" })).toBeTruthy());
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Edit" })); });
    const box = await screen.findByLabelText("Edit AGENT.md");
    fireEvent.change(box, { target: { value: "my precious draft" } });
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Save" })); });

    expect(screen.getByLabelText("Edit AGENT.md").value).toBe("my precious draft");
  });

  it("confirms before closing while the edit is dirty and honours the choice", async () => {
    mockLoad();
    const onClose = vi.fn();
    render(<MemoryModal open profile="doc" connectionId={null} canEdit onClose={onClose} />);
    await waitFor(() => expect(screen.getByRole("button", { name: "Edit" })).toBeTruthy());
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Edit" })); });
    const box = await screen.findByLabelText("Edit AGENT.md");
    fireEvent.change(box, { target: { value: "dirty draft" } });

    const confirmSpy = vi.spyOn(globalThis, "confirm").mockReturnValue(false);
    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(confirmSpy).toHaveBeenCalled();
    expect(onClose).not.toHaveBeenCalled();

    confirmSpy.mockReturnValue(true);
    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(onClose).toHaveBeenCalledTimes(1);
    confirmSpy.mockRestore();
  });

  it("reloads the latest content when the edit is cancelled", async () => {
    mockLoad();
    render(<MemoryModal open profile="doc" connectionId={null} canEdit />);
    await waitFor(() => expect(screen.getByRole("button", { name: "Edit" })).toBeTruthy());
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Edit" })); });
    await screen.findByLabelText("Edit AGENT.md");
    const before = invoke.mock.calls.filter((c) => c[0] === "profile_memory").length;
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Cancel" })); });
    await waitFor(() =>
      expect(invoke.mock.calls.filter((c) => c[0] === "profile_memory").length).toBe(before + 1),
    );
  });
});
