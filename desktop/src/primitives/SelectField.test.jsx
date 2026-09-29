import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import SelectField from "./SelectField.jsx";

const OPTIONS = [
  { value: "connection", label: "Shared across its devices" },
  { value: "device", label: "Private to each device", caption: "each device keeps its own thread" },
];

describe("SelectField", () => {
  it("names the control, shows the current option and highlights it in the menu", () => {
    render(<SelectField aria-label="Session scope" value="device" options={OPTIONS} onChange={() => {}} />);
    const trigger = screen.getByRole("button", { name: "Session scope" });
    expect(trigger).toHaveTextContent("Private to each device");
    fireEvent.click(trigger);
    const active = screen.getByRole("button", { name: /Private to each device/ });
    expect(active.className).toMatch(/rowActive/);
    expect(screen.getByText("each device keeps its own thread")).toBeInTheDocument();
  });

  it("reports the picked value and closes", () => {
    const onChange = vi.fn();
    render(<SelectField aria-label="Session scope" value="connection" options={OPTIONS} onChange={onChange} />);
    fireEvent.click(screen.getByRole("button", { name: "Session scope" }));
    fireEvent.click(screen.getByText("Private to each device"));
    expect(onChange).toHaveBeenCalledWith("device");
    expect(screen.queryByText("each device keeps its own thread")).not.toBeInTheDocument();
  });

  it("stays shut while disabled", () => {
    render(<SelectField aria-label="Session scope" value="connection" options={OPTIONS} disabled />);
    const trigger = screen.getByRole("button", { name: "Session scope" });
    expect(trigger).toBeDisabled();
  });
});
