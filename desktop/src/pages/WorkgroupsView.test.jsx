import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import WorkgroupsView from "./WorkgroupsView.jsx";
import { nameTone } from "../../../common/name.mjs";
import { palettes } from "../../../common/tokens.mjs";

const WORKGROUPS = [
  { id: "wg-active", name: "Active hotel", profile: "mira", pipeline_status: "running", pipeline_phase: "content", members: 7, mtime: 20, spent_usd: 1.2, budget_usd: 8 },
  { id: "wg-done", name: "Finished hotel", profile: "mira", pipeline_status: "completed", members: 7, mtime: 10 },
  { id: "wg-paused", name: "Paused hotel", profile: "mira", paused: true, members: 3, mtime: 5 },
  { id: "wg-queued", name: "Queued hotel", profile: "mira", pipeline_status: "queued", queue_position: 2, members: 7, mtime: 4 },
];

describe("WorkgroupsView", () => {
  it("sets its heading in the name face like every other page header", () => {
    const { container } = render(<WorkgroupsView workgroups={WORKGROUPS} profiles={[]} onOpenWorkgroup={vi.fn()} />);
    const h1 = container.querySelector("h1");
    expect(h1.textContent).toBe("Workgroups");
    expect(h1.className).toBe("ds-name");
    expect(h1.style.getPropertyValue("--name-light")).toBe("var(--ink-3)");
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
    expect(screen.getByRole("heading", { name: "No workgroups yet" }).parentElement.firstElementChild.dataset.shape).toBe("honeycomb");
    fireEvent.click(screen.getAllByRole("button", { name: "New workgroup" }).at(-1));
    expect(onNewWorkgroup).toHaveBeenCalledTimes(1);
  });

  it("draws each row as the neutral soft honeycomb, never the hub's colour at rest, in the state of its pipeline", () => {
    render(<WorkgroupsView workgroups={WORKGROUPS} profiles={[{ name: "mira", accent: "#3388ff" }]} />);
    const glyph = (name) => screen.getByText(name).closest("button").querySelector("[data-shape]");
    const cells = (name) => [...glyph(name).querySelectorAll("[data-cell]")];
    expect(glyph("Finished hotel").dataset.mark).toBe("soft-honeycomb");
    expect(glyph("Finished hotel").dataset.state).toBe("idle");
    expect(cells("Finished hotel").map((c) => c.getAttribute("fill"))).toEqual(["var(--ink-3)", "var(--ink-3)", "var(--ink-3)"]);
    expect(glyph("Active hotel").dataset.state).toBe("running");
    expect(glyph("Queued hotel").dataset.state).toBe("queued");
    expect(cells("Queued hotel").every((c) => c.getAttribute("fill") === "none" && c.getAttribute("stroke") === "var(--ink-3)")).toBe(true);
    expect(glyph("Paused hotel").dataset.state).toBe("paused");
    expect(cells("Paused hotel").every((c) => c.querySelector("path").getAttribute("fill") === "none")).toBe(true);
  });

  it("lights a running row's phase cell in the hub's colour, never the owner's, and names the owner in the status", () => {
    const running = {
      id: "wg-run", name: "Running hotel", profile: "mira", pipeline_status: "running", pipeline_phase: "media",
      phase_map: { media: { owner: "lingo" } }, mtime: 30,
    };
    render(
      <WorkgroupsView
        workgroups={[running]}
        profiles={[{ name: "mira", accent: "#3388ff" }, { name: "lingo", accent: "#f36a8a" }]}
        runByWorkgroup={{ "mira/wg-run": { phase: "media", phasesDone: 1, phasesTotal: 3 } }}
      />,
    );
    const glyph = screen.getByText("Running hotel").closest("button").querySelector("[data-shape]");
    expect(glyph.dataset.cell).toBe("top");
    expect(glyph.querySelector("[data-lead]").getAttribute("fill")).toBe("var(--wg-lit)");
    expect(glyph.style.getPropertyValue("--wg-lit-light")).toBe(nameTone("#3388ff", palettes.light.bgPane));
    expect(glyph.innerHTML).not.toContain("#f36a8a");
    expect(screen.getByText("Working · media · @lingo")).toBeInTheDocument();
  });

  it("sets workgroup names in the same row type as a profile row, never bold, the name face or the hub's tone", () => {
    render(<WorkgroupsView workgroups={WORKGROUPS} profiles={[{ name: "mira", accent: "#3388ff" }]} />);
    const active = screen.getByText("Active hotel");
    expect(active.tagName).toBe("SPAN");
    expect(active.className).toBe("sb-name");
    expect(active.getAttribute("style")).toBeNull();
  });

  it("asks for attention with the needs-you honeycomb when the pipeline is blocked", () => {
    render(<WorkgroupsView workgroups={[{ id: "wg-b", name: "Blocked hotel", profile: "mira", pipeline_status: "blocked", mtime: 1 }]} profiles={[{ name: "mira", accent: "#3388ff" }]} />);
    expect(screen.getByText("Blocked hotel").closest("button").querySelector("[data-shape]").dataset.state).toBe("needs");
  });

  it("says who the blocked phase waits on", () => {
    const blocked = { id: "wg-b", name: "Blocked hotel", profile: "mira", pipeline_status: "blocked", pipeline_phase: "approval", phase_map: { approval: { owner: "@yuri" } }, mtime: 1 };
    render(<WorkgroupsView workgroups={[blocked]} profiles={[{ name: "mira", accent: "#3388ff" }]} />);
    expect(screen.getByText("Needs you · approval · @yuri")).toBeInTheDocument();
  });

  it("marks a blocked row with its own warning status, apart from a failed task's danger", () => {
    const blocked = { id: "wg-b", name: "Blocked hotel", profile: "mira", pipeline_status: "blocked", pipeline_phase: "approval", phase_map: { approval: { owner: "yuri" } }, mtime: 2 };
    const failed = { id: "wg-f", name: "Failed hotel", profile: "mira", mtime: 1 };
    render(<WorkgroupsView workgroups={[blocked, failed]} taskByWorkgroup={{ "mira/wg-f": { state: "error", slug: "x" } }} />);
    const needs = screen.getByText("Needs you · approval · @yuri");
    expect(needs.className).toMatch(/status_needs/);
    expect(needs.className).not.toMatch(/status_error/);
    expect(screen.getByText("Needs attention").className).toMatch(/status_error/);
    expect(screen.getByText(/1 need you · 1 need attention/)).toBeInTheDocument();
    const css = readFileSync(join(import.meta.dirname, "WorkgroupsView.module.css"), "utf8");
    expect(css).toContain(".status_needs { color: var(--c-warning-text); }");
    expect(css).toContain(".status_needs > span { background: var(--c-warning); }");
    expect(css).toContain(".status_error > span { background: var(--c-danger); }");
  });

  it("takes the step and its owner from the same phase", () => {
    const wg = {
      id: "wg-r", name: "Running hotel", profile: "mira", pipeline_status: "running", pipeline_phase: "content",
      phase_map: { content: { owner: "quill" }, media: { owner: "lingo" } }, mtime: 3,
    };
    render(<WorkgroupsView workgroups={[wg]} runByWorkgroup={{ "mira/wg-r": { phase: "media", phasesDone: 1, phasesTotal: 3 } }} />);
    expect(screen.getByText("Working · media · @lingo")).toBeInTheDocument();
  });

  it("ellipsizes a long name through the global row class", () => {
    const css = readFileSync(join(import.meta.dirname, "WorkgroupsView.module.css"), "utf8");
    expect(css).toContain(".identity :global(.sb-name) { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }");
    expect(css).not.toMatch(/\.identity \.sb-name/);
  });

  it("heads the page with the neutral honeycomb at header size", () => {
    render(<WorkgroupsView workgroups={WORKGROUPS} profiles={[]} />);
    const glyph = screen.getByRole("heading", { name: "Workgroups" }).parentElement.firstElementChild;
    expect(glyph.dataset.shape).toBe("honeycomb");
    expect(glyph.style.width).toBe("28px");
    expect(glyph.querySelector("[data-cell]").getAttribute("fill")).toBe("var(--ink-3)");
  });
});

it("warns about stale workgroups, preserves rows and offers a retry until recovery", () => {
  const onRefresh = vi.fn();
  const { rerender } = render(<WorkgroupsView workgroups={WORKGROUPS} stale onRefresh={onRefresh} />);
  expect(screen.getByText("Workgroups may be out of date. Retrying automatically.")).toBeInTheDocument();
  expect(screen.getByText("Active hotel")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Retry" }));
  expect(onRefresh).toHaveBeenCalledOnce();
  rerender(<WorkgroupsView workgroups={WORKGROUPS} stale syncing onRefresh={onRefresh} />);
  expect(screen.getByText("Updating workgroups… Displayed data may be out of date.")).toBeInTheDocument();
  rerender(<WorkgroupsView workgroups={WORKGROUPS} onRefresh={onRefresh} />);
  expect(screen.queryByRole("button", { name: "Retry" })).not.toBeInTheDocument();
});
