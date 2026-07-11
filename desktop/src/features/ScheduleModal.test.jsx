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
