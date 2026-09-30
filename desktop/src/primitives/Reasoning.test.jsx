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

  it("streaming with no trace yet is a polite live status, not a dead button", () => {
    render(<Reasoning text="" streaming />);
    expect(screen.queryByRole("button")).toBeNull();
    const status = screen.getByRole("status");
    expect(status).toHaveAttribute("aria-live", "polite");
    expect(status.textContent).toContain("Thinking…");
  });

  it("each row is named by its visible label and carries state in aria-expanded", () => {
    render(<Reasoning text="plan" seconds={3} />);
    const btn = screen.getByRole("button", { name: "Thought for 3s" });
    expect(btn).not.toHaveAttribute("aria-label");
    expect(btn).toHaveAttribute("aria-expanded", "false");
  });

  it("a stored span with seconds but no text still shows its row, without a toggle", () => {
    render(<Reasoning text="" seconds={4} />);
    expect(screen.queryByRole("button")).toBeNull();
    expect(screen.getByText("Thought for 4s")).toBeTruthy();
  });

  it("the merged legacy row lays its trace out with tool markers between segments", () => {
    const timeline = [
      { kind: "text", text: "read the log" },
      { kind: "tools", names: ["read_file"] },
      { kind: "text", text: "now summarize" },
    ];
    const { container } = render(<Reasoning text={"read the log\n\nnow summarize"} seconds={3} timeline={timeline} />);
    fireEvent.click(screen.getByRole("button"));
    const text = container.textContent;
    expect(text.indexOf("read the log")).toBeLessThan(text.indexOf("read_file"));
    expect(text.indexOf("read_file")).toBeLessThan(text.indexOf("now summarize"));
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

  it("opens to this span's own text only", () => {
    const { container } = render(<Reasoning text={"read the log\n\nnow summarize"} seconds={3} />);
    fireEvent.click(screen.getByRole("button"));
    expect([...container.querySelectorAll("p")].map((p) => p.textContent)).toEqual(["read the log", "now summarize"]);
  });
});
