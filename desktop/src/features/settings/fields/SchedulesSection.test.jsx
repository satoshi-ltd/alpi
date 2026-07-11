import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor, act, fireEvent } from "@testing-library/react";

globalThis.ResizeObserver ??= class { observe() {} unobserve() {} disconnect() {} };

const invokeMock = vi.fn();
const listenSubs = new Map();

vi.mock("@tauri-apps/api/core", () => ({ invoke: (...a) => invokeMock(...a) }));
vi.mock("@tauri-apps/api/event", () => ({
  listen: vi.fn(async (name, fn) => {
    if (!listenSubs.has(name)) listenSubs.set(name, new Set());
    listenSubs.get(name).add(fn);
    return () => { listenSubs.get(name)?.delete(fn); };
  }),
}));

function emit(name, payload) {
  for (const fn of listenSubs.get(name) ?? []) fn({ payload });
}

import { SchedulesSection, _clearScheduleCache } from "./SchedulesSection.jsx";
import { _resetDaemonBus } from "../../../lib/daemon-bus.js";

const JOB = (over = {}) => ({ id: "j1", title: "Daily", prompt: "x", paused: false, ...over });

beforeEach(() => {
  _clearScheduleCache();
  _resetDaemonBus();
  invokeMock.mockReset();
  listenSubs.clear();
});

describe("SchedulesSection", () => {
  it("renders the corrupt-schedule error instead of silently swallowing it", async () => {
    invokeMock.mockRejectedValueOnce("jobs.json corrupt: profiles/work: invalid JSON (line 3)");
    render(<SchedulesSection profile={{ name: "work" }} />);
    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(/jobs\.json corrupt/i);
    });
  });

  it("renders nothing when there are no jobs", async () => {
    invokeMock.mockResolvedValueOnce([]);
    const { container } = render(<SchedulesSection profile={{ name: "work" }} />);
    await act(async () => { await Promise.resolve(); });
    expect(container.firstChild).toBeNull();
  });

  it("stays visible while the selected daemon is loading", async () => {
    invokeMock.mockImplementationOnce(() => new Promise(() => {}));
    render(<SchedulesSection profile={{ name: "work" }} connectionId="casa" />);
    expect(screen.getByText("Schedule")).toBeInTheDocument();
    expect(screen.getByText("loading…")).toBeInTheDocument();
  });

  it("summarizes job + active count and opens the viewer on click", async () => {
    const onOpen = vi.fn();
    invokeMock.mockResolvedValueOnce([JOB(), JOB({ id: "j2", paused: true })]);
    render(<SchedulesSection profile={{ name: "work" }} onOpen={onOpen} />);
    const link = await screen.findByRole("button", { name: "2 jobs · 1 active" });
    fireEvent.click(link);
    expect(onOpen).toHaveBeenCalledTimes(1);
  });

  it("renders prefetched jobs without an individual schedules fetch", async () => {
    render(
      <SchedulesSection
        profile={{ name: "work" }}
        connectionId="casa"
        prefetched={[JOB({ title: "From snapshot" })]}
      />,
    );
    expect(await screen.findByText("1 job · 1 active")).toBeInTheDocument();
    await act(async () => { await Promise.resolve(); });
    expect(invokeMock.mock.calls.some((c) => c[0] === "schedules")).toBe(false);
  });

  it("forwards connectionId so two daemons with the same profile name don't share state", async () => {
    invokeMock.mockResolvedValueOnce([]);
    render(<SchedulesSection profile={{ name: "work" }} connectionId="casa" />);
    await waitFor(() => {
      expect(invokeMock).toHaveBeenCalledWith("schedules", { profile: "work", connectionId: "casa" });
    });
  });

  it("omits connectionId when the caller did not pass one", async () => {
    invokeMock.mockResolvedValueOnce([]);
    render(<SchedulesSection profile={{ name: "work" }} />);
    await waitFor(() => {
      expect(invokeMock).toHaveBeenCalledWith("schedules", { profile: "work" });
    });
  });

  it("ignores a late response from a previous connection after switching", async () => {
    let resolveA;
    const deferredA = new Promise((res) => { resolveA = res; });
    invokeMock.mockImplementationOnce(() => deferredA);
    invokeMock.mockImplementationOnce(() => Promise.resolve([JOB({ id: "b", title: "B" })]));

    const { rerender } = render(<SchedulesSection profile={{ name: "work" }} connectionId="A" />);
    rerender(<SchedulesSection profile={{ name: "work" }} connectionId="B" />);
    expect(await screen.findByText("1 job · 1 active")).toBeInTheDocument();

    resolveA([JOB({ id: "a1" }), JOB({ id: "a2" })]);
    await act(async () => { await Promise.resolve(); await Promise.resolve(); });
    expect(screen.getByText("1 job · 1 active")).toBeInTheDocument();
  });

  it("reports loading state via onLoadingChange", async () => {
    let resolve;
    invokeMock.mockImplementationOnce(() => new Promise((r) => { resolve = r; }));
    const onLoadingChange = vi.fn();
    render(<SchedulesSection profile={{ name: "work" }} onLoadingChange={onLoadingChange} />);
    await waitFor(() => expect(onLoadingChange).toHaveBeenCalledWith(true));
    onLoadingChange.mockClear();
    resolve([]);
    await waitFor(() => expect(onLoadingChange).toHaveBeenCalledWith(false));
  });

  it("re-fetches when the daemon emits schedule.changed for this (profile, connection)", async () => {
    invokeMock.mockResolvedValueOnce([JOB()]);
    render(<SchedulesSection profile={{ name: "work" }} connectionId="casa" />);
    expect(await screen.findByText("1 job · 1 active")).toBeInTheDocument();

    invokeMock.mockResolvedValueOnce([JOB(), JOB({ id: "j2" })]);
    await act(async () => {
      emit("daemon-event", {
        connection_id: "casa",
        frame: { event: "schedule.changed", data: { profile: "work" } },
      });
    });
    expect(await screen.findByText("2 jobs · 2 active")).toBeInTheDocument();
  });
});
