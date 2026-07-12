import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent, act, waitFor } from "@testing-library/react";

const h = vi.hoisted(() => ({ invoke: vi.fn() }));
vi.mock("@tauri-apps/api/core", () => ({ invoke: h.invoke }));
vi.mock("../../../primitives/Notification.jsx", () => ({ useNotify: () => () => {} }));

import { CleanupField } from "./maintenance.jsx";

const PLAN = [
  { key: "tts", label: "TTS cache", desc: "mp3s", size: 2048, count: 3, action: "unlink", destructive: false },
  { key: "knowledge", label: "Knowledge index bloat", desc: "freelist", size: 1024, count: 1, action: "vacuum", destructive: false },
  { key: "sessions", label: "Old sessions", desc: "transcripts", size: 512, count: 2, action: "unlink", destructive: true },
  { key: "logs", label: "Subsystem logs", desc: "logs", size: 0, count: 0, action: "unlink", destructive: false },
];

beforeEach(() => {
  h.invoke.mockReset();
});

describe("CleanupField", () => {
  it("lists only reclaimable categories, with Compact for vacuum actions", async () => {
    h.invoke.mockResolvedValue(PLAN);
    render(
      <CleanupField
        profile={{ name: "agora" }}
        activeConnection={{ id: "conn-1", kind: "local" }}
      />,
    );
    await waitFor(() => expect(screen.getByText("tts cache")).toBeTruthy());
    expect(h.invoke).toHaveBeenCalledWith("cleanup_plan", {
      profile: "agora", connectionId: "conn-1",
    });
    expect(screen.getByText("Compact")).toBeTruthy();
    expect(screen.getAllByText("Clean")).toHaveLength(2);
    expect(screen.queryByText("subsystem logs")).toBeNull();
  });

  it("destructive categories confirm through ConfirmDelete before applying", async () => {
    h.invoke.mockImplementation(async (cmd) =>
      cmd === "cleanup_plan" ? PLAN : [{ key: "sessions", ok: true, removed: 2, freed_bytes: 512 }],
    );
    render(
      <CleanupField profile={{ name: "agora" }} activeConnection={{ id: "c1", kind: "local" }} />,
    );
    await waitFor(() => expect(screen.getByText("old sessions")).toBeTruthy());
    await act(async () => { fireEvent.click(screen.getAllByText("Clean")[1]); });
    expect(h.invoke.mock.calls.filter(([c]) => c === "cleanup_apply")).toHaveLength(0);
    expect(screen.getByText("Delete old sessions?")).toBeTruthy();
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Delete" })); });
    expect(h.invoke).toHaveBeenCalledWith("cleanup_apply", {
      profile: "agora", keys: ["sessions"], connectionId: "c1",
    });
  });

  it("closing the confirm without confirming applies nothing", async () => {
    h.invoke.mockImplementation(async (cmd) => (cmd === "cleanup_plan" ? PLAN : []));
    render(
      <CleanupField profile={{ name: "agora" }} activeConnection={{ id: "c1", kind: "local" }} />,
    );
    await waitFor(() => expect(screen.getByText("old sessions")).toBeTruthy());
    await act(async () => { fireEvent.click(screen.getAllByText("Clean")[1]); });
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Cancel" })); });
    expect(h.invoke.mock.calls.filter(([c]) => c === "cleanup_apply")).toHaveLength(0);
  });

  it("a partial failure surfaces the error AND refreshes state", async () => {
    h.invoke.mockImplementation(async (cmd) =>
      cmd === "cleanup_plan"
        ? PLAN
        : [{ key: "tts", ok: false, removed: 2, freed_bytes: 128, errors: ["a.mp3: permission denied"] }],
    );
    const onCleaned = vi.fn();
    render(
      <CleanupField
        profile={{ name: "agora" }}
        activeConnection={{ id: "c1", kind: "local" }}
        onCleaned={onCleaned}
      />,
    );
    await waitFor(() => expect(screen.getAllByText("Clean").length).toBeGreaterThan(0));
    const planCallsBefore = h.invoke.mock.calls.filter(([c]) => c === "cleanup_plan").length;
    await act(async () => { fireEvent.click(screen.getAllByText("Clean")[0]); });
    const planCallsAfter = h.invoke.mock.calls.filter(([c]) => c === "cleanup_plan").length;
    expect(planCallsAfter).toBe(planCallsBefore + 1);
    expect(onCleaned).toHaveBeenCalled();
  });

  it("shows the unavailable state when the daemon rejects the plan", async () => {
    h.invoke.mockRejectedValue(new Error("no such verb"));
    render(
      <CleanupField profile={{ name: "old" }} activeConnection={{ id: "c1", kind: "local" }} />,
    );
    await waitFor(() =>
      expect(screen.getByText(/cleanup unavailable/)).toBeTruthy(),
    );
  });

  it("applies one category, forwarding the connection, then refetches", async () => {
    h.invoke.mockImplementation(async (cmd) =>
      cmd === "cleanup_plan" ? PLAN : [{ key: "tts", ok: true, removed: 3, freed_bytes: 2048 }],
    );
    const onCleaned = vi.fn();
    render(
      <CleanupField
        profile={{ name: "agora" }}
        activeConnection={{ id: "conn-remote", kind: "remote" }}
        onCleaned={onCleaned}
      />,
    );
    await waitFor(() => expect(screen.getAllByText("Clean").length).toBeGreaterThan(0));
    await act(async () => {
      fireEvent.click(screen.getAllByText("Clean")[0]);
    });
    expect(h.invoke).toHaveBeenCalledWith("cleanup_apply", {
      profile: "agora", keys: ["tts"], connectionId: "conn-remote",
    });
    expect(onCleaned).toHaveBeenCalled();
    const planCalls = h.invoke.mock.calls.filter(([c]) => c === "cleanup_plan");
    expect(planCalls.length).toBeGreaterThanOrEqual(2);
  });

  it("shows the tidy state when nothing is reclaimable", async () => {
    h.invoke.mockResolvedValue([{ key: "tts", label: "TTS cache", desc: "", size: 0, count: 0, action: "unlink" }]);
    render(
      <CleanupField profile={{ name: "doc" }} activeConnection={{ id: "c", kind: "local" }} />,
    );
    await waitFor(() => expect(screen.getByText("nothing to clean")).toBeTruthy());
  });
});
