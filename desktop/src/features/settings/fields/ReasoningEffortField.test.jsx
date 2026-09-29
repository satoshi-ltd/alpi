import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

import { ReasoningEffortField } from "./ReasoningEffortField.jsx";

describe("ReasoningEffortField", () => {
  it("highlights the current effort in the menu and reports a new pick", () => {
    const onChange = vi.fn();
    render(<ReasoningEffortField value="medium" onChange={onChange} />);
    fireEvent.click(screen.getByRole("button", { name: "Medium" }));
    const rows = screen.getAllByRole("button").filter((b) => /rowActive|row\b/.test(b.className));
    const active = rows.filter((b) => /rowActive/.test(b.className));
    expect(active.map((b) => b.textContent)).toEqual(["Mediumbalanced"]);
    fireEvent.click(screen.getByText("High"));
    expect(onChange).toHaveBeenCalledWith("high");
  });
});
