import { describe, it, expect, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import ActivityPanel from "./ActivityPanel.jsx";

const now = Math.floor(Date.now() / 1000);

const ACTIVITY = {
  needs_you: [{ kind: "approval", request_id: "r1", profile: "builder", title: "run a shell command", ts: now - 12 }],
  running: [
    { kind: "turn", profile: "alpi", session_id: "s1", title: "deploy summary", started_at: now - 42, source: "schedule" },
    { kind: "workgroup", profile: "alpi", workgroup_id: "wg1", name: "launch-crew", phase: "analyze", phases_done: 1, phases_total: 4 },
  ],
  scheduled: [
    { profile: "doc", job_id: "j1", title: "daily brief", next_fire: new Date(Date.now() + 7200e3).toISOString(), last_run_status: "ok" },
    { profile: "doc", job_id: "j2", title: "weekly labs", next_fire: null, last_run_status: "error", last_run_at: now - 3600 },
  ],
};

function mount(overrides = {}) {
  const props = {
    open: true,
    onClose: vi.fn(),
    activity: ACTIVITY,
    onReview: vi.fn(),
    onOpenSession: vi.fn(),
    onOpenWorkgroup: vi.fn(),
    onOpenProfile: vi.fn(),
    ...overrides,
  };
  render(<ActivityPanel {...props} />);
  return props;
}

describe("ActivityPanel", () => {
  it("orders needs you, running, scheduled", () => {
    mount();
    const labels = screen.getAllByRole("region").map((r) => r.getAttribute("aria-label"));
    expect(labels).toEqual(["Needs you", "Running", "Scheduled"]);
    expect(screen.getByText("Needs you · 1")).toBeInTheDocument();
    expect(screen.getByText("Running · 2")).toBeInTheDocument();
  });

  it("Review hands the request to the approval flow and closes the panel", () => {
    const props = mount();
    fireEvent.click(screen.getByRole("button", { name: "Review" }));
    expect(props.onReview).toHaveBeenCalledWith(ACTIVITY.needs_you[0]);
    expect(props.onClose).toHaveBeenCalled();
  });

  it("opens the running session and workgroup", () => {
    const props = mount();
    const running = screen.getByRole("region", { name: "Running" });
    fireEvent.click(within(running).getByText("alpi · deploy summary"));
    expect(props.onOpenSession).toHaveBeenCalledWith("alpi", "s1");
    fireEvent.click(within(running).getByText("launch-crew · #analyze"));
    expect(props.onOpenWorkgroup).toHaveBeenCalledWith("alpi", "wg1");
    expect(within(running).getByText("phase 2 of 4")).toBeInTheDocument();
  });

  it("marks a recent scheduled failure", () => {
    mount();
    const scheduled = screen.getByRole("region", { name: "Scheduled" });
    expect(within(scheduled).getByText("failed 1h ago")).toBeInTheDocument();
  });

  it("says so when nothing is going on", () => {
    mount({ activity: { needs_you: [], running: [], scheduled: [] } });
    expect(screen.getByText(/Nothing running/)).toBeInTheDocument();
  });
});
