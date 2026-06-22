import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor, act } from "@testing-library/react";

globalThis.ResizeObserver ??= class { observe() {} unobserve() {} disconnect() {} };

const invokeMock = vi.fn();

vi.mock("@tauri-apps/api/core", () => ({ invoke: (...a) => invokeMock(...a) }));
vi.mock("../../../primitives/Notification.jsx", () => ({ useNotify: () => () => {} }));

import { SchedulesSection } from "./SchedulesSection.jsx";

beforeEach(() => {
  invokeMock.mockReset();
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

  it("renders rows when jobs come back", async () => {
    invokeMock.mockResolvedValueOnce([
      { id: "j1", title: "Daily standup", prompt: "summarize", paused: false, cron: "0 9 * * *" },
    ]);
    render(<SchedulesSection profile={{ name: "work" }} />);
    expect(await screen.findByText("Daily standup")).toBeInTheDocument();
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
