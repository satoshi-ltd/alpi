import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import WorkgroupsView from "./WorkgroupsView.jsx";

const WORKGROUPS = [
  { id: "wg-active", name: "Active hotel", profile: "mira", members: 7, mtime: 20, spent_usd: 1.2, budget_usd: 8 },
  { id: "wg-done", name: "Finished hotel", profile: "mira", members: 7, mtime: 10 },
  { id: "wg-paused", name: "Paused hotel", profile: "mira", paused: true, members: 3, mtime: 5 },
];

describe("WorkgroupsView", () => {
  it("lists every workgroup and opens the selected row", () => {
    const onOpenWorkgroup = vi.fn();
    render(
      <WorkgroupsView
        workgroups={WORKGROUPS}
        profiles={[{ name: "mira", accent: "#3388ff" }]}
        taskByWorkgroup={{ "mira/wg-active": { state: "open", slug: "assets" } }}
        onOpenWorkgroup={onOpenWorkgroup}
      />,
    );

    expect(screen.getByText("3 total")).toBeInTheDocument();
    expect(screen.getByText("Active hotel")).toBeInTheDocument();
    expect(screen.getByText("Working")).toBeInTheDocument();
    expect(screen.getAllByText("Idle")).toHaveLength(1);
    expect(screen.queryByText("Complete")).not.toBeInTheDocument();
    fireEvent.click(screen.getByText("Finished hotel"));
    expect(onOpenWorkgroup).toHaveBeenCalledWith(WORKGROUPS[1]);
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
  });
});
