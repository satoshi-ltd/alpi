import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor, fireEvent, act } from "@testing-library/react";
import { createRoot } from "react-dom/client";

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
  it("renders each file's use against its limit from memory_usage", async () => {
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
    await waitFor(() => expect(screen.getAllByText("4,000 / 8,000").length).toBeGreaterThan(0));
    expect(screen.getAllByText("Identity").length).toBeGreaterThan(0);
    expect(screen.getByText("Learned")).toBeTruthy();
    expect(screen.getByText("About you")).toBeTruthy();
  });

  it("splits a file into its entries and says when each was captured and reinforced", async () => {
    const raw = "Fact one.\n<!-- alpi-meta conf=normal captured=2026-09-28 reinforced=3 -->\n§\nFact two.\n<!-- alpi-meta conf=low captured=2026-10-02 reinforced=0 -->";
    invoke.mockImplementation((cmd) =>
      cmd === "profile_memory"
        ? Promise.resolve({ "AGENT.md": raw, "MEMORY.md": "", "USER.md": "" })
        : Promise.resolve(null),
    );
    render(<MemoryModal open profile="scout" connectionId={null} owner={{ name: "scout", fold: "house", accent: "#c42" }} />);
    await waitFor(() => expect(screen.getByText("Fact one.")).toBeTruthy());
    expect(screen.getByText("Fact two.")).toBeTruthy();
    expect(screen.getByText("captured Sep 28 · reinforced ×3")).toBeTruthy();
    expect(screen.getByText("captured Oct 2 · low confidence")).toBeTruthy();
    expect(screen.getByText("who scout is")).toBeTruthy();
    expect(document.body.textContent).not.toContain("alpi-meta");
    expect(document.body.textContent).not.toContain("§");
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

  it("confirms before switching to a sibling panel while the edit is dirty", async () => {
    mockLoad();
    const onSection = vi.fn();
    render(<MemoryModal open profile="doc" connectionId={null} canEdit owner={{ name: "doc", fold: "house", accent: "#cc4422" }} onSection={onSection} />);
    await waitFor(() => expect(screen.getByRole("button", { name: "Edit" })).toBeTruthy());
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Edit" })); });
    fireEvent.change(await screen.findByLabelText("Edit AGENT.md"), { target: { value: "dirty draft" } });

    const confirmSpy = vi.spyOn(globalThis, "confirm").mockReturnValue(false);
    fireEvent.click(screen.getByRole("tab", { name: "Skills" }));
    expect(confirmSpy).toHaveBeenCalled();
    expect(onSection).not.toHaveBeenCalled();

    confirmSpy.mockReturnValue(true);
    fireEvent.click(screen.getByRole("tab", { name: "Skills" }));
    expect(onSection).toHaveBeenCalledWith("skills");
    confirmSpy.mockRestore();
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

describe("MemoryModal edit right after the list loads", () => {
  it("keeps the editor open when Edit is pressed before the selection effects run", async () => {
    invoke.mockImplementation((cmd) => {
      if (cmd === "profile_memory") return Promise.resolve({ "AGENT.md": "old body", "MEMORY.md": "", "USER.md": "" });
      if (cmd === "memory_read") return Promise.resolve({ text: "old body full", rev: "r1" });
      return Promise.resolve(null);
    });
    const actEnv = globalThis.IS_REACT_ACT_ENVIRONMENT;
    globalThis.IS_REACT_ACT_ENVIRONMENT = false;
    const host = document.createElement("div");
    document.body.appendChild(host);
    const root = createRoot(host);
    let watch;
    try {
      const pressed = new Promise((resolve, reject) => {
        watch = new MutationObserver(() => {
          const edit = document.querySelector('button[aria-label="Edit"]');
          if (!edit) return;
          watch.disconnect();
          edit.click();
          resolve();
        });
        watch.observe(document.body, { childList: true, subtree: true });
        setTimeout(() => reject(new Error("Edit never appeared")), 3000);
      });
      root.render(<MemoryModal open profile="doc" connectionId={null} canEdit />);
      await pressed;
      await new Promise((r) => setTimeout(r, 200));
      expect(document.querySelector('[aria-label="Edit AGENT.md"]')).not.toBeNull();
    } finally {
      watch?.disconnect();
      root.unmount();
      host.remove();
      globalThis.IS_REACT_ACT_ENVIRONMENT = actEnv;
    }
  });

  it("asks before switching file with a dirty edit, and drops the edit when it switches", async () => {
    invoke.mockImplementation((cmd) => {
      if (cmd === "profile_memory") return Promise.resolve({ "AGENT.md": "old body", "MEMORY.md": "learned", "USER.md": "" });
      if (cmd === "memory_read") return Promise.resolve({ text: "old body full", rev: "r1" });
      return Promise.resolve(null);
    });
    render(<MemoryModal open profile="doc" connectionId={null} canEdit />);
    await waitFor(() => expect(screen.getByRole("button", { name: "Edit" })).toBeTruthy());
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Edit" })); });
    fireEvent.change(await screen.findByLabelText("Edit AGENT.md"), { target: { value: "draft" } });
    const learned = screen.getByRole("option", { name: /Learned/ });

    const confirm = vi.spyOn(globalThis, "confirm").mockReturnValue(false);
    fireEvent.click(learned);
    expect(screen.getByLabelText("Edit AGENT.md").value).toBe("draft");

    confirm.mockReturnValue(true);
    fireEvent.click(learned);
    await waitFor(() => expect(screen.queryByLabelText("Edit AGENT.md")).toBeNull());
    fireEvent.click(screen.getByRole("option", { name: /Identity/ }));
    expect(screen.queryByLabelText("Edit AGENT.md")).toBeNull();
    confirm.mockRestore();
  });
});
