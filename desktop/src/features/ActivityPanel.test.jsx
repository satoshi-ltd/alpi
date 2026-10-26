import { describe, it, expect, vi } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import ActivityPanel from "./ActivityPanel.jsx";
import { ICON_ROLES } from "../../../common/iconRoles.mjs";

const now = Math.floor(Date.now() / 1000);
const future = (s) => new Date(Date.now() + s * 1000).toISOString();

const fail = (profile, id, title, agoS, extra = {}) => ({ profile, job_id: id, title, next_fire: future(3600), last_run_status: "error", last_run_at: now - agoS, ...extra });

const ACTIVITY = {
  needs_you: [{ kind: "approval", request_id: "r1", profile: "builder", title: "run a shell command", ts: now - 12 }],
  running: [
    { kind: "turn", profile: "alpi", session_id: "s1", title: "deploy summary", started_at: now - 42, source: "schedule" },
    { kind: "workgroup", profile: "alpi", workgroup_id: "wg1", name: "launch-crew", phase: "analyze", phases_done: 1, phases_total: 4 },
  ],
  scheduled: [
    { profile: "doc", job_id: "j1", title: "daily brief", next_fire: future(7200), last_run_status: "ok" },
    { profile: "doc", job_id: "past", title: "overdue", next_fire: future(-600), last_run_status: "ok" },
    fail("sentinel", "a", "Sentinel PR review", 3000, { last_ok_at: new Date((now - 90000) * 1000).toISOString() }),
    fail("sentinel", "b", "Sentinel #force-review watch", 600),
    fail("pulse", "c", "Lobby daily insights", 28800),
    fail("agora", "d", "Agora knowledge refresh", 21600),
  ],
};

function mount(overrides = {}) {
  const props = {
    open: true,
    onClose: vi.fn(),
    activity: ACTIVITY,
    canRetry: true,
    onRetry: vi.fn(async () => {}),
    onReview: vi.fn(),
    onOpenSession: vi.fn(),
    onOpenWorkgroup: vi.fn(),
    onOpenProfile: vi.fn(),
    onOpenJob: vi.fn(),
    ...overrides,
  };
  const view = render(<ActivityPanel {...props} />);
  return { ...props, view };
}

const radio = (name) => screen.getByRole("radio", { name: new RegExp(`^${name}`) });

describe("ActivityPanel dialog", () => {
  it("is a labelled modal dialog with a heading, 500 px wide", () => {
    mount();
    const dialog = screen.getByRole("dialog", { name: "Activity" });
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(dialog.style.width).toBe("500px");
    expect(screen.getByRole("heading", { level: 2, name: "Activity" })).toBeInTheDocument();
  });

  it("closes with Escape", () => {
    const props = mount();
    fireEvent.keyDown(document.activeElement || document.body, { key: "Escape" });
    expect(props.onClose).toHaveBeenCalled();
  });

  it("closes from the header button", () => {
    const props = mount();
    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(props.onClose).toHaveBeenCalled();
  });
});

describe("ActivityPanel sections", () => {
  it("orders needs you, failing, running, upcoming", () => {
    mount();
    const labels = screen.getAllByRole("region").map((r) => r.getAttribute("aria-label"));
    expect(labels).toEqual(["Needs you", "Failing", "Running", "Upcoming"]);
    expect(screen.getByText("Failing · 4")).toBeInTheDocument();
    expect(screen.getByText("Upcoming · 1")).toBeInTheDocument();
  });

  it("keeps Running and Upcoming apart and lists only future runs", () => {
    mount();
    const upcoming = screen.getByRole("region", { name: "Upcoming" });
    expect(within(upcoming).getByText("daily brief")).toBeInTheDocument();
    expect(within(upcoming).queryByText("overdue")).toBeNull();
    expect(within(upcoming).queryByText("Lobby daily insights")).toBeNull();
    expect(within(screen.getByRole("region", { name: "Running" })).queryByText("daily brief")).toBeNull();
  });

  it("moves the profile into the meta line", () => {
    mount();
    const upcoming = screen.getByRole("region", { name: "Upcoming" });
    expect(within(upcoming).getByText("daily brief")).toBeInTheDocument();
    expect(within(upcoming).getByText(/^doc · /)).toBeInTheDocument();
    const running = screen.getByRole("region", { name: "Running" });
    expect(within(running).getByText("deploy summary")).toBeInTheDocument();
    expect(within(running).getByText(/^alpi · 42s|^alpi · now|^alpi · 0m/)).toBeInTheDocument();
  });

  it("leads every row with the profile's object", () => {
    mount({ foldByProfile: { builder: "box", doc: "heart", alpi: "alpaca" }, accentByProfile: { builder: "#3ac9f3", doc: "#f36a8a" } });
    const folds = [...document.querySelectorAll("[data-fold]")].map((n) => n.dataset.fold);
    expect(folds).toEqual(expect.arrayContaining(["box", "heart", "honeycomb"]));
    expect(document.querySelector("[data-fold='box']").querySelector("polygon[class*='cell']")).toBeNull();
  });

  it("paints the word failed red and the rest of the meta line plain", () => {
    mount();
    const failed = screen.getAllByText(/^failed /);
    expect(failed.length).toBe(2);
    expect(failed.every((n) => n.dataset.tone === "danger")).toBe(true);
    const meta = failed[1].parentElement;
    expect(meta.textContent).toMatch(/^failed 50m ago · last ok 1d ago$/);
    expect(meta.dataset.tone).toBeUndefined();
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
    fireEvent.click(within(running).getByText("deploy summary"));
    expect(props.onOpenSession).toHaveBeenCalledWith("alpi", "s1");
    fireEvent.click(within(running).getByText("launch-crew · #analyze"));
    expect(props.onOpenWorkgroup).toHaveBeenCalledWith("alpi", "wg1");
    expect(within(running).getByText(/phase 2 of 4/)).toBeInTheDocument();
  });

  it("opens each running job by its own id instead of opening an empty chat", () => {
    const onOpenJob = vi.fn();
    const props = mount({ onOpenJob, activity: {
      needs_you: [], scheduled: [], running: [
        { kind: "turn", profile: "doc", job_id: "j1", title: "First job", source: "schedule" },
        { kind: "turn", profile: "doc", job_id: "j2", title: "Second job", source: "schedule" },
      ],
    } });
    fireEvent.click(screen.getByText("First job"));
    fireEvent.click(screen.getByText("Second job"));
    expect(onOpenJob.mock.calls).toEqual([["doc", "j1"], ["doc", "j2"]]);
    expect(props.onOpenSession).not.toHaveBeenCalled();
  });

  it("opens an upcoming job, and the profile when the host has no job route", () => {
    const props = mount();
    fireEvent.click(screen.getByText("daily brief"));
    expect(props.onOpenJob).toHaveBeenCalledWith("doc", "j1");
    expect(props.onClose).toHaveBeenCalled();
    const bare = mount({ onOpenJob: undefined });
    fireEvent.click(screen.getAllByText("daily brief").at(-1));
    expect(bare.onOpenProfile).toHaveBeenCalledWith("doc");
  });
});

describe("ActivityPanel filters", () => {
  it("shows counts on five chips in a radiogroup", () => {
    mount();
    const group = screen.getByRole("radiogroup", { name: "Filter activity" });
    const chips = within(group).getAllByRole("radio");
    expect(chips.map((c) => c.textContent)).toEqual(["All8", "Needs you1", "Failing4", "Running2", "Upcoming1"]);
    expect(radio("All")).toHaveAttribute("aria-checked", "true");
    expect(radio("Failing").querySelector("[data-tone='danger']")).not.toBeNull();
  });

  it("narrows the list to one section", () => {
    mount();
    fireEvent.click(radio("Running"));
    expect(screen.getAllByRole("region").map((r) => r.getAttribute("aria-label"))).toEqual(["Running"]);
    fireEvent.click(radio("Upcoming"));
    expect(screen.getAllByRole("region").map((r) => r.getAttribute("aria-label"))).toEqual(["Upcoming"]);
    fireEvent.click(radio("All"));
    expect(screen.getAllByRole("region")).toHaveLength(4);
  });

  it("walks the chips with the arrow keys, Home and End, wrapping, with one tab stop", () => {
    mount();
    const stops = () => screen.getAllByRole("radio").filter((r) => r.tabIndex === 0);
    expect(stops()).toHaveLength(1);
    fireEvent.keyDown(radio("All"), { key: "ArrowRight" });
    expect(radio("Needs you")).toHaveAttribute("aria-checked", "true");
    expect(document.activeElement).toBe(radio("Needs you"));
    fireEvent.keyDown(radio("Needs you"), { key: "ArrowLeft" });
    fireEvent.keyDown(radio("All"), { key: "ArrowLeft" });
    expect(radio("Upcoming")).toHaveAttribute("aria-checked", "true");
    fireEvent.keyDown(radio("Upcoming"), { key: "ArrowRight" });
    expect(radio("All")).toHaveAttribute("aria-checked", "true");
    fireEvent.keyDown(radio("All"), { key: "End" });
    expect(radio("Upcoming")).toHaveAttribute("aria-checked", "true");
    fireEvent.keyDown(radio("Upcoming"), { key: "Home" });
    expect(radio("All")).toHaveAttribute("aria-checked", "true");
    expect(stops()).toHaveLength(1);
  });

  it("says what is empty under a filter", () => {
    mount({ activity: { needs_you: [], running: [ACTIVITY.running[0]], scheduled: [] } });
    fireEvent.click(radio("Failing"));
    expect(screen.getByText("No failing jobs")).toBeInTheDocument();
    fireEvent.click(radio("Needs you"));
    expect(screen.getByText("Nothing needs you")).toBeInTheDocument();
    fireEvent.click(radio("Upcoming"));
    expect(screen.getByText("Nothing upcoming")).toBeInTheDocument();
  });
});

describe("ActivityPanel empty states", () => {
  it("says nothing needs you when only running and upcoming remain", () => {
    mount({ activity: { needs_you: [], running: [ACTIVITY.running[0]], scheduled: [ACTIVITY.scheduled[0]] } });
    expect(screen.getByText("Nothing needs you now")).toBeInTheDocument();
  });

  it("does not say it while something needs you or fails", () => {
    mount();
    expect(screen.queryByText("Nothing needs you now")).toBeNull();
  });

  it("says so when nothing is going on, without filters", () => {
    mount({ activity: { needs_you: [], running: [], scheduled: [] } });
    expect(screen.getByText(/Nothing running/)).toBeInTheDocument();
    expect(screen.queryByRole("radiogroup")).toBeNull();
  });
});

describe("ActivityPanel failing groups", () => {
  it("groups per profile, newest first, with count and latest time", () => {
    mount();
    const failing = screen.getByRole("region", { name: "Failing" });
    const names = within(failing).getAllByRole("button", { name: /job/ }).map((b) => b.textContent);
    expect(names[0]).toMatch(/^sentinel2 jobs10m ago$/);
    expect(names[1]).toMatch(/^agora1 job6h ago$/);
    expect(names[2]).toMatch(/^pulse1 job8h ago$/);
  });

  it("expands the first group only and drops the profile from the job titles", () => {
    mount();
    const failing = screen.getByRole("region", { name: "Failing" });
    const [first, second] = within(failing).getAllByRole("button", { name: /job/ });
    expect(first).toHaveAttribute("aria-expanded", "true");
    expect(second).toHaveAttribute("aria-expanded", "false");
    expect(within(failing).getByText("#force-review watch")).toBeInTheDocument();
    expect(within(failing).getByText("PR review")).toBeInTheDocument();
    expect(within(failing).queryByText("knowledge refresh")).toBeNull();
  });

  it("toggles a group as a button with aria-expanded", () => {
    mount();
    const failing = screen.getByRole("region", { name: "Failing" });
    const second = () => within(failing).getAllByRole("button", { name: /job/ })[1];
    fireEvent.click(second());
    expect(second()).toHaveAttribute("aria-expanded", "true");
    expect(within(failing).getByText("knowledge refresh")).toBeInTheDocument();
    fireEvent.click(second());
    expect(within(failing).queryByText("knowledge refresh")).toBeNull();
    const first = within(failing).getAllByRole("button", { name: /job/ })[0];
    expect(first.tagName).toBe("BUTTON");
    expect(first.getAttribute("aria-controls")).toBeTruthy();
    fireEvent.click(first);
    expect(first).toHaveAttribute("aria-expanded", "false");
  });

  it("opens a failing job from its row and from Open", () => {
    const props = mount();
    fireEvent.click(screen.getByText("#force-review watch"));
    expect(props.onOpenJob).toHaveBeenLastCalledWith("sentinel", "b");
    const row = screen.getByText("PR review").closest("li");
    fireEvent.click(within(row).getByRole("button", { name: "Open" }));
    expect(props.onOpenJob).toHaveBeenLastCalledWith("sentinel", "a");
  });

  it("puts the long list behind collapsed groups", () => {
    const many = Array.from({ length: 40 }, (_, i) => fail(`p${i % 8}`, `j${i}`, `Job number ${i} with a very long title that has to be cut with an ellipsis and a tooltip`, 100 + i));
    mount({ activity: { needs_you: [], running: [], scheduled: many } });
    const failing = screen.getByRole("region", { name: "Failing" });
    expect(within(failing).getAllByRole("button", { name: /jobs?/ })).toHaveLength(8);
    expect(within(failing).getAllByRole("listitem").filter((li) => li.dataset.nested !== undefined)).toHaveLength(5);
    const title = screen.getAllByText(/very long title/)[0];
    expect(title).toHaveAttribute("title", expect.stringContaining("very long title"));
    expect(screen.getByText("Failing · 40")).toBeInTheDocument();
  });
});

describe("ActivityPanel retry", () => {
  it("retries one job without closing the panel", async () => {
    const props = mount();
    const row = screen.getByText("PR review").closest("li");
    fireEvent.click(within(row).getByRole("button", { name: "Retry" }));
    await waitFor(() => expect(props.onRetry).toHaveBeenCalledWith("sentinel", "a"));
    expect(props.onClose).not.toHaveBeenCalled();
  });

  it("hides Retry and Retry all for a member", () => {
    mount({ canRetry: false });
    expect(screen.queryByRole("button", { name: "Retry" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Retry all" })).toBeNull();
    expect(screen.getAllByRole("button", { name: "Open" }).length).toBeGreaterThan(0);
  });

  it("hides Retry when the host gives no way to fire", () => {
    mount({ onRetry: null });
    expect(screen.queryByRole("button", { name: "Retry all" })).toBeNull();
  });

  it.each(["forbidden", "-32601 method not found"])("hides Retry for good once the daemon answers %s", async (reason) => {
    const onRetry = vi.fn(async () => { throw new Error(reason); });
    mount({ onRetry });
    const row = screen.getByText("PR review").closest("li");
    fireEvent.click(within(row).getByRole("button", { name: "Retry" }));
    await waitFor(() => expect(screen.queryByRole("button", { name: "Retry" })).toBeNull());
    expect(screen.queryByRole("button", { name: "Retry all" })).toBeNull();
  });

  it("asks before retrying all, then fires every failing job in order", async () => {
    const props = mount();
    fireEvent.click(screen.getByRole("button", { name: "Retry all" }));
    expect(props.onRetry).not.toHaveBeenCalled();
    expect(screen.getByText("Retry 4 jobs?")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.getByRole("button", { name: "Retry all" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Retry all" }));
    fireEvent.click(within(screen.getByText(/^Retry \d+ jobs?\?$/).parentElement).getByRole("button", { name: "Retry" }));
    await waitFor(() => expect(props.onRetry).toHaveBeenCalledTimes(4));
    expect(props.onRetry.mock.calls.map((c) => c[1])).toEqual(["b", "a", "d", "c"]);
  });

  it("stops retrying all at the first forbidden answer", async () => {
    const onRetry = vi.fn(async () => { throw new Error("forbidden"); });
    mount({ onRetry });
    fireEvent.click(screen.getByRole("button", { name: "Retry all" }));
    fireEvent.click(within(screen.getByText(/^Retry \d+ jobs?\?$/).parentElement).getByRole("button", { name: "Retry" }));
    await waitFor(() => expect(screen.queryByRole("button", { name: "Retry all" })).toBeNull());
    expect(onRetry).toHaveBeenCalledTimes(1);
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
