import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

import Reasoning, { thoughtLabel } from "./Reasoning.jsx";

describe("thoughtLabel", () => {
  it("omits the duration when reasoned_s is missing or sub-second", () => {
    expect(thoughtLabel(null)).toBe("Thought");
    expect(thoughtLabel(undefined)).toBe("Thought");
    expect(thoughtLabel(0)).toBe("Thought");
    expect(thoughtLabel(0.4)).toBe("Thought");
  });
  it("shows the duration for a real value", () => {
    expect(thoughtLabel(11)).toBe("Thought for 11s");
    expect(thoughtLabel(90)).toBe("Thought for 1m 30s");
  });
});

describe("Reasoning", () => {
  it("renders nothing for blank finished text", () => {
    const { container } = render(<Reasoning text="   " />);
    expect(container.firstChild).toBeNull();
  });

  it("streaming shows the Thinking label even before any trace text", () => {
    render(<Reasoning text="" streaming />);
    expect(screen.getByRole("button").textContent).toContain("Thinking…");
  });

  it("streaming peeks the latest line while collapsed and expands to the full trace", () => {
    render(<Reasoning text={"line one\nline two"} streaming />);
    const btn = screen.getByRole("button");
    expect(btn.textContent).toContain("Thinking…");
    expect(screen.getByText("line two")).toBeTruthy();
    expect(screen.queryByText("line one")).toBeNull();
    fireEvent.click(btn);
    expect(screen.getByText("line one")).toBeTruthy();
  });

  it("the open live trace is readable by assistive tech and scrolls instead of clipping", () => {
    const { container } = render(<Reasoning text={"a\nb"} streaming />);
    fireEvent.click(screen.getByRole("button"));
    expect(container.querySelector("[aria-hidden='true'] p")).toBeNull();
    expect(screen.getByText("a").tagName).toBe("P");
  });

  it("finished is collapsed, labelled, and expands on click", () => {
    render(<Reasoning text={"alpha\nbeta"} seconds={11} />);
    const btn = screen.getByRole("button");
    expect(btn.textContent).toContain("Thought for 11s");
    expect(screen.queryByText("alpha")).toBeNull();
    fireEvent.click(btn);
    expect(screen.getByText("alpha")).toBeTruthy();
  });

  it("finished with no reasoned_s never reads 'Thought for 0s'", () => {
    render(<Reasoning text="x" seconds={0} />);
    const btn = screen.getByRole("button");
    expect(btn.textContent).toContain("Thought");
    expect(btn.textContent).not.toContain("0s");
  });

  it("collapses to the Thought row when reasoning ends, keeping the open state until the answer lands", () => {
    const { rerender } = render(<Reasoning text="plan" streaming />);
    fireEvent.click(screen.getByRole("button"));
    rerender(<Reasoning text="plan" seconds={7} />);
    const btn = screen.getByRole("button");
    expect(btn.textContent).toContain("Thought for 7s");
    expect(btn).toHaveAttribute("aria-expanded", "true");
    rerender(<Reasoning text="plan" seconds={7} answered />);
    expect(screen.getByRole("button")).toHaveAttribute("aria-expanded", "false");
  });

  it("lays the trace out in order with the tool steps between segments", () => {
    const timeline = [
      { kind: "text", text: "read the log" },
      { kind: "tools", names: ["read_file"] },
      { kind: "text", text: "now summarize" },
    ];
    const { container } = render(<Reasoning text="read the log\n\nnow summarize" seconds={3} timeline={timeline} />);
    fireEvent.click(screen.getByRole("button"));
    const text = container.textContent;
    expect(text.indexOf("read the log")).toBeLessThan(text.indexOf("read_file"));
    expect(text.indexOf("read_file")).toBeLessThan(text.indexOf("now summarize"));
  });
});
