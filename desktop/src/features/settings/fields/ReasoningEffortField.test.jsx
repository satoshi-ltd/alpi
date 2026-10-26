import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

import { ReasoningEffortField } from "./ReasoningEffortField.jsx";

describe("ReasoningEffortField", () => {
  it("highlights the current effort in the menu and reports a new pick", () => {
    const onChange = vi.fn();
    render(<ReasoningEffortField value="medium" onChange={onChange} />);
    fireEvent.click(screen.getByRole("button", { name: "Medium" }));
    const rows = screen.getAllByRole("menuitemradio");
    const active = rows.filter((b) => b.getAttribute("aria-checked") === "true");
    expect(active.map((b) => b.textContent)).toEqual(["Mediumbalanced"]);
    expect(active[0].className).toMatch(/rowSelected/);
    fireEvent.click(screen.getByText("High"));
    expect(onChange).toHaveBeenCalledWith("high");
  });
});
