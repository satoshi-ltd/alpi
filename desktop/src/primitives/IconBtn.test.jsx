import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import IconBtn from "./IconBtn.jsx";

describe("IconBtn", () => {
  it("wraps in a tooltip when tip is provided", () => {
    render(<IconBtn tip="Save"><svg /></IconBtn>);
    expect(screen.getByText("Save")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save" })).toBeInTheDocument();
  });

  it("keeps aria-label as the accessible name over tip", () => {
    render(<IconBtn tip="Save changes" aria-label="Save"><svg /></IconBtn>);
    expect(screen.getByRole("button", { name: "Save" })).toBeInTheDocument();
    expect(screen.getByText("Save changes")).toBeInTheDocument();
  });

  it("renders no tooltip wrapper without tip", () => {
    render(<IconBtn aria-label="Close"><svg /></IconBtn>);
    const btn = screen.getByRole("button", { name: "Close" });
    expect(btn.parentElement?.className ?? "").not.toContain("ds-tip");
    expect(screen.queryByText("Close")).toBeNull();
  });
});
