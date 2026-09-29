import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import BudgetEdit, { parseBudget } from "./BudgetEdit.jsx";

globalThis.ResizeObserver ??= class { observe() {} unobserve() {} disconnect() {} };

const openEditor = (props) => {
  render(<BudgetEdit value={10} {...props} />);
  fireEvent.click(screen.getByText("$10.00"));
  return screen.getByPlaceholderText("empty = unlimited");
};

describe("BudgetEdit", () => {
  it("parses empty as no cap and rejects zero, negatives and text", () => {
    expect(parseBudget(" ")).toEqual({ valid: true, next: null });
    expect(parseBudget("2.5")).toEqual({ valid: true, next: 2.5 });
    for (const bad of ["0", "-1", "ten"]) expect(parseBudget(bad).valid).toBe(false);
  });

  it("clears the cap with an empty value", async () => {
    const onSave = vi.fn(async () => {});
    fireEvent.change(openEditor({ onSave }), { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(onSave).toHaveBeenCalledWith(null));
  });

  it("explains an invalid value and keeps Save disabled", () => {
    fireEvent.change(openEditor({ onSave: vi.fn() }), { target: { value: "-3" } });
    expect(screen.getByText(/Enter a positive number/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
  });

  it("stays open when the save fails", async () => {
    const onSave = vi.fn(async () => { throw new Error("nope"); });
    fireEvent.change(openEditor({ onSave }), { target: { value: "4" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(onSave).toHaveBeenCalledWith(4));
    expect(screen.getByPlaceholderText("empty = unlimited")).toBeInTheDocument();
  });
});
