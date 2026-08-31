import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import WorkgroupsView from "./WorkgroupsView.jsx";

const WORKGROUPS = [
  { id: "wg-active", name: "Active hotel", profile: "mira", pipeline_status: "running", members: 7, mtime: 20, spent_usd: 1.2, budget_usd: 8 },
  { id: "wg-done", name: "Finished hotel", profile: "mira", pipeline_status: "completed", members: 7, mtime: 10 },
  { id: "wg-paused", name: "Paused hotel", profile: "mira", paused: true, members: 3, mtime: 5 },
  { id: "wg-queued", name: "Queued hotel", profile: "mira", pipeline_status: "queued", queue_position: 2, members: 7, mtime: 4 },
];

describe("WorkgroupsView", () => {
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
    expect(screen.getByText("Working")).toBeInTheDocument();
    expect(screen.getAllByText("Idle")).toHaveLength(1);
    expect(screen.getByText("Queued · #2")).toBeInTheDocument();
    expect(screen.queryByText("Complete")).not.toBeInTheDocument();
    expect(screen.queryByText("wg-active")).not.toBeInTheDocument();
    expect(screen.getByText("$1.20")).toBeInTheDocument();
    expect(screen.queryByText("of $8.00")).not.toBeInTheDocument();
    fireEvent.click(screen.getByText("Finished hotel"));
    expect(onOpenWorkgroup).toHaveBeenCalledWith(WORKGROUPS[1]);
  });

  it("orders queued pipelines by their FIFO position", () => {
    render(
      <WorkgroupsView
        workgroups={[
          { id: "wg-2", name: "Second", profile: "mira", pipeline_status: "queued", queue_position: 2, mtime: 20 },
          { id: "wg-1", name: "First", profile: "mira", pipeline_status: "queued", queue_position: 1, mtime: 10 },
        ]}
      />,
    );

    expect(screen.getAllByText(/^Queued · #/).map((node) => node.textContent)).toEqual([
      "Queued · #1",
      "Queued · #2",
    ]);
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
});
