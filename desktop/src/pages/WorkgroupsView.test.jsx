import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import WorkgroupsView from "./WorkgroupsView.jsx";

const WORKGROUPS = [
  { id: "wg-active", name: "Active hotel", profile: "mira", pipeline_status: "running", pipeline_phase: "content", members: 7, mtime: 20, spent_usd: 1.2, budget_usd: 8 },
  { id: "wg-done", name: "Finished hotel", profile: "mira", pipeline_status: "completed", members: 7, mtime: 10 },
  { id: "wg-paused", name: "Paused hotel", profile: "mira", paused: true, members: 3, mtime: 5 },
  { id: "wg-queued", name: "Queued hotel", profile: "mira", pipeline_status: "queued", queue_position: 2, members: 7, mtime: 4 },
];

describe("WorkgroupsView", () => {
  it("sets its heading in crease type like every other page header", () => {
    const { container } = render(<WorkgroupsView workgroups={WORKGROUPS} profiles={[]} onOpenWorkgroup={vi.fn()} />);
    const h1 = container.querySelector("h1");
    expect(h1.textContent).toBe("Workgroups");
    expect(h1.querySelector("span").className).toMatch(/crease/);
  });

  it("lists every workgroup and opens the selected row", () => {
    const onOpenWorkgroup = vi.fn();
    render(
      <WorkgroupsView
        workgroups={WORKGROUPS}
        profiles={[{ name: "mira", accent: "#3388ff" }]}
        taskByWorkgroup={{
          "mira/wg-done": { state: "open", slug: "stale-task" },
          "mira/wg-queued": { state: "open", slug: "stale-task" },
        }}
        onOpenWorkgroup={onOpenWorkgroup}
      />,
    );

    expect(screen.getByText("4 workgroups")).toBeInTheDocument();
    expect(screen.getByText("1 working · 1 queued · 1 idle · 1 paused")).toBeInTheDocument();
    expect(screen.getByText("Active hotel")).toBeInTheDocument();
    expect(screen.getByText("Working · content")).toBeInTheDocument();
    expect(screen.getAllByText("Idle")).toHaveLength(1);
    expect(screen.getByText("Queued · #2")).toBeInTheDocument();
    expect(screen.queryByText("Complete")).not.toBeInTheDocument();
    expect(screen.queryByText("wg-active")).not.toBeInTheDocument();
    expect(screen.getByText("$1.20")).toBeInTheDocument();
    expect(screen.queryByText("of $8.00")).not.toBeInTheDocument();
    fireEvent.click(screen.getByText("Finished hotel"));
    expect(onOpenWorkgroup).toHaveBeenCalledWith(WORKGROUPS[1]);
  });

  it("captions a row with what finished and what waits, and draws nothing for a row without a note", () => {
    render(
      <WorkgroupsView
        workgroups={[
          { id: "wg-q", name: "Queued hotel", profile: "mira", pipeline_status: "queued", queue_position: 2, pipeline_note: "setup done · media next", mtime: 4 },
          { id: "wg-a", name: "Active hotel", profile: "mira", pipeline_status: "running", pipeline_phase: "media", pipeline_note: "setup done", mtime: 20 },
          { id: "wg-i", name: "Idle hotel", profile: "mira", pipeline_status: "completed", mtime: 10 },
        ]}
      />,
    );

    expect(screen.getByText("setup done · media next")).toBeInTheDocument();
    expect(screen.getByText("setup done")).toBeInTheDocument();
    expect(screen.getByText("Queued · #2")).toBeInTheDocument();
    expect(screen.getByText("Working · media")).toBeInTheDocument();
    expect(document.querySelectorAll('[class*="statusNote"]')).toHaveLength(2);
  });

  it("groups working first, then queued, then paused and idle by last update", () => {
    const now = Math.floor(Date.now() / 1000);
    render(
      <WorkgroupsView
        workgroups={[
          { id: "wg-old-active", name: "Old active", profile: "mira", pipeline_status: "running", mtime: now - 600 },
          { id: "wg-paused", name: "Fresh paused", profile: "mira", paused: true, mtime: now - 60 },
          { id: "wg-idle", name: "Older idle", profile: "mira", pipeline_status: "completed", mtime: now - 3000 },
          { id: "wg-queued", name: "Queued hotel", profile: "mira", pipeline_status: "queued", queue_position: 1, mtime: now - 180 },
        ]}
      />,
    );

    expect(screen.getAllByText(/^(Fresh paused|Queued hotel|Old active|Older idle)$/).map((node) => node.textContent)).toEqual([
      "Old active",
      "Queued hotel",
      "Fresh paused",
      "Older idle",
    ]);
  });

  it("working comes before queued and queued before idle regardless of age", () => {
    const now = Math.floor(Date.now() / 1000);
    render(
      <WorkgroupsView
        workgroups={[
          { id: "wg-idle", name: "Idle hotel", profile: "mira", pipeline_status: "completed", mtime: now - 500 },
          { id: "wg-queued", name: "Queued hotel", profile: "mira", pipeline_status: "queued", queue_position: 1, mtime: now - 490 },
          { id: "wg-active", name: "Working hotel", profile: "mira", pipeline_status: "running", mtime: now - 510 },
        ]}
      />,
    );

    expect(screen.getAllByText(/^(Idle hotel|Queued hotel|Working hotel)$/).map((node) => node.textContent)).toEqual([
      "Working hotel",
      "Queued hotel",
      "Idle hotel",
    ]);
  });

  it("breaks an update tie between queued pipelines by their FIFO position", () => {
    render(
      <WorkgroupsView
        workgroups={[
          { id: "wg-2", name: "Second", profile: "mira", pipeline_status: "queued", queue_position: 2, mtime: Math.floor(Date.now() / 1000) - 300 },
          { id: "wg-1", name: "First", profile: "mira", pipeline_status: "queued", queue_position: 1, mtime: Math.floor(Date.now() / 1000) - 310 },
        ]}
      />,
    );

    expect(screen.getAllByText(/^Queued · #/).map((node) => node.textContent)).toEqual([
      "Queued · #1",
      "Queued · #2",
    ]);
  });

  it("falls back to the open task while an older daemon omits the pipeline phase", () => {
    render(
      <WorkgroupsView
        workgroups={[{
          id: "wg-active", name: "Active hotel", profile: "mira",
          pipeline_status: "running", members: 7, mtime: 20,
        }]}
        taskByWorkgroup={{ "mira/wg-active": { state: "open", slug: "assets" } }}
      />,
    );

    expect(screen.getByText("Working · assets")).toBeInTheDocument();
  });

  it("searches and filters without hiding the complete inventory", () => {
    render(
      <WorkgroupsView
        workgroups={WORKGROUPS}
        taskByWorkgroup={{ "mira/wg-active": { state: "open", slug: "assets" } }}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Active" }));
    expect(screen.getByText("Active hotel")).toBeInTheDocument();
    expect(screen.queryByText("Finished hotel")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "All" }));
    fireEvent.change(screen.getByRole("searchbox", { name: "Search workgroups" }), {
      target: { value: "paused" },
    });
    expect(screen.getByText("Paused hotel")).toBeInTheDocument();
    expect(screen.queryByText("Active hotel")).not.toBeInTheDocument();

    fireEvent.change(screen.getByRole("searchbox", { name: "Search workgroups" }), {
      target: { value: "" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Queued" }));
    expect(screen.getByText("Queued hotel")).toBeInTheDocument();
    expect(screen.queryByText("Finished hotel")).not.toBeInTheDocument();
  });

  it("waits quietly while the connection syncs, then offers to create the first workgroup", async () => {
    const onNewWorkgroup = vi.fn();
    const { rerender } = render(<WorkgroupsView workgroups={[]} profiles={[]} syncing onNewWorkgroup={onNewWorkgroup} />);
    expect((await screen.findByRole("status", { name: "Syncing workgroups" })).querySelectorAll("[class*=listRow]")).toHaveLength(3);
    expect(screen.queryByText(/Syncing workgroups…/)).toBeNull();
    expect(screen.queryByText("No workgroups yet")).toBeNull();
    rerender(<WorkgroupsView workgroups={[]} profiles={[]} syncing={false} onNewWorkgroup={onNewWorkgroup} />);
    expect(screen.getByText("No workgroups yet")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "No workgroups yet" }).parentElement.firstElementChild.dataset.fold).toBe("honeycomb");
    fireEvent.click(screen.getAllByRole("button", { name: "New workgroup" }).at(-1));
    expect(onNewWorkgroup).toHaveBeenCalledTimes(1);
  });

  it("draws each row as the honeycomb in its hub's colour, rippling when working and unfolded in grey when paused", () => {
    render(<WorkgroupsView workgroups={WORKGROUPS} profiles={[{ name: "mira", accent: "#3388ff" }]} />);
    const glyph = (name) => screen.getByText(name).closest("button").querySelector("[data-fold]");
    const cells = (name) => [...glyph(name).querySelectorAll("polygon")];
    expect(glyph("Finished hotel").dataset.fold).toBe("honeycomb");
    expect(cells("Finished hotel").map((c) => c.getAttribute("fill"))).toContain("#3388ff");
    expect(cells("Finished hotel").every((c) => c.getAttribute("fill-opacity") === null && c.style.animationDelay === "")).toBe(true);
    expect(cells("Active hotel").every((c) => c.style.animationDelay !== "")).toBe(true);
    expect(cells("Paused hotel").every((c) => c.getAttribute("fill") === "none")).toBe(true);
    expect(document.querySelector(".ds-diamond")).toBeNull();
  });

  it("heads the page with the honeycomb at header size", () => {
    render(<WorkgroupsView workgroups={WORKGROUPS} profiles={[]} />);
    const glyph = screen.getByRole("heading", { name: "Workgroups" }).parentElement.firstElementChild;
    expect(glyph.dataset.fold).toBe("honeycomb");
    expect(glyph.style.width).toBe("20px");
  });
});
