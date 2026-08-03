import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import TasksButton from "./TasksButton.jsx";

const HUB = "hub-pubkey";

describe("TasksButton", () => {
  it("opens task history when openTick changes", () => {
    const thread = [
      { seq: 1, from_pubkey: HUB, body: "#task #qa Review launch" },
      { seq: 2, from_pubkey: HUB, body: "#done passed" },
    ];
    const { rerender } = render(
      <TasksButton thread={thread} hubPubkey={HUB} openTick={0} />,
    );

    expect(screen.queryByText("Task history")).not.toBeInTheDocument();

    rerender(<TasksButton thread={thread} hubPubkey={HUB} openTick={1} />);

    expect(screen.getByText("Task history")).toBeInTheDocument();
    expect(screen.getByText("Review launch")).toBeInTheDocument();
  });

  it("does not auto-open task history from a stale tick on mount", () => {
    const thread = [
      { seq: 1, from_pubkey: HUB, body: "#task #qa Review launch" },
      { seq: 2, from_pubkey: HUB, body: "#done passed" },
    ];

    render(<TasksButton thread={thread} hubPubkey={HUB} openTick={1} />);

    expect(screen.queryByText("Task history")).not.toBeInTheDocument();
    expect(screen.queryByText("Review launch")).not.toBeInTheDocument();
  });
});

const MIXED = [
  { seq: 1, from_pubkey: HUB, body: "#task #media-config wire the logo" },
  { seq: 2, from_pubkey: HUB, body: "#done skipped · no config change needed" },
  { seq: 3, from_pubkey: HUB, body: "#task #media-build rebuild" },
  { seq: 4, from_pubkey: HUB, body: "#done BLOCKED · the template cannot build" },
];

function glyphOf(label) {
  return screen.getByText(label).closest("button").firstElementChild;
}

describe("TasksButton outcome vocabulary", () => {
  it("a blocked close never reads or draws as success", () => {
    const { rerender } = render(<TasksButton thread={MIXED} hubPubkey={HUB} openTick={0} />);

    const glyph = glyphOf("Blocked at #media-build");
    expect(screen.queryByText("All tasks resolved")).toBeNull();
    expect(screen.getByText("2/2")).toBeInTheDocument();
    expect(glyph.querySelector("circle")).not.toBeNull();
    expect(glyph.getAttribute("style")).toContain("--c-danger");

    rerender(<TasksButton thread={MIXED} hubPubkey={HUB} openTick={1} />);
    expect(screen.getByText("2/2 closed · 1 blocked")).toBeInTheDocument();
    expect(screen.queryByText("2/2 done")).toBeNull();
    expect(screen.getByText("blocked")).toBeInTheDocument();
    expect(screen.getByText("skipped")).toBeInTheDocument();
  });

  it("names the block that is still the latest outcome", () => {
    const thread = [
      ...MIXED,
      { seq: 5, from_pubkey: HUB, body: "#task #media-qa audit" },
      { seq: 6, from_pubkey: HUB, body: "#done BLOCKED · nothing to audit" },
    ];
    render(<TasksButton thread={thread} hubPubkey={HUB} openTick={0} />);
    expect(screen.getByText("Blocked at #media-qa")).toBeInTheDocument();
    expect(screen.queryByText("All tasks resolved")).toBeNull();
  });

  it("a block that was re-tasked and closed green no longer reads as blocked", () => {
    const thread = [
      { seq: 1, from_pubkey: HUB, body: "#task #enrich research" },
      { seq: 2, from_pubkey: HUB, body: "#done BLOCKED · no photos" },
      { seq: 3, from_pubkey: HUB, body: "#task #enrich-retry research again" },
      { seq: 4, from_pubkey: HUB, body: "#done enrich green" },
    ];
    render(<TasksButton thread={thread} hubPubkey={HUB} openTick={0} />);
    expect(screen.queryByText(/Blocked at/)).toBeNull();
    expect(screen.getByText("All tasks closed")).toBeInTheDocument();
  });

  it("a skipped-only history counts as closed but never as done", () => {
    const thread = MIXED.slice(0, 2);
    const { rerender } = render(<TasksButton thread={thread} hubPubkey={HUB} openTick={0} />);

    const glyph = glyphOf("All tasks closed");
    expect(screen.queryByText("All tasks resolved")).toBeNull();
    // skipped is the `x`; only blocked draws the ban circle.
    expect(glyph.querySelector("circle")).toBeNull();
    expect(glyph.querySelectorAll("path")).toHaveLength(2);
    expect(glyph.getAttribute("style")).toContain("--c-warning");

    rerender(<TasksButton thread={thread} hubPubkey={HUB} openTick={1} />);
    expect(screen.getByText("1/1 closed")).toBeInTheDocument();
    expect(screen.queryByText("1/1 done")).toBeNull();
    expect(screen.getByText("skipped")).toBeInTheDocument();
  });

  it("a preempted task counts as closed but never as done", () => {
    const thread = [
      { seq: 1, from_pubkey: HUB, body: "#task #first go" },
      { seq: 2, from_pubkey: HUB, body: "#task #second go" },
      { seq: 3, from_pubkey: HUB, body: "#done second green" },
    ];
    const { rerender } = render(<TasksButton thread={thread} hubPubkey={HUB} openTick={0} />);

    expect(screen.getByText("All tasks closed")).toBeInTheDocument();

    rerender(<TasksButton thread={thread} hubPubkey={HUB} openTick={1} />);
    expect(screen.getByText("2/2 closed")).toBeInTheDocument();
    expect(screen.getByText("preempted")).toBeInTheDocument();
    expect(screen.getByText("done")).toBeInTheDocument();
  });

  it("an all-green history still reads resolved and draws the check", () => {
    const thread = [
      { seq: 1, from_pubkey: HUB, body: "#task #qa Review launch" },
      { seq: 2, from_pubkey: HUB, body: "#done passed" },
    ];
    const { rerender } = render(<TasksButton thread={thread} hubPubkey={HUB} openTick={0} />);

    const glyph = glyphOf("All tasks resolved");
    expect(glyph.querySelector("circle")).toBeNull();
    expect(glyph.querySelectorAll("path")).toHaveLength(1);

    rerender(<TasksButton thread={thread} hubPubkey={HUB} openTick={1} />);
    expect(screen.getByText("1/1 done")).toBeInTheDocument();
  });

  it("prefers the canonical rows over the loaded thread", () => {
    render(
      <TasksButton
        thread={[]}
        hubPubkey={HUB}
        openTick={0}
        tasks={[
          { seq: 41, slug: "setup", title: "", status: "done" },
          { seq: 43, slug: "enrich", title: "", status: "blocked" },
        ]}
      />,
    );

    expect(screen.getByText("Blocked at #enrich")).toBeInTheDocument();
    expect(screen.queryByText("No tasks yet")).toBeNull();
  });

  it("keeps a canonical row jumpable by its daemon seq", () => {
    const onJump = vi.fn();
    const { rerender } = render(
      <TasksButton
        thread={[]}
        hubPubkey={HUB}
        openTick={0}
        onJump={onJump}
        tasks={[{ seq: 41, slug: "setup", title: "", status: "done" }]}
      />,
    );
    rerender(
      <TasksButton
        thread={[]}
        hubPubkey={HUB}
        openTick={1}
        onJump={onJump}
        tasks={[{ seq: 41, slug: "setup", title: "", status: "done" }]}
      />,
    );

    fireEvent.click(screen.getByText("setup"));
    expect(onJump).toHaveBeenCalledWith(41);
  });
});

describe("TasksButton capped history", () => {
  const rows = Array.from({ length: 20 }, (_, i) => ({
    seq: i + 1, slug: `p${i}`, title: "", status: "done",
  }));

  it("does not present a full fold window as the whole history", () => {
    const { rerender } = render(
      <TasksButton thread={[]} hubPubkey={HUB} openTick={0} tasks={rows} historyCapped />,
    );
    rerender(
      <TasksButton thread={[]} hubPubkey={HUB} openTick={1} tasks={rows} historyCapped />,
    );
    expect(screen.getByText("20/20 done · recent history")).toBeInTheDocument();
  });

  it("claims the whole history when the window is not full", () => {
    const short = rows.slice(0, 3);
    const { rerender } = render(
      <TasksButton thread={[]} hubPubkey={HUB} openTick={0} tasks={short} />,
    );
    rerender(<TasksButton thread={[]} hubPubkey={HUB} openTick={1} tasks={short} />);
    expect(screen.getByText("3/3 done")).toBeInTheDocument();
  });
});
