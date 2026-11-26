import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import WorkgroupsView from "./WorkgroupsView.jsx";
import styles from "./WorkgroupsView.module.css";
import { nameTone } from "../../../common/name.mjs";
import { palettes } from "../../../common/tokens.mjs";

const WORKGROUPS = [
  { id: "wg-active", name: "Active hotel", profile: "mira", pipeline_status: "running", pipeline_phase: "content", members: 7, mtime: 20, spent_usd: 1.2, budget_usd: 8 },
  { id: "wg-done", name: "Finished hotel", profile: "mira", pipeline_status: "completed", members: 7, mtime: 10 },
  { id: "wg-paused", name: "Paused hotel", profile: "mira", paused: true, members: 3, mtime: 5 },
  { id: "wg-queued", name: "Queued hotel", profile: "mira", pipeline_status: "queued", queue_position: 2, members: 7, mtime: 4 },
];

describe("WorkgroupsView", () => {
  it("uses the compact page header every other page wears, with no details popover", () => {
    const { container } = render(<WorkgroupsView workgroups={WORKGROUPS} profiles={[]} onOpenWorkgroup={vi.fn()} />);
    const header = container.querySelector("header.ds-chat-header");
    const h1 = header.querySelector("h1");
    expect(h1.textContent).toBe("Workgroups");
    expect(h1.className).toBe("ds-name");
    expect(header.querySelector(".title-row [data-mark='soft-honeycomb']")).not.toBeNull();
    expect(header.querySelector("[role='dialog']")).toBeNull();
    expect(header.querySelector("[aria-haspopup]")).toBeNull();
    expect(container.querySelector(".meta-row")).toBeNull();
  });

  it("counts the whole set on each filter, dims an empty one and drops the N of M counter", () => {
    render(<WorkgroupsView workgroups={WORKGROUPS} profiles={[]} />);
    expect(screen.getByRole("button", { name: "All, 4" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Active, 1" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Queued, 1" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Paused, 1" })).toBeEnabled();
    expect(screen.queryByText(/\d+ of \d+/)).toBeNull();
    fireEvent.change(screen.getByRole("searchbox", { name: "Search workgroups" }), { target: { value: "paused" } });
    expect(screen.getByRole("button", { name: "All, 4" })).toBeInTheDocument();
  });

  it("disables a filter with nothing in it, the creator's all-idle day", () => {
    const idle = Array.from({ length: 3 }, (_, i) => ({ id: `wg-${i}`, name: `Idle ${i}`, profile: "mira", pipeline_status: "completed", mtime: i }));
    render(<WorkgroupsView workgroups={idle} profiles={[]} />);
    expect(screen.getByRole("button", { name: "Active, 0" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Queued, 0" })).toBeDisabled();
    expect(screen.getByRole("group", { name: "Idle" })).toBeInTheDocument();
    expect(screen.queryByRole("group", { name: "Working" })).toBeNull();
  });

  it("files the rows of All under their state with a count, needs you and attention first", () => {
    render(
      <WorkgroupsView
        workgroups={[
          { id: "wg-i", name: "Idle hotel", profile: "mira", pipeline_status: "completed", mtime: 9 },
          { id: "wg-b", name: "Blocked hotel", profile: "mira", pipeline_status: "blocked", mtime: 1 },
          { id: "wg-f", name: "Failed hotel", profile: "mira", mtime: 2 },
          { id: "wg-r", name: "Running hotel", profile: "mira", pipeline_status: "running", mtime: 3 },
          { id: "wg-q", name: "Queued hotel", profile: "mira", pipeline_status: "queued", queue_position: 1, mtime: 4 },
          { id: "wg-p", name: "Paused hotel", profile: "mira", paused: true, mtime: 5 },
        ]}
        taskByWorkgroup={{ "mira/wg-f": { state: "error", slug: "x" } }}
      />,
    );
    const groups = screen.getAllByRole("group");
    expect(groups.map((g) => g.getAttribute("aria-label"))).toEqual(["Needs you", "Working", "Queued", "Idle", "Paused"]);
    expect(groups[0].textContent).toMatch(/^Needs you2/);
    expect(groups[0].firstElementChild.className).toMatch(/groupNeeds/);
    fireEvent.click(screen.getByRole("button", { name: "Queued, 1" }));
    expect(screen.queryAllByRole("group").map((g) => g.getAttribute("aria-label"))).toEqual([null]);
    expect(screen.getByText("Queued hotel")).toBeInTheDocument();
  });

  it("answers an empty search with one line naming the filter", () => {
    render(<WorkgroupsView workgroups={WORKGROUPS} profiles={[]} />);
    fireEvent.click(screen.getByRole("button", { name: "Paused, 1" }));
    fireEvent.change(screen.getByRole("searchbox", { name: "Search workgroups" }), { target: { value: "deploy" } });
    expect(screen.getByText("No paused workgroup matches deploy.")).toBeInTheDocument();
    expect(screen.queryAllByRole("group")).toHaveLength(0);
  });

  it("keeps a queued or working label whole, titled, and lets the note give way first", () => {
    render(
      <WorkgroupsView
        workgroups={[
          { id: "wg-q", name: "Queued hotel", profile: "mira", pipeline_status: "queued", queue_position: 12, pipeline_note: "setup done · media next", mtime: 4 },
          { id: "wg-r", name: "Running hotel", profile: "mira", pipeline_status: "running", pipeline_phase: "build", phase_map: { build: { owner: "@pixel" } }, pipeline_note: "setup done", mtime: 5 },
        ]}
      />,
    );
    const queued = screen.getByText("Queued · #12");
    expect(queued.className).toBe(styles.statusText);
    expect(queued.parentElement).toHaveAttribute("title", "Queued · #12");
    expect(queued.parentElement.className).toBe(`${styles.status} ${styles.status_queued}`);
    expect(queued.previousElementSibling.className).toBe(styles.dot);
    expect(screen.getByText("setup done · media next").className).toBe(styles.statusNote);
    expect(screen.getByText("Working · build · @pixel").parentElement).toHaveAttribute("title", "Working · build · @pixel");
    const css = readFileSync(join(import.meta.dirname, "WorkgroupsView.module.css"), "utf8");
    expect(css).toMatch(/\.status \{ flex: 0 0 auto; max-width: 100%; min-width: 0;/);
    expect(css).toMatch(/\.statusText \{ min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; \}/);
    expect(css).toMatch(/\.statusNote \{ flex: 1 1 0; min-width: 0; overflow: hidden; text-overflow: ellipsis;/);
    expect(css).toMatch(/@media \(max-width: 900px\) \{\s*\.tableHead, \.row \{ grid-template-columns: minmax\(180px, 1fr\) minmax\(12rem, 1\.2fr\)/);
    expect(css).toMatch(/\.tableHead, \.row \{ display: grid; grid-template-columns: minmax\(200px, 1fr\) minmax\(15rem, 1\.4fr\)/);
  });

  it("drops the repeated Idle from idle rows and keeps their note", () => {
    render(<WorkgroupsView workgroups={[{ id: "wg-i", name: "Idle hotel", profile: "mira", pipeline_status: "completed", pipeline_note: "last run done", mtime: 1 }]} />);
    const row = screen.getByText("Idle hotel").closest("button");
    expect(row.textContent).not.toMatch(/Idle(?! hotel)/);
    expect(screen.getByText("last run done")).toBeInTheDocument();
    expect(row.querySelector('[class*="status_"]')).toBeNull();
  });

  it("centres the table column under a header that runs the pane", () => {
    const css = readFileSync(join(import.meta.dirname, "WorkgroupsView.module.css"), "utf8");
    expect(css).toMatch(/\.table \{ width: 100%; max-width: calc\(var\(--stream-max\) \+ 200px\); margin-inline: auto; \}/);
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

    expect(screen.getByText("Active hotel")).toBeInTheDocument();
    expect(screen.getByText("Working · content")).toBeInTheDocument();
    expect(screen.getAllByText("Idle")).toHaveLength(1);
    expect(screen.getAllByText("Idle")[0].closest("button")).toBeNull();
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

  it("groups working first, then queued, idle and paused", () => {
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
      "Older idle",
      "Fresh paused",
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

    fireEvent.click(screen.getByRole("button", { name: "Active, 1" }));
    expect(screen.getByText("Active hotel")).toBeInTheDocument();
    expect(screen.queryByText("Finished hotel")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "All, 4" }));
    fireEvent.change(screen.getByRole("searchbox", { name: "Search workgroups" }), {
      target: { value: "paused" },
    });
    expect(screen.getByText("Paused hotel")).toBeInTheDocument();
    expect(screen.queryByText("Active hotel")).not.toBeInTheDocument();

    fireEvent.change(screen.getByRole("searchbox", { name: "Search workgroups" }), {
      target: { value: "" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Queued, 1" }));
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

  it("lights a running row's phase cell in the colour of the profile that owns the phase and names it in the status", () => {
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
    expect(glyph.style.getPropertyValue("--wg-lit-light")).toBe(nameTone("#f36a8a", palettes.light.bgPane));
    expect(screen.getByText("Working · media · @lingo")).toBeInTheDocument();
  });

  it("sets workgroup names in the same row type as a profile row, never bold, the name face or the hub's tone", () => {
    render(<WorkgroupsView workgroups={WORKGROUPS} profiles={[{ name: "mira", accent: "#3388ff" }]} />);
    const active = screen.getByText("Active hotel");
    expect(active.tagName).toBe("SPAN");
    expect(active.className).toBe("sb-name");
    expect(active.getAttribute("style")).toBeNull();
  });

  it("counts a workgroup with a live run and no pipeline status as working", () => {
    render(
      <WorkgroupsView
        workgroups={[{ id: "wg-r", name: "Running hotel", profile: "mira", mtime: 1 }, { id: "wg-i", name: "Idle hotel", profile: "mira", mtime: 2 }]}
        runByWorkgroup={{ "mira/wg-r": { phase: "media", phasesDone: 1, phasesTotal: 3 } }}
      />,
    );
    expect(screen.getByRole("button", { name: "Active, 1" })).toBeEnabled();
    expect(screen.getByRole("group", { name: "Working" }).textContent).toContain("Running hotel");
    expect(screen.getByText("Working · media")).toBeInTheDocument();
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
    const needs = screen.getByText("Needs you · approval · @yuri").parentElement;
    expect(needs.className).toMatch(/status_needs/);
    expect(needs.className).not.toMatch(/status_error/);
    expect(screen.getByText("Needs attention").parentElement.className).toMatch(/status_error/);
    expect(screen.getByRole("button", { name: "Active, 2" })).toBeInTheDocument();
    const css = readFileSync(join(import.meta.dirname, "WorkgroupsView.module.css"), "utf8");
    expect(css).toContain(".status_needs { color: var(--c-warning-text); }");
    expect(css).toContain(".status_needs > .dot { background: var(--c-warning); }");
    expect(css).toContain(".status_error > .dot { background: var(--c-danger); }");
  });

  it("takes the step and its owner from the same phase", () => {
    const wg = {
      id: "wg-r", name: "Running hotel", profile: "mira", pipeline_status: "running", pipeline_phase: "content",
      phase_map: { content: { owner: "quill" }, media: { owner: "lingo" } }, mtime: 3,
    };
    render(<WorkgroupsView workgroups={[wg]} runByWorkgroup={{ "mira/wg-r": { phase: "media", phasesDone: 1, phasesTotal: 3 } }} />);
    expect(screen.getByText("Working · media · @lingo")).toBeInTheDocument();
  });

  it("sets the member count and the spend under their right-aligned headings, at the meta size", () => {
    render(<WorkgroupsView workgroups={[WORKGROUPS[0]]} profiles={[]} />);
    const css = readFileSync(join(import.meta.dirname, "WorkgroupsView.module.css"), "utf8");
    expect(css).toContain(".tableHead span:nth-child(n + 3) { text-align: right; }");
    expect(css).toContain(".num { min-width: 0; text-align: right; color: var(--ink-2); font-size: var(--text-meta); }");
    expect(css).toContain(".updated { text-align: right;");
    const row = screen.getByText("Active hotel").closest("button");
    expect([...row.children].slice(2).map((cell) => cell.textContent)).toEqual(["7", "$1.20", expect.any(String)]);
    expect([...row.children].slice(2, 4).map((cell) => cell.className)).toEqual([`tnum ${styles.num}`, `tnum ${styles.num}`]);
    expect(row.children[4].className).toBe(styles.updated);
  });

  it("sets each filter count in its own quiet class, and no rule waits for a mono or tnum element", () => {
    render(<WorkgroupsView workgroups={[WORKGROUPS[0]]} profiles={[]} />);
    const css = readFileSync(join(import.meta.dirname, "WorkgroupsView.module.css"), "utf8");
    expect(css).toContain(".segCount { margin-left: var(--sp-4); color: var(--ink-3);");
    expect(screen.getByRole("button", { name: "All, 1" }).querySelector("span").className).toBe(styles.segCount);
    expect(css).not.toMatch(/:global\(\.(mono|tnum)\)/);
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
