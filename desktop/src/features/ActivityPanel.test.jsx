import { describe, it, expect, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import ActivityPanel from "./ActivityPanel.jsx";
import { ICON_ROLES } from "../../../common/iconRoles.mjs";

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

  it("leads every row with the profile's object, still unless it runs, and keeps the state word's colour", () => {
    mount({ foldByProfile: { builder: "box", doc: "heart", alpi: "alpaca" }, accentByProfile: { builder: "#3ac9f3", doc: "#f36a8a" } });
    const folds = [...document.querySelectorAll("[data-fold]")].map((n) => n.dataset.fold);
    expect(folds).toEqual(expect.arrayContaining(["box", "heart", "honeycomb"]));
    const builder = document.querySelector("[data-fold='box']");
    expect(builder.querySelector("polygon[class*='cell']")).toBeNull();
    expect(screen.getByText(/^approval · /).dataset.tone).toBe("warning");
    expect(screen.getByText(/^failed /).dataset.tone).toBe("danger");
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

describe("ActivityPanel iconography", () => {
  it("heads the panel with the shared Activity role glyph", () => {
    render(<ActivityPanel open onClose={vi.fn()} activity={{ needs_you: [], running: [], scheduled: [] }} />);
    expect(screen.getByText("Activity").parentElement.querySelector("svg").getAttribute("data-icon")).toBe(ICON_ROLES.activity);
  });

  it("draws a running workgroup as the rippling honeycomb in its hub's colour", () => {
    mount({ accentByProfile: { alpi: "#3899e2" } });
    const running = screen.getByRole("region", { name: "Running" });
    const glyph = within(running).getByText("launch-crew · #analyze").closest("button").querySelector("[data-fold]");
    expect(glyph.dataset.fold).toBe("honeycomb");
    const cells = [...glyph.querySelectorAll("polygon")];
    expect(cells.map((c) => c.getAttribute("fill"))).toContain("#3899e2");
    expect(cells.every((c) => c.style.animationDelay !== "")).toBe(true);
  });
});
