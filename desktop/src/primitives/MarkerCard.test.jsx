import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import MarkerCard from "./MarkerCard.jsx";

describe("MarkerCard close outcomes", () => {
  it.each([
    ["blocked", "BLOCKED"],
    ["skipped", "SKIPPED"],
    ["preempted", "PREEMPTED"],
  ])("a %s close never reads as a green DONE", (outcome, label) => {
    const { container } = render(
      <MarkerCard variant="done" outcome={outcome} taskId="t1" title="qa" />,
    );
    expect(screen.getByText(label)).toBeInTheDocument();
    expect(screen.queryByText("DONE")).toBeNull();
    expect(container.querySelector("svg path[d^='M20 6']")).toBeNull();
  });

  it("a plain done close keeps the check and the DONE label", () => {
    render(<MarkerCard variant="done" outcome="done" taskId="t2" title="qa" />);
    expect(screen.getByText("DONE")).toBeInTheDocument();
  });
});
