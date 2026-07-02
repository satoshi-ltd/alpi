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
vi.mock("../../../primitives/Notification.jsx", () => ({ useNotify: () => () => {} }));

function emit(name, payload) {
  for (const fn of listenSubs.get(name) ?? []) fn({ payload });
}

import { SchedulesSection, _clearScheduleCache } from "./SchedulesSection.jsx";
import { _resetDaemonBus } from "../../../lib/daemon-bus.js";

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

  it("renders nothing when the schedule list is empty (no jobs, no error)", async () => {
    invokeMock.mockResolvedValueOnce([]);
    const { container } = render(<SchedulesSection profile={{ name: "work" }} />);
    await act(async () => { await Promise.resolve(); });
    expect(container.firstChild).toBeNull();
  });

  it("keeps the schedule section visible while the selected daemon is loading", async () => {
    invokeMock.mockImplementationOnce(() => new Promise(() => {}));
    render(<SchedulesSection profile={{ name: "work" }} connectionId="casa" />);
    expect(screen.getByText("Schedule")).toBeInTheDocument();
    expect(screen.getByText("loading…")).toBeInTheDocument();
  });

  it("renders prefetched jobs without an individual schedules fetch", async () => {
    render(
      <SchedulesSection
        profile={{ name: "work" }}
        connectionId="casa"
        prefetched={[{ id: "j1", title: "From snapshot", prompt: "", paused: false, cron: "* * * * *" }]}
      />,
    );
    expect(await screen.findByText("From snapshot")).toBeInTheDocument();
    await act(async () => { await Promise.resolve(); });
    expect(invokeMock.mock.calls.some((c) => c[0] === "schedules")).toBe(false);
  });

  it("refreshes the snapshot after a mutation when seeded by prefetched jobs", async () => {
    const onSnapshotRefresh = vi.fn(async () => {});
    invokeMock.mockResolvedValueOnce(null);
    render(
      <SchedulesSection
        profile={{ name: "work" }}
        connectionId="casa"
        prefetched={[{ id: "j1", title: "From snapshot", prompt: "", paused: false, cron: "* * * * *" }]}
        onSnapshotRefresh={onSnapshotRefresh}
      />,
    );
    fireEvent.click(await screen.findByRole("button", { name: "Disable" }));

    await waitFor(() => {
      expect(invokeMock).toHaveBeenCalledWith("schedule_set_paused", {
        profile: "work",
        connectionId: "casa",
        id: "j1",
        paused: true,
      });
      expect(onSnapshotRefresh).toHaveBeenCalledTimes(1);
    });
    expect(invokeMock.mock.calls.some(([cmd]) => cmd === "schedules")).toBe(false);
  });

  it("renders rows when jobs come back", async () => {
    invokeMock.mockResolvedValueOnce([
      { id: "j1", title: "Daily standup", prompt: "summarize", paused: false, cron: "0 9 * * *" },
    ]);
    render(<SchedulesSection profile={{ name: "work" }} />);
    expect(await screen.findByText("Daily standup")).toBeInTheDocument();
  });

  it("renders cached jobs immediately while refreshing", async () => {
    invokeMock
      .mockResolvedValueOnce([
        { id: "j1", title: "Cached", prompt: "", paused: false, cron: "* * * * *" },
      ])
      .mockResolvedValueOnce([
        { id: "j2", title: "Fresh", prompt: "", paused: false, cron: "* * * * *" },
      ]);
    const first = render(<SchedulesSection profile={{ name: "work" }} connectionId="casa" />);
    expect(await screen.findByText("Cached")).toBeInTheDocument();
    first.unmount();

    render(<SchedulesSection profile={{ name: "work" }} connectionId="casa" />);
    expect(screen.getByText("Cached")).toBeInTheDocument();
    expect(await screen.findByText("Fresh")).toBeInTheDocument();
    expect(invokeMock).toHaveBeenCalledTimes(2);
  });

  it("forwards connectionId so two daemons with the same profile name don't share state", async () => {
    invokeMock.mockResolvedValueOnce([]);
    render(<SchedulesSection profile={{ name: "work" }} connectionId="casa" />);
    await waitFor(() => {
      expect(invokeMock).toHaveBeenCalledWith("schedules", { profile: "work", connectionId: "casa" });
    });
  });

  it("omits connectionId when caller did not pass one (active-connection fallback)", async () => {
    invokeMock.mockResolvedValueOnce([]);
    render(<SchedulesSection profile={{ name: "work" }} />);
    await waitFor(() => {
      expect(invokeMock).toHaveBeenCalledWith("schedules", { profile: "work" });
    });
  });

  it("ignores a late response from a previous connection after switching", async () => {
    let resolveA;
    const deferredA = new Promise((res) => { resolveA = res; });
    const aJobs = [{ id: "j-from-A", title: "From A", prompt: "", paused: false, cron: "* * * * *" }];
    const bJobs = [{ id: "j-from-B", title: "From B", prompt: "", paused: false, cron: "* * * * *" }];

    invokeMock.mockImplementationOnce(() => deferredA);
    invokeMock.mockImplementationOnce(() => Promise.resolve(bJobs));

    const { rerender } = render(<SchedulesSection profile={{ name: "work" }} connectionId="A" />);
    rerender(<SchedulesSection profile={{ name: "work" }} connectionId="B" />);
    expect(await screen.findByText("From B")).toBeInTheDocument();
    expect(screen.queryByText("From A")).toBeNull();

    resolveA(aJobs);
    await act(async () => { await Promise.resolve(); await Promise.resolve(); });
    expect(screen.queryByText("From A")).toBeNull();
    expect(screen.getByText("From B")).toBeInTheDocument();
  });

  it("reports loading state via onLoadingChange so the parent RefreshBar reflects the panel", async () => {
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
    invokeMock.mockResolvedValueOnce([
      { id: "j1", title: "First", prompt: "", paused: false, cron: "* * * * *" },
    ]);
    render(<SchedulesSection profile={{ name: "work" }} connectionId="casa" />);
    expect(await screen.findByText("First")).toBeInTheDocument();

    invokeMock.mockResolvedValueOnce([
      { id: "j1", title: "First", prompt: "", paused: false, cron: "* * * * *" },
      { id: "j2", title: "Second", prompt: "", paused: false, cron: "* * * * *" },
    ]);
    await act(async () => {
      emit("daemon-event", {
        connection_id: "casa",
        frame: { event: "schedule.changed", data: { profile: "work" } },
      });
    });
    expect(await screen.findByText("Second")).toBeInTheDocument();
  });

  it("re-fetches when a background job finishes (schedule.done / schedule.failed)", async () => {
    invokeMock.mockResolvedValueOnce([
      { id: "j1", title: "First", prompt: "", paused: false, cron: "* * * * *" },
    ]);
    render(<SchedulesSection profile={{ name: "work" }} connectionId="casa" />);
    expect(await screen.findByText("First")).toBeInTheDocument();

    invokeMock.mockResolvedValueOnce([
      { id: "j1", title: "Renamed", prompt: "", paused: false, cron: "* * * * *" },
    ]);
    await act(async () => {
      emit("daemon-event", {
        connection_id: "casa",
        frame: { event: "schedule.done", data: { profile: "work" } },
      });
    });
    expect(await screen.findByText("Renamed")).toBeInTheDocument();
  });

  it("ignores schedule.changed events for a different profile", async () => {
    invokeMock.mockResolvedValueOnce([
      { id: "j1", title: "Stay", prompt: "", paused: false, cron: "* * * * *" },
    ]);
    render(<SchedulesSection profile={{ name: "work" }} connectionId="casa" />);
    expect(await screen.findByText("Stay")).toBeInTheDocument();
    invokeMock.mockClear();

    await act(async () => {
      emit("daemon-event", {
        connection_id: "casa",
        frame: { event: "schedule.changed", data: { profile: "personal" } },
      });
    });
    expect(invokeMock).not.toHaveBeenCalled();
  });

  it("ignores schedule.changed events from a different pinned connection", async () => {
    invokeMock.mockResolvedValueOnce([
      { id: "j1", title: "Stay", prompt: "", paused: false, cron: "* * * * *" },
    ]);
    render(<SchedulesSection profile={{ name: "work" }} connectionId="casa" />);
    expect(await screen.findByText("Stay")).toBeInTheDocument();
    invokeMock.mockClear();

    await act(async () => {
      emit("daemon-event", {
        connection_id: "other",
        frame: { event: "schedule.changed", data: { profile: "work" } },
      });
    });
    expect(invokeMock).not.toHaveBeenCalled();
  });

  it("defers the standalone fetch while the snapshot is pending, then renders prefetched jobs", async () => {
    const { rerender } = render(
      <SchedulesSection profile={{ name: "work" }} connectionId="casa" defer />,
    );
    expect(screen.getByText("loading…")).toBeInTheDocument();
    await act(async () => { await Promise.resolve(); });
    expect(invokeMock).not.toHaveBeenCalled();

    rerender(
      <SchedulesSection
        profile={{ name: "work" }}
        connectionId="casa"
        prefetched={[{ id: "j1", title: "From snapshot", prompt: "", paused: false, cron: "* * * * *" }]}
      />,
    );
    expect(await screen.findByText("From snapshot")).toBeInTheDocument();
    expect(invokeMock.mock.calls.some(([cmd]) => cmd === "schedules")).toBe(false);
  });

  it("falls back to its own fetch when defer lifts without prefetched data (snapshot failed)", async () => {
    invokeMock.mockResolvedValueOnce([
      { id: "j1", title: "Fallback", prompt: "", paused: false, cron: "* * * * *" },
    ]);
    const { rerender } = render(
      <SchedulesSection profile={{ name: "work" }} connectionId="casa" defer />,
    );
    await act(async () => { await Promise.resolve(); });
    expect(invokeMock).not.toHaveBeenCalled();

    rerender(<SchedulesSection profile={{ name: "work" }} connectionId="casa" />);
    expect(await screen.findByText("Fallback")).toBeInTheDocument();
  });

  it("clears the stale list while loading the new connection so no A-job is interactive against B", async () => {
    let resolveB;
    const deferredB = new Promise((res) => { resolveB = res; });
    const aJobs = [{ id: "j-from-A", title: "From A", prompt: "", paused: false, cron: "* * * * *" }];

    invokeMock.mockImplementationOnce(() => Promise.resolve(aJobs));
    invokeMock.mockImplementationOnce(() => deferredB);

    const { rerender } = render(<SchedulesSection profile={{ name: "work" }} connectionId="A" />);
    expect(await screen.findByText("From A")).toBeInTheDocument();

    rerender(<SchedulesSection profile={{ name: "work" }} connectionId="B" />);
    await act(async () => { await Promise.resolve(); });
    expect(screen.queryByText("From A")).toBeNull();

    resolveB([]);
    await act(async () => { await Promise.resolve(); });
  });
});
