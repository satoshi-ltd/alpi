import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
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
