import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

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
  it("waits for the schedule with placeholder rows and lines, never the word", async () => {
    invokeMock.mockImplementation(() => new Promise(() => {}));
    open();
    expect(screen.getByRole("progressbar", { name: "Loading schedule" })).toBeTruthy();
    await waitFor(() => expect(document.querySelectorAll("[role=listbox] li[role=presentation] [class*=listRow]").length).toBeGreaterThan(1));
    await waitFor(() => expect(document.querySelector("[aria-hidden=true][class*=reader]")).not.toBeNull());
    expect(document.body.textContent).not.toMatch(/Loading/);
  });

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
    await waitFor(() => expect(screen.getByText(/every day at 07:00/)).toBeTruthy());
    expect(screen.getByText("0 7 * * *")).toBeTruthy();
    expect(screen.getAllByText(/0 7 \* \* \*/)).toHaveLength(1);
  });

  it("marks a failed last run in red words and shows a broken timeout", async () => {
    invokeMock.mockResolvedValue([
      { ...JOBS[0], last_run_at: "2026-10-03T07:00:00Z", last_run_status: "error", run_timeout: null, timeout_error: "'timeout' must be a whole number of seconds" },
    ]);
    open();
    await waitFor(() => expect(screen.getAllByText("failed").length).toBeGreaterThan(0));
    expect(screen.getAllByText("failed").some((el) => /failed/.test(el.className))).toBe(true);
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

const NOW = Date.parse("2026-10-07T12:00:00Z");
const day = (n) => new Date(NOW + n * 86400000).toISOString();
const MIX = [
  { id: "ok1", kind: "cron", expression: "0 6 * * 1", title: "Weekly refresh", description: "Compares every listing", prompt: "refresh", paused: false, last_run_status: "ok", next_fire: day(2) },
  { id: "bad1", kind: "cron", expression: "30 7 * * *", title: "Daily digest", description: "Summarises reviews", prompt: "digest", paused: false, last_run_status: "error", last_run_at: day(-0.1), last_run_message: "timeout", last_ok_at: day(-1), next_fire: day(1) },
  { id: "nap1", kind: "inactivity", after_hours: 168, title: "Nudge", prompt: "nudge", paused: true, next_fire: null },
  { id: "bare1", kind: "cron", expression: "0 9 * * *", prompt: "only a prompt line", paused: false, next_fire: day(1) },
];

describe("ScheduleModal grouped list and reader", () => {
  beforeEach(() => { vi.useFakeTimers({ toFake: ["Date"] }); vi.setSystemTime(NOW); });
  afterEach(() => { vi.useRealTimers(); });

  it("groups the sidebar under Needs you, Active and Paused with the next-run word and no cron", async () => {
    invokeMock.mockResolvedValue(MIX);
    open();
    await waitFor(() => expect(screen.getByText("Needs you · 1")).toBeTruthy());
    expect(screen.getByText("Active · 2")).toBeTruthy();
    expect(screen.getByText("Paused · 1")).toBeTruthy();
    const rows = screen.getAllByRole("option");
    expect(rows.map((r) => r.textContent)[0]).toMatch(/Daily digest.*Summarises reviews.*failed/);
    expect(rows.find((r) => /Weekly refresh/.test(r.textContent)).textContent).toMatch(/in 2d/);
    expect(rows.find((r) => /Nudge/.test(r.textContent)).textContent).toMatch(/paused/);
    for (const r of rows) expect(r.textContent).not.toMatch(/\d+ \d+ \* \*|every day|Every/);
  });

  it("shows no empty description line and keeps the fallback title", async () => {
    invokeMock.mockResolvedValue(MIX);
    open();
    await waitFor(() => expect(screen.getByText("Nudge")).toBeTruthy());
    const nudge = screen.getAllByRole("option").find((r) => /Nudge/.test(r.textContent));
    expect(nudge.querySelectorAll("span").length).toBeLessThanOrEqual(4);
    expect(screen.getByText("only a prompt line", { selector: "span" })).toBeTruthy();
  });

  it("opens a failed job on the banner with a Run now that fires it", async () => {
    invokeMock.mockResolvedValue(MIX);
    open();
    await waitFor(() => expect(screen.getByRole("group", { name: /Last run failed/ })).toBeTruthy());
    expect(screen.getByRole("group", { name: /Last run failed/ }).textContent).toMatch(/Last run failed.*timeout/);
    expect(screen.getAllByRole("button", { name: "Run now" })).toHaveLength(1);
    invokeMock.mockClear();
    invokeMock.mockResolvedValue({ ok: true });
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Run now" })); });
    expect(invokeMock).toHaveBeenCalledWith("schedule_fire", { profile: "lens", id: "bad1" });
  });

  it("lays the reader out as About, When with the cron chip, Next, Last run, Runs, Notify and a PROMPT box", async () => {
    invokeMock.mockResolvedValue(MIX);
    open();
    await waitFor(() => expect(screen.getAllByRole("option").length).toBe(4));
    fireEvent.click(screen.getAllByRole("option").find((r) => /Weekly refresh/.test(r.textContent)));
    await waitFor(() => expect(screen.getByText("Compares every listing", { selector: "dd" })).toBeTruthy());
    const labels = Array.from(document.querySelectorAll("dt")).map((d) => d.textContent);
    expect(labels).toEqual(["about", "when", "next", "last run", "runs", "notify"]);
    expect(screen.getByText("0 6 * * 1")).toBeTruthy();
    expect(screen.getByText("prompt")).toBeTruthy();
    expect(screen.getByText("Prompt")).toBeTruthy();
    expect(screen.getAllByRole("option")).toHaveLength(4);
    expect(screen.queryByRole("button", { name: /edit/i })).toBeNull();
    expect(screen.queryByRole("group", { name: /Last run failed/ })).toBeNull();
  });

  it("omits About for a job without a description", async () => {
    invokeMock.mockResolvedValue([MIX[2]]);
    open();
    await waitFor(() => expect(document.querySelectorAll("dt").length).toBeGreaterThan(0));
    expect(Array.from(document.querySelectorAll("dt")).map((d) => d.textContent)).not.toContain("about");
  });
});
