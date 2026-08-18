import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import AlpiPicker from "./AlpiPicker.jsx";

const PROFILES = [
  { name: "default", accent: "#b8954a" },
  { name: "pixel", accent: "#446" },
];

describe("AlpiPicker", () => {
  it("calls the entity a profile in the search placeholder and empty state", () => {
    render(<AlpiPicker profiles={PROFILES} activeAlpi="pixel" onChange={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: /pixel/ }));

    const search = screen.getByPlaceholderText("Find profile…");
    fireEvent.change(search, { target: { value: "zzz" } });
    expect(screen.getByText("No profiles match")).toBeInTheDocument();
  });

  it("keeps alpi as the display label of the default profile", () => {
    render(<AlpiPicker profiles={PROFILES} activeAlpi="default" onChange={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: /alpi/ }));

    expect(screen.getAllByText("alpi").length).toBeGreaterThan(0);
    expect(screen.queryByText("default")).not.toBeInTheDocument();
  });
});
