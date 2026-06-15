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
  it("renders nothing for blank text", () => {
    const { container } = render(<Reasoning text="   " />);
    expect(container.firstChild).toBeNull();
  });

  it("streaming shows the live thinking label", () => {
    render(<Reasoning text={"line one\nline two"} streaming />);
    expect(screen.getByText(/thinking/)).toBeTruthy();
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
});
