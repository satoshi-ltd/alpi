import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const invokeMock = vi.fn();
vi.mock("@tauri-apps/api/core", () => ({ invoke: (...a) => invokeMock(...a) }));
vi.mock("../lib/daemon-bus.js", () => ({ subscribeDaemonEvent: () => () => {} }));
vi.mock("../primitives/Notification.jsx", () => ({ useNotify: () => () => {} }));

import ScheduleModal from "./ScheduleModal.jsx";
import { lastRunShort } from "../lib/time.js";

globalThis.ResizeObserver ??= class { observe() {} unobserve() {} disconnect() {} };

const JOBS = [
  { id: "45188eab", kind: "cron", expression: "0 7 * * *", prompt: "Run the whoop skill", title: "WHOOP sync", paused: false, notify: false, no_agent: false, last_run_at: null, last_run_status: null, next_fire: null },
  { id: "aa11bb22", kind: "cron", expression: "0 22 * * *", prompt: "python3 run.py", title: "Wind-down checklist", paused: true, notify: true, no_agent: true, next_fire: null },
];

beforeEach(() => {
  invokeMock.mockReset();
  invokeMock.mockResolvedValue(JOBS);
});

function open() {
  return render(<ScheduleModal open onClose={vi.fn()} profile="lens" connectionId={null} />);
}

describe("ScheduleModal", () => {
  it("lists jobs and shows the first job's detail", async () => {
    open();
    await waitFor(() => expect(screen.getByText("Run the whoop skill")).toBeTruthy());
    expect(screen.getByText("Wind-down checklist")).toBeTruthy();
  });

  it("fires the selected job via schedule_fire", async () => {
    open();
    await waitFor(() => expect(screen.getByText("Run the whoop skill")).toBeTruthy());
    invokeMock.mockClear();
    invokeMock.mockResolvedValue({ ok: true });
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Run now" })); });
    expect(invokeMock).toHaveBeenCalledWith("schedule_fire", { profile: "lens", id: "45188eab" });
  });

  it("opens on the job a notification pointed at", async () => {
    render(<ScheduleModal open onClose={vi.fn()} profile="lens" connectionId={null} openJob={{ id: "aa11bb22" }} />);
    await waitFor(() => expect(screen.getByText("python3 run.py")).toBeTruthy());
    expect(screen.queryByText("Run the whoop skill")).toBeNull();
  });

  it("opens on the linked job after it was opened and closed before on the same profile", async () => {
    const onClose = vi.fn();
    const { rerender } = render(<ScheduleModal open onClose={onClose} profile="lens" connectionId={null} />);
    await waitFor(() => expect(screen.getByText("Run the whoop skill")).toBeTruthy());
    rerender(<ScheduleModal open={false} onClose={onClose} profile="lens" connectionId={null} />);
    rerender(<ScheduleModal open onClose={onClose} profile="lens" connectionId={null} openJob={{ id: "aa11bb22" }} />);
    await waitFor(() => expect(screen.getByText("python3 run.py")).toBeTruthy());
  });

  it("goes back to a job asked for again after another one was picked", async () => {
    const onClose = vi.fn();
    const { rerender } = render(<ScheduleModal open onClose={onClose} profile="lens" connectionId={null} openJob={{ id: "aa11bb22" }} />);
    await waitFor(() => expect(screen.getByText("python3 run.py")).toBeTruthy());
    fireEvent.click(screen.getByText("WHOOP sync"));
    await waitFor(() => expect(screen.getByText("Run the whoop skill")).toBeTruthy());
    rerender(<ScheduleModal open onClose={onClose} profile="lens" connectionId={null} openJob={{ id: "aa11bb22" }} />);
    await waitFor(() => expect(screen.getByText("python3 run.py")).toBeTruthy());
  });

  it("moves to a job another notification points at while it is already open", async () => {
    const onClose = vi.fn();
    const { rerender } = render(<ScheduleModal open onClose={onClose} profile="lens" connectionId={null} />);
    await waitFor(() => expect(screen.getByText("Run the whoop skill")).toBeTruthy());
    rerender(<ScheduleModal open onClose={onClose} profile="lens" connectionId={null} openJob={{ id: "aa11bb22" }} />);
    await waitFor(() => expect(screen.getByText("python3 run.py")).toBeTruthy());
  });

  it("shows mode and notify state in the detail", async () => {
    open();
    await waitFor(() => expect(screen.getByText("Run the whoop skill")).toBeTruthy());
    expect(screen.getByText("agent")).toBeTruthy();
    expect(screen.getByText("silent — failures still alert")).toBeTruthy();
  });

  it("shows the last-run time in the list once a run has a status", async () => {
    const when = new Date(Date.now() - 90 * 60 * 1000).toISOString();
    invokeMock.mockResolvedValue([
      { id: "ran1", kind: "cron", expression: "0 7 * * *", prompt: "p", title: "Ran job", paused: false, last_run_at: when, last_run_status: "ok", next_fire: null },
    ]);
    open();
    await waitFor(() => expect(screen.getByText("Ran job")).toBeTruthy());
    expect(screen.getByText(lastRunShort(when))).toBeTruthy();
  });

  it("hides the list time for a never-run job that carries a cron anchor timestamp", async () => {
    const anchor = new Date(Date.now() - 90 * 60 * 1000).toISOString();
    invokeMock.mockResolvedValue([
      { id: "new1", kind: "cron", expression: "0 7 * * *", prompt: "p", title: "Fresh job", paused: false, last_run_at: anchor, last_run_status: null, next_fire: null },
    ]);
    open();
    await waitFor(() => expect(screen.getByText("Fresh job")).toBeTruthy());
    expect(screen.queryByText(lastRunShort(anchor))).toBeNull();
  });

  it("pauses the selected job via schedule_set_paused", async () => {
    open();
    await waitFor(() => expect(screen.getByText("Run the whoop skill")).toBeTruthy());
    invokeMock.mockClear();
    invokeMock.mockResolvedValue({ ok: true });
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Pause" })); });
    expect(invokeMock).toHaveBeenCalledWith("schedule_set_paused", { profile: "lens", id: "45188eab", paused: true });
  });
});

describe("ScheduleModal mutation scope", () => {
  it("does not leave a new profile busy when an old profile's action is still pending", async () => {
    let finishOld;
    invokeMock.mockImplementation((method) => method === "schedule_fire"
      ? new Promise((resolve) => { finishOld = resolve; })
      : Promise.resolve(JOBS));
    const { rerender } = render(<ScheduleModal open profile="first" onClose={() => {}} />);
    await screen.findByText("Run the whoop skill");
    fireEvent.click(screen.getByRole("button", { name: "Run now" }));
    expect(screen.getByRole("button", { name: "Run now" })).toBeDisabled();
    rerender(<ScheduleModal open profile="second" onClose={() => {}} />);
    await screen.findByText("Run the whoop skill");
    expect(screen.getByRole("button", { name: "Run now" })).not.toBeDisabled();
    invokeMock.mockClear();
    await act(async () => finishOld({ ok: true }));
    expect(invokeMock).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Run now" })).not.toBeDisabled();
  });
});

describe("ScheduleModal reads like the profile's page", () => {
  it("says when each job runs in words and keeps the cron as a fact", async () => {
    open();
    await waitFor(() => expect(screen.getAllByText("every day at 07:00").length).toBeGreaterThan(0));
    expect(screen.getByText("every day at 22:00")).toBeTruthy();
    await waitFor(() => expect(screen.getByText("0 7 * * *")).toBeTruthy());
  });

  it("marks a failed last run in red words and shows a broken timeout", async () => {
    invokeMock.mockResolvedValue([
      { ...JOBS[0], last_run_at: "2026-10-03T07:00:00Z", last_run_status: "error", run_timeout: null, timeout_error: "'timeout' must be a whole number of seconds" },
    ]);
    open();
    await waitFor(() => expect(screen.getByText("failed")).toBeTruthy());
    expect(screen.getByText("failed").className).toMatch(/failed/);
    await waitFor(() => expect(screen.getByText(/must be a whole number of seconds/)).toBeTruthy());
  });

  it("heads the window with the profile and switches to a sibling panel", async () => {
    const onSection = vi.fn();
    render(<ScheduleModal open onClose={vi.fn()} profile="scout" connectionId={null} owner={{ name: "scout", fold: "house", accent: "#cc4422" }} onSection={onSection} />);
    await waitFor(() => expect(screen.getByRole("tab", { name: /Schedules/ })).toBeTruthy());
    expect(screen.getByRole("tab", { name: /Schedules/ }).getAttribute("aria-selected")).toBe("true");
    expect(screen.getByText("scout")).toBeTruthy();
    fireEvent.click(screen.getByRole("tab", { name: "Memories" }));
    expect(onSection).toHaveBeenCalledWith("memory");
  });
});
