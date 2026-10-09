import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { invoke } from "@tauri-apps/api/core";

const busHandlers = new Set();
vi.mock("../lib/daemon-bus.js", () => ({
  subscribeDaemonEvent: (fn) => {
    busHandlers.add(fn);
    return () => busHandlers.delete(fn);
  },
}));

import {
  ACTIVITY_DEBOUNCE_MS,
  isMissingVerb,
  recentlyFailed,
  rosterStates,
  useActivity,
} from "./useActivity.js";

function emit(frame, extra = {}) {
  for (const fn of Array.from(busHandlers)) fn({ payload: { frame, ...extra } });
}

const SAMPLE = {
  needs_you: [{ kind: "approval", request_id: "r1", profile: "builder", title: "rm -rf dist", ts: 1 }],
  running: [
    { kind: "turn", profile: "alpi", session_id: "s1", title: "deploy", started_at: 1 },
    { kind: "workgroup", profile: "alpi", workgroup_id: "wg1", name: "crew", phase: "analyze", phases_done: 2, phases_total: 4 },
  ],
  scheduled: [{ profile: "doc", job_id: "j1", title: "brief", next_fire: null, last_run_status: "error", last_run_at: 1000 }],
};

beforeEach(() => {
  vi.resetAllMocks();
  busHandlers.clear();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("rosterStates", () => {
  it("ranks needs-you over failed over working and maps workgroup phases", () => {
    const now = 1000 + 3600;
    const { profiles, workgroups } = rosterStates(
      {
        ...SAMPLE,
        running: [...SAMPLE.running, { kind: "turn", profile: "builder" }],
        scheduled: [...SAMPLE.scheduled, { profile: "builder", last_run_status: "error", last_run_at: 1000 }],
      },
      { nowS: now },
    );
    expect(profiles).toEqual({ builder: "needs-you", alpi: "working", doc: "failed" });
    expect(workgroups["alpi/wg1"]).toEqual({ state: "working", phasesDone: 2, phasesTotal: 4, phase: "analyze" });
  });

  it("reads a failed job that is running again as working, but not another failed job of the profile", () => {
    const now = 1000 + 3600;
    const failed = (job_id) => ({ profile: "smith", job_id, last_run_status: "error", last_run_at: 1000 });
    const rerun = { kind: "turn", source: "schedule", profile: "smith", job_id: "audit", started_at: 1100 };
    expect(rosterStates({ needs_you: [], running: [rerun], scheduled: [failed("audit")] }, { nowS: now }).profiles).toEqual({ smith: "working" });
    expect(rosterStates({ needs_you: [], running: [rerun], scheduled: [failed("audit"), failed("digest")] }, { nowS: now }).profiles).toEqual({ smith: "failed" });
    expect(rosterStates({ needs_you: [{ kind: "approval", profile: "smith" }], running: [rerun], scheduled: [failed("audit")] }, { nowS: now }).profiles).toEqual({ smith: "needs-you" });
    expect(rosterStates({ needs_you: [], running: [{ ...rerun, profile: "doc" }], scheduled: [failed("audit")] }, { nowS: now }).profiles).toEqual({ smith: "failed", doc: "working" });
    const { job_id: _, ...older } = rerun;
    expect(rosterStates({ needs_you: [], running: [older], scheduled: [failed("audit")] }, { nowS: now }).profiles).toEqual({ smith: "failed" });
  });

  it("only counts a scheduled error from the last 24 hours as failed", () => {
    const job = { last_run_status: "error", last_run_at: "2026-09-29T10:00:00Z" };
    const at = Date.parse(job.last_run_at) / 1000;
    expect(recentlyFailed(job, at + 3600)).toBe(true);
    expect(recentlyFailed(job, at + 25 * 3600)).toBe(false);
    expect(recentlyFailed({ ...job, last_run_status: "ok" }, at)).toBe(false);
  });

  it("marks locally streaming profiles as working even with no daemon activity", () => {
    expect(rosterStates(null, { pendingProfiles: new Set(["abby"]) }).profiles).toEqual({ abby: "working" });
  });
});

describe("isMissingVerb", () => {
  it("recognises the daemon's missing-method errors", () => {
    expect(isMissingVerb("alp -32601: method-not-found")).toBe(true);
    expect(isMissingVerb(new Error("alp -32601: method-not-found"))).toBe(true);
    expect(isMissingVerb("alp -32004: not-found — no session 's1'")).toBe(false);
    expect(isMissingVerb("connection refused")).toBe(false);
  });

  it("treats a scoped device's forbidden answer like a missing verb so the entry hides", () => {
    expect(isMissingVerb("alp -32000: forbidden")).toBe(true);
    expect(isMissingVerb(new Error("forbidden"))).toBe(true);
  });
});

describe("useActivity", () => {
  it("fetches on mount for the active connection", async () => {
    invoke.mockResolvedValueOnce(SAMPLE);
    const { result } = renderHook(() => useActivity({ connectionId: "local" }));
    await waitFor(() => expect(result.current.activity?.running).toHaveLength(2));
    expect(invoke).toHaveBeenCalledWith("activity_list", { connectionId: "local" });
    expect(result.current.counts).toEqual({ needsYou: 1, running: 2 });
  });

  it("hides itself silently when the daemon predates the verb", async () => {
    invoke.mockRejectedValueOnce("alp -32601: method-not-found");
    const { result } = renderHook(() => useActivity({ connectionId: "local" }));
    await waitFor(() => expect(result.current.supported).toBe(false));
    expect(result.current.activity).toBeNull();
  });

  it("keeps the last snapshot on a transient failure", async () => {
    invoke.mockResolvedValueOnce(SAMPLE).mockRejectedValueOnce("timeout");
    const { result } = renderHook(() => useActivity({ connectionId: "local" }));
    await waitFor(() => expect(result.current.activity?.needs_you).toHaveLength(1));
    await act(async () => { await result.current.refresh(); });
    expect(result.current.supported).toBe(true);
    expect(result.current.activity.needs_you).toHaveLength(1);
  });

  it("debounces a burst of activity.changed events into one refetch", async () => {
    invoke.mockResolvedValue(SAMPLE);
    const { result } = renderHook(() => useActivity({ connectionId: "local" }));
    await waitFor(() => expect(result.current.activity).not.toBeNull());
    vi.useFakeTimers();
    invoke.mockClear();
    act(() => {
      emit({ event: "activity.changed", data: { profile: "alpi" } });
      emit({ event: "activity.changed", data: { profile: "doc" } });
      emit({ event: "session_changed", data: { profile: "doc" } });
    });
    expect(invoke).not.toHaveBeenCalled();
    await act(async () => { vi.advanceTimersByTime(ACTIVITY_DEBOUNCE_MS); });
    expect(invoke).toHaveBeenCalledTimes(1);
  });

  it("ignores events from another daemon", async () => {
    invoke.mockResolvedValue(SAMPLE);
    renderHook(() => useActivity({ connectionId: "local" }));
    await waitFor(() => expect(invoke).toHaveBeenCalledTimes(1));
    vi.useFakeTimers();
    act(() => emit({ event: "activity.changed", data: {} }, { connection_id: "remote" }));
    await act(async () => { vi.advanceTimersByTime(ACTIVITY_DEBOUNCE_MS * 2); });
    expect(invoke).toHaveBeenCalledTimes(1);
  });

  it("refetches when the connection comes back online", async () => {
    invoke.mockResolvedValue(SAMPLE);
    const { rerender } = renderHook(({ online }) => useActivity({ connectionId: "local", online }), {
      initialProps: { online: false },
    });
    expect(invoke).not.toHaveBeenCalled();
    rerender({ online: true });
    await waitFor(() => expect(invoke).toHaveBeenCalledTimes(1));
  });
});
