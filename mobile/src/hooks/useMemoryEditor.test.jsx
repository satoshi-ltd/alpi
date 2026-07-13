import { describe, it, expect, vi } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";

import { EndpointContext } from "../lib/EndpointContext";
import { useMemoryEditor } from "./useMemoryEditor";

function wrap(call) {
  return ({ children }) => (
    <EndpointContext.Provider value={{ endpoint: { id: "e1" }, call }}>
      {children}
    </EndpointContext.Provider>
  );
}

describe("useMemoryEditor", () => {
  it("loads text + revision and enables editing", async () => {
    const call = vi.fn(async () => ({ text: "body", rev: "r1" }));
    const { result } = renderHook(() => useMemoryEditor("doc", "AGENT.md"), { wrapper: wrap(call) });
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.raw).toBe("body");
    expect(result.current.rev).toBe("r1");
    expect(result.current.canEdit).toBe(true);
  });

  it("disables editing when the initial read fails", async () => {
    const call = vi.fn(async () => { throw new Error("network down"); });
    const { result } = renderHook(() => useMemoryEditor("doc", "AGENT.md"), { wrapper: wrap(call) });
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.loadError).toContain("network down");
    expect(result.current.canEdit).toBe(false);
    expect(result.current.rev).toBeNull();
  });

  it("saves the draft with the revision", async () => {
    const call = vi.fn(async (method) =>
      method === "host.profile.memory_read" ? { text: "old", rev: "r1" } : { ok: true, rev: "r2" },
    );
    const { result } = renderHook(() => useMemoryEditor("doc", "AGENT.md"), { wrapper: wrap(call) });
    await waitFor(() => expect(result.current.canEdit).toBe(true));
    act(() => result.current.startEdit());
    act(() => result.current.setDraft("new body"));
    let res;
    await act(async () => { res = await result.current.save(); });
    expect(res.ok).toBe(true);
    expect(call).toHaveBeenCalledWith("host.profile.memory_write", {
      profile: "doc", name: "AGENT.md", text: "new body", rev: "r1",
    });
    expect(result.current.editing).toBe(false);
  });

  it("tracks dirty only while the draft diverges from the loaded text", async () => {
    const call = vi.fn(async (method) =>
      method === "host.profile.memory_read" ? { text: "old", rev: "r1" } : { ok: true, rev: "r2" },
    );
    const { result } = renderHook(() => useMemoryEditor("doc", "AGENT.md"), { wrapper: wrap(call) });
    await waitFor(() => expect(result.current.canEdit).toBe(true));
    expect(result.current.dirty).toBe(false);
    act(() => result.current.startEdit());
    expect(result.current.dirty).toBe(false);
    act(() => result.current.setDraft("changed"));
    expect(result.current.dirty).toBe(true);
    act(() => result.current.setDraft("old"));
    expect(result.current.dirty).toBe(false);
  });

  it("keeps the draft and stale rev on conflict — no silent overwrite", async () => {
    const call = vi.fn(async (method) => {
      if (method === "host.profile.memory_read") return { text: "old", rev: "r1" };
      throw new Error("conflict: memory changed since it was read");
    });
    const { result } = renderHook(() => useMemoryEditor("doc", "AGENT.md"), { wrapper: wrap(call) });
    await waitFor(() => expect(result.current.canEdit).toBe(true));
    act(() => result.current.startEdit());
    act(() => result.current.setDraft("mine"));
    let res;
    await act(async () => { res = await result.current.save(); });
    expect(res).toMatchObject({ ok: false, conflict: true });
    expect(result.current.editing).toBe(true);
    expect(result.current.draft).toBe("mine");
    expect(result.current.rev).toBe("r1");
  });

  it("force save re-reads the latest rev then overwrites", async () => {
    const writes = [];
    let reads = 0;
    const call = vi.fn(async (method, params) => {
      if (method === "host.profile.memory_read") { reads += 1; return { text: "old", rev: reads === 1 ? "r1" : "r9" }; }
      writes.push(params.rev);
      return { ok: true, rev: "r10" };
    });
    const { result } = renderHook(() => useMemoryEditor("doc", "AGENT.md"), { wrapper: wrap(call) });
    await waitFor(() => expect(result.current.canEdit).toBe(true));
    act(() => result.current.startEdit());
    act(() => result.current.setDraft("mine"));
    let res;
    await act(async () => { res = await result.current.save({ force: true }); });
    expect(res.ok).toBe(true);
    expect(writes).toEqual(["r9"]);
  });

  it("reports failure and does not write when the Overwrite re-read fails", async () => {
    let reads = 0;
    const writes = [];
    const call = vi.fn(async (method, params) => {
      if (method === "host.profile.memory_read") {
        reads += 1;
        if (reads === 1) return { text: "old", rev: "r1" };
        throw new Error("read failed");
      }
      writes.push(params.rev);
      return { ok: true, rev: "r2" };
    });
    const { result } = renderHook(() => useMemoryEditor("doc", "AGENT.md"), { wrapper: wrap(call) });
    await waitFor(() => expect(result.current.canEdit).toBe(true));
    act(() => result.current.startEdit());
    act(() => result.current.setDraft("mine"));
    let res;
    await act(async () => { res = await result.current.save({ force: true }); });
    expect(res.ok).toBe(false);
    expect(res.message).toMatch(/overwrite/i);
    expect(writes).toEqual([]);
    expect(result.current.editing).toBe(true);
  });

  it("ignores a stale read after the target changes", async () => {
    let resolveA;
    const call = vi.fn((method, params) => {
      if (params.name === "A.md") return new Promise((r) => { resolveA = () => r({ text: "A", rev: "ra" }); });
      return Promise.resolve({ text: "B", rev: "rb" });
    });
    const { result, rerender } = renderHook(({ n }) => useMemoryEditor("doc", n), {
      wrapper: wrap(call),
      initialProps: { n: "A.md" },
    });
    rerender({ n: "B.md" });
    await waitFor(() => expect(result.current.raw).toBe("B"));
    await act(async () => { resolveA(); await Promise.resolve(); });
    expect(result.current.raw).toBe("B");
    expect(result.current.rev).toBe("rb");
  });

  it("ignores a pending save after the target changes", async () => {
    let resolveWrite;
    const call = vi.fn((method, params) => {
      if (method === "host.profile.memory_read") {
        return Promise.resolve({ text: params.name === "A.md" ? "A" : "B", rev: params.name === "A.md" ? "ra" : "rb" });
      }
      return new Promise((r) => { resolveWrite = () => r({ ok: true, rev: "rZ" }); });
    });
    const { result, rerender } = renderHook(({ n }) => useMemoryEditor("doc", n), {
      wrapper: wrap(call),
      initialProps: { n: "A.md" },
    });
    await waitFor(() => expect(result.current.canEdit).toBe(true));
    act(() => result.current.startEdit());
    act(() => result.current.setDraft("draft-A"));
    let saveP;
    act(() => { saveP = result.current.save(); });

    rerender({ n: "B.md" });
    await waitFor(() => expect(result.current.raw).toBe("B"));

    await act(async () => { resolveWrite(); await saveP; });
    expect(result.current.raw).toBe("B");
    expect(result.current.editing).toBe(false);
  });

  it("reload discards the draft and reloads from the daemon", async () => {
    const call = vi.fn(async () => ({ text: "latest", rev: "r2" }));
    const { result } = renderHook(() => useMemoryEditor("doc", "AGENT.md"), { wrapper: wrap(call) });
    await waitFor(() => expect(result.current.canEdit).toBe(true));
    act(() => result.current.startEdit());
    act(() => result.current.setDraft("mine"));
    await act(async () => { await result.current.reload(); });
    expect(result.current.editing).toBe(false);
    expect(result.current.raw).toBe("latest");
  });
});
